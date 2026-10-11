import type { components } from "./api-types";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Typed query client. All shapes derive from the generated `api-types.ts`
// (run `make gen-api` after backend model changes).
// ---------------------------------------------------------------------------

type Schemas = components["schemas"];

export type ImpactResult = Schemas["ImpactResult"];
export type SearchResult = Schemas["SearchResult"];
export type NodeDetail = Schemas["NodeDetail"];
export type OverviewResult = Schemas["OverviewResult"];
export type AmbiguousReference = Schemas["AmbiguousReference"];
export type SymbolNotFound = Schemas["SymbolNotFound"];
export type ErrorResponse = Schemas["ErrorResponse"];
export type ErrorCode = Schemas["ErrorCode"];
export type SymbolKind = Schemas["SymbolKind"];
export type SymbolRef = Schemas["SymbolRef"];
export type ResultItem = Schemas["ResultItem"];
export type ImpactGroup = Schemas["ImpactGroup"];
export type Via = Schemas["Via"];
export type ViaKind = Schemas["ViaKind"];
export type Caveat = Schemas["Caveat"];
export type CaveatCode = Schemas["CaveatCode"];
export type EdgeRef = Schemas["EdgeRef"];
export type EdgeType = Schemas["EdgeType"];
export type MatchRule = Schemas["MatchRule"];
export type RankedSymbol = Schemas["RankedSymbol"];
export type LibraryUsage = Schemas["LibraryUsage"];
export type IndexCounts = Schemas["IndexCounts"];
export type IndexStatus = Schemas["IndexStatus"];
export type SearchHit = Schemas["SearchHit"];
export type ErrorDetail = Schemas["ErrorDetail"];

/** Backend error codes plus `NETWORK` for "backend unreachable". */
export type ClientErrorCode = ErrorCode | "NETWORK";

export type ImpactOutcome =
  | { status: "ok"; data: ImpactResult }
  | { status: "ambiguous"; data: AmbiguousReference }
  | { status: "not_found"; data: SymbolNotFound };

export class ApiError extends Error {
  readonly code: ClientErrorCode;
  readonly status: number;
  readonly details: ReadonlyArray<ErrorDetail>;

