<!-- last_verified: 2026-08-10 -->
# Feature: Sensor Asset Explorer

## Purpose
Browse a single Scene's sensor blobs in B2, grouped by sensor channel, with
inline camera previews — the sample-specific asset explorer, distinct from the
kept full-bucket File Explorer (`/files`).

## Used By
- UI: `/scenes/[token]` detail (`components/scenes/sensor-asset-explorer.tsx`)
- API: `GET /scenes/{token}` (blob list), `GET /files-by-key/preview` (inline presigned URL per camera blob, reused from the starter)

## Core Functions
- `services/api/app/service/scenes.py` — `get_scene()` returns a `SceneDetail` with `blobs[]` grouped-ready
- `services/api/app/repo/nuscenes_lake.py` — `list_sensor_blobs()` lists `nuscenes/<slug>/samples/`
- `apps/web/src/components/scenes/sensor-asset-explorer.tsx` — grouping + lazy camera thumbnails
- `apps/web/src/lib/queries.ts` — `useScene()`, `usePreviewUrl()`

## Canonical Files
- Pattern exemplar: `apps/web/src/components/scenes/sensor-asset-explorer.tsx`

## Inputs
- token: str (path) — the scene slug

## Outputs
- `SceneDetail.blobs`: `SensorBlob[]` (channel, modality, key, filename, size, content_type)
- Side effect: opening a camera channel fetches one inline presigned GET URL per camera blob (lazy — only when the group is expanded)

## Flow
- The detail page loads the scene via `useScene()`
- Blobs are grouped by channel client-side (CAM_* / LIDAR_TOP / RADAR_*), each group tagged with its modality
- Expanding a camera group renders an inline `<img>` per blob using a presigned inline URL from `GET /files-by-key/preview`
- LiDAR/radar groups list each blob with its filename and size

## Edge Cases
- Scene not found → 404 → the detail page shows an error state
- No sensor blobs → "No sensor blobs found for this scene."
- Camera preview URL still loading → skeleton placeholder in the thumbnail slot

## UX States
- Loading: skeletons while the scene loads
- Empty: per-group empty note
- Loaded: collapsible per-channel rows; camera thumbnails on expand

## Verification
- Test files: `services/api/tests/test_scenes.py` (`test_list_and_detail`)
- Required cases: detail returns every blob, modalities cover camera/lidar/radar, blobs carry the full B2 key
- Focused verify command: `pnpm test:api`
- Default pre-PR verify command: `pnpm verify`
- Full local verify command: `pnpm verify:full` when E2E/live prerequisites apply
- Pass criteria: focused tests and `pnpm verify` green

## Related Docs
- [Scene Index & Serve](scene-index-serve.md)
- [File Browser](file-browser.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
