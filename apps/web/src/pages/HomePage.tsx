import { PromptCard } from "@/components/home/PromptCard";
import { TasksPanel } from "@/components/home/TasksPanel";

export function HomePage() {
  return (
    <div className="flex items-center justify-center min-h-screen px-8 py-12">
      <div className="w-full max-w-2xl flex flex-col gap-8">
        <PromptCard />
        <TasksPanel />
      </div>
    </div>
  );
}
