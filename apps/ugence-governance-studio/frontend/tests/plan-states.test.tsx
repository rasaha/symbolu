import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CompositionScreen } from "@/features/composition/CompositionScreen";
import { decodePlan, DecodeError } from "@/api/decoders";

import procPlan from "./fixtures/procurement.plan.json";
import cyberPlan from "./fixtures/cybersecurity_no_feasible_team.plan.json";
import partialPlan from "./fixtures/partial.plan.json";
import searchPlan from "./fixtures/search_exceeded.plan.json";
import invalidPlan from "./fixtures/invalid_input.plan.json";

afterEach(() => vi.unstubAllGlobals());

function envelope(result: unknown) {
  return {
    api_version: "governance_studio.api.v1", request_id: "req", operation: "op", scenario_id: null,
    source_contract_version: "workflow_ir.v1", awc_version: "0.2.1", input_digests: {},
    result, diagnostics: [], warnings: [], maturity: {},
  };
}
const json = (b: unknown) => new Response(JSON.stringify(b), { status: 200, headers: { "Content-Type": "application/json" } });
const EXPLAIN = { plan_state: "COMPLETE", selection_states: {}, team_constraint_results: [], permission_bound_proposals: [], role_fallback_plans: [] };

function stub(plan: unknown) {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input).replace(/^https?:\/\/[^/]+/, "").split("?")[0];
    if (path.endsWith("/plan")) return json(envelope(plan));
    if (path.endsWith("/ranking")) return json(envelope({ rankings: [] }));
    if (path === "/api/v1/explanations/plan") return json(envelope(EXPLAIN));
    return json({ error: { code: "not_found", message: path } });
  }));
}

function renderComposition(scenarioId: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/scenarios/${scenarioId}/composition`]}>
        <Routes><Route path="/scenarios/:scenarioId/composition" element={<CompositionScreen />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("C4 — strict decoder accepts every public plan state and rejects the unknown", () => {
  it("accepts all five live plan states as domain results", () => {
    expect(decodePlan(procPlan).agent_team_plan.plan_state).toBe("COMPLETE");
    expect(decodePlan(partialPlan).agent_team_plan.plan_state).toBe("PARTIAL");
    expect(decodePlan(cyberPlan).agent_team_plan.plan_state).toBe("NO_FEASIBLE_TEAM");
    expect(decodePlan(searchPlan).agent_team_plan.plan_state).toBe("SEARCH_SPACE_EXCEEDED");
    expect(decodePlan(invalidPlan).agent_team_plan.plan_state).toBe("INVALID_INPUT");
  });

  it("treats INVALID_INPUT as a valid DOMAIN state, not a decoder failure", () => {
    expect(() => decodePlan(invalidPlan)).not.toThrow();
    expect(decodePlan(invalidPlan).agent_team_plan.plan_state).toBe("INVALID_INPUT");
  });

  it("distinguishes a domain state from malformed transport (non-object / garbage throws)", () => {
    expect(() => decodePlan(null)).toThrow(DecodeError);
    expect(() => decodePlan("not json object")).toThrow(DecodeError);
    expect(() => decodePlan({ plan_state: "COMPLETE" })).toThrow(DecodeError); // missing agent_team_plan
  });

  it("rejects an unknown plan state", () => {
    const bad = JSON.parse(JSON.stringify(procPlan));
    bad.agent_team_plan.plan_state = "MADE_UP_STATE";
    expect(() => decodePlan(bad)).toThrow(/unknown plan state/);
  });
});

describe("C4 — PARTIAL renders honestly", () => {
  it("shows PARTIAL, filled assignments, and the unfilled role without fabrication", async () => {
    stub(partialPlan);
    renderComposition("partial_demo");
    await screen.findByTestId("partial-notice");
    expect(screen.getByRole("table")).toBeInTheDocument(); // filled assignments visible
    const rows = screen.getAllByRole("row");
    expect(rows.length).toBe(partialPlan.agent_team_plan.role_assignments.length + 1); // no fabricated rows
    expect(screen.getByText("role::proc_supplier_risk")).toBeInTheDocument(); // unfilled role listed
    expect(screen.getByTestId("planning-note")).toBeInTheDocument(); // maturity language visible
    expect(screen.queryByTestId("no-feasible-team")).not.toBeInTheDocument();
  });
});

describe("C4 — SEARCH_SPACE_EXCEEDED renders honestly", () => {
  it("shows the state and search-limit diagnostics with no fabricated team", async () => {
    stub(searchPlan);
    renderComposition("search_demo");
    const panel = await screen.findByTestId("search-space-exceeded");
    expect(within(panel).getByText(/search space limit exceeded/i)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument(); // no fabricated assignments
    expect(screen.queryByText("Selected primary")).not.toBeInTheDocument();
    expect(within(panel).getByText(/browser runs no search/i)).toBeInTheDocument(); // no client-side search implied
  });
});

describe("C4 — INVALID_INPUT renders honestly", () => {
  it("shows validation diagnostics and fabricates nothing", async () => {
    stub(invalidPlan);
    renderComposition("invalid_demo");
    const panel = await screen.findByTestId("invalid-input");
    expect(within(panel).getByText(/input_validation:registry_snapshot_digest/)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByText("Selected primary")).not.toBeInTheDocument();
    expect(within(panel).getByText(/distinct from malformed transport JSON or a network failure/i)).toBeInTheDocument();
  });
});
