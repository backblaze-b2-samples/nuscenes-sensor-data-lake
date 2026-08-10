"""Synthetic nuScenes-format scene generator.

Vendor fidelity (team rule): the app drives the *real* `nuscenes.nuscenes.NuScenes`
devkit, so this generator must emit a dataset the devkit actually loads. That
means the 13 annotation tables are **referentially consistent** — every token
referenced by another table exists, and `next`/`prev` chains resolve.

`NuScenes.__init__` reads only JSON (it does not require the sensor blobs on
disk, though it *does* open each map mask), so Index materializes the tables +
map masks locally; the sensor blobs live in B2 and are fetched on demand. The
LiDAR blob round-trips through `LidarPointCloud.from_file`; radar is opaque. See
`scene_blobs.py` for the blob byte generators and
docs/features/scene-index-serve.md for the radar simplification.

Pure computation only: no boto3 here. `repo/nuscenes_lake.py` uploads what this
returns to B2.
"""

from __future__ import annotations

from uuid import uuid4

from app.repo.scene_blobs import (
    LIDAR_POINTS,
    blob_for,
    channels_for,
    map_filename,
    map_png,
    modality_of,
)

# Re-exported so callers (service/scenes.py) can reference channels_for /
# modality_of through this module too.
__all__ = [
    "channels_for",
    "generate_scene",
    "map_filename",
    "modality_of",
    "scene_description",
]

_IDENTITY_QUAT = [1.0, 0.0, 0.0, 0.0]


def _token() -> str:
    return uuid4().hex


def scene_description(description: str, time_of_day: str, weather: str) -> str:
    tags = [t for t in (time_of_day, weather) if t]
    suffix = ", ".join(tags)
    if description and suffix:
        return f"{description} ({suffix})"
    return description or suffix


