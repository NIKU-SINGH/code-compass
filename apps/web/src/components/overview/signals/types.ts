/**
 * Shapes of the code-health signals shown on the Overview.
 *
 * Index health comes from the overview API. The other four are not produced by the backend
 * yet; `sampleData.ts` is their only source. They are
 * counts rather than percentages so a real source cannot send inconsistent numbers: every
 * percentage on screen is derived from them.
 */

export interface DeadCodeKindCount {
  kind: "function" | "method" | "class";
  unused: number;
}

export interface DeadCodeFile {
  path: string;
  unused: number;
  total: number;
}

export interface DeadCodeSignal {
  /** Functions, methods and classes considered. */
  totalSymbols: number;
  byKind: ReadonlyArray<DeadCodeKindCount>;
  topFiles: ReadonlyArray<DeadCodeFile>;
}

export interface RefactorEntry {
  /** File or folder path. */
  path: string;
  commits: number;
  /** Commits whose subject marks them as a refactor. */
  refactorCommits: number;
  linesChanged: number;
}

export interface AreaActivity {
  path: string;
  /** Commits per period, aligned with `RefactorActivity.labels`. */
  commits: ReadonlyArray<number>;
}

export interface RefactorActivity {
  /** Period labels, oldest first, e.g. months. */
  labels: ReadonlyArray<string>;
  areas: ReadonlyArray<AreaActivity>;
}

export interface RefactorSignal {
  files: ReadonlyArray<RefactorEntry>;
  areas: ReadonlyArray<RefactorEntry>;
  activity: RefactorActivity;
}

export interface AgentLines {
  name: string;
  /** Surviving lines attributed to this agent. */
  lines: number;
}

export interface AreaAiLines {
  path: string;
  aiLines: number;
  totalLines: number;
}

export interface AiShareHistory {
  /** Period labels, oldest first. */
  labels: ReadonlyArray<string>;
  /** Share of lines written by AI at the end of each period, 0-100. */
  percent: ReadonlyArray<number>;
}

export interface AiAuthorshipSignal {
  totalLines: number;
  history: AiShareHistory;
  agents: ReadonlyArray<AgentLines>;
  areas: ReadonlyArray<AreaAiLines>;
}

export interface Owner {
  name: string;
  kind: "person" | "agent";
  /** Share of the area's surviving lines, 0-100. */
  percent: number;
}

export interface AreaOwnership {
  path: string;
  owners: ReadonlyArray<Owner>;
}

export interface OwnershipSignal {
  areas: ReadonlyArray<AreaOwnership>;
}
