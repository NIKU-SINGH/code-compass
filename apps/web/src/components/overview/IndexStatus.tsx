import { Badge } from "@/components/ui/badge";

interface Props {
  /** e.g. "Indexed 5 min ago". */
  indexed: string;
  commit?: string;
  staleCount: number;
  repoRoot: string;
}

/** Where the index came from and whether it has fallen behind the working tree. */
export function IndexStatus({ indexed, commit, staleCount, repoRoot }: Props) {
  return (
    <div className="flex flex-col items-end gap-1 text-xs text-muted-foreground">
      <div className="flex flex-wrap items-center justify-end gap-2">
        <span>{indexed}</span>
        {commit && <span className="font-mono">{commit}</span>}
        {staleCount > 0 && <Badge variant="outline">{staleCount.toLocaleString()} changed since</Badge>}
      </div>
      <span className="max-w-[28rem] truncate font-mono" title={repoRoot}>
        {repoRoot}
      </span>
    </div>
  );
}
