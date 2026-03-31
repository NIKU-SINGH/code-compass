import { Bot } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export interface Task {
  id: string;
  title: string;
  date: string;
  tags: string[];
  status: "active" | "done" | "pending";
}

const STATUS_DOT: Record<Task["status"], string> = {
  active: "bg-success",
  done: "bg-success",
  pending: "bg-muted-foreground/40",
};

interface TaskRowProps {
  task: Task;
}

export function TaskRow({ task }: TaskRowProps) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 hover:bg-secondary/60 transition-colors cursor-pointer group">
      <span className={`size-2 rounded-full shrink-0 ${STATUS_DOT[task.status]}`} />

      <div className="flex-1 min-w-0">
        <p className="text-sm text-foreground truncate">{task.title}</p>
        <div className="flex items-center gap-2 mt-1">
          <span className="text-xs text-muted-foreground">{task.date}</span>
          {task.tags.map((tag) => (
            <Badge key={tag} variant="secondary" className="rounded px-1.5 py-0 text-xs font-normal">
              {tag}
            </Badge>
          ))}
        </div>
      </div>

      <div className="size-6 rounded-full bg-secondary flex items-center justify-center shrink-0 opacity-50 group-hover:opacity-100 transition-opacity">
        <Bot className="size-3.5 text-muted-foreground" />
      </div>
    </div>
  );
}
