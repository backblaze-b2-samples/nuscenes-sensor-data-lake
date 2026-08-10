"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { SceneFormDialog } from "@/components/scenes/scene-form-dialog";
import { SensorAssetExplorer } from "@/components/scenes/sensor-asset-explorer";
import { ServeFramePanel } from "@/components/scenes/serve-frame-panel";
import { useDeleteScene, useScene } from "@/lib/queries";
import { LOCATIONS, labelFor } from "@/lib/scene-fields";

export function SceneDetail({ token }: { token: string }) {
  const { data: scene, isLoading, error, refetch } = useScene(token);
  const [editOpen, setEditOpen] = useState(false);
  const router = useRouter();
  const del = useDeleteScene();

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (error || !scene) {
    return (
      <ErrorState
        error={error ?? new Error("Scene not found")}
        onRetry={() => refetch()}
      />
    );
  }

  const onDelete = () =>
    del.mutate(scene.token, {
      onSuccess: (res) => {
        toast.success("Scene deleted", {
          description: `${res.objects_removed} objects removed from B2.`,
        });
        router.push("/scenes");
      },
      onError: (e) => toast.error("Delete failed", { description: e.message }),
    });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border pb-5">
        <div className="min-w-0">
          <h1 className="page-title truncate">{scene.name}</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            {labelFor(LOCATIONS, scene.location)} · {scene.time_of_day} · {scene.weather}
          </p>
          <div className="mt-3 flex flex-wrap gap-1.5">
            <Badge variant="secondary">{scene.keyframes} keyframes</Badge>
            <Badge variant="secondary">{scene.channels.length} channels</Badge>
            <Badge variant="secondary">{scene.blob_count} blobs</Badge>
            <Badge variant="outline">{scene.total_size_human}</Badge>
            <Badge variant="outline">{scene.sensor_suite}</Badge>
          </div>
          {scene.description && (
            <p className="mt-3 max-w-prose text-sm text-muted-foreground">{scene.description}</p>
          )}
        </div>
        <div className="flex shrink-0 gap-2">
          <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
            <Pencil className="h-3.5 w-3.5" />
            Edit
          </Button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="outline" size="sm">
                <Trash2 className="h-3.5 w-3.5" />
                Delete
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete this scene?</AlertDialogTitle>
                <AlertDialogDescription>
                  This permanently removes every object under{" "}
                  <code>nuscenes/{scene.token}/</code> in B2. This cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={onDelete}>Delete</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      <SceneFormDialog open={editOpen} onOpenChange={setEditOpen} scene={scene} />
      <ServeFramePanel token={scene.token} numKeyframes={scene.keyframes} />
      <SensorAssetExplorer scene={scene} />
    </div>
  );
}
