import type { ImpactGroup } from "@/lib/api";
import { AffectedRow } from "./AffectedRow";

interface AffectedGroupListProps {
  groups: ReadonlyArray<ImpactGroup>;
  onRetarget: (id: string) => void;
}

interface DistanceSection {
  distance: number;
  count: number;
  files: ImpactGroup[];
}

/** The API returns one group per (distance, file); fold them into one section per distance. */
function sectionsByDistance(groups: ReadonlyArray<ImpactGroup>): DistanceSection[] {
  const byDistance = new Map<number, DistanceSection>();
  for (const g of groups) {
    const section = byDistance.get(g.distance) ?? { distance: g.distance, count: 0, files: [] };
    section.count += g.items.length;
    section.files.push(g);
    byDistance.set(g.distance, section);
  }
  return [...byDistance.values()].sort((a, b) => a.distance - b.distance);
}

function distanceLabel(distance: number): string {
  return distance === 1 ? "Direct dependents" : `${distance} hops away`;
}

export function AffectedGroupList({ groups, onRetarget }: AffectedGroupListProps) {
  return (
    <div className="flex flex-col gap-5">
      {sectionsByDistance(groups).map((section) => (
        <section key={section.distance} aria-label={distanceLabel(section.distance)} className="flex flex-col gap-2">
          <div className="flex items-center gap-2.5">
            <h3 className="text-sm font-semibold">{distanceLabel(section.distance)}</h3>
            <span className="flex-1" />
            <span className="font-mono text-xs text-muted-foreground">{section.count}</span>
          </div>
          <div className="flex flex-col gap-3">
            {section.files.map((g) => (
              <div key={g.file_path} className="overflow-hidden rounded-lg border border-border">
                <div className="border-b border-border bg-muted px-3.5 py-1.5 font-mono text-xs text-muted-foreground">
                  {g.file_path}
                </div>
                <div className="flex flex-col gap-px bg-border">
                  {g.items.map((item) => (
                    <AffectedRow key={item.symbol.id} item={item} onRetarget={onRetarget} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
