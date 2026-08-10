"""Scene lifecycle orchestration (the AV multi-sensor data lake).

Coordinates the repo adapters — synthetic generation (`scene_synth`), B2 storage
(`nuscenes_lake`) and the real devkit (`nuscenes_devkit`) — into the create /
read / edit / delete / run verbs the routes expose. No boto3 or `nuscenes`
imports here: those stay in repo/.
"""

from __future__ import annotations

import re
from uuid import uuid4

from app.repo import nuscenes_devkit as devkit
from app.repo import nuscenes_lake as lake
from app.repo import scene_synth
from app.types.formatting import humanize_bytes
from app.types.scenes import (
    ChannelFrame,
    FrameManifest,
    LakeStats,
    ModalityBreakdown,
    PointCloudStats,
    SceneCreateRequest,
    SceneDetail,
    SceneSummary,
    SceneUpdateRequest,
    SensorBlob,
)

KEYFRAME_CHOICES = (3, 5, 10)


class SceneError(Exception):
    """Invalid scene request (bad slug, unknown scene, bad keyframe choice)."""

    def __init__(self, detail: str, status: int = 400):
        self.detail = detail
        self.status = status
        super().__init__(detail)


class SceneNotFoundError(SceneError):
    def __init__(self, token: str):
        super().__init__(f"Scene '{token}' not found", status=404)


_SLUG_RE = re.compile(r"[^a-z0-9]+")
_VALID_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")


def _slugify(name: str) -> str:
    base = _SLUG_RE.sub("-", name.strip().lower()).strip("-") or "scene"
    return f"{base[:48]}-{uuid4().hex[:6]}"


def _validate_token(token: str) -> None:
    if not _VALID_SLUG_RE.match(token):
        raise SceneError("Invalid scene token")


def _modality_of(channel: str) -> str:
    return scene_synth.modality_of(channel)


def create_scene(req: SceneCreateRequest) -> SceneSummary:
    if req.keyframes not in KEYFRAME_CHOICES:
        raise SceneError(f"keyframes must be one of {KEYFRAME_CHOICES}")
    slug = _slugify(req.name)
    tables, blobs = scene_synth.generate_scene(
        name=req.name,
        description=req.description,
        location=req.location,
        time_of_day=req.time_of_day,
        weather=req.weather,
        keyframes=req.keyframes,
        sensor_suite=req.sensor_suite,
    )
    channels = scene_synth.channels_for(req.sensor_suite)
    meta = {
        "token": slug,
        "name": req.name,
        "description": req.description,
        "location": req.location,
        "time_of_day": req.time_of_day,
        "weather": req.weather,
        "sensor_suite": req.sensor_suite,
        "keyframes": req.keyframes,
        "channels": channels,
        "created_at": lake.utc_now_iso(),
    }
    lake.put_scene(slug, tables, blobs, meta)
    return _summary_from_meta(meta, lake.list_sensor_blobs(slug))


def list_scenes() -> list[SceneSummary]:
    summaries = []
    for meta in lake.list_scene_metas():
        blobs = lake.list_sensor_blobs(meta["token"])
        summaries.append(_summary_from_meta(meta, blobs))
    return summaries


def get_scene(token: str) -> SceneDetail:
    _validate_token(token)
    meta = lake.read_meta(token)
    if meta is None:
        raise SceneNotFoundError(token)
    raw_blobs = lake.list_sensor_blobs(token)
    summary = _summary_from_meta(meta, raw_blobs)
    blobs = [
        SensorBlob(
            channel=_channel_of(b["filename"]),
            modality=_modality_of(_channel_of(b["filename"])),
            key=b["key"],
            filename=b["filename"],
            size_bytes=b["size_bytes"],
            size_human=b["size_human"],
            content_type=b["content_type"],
        )
        for b in raw_blobs
    ]
    return SceneDetail(**summary.model_dump(), blobs=blobs)


def update_scene(token: str, req: SceneUpdateRequest) -> SceneSummary:
    _validate_token(token)
    meta = lake.read_meta(token)
    if meta is None:
        raise SceneNotFoundError(token)

    meta.update(
        {
            "name": req.name,
            "description": req.description,
            "location": req.location,
            "time_of_day": req.time_of_day,
            "weather": req.weather,
        }
    )
    lake.write_meta(token, meta)

    # Keep the real nuScenes tables in sync so the devkit reads the new metadata.
    scene_rows = lake.read_table(token, "scene")
    if scene_rows:
        scene_rows[0]["name"] = req.name
        scene_rows[0]["description"] = scene_synth.scene_description(
            req.description, req.time_of_day, req.weather
        )
        lake.write_table(token, "scene", scene_rows)
    log_rows = lake.read_table(token, "log")
    if log_rows:
        log_rows[0]["location"] = req.location
        lake.write_table(token, "log", log_rows)

    return _summary_from_meta(meta, lake.list_sensor_blobs(token))


