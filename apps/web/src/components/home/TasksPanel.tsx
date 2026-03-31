import { TaskRow, type Task } from "./TaskRow";

const RECENT_TASKS: Task[] = [
  {
    id: "1",
    title: "Repository Purpose Overview",
    date: "Mar 22",
    tags: ["Dashboard", "agent-server"],
    status: "done",
  },
  {
    id: "2",
    title: "Explain the purpose and overview of this repository",
    date: "Mar 14",
    tags: ["Dashboard", "agent-server"],
    status: "done",
  },
  {
    id: "3",
    title: "Set up CI/CD pipeline with GitHub Actions",
    date: "Mar 12",
    tags: ["DevOps"],
    status: "done",
  },
  {
    id: "4",
    title: "Design the core data models for the API",
    date: "Mar 10",
    tags: ["Backend", "API"],
    status: "done",
  },
];

export function TasksPanel() {
  return (
    <div>
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-foreground">Tasks</h2>
        <p className="text-sm text-muted-foreground mt-0.5">
          Dive into your most recent tasks
        </p>
      </div>

      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="divide-y divide-border">
          {RECENT_TASKS.map((task) => (
            <TaskRow key={task.id} task={task} />
          ))}
        </div>
      </div>
    </div>
  );
}
