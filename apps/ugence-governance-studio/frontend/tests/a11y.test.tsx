import { afterEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { axe } from "vitest-axe";
import { App } from "@/app/App";
import { installFetchMock, renderWithProviders } from "./testUtils";

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