def generate_scene(
    *,
    name: str,
    description: str,
    location: str,
    time_of_day: str,
    weather: str,
    keyframes: int,
    sensor_suite: str,
) -> tuple[dict[str, list[dict]], dict[str, bytes]]:
    """Build a referentially-valid nuScenes dataset.

    Returns (tables, blobs):
      * tables: {table_name: [rows]} for the 13 nuScenes tables.
      * blobs:  {relative_path: bytes} where relative_path matches
        sample_data.filename (e.g. "samples/CAM_FRONT/<file>.jpg"), so the B2 key
        is "nuscenes/<slug>/<relative_path>".
    """
    channels = channels_for(sensor_suite)
    scene_token = _token()
    log_token = _token()

    category = [
        {"token": _token(), "name": "vehicle.car", "description": "Car."},
        {
            "token": _token(),
            "name": "human.pedestrian.adult",
            "description": "Adult pedestrian.",
        },
    ]
    attribute = [
        {"token": _token(), "name": "vehicle.moving", "description": "Moving."},
        {"token": _token(), "name": "pedestrian.moving", "description": "Walking."},
    ]
    visibility = [
        {"token": str(i), "level": lvl, "description": f"Visibility {lvl}."}
        for i, lvl in enumerate(["v0-40", "v40-60", "v60-80", "v80-100"], start=1)
    ]

    sensor, calibrated_sensor = [], []
    cs_by_channel: dict[str, str] = {}
    for channel in channels:
        s_tok, cs_tok = _token(), _token()
        modality = modality_of(channel)
        sensor.append({"token": s_tok, "channel": channel, "modality": modality})
        intrinsic = (
            [[1000.0, 0.0, 32.0], [0.0, 1000.0, 18.0], [0.0, 0.0, 1.0]]
            if modality == "camera"
            else []
        )
        calibrated_sensor.append(
            {
                "token": cs_tok,
                "sensor_token": s_tok,
                "translation": [1.0, 0.0, 1.5],
                "rotation": list(_IDENTITY_QUAT),
                "camera_intrinsic": intrinsic,
            }
        )
        cs_by_channel[channel] = cs_tok

    log = [
        {
            "token": log_token,
            "logfile": f"{location}-demo",
            "vehicle": "demo-vehicle",
            "date_captured": "2024-01-01",
            "location": location,
        }
    ]
    map_table = [
        {
            "token": _token(),
            "log_tokens": [log_token],
            "category": "semantic_prior",
            "filename": map_filename(location),
        }
    ]

    # Samples chained via next/prev; one ego_pose per sample.
    sample_tokens = [_token() for _ in range(keyframes)]
    sample, ego_pose = [], []
    ego_by_sample: dict[str, str] = {}
    base_ts = 1_531_000_000_000_000
    for i, tok in enumerate(sample_tokens):
        ts = base_ts + i * 500_000
        sample.append(
            {
                "token": tok,
                "timestamp": ts,
                "scene_token": scene_token,
                "next": sample_tokens[i + 1] if i + 1 < keyframes else "",
                "prev": sample_tokens[i - 1] if i > 0 else "",
            }
        )
        ego_tok = _token()
        ego_by_sample[tok] = ego_tok
        ego_pose.append(
            {
                "token": ego_tok,
                "timestamp": ts,
                "translation": [float(i) * 5.0, 0.0, 0.0],
                "rotation": list(_IDENTITY_QUAT),
            }
        )

    # sample_data (one per channel per keyframe) + the blobs they point at.
    sample_data: list[dict] = []
    blobs: dict[str, bytes] = {map_filename(location): map_png(location)}
    per_channel_chain: dict[str, list[str]] = {c: [] for c in channels}
    for i, s_tok in enumerate(sample_tokens):
        for channel in channels:
            sd_tok = _token()
            data, ext, fmt, height, width = blob_for(channel, i)
            filename = f"samples/{channel}/{channel}__{i:03d}.{ext}"
            blobs[filename] = data
            sample_data.append(
                {
                    "token": sd_tok,
                    "sample_token": s_tok,
                    "ego_pose_token": ego_by_sample[s_tok],
                    "calibrated_sensor_token": cs_by_channel[channel],
                    "timestamp": base_ts + i * 500_000,
                    "fileformat": fmt,
                    "is_key_frame": True,
                    "height": height,
                    "width": width,
                    "filename": filename,
                    "prev": "",
                    "next": "",
                }
            )
            per_channel_chain[channel].append(sd_tok)
    by_token = {sd["token"]: sd for sd in sample_data}
    for chain in per_channel_chain.values():
        for j, sd_tok in enumerate(chain):
            if j > 0:
                by_token[sd_tok]["prev"] = chain[j - 1]
            if j + 1 < len(chain):
                by_token[sd_tok]["next"] = chain[j + 1]

    # One instance per category, annotated once per keyframe.
    instance, sample_annotation = [], []
    for cat in category:
        inst_tok = _token()
        ann_tokens = [_token() for _ in sample_tokens]
        for j, (s_tok, ann_tok) in enumerate(zip(sample_tokens, ann_tokens, strict=True)):
            sample_annotation.append(
                {
                    "token": ann_tok,
                    "sample_token": s_tok,
                    "instance_token": inst_tok,
                    "visibility_token": "4",
                    "attribute_tokens": [attribute[0]["token"]],
                    "translation": [10.0 + j, 2.0, 1.0],
                    "size": [1.9, 4.5, 1.7],
                    "rotation": list(_IDENTITY_QUAT),
                    "num_lidar_pts": LIDAR_POINTS,
                    "num_radar_pts": 0,
                    "next": ann_tokens[j + 1] if j + 1 < len(ann_tokens) else "",
                    "prev": ann_tokens[j - 1] if j > 0 else "",
                }
            )
        instance.append(
            {
                "token": inst_tok,
                "category_token": cat["token"],
                "nbr_annotations": len(ann_tokens),
                "first_annotation_token": ann_tokens[0],
                "last_annotation_token": ann_tokens[-1],
            }
        )

    scene = [
        {
            "token": scene_token,
            "name": name,
            "description": scene_description(description, time_of_day, weather),
            "log_token": log_token,
            "nbr_samples": keyframes,
            "first_sample_token": sample_tokens[0],
            "last_sample_token": sample_tokens[-1],
        }
    ]

    tables = {
        "category": category,
        "attribute": attribute,
        "visibility": visibility,
        "instance": instance,
        "sensor": sensor,
        "calibrated_sensor": calibrated_sensor,
        "ego_pose": ego_pose,
        "log": log,
        "scene": scene,
        "sample": sample,
        "sample_data": sample_data,
        "sample_annotation": sample_annotation,
        "map": map_table,
    }
    return tables, blobs
