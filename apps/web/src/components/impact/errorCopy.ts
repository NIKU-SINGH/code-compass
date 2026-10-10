import type { ApiError } from "@/lib/api";

export interface ErrorCopy {
  title: string;
  message: string;
  retryable: boolean;
}

/** Maps a client error to user-facing copy; exhaustive over the known codes. */
export function errorCopy(error: ApiError): ErrorCopy {
  const code = error.code;
  switch (code) {
    case "NETWORK":
      return {
        title: "Backend unreachable",
        message: "Can't reach the Code Compass backend. Is `compass serve` running?",
        retryable: true,
      };
    case "INDEX_NOT_FOUND":
      return {
        title: "No index",
        message: "No index found. Run `compass ingest` in your repository.",
        retryable: false,
      };
    case "INDEX_BUSY":
      return {
        title: "Index busy",
        message: "The index is being rebuilt. Try again in a moment.",
        retryable: true,
      };
    case "INDEX_INCOMPATIBLE":
      return {
        title: "Incompatible index",
        message: "The index was created by an incompatible version. Re-run `compass ingest`.",
        retryable: false,
      };
    case "QUERY_TIMEOUT":
      return {
        title: "Query timed out",
        message: "The analysis took too long. Try a smaller depth or retry.",
        retryable: true,
      };
    case "INVALID_ARGUMENT":
      return { title: "Invalid request", message: error.message, retryable: false };
    case "NOT_FOUND":
      return { title: "Not found", message: error.message, retryable: false };
    case "AMBIGUOUS":
      return { title: "Ambiguous reference", message: error.message, retryable: false };
    case "INTERNAL":
      return {
        title: "Something went wrong",
        message: "The backend hit an unexpected error. Try again.",
        retryable: true,
      };
    default: {
      const unreachable: never = code;
      void unreachable;
      return { title: "Something went wrong", message: error.message, retryable: true };
    }
  }
}
