<!-- last_verified: 2026-08-10 -->
# Architecture

## Components

- **apps/web/** — Next.js 16 frontend (App Router, Tailwind v4, shadcn/ui)
  - **Scenes** — the primary entity: list + create (`/scenes`), detail with the
    scene-scoped sensor asset explorer and Serve-frame action (`/scenes/[token]`)
  - AV-lake dashboard (scenes, keyframes, blobs-by-modality chart, recent scenes)
  - Full-bucket file browser and drag-and-drop upload (kept from the starter)
  - Dark mode via `next-themes`
- **services/api/** — FastAPI backend (layered architecture)
  - **Scenes domain** — synthesize a nuScenes scene, ingest blobs + tables to B2,
    index it with the real nuScenes devkit, serve a per-keyframe training manifest
  - B2 S3 integration via boto3 (the devkit and numpy/Pillow stay inside `repo/`)
  - REST API for generic file upload, listing, deletion (kept from the starter)
  - Health check endpoint with B2 connectivity verification
  - Structured JSON logging with request tracing
  - Prometheus-format metrics endpoint
- **packages/shared/** — TypeScript type definitions
  - Mirrors Pydantic models from the API
  - Consumed by `apps/web/` as workspace dependency

## Backend Layering

The API follows a strict layered architecture:

```
types/     Pydantic models — no logic, no imports from other layers
  |
config/    Settings (pydantic-settings) — depends only on types
  |
repo/      Data access (boto3 B2 client) — no business logic
  |
service/   Business logic — calls repo, returns types
  |
runtime/   FastAPI routes — calls service, never repo directly
```

### Layering Rules

1. Dependencies flow downward only: `types` -> `config` -> `repo` -> `service` -> `runtime`
2. No backward imports (e.g., service must not import from runtime)
3. `boto3` only allowed in `repo/` layer
4. All boundary data uses Pydantic models (no raw dicts across layers)
5. Authored Python files under `services/api/app/` stay under 300 lines

### Directory Structure

```
services/api/
  main.py                  App entrypoint, middleware, router registration
  app/
    types/                 Pydantic models (scenes.py, files.py, upload.py, ...)
    config/                Settings loaded from environment
    repo/                  Data access — B2 S3 client + the Scenes adapters:
                             scene_blobs.py    tiny sensor-blob byte generators
                             scene_synth.py    referentially-valid nuScenes tables
                             nuscenes_lake.py  B2-backed dataset store (S3)
                             nuscenes_devkit.py the ONLY `nuscenes` importer
    service/               Business logic (scenes.py, upload, files, metadata)
    runtime/               FastAPI route handlers (scenes.py, files, upload, ...)
  tests/                   pytest tests (structural + integration + test_scenes.py)
```

### Scenes domain

Each Scene is a self-contained nuScenes dataset under its own B2 prefix
(`nuscenes/<slug>/`), so CRUD is a clean prefix operation and there is no
shared-table read-modify-write race:

```
nuscenes/<slug>/lake-meta.json            app display metadata (listing source)
nuscenes/<slug>/v1.0-demo/<table>.json    the 13 nuScenes annotation tables
nuscenes/<slug>/samples/<CHANNEL>/<file>  keyframe sensor blobs (camera/LiDAR/radar)
nuscenes/<slug>/maps/<location>.png       map mask (the devkit opens it at init)
```

`NuScenes.__init__` reads only JSON (plus the map mask), so **Index materializes
just the tables + map masks locally** to a temp `dataroot`; sensor blobs stay in
B2 and are fetched on demand. `nuscenes_devkit.py` is the only module importing
`nuscenes`, keeping the heavy toolkit out of the service/runtime layers.

## Boundary Invariants

- **No external SDK leakage**: `boto3` is only imported in `app/repo/`. All other layers interact with B2 through the repo interface.
- **No raw dicts at boundaries**: All data crossing layer boundaries uses typed Pydantic models.
- **No cross-layer mutable state**: Configuration is read-only after init, and no mutable state is shared *between* layers. Intra-layer caches/counters (the listing cache in `repo/list_cache.py`, the B2 connectivity cache in `repo/b2_client.py`, the download counter in `repo/counter.py`, the rate-limit and metrics state in `runtime/`) are module-local and guarded by a `threading.Lock`. The listing cache also owns the only background thread in the app: a stale entry is served immediately while that thread re-scans (stale-while-revalidate), and `main.lifespan` warms it once at startup so no user pays for the cold full-bucket scan.
- **Validated inputs**: All HTTP inputs validated by FastAPI/Pydantic. File keys reject empty and path-traversal patterns; optional prefix confinement via `ALLOWED_KEY_PREFIX` (off by default).

## Deployment

- **Local dev** — `pnpm dev` runs both services via `concurrently`
  - Web: `localhost:3000`
  - API: `localhost:8000`
- **Railway** — two services from the same repository: `web` builds from the
  repository root because it consumes `packages/shared`; `api` builds from
  `services/api`. The versioned per-service configs and the human-approved
  staging/production contract live in [infra/railway/README.md](infra/railway/README.md).
- **Vercel** — one project using [Vercel Services](https://vercel.com/docs/services):
  the `web` (Next.js) and `api` (FastAPI) services build from the same repo and
  share one origin — the web app at `/`, the API under `/api`. The repo-root
  `vercel.json` declares both services and routes `/api/*` to the API service;
  the Vercel-only `services/api/index.py` strips the `/api` prefix so FastAPI
  keeps its native paths (`/health`, `/files`, …). Uploads go directly from the
  browser to B2 via a presigned PUT (see
  [File Upload](docs/features/file-upload.md)), so they bypass the Function's
  4.5 MB payload ceiling entirely — the bucket must allow the deploy origin in
  its CORS. A two-separate-Projects alternative and the full delivery contract
  live in [infra/vercel/README.md](infra/vercel/README.md).

External provisioning and deployment remain explicit user-approved actions.

## Data Stores

- **Backblaze B2** — object storage (S3-compatible API)
  - All uploaded files stored in a single bucket
  - File listing and metadata via S3 `list_objects_v2` / `head_object`
  - No application database — B2 is the sole data store

## External Services

- **Backblaze B2 S3 API** — file storage, retrieval, deletion, presigned URLs

## Trust Boundaries

See [docs/SECURITY.md](docs/SECURITY.md) for full security documentation.

- **Frontend -> API** — CORS-restricted to configured origins. `CORSMiddleware` is registered LAST in `main.py` (outermost) so it wraps **every** response, including uncaught-exception 500s — otherwise the browser would block error responses and the UI would only see an opaque "network error". See [docs/RELIABILITY.md](docs/RELIABILITY.md#error-handling). A per-IP rate-limit middleware sits inner to CORS; see [docs/SECURITY.md](docs/SECURITY.md#rate-limiting).
- **API -> B2** — authenticated via application keys, signature v4
- **Client -> B2** — presigned URLs for download (10-min expiry, forced attachment)

## Data Flows

- **Scene ingest**: Browser -> `POST /scenes` -> service slugs the scene, `scene_synth` generates referentially-valid tables + tiny blobs -> `nuscenes_lake` `put_object`s them under `nuscenes/<slug>/` -> summary response
- **Serve frame (index + resolve)**: Browser -> `POST /scenes/{token}/frame` -> `nuscenes_lake.materialize_dataroot` `get_object`s the JSON tables + map masks to a temp dir -> `nuscenes_devkit.build_index` runs the real `NuScenes(...)` -> resolve the keyframe's channels -> presign each blob (S3 `generate_presigned_url`) -> pull the LiDAR `.pcd.bin` to temp and load it via `LidarPointCloud.from_file` for real point-cloud stats -> `FrameManifest`
- **Scene list / detail**: Browser -> `GET /scenes` / `GET /scenes/{token}` -> `list_objects_v2` for `lake-meta.json` and the scene's `samples/` blobs
- **Scene edit**: Browser -> `POST /scenes/{token}` -> rewrite `lake-meta.json` + `scene.json`/`log.json` in B2
- **Scene delete**: Browser -> `DELETE /scenes/{token}` -> prefix-scoped `delete_objects` under `nuscenes/<slug>/` only
- **Upload (kept)**: Browser -> `POST /upload/presign` -> Browser PUTs bytes **directly to B2** -> `POST /upload/verify`
- **List / Download / Delete (kept)**: `GET /files`, `GET /files/{key}/download`, `DELETE /files/{key}`

## Observability

- Structured JSON logging on all requests with `request_id`
- Request timing middleware (logs duration per request; also the catch-all that converts uncaught exceptions to a typed JSON 500)
- `/metrics` endpoint (Prometheus format: request count, latency, upload count)
- `/health` endpoint (B2 connectivity check)

## API Contract

- Checked-in OpenAPI artifact: `docs/api/openapi.json`
- Export/check command: `pnpm contract:export` / `pnpm contract:check`
- FastAPI freshness test: `services/api/tests/test_openapi_contract.py`
- Frontend route drift test: `apps/web/src/lib/api-contract.test.ts`

The frontend client keeps a small `API_CLIENT_ROUTES` registry in
`apps/web/src/lib/api-client.ts`. Tests compare that registry to the checked-in
OpenAPI artifact so route changes fail loudly before the hand-written client can
silently drift from FastAPI. `GET /metrics` is intentionally server-only.

## Canonical Files

- Scenes route handler: `services/api/app/runtime/scenes.py`
- Scenes orchestration: `services/api/app/service/scenes.py`
- B2 dataset store (repo layer): `services/api/app/repo/nuscenes_lake.py`
- Devkit adapter (only `nuscenes` importer): `services/api/app/repo/nuscenes_devkit.py`
- Synthetic generator: `services/api/app/repo/scene_synth.py` + `scene_blobs.py`
- B2 S3 primitives (shared client): `services/api/app/repo/b2_client.py`
- Pydantic models: `services/api/app/types/` (`scenes.py`, `files.py`, `upload.py`, `stats.py`)
- Config (pydantic-settings): `services/api/app/config/settings.py`
- Structural tests: `services/api/tests/test_structure.py`
- Scene tests (real devkit): `services/api/tests/test_scenes.py`
- OpenAPI contract: `docs/api/openapi.json`
- Frontend API client: `apps/web/src/lib/api-client.ts`
- Shared TypeScript types: `packages/shared/src/types.ts`

## Core Features

- [Scene Ingest](docs/features/scene-ingest.md)
- [Scene Index & Serve](docs/features/scene-index-serve.md)
- [Sensor Asset Explorer](docs/features/sensor-asset-explorer.md)
- [Dashboard](docs/features/dashboard.md)
- [File Upload](docs/features/file-upload.md)
- [File Browser](docs/features/file-browser.md)
- [Metadata Extraction](docs/features/metadata-extraction.md)

## References

- [docs/SECURITY.md](docs/SECURITY.md) — security principles and implementation
- [docs/RELIABILITY.md](docs/RELIABILITY.md) — reliability expectations
- [AGENTS.md](AGENTS.md) — architectural invariants and agent instructions
