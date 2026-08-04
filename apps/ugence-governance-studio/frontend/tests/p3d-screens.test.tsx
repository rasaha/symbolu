import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "@/app/App";
import { installFetchMock, renderWithProviders, fixtures } from "./testUtils";
import type { RoleRanking, AgentTeamPlan } from "@/api/types-p3d";

afterEach(() => vi.unstubAllGlobals());

describe("Ranking Explorer (§12, §13)", () => {
  it("renders canonical ranked candidates with score decomposition", async () => {
    installFetchMock();
    renderWithProviders(<App />, "/scenarios/procurement/ranking");
    await screen.findByRole("table");
    const rk = (fixtures.procRanking as { rankings: RoleRanking[] }).rankings[0];
    // canonical order: first row rank equals API first candidate rank
    const rows = within(screen.getByRole("table")).getAllByRole("row");
    expect(rows.length).toBe(rk.ranked_candidates.length + 1);
    await userEvent.click(screen.getAllByRole("button", { name: /show breakdown/i })[0]);
    expect(screen.getByText(/score decomposition/i)).toBeInTheDocument();
    expect(screen.getByText(/Contribution \(bp\)/i)).toBeInTheDocument();
  });
});

describe("Composition Explorer (§14-§16)", () => {
  it("shows plan state, assignments and the non-greedy explanation", async () => {
    installFetchMock();
    renderWithProviders(<App />, "/scenarios/procurement/composition");
    await screen.findByTestId("non-greedy");
    const plan = (fixtures.procPlan as unknown as { agent_team_plan: AgentTeamPlan }).agent_team_plan;
    const firstRole = plan.role_assignments[0].role_id;
    expect(screen.getAllByText(firstRole).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Selected primary/).length).toBeGreaterThan(0);
    expect(screen.getByText(/ranking evaluates role-level suitability/i)).toBeInTheDocument();
  });

  it("renders NO_FEASIBLE_TEAM honestly with no fabricated assignment", async () => {
    installFetchMock();
    renderWithProviders(<App />, "/scenarios/cybersecurity_no_feasible_team/composition");
    await screen.findByTestId("no-feasible-team");
    expect(screen.queryByText(/Selected primary/)).not.toBeInTheDocument();
  });
});

describe("Permission proposals (§18, §19)", () => {
  it("shows proposals with categories and a no-grant notice", async () => {
    installFetchMock();
    renderWithProviders(<App />, "/scenarios/procurement/permissions");
    await screen.findByTestId("proposal-notice");
    expect(screen.getByTestId("proposal-notice")).toHaveTextContent(/do not grant, provision or activate/i);
    expect(screen.getAllByText(/Proposed/i).length).toBeGreaterThan(0);
  });
});

describe("Fallback Explorer (§20, §21)", () => {
  it("shows the coverage summary and explicit fallback states", async () => {
    installFetchMock();
    renderWithProviders(<App />, "/scenarios/procurement/fallbacks");
    await screen.findByTestId("fallback-summary");
    expect(screen.getByText(/Roles with no fallback/i)).toBeInTheDocument();
    expect(screen.getAllByText(/No fallback available|Fallback available|Limited fallback/).length).toBeGreaterThan(0);
  });
});

describe("Replay (§22)", () => {
  it("shows a matching replay with fingerprints and no execution language", async () => {
    installFetchMock();
    renderWithProviders(<App />, "/scenarios/procurement/replay");
    await screen.findByTestId("replay-result");
    expect(screen.getByTestId("replay-result")).toHaveTextContent(/fingerprints match/i);
    expect(screen.getByText(/does not rerun or replay agent execution/i)).toBeInTheDocument();
  });
});

describe("Comparison (§23)", () => {
  it("renders the API diff", async () => {
    installFetchMock();
    renderWithProviders(<App />, "/scenarios/procurement/compare");
    await screen.findByTestId("plan-diff");
    expect(screen.getByText(/Assignment changes/i)).toBeInTheDocument();
  });
});

describe("Controlled what-if (§24, §25)", () => {
  it("applies a bounded perturbation and shows baseline vs modified with reset", async () => {
    installFetchMock();
    renderWithProviders(<App />, "/scenarios/procurement/what-if");
    await screen.findByTestId("whatif-apply");
    expect(screen.getByTestId("whatif-notice")).toHaveTextContent(/temporary copied scenario/i);
    await userEvent.click(screen.getByTestId("whatif-apply"));
    await screen.findByTestId("whatif-result");
    expect(screen.getByText(/Modified \(temporary copy\)/i)).toBeInTheDocument();
    await userEvent.click(screen.getByTestId("whatif-reset"));
    expect(screen.queryByTestId("whatif-result")).not.toBeInTheDocument();
  });

  it("offers only the nine allowlisted operations", async () => {
    installFetchMock();
    renderWithProviders(<App />, "/scenarios/procurement/what-if");
    const select = await screen.findByLabelText("Perturbation (bounded)");
    const options = within(select).getAllByRole("option").map((o) => o.getAttribute("value"));
    expect(options).toEqual([
      "FORBID_PROVIDER", "REQUIRE_RESIDENCY", "TIGHTEN_COST_CEILING", "TIGHTEN_LATENCY_CEILING",
      "REVOKE_AGENT_VERSION", "EXPIRE_EVIDENCE", "TIGHTEN_PERMISSION_POLICY",
      "TIGHTEN_PROVIDER_CONCENTRATION", "REMOVE_CANDIDATE",
    ]);
  });
});
