/**
 * Centralized typed HTTP client for the DilChat backend.
 *
 * Responsibilities:
 * - attach `Authorization: Bearer <access>` for authenticated calls;
 * - enforce a request timeout with AbortController (cancellation-capable);
 * - normalize every failure into ApiError (network vs timeout vs http);
 * - perform EXACTLY ONE refresh+retry on a 401, via an injected refresh hook;
 * - single-flight that refresh so concurrent 401s share ONE backend refresh
 *   (the backend rotates refresh tokens and revokes the whole session chain on
 *   reuse, so parallel refreshes with the same token would force a spurious
 *   sign-out);
 * - never log tokens, credentials, or request bodies.
 *
 * The client holds no React state; auth tokens are supplied by callbacks so the
 * secure store remains the single source of truth.
 */
import { REQUEST_TIMEOUT_MS, getApiBaseUrl } from "@/config/env";
import { ApiError, httpErrorFromBody } from "@/api/errors";

export interface TokenProvider {
  getAccessToken: () => Promise<string | null>;
  /** Attempt a single refresh; returns the new access token or null on failure. */
  refresh: () => Promise<string | null>;
  /** Called when auth cannot be recovered (refresh failed) so the app can sign out. */
  onAuthLost: () => void | Promise<void>;
}

type Method = "GET" | "POST" | "PATCH" | "DELETE";

interface RequestOptions {
  method: Method;
  path: string;
  body?: unknown;
  auth?: boolean; // default true
  signal?: AbortSignal;
}

async function parseJsonSafe(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

export class HttpClient {
  private readonly baseUrl: string;
  /**
   * A shared in-flight refresh promise. When several authenticated requests get
   * a 401 at the same time, they all await this ONE promise instead of each
   * calling the (rotating, reuse-detecting) refresh endpoint — which would
   * revoke the session chain and sign the user out.
   */
  private refreshInFlight: Promise<string | null> | null = null;

  constructor(private readonly tokens: TokenProvider, baseUrl?: string) {
    this.baseUrl = baseUrl ?? getApiBaseUrl();
  }

  /** Deduplicate concurrent refreshes: only one backend refresh runs at a time. */
  private dedupedRefresh(): Promise<string | null> {
    if (!this.refreshInFlight) {
      this.refreshInFlight = Promise.resolve()
        .then(() => this.tokens.refresh())
        .finally(() => {
          this.refreshInFlight = null;
        });
    }
    return this.refreshInFlight;
  }

  private async raw<T>(opts: RequestOptions, accessToken: string | null): Promise<{ status: number; data: T }> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    // Chain any caller-provided cancellation signal.
    if (opts.signal) {
      if (opts.signal.aborted) controller.abort();
      else opts.signal.addEventListener("abort", () => controller.abort(), { once: true });
    }
    const headers: Record<string, string> = { Accept: "application/json" };
    if (opts.body !== undefined) headers["Content-Type"] = "application/json";
    if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;

    let res: Response;
    try {
      res = await fetch(`${this.baseUrl}${opts.path}`, {
        method: opts.method,
        headers,
        body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
        signal: controller.signal,
      });
    } catch (e) {
      clearTimeout(timeout);
      if (controller.signal.aborted) {
        throw new ApiError({ kind: "timeout", message: "Request timed out." });
      }
      throw new ApiError({ kind: "network", message: "Network request failed." });
    }
    clearTimeout(timeout);

    if (res.status === 204) return { status: 204, data: undefined as T };
    const data = await parseJsonSafe(res);
    if (!res.ok) throw httpErrorFromBody(res.status, data);
    return { status: res.status, data: data as T };
  }

  async request<T>(opts: RequestOptions): Promise<T> {
    const useAuth = opts.auth !== false;
    const access = useAuth ? await this.tokens.getAccessToken() : null;
    try {
      const { data } = await this.raw<T>(opts, access);
      return data;
    } catch (e) {
      // Exactly one refresh + retry on an auth failure for authenticated calls.
      // Concurrent 401s collapse onto a single shared refresh (see dedupedRefresh).
      if (useAuth && e instanceof ApiError && e.isAuthError) {
        const refreshed = await this.dedupedRefresh();
        if (!refreshed) {
          await this.tokens.onAuthLost();
          throw e;
        }
        const { data } = await this.raw<T>(opts, refreshed);
        return data;
      }
      throw e;
    }
  }

  get<T>(path: string, signal?: AbortSignal): Promise<T> {
    return this.request<T>({ method: "GET", path, signal });
  }
  post<T>(path: string, body?: unknown, auth = true): Promise<T> {
    return this.request<T>({ method: "POST", path, body, auth });
  }
  patch<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>({ method: "PATCH", path, body });
  }
}
