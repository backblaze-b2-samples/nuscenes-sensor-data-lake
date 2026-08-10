// Finite value sets for the Scene forms (rendered as Select / RadioGroup, never
// free text) and shared label/badge helpers for the Scene views.
import type {
  SceneLocation,
  SensorModality,
  SensorSuite,
  TimeOfDay,
  Weather,
} from "@nuscenes-sensor-data-lake/shared";

export const LOCATIONS: { value: SceneLocation; label: string }[] = [
  { value: "boston-seaport", label: "Boston Seaport" },
  { value: "singapore-onenorth", label: "Singapore One-North" },
  { value: "singapore-queenstown", label: "Singapore Queenstown" },
  { value: "singapore-hollandvillage", label: "Singapore Holland Village" },
];

export const TIMES_OF_DAY: { value: TimeOfDay; label: string }[] = [
  { value: "day", label: "Day" },
  { value: "night", label: "Night" },
];

export const WEATHERS: { value: Weather; label: string }[] = [
  { value: "clear", label: "Clear" },
  { value: "rain", label: "Rain" },
];

export const KEYFRAME_CHOICES = [3, 5, 10] as const;

export const SENSOR_SUITES: { value: SensorSuite; label: string }[] = [
  { value: "full", label: "Full (12-channel nuScenes suite)" },
  { value: "camera+lidar", label: "Camera + LiDAR (CAM_FRONT, LIDAR_TOP, RADAR_FRONT)" },
];

export const MODALITY_LABELS: Record<SensorModality, string> = {
  camera: "Camera",
  lidar: "LiDAR",
  radar: "Radar",
};

// Tailwind classes for a per-modality badge dot (design tokens only).
export const MODALITY_DOT: Record<SensorModality, string> = {
  camera: "bg-[var(--chart-1)]",
  lidar: "bg-[var(--chart-2)]",
  radar: "bg-[var(--chart-3)]",
};

export function labelFor(
  options: { value: string; label: string }[],
  value: string,
): string {
  return options.find((option) => option.value === value)?.label ?? value;
}
