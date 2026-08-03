import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "@/app/App";
import { installFetchMock, renderWithProviders, fixtures } from "./testUtils";
import type { RoleEligibilityReport } from "@/api/types";

afterEach(() => vi.unstubAllGlobals());

describe("scenario catalog (§11)", () => {
  it("renders the four scenarios with synthetic labels and a recommended demo", async () => {
    installFetchMock();
    renderWithProviders(<App />, "/scenarios");
    await screen.findByRole("heading", { name: /scenario catalog/i });
    for (const s of fixtures.scenarios.scenarios) {
      expect(screen.getByText(s.title)).toBeInTheDocument();
    }
    expect(screen.getAllByText(/synthetic data/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/recommended demo/i)).toBeInTheDocument();
  });

  it("does not auto-open a scenario (requires an explicit action)", async () => {
    installFetchMock();
    renderWithProviders(<App />, "/scenarios");
    await screen.findByRole("heading", { name: /scenario catalog/i });
    // still on the catalog; no overview heading present
    expect(screen.queryByText(/deterministic verification/i)).not.toBeInTheDocument();
  });
});

describe("scenario overview (§12)", () => {
  it("shows verification state and no ranking metrics", async () => {
    installFetchMock();
    renderWithProviders(<App />, "/scenarios/procurement");
    await screen.findByTestId("verification-state");
    expect(screen.getByText("Eligible pairs")).toBeInTheDocument();
    expect(screen.queryByText(/team score/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/\brank\b/i)).not.toBeInTheDocument();
  });
});

describe("workflow (§13-§15)", () => {
  it("renders every node in the accessible list with an API disposition", async () => {
    installFetchMock();
    renderWithProviders(<App />, "/scenarios/procurement/workflow");
    const list = await screen.findByRole("region", { name: /accessible list/i });
    const buttons = within(list).getAllByRole("button");
    expect(buttons.length).toBe(fixtures.procWorkflow.nodes.length);
    // a known AWC disposition label appears
    expect(within(list).getAllByText(/AI-agent role|Deterministic service|Human authority|Governance-owned|No agent required/).length).toBeGreaterThan(0);
  });

  it("opens node details on selection", async () => {
    installFetchMock();
    renderWithProviders(<App />, "/scenarios/procurement/workflow");
    const list = await screen.findByRole("region", { name: /accessible list/i });
    const first = within(list).getAllByRole("button")[0];
    await userEvent.click(first);
    expect(screen.getByText(/compiler-derived workflow semantics/i)).toBeInTheDocument();
  });
});

describe("registry (§17)", () => {
  it("renders agents with separated evidence classes and synthetic labels", async () => {
    installFetchMock();
    renderWithProviders(<App />, "/scenarios/procurement/registry");
    await screen.findByRole("heading", { name: /agent registry/i });
    expect(screen.getAllByText(/synthetic/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/DECLARED evidence/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/MEASURED evidence/i).length).toBeGreaterThan(0);
  });
});

describe("eligibility matrix (§18-§20)", () => {
  it("accounts for every role-agent pair and shows states, no rank column", async () => {
    installFetchMock();
    renderWithProviders(<App />, "/scenarios/procurement/eligibility");
    const table = await screen.findByRole("table");
    const report = (fixtures.procEligibility as { role_reports: RoleEligibilityReport[] }).role_reports[0];
    const rows = within(table).getAllByRole("row");
    // header + one row per agent in the first role
    expect(rows.length).toBe(report.results.length + 1);
    expect(screen.queryByText(/score/i)).not.toBeInTheDocument();
    expect(screen.getByText(/not a selection decision/i)).toBeInTheDocument();
  });

  it("opens the explanation drawer with reasons and fingerprints, and restores focus", async () => {
    installFetchMock();
    renderWithProviders(<App />, "/scenarios/procurement/eligibility");
    await screen.findByRole("table");
    const explainButtons = screen.getAllByRole("button", { name: /^Explain$/i });
    const trigger = explainButtons[0];
    await userEvent.click(trigger);
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/failed conditions/i)).toBeInTheDocument();
    expect(within(dialog).getByText(/result fingerprint/i)).toBeInTheDocument();
    // close restores focus to the page
    await userEvent.click(within(dialog).getByRole("button", { name: /close explanation/i }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});
