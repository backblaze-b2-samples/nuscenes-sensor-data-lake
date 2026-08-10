export type FileStatus = "uploading" | "complete" | "error";

export interface FileMetadata {
  key: string;
  filename: string;
  folder: string;
  size_bytes: number;
  size_human: string;
  content_type: string;
  uploaded_at: string;
  url: string | null;
}

export interface FileMetadataDetail {
  filename: string;
  size_bytes: number;
  size_human: string;
  mime_type: string;
  extension: string;
  md5: string;
  sha256: string;
  uploaded_at: string;
  /** Set when a format-specific extractor was skipped or failed (e.g. an image
   *  above the decompression-bomb decode limit). Core fields stay exact. */
  metadata_warning: string | null;
  // Image-specific
  image_width: number | null;
  image_height: number | null;
  exif: Record<string, string> | null;
  // PDF-specific
  pdf_pages: number | null;
  pdf_author: string | null;
  pdf_title: string | null;
  // Audio/Video
  duration_seconds: number | null;
  codec: string | null;
  bitrate: number | null;
}

export interface FileUploadResponse {
  key: string;
  filename: string;
  size_bytes: number;
  size_human: string;
  content_type: string;
  uploaded_at: string;
  url: string | null;
  metadata: FileMetadataDetail | null;
}

/** A short-lived presigned PUT the browser uploads a file directly to B2 with.
 *  `headers` are signed into the URL, so the browser must send them verbatim. */
export interface PresignUploadResponse {
  key: string;
  url: string;
  method: string;
  content_type: string;
  headers: Record<string, string>;
  expires_in: number;
}

export interface DailyUploadCount {
  date: string;
  uploads: number;
}

export interface UploadStats {
  total_files: number;
  total_size_bytes: number;
  total_size_human: string;
  uploads_today: number;
  total_downloads: number;
}

// --- Scene domain (the AV multi-sensor data lake) ---------------------------

export type SceneLocation =
  | "boston-seaport"
  | "singapore-onenorth"
  | "singapore-queenstown"
  | "singapore-hollandvillage";
export type TimeOfDay = "day" | "night";
export type Weather = "clear" | "rain";
export type SensorSuite = "full" | "camera+lidar";
export type SensorModality = "camera" | "lidar" | "radar";

export interface SceneSummary {
  token: string;
  name: string;
  description: string;
  location: string;
  time_of_day: string;
  weather: string;
  sensor_suite: string;
  keyframes: number;
  channels: string[];
  blob_count: number;
  total_size_bytes: number;
  total_size_human: string;
  created_at: string;
}

export interface SensorBlob {
  channel: string;
  modality: SensorModality;
  key: string;
  filename: string;
  size_bytes: number;
  size_human: string;
  content_type: string;
}

export interface SceneDetail extends SceneSummary {
  blobs: SensorBlob[];
}

export interface ChannelFrame {
  channel: string;
  modality: SensorModality;
  filename: string;
  key: string;
  url: string;
  content_type: string;
  size_bytes: number;
  size_human: string;
}

export interface PointCloudStats {
  channel: string;
  num_points: number;
  x_min: number;
  x_max: number;
  y_min: number;
  y_max: number;
  z_min: number;
  z_max: number;
  intensity_min: number;
  intensity_max: number;
}

export interface FrameManifest {
  scene_token: string;
  scene_name: string;
  sample_token: string;
  keyframe_index: number;
  num_keyframes: number;
  timestamp: number;
  ego_translation: number[];
  num_annotations: number;
  devkit_version: string;
  frames: ChannelFrame[];
  lidar_stats: PointCloudStats | null;
}

export interface SceneDeleteResponse {
  deleted: boolean;
  token: string;
  objects_removed: number;
}

export interface ModalityBreakdown {
  camera: number;
  lidar: number;
  radar: number;
}

export interface LakeStats {
  total_scenes: number;
  total_keyframes: number;
  total_blobs: number;
  blobs_by_modality: ModalityBreakdown;
  total_size_bytes: number;
  total_size_human: string;
}

export interface SceneCreateRequest {
  name: string;
  description: string;
  location: SceneLocation;
  time_of_day: TimeOfDay;
  weather: Weather;
  keyframes: number;
  sensor_suite: SensorSuite;
}

export interface SceneUpdateRequest {
  name: string;
  description: string;
  location: SceneLocation;
  time_of_day: TimeOfDay;
  weather: Weather;
}
