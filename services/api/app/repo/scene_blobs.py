"""Tiny, deterministic sensor-blob generators for synthetic nuScenes scenes.

Split out of `scene_synth.py` to keep both modules under the 300-line limit.
Pure byte generation (numpy/Pillow) — no boto3. The LiDAR blob is a genuine
nuScenes `.pcd.bin` (float32 (N, 5) = x, y, z, intensity, ring_index) so it
round-trips through `LidarPointCloud.from_file`; radar is an opaque placeholder.
"""

from __future__ import annotations

import io
import struct

import numpy as np
from PIL import Image

LIDAR_POINTS = 60  # tiny, but real: reshaped to (N, 5) float32

FULL_CHANNELS = [
    "CAM_FRONT",
    "CAM_FRONT_RIGHT",
    "CAM_BACK_RIGHT",
    "CAM_BACK",
    "CAM_BACK_LEFT",
    "CAM_FRONT_LEFT",
    "LIDAR_TOP",
    "RADAR_FRONT",
    "RADAR_FRONT_LEFT",
    "RADAR_FRONT_RIGHT",
    "RADAR_BACK_LEFT",
    "RADAR_BACK_RIGHT",
]
MINIMAL_CHANNELS = ["CAM_FRONT", "LIDAR_TOP", "RADAR_FRONT"]


def channels_for(sensor_suite: str) -> list[str]:
    return MINIMAL_CHANNELS if sensor_suite == "camera+lidar" else FULL_CHANNELS


def modality_of(channel: str) -> str:
    if channel.startswith("CAM"):
        return "camera"
    if channel.startswith("LIDAR"):
        return "lidar"
    return "radar"


def map_filename(location: str) -> str:
    """B2-relative path of a scene's map mask (fetched at Index time — the devkit
    requires the mask PNG to exist on disk when NuScenes(...) is instantiated)."""
    return f"maps/{location}.png"


def map_png(location: str) -> bytes:
    """A tiny valid grayscale PNG the devkit's MapMask can point at."""
    rng = np.random.default_rng(abs(hash(location)) % (2**32))
    arr = rng.integers(0, 2, size=(16, 16), dtype=np.uint8) * 255
    img = Image.fromarray(arr, "L")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _camera_jpeg(channel: str, index: int) -> bytes:
    """A small deterministic 64x36 JPEG so camera keyframes preview inline."""
    rng = np.random.default_rng(abs(hash((channel, index))) % (2**32))
    base = rng.integers(40, 210, size=3)
    arr = np.zeros((36, 64, 3), dtype=np.uint8)
    for row in range(36):
        arr[row, :, :] = np.clip(base + row * 2, 0, 255)
    img = Image.fromarray(arr, "RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    return buf.getvalue()


def _lidar_pcd_bin(channel: str, index: int) -> bytes:
    """nuScenes .pcd.bin: raw float32 (N, 5) = x, y, z, intensity, ring_index."""
    rng = np.random.default_rng(abs(hash((channel, index, "lidar"))) % (2**32))
    xyz = rng.uniform(-40.0, 40.0, size=(LIDAR_POINTS, 3)).astype(np.float32)
    intensity = rng.uniform(0.0, 255.0, size=(LIDAR_POINTS, 1)).astype(np.float32)
    ring = rng.integers(0, 32, size=(LIDAR_POINTS, 1)).astype(np.float32)
    points = np.hstack([xyz, intensity, ring]).astype(np.float32)
    return points.tobytes()


def _radar_pcd(channel: str, index: int) -> bytes:
    """Minimal opaque placeholder blob for a radar sweep (not devkit-decoded)."""
    header = (
        "# .PCD v0.7 - synthetic nuScenes radar placeholder\n"
        f"# channel {channel} keyframe {index}\n"
        "FIELDS x y z\nSIZE 4 4 4\nTYPE F F F\nCOUNT 1 1 1\n"
        "WIDTH 4\nHEIGHT 1\nPOINTS 4\nDATA binary\n"
    ).encode("ascii")
    body = struct.pack("<12f", *[float(i) for i in range(12)])
    return header + body


def blob_for(channel: str, index: int) -> tuple[bytes, str, str, int, int]:
    """Return (bytes, extension, fileformat, height, width) for a channel."""
    modality = modality_of(channel)
    if modality == "camera":
        return _camera_jpeg(channel, index), "jpg", "jpg", 36, 64
    if modality == "lidar":
        return _lidar_pcd_bin(channel, index), "pcd.bin", "pcd", 0, 0
    return _radar_pcd(channel, index), "pcd", "pcd", 0, 0