def delete_scene(token: str) -> int:
    _validate_token(token)
    if lake.read_meta(token) is None:
        raise SceneNotFoundError(token)
    return lake.delete_scene(token)


def serve_frame(token: str, keyframe_index: int = 0) -> FrameManifest:
    """Index the scene with the real devkit, resolve a keyframe's sensors,
    presign each blob, and compute real LiDAR point-cloud stats."""
    _validate_token(token)
    meta = lake.read_meta(token)
    if meta is None:
        raise SceneNotFoundError(token)

    dataroot = lake.materialize_dataroot(token)
    nusc = devkit.build_index(dataroot)
    frame = devkit.resolve_frame(nusc, keyframe_index)

    channel_frames: list[ChannelFrame] = []
    lidar_stats: PointCloudStats | None = None
    blob_index = {b["filename"]: b for b in lake.list_sensor_blobs(token)}

    for ch in frame["channels"]:
        key = f"{lake.scene_prefix(token)}{ch['filename']}"
        blob = blob_index.get(ch["filename"], {})
        size = blob.get("size_bytes", 0)
        channel_frames.append(
            ChannelFrame(
                channel=ch["channel"],
                modality=ch["modality"],
                filename=ch["filename"],
                key=key,
                url=lake.presign_key(key, disposition="inline"),
                content_type=blob.get("content_type", "application/octet-stream"),
                size_bytes=size,
                size_human=humanize_bytes(size),
            )
        )
        if ch["modality"] == "lidar" and lidar_stats is None:
            local_path = lake.fetch_blob(token, ch["filename"], dataroot)
            lidar_stats = PointCloudStats(**devkit.lidar_stats(local_path, ch["channel"]))

    return FrameManifest(
        scene_token=token,
        scene_name=meta["name"],
        sample_token=frame["sample_token"],
        keyframe_index=frame["keyframe_index"],
        num_keyframes=frame["num_keyframes"],
        timestamp=frame["timestamp"],
        ego_translation=frame["ego_translation"],
        num_annotations=frame["num_annotations"],
        devkit_version=devkit.devkit_version(),
        frames=channel_frames,
        lidar_stats=lidar_stats,
    )


def get_lake_stats() -> LakeStats:
    """Aggregate the AV lake for the dashboard: scenes, keyframes, blobs by
    modality (camera / LiDAR / radar) and total lake size."""
    metas = lake.list_scene_metas()
    camera = lidar = radar = total_blobs = total_size = total_keyframes = 0
    for meta in metas:
        total_keyframes += int(meta.get("keyframes", 0))
        for blob in lake.list_sensor_blobs(meta["token"]):
            total_blobs += 1
            total_size += blob["size_bytes"]
            modality = _modality_of(_channel_of(blob["filename"]))
            if modality == "camera":
                camera += 1
            elif modality == "lidar":
                lidar += 1
            else:
                radar += 1
    return LakeStats(
        total_scenes=len(metas),
        total_keyframes=total_keyframes,
        total_blobs=total_blobs,
        blobs_by_modality=ModalityBreakdown(camera=camera, lidar=lidar, radar=radar),
        total_size_bytes=total_size,
        total_size_human=humanize_bytes(total_size),
    )


def _channel_of(filename: str) -> str:
    # filename like "samples/CAM_FRONT/CAM_FRONT__000.jpg"
    parts = filename.split("/")
    return parts[1] if len(parts) >= 2 else parts[0]


def _summary_from_meta(meta: dict, raw_blobs: list[dict]) -> SceneSummary:
    total = sum(b["size_bytes"] for b in raw_blobs)
    return SceneSummary(
        token=meta["token"],
        name=meta["name"],
        description=meta.get("description", ""),
        location=meta["location"],
        time_of_day=meta["time_of_day"],
        weather=meta["weather"],
        sensor_suite=meta["sensor_suite"],
        keyframes=meta["keyframes"],
        channels=meta.get("channels", []),
        blob_count=len(raw_blobs),
        total_size_bytes=total,
        total_size_human=humanize_bytes(total),
        created_at=meta["created_at"],
    )
