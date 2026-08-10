"use client";

import Link from "next/link";
import { ArrowRight, Radar } from "lucide-react";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { useScenes } from "@/lib/queries";
import { LOCATIONS, labelFor } from "@/lib/scene-fields";
import { formatDate } from "@/lib/utils";

export function RecentScenesTable() {
  const { data: scenes = [], isLoading, error, refetch } = useScenes();
  const recent = scenes.slice(0, 8);

  return (
    <Card>
      <CardHeader className="border-b border-border py-4 px-5">
        <CardTitle className="card-title">Recent scenes</CardTitle>
        <CardAction className="self-center">
          <Link
            href="/scenes"
            className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
          >
            View all
            <ArrowRight className="h-3 w-3" />
          </Link>
        </CardAction>
      </CardHeader>
      <CardContent className="p-0">
        {isLoading ? (
          <div className="p-4 space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : error ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : recent.length === 0 ? (
          <EmptyState
            icon={Radar}
            title="No scenes yet"
            description="Head to Scenes to create your first multi-sensor recording."
          />
        ) : (
          <Table className="table-fixed">
            <TableHeader>
              <TableRow className="bg-muted/40 hover:bg-muted/40">
                <TableHead className="w-[36%] text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Scene
                </TableHead>
                <TableHead className="w-[28%] text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Location
                </TableHead>
                <TableHead className="w-[12%] text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Blobs
                </TableHead>
                <TableHead className="w-[24%] text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Created
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {recent.map((scene) => (
                <TableRow key={scene.token} className="table-row-hover">
                  <TableCell className="font-medium">
                    <Link
                      href={`/scenes/${scene.token}`}
                      className="block truncate rounded-sm underline-offset-4 hover:underline"
                      title={scene.name}
                    >
                      {scene.name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground whitespace-nowrap truncate">
                    {labelFor(LOCATIONS, scene.location)}
                  </TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground tabular-nums">
                    {scene.blob_count}
                  </TableCell>
                  <TableCell className="text-muted-foreground whitespace-nowrap">
                    {formatDate(scene.created_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
