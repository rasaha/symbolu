/**
 * Normalized API/network errors. The client turns every failure into one of
 * these so the UI can distinguish a network problem from a server rejection and
 * react to auth expiry — without ever surfacing tokens or raw credentials.
 */

export type ApiErrorKind = "network" | "timeout" | "http" | "parse";

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | null;
  /** Machine-readable backend code (problem+json `code`), when present. */
  readonly code: string | null;

  constructor(params: {
    kind: ApiErrorKind;
    status?: number | null;
    code?: string | null;
    message: string;
  }) {
    super(params.message);
    this.name = "ApiError";
    this.kind = params.kind;
    this.status = params.status ?? null;
    this.code = params.code ?? null;
  }

  /** True when the failure means the session is no longer valid. */
  get isAuthError(): boolean {
    return this.status === 401 || this.code === "AUTH_SESSION_REVOKED";
  }

  /** True for a client-side validation rejection (safe to show field errors). */
  get isValidationError(): boolean {
    return this.status === 422 || this.code === "VALIDATION_ERROR";
  }
}

interface ProblemBody {
  code?: unknown;
  detail?: unknown;
  title?: unknown;
  message?: unknown;
}

/** Build an ApiError from an HTTP response body (problem+json or FastAPI 422). */
export function httpErrorFromBody(status: number, body: unknown): ApiError {
  let code: string | null = null;
  let detail: string | null = null;
  if (body && typeof body === "object") {
    const b = body as ProblemBody;
    if (typeof b.code === "string") code = b.code;
    if (typeof b.detail === "string") detail = b.detail;
    else if (typeof b.title === "string") detail = b.title;
    else if (typeof b.message === "string") detail = b.message;
  }
  return new ApiError({
    kind: "http",
    status,
    code,
    message: detail ?? `Request failed (${status}).`,
  });
}

/** A user-facing message that never leaks internals. */
export function userMessageFor(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.kind === "network") return "You appear to be offline. Check your connection and try again.";
    if (err.kind === "timeout") return "The request timed out. Please try again.";
    if (err.isAuthError) return "Your session has expired. Please sign in again.";
    return err.message;
  }
  return "Something went wrong. Please try again.";
}
