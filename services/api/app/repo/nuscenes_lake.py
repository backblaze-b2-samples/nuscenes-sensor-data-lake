"""B2-backed nuScenes dataset store.

Every Scene is a self-contained nuScenes dataset living under its own B2 prefix
`nuscenes/<slug>/`, so CRUD is a clean prefix operation with no shared-table race:

    nuscenes/<slug>/lake-meta.json                 # app display metadata
    nuscenes/<slug>/v1.0-demo/<table>.json         # the 13 annotation tables
    nuscenes/<slug>/samples/<CHANNEL>/<file>       # keyframe sensor blobs
    nuscenes/<slug>/maps/<location>.png            # map mask (devkit needs it)

All storage is plain S3 through the shared boto3 client in `b2_client.py`
(custom user-agent set there) — no new boto3 session. `NuScenes.__init__` reads
only JSON, so Index materializes just the tables + map mask locally; sensor blobs
stay in B2 and are fetched on demand.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime

from botocore.exceptions import ClientError

from app.config import settings
from app.repo.b2_client import get_presigned_url, get_s3_client
from app.repo.list_cache import invalidate as _invalidate_list_cache
from app.types.formatting import humanize_bytes

ROOT_PREFIX = "nuscenes"
VERSION = "v1.0-demo"
META_FILE = "lake-meta.json"

_CONTENT_TYPES = {
    ".json": "application/json",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".bin": "application/octet-stream",
    ".pcd": "application/octet-stream",
}


def scene_prefix(slug: str) -> str:
    return f"{ROOT_PREFIX}/{slug}/"


def _meta_key(slug: str) -> str:
    return f"{scene_prefix(slug)}{META_FILE}"


def _table_key(slug: str, table: str) -> str:
    return f"{scene_prefix(slug)}{VERSION}/{table}.json"


def _content_type(key: str) -> str:
    for ext, ctype in _CONTENT_TYPES.items():
        if key.endswith(ext):
            return ctype
    return "application/octet-stream"


def _put(key: str, data: bytes, content_type: str) -> None:
    client = get_s3_client()
    try:
        client.put_object(
            Bucket=settings.b2_bucket_name,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
    except ClientError as e:  # pragma: no cover - network failure path
        raise RuntimeError(f"B2 put failed for '{key}': {e}") from e


def _get_bytes(key: str) -> bytes:
    client = get_s3_client()
    try:
        return client.get_object(Bucket=settings.b2_bucket_name, Key=key)[
            "Body"
        ].read()
    except ClientError as e:
        raise RuntimeError(f"B2 get failed for '{key}': {e}") from e


def _list(prefix: str) -> list[dict]:
    """Every object under `prefix` (paginated). Raw S3 dicts (Key, Size)."""
    client = get_s3_client()
    contents: list[dict] = []
    kwargs = {"Bucket": settings.b2_bucket_name, "Prefix": prefix, "MaxKeys": 1000}
    try:
        while True:
            resp = client.list_objects_v2(**kwargs)
            contents.extend(resp.get("Contents", []))
            if not resp.get("IsTruncated"):
                break
            kwargs["ContinuationToken"] = resp["NextContinuationToken"]
    except ClientError as e:
        raise RuntimeError(f"B2 list failed for '{prefix}': {e}") from e
    return contents


def put_scene(
    slug: str, tables: dict[str, list[dict]], blobs: dict[str, bytes], meta: dict
) -> None:
    """Ingest a whole scene: annotation tables, sensor blobs, and app metadata.

    Invalidates the shared listing cache once at the end so the new objects show
    up in the full-bucket File Explorer and dashboard stats.
    """
    for table, rows in tables.items():
        _put(
            _table_key(slug, table),
            json.dumps(rows).encode("utf-8"),
            "application/json",
        )
    for rel_path, data in blobs.items():
        key = f"{scene_prefix(slug)}{rel_path}"
        _put(key, data, _content_type(key))
    write_meta(slug, meta)
    _invalidate_list_cache()


def write_meta(slug: str, meta: dict) -> None:
    _put(_meta_key(slug), json.dumps(meta).encode("utf-8"), "application/json")


def read_meta(slug: str) -> dict | None:
    try:
        return json.loads(_get_bytes(_meta_key(slug)))
    except RuntimeError:
        return None


def list_scene_metas() -> list[dict]:
    """Every scene's app metadata, newest first (by created_at)."""
    metas: list[dict] = []
    for obj in _list(f"{ROOT_PREFIX}/"):
        if obj["Key"].endswith(f"/{META_FILE}"):
            try:
                metas.append(json.loads(_get_bytes(obj["Key"])))
            except RuntimeError:
                continue
    metas.sort(key=lambda m: m.get("created_at", ""), reverse=True)
    return metas


