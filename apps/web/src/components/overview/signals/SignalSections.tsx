import type { ReactNode } from "react";
import { Donut } from "../charts/Donut";
import { Heatmap } from "../charts/Heatmap";
import { HorizontalBars } from "../charts/HorizontalBars";
import { Trend } from "../charts/Trend";
import { InsightGroup } from "../InsightGroup";
import {
  agentSegments,
  aiShare,
  aiTrend,
  deadCodeFileBars,
  deadCodeSegments,
  ownershipMatrix,
  percentOf,
  refactorFileBars,
  refactorTrend,
  unusedTotal,
} from "./cards";
import {
  SAMPLE_AI_AUTHORSHIP,
  SAMPLE_DEAD_CODE,
  SAMPLE_OWNERSHIP,
  SAMPLE_REFACTORING,
} from "./sampleData";

const NOTE = "Sample data";
const NOTE_TITLE = "Placeholder numbers: the index does not record this yet";

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <InsightGroup title={title} note={NOTE} noteTitle={NOTE_TITLE}>
      {children}
    </InsightGroup>
  );
}

/** Dead code, refactoring, AI authorship and ownership; all fed by sample data for now. */
export function SignalSections() {
  const dead = SAMPLE_DEAD_CODE;
  const unused = unusedTotal(dead);
  const ai = SAMPLE_AI_AUTHORSHIP;
  const matrix = ownershipMatrix(SAMPLE_OWNERSHIP);
  return (
    <>
      <Group title="Dead code">
        <Donut
          title="Likely unused symbols"
          description="Dynamic calls cannot be seen, so these are likely, not certain"
          segments={deadCodeSegments(dead)}
          centre={{ value: `${percentOf(unused, dead.totalSymbols)}%`, caption: "unused" }}
        />
        <HorizontalBars
          title="Files with the most dead code"
          description="Unused symbols per file"
          rows={deadCodeFileBars(dead)}
          valueLabel="Unused symbols"
        />
      </Group>
      <Group title="Refactoring">
        <Trend
          title="Refactoring activity"
          description="Commits per month in the busiest areas"
          labels={SAMPLE_REFACTORING.activity.labels}
          series={refactorTrend(SAMPLE_REFACTORING)}
        />
        <HorizontalBars
          title="Most reworked files"
          description="Commits touching each file"
          rows={refactorFileBars(SAMPLE_REFACTORING.files)}
          valueLabel="Commits"
        />
      </Group>
      <Group title="AI authorship">
        <Donut
          title="Lines by author"
          description="Surviving lines, credited from commit trailers"
          aside={`${ai.totalLines.toLocaleString()} lines`}
          segments={agentSegments(ai)}
          centre={{ value: `${aiShare(ai)}%`, caption: "AI-written" }}
        />
        <Trend
          title="AI share over time"
          description="Share of lines written by AI agents"
          labels={ai.history.labels}
          series={aiTrend(ai)}
          unit="%"
          area
        />
      </Group>
      <Group title="Code ownership">
        <Heatmap
          title="Who owns what"
          description="Share of each area's surviving lines, by author; people first, then AI agents"
          columns={matrix.columns}
          rows={matrix.rows}
        />
      </Group>
    </>
  );
}
