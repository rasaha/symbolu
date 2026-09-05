import { afterEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { axe } from "vitest-axe";
import { App } from "@/app/App";
import { installFetchMock, renderWithProviders } from "./testUtils";
import { installV2FetchMock, renderStudio } from "./studioTestUtils";

afterEach(() => vi.unstubAllGlobals());

// color-contrast cannot be evaluated in jsdom; disable that rule only.
const axeOpts = { rules: { "color-contrast": { enabled: false } } };

describe("accessibility (§24)", () => {
  it("scenario catalog has no serious axe violations", async () => {
    installFetchMock();
    const { container } = renderWithProviders(<App />, "/scenarios");
    await screen.findByRole("heading", { name: /scenario catalog/i });
    const results = await axe(container, axeOpts);
    expect(results).toHaveNoViolations();
  });

  it("eligibility matrix has no serious axe violations", async () => {
    installFetchMock();
    const { container } = renderWithProviders(<App />, "/scenarios/procurement/eligibility");
    await screen.findByRole("table");
    const results = await axe(container, axeOpts);
    expect(results).toHaveNoViolations();
  });
});

// --------------------------------------------------------------------------- //
// Governed Agent Studio — all six screens (GAS-4/5)
// --------------------------------------------------------------------------- //
const STUDIO_SCREENS: { route: string; name: string; ready: () => Promise<unknown> }[] = [
  {
    route: "/studio/constitution",
    name: "Constitution",
    ready: () => screen.findByRole("button", { name: /preflight issuance/i }),
  },
  {
    route: "/studio/policy",
    name: "Policy",
    ready: () => screen.findByTestId("policy-canvas"),
  },
  {
    route: "/studio/authority",
    name: "Authority",
    ready: () => screen.findByRole("note", { name: /capability unavailable/i }),
  },
  {
    route: "/studio/simulate",
    name: "Simulate",
    ready: () => screen.findByLabelText(/execution mode/i),
  },
  {
    route: "/studio/publish",
    name: "Publish",
    ready: () => screen.findByRole("button", { name: /send to shadow loop/i }),
  },
  {
    route: "/studio/observe",
    name: "Observe",
    ready: () => screen.findByLabelText(/correlation id/i),
  },
];

describe("accessibility — Governed Agent Studio", () => {
  for (const s of STUDIO_SCREENS) {
    it(`${s.name} has no serious axe violations`, async () => {
      installV2FetchMock();
      const { container } = renderStudio(<App />, s.route);
      await s.ready();
      const results = await axe(container, axeOpts);
      expect(results).toHaveNoViolations();
    });
  }

  it("the permissive-hook banner is announced, not merely coloured", async () => {
    // The banner carries the single most important caveat on the Simulate screen; a
    // user who cannot see the colour must still receive it.
    installV2FetchMock({
      results: {
        "/api/v2/simulate/run": {
          available: true,
          execution_mode: "DRY_RUN",
          instance_id: "i1",
          governance_hook_configured: true,
          governance_hook_permissive: true,
          quanta: [],
        },
      },
    });
    const { container } = renderStudio(<App />, "/studio/simulate");
    const button = await screen.findByRole("button", { name: /run simulation/i });
    button.click();
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/not a governance result/i);
    const results = await axe(container, axeOpts);
    expect(results).toHaveNoViolations();
  });
});
