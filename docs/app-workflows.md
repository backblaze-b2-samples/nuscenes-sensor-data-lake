<!-- last_verified: 2026-08-10 -->
# App Workflows

User journeys inside the application. The primary journey is the Scene loop
(**Ingest → Index → Serve**); the generic Upload / Files / Settings journeys are
kept from the starter.

## Create a Scene (Ingest + Annotate)

- User navigates to `/scenes` and clicks **New scene**
- A dialog opens with **selectors, not free text**, for the finite-option fields:
  location (`boston-seaport`, `singapore-onenorth`, `singapore-queenstown`,
  `singapore-hollandvillage`), time of day (`day` | `night`), weather
  (`clear` | `rain`), keyframes (`3` | `5` | `10`), sensor suite (`full` 12-channel
  | `camera+lidar` minimal). Only name and description are free text.
- Safe defaults are pre-selected (`boston-seaport`, `day`, `clear`, `5`, `full`)
  with a hint that they "produce a sound demo scene you can index immediately" —
  a hint, never an autofill button
- On submit, the API synthesizes a referentially-valid nuScenes dataset and
  **ingests every sensor blob + the 13 annotation tables to B2** under
  `nuscenes/<slug>/`; a toast reports the blob count and, on success, the app
  auto-navigates to the new scene's detail page (its Serve panel) when the user
  is still on `/scenes` — otherwise the scene just appears in the list
- See: [Scene Ingest](features/scene-ingest.md)

## Open a Scene, explore its sensors, and Serve a frame (Index + Serve)

- User opens a scene from the list (`/scenes/[token]`)
- The **sensor asset explorer** lists the scene's B2 blobs grouped by channel
  (CAM_* / LIDAR_TOP / RADAR_*); expanding a camera channel previews its keyframes
  inline via presigned GET URLs, LiDAR/radar rows show per-blob size
- Clicking **Serve** (choosing a keyframe) materializes the JSON tables from B2,
  builds the in-memory index with the **real** `NuScenes(...)` devkit, resolves
  every sensor channel, presigns each blob, and computes **real** LiDAR
  point-cloud stats via `LidarPointCloud.from_file` — returning a per-frame
  training manifest (channels, annotations, point count, xyz/intensity ranges,
  devkit version)
- See: [Scene Index & Serve](features/scene-index-serve.md), [Sensor Asset Explorer](features/sensor-asset-explorer.md)

## Edit or delete a Scene

- **Edit** (`/scenes/[token]` → Edit): a pre-filled form (same selectors) updates
  name/description/location/time-of-day/weather; the API rewrites `lake-meta.json`
  and the nuScenes `scene.json`/`log.json` in B2
- **Delete** (list row or detail): an AlertDialog confirms, then the API removes
  every object under `nuscenes/<slug>/` — prefix-scoped, so no other scene is
  touched

## Upload Files

- User navigates to `/upload`
- Drops or selects files in the dropzone
- Client validates file size (max 100MB) and type
- Files upload **directly from the browser to B2** (a presigned PUT). A determinate progress bar tracks the bytes leaving the browser; once they are all sent the row switches to "Verifying upload..." with an *indeterminate* sweeping bar while the API HEADs and magic-byte-sniffs the stored object. That phase has no percentage to report, and a bar parked at a full 100% read as finished-but-stuck
- On success: toast notification, green checkmark, and a "View in Files" link through to the browser
- On failure: red status icon with error message
- User can clear completed uploads
- The queue lives in an app-wide provider: navigating to another page keeps the upload running, shows an "Uploading N files" indicator in the header, and keeps the duplicate-upload guard armed
- Reloading or closing mid-upload asks for confirmation first; if the upload dies anyway, the next load says which file didn't finish
- See: [File Upload](features/file-upload.md)

## Browse and Manage Files

- User navigates to `/files`
- Page loads the 100 most recent objects from the API (sorted most recent first). While it loads, the page says so on screen and escalates the wording if the wait runs long — a full bucket listing measured 2.8s-21s cold
- If that limit was hit, a notice states how many objects the bucket actually holds — the page never claims to show everything
- Files displayed in tree view with folders and type-specific icons
- Folders auto-expand on load until the *majority* of the listed files are reachable without clicking, so the page's own "click a file" instruction is always actionable. Stopping at the first visible file was not enough: one stray top-level object left the other 99 sealed in collapsed folders while the page claimed to show 100
- Clicking a file row opens its preview; the per-row actions menu (preview / download / delete) is always visible, on every viewport
- Arriving at `/files?preview=<key>` expands that file's folders and opens its preview directly. This is how the ⌘K palette and the dashboard's recent-uploads rows hand off a *specific* file; the param is consumed on arrival so it doesn't re-fire later
- **Preview**: opens dialog with image/PDF preview + metadata panel, and the file's Download / Delete actions — the advertised "click a file" path offers everything the row menu does. The loading state holds until the media paints; a failure offers "Open in a new tab". The preview URL is signed with `Content-Disposition: inline` so PDFs render in place
- **Download**: shows a pending state on the row plus a toast while the presigned URL is fetched, then starts the download via an anchor click (which, unlike a popup, still works if the click's user activation expired during a slow presign). Failures are reported; the click can never silently do nothing
- **Delete**: the confirmation dialog stays open showing "Deleting..." until the request settles, then the row disappears with the toast (optimistic cache update) and the list reconciles with the server. The dialog is held deliberately — Radix closes on action click by default, which dismissed the only pending state and left the row looking untouched while the delete was still in flight
- Empty bucket shows "No files found" with upload prompt
- See: [File Browser](features/file-browser.md)

## View Dashboard

- User navigates to `/` (home)
- Stat cards show the AV lake at a glance: scenes, keyframes, sensor blobs, and total lake size
- A blobs-by-modality bar chart breaks the lake down into camera / LiDAR / radar
- A recent-scenes table lists the latest scenes (name, location, blob count, created); each name links to the scene detail
- Empty state: "No scenes yet" with a prompt to create one
- See: [Dashboard](features/dashboard.md)

## Change Preferences

- User navigates to `/settings`
- A banner at the top states that the page is mostly a demonstration: only Theme is wired up for real, the rest showcases what a settings page can look like when you adapt the kit
- **Theme** (real): editing it and saving applies it immediately and persists it (`next-themes`), and the header's theme toggle drives the same state
- **Profile and preference fields** (demo): Display name, Bio, Default file view (Tree/List/Grid), Email me on every upload, Warn me when approaching quota + threshold. Each is labelled "Demo field", persists to `localStorage` only, and drives no behaviour — there is no account system, mailer, quota banner, activity log, or List/Grid view behind them yet
- Saving reports honestly: a success toast that separates the real theme change from the locally-stored demo values, or a warning toast if the browser blocked storage (theme still changes). It never claims a save that did not happen — the original page toasted "Settings saved" for fields that changed nothing
- Danger Zone actions are a demo — no real delete runs
- See: [Settings](features/settings.md)
