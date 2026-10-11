import type {
  AiAuthorshipSignal,
  DeadCodeSignal,
  OwnershipSignal,
  RefactorSignal,
} from "./types";

// Placeholder numbers for a fictional repository. The index does not record dead-code analysis
// or git history yet, so these stand in until it does; the Overview labels them "Sample data".

export const SAMPLE_DEAD_CODE: DeadCodeSignal = {
  totalSymbols: 149,
  byKind: [
    { kind: "function", unused: 9 },
    { kind: "method", unused: 6 },
    { kind: "class", unused: 2 },
  ],
  topFiles: [
    { path: "app/legacy/exporters.py", unused: 5, total: 8 },
    { path: "app/billing/refunds.py", unused: 4, total: 11 },
    { path: "app/jobs/cleanup.py", unused: 3, total: 5 },
    { path: "app/utils/dates.py", unused: 3, total: 7 },
    { path: "app/auth/tokens.py", unused: 2, total: 9 },
  ],
};

export const SAMPLE_REFACTORING: RefactorSignal = {
  files: [
    { path: "app/billing/invoice.py", commits: 38, refactorCommits: 9, linesChanged: 1840 },
    { path: "app/auth/permissions.py", commits: 27, refactorCommits: 6, linesChanged: 1210 },
    { path: "app/api/routes.py", commits: 24, refactorCommits: 4, linesChanged: 960 },
    { path: "app/models/user.py", commits: 19, refactorCommits: 5, linesChanged: 720 },
    { path: "app/jobs/scheduler.py", commits: 14, refactorCommits: 3, linesChanged: 510 },
  ],
  areas: [
    { path: "app/billing", commits: 71, refactorCommits: 16, linesChanged: 3420 },
    { path: "app/auth", commits: 49, refactorCommits: 11, linesChanged: 2380 },
    { path: "app/api", commits: 41, refactorCommits: 7, linesChanged: 1790 },
    { path: "app/models", commits: 30, refactorCommits: 8, linesChanged: 1260 },
    { path: "app/jobs", commits: 22, refactorCommits: 4, linesChanged: 840 },
  ],
  activity: {
    labels: ["May", "Jun", "Jul", "Aug", "Sep", "Oct"],
    areas: [
      { path: "app/billing", commits: [8, 15, 17, 13, 12, 6] },
      { path: "app/auth", commits: [6, 9, 12, 10, 8, 4] },
      { path: "app/api", commits: [4, 7, 9, 9, 8, 4] },
      { path: "app/models", commits: [3, 5, 7, 6, 5, 4] },
    ],
  },
};

export const SAMPLE_AI_AUTHORSHIP: AiAuthorshipSignal = {
  totalLines: 24600,
  history: {
    labels: ["May", "Jun", "Jul", "Aug", "Sep", "Oct"],
    percent: [8.4, 13.9, 20.6, 25.8, 29.7, 32.1],
  },
  agents: [
    { name: "Claude Opus 5.5", lines: 3420 },
    { name: "Claude Sonnet 5.5", lines: 2980 },
    { name: "Claude Sonnet 4.6", lines: 1150 },
    { name: "Pi Coding Agent", lines: 340 },
  ],
  areas: [
    { path: "app/billing", aiLines: 1980, totalLines: 3100 },
    { path: "app/api", aiLines: 1560, totalLines: 3300 },
    { path: "app/jobs", aiLines: 820, totalLines: 2100 },
    { path: "app/models", aiLines: 900, totalLines: 2900 },
    { path: "app/auth", aiLines: 630, totalLines: 4200 },
  ],
};

export const SAMPLE_OWNERSHIP: OwnershipSignal = {
  areas: [
    {
      path: "app/billing",
      owners: [
        { name: "Priya Nair", kind: "person", percent: 38 },
        { name: "Claude Opus 5.5", kind: "agent", percent: 41 },
        { name: "Marcus Lee", kind: "person", percent: 21 },
      ],
    },
    {
      path: "app/auth",
      owners: [
        { name: "Marcus Lee", kind: "person", percent: 72 },
        { name: "Claude Sonnet 5.5", kind: "agent", percent: 18 },
        { name: "Priya Nair", kind: "person", percent: 10 },
      ],
    },
    {
      path: "app/api",
      owners: [
        { name: "Dana Okafor", kind: "person", percent: 46 },
        { name: "Claude Sonnet 5.5", kind: "agent", percent: 33 },
        { name: "Pi Coding Agent", kind: "agent", percent: 9 },
        { name: "Marcus Lee", kind: "person", percent: 12 },
      ],
    },
    {
      path: "app/models",
      owners: [
        { name: "Priya Nair", kind: "person", percent: 64 },
        { name: "Claude Sonnet 4.6", kind: "agent", percent: 31 },
        { name: "Dana Okafor", kind: "person", percent: 5 },
      ],
    },
    {
      path: "app/jobs",
      owners: [
        { name: "Dana Okafor", kind: "person", percent: 57 },
        { name: "Claude Opus 5.5", kind: "agent", percent: 39 },
        { name: "Marcus Lee", kind: "person", percent: 4 },
      ],
    },
  ],
};
