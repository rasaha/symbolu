// Test helpers for the studio screens (the six of GAS-4 and the two review screens of GAS-7).
//
// A separate fetch mock from the v1 one, serving the v2 envelope shape. Kept apart so
// the v1 helpers stay exactly as they were and the studio's fixtures cannot perturb
// the explorer's tests.
import type { ReactElement } from "react";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi } from "vitest";

// The studio is mounted inside the app's CompatibilityGate, which is correct: a studio
// talking to an incompatible API should be gated exactly like the explorer. So the v2
// mock serves the operational endpoints the gate reads, reusing the v1 fixtures rather
// than inventing a second version payload that could disagree with them.
import ready from "./fixtures/ready.json";
import version from "./fixtures/version.json";

export function v2Envelope(result: unknown) {
  return {
    api_version: "governance_studio.api.v2",
    request_id: "req_test",
    operation: "test",
    awc_version: "0.2.1",
    input_digests: {},
    result,
    diagnostics: [],
    warnings: [],
    maturity: {
      synthetic_demonstration_data: true,
      planning_only: true,
      no_agent_execution: true,
      no_permission_grant: true,
      no_business_action_authorization: true,
    },
  };
}

export function unavailable(capability: string, reason: string) {
  return { available: false, capability, reason, result: null };
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export interface V2MockOptions {
  /** Map of path → result, wrapped in the envelope automatically. */
  results?: Record<string, unknown>;
  unreachable?: boolean;
}

/** The default posture: every capability reports itself unavailable, as a bare
 *  deployment really does. Screens must render that, which is the point. */
const DEFAULT_RESULTS: Record<string, unknown> = {
  "/api/v2/authority/policies": unavailable(
    "authority_registry",
    "no PolicyRegistry is configured: the only reachable implementation is in-memory",
  ),
  "/api/v2/observe/audit": unavailable(
    "console_api",
    "no ugence_console_api base URL is configured",
  ),
  "/api/v2/review/queue": unavailable(
    "review_service",
    "no governed review service base URL is configured",
  ),
};

export function installV2FetchMock(opts: V2MockOptions = {}) {
  const results = { ...DEFAULT_RESULTS, ...(opts.results ?? {}) };
  const fn = vi.fn(async (input: RequestInfo | URL) => {
    if (opts.unreachable) throw new TypeError("failed to fetch");
    const url = typeof input === "string" ? input : input.toString();
    const path = url.replace(/^https?:\/\/[^/]+/, "").split("?")[0];

    if (path === "/health") return jsonResponse({ status: "healthy" });
    if (path === "/ready") return jsonResponse(ready);
    if (path === "/version") return jsonResponse(version);

    if (path in results) return jsonResponse(v2Envelope(results[path]));
    // An unmocked v2 path is a test bug, not a 404 to render around.
    return jsonResponse(v2Envelope(unavailable("unmocked", `no fixture for ${path}`)));
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

export function renderStudio(ui: ReactElement, route = "/studio") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}
