<!-- last_verified: 2026-08-10 -->
# Feature: Scene Ingest

## Purpose
Create a Scene: synthesize a referentially-valid nuScenes-format multi-sensor
recording and ingest its sensor blobs + annotation tables to Backblaze B2 under
the scene's own prefix (the Ingest + Annotate steps in one action).

## Used By
- UI: `/scenes` → **New scene** dialog (`components/scenes/scene-form-dialog.tsx`)
- API: `POST /scenes`

## Core Functions
- `services/api/app/repo/scene_synth.py` — builds the 13 referentially-consistent nuScenes tables
- `services/api/app/repo/scene_blobs.py` — tiny deterministic sensor-blob bytes (JPEG camera, `.pcd.bin` LiDAR, placeholder radar, map-mask PNG)
- `services/api/app/repo/nuscenes_lake.py` — `put_scene()` uploads tables + blobs + `lake-meta.json` to B2
- `services/api/app/service/scenes.py` — `create_scene()` slugs the scene and orchestrates synth + storage

## Canonical Files
- Pattern exemplar: `services/api/app/service/scenes.py`

## Inputs
- name: str (form, free text)
- description: str (form, free text, optional)
- location: enum `boston-seaport` | `singapore-onenorth` | `singapore-queenstown` | `singapore-hollandvillage` (Select)
- time_of_day: enum `day` | `night` (RadioGroup)
- weather: enum `clear` | `rain` (Select)
- keyframes: enum `3` | `5` | `10` (Select)
- sensor_suite: enum `full` (12-channel nuScenes suite) | `camera+lidar` (CAM_FRONT + LIDAR_TOP + RADAR_FRONT) (Select)

## Outputs
- `SceneSummary` (token/slug, channels, blob_count, total size, created_at)
- Side effects: N objects written to B2 under `nuscenes/<slug>/` (13 tables + one map mask + `keyframes × channels` sensor blobs + `lake-meta.json`); the shared listing cache is invalidated once

## Flow
- User submits the New-scene form (selectors for every finite field; safe defaults pre-selected with a hint)
- `create_scene()` validates the keyframe count and slugs the name (`<name>-<6hex>`)
- `scene_synth.generate_scene()` returns the 13 tables + a `{relative_path: bytes}` blob map
- `nuscenes_lake.put_scene()` `put_object`s every table under `v1.0-demo/`, every blob under `samples/`/`maps/`, and writes `lake-meta.json`
- On success the app auto-navigates to the new scene's detail page (its Serve panel) when the user is still on `/scenes`; otherwise the scene appears in the list. A toast reports the blob count either way

## Edge Cases
- keyframes not in {3,5,10} → 400 (`SceneError`)
- name shorter than 2 chars / description over 280 → 422 (Pydantic)
- `camera+lidar` suite → 3 channels (CAM_FRONT, LIDAR_TOP, RADAR_FRONT); `full` → 12 channels

## UX States
- Loading: submit button shows "Ingesting…"
- Error: destructive toast with the API message
- Loaded: dialog closes; success toast, then auto-navigate to the scene's detail page (Serve panel) if still on `/scenes`, else the scene card appears in the list

## Verification
- Test files: `services/api/tests/test_scenes.py`
- Required cases: full-suite blob count, camera+lidar suite channel count, invalid keyframes rejected, tables + meta present in B2
- Focused verify command: `pnpm test:api`
- Default pre-PR verify command: `pnpm verify`
- Full local verify command: `pnpm verify:full` when E2E/live prerequisites apply
- Pass criteria: focused tests and `pnpm verify` green

## Related Docs
- [Scene Index & Serve](scene-index-serve.md)
- [Sensor Asset Explorer](sensor-asset-explorer.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [App Workflows](../app-workflows.md)
