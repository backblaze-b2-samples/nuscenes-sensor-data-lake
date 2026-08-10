"use client";

import { useMemo, useState } from "react";
import { Camera, ChevronDown, ChevronRight, Radar, Radio } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { usePreviewUrl } from "@/lib/queries";
import { MODALITY_DOT, MODALITY_LABELS } from "@/lib/scene-fields";
import type { SceneDetail, SensorBlob, SensorModality } from "@nuscenes-sensor-data-lake/shared";

const MODALITY_ICON = {
  camera: Camera,
  lidar: Radar,
  radar: Radio,
} as const;

interface ChannelGroup {
  channel: string;
  modality: SensorModality;
  blobs: SensorBlob[];
  totalSize: number;
}

export function SensorAssetExplorer({ scene }: { scene: SceneDetail }) {
  const groups = useMemo(() => groupByChannel(scene.blobs), [scene.blobs]);

  return (
    <Card>
      <CardHeader className="border-b border-border py-4 px-5">
        <CardTitle className="card-title">Sensor assets</CardTitle>
        <p className="mt-1 text-xs text-muted-foreground">
          Blobs stored in B2 under <code>nuscenes/{scene.token}/samples/</code>, grouped by
          sensor channel. Camera keyframes preview inline via presigned GET URLs.
        </p>
      </CardHeader>
      <CardContent className="p-0">
        {groups.length === 0 ? (
          <p className="p-5 text-sm text-muted-foreground">No sensor blobs found for this scene.</p>
        ) : (
          <ul className="divide-y divide-border">
            {groups.map((group) => (
              <ChannelRow key={group.channel} group={group} />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function ChannelRow({ group }: { group: ChannelGroup }) {
  const [open, setOpen] = useState(false);
  const Icon = MODALITY_ICON[group.modality];
  const humanSize = group.blobs[0]?.size_human ?? "";

  return (
    <li>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 px-5 py-3 text-left hover:bg-muted/40 transition-colors"
      >
        {open ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        )}
        <span className={`inline-block h-2 w-2 rounded-full ${MODALITY_DOT[group.modality]}`} />
        <Icon className="h-4 w-4 text-muted-foreground" />
        <span className="font-mono text-sm">{group.channel}</span>
        <Badge variant="secondary" className="ml-1">
          {MODALITY_LABELS[group.modality]}
        </Badge>
        <span className="ml-auto text-xs text-muted-foreground tabular-nums">
          {group.blobs.length} blob{group.blobs.length === 1 ? "" : "s"} · {humanSize} each
        </span>
      </button>
      {open && (
        <div className="px-5 pb-4">
          {group.modality === "camera" ? (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-5">
              {group.blobs.map((blob) => (
                <CameraThumb key={blob.key} blob={blob} />
              ))}
            </div>
          ) : (
            <ul className="space-y-1">
              {group.blobs.map((blob) => (
                <li
                  key={blob.key}
                  className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-xs"
                >
                  <span className="font-mono truncate">{blob.filename.split("/").pop()}</span>
                  <span className="text-muted-foreground tabular-nums">{blob.size_human}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </li>
  );
}

function CameraThumb({ blob }: { blob: SensorBlob }) {
  // Lazy: only mounted (and only fetched) once its channel group is open.
  const { data, isLoading } = usePreviewUrl(blob.key, true);
  const name = blob.filename.split("/").pop();

  return (
    <figure className="space-y-1">
      {isLoading || !data ? (
        <Skeleton className="aspect-video w-full rounded-md" />
      ) : (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={data.url}
          alt={name}
          className="aspect-video w-full rounded-md border border-border object-cover"
        />
      )}
      <figcaption className="truncate font-mono text-[10px] text-muted-foreground" title={name}>
        {name}
      </figcaption>
    </figure>
  );
}

function groupByChannel(blobs: SensorBlob[]): ChannelGroup[] {
  const map = new Map<string, ChannelGroup>();
  for (const blob of blobs) {
    const existing = map.get(blob.channel);
    if (existing) {
      existing.blobs.push(blob);
      existing.totalSize += blob.size_bytes;
    } else {
      map.set(blob.channel, {
        channel: blob.channel,
        modality: blob.modality,
        blobs: [blob],
        totalSize: blob.size_bytes,
      });
    }
  }
  return [...map.values()].sort((a, b) => a.channel.localeCompare(b.channel));
}
