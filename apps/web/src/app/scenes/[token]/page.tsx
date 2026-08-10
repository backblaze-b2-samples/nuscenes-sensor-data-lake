import { SceneDetail } from "@/components/scenes/scene-detail";

export default async function SceneDetailPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return (
    <div className="animate-fade-in space-y-8">
      <SceneDetail token={token} />
    </div>
  );
}
