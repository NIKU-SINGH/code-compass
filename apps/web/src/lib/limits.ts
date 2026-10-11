/**
 * Maximum traversal depth accepted by the impact query. Mirrors `MAX_DEPTH` in
 * `packages/core/src/compass_core/query/params.py`; keep the two in sync.
 */
export const MAX_DEPTH = 10;

/** Default traversal depth for impact analysis. */
export const DEFAULT_IMPACT_DEPTH = 3;

/**
 * How many of the most-called functions the overview ranks for "Riskiest to change".
 * Mirrors `RISK_CANDIDATES` in `packages/core/src/compass_core/query/overview.py`;
 * keep the two in sync.
 */
export const RISK_CANDIDATES = 30;
