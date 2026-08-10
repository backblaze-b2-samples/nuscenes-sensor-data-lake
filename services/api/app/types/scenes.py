"""Pydantic models for the Scene domain (the AV multi-sensor data lake).

A Scene is a self-contained nuScenes-format dataset stored under its own B2
prefix. These models validate the create/edit boundary and shape every response
the frontend consumes; heavy work (synthesis, the devkit) lives in repo/.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# Real nuScenes capture locations (finite set -> Select in the UI).
Location = Literal[
    "boston-seaport",
    "singapore-onenorth",
    "singapore-queenstown",
    "singapore-hollandvillage",
]
TimeOfDay = Literal["day", "night"]
Weather = Literal["clear", "rain"]
SensorSuite = Literal["full", "camera+lidar"]
Modality = Literal["camera", "lidar", "radar"]

# Allowed keyframe counts (finite set -> Select in the UI).
KEYFRAME_CHOICES = (3, 5, 10)


class SceneCreateRequest(BaseModel):
    """Create-a-scene payload. Defaults produce a sound, immediately-indexable
    demo scene (surfaced as pre-selected values + a hint on the form)."""

    name: str = Field(min_length=2, max_length=64)
    description: str = Field(default="", max_length=280)
    location: Location = "boston-seaport"
    time_of_day: TimeOfDay = "day"
    weather: Weather = "clear"
    keyframes: int = 5
    sensor_suite: SensorSuite = "full"


class SceneUpdateRequest(BaseModel):
    """Edit-a-scene payload — metadata only (no re-synthesis of blobs)."""

    name: str = Field(min_length=2, max_length=64)
    description: str = Field(default="", max_length=280)
    location: Location
    time_of_day: TimeOfDay
    weather: Weather


class SceneSummary(BaseModel):
    token: str  # scene slug: the URL id and the B2 prefix component
    name: str
    description: str
    location: str
    time_of_day: str
    weather: str
    sensor_suite: str
    keyframes: int
    channels: list[str]
    blob_count: int
    total_size_bytes: int
    total_size_human: str
    created_at: datetime


class SensorBlob(BaseModel):
    channel: str
    modality: Modality
    key: str
    filename: str
    size_bytes: int
    size_human: str
    content_type: str


class SceneDetail(SceneSummary):
    blobs: list[SensorBlob]


class ChannelFrame(BaseModel):
    """One sensor channel of a keyframe, resolved through the real devkit."""

    channel: str
    modality: Modality
    filename: str  # devkit-resolved sample_data.filename (relative to dataroot)
    key: str  # full B2 object key
    url: str  # presigned GET URL
    content_type: str
    size_bytes: int
    size_human: str


class PointCloudStats(BaseModel):
    """Real stats computed by loading the LiDAR blob through the devkit's
    LidarPointCloud.from_file — the proof that B2-stored blobs are usable."""

    channel: str
    num_points: int
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float
    intensity_min: float
    intensity_max: float


class FrameManifest(BaseModel):
    """The per-keyframe training manifest returned by Serve frame."""

    scene_token: str
    scene_name: str
    sample_token: str
    keyframe_index: int
    num_keyframes: int
    timestamp: int
    ego_translation: list[float]
    num_annotations: int
    devkit_version: str
    frames: list[ChannelFrame]
    lidar_stats: PointCloudStats | None = None


class SceneDeleteResponse(BaseModel):
    deleted: bool
    token: str
    objects_removed: int


class ModalityBreakdown(BaseModel):
    camera: int
    lidar: int
    radar: int


class LakeStats(BaseModel):
    """AV-lake dashboard aggregates across every scene in the bucket."""

    total_scenes: int
    total_keyframes: int
    total_blobs: int
    blobs_by_modality: ModalityBreakdown
    total_size_bytes: int
    total_size_human: str
