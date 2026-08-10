<!-- last_verified: 2026-08-10 -->
# Feature: Dashboard

## Purpose
Give an at-a-glance overview of the autonomous-vehicle sensor lake: how many
scenes and keyframes it holds, how its sensor blobs break down by modality, and
which scenes are newest.

## Used By
- UI: `/` page (dashboard home)
- API: `GET /scenes/stats`, `GET /scenes`

## Core Functions
- `apps/web/src/components/dashboard/stats-cards.tsx` — 4 AV-lake stat cards, plus the on-screen loading notice
- `apps/web/src/components/dashboard/modality-chart.tsx` — bar chart of sensor blobs by modality (camera / LiDAR / radar)
- `apps/web/src/components/dashboard/recent-scenes-table.tsx` — the newest scenes, each linking to its detail
- `apps/web/src/lib/queries.ts` — `useLakeStats()`, `useScenes()`
- `services/api/app/runtime/scenes.py` — `GET /scenes/stats` handler
- `services/api/app/service/scenes.py` — `get_lake_stats()` aggregation
- `services/api/app/repo/nuscenes_lake.py` — `list_scene_metas()` + `list_sensor_blobs()` data access

## Canonical Files
- Dashboard stat cards: `apps/web/src/components/dashboard/stats-cards.tsx`
- Lake aggregation: `services/api/app/service/scenes.py`

## Inputs
- None (dashboard loads data automatically)

## Outputs
- `GET /scenes/stats` → `LakeStats` (total_scenes, total_keyframes, total_blobs, blobs_by_modality{camera,lidar,radar}, total_size_bytes, total_size_human)
- `GET /scenes` (for the recent-scenes table) → `SceneSummary[]` (newest first)

## Flow
- Page loads → `useLakeStats()` and `useScenes()` fetch in parallel
- Stat cards display scenes, keyframes, sensor blobs, and total lake size
- The modality chart renders the camera / LiDAR / radar blob counts
- The recent-scenes table lists the newest scenes; each name links to `/scenes/<token>`

## Edge Cases
- API unavailable → inline `ErrorState` with retry
- No scenes yet → empty stat values, empty-chart message, empty-table prompt to create a scene
- Many scenes → `get_lake_stats()` lists each scene's `lake-meta.json` + `samples/` prefix; counts aggregate across the whole lake

## UX States
- Loading: an on-screen "Loading lake stats…" notice above the cards, with skeleton placeholders for cards, chart, and table
- Empty: "No sensor blobs yet" / "No scenes yet"
- Loaded: populated cards, modality chart, recent-scenes table

## Verification
- Test files: `services/api/tests/test_scenes.py` (`test_lake_stats`), `apps/web/src/lib/api-contract.test.ts`
- Required cases: stats with multiple scenes, modality counts per suite, empty lake
- Focused verify command: `pnpm test:api`
- Default pre-PR verify command: `pnpm verify`
- Full local verify command: `pnpm verify:full` when the E2E/live prerequisites in [Dev Workflows](../dev-workflows.md#commands) are available
- Pass criteria: focused tests and `pnpm verify` green

## Related Docs
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [App Workflows](../app-workflows.md)
- [Scene Ingest](scene-ingest.md)