def read_table(slug: str, table: str) -> list[dict]:
    return json.loads(_get_bytes(_table_key(slug, table)))


def write_table(slug: str, table: str, rows: list[dict]) -> None:
    _put(_table_key(slug, table), json.dumps(rows).encode("utf-8"), "application/json")


def list_sensor_blobs(slug: str) -> list[dict]:
    """Sensor blobs under the scene, with (key, filename, size, content_type)."""
    prefix = f"{scene_prefix(slug)}samples/"
    blobs = []
    for obj in _list(prefix):
        key = obj["Key"]
        blobs.append(
            {
                "key": key,
                "filename": key[len(scene_prefix(slug)) :],
                "size_bytes": obj["Size"],
                "size_human": humanize_bytes(obj["Size"]),
                "content_type": _content_type(key),
            }
        )
    blobs.sort(key=lambda b: b["filename"])
    return blobs


def presign_key(key: str, disposition: str = "inline", expires_in: int = 900) -> str:
    filename = key.rsplit("/", 1)[-1]
    return get_presigned_url(
        key, filename=filename, expires_in=expires_in, disposition=disposition
    )


def materialize_dataroot(slug: str) -> str:
    """Fetch the JSON tables + map masks to a temp dataroot for the devkit.

    Sensor blobs are intentionally NOT downloaded — NuScenes.__init__ reads only
    JSON (plus the map mask, which it opens). Returns the dataroot path
    (`<tmp>/`, containing `<tmp>/v1.0-demo/*.json`).
    """
    dataroot = tempfile.mkdtemp(prefix=f"nusc-{slug}-")
    version_dir = os.path.join(dataroot, VERSION)
    os.makedirs(version_dir, exist_ok=True)
    tables_present = _list(f"{scene_prefix(slug)}{VERSION}/")
    if not tables_present:
        raise FileNotFoundError(f"scene '{slug}' has no annotation tables in B2")
    for obj in tables_present:
        name = obj["Key"].rsplit("/", 1)[-1]
        with open(os.path.join(version_dir, name), "wb") as fh:
            fh.write(_get_bytes(obj["Key"]))
    # The devkit's MapMask opens each map file at init, so fetch them too.
    for map_record in read_table(slug, "map"):
        rel = map_record.get("filename")
        if not rel:
            continue
        dest = os.path.join(dataroot, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as fh:
            fh.write(_get_bytes(f"{scene_prefix(slug)}{rel}"))
    return dataroot


def fetch_blob(slug: str, rel_filename: str, dataroot: str) -> str:
    """Download one sensor blob (e.g. the LiDAR .pcd.bin) into the dataroot so a
    devkit call that needs the file on disk can read it. Returns the local path."""
    dest = os.path.join(dataroot, rel_filename)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as fh:
        fh.write(_get_bytes(f"{scene_prefix(slug)}{rel_filename}"))
    return dest


def delete_scene(slug: str) -> int:
    """Delete every object under the scene's own prefix ONLY (scoped wipe).

    Returns the number of objects removed. Invalidates the listing cache so the
    scene disappears from the File Explorer and dashboard.
    """
    client = get_s3_client()
    keys = [{"Key": obj["Key"]} for obj in _list(scene_prefix(slug))]
    removed = 0
    for start in range(0, len(keys), 1000):
        batch = keys[start : start + 1000]
        try:
            client.delete_objects(
                Bucket=settings.b2_bucket_name, Delete={"Objects": batch}
            )
        except ClientError as e:
            raise RuntimeError(f"B2 delete failed for '{slug}': {e}") from e
        removed += len(batch)
    if removed:
        _invalidate_list_cache()
    return removed


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()
