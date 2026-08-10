"""Thin adapter over the real nuScenes devkit.

This is the ONLY module that imports `nuscenes`, keeping the heavy toolkit
(numpy/opencv/matplotlib/pyquaternion) out of the service/runtime layers and
honouring the no-SDK-outside-repo rule. It drives the actual
`nuscenes.nuscenes.NuScenes` class to build the in-memory scene graph and the
actual `LidarPointCloud.from_file` to compute real point-cloud stats.
"""

from __future__ import annotations

from typing import Any

import nuscenes
from nuscenes.nuscenes import NuScenes
from nuscenes.utils.data_classes import LidarPointCloud

VERSION = "v1.0-demo"


def devkit_version() -> str:
    return getattr(nuscenes, "__version__", "nuscenes-devkit")


def build_index(dataroot: str) -> NuScenes:
    """Instantiate the real devkit over a materialized dataroot.

    This is where the 13 JSON tables are loaded and the reverse indexes (the
    in-memory scene graph) are built. Raises on a malformed dataset.
    """
    return NuScenes(version=VERSION, dataroot=dataroot, verbose=False)


def resolve_frame(nusc: NuScenes, keyframe_index: int) -> dict[str, Any]:
    """Resolve one keyframe through the devkit graph.

    Walks the sample chain to the requested keyframe, then resolves every sensor
    channel via `sample['data']` -> `get('sample_data', ...)`, returning the
    devkit-computed channel, modality and relative filename for each.
    """
    scene = nusc.scene[0]
    num = scene["nbr_samples"]
    index = max(0, min(keyframe_index, num - 1))

    token = scene["first_sample_token"]
    for _ in range(index):
        token = nusc.get("sample", token)["next"]
    sample = nusc.get("sample", token)
    ego_pose = _ego_pose_for_sample(nusc, sample)

    channels = []
    for _channel, sd_token in sorted(sample["data"].items()):
        sd = nusc.get("sample_data", sd_token)
        channels.append(
            {
                "channel": sd["channel"],
                "modality": sd["sensor_modality"],
                "filename": sd["filename"],
            }
        )

    return {
        "sample_token": token,
        "keyframe_index": index,
        "num_keyframes": num,
        "timestamp": sample["timestamp"],
        "ego_translation": ego_pose["translation"],
        "num_annotations": len(sample["anns"]),
        "channels": channels,
    }


def _ego_pose_for_sample(nusc: NuScenes, sample: dict) -> dict:
    any_sd_token = next(iter(sample["data"].values()))
    sd = nusc.get("sample_data", any_sd_token)
    return nusc.get("ego_pose", sd["ego_pose_token"])


def lidar_stats(local_path: str, channel: str) -> dict[str, Any]:
    """Load a LiDAR blob through the devkit and compute real point-cloud stats.

    `LidarPointCloud.from_file` reads the nuScenes `.pcd.bin` float32 (N, 5)
    layout and keeps (x, y, z, intensity) as a (4, N) array — this is the proof
    that a blob served from the B2 lake is a usable nuScenes point cloud.
    """
    pc = LidarPointCloud.from_file(local_path)
    pts = pc.points  # shape (4, N): x, y, z, intensity
    return {
        "channel": channel,
        "num_points": int(pts.shape[1]),
        "x_min": float(pts[0].min()),
        "x_max": float(pts[0].max()),
        "y_min": float(pts[1].min()),
        "y_max": float(pts[1].max()),
        "z_min": float(pts[2].min()),
        "z_max": float(pts[2].max()),
        "intensity_min": float(pts[3].min()),
        "intensity_max": float(pts[3].max()),
    }
