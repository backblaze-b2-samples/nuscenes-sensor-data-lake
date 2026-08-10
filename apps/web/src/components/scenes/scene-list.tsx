"use client";

import Link from "next/link";
import { useState } from "react";
import { Radar, Plus, Trash2, ArrowRight } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
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
import { useDeleteScene, useScenes } from "@/lib/queries";
import { LOCATIONS, labelFor } from "@/lib/scene-fields";
import type { SceneSummary } from "@nuscenes-sensor-data-lake/shared";

export function SceneList() {
  const { data: scenes = [], isLoading, error, refetch } = useScenes();
  const [createOpen, setCreateOpen] = useState(false);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-end">
        <Button size="sm" className="h-8" onClick={() => setCreateOpen(true)}>
          <Plus className="h-3.5 w-3.5" />
          New scene
        </Button>
      </div>
      <SceneFormDialog open={createOpen} onOpenChange={setCreateOpen} />

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-44 w-full" />
          ))}
        </div>
      ) : error ? (
        <ErrorState error={error} onRetry={() => refetch()} />
      ) : scenes.length === 0 ? (
        <EmptyState
          icon={Radar}
          title="No scenes yet"
          description="Create a scene to synthesize a nuScenes-format multi-sensor recording and ingest it to your B2 lake."
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {scenes.map((scene) => (
            <SceneCard key={scene.token} scene={scene} />
          ))}
        </div>
      )}
    </div>
  );
}

function SceneCard({ scene }: { scene: SceneSummary }) {
  const del = useDeleteScene();

  const onDelete = () =>
    del.mutate(scene.token, {
      onSuccess: (res) =>
        toast.success("Scene deleted", {
          description: `${res.objects_removed} objects removed from nuscenes/${scene.token}/`,
        }),
      onError: (error) => toast.error("Delete failed", { description: error.message }),
    });

  return (
    <Card className="card-hover">
      <CardHeader className="flex flex-row items-start justify-between gap-2 border-b border-border py-4 px-5">
        <div className="min-w-0">
          <CardTitle className="card-title truncate" title={scene.name}>
            {scene.name}
          </CardTitle>
          <p className="mt-1 text-xs text-muted-foreground truncate">
            {labelFor(LOCATIONS, scene.location)}
          </p>
        </div>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0" aria-label="Delete scene">
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete this scene?</AlertDialogTitle>
              <AlertDialogDescription>
                This permanently removes every object under{" "}
                <code>nuscenes/{scene.token}/</code> in B2 ({scene.blob_count} sensor
                blobs plus annotation tables). This cannot be undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={onDelete}>Delete</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </CardHeader>
      <CardContent className="space-y-3 px-5 py-4">
        <div className="flex flex-wrap gap-1.5">
          <Badge variant="secondary">{scene.time_of_day}</Badge>
          <Badge variant="secondary">{scene.weather}</Badge>
          <Badge variant="outline">{scene.sensor_suite}</Badge>
        </div>
        <dl className="grid grid-cols-3 gap-2 text-xs">
          <Stat label="Keyframes" value={scene.keyframes} />
          <Stat label="Blobs" value={scene.blob_count} />
          <Stat label="Size" value={scene.total_size_human} />
        </dl>
        <Button asChild variant="outline" size="sm" className="w-full">
          <Link href={`/scenes/${scene.token}`}>
            Open scene
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </Button>
      </CardContent>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-mono tabular-nums">{value}</dd>
    </div>
  );
}
