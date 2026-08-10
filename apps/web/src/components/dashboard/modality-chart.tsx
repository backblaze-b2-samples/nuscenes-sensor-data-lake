"use client";

import { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { BarChart3 } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  type ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useLakeStats } from "@/lib/queries";

const chartConfig = {
  blobs: { label: "Blobs", color: "var(--chart-1)" },
} satisfies ChartConfig;

export function ModalityChart() {
  const { data: stats, isLoading, error, refetch } = useLakeStats();

  const data = useMemo(() => {
    const m = stats?.blobs_by_modality;
    if (!m) return [];
    return [
      { modality: "Camera", blobs: m.camera },
      { modality: "LiDAR", blobs: m.lidar },
      { modality: "Radar", blobs: m.radar },
    ];
  }, [stats]);

  const total = data.reduce((sum, d) => sum + d.blobs, 0);

  return (
    <Card>
      <CardHeader className="border-b border-border py-4 px-5">
        <CardTitle className="card-title">Sensor blobs by modality</CardTitle>
        <CardDescription className="text-xs">Across every scene in the lake</CardDescription>
      </CardHeader>
      <CardContent className="p-5">
        {isLoading ? (
          <Skeleton className="h-[240px] w-full" />
        ) : error ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : total === 0 ? (
          <EmptyState
            icon={BarChart3}
            title="No sensor blobs yet"
            description="Create a scene to populate the lake and see the modality breakdown."
          />
        ) : (
          <ChartContainer config={chartConfig} className="h-[240px] w-full">
            <BarChart data={data} margin={{ top: 8, right: 4, left: -16, bottom: 0 }}>
              <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="modality" tickLine={false} axisLine={false} tickMargin={10} fontSize={11} />
              <YAxis allowDecimals={false} tickLine={false} axisLine={false} tickMargin={6} fontSize={11} width={28} />
              <ChartTooltip cursor={{ fill: "var(--accent-subtle)" }} content={<ChartTooltipContent />} />
              <Bar dataKey="blobs" fill="var(--color-blobs)" radius={[4, 4, 0, 0]} animationDuration={500} />
            </BarChart>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  );
}
