"use client";

import { useState } from "react";
import { Loader2, Play } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useServeFrame } from "@/lib/queries";
import { MODALITY_LABELS } from "@/lib/scene-fields";
import type { FrameManifest } from "@nuscenes-sensor-data-lake/shared";

export function ServeFramePanel({
  token,
  numKeyframes,
}: {
  token: string;
  numKeyframes: number;
}) {
  const [keyframe, setKeyframe] = useState("0");
  const serve = useServeFrame(token);
  const manifest = serve.data;

  const onRun = () =>
    serve.mutate(Number(keyframe), {
      onError: (error) => toast.error("Index failed", { description: error.message }),
    });

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3 border-b border-border py-4 px-5">
        <div>
          <CardTitle className="card-title">Serve frame</CardTitle>
          <p className="mt-1 text-xs text-muted-foreground">
            Materializes the JSON tables from B2, builds the in-memory index with the
            real nuScenes devkit, and returns a per-frame training manifest.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={keyframe} onValueChange={setKeyframe}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Array.from({ length: numKeyframes }).map((_, i) => (
                <SelectItem key={i} value={String(i)}>
                  Keyframe {i}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button size="sm" onClick={onRun} disabled={serve.isPending}>
            <Play className="h-3.5 w-3.5" />
            {serve.isPending ? "Indexing..." : "Serve"}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-5">
        {serve.isPending ? (
          <div className="flex items-start gap-3 text-sm text-muted-foreground">
            <Loader2 aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 animate-spin" />
            <p>
              Materializing JSON tables from B2 → building the nuScenes index → resolving
              the keyframe → downloading one LiDAR blob and computing point-cloud stats…
            </p>
          </div>
        ) : manifest ? (
          <FrameResult manifest={manifest} />
        ) : (
          <p className="text-sm text-muted-foreground">
            Pick a keyframe and run Serve to resolve every sensor channel through the
            devkit, presign each blob&apos;s B2 URL, and compute real LiDAR point-cloud
            stats.
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function FrameResult({ manifest }: { manifest: FrameManifest }) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <Badge variant="secondary">keyframe {manifest.keyframe_index} / {manifest.num_keyframes - 1}</Badge>
        <Badge variant="secondary">{manifest.frames.length} channels</Badge>
        <Badge variant="secondary">{manifest.num_annotations} annotations</Badge>
        <Badge variant="outline">devkit {manifest.devkit_version}</Badge>
      </div>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs sm:grid-cols-3">
        <Field label="Sample token" value={manifest.sample_token.slice(0, 12) + "…"} mono />
        <Field label="Timestamp" value={String(manifest.timestamp)} mono />
        <Field
          label="Ego translation"
          value={manifest.ego_translation.map((n) => n.toFixed(1)).join(", ")}
          mono
        />
      </dl>

      {manifest.lidar_stats && (
        <div className="rounded-md border border-border p-3">
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            LiDAR point cloud ({manifest.lidar_stats.channel}) — computed via
            LidarPointCloud.from_file
          </h4>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs sm:grid-cols-4">
            <Field label="Points" value={String(manifest.lidar_stats.num_points)} mono />
            <Field
              label="x range"
              value={`${manifest.lidar_stats.x_min.toFixed(1)} … ${manifest.lidar_stats.x_max.toFixed(1)}`}
              mono
            />
            <Field
              label="y range"
              value={`${manifest.lidar_stats.y_min.toFixed(1)} … ${manifest.lidar_stats.y_max.toFixed(1)}`}
              mono
            />
            <Field
              label="intensity"
              value={`${manifest.lidar_stats.intensity_min.toFixed(0)} … ${manifest.lidar_stats.intensity_max.toFixed(0)}`}
              mono
            />
          </dl>
        </div>
      )}

      <div>
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Resolved sensors (presigned B2 URLs)
        </h4>
        <ul className="space-y-1">
          {manifest.frames.map((frame) => (
            <li
              key={frame.key}
              className="flex items-center gap-2 rounded-md border border-border px-3 py-2 text-xs"
            >
              <span className="font-mono">{frame.channel}</span>
              <Badge variant="outline">{MODALITY_LABELS[frame.modality]}</Badge>
              <a
                href={frame.url}
                target="_blank"
                rel="noopener noreferrer"
                className="ml-auto truncate text-muted-foreground underline-offset-4 hover:underline"
                title={frame.filename}
              >
                {frame.filename.split("/").pop()}
              </a>
              <span className="text-muted-foreground tabular-nums">{frame.size_human}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={mono ? "font-mono tabular-nums" : ""}>{value}</dd>
    </div>
  );
}
