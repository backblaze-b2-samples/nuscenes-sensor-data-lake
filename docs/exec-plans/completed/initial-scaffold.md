# Build plan — `nuscenes-sensor-data-lake`

Scaffold a new B2 sample from `vibe-coding-starter-kit`. Source of truth for the
starter tree: `.claude/scratch/vcsk-c7cf2aff-0541-45d2-9903-83e40882f6bb/`
(cloned fresh in Phase 0 — do NOT clone again, do NOT read any sibling checkout).
Paths in this plan are relative to the sample root `./nuscenes-sensor-data-lake`
unless prefixed with the scratch path.

---

## 1. Purpose

`nuscenes-sensor-data-lake` shows Backblaze B2 as the **S3-compatible data lake for
an autonomous-vehicle multi-sensor dataset**, driven by the real
[nuScenes devkit](https://github.com/nutonomy/nuscenes-devkit). AV/robotics teams
building 3D-perception models keep terabyte-scale multi-modal recordings (360°
camera images, LiDAR point-cloud sweeps, radar sweeps) plus the nuScenes-format
annotation tables in B2, and stream frames on demand into training — never
co-locating the whole dataset on a training node. The app demonstrates the full
loop for a **Scene** (the primary entity): **Ingest** synthetic nuScenes-format
sensor blobs + annotation JSON to B2 → **Annotate** (the JSON tables that complete
the schema) → **Index** (materialize the lightweight tables locally and let the
*actual* `nuscenes.nuscenes.NuScenes` devkit build its in-memory scene graph) →
**Serve/Query** (resolve a keyframe's sensors via the devkit, presign B2 URLs, and
return a per-frame training manifest with real point-cloud stats). B2 credentials
only — no second API key, all local OSS.

**Honest framing (must be reflected in README/docs, not overstated):** B2 is the
system of record for every sensor blob and annotation table. The devkit needs a
local `dataroot`, so the app **materializes only the small JSON annotation tables**
locally to build the in-memory index; **sensor blobs stay in B2** and are fetched
on demand (presigned GET, or pulled to a temp file only when computing real
point-cloud stats). That is exactly the "stream from a B2 lake without co-locating
the dataset" story — do not claim the multi-GB blobs live locally.

---

## 2. Architecture delta from `vibe-coding-starter-kit`

The starter kit is the ceiling. This app mostly **adds a domain layer** on top of a
lean base; almost nothing is removed. Backend layering
(`types → config → repo → service → runtime`), no-boto3-outside-`repo/`, thin
routes, TanStack-Query-only fetching, and the shadcn `components/ui/` primitives are
all invariants — keep them.

### KEEP (as-is)
- **Full-bucket File Explorer** — `/files` route, `apps/web/src/app/files/`,
  `apps/web/src/components/files/`, and the Files sidebar entry. **Non-negotiable
  keep** (starter contract + skill rule). Never remove it.
- **Upload** — `/upload` route + `apps/web/src/components/upload/` and the Upload
  sidebar entry. Starter-contract keep. The generic upload coexists with the
  domain-specific Scene ingest.
- **shadcn UI kit** (`components/ui/**` — never edit generated files), design tokens
  in `globals.css`, and the `/design` reference page + its sidebar util link.
- **Settings** page as an honest demo showcase (theme is the one real preference).
  Keep; it is the in-repo exemplar for form UX (§4).
- Backend `repo/b2_client.py` S3 primitives (put/get/list/head/delete/presign),
  `list_cache.py`, health, metrics, rate-limit, the request-id/timing middleware,
  the whole test/verify harness, CI, `scripts/`, Vercel/Railway infra.
- The sidebar shell, header, theme provider, command palette.

### TRIM (remove from starter)
- **Dashboard illustrative defaults** — rewrite (not delete) the dashboard so it
  reflects the AV lake (§4 Dashboard). `components/dashboard/*` get AV-appropriate
  content; new aggregations flow through `runtime → service → repo` and TanStack
  Query hooks in `lib/queries.ts` (AGENTS.md §2 mandates this rewrite).
- Starter-specific exec-plans under `docs/exec-plans/completed/*` — remove the
  starter's historical plans (they describe the starter, not this app). Keep the
  `active/` + `completed/` dirs (with `.gitkeep`) and the `tech-debt-tracker.md`
  shell. The scaffold plan lands in `docs/exec-plans/completed/initial-scaffold.md`
  (Phase 5).
- Do **not** trim PyPDF2 / metadata extraction — the generic Upload path uses it and
  tests cover it; removing it breaks gates for no benefit.

### ADD (new for this app)
- **Scenes domain** — the primary-entity surface (full CRUD + run, §4):
  - Backend: `repo/nuscenes_lake.py` (B2-backed dataset store: ingest blobs +
    tables, materialize a scene's JSON dataroot from B2, delete a scene prefix,
    presign sensor blobs), `repo/nuscenes_devkit.py` (thin adapter that imports and
    drives the real `NuScenes` class + `LidarPointCloud`), `repo/scene_synth.py`
    (synthetic nuScenes-format generator — §6), `service/scenes.py` (Scene
    lifecycle orchestration), `runtime/scenes.py` (thin routes), `types/scenes.py`
    (Pydantic models). Keep every authored `app/**` Python file **< 300 lines**
    (enforced) — split if needed.
  - Frontend: `/scenes` (list + create), `/scenes/[token]` (detail = the
    **sample-specific asset explorer** scoped to the scene's B2 prefix, grouped by
    sensor channel, with a "Serve frame" action). Add a **Scenes** sidebar entry
    (below Dashboard). Add TanStack Query hooks in `lib/queries.ts`; add every new
    route to `lib/api-client.ts` `API_CLIENT_ROUTES`.
- **Scene-scoped asset explorer** (the mandatory sample-specific explorer, distinct
  from the kept full-bucket `/files`): the `/scenes/[token]` detail view lists the
  scene's sensor blobs from B2 grouped by channel (CAM_* / LIDAR_TOP / RADAR_*),
  previews camera images inline (presigned), and shows LiDAR/radar blob stats.

---

## 3. B2 surface (all via S3-compatible API — Standard #1, no b2-native)

Every operation is plain S3 through the existing `repo/b2_client.py` boto3 client
(custom user-agent set — Standard #2). New repo code MUST route through this client;
no new boto3 sessions elsewhere (enforced by `test_structure.py`).

| Operation | S3 call | Used by |
|-----------|---------|---------|
| Ingest sensor blobs + annotation JSON | `put_object` | Scene create (Ingest/Annotate) |
| List a scene's blobs (prefix-scoped) + full bucket | `list_objects_v2` (paginated) | Asset explorer, dashboard stats, full `/files` |
| Materialize JSON tables locally; fetch a blob to temp for point-cloud stats | `get_object` | Scene index + Serve frame |
| Serve sensor blobs to the training client / inline preview | `generate_presigned_url` (GET) | Serve frame, asset explorer preview |
| Delete a scene (prefix-scoped) | `delete_object` per key under the scene prefix | Scene delete |
| Blob metadata | `head_object` | detail views |

No b2-native API anywhere. A `get_object`→bytes helper and a prefix-scoped batch
delete are the only new repo primitives; both wrap the shared client.

**Dataset layout in B2 — each Scene is a self-contained nuScenes dataset** (avoids
any shared-table read-modify-write race; makes CRUD a clean prefix operation):
```
nuscenes/<scene_slug>/v1.0-demo/<table>.json     # the 13 annotation tables
nuscenes/<scene_slug>/samples/<CHANNEL>/<file>    # keyframe sensor blobs
```
`sample_data.filename` stays relative (`samples/CAM_FRONT/<file>.jpg`) so B2 key =
`nuscenes/<scene_slug>/<filename>`, and the materialized local dataroot's root maps
1:1 to `nuscenes/<scene_slug>/`. Delete a scene = delete everything under
`nuscenes/<scene_slug>/`. (Delete scoping honors CLAUDE.local.md: only the scene's
own prefix is ever removed.)

---

## 4. Key features

1. **Scene ingest (create + Annotate)** — synthesize a referentially-valid
   nuScenes-format scene (N keyframes across the nuScenes sensor suite), upload the
   sensor blobs and the JSON annotation tables to B2 under the scene's prefix. This
   is the "Ingest" + "Annotate" workflow steps in one create action.
2. **Scene index + Serve frame (run)** — materialize the scene's JSON tables from B2
   into a temp dataroot, instantiate the **real** `NuScenes('v1.0-demo', dataroot)`
   devkit to build the in-memory scene graph, then for a chosen keyframe use
   `nusc.get('sample', token)` / `nusc.get_sample_data(...)` to resolve every sensor
   channel, presign each blob's B2 URL, and compute **real point-cloud stats** by
   pulling the tiny LiDAR `.pcd.bin` to a temp file and loading it through
   `nuscenes.utils.data_classes.LidarPointCloud.from_file` (point count, xyz bounds,
   intensity range). Returns the per-frame training manifest.
3. **Scene-scoped sensor asset explorer (read)** — `/scenes/[token]` lists the
   scene's B2 blobs grouped by channel, inline-previews camera keyframes (presigned),
   and shows per-blob size/type; the full-bucket `/files` explorer stays alongside.
4. **Scene metadata edit (edit)** — rename / re-describe a scene (name, description,
   location, time-of-day); rewrites the scene's `scene.json`/`log.json` in B2.
5. **AV-lake dashboard** — replaces the starter dashboard: stat cards (scenes,
   keyframes indexed, sensor blobs by modality: camera / LiDAR / radar, total lake
   size), a blobs-by-modality chart, and a recent-scenes table.
6. **Delete scene (delete)** — prefix-scoped wipe of the scene's B2 objects with an
   AlertDialog confirm.

### External API provider
| Feature | Provider/model | deployment | est. cost / demo run | key env var |
|---------|----------------|------------|----------------------|-------------|
| All (index/serve/synth) | **none** — nuScenes devkit (local OSS) + numpy/opencv/Pillow | **local** | **$0** | none |

- No external API. Per `api-provider-selection.md`, a purely-local feature is
  `deployment: local`. There is **no GPU/tensor workload** here — the devkit is a
  data toolkit (numpy/opencv/pyquaternion/matplotlib), CPU-only; no CUDA/MPS/CPU
  autodetect path is needed and none should be hard-required. Record `deployment:
  local` in `build-result` context; **no key beyond `B2_*`**.
- **No Genblaze** — the description does not mention Genblaze / `genblaze-*` /
  `genblaze-s3`, so provider-orchestration routing does not apply.

### Primary-entity lifecycle — entity = **Scene**
DEFAULT is that the UI exposes every verb, and it does:
| Verb | UI surface |
|------|-----------|
| create | `/scenes` "New Scene" form → ingest to B2 |
| read | `/scenes` list + `/scenes/[token]` detail (scoped asset explorer) |
| edit | `/scenes/[token]` edit form (name/description/location/time-of-day) |
| delete | `/scenes/[token]` (and list row) delete → AlertDialog confirm, prefix-scoped |
| run | `/scenes/[token]` "Serve frame" → index + resolve + presign + point-cloud stats |

No verb is omitted → `omitted_ui_verbs` is expected to be **empty**. Stay scoped to
this one entity and these verbs.

### Form UX conventions (create/edit Scene forms) — follow the `settings-form.tsx` exemplar
- **Selector fields (finite value sets → `Select` / `RadioGroup`, never free text),
  on both create and edit:**
  - `location` → `Select` of real nuScenes locations: `boston-seaport`,
    `singapore-onenorth`, `singapore-queenstown`, `singapore-hollandvillage`.
  - `timeOfDay` → `RadioGroup`: `day` | `night`.
  - `weather` → `Select`: `clear` | `rain`.
  - `keyframes` (count, create-only) → `Select`: `3` | `5` | `10`.
  - `sensorSuite` (create-only) → `Select`: `full` (12-channel nuScenes suite) |
    `camera+lidar` (CAM_FRONT + LIDAR_TOP + RADAR_FRONT minimal). Free-text fields:
    only `name` and `description`.
- **Create-form safe defaults as placeholder / `FormDescription` guidance (never an
  autofill button):** name placeholder e.g. `"scene-boston-01"`; default
  `location=boston-seaport`, `timeOfDay=day`, `weather=clear`, `keyframes=5`,
  `sensorSuite=full`, surfaced as the pre-selected value + a `FormDescription`
  line ("Defaults produce a sound demo scene you can index immediately").
- The edit form opens pre-filled from the real scene (no default-hint rule there).

---

## 5. Doc transforms
- **Rewrite** `docs/features/dashboard.md` (AV-lake metrics). **Rewrite**
  `docs/features/file-browser.md` only if wording ties it to the starter; the
  full-bucket browser behavior is unchanged, so prefer light edits.
- **Keep** `docs/features/file-upload.md`, `metadata-extraction.md`, `settings.md`
  (behavior unchanged), with name/wording updated by the rename table.
- **Add** feature docs (use `docs/features/_template.md`): `scene-ingest.md`,
  `scene-index-serve.md`, `sensor-asset-explorer.md`.
- **Update** `README.md` (hero, quick start, feature list, the honest B2-lake
  framing from §1), `ARCHITECTURE.md` (new Scenes domain + data flow), `AGENTS.md`
  repository-map note for the Scenes domain, `docs/app-workflows.md` (Ingest →
  Index → Serve journey). Keep AGENTS.md within its size gate (≥1KB, ≤20KB,
  ≤250 lines) and keep the mechanical-enforcement table honest.
- Rewrite the starter README hero; **remove** starter-history exec-plans (§2 Trim).

---

## 6. Synthetic nuScenes generator — the build's crux (get this right)

Vendor fidelity (team rule) means the app MUST import and drive the real devkit, not
reimplement it. So the generator must emit a dataset the devkit actually loads.

- `NuScenes(version, dataroot)` loads exactly these 13 JSON tables from
  `<dataroot>/<version>/` and builds reverse indexes over them — they must be
  **referentially consistent** (every referenced token exists; `first/last_*` chains
  and `next/prev` links are valid; `nbr_samples` matches):
  `category, attribute, visibility, instance, sensor, calibrated_sensor, ego_pose,
  log, scene, sample, sample_data, sample_annotation, map`.
- `NuScenes.__init__` does **not** require the blob files to exist on disk (it only
  reads JSON), so **Index** needs only the JSON materialized locally — blobs stay in
  B2. File existence matters only when computing point-cloud stats, where the app
  pulls the one tiny `.pcd.bin` to a temp file on demand.
- **Blob formats (tiny, deterministic):**
  - Camera (`CAM_*`): a small JPEG (e.g. 64×36) via Pillow.
  - LiDAR (`LIDAR_TOP`): nuScenes `.pcd.bin` = raw `float32` array shape `(N, 5)`
    = `x, y, z, intensity, ring_index`, small N (e.g. 60). Must round-trip through
    `LidarPointCloud.from_file` — this is the real-devkit-compute proof.
  - Radar (`RADAR_*`): store/serve/count as opaque blobs (a minimal placeholder
    `.pcd`); do **not** require `RadarPointCloud.from_file` round-trip (its 18-field
    PCD header is fiddly and not needed to prove the lake). Note this simplification
    in `docs/features/scene-index-serve.md`.
- **Scale (keep it tiny, a few hundred KB per scene):** `full` suite = the real 12
  nuScenes channels (`CAM_FRONT, CAM_FRONT_RIGHT, CAM_BACK_RIGHT, CAM_BACK,
  CAM_BACK_LEFT, CAM_FRONT_LEFT, LIDAR_TOP, RADAR_FRONT, RADAR_FRONT_LEFT,
  RADAR_FRONT_RIGHT, RADAR_BACK_LEFT, RADAR_BACK_RIGHT`); `camera+lidar` = `CAM_FRONT,
  LIDAR_TOP, RADAR_FRONT`. `keyframes` samples per scene, chained via `next/prev`.
  A couple of categories/instances/annotations are enough for `get_sample_data` to
  return boxes.
- **Fallback if the full generator proves fragile within the round budget:** reduce
  to the `camera+lidar` minimal suite as the built default, but NEVER drop
  referential integrity or the real `NuScenes(...)` instantiation + real
  `LidarPointCloud.from_file` call. Document whatever suite ships.

---

## 7. Dependency & lock (install-risk — treat carefully)

- Add to `services/api/requirements.txt` (lower-bound `>=` pins **only** —
  `tests/test_dependency_lock.py` enforces that): `nuscenes-devkit>=1.1.11`,
  `numpy` (pin a nuScenes-compatible bound, e.g. `numpy>=1.26,<2` — nuScenes-devkit
  historically breaks on numpy 2.x). `opencv-python`, `matplotlib`, `pyquaternion`,
  `Shapely`, `scikit-learn` arrive transitively via nuscenes-devkit; add explicit
  `>=` lines for any the app imports directly. `Pillow` is already present.
- **Regenerate `services/api/requirements.lock`** via the reviewed pip-compile
  workflow in `docs/dev-workflows.md#python-dependency-updates` (NOT `pip freeze`)
  and confirm a **clean-venv install succeeds on Python 3.12** — nuscenes-devkit
  pulls heavy/older transitive deps (`descartes`, `matplotlib`, `opencv`) that can
  fail to resolve; if a transitive dep won't build on 3.12, pin the nearest working
  versions and record it. A lock that only "looks" complete but fails a fresh
  install is a false green (team-known failure mode).
- `nuscenes-devkit` is imported **only** inside `repo/` (adapter), keeping heavy
  imports out of the service/runtime layers and honoring the no-SDK-outside-repo
  rule.

---

## 8. Rename table (`vibe-coding-starter-kit` → `nuscenes-sensor-data-lake`)

| Surface | From | To |
|---------|------|----|
| Repo / kebab id | `vibe-coding-starter-kit` | `nuscenes-sensor-data-lake` |
| Frontend display name (`apps/web/src/lib/app-config.ts` `APP_NAME` — the ONE place) | `Vibe Coding Starter Kit` | `nuScenes Sensor Data Lake` |
| `APP_DESCRIPTION` | file-mgmt template blurb | `Autonomous-vehicle multi-sensor data lake on Backblaze B2, indexed with the nuScenes devkit` |
| FastAPI `API_TITLE` (main.py) — must derive as `${APP_NAME} API` | `Vibe Coding Starter Kit API` | `nuScenes Sensor Data Lake API` (+ description mentions the name; re-export `docs/api/openapi.json`) |
| Root `package.json` `name` + workspace pkg names | `vibe-coding-starter-kit*` | `nuscenes-sensor-data-lake*` |
| **B2 attribution token** — the single value across every `user_agent_extra` (`b2_client.py`, `scripts/setup_b2_cors.py`) AND every `utm_content=` (README ×3, `app-sidebar.tsx`, `scripts/doctor.mjs`) | `b2ai-oss-start` | `nuscenes-sensor-data-lake` |
| Railway/Vercel service names, image tags, workflow slugs | `vibe-coding-starter-kit*` | `nuscenes-sensor-data-lake*` |
| Titles/headings across README, docs, ARCHITECTURE, AGENTS shims | starter name | nuScenes Sensor Data Lake |

**Env-var standardization (Standard #3 — parent CLAUDE.md; reviewer enforces).** The
starter deviates (`B2_KEY_ID`, `B2_ENDPOINT`, `B2_PUBLIC_URL`, no `B2_REGION`).
Rename to the standard names so `/b2-doctor` and the reviewer pass:
| From (starter) | To (Standard #3) |
|----------------|------------------|
| `B2_KEY_ID` | `B2_APPLICATION_KEY_ID` |
| `B2_APPLICATION_KEY` | `B2_APPLICATION_KEY` (unchanged) |
| `B2_BUCKET_NAME` | `B2_BUCKET_NAME` (unchanged) |
| `B2_PUBLIC_URL` | `B2_PUBLIC_URL_BASE` |
| *(add)* | `B2_REGION` (e.g. `us-west-004`) |
- `settings.py`: rename the fields (`b2_application_key_id`, `b2_public_url_base`),
  add `b2_region`, and **derive** `b2_endpoint` as
  `https://s3.{b2_region}.backblazeb2.com` when no explicit endpoint is set; keep an
  optional `B2_ENDPOINT` override (some B2 setups need the literal endpoint). Update
  `main.py` `REQUIRED_B2_SETTINGS`/placeholder set, `b2_client.py`,
  `scripts/setup_b2_cors.py`, `.env.example`, `tests/conftest.py` + any test that
  sets these, `scripts/doctor.mjs`, and all docs. Re-run the agent-docs env checks.
  Keep `B2_REGION` from false-BLOCKing seed-env if it has a sane default.

---

## Build/verify contract (for the builder)
- `pnpm run setup` (needs a venv), then the credential-free gate `pnpm verify`
  (chains `check:agent-docs` → `verify:api` → `verify:web`) must pass. Every
  route change re-exports `docs/api/openapi.json` (`pnpm contract:export`);
  backend-only routes also go in `SERVER_ONLY_OPERATIONS`
  (`apps/web/src/lib/api-contract.test.ts`). Add/adjust tests for every new
  behavior. Lint clean (ruff T20/I001; eslint eqeqeq). Strip `.git` history.
- Do NOT push, create binary assets/screenshots, or touch any sibling in `../`.
