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

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

function isErrorResponse(v: unknown): v is ErrorResponse {
  return (
    isRecord(v) &&
    typeof v.code === "string" &&
    typeof v.message === "string" &&
    Array.isArray(v.details)
  );
}

async function readJson(res: Response): Promise<unknown> {
  try {
    return await res.json();
  } catch {
    return undefined;
  }
}

function toApiError(res: Response, body: unknown): ApiError {
  if (isErrorResponse(body)) {
    return new ApiError(body.code, body.message, res.status, body.details);
  }
  // Non-ErrorResponse body (proxy page, missing route): surface as INTERNAL.
  return new ApiError("INTERNAL", `Unexpected response (HTTP ${res.status})`, res.status);
}

/** Performs a GET; the native AbortError propagates, other failures become NETWORK. */
async function request(path: string, params: URLSearchParams, signal?: AbortSignal): Promise<Response> {
  const qs = params.toString();
  try {
    return await fetch(`${API_BASE}${path}${qs ? `?${qs}` : ""}`, { signal });
  } catch (e) {
    if (isAbortError(e)) throw e;
    throw new ApiError("NETWORK", "Could not reach the Compass backend", 0);
  }
}

async function getOk<T>(path: string, params: URLSearchParams, signal?: AbortSignal): Promise<T> {
  const res = await request(path, params, signal);
  const body = await readJson(res);
  if (!res.ok) throw toApiError(res, body);
  return body as T;
}

export function searchSymbols(
  q: string,
  opts: { kind?: SymbolKind; limit?: number; signal?: AbortSignal } = {},
): Promise<SearchResult> {
  const params = new URLSearchParams({ q });
  if (opts.kind !== undefined) params.set("kind", opts.kind);
  if (opts.limit !== undefined) params.set("limit", String(opts.limit));
  return getOk<SearchResult>("/api/search", params, opts.signal);
}

export async function getImpact(
  ref: string,
  opts: { depth?: number; minConfidence?: number; limit?: number; signal?: AbortSignal } = {},
): Promise<ImpactOutcome> {
  const params = new URLSearchParams({ ref });
  if (opts.depth !== undefined) params.set("depth", String(opts.depth));
  if (opts.minConfidence !== undefined) params.set("min_confidence", String(opts.minConfidence));
  if (opts.limit !== undefined) params.set("limit", String(opts.limit));
  const res = await request("/api/impact", params, opts.signal);
  const body = await readJson(res);
  if (res.ok) return { status: "ok", data: body as ImpactResult };
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
  return getOk<OverviewResult>("/api/overview", new URLSearchParams(), opts.signal);
}
