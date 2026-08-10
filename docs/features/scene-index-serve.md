<!-- last_verified: 2026-08-10 -->
# Feature: Scene Index & Serve

## Purpose
Index a Scene with the **real** nuScenes devkit and serve a chosen keyframe as a
per-frame training manifest — resolving every sensor channel, presigning each
blob's B2 URL, and computing genuine LiDAR point-cloud stats.

## Used By
- UI: `/scenes/[token]` → **Serve** action (`components/scenes/serve-frame-panel.tsx`)
- API: `POST /scenes/{token}/frame?keyframe=<n>`

## Core Functions
- `services/api/app/repo/nuscenes_lake.py` — `materialize_dataroot()` (fetch JSON tables + map masks to a temp dir), `fetch_blob()` (pull one blob for stats), `presign_key()`
- `services/api/app/repo/nuscenes_devkit.py` — `build_index()` runs `NuScenes(...)`; `resolve_frame()` walks the sample graph; `lidar_stats()` calls `LidarPointCloud.from_file`
- `services/api/app/service/scenes.py` — `serve_frame()` orchestration

## Canonical Files
- Pattern exemplar: `services/api/app/repo/nuscenes_devkit.py`

## Inputs
- token: str (path) — the scene slug
- keyframe: int (query, default 0) — clamped to `[0, nbr_samples-1]`

## Outputs
- `FrameManifest`: scene/sample tokens, keyframe index + count, timestamp, ego translation, num_annotations, devkit_version, `frames[]` (per channel: channel, modality, filename, key, presigned url, size), and `lidar_stats` (num_points, x/y/z ranges, intensity range)
- Side effects: reads JSON tables + map masks + one LiDAR blob from B2 to a temp dataroot; no writes

## Flow
- `materialize_dataroot()` `get_object`s `v1.0-demo/*.json` and the map masks into a temp dir (sensor blobs are **not** downloaded — `NuScenes.__init__` reads only JSON, plus the map mask it opens)
- `build_index()` instantiates the real `NuScenes("v1.0-demo", dataroot)` — this is the in-memory scene-graph build over the reverse indexes
- `resolve_frame()` walks the sample chain to the requested keyframe and resolves each channel via `sample['data'][channel]` → `get('sample_data', ...)` (devkit-computed channel/modality/filename)
- Each channel's blob is presigned (S3 `generate_presigned_url`, inline)
- The LiDAR `.pcd.bin` is pulled to the temp dataroot and loaded through `LidarPointCloud.from_file` for real point-cloud stats

## Edge Cases
- keyframe out of range → clamped to the valid range
- scene has no tables in B2 → 409 (`FileNotFoundError`)
- a malformed dataset the devkit rejects → 502 with an actionable message
- **Radar simplification:** radar sweeps are stored/served/counted as opaque
  placeholder `.pcd` blobs; the app does **not** round-trip
  `RadarPointCloud.from_file` (its 18-field PCD header is fiddly and not needed to
  prove the lake). Only the LiDAR `.pcd.bin` is decoded, which is the real
  devkit-compute proof.

## UX States
- Empty: prompt to pick a keyframe and run Serve
- Loading: Serve button shows "Indexing…"
- Error: destructive toast with the API message
- Loaded: badges (keyframe, channels, annotations, devkit version), LiDAR stats card, and the resolved-sensors list with presigned links

## Verification
- Test files: `services/api/tests/test_scenes.py` (`test_serve_frame_runs_real_devkit`)
- Required cases: real devkit load, all channels resolved with presigned URLs, LiDAR num_points and ranges computed
- Focused verify command: `pnpm test:api`
- Default pre-PR verify command: `pnpm verify`
- Full local verify command: `pnpm verify:full` when E2E/live prerequisites apply
- Pass criteria: focused tests and `pnpm verify` green

## Related Docs
- [Scene Ingest](scene-ingest.md)
- [Sensor Asset Explorer](sensor-asset-explorer.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
