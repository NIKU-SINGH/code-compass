import { ChatPanel } from "@/components/project/ChatPanel";
import { RightPanel } from "@/components/project/RightPanel";

interface Props {
  params: Promise<{ projectId: string }>;
}

export default async function ProjectPage({ params }: Props) {
  const { projectId } = await params;

  return (
    <div className="flex-1 flex overflow-hidden">
      <ChatPanel projectId={projectId} />
      <RightPanel key={projectId} projectId={projectId} />
    </div>
  );
}