  constructor(
    code: ClientErrorCode,
    message: string,
    status: number,
    details: ReadonlyArray<ErrorDetail> = [],
  ) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

export function isAbortError(e: unknown): e is DOMException {
  return e instanceof DOMException && e.name === "AbortError";
}

/** True when a failure is the caller's abort (native error or custom abort reason). */
function isAbort(e: unknown, signal?: AbortSignal): boolean {
  return signal?.aborted === true || isAbortError(e);
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

/**
 * Deliberately permissive: unknown (future) codes pass through, so consumers
 * switching on `ApiError.code` must keep a default branch rather than rely on
 * `never`-exhaustiveness.
 */
function isErrorResponse(v: unknown): v is ErrorResponse {
  return (
    isRecord(v) &&
    typeof v.code === "string" &&
    typeof v.message === "string" &&
    Array.isArray(v.details)
  );
}

/** Parses a JSON body; returns undefined for unparsable bodies, rethrows aborts. */
async function readJson(res: Response, signal?: AbortSignal): Promise<unknown> {
  let text: string;
  try {
    text = await res.text();
  } catch (e) {
    if (isAbort(e, signal)) throw e;
    throw new ApiError("NETWORK", "Connection lost while reading the response", 0);
  }
  try {
    return JSON.parse(text);
  } catch {
    return text.length > 0 ? { __raw: text.slice(0, 200) } : undefined;
  }
}

function rawSnippet(body: unknown): string {
  return isRecord(body) && typeof body.__raw === "string" ? `: ${body.__raw}` : "";
}

function toApiError(res: Response, body: unknown): ApiError {
  if (isErrorResponse(body)) {
    return new ApiError(body.code, body.message, res.status, body.details);
  }
  const text = res.statusText ? ` ${res.statusText}` : "";
  return new ApiError(
    "INTERNAL",
    `Unexpected response (HTTP ${res.status}${text})${rawSnippet(body)}`.slice(0, 300),
    res.status,
  );
}

function unexpected(path: string, res: Response, body: unknown): ApiError {
  return new ApiError(
    "INTERNAL",
    `Unexpected response from ${path} (is NEXT_PUBLIC_API_URL correct?)${rawSnippet(body)}`.slice(0, 300),
    res.status,
  );
}

function isOk(body: unknown, operation: string): boolean {
  return isRecord(body) && body.outcome === "ok" && body.operation === operation;
}

/** Performs a GET; aborts propagate natively, other failures become NETWORK. */
async function request(path: string, params: URLSearchParams, signal?: AbortSignal): Promise<Response> {
  const qs = params.toString();
  try {
    return await fetch(`${API_BASE}${path}${qs ? `?${qs}` : ""}`, { signal });
  } catch (e) {
    if (isAbort(e, signal)) throw e;
    throw new ApiError("NETWORK", "Could not reach the Compass backend", 0);
  }
}

async function getOk<T>(
  path: string,
  params: URLSearchParams,
  operation: string,
  signal?: AbortSignal,
): Promise<T> {
  const res = await request(path, params, signal);
  const body = await readJson(res, signal);
  if (!res.ok) throw toApiError(res, body);
  if (!isOk(body, operation)) throw unexpected(path, res, body);
  return body as T;
}

export function searchSymbols(
  q: string,
  opts: { kind?: SymbolKind; limit?: number; signal?: AbortSignal } = {},
): Promise<SearchResult> {
  const params = new URLSearchParams({ q });
  if (opts.kind !== undefined) params.set("kind", opts.kind);
  if (opts.limit !== undefined) params.set("limit", String(opts.limit));
  return getOk<SearchResult>("/api/search", params, "FIND", opts.signal);
}

export async function getImpact(
  ref: string,
  opts: { depth?: number; minConfidence?: number; limit?: number; signal?: AbortSignal } = {},
): Promise<ImpactOutcome> {
  const params = new URLSearchParams({ ref });
  if (opts.depth !== undefined) params.set("depth", String(opts.depth));
  if (opts.minConfidence !== undefined) params.set("min_confidence", String(opts.minConfidence));
  if (opts.limit !== undefined) params.set("limit", String(opts.limit));
  const path = "/api/impact";
  const res = await request(path, params, opts.signal);
  const body = await readJson(res, opts.signal);
  if (res.ok) {
    if (!isOk(body, "IMPACT")) throw unexpected(path, res, body);
    return { status: "ok", data: body as ImpactResult };
  }
  // 404 is also used for errors on unknown routes, so check the discriminator.
  if (res.status === 409 && isRecord(body) && body.outcome === "ambiguous") {
    return { status: "ambiguous", data: body as AmbiguousReference };
  }
  if (res.status === 404 && isRecord(body) && body.outcome === "not_found") {
    return { status: "not_found", data: body as SymbolNotFound };
  }
  throw toApiError(res, body);
}

export function getOverview(opts: { signal?: AbortSignal } = {}): Promise<OverviewResult> {
  return getOk<OverviewResult>("/api/overview", new URLSearchParams(), "OVERVIEW", opts.signal);
}

/**
 * Everything known about one node. Resolves to `null` when the node is unknown or the
 * reference is ambiguous (404 / 409), so callers can show "no details" without an error.
 */
export async function getNodeDetail(
  ref: string,
  opts: { signal?: AbortSignal } = {},
): Promise<NodeDetail | null> {
  const path = "/api/describe";
  const res = await request(path, new URLSearchParams({ ref }), opts.signal);
  const body = await readJson(res, opts.signal);
  if (res.ok) {
    if (!isOk(body, "DESCRIBE")) throw unexpected(path, res, body);
    return body as NodeDetail;
  }
  if (
    (res.status === 404 || res.status === 409) &&
    isRecord(body) &&
    (body.outcome === "not_found" || body.outcome === "ambiguous")
  ) {
    return null;
  }
  throw toApiError(res, body);
}
