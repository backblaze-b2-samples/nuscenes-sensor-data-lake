"""Scene domain tests.

Hermetic: an in-memory fake S3 stands in for B2 (conftest forbids external
network), but the nuScenes devkit runs for real against the materialized
dataset — so `serve_frame` exercises the genuine `NuScenes(...)` load and
`LidarPointCloud.from_file` compute, not a mock.
"""

from datetime import UTC, datetime

import pytest
from botocore.exceptions import ClientError

from app.repo import nuscenes_lake


class _Body:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data


class FakeS3:
    """Minimal in-memory S3 covering exactly what nuscenes_lake calls."""

    def __init__(self):
        self.store: dict[str, bytes] = {}

    def put_object(self, Bucket, Key, Body, ContentType=None):
        data = Body if isinstance(Body, (bytes, bytearray)) else Body.read()
        self.store[Key] = bytes(data)

    def get_object(self, Bucket, Key):
        if Key not in self.store:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return {"Body": _Body(self.store[Key])}

    def list_objects_v2(self, Bucket, Prefix="", MaxKeys=1000, ContinuationToken=None):
        contents = [
            {"Key": key, "Size": len(value), "LastModified": datetime.now(UTC)}
            for key, value in self.store.items()
            if key.startswith(Prefix)
        ]
        return {"Contents": contents, "IsTruncated": False}

    def delete_objects(self, Bucket, Delete):
        for obj in Delete["Objects"]:
            self.store.pop(obj["Key"], None)
        return {}


@pytest.fixture
def fake_lake(monkeypatch):
    fake = FakeS3()
    monkeypatch.setattr(nuscenes_lake, "get_s3_client", lambda: fake)
    monkeypatch.setattr(
        nuscenes_lake, "get_presigned_url", lambda key, **_: f"https://example.test/{key}"
    )
    monkeypatch.setattr(nuscenes_lake, "_invalidate_list_cache", lambda: None)
    return fake


DEFAULT_BODY = {
    "name": "scene-boston-01",
    "description": "demo capture",
    "location": "boston-seaport",
    "time_of_day": "night",
    "weather": "rain",
    "keyframes": 5,
    "sensor_suite": "full",
}


async def _create(client, **overrides):
    body = {**DEFAULT_BODY, **overrides}
    resp = await client.post("/scenes", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_create_ingests_full_suite(client, fake_lake):
    scene = await _create(client)
    # 12-channel full suite x 5 keyframes = 60 sensor blobs.
    assert scene["blob_count"] == 60
    assert len(scene["channels"]) == 12
    assert scene["location"] == "boston-seaport"
    # 13 annotation tables + a map mask + meta are all in the B2 store.
    keys = list(fake_lake.store)
    assert any(k.endswith("/v1.0-demo/sample_data.json") for k in keys)
    assert any(k.endswith("/lake-meta.json") for k in keys)
    assert any("/samples/LIDAR_TOP/" in k for k in keys)


async def test_camera_lidar_suite_has_three_channels(client, fake_lake):
    scene = await _create(client, sensor_suite="camera+lidar", keyframes=3)
    assert len(scene["channels"]) == 3
    assert scene["blob_count"] == 9  # 3 channels x 3 keyframes


async def test_invalid_keyframes_rejected(client, fake_lake):
    resp = await client.post("/scenes", json={**DEFAULT_BODY, "keyframes": 7})
    assert resp.status_code == 400


async def test_list_and_detail(client, fake_lake):
    created = await _create(client)
    listed = (await client.get("/scenes")).json()
    assert any(s["token"] == created["token"] for s in listed)

    detail = (await client.get(f"/scenes/{created['token']}")).json()
    assert detail["blob_count"] == 60
    assert len(detail["blobs"]) == 60
    modalities = {b["modality"] for b in detail["blobs"]}
    assert modalities == {"camera", "lidar", "radar"}


async def test_serve_frame_runs_real_devkit(client, fake_lake):
    scene = await _create(client)
    resp = await client.post(f"/scenes/{scene['token']}/frame?keyframe=1")
    assert resp.status_code == 200, resp.text
    manifest = resp.json()

    assert manifest["keyframe_index"] == 1
    assert manifest["num_keyframes"] == 5
    assert len(manifest["frames"]) == 12
    assert manifest["num_annotations"] == 2  # one per category, per keyframe
    assert manifest["devkit_version"]
    # Every resolved channel carries a presigned URL.
    assert all(frame["url"].startswith("https://example.test/") for frame in manifest["frames"])
    # Real point-cloud stats from LidarPointCloud.from_file.
    stats = manifest["lidar_stats"]
    assert stats is not None
    assert stats["num_points"] == 60
    assert stats["x_max"] >= stats["x_min"]


async def test_update_rewrites_metadata_and_tables(client, fake_lake):
    scene = await _create(client)
    resp = await client.post(
        f"/scenes/{scene['token']}",
        json={
            "name": "scene-renamed",
            "description": "updated",
            "location": "singapore-onenorth",
            "time_of_day": "day",
            "weather": "clear",
        },
    )
    assert resp.status_code == 200, resp.text
    updated = resp.json()
    assert updated["name"] == "scene-renamed"
    assert updated["location"] == "singapore-onenorth"

    # The real nuScenes tables were rewritten too.
    log_rows = nuscenes_lake.read_table(scene["token"], "log")
    assert log_rows[0]["location"] == "singapore-onenorth"


async def test_delete_is_prefix_scoped(client, fake_lake):
    keep = await _create(client, name="keeper")
    doomed = await _create(client, name="doomed")

    resp = await client.request("DELETE", f"/scenes/{doomed['token']}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["objects_removed"] > 0

    # The other scene's objects are untouched (delete was prefix-scoped).
    assert (await client.get(f"/scenes/{doomed['token']}")).status_code == 404
    assert (await client.get(f"/scenes/{keep['token']}")).status_code == 200
    assert any(k.startswith(f"nuscenes/{keep['token']}/") for k in fake_lake.store)


async def test_lake_stats(client, fake_lake):
    await _create(client, name="s1", keyframes=5, sensor_suite="full")
    await _create(client, name="s2", keyframes=3, sensor_suite="camera+lidar")

    stats = (await client.get("/scenes/stats")).json()
    assert stats["total_scenes"] == 2
    assert stats["total_keyframes"] == 8
    # full: 5x6 cameras=30, 5 lidar, 5x5 radar=25; camera+lidar: 3 camera, 3 lidar, 3 radar.
    assert stats["blobs_by_modality"]["camera"] == 33
    assert stats["blobs_by_modality"]["lidar"] == 8
    assert stats["blobs_by_modality"]["radar"] == 28
    assert stats["total_blobs"] == 69
