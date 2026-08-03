import { ReactElement } from "react";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi } from "vitest";

import version from "./fixtures/version.json";
import ready from "./fixtures/ready.json";
import scenarios from "./fixtures/scenarios.json";
import procDetail from "./fixtures/procurement.detail.json";
import procWorkflow from "./fixtures/procurement.workflow.json";
import procRegistry from "./fixtures/procurement.registry.json";
import procEligibility from "./fixtures/procurement.eligibility.json";
import procExplain from "./fixtures/procurement.explain.json";
import cyberDetail from "./fixtures/cybersecurity_no_feasible_team.detail.json";
import cyberWorkflow from "./fixtures/cybersecurity_no_feasible_team.workflow.json";
import cyberRegistry from "./fixtures/cybersecurity_no_feasible_team.registry.json";
import cyberEligibility from "./fixtures/cybersecurity_no_feasible_team.eligibility.json";
import cyberExplain from "./fixtures/cybersecurity_no_feasible_team.explain.json";

const RESULT: Record<string, unknown> = {
  "/api/v1/scenarios": scenarios,
  "/api/v1/scenarios/procurement": procDetail,
  "/api/v1/scenarios/procurement/workflow": procWorkflow,
  "/api/v1/scenarios/procurement/registry": procRegistry,
  "/api/v1/scenarios/cybersecurity_no_feasible_team": cyberDetail,
  "/api/v1/scenarios/cybersecurity_no_feasible_team/workflow": cyberWorkflow,
  "/api/v1/scenarios/cybersecurity_no_feasible_team/registry": cyberRegistry,
};

function envelope(result: unknown) {
  return {
    api_version: "governance_studio.api.v1",
    request_id: "req_test",
    operation: "test",
    scenario_id: null,
    source_contract_version: "workflow_ir.v1",
    awc_version: "0.2.1",
    input_digests: {},
    result,
    diagnostics: [],
    warnings: [],
    maturity: {},
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export interface FetchMockOptions {
  unsupportedContract?: boolean;
  notReady?: boolean;
  unreachable?: boolean;
}

export function installFetchMock(opts: FetchMockOptions = {}) {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    if (opts.unreachable) throw new TypeError("failed to fetch");
    const url = typeof input === "string" ? input : input.toString();
    const path = url.replace(/^https?:\/\/[^/]+/, "").split("?")[0];

    if (path === "/health") return jsonResponse({ status: "healthy" });
    if (path === "/ready") return jsonResponse(opts.notReady ? { ...ready, ready: false, status: "not_ready" } : ready, opts.notReady ? 503 : 200);
    if (path === "/version") {
      return jsonResponse(opts.unsupportedContract ? { ...version, api_contract_version: "governance_studio.api.v9" } : version);
    }
    if (path === "/api/v1/scenarios/procurement/eligibility") return jsonResponse(envelope(procEligibility));
    if (path === "/api/v1/scenarios/cybersecurity_no_feasible_team/eligibility") return jsonResponse(envelope(cyberEligibility));
    if (path === "/api/v1/explanations/eligibility") {
      let scenarioId = "procurement";
      try {
        scenarioId = JSON.parse(String(init?.body ?? "{}")).scenario_id ?? "procurement";
      } catch {
        /* default */
      }
      return jsonResponse(envelope(scenarioId === "cybersecurity_no_feasible_team" ? cyberExplain : procExplain));
    }
    if (path in RESULT) return jsonResponse(envelope(RESULT[path]));
    return jsonResponse({ error: { code: "not_found", message: `no mock for ${path}`, request_id: "req_test" } }, 404);
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

export function renderWithProviders(ui: ReactElement, route = "/") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

export const fixtures = {
  version,
  ready,
  scenarios,
  procWorkflow,
  procRegistry,
  procEligibility,
  procExplain,
  cyberEligibility,
};
