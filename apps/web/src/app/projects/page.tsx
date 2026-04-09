export default function ProjectsPage() {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[60vh] gap-3 text-center px-4">
      <h1 className="text-xl font-semibold">Projects</h1>
      <p className="text-sm text-muted-foreground max-w-xs">
        Project management is coming soon. Use <code className="text-xs bg-muted px-1.5 py-0.5 rounded">compass index ./repo</code> to index a repository.
      </p>
    </div>
  );
}
