import { SceneList } from "@/components/scenes/scene-list";

export default function ScenesPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5">
        <h1 className="page-title">Scenes</h1>
        <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">
          Each scene is a self-contained nuScenes-format multi-sensor recording stored
          under its own prefix in Backblaze B2. Create one to ingest synthetic camera,
          LiDAR and radar blobs plus the annotation tables, then open it to index and
          serve frames with the real nuScenes devkit.
        </p>
      </div>
      <div className="animate-fade-in-up stagger-2">
        <SceneList />
      </div>
    </div>
  );
}
