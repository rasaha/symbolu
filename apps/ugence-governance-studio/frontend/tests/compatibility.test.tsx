import { afterEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { App } from "@/app/App";
import { installFetchMock, renderWithProviders } from "./testUtils";

afterEach(() => vi.unstubAllGlobals());

describe("API compatibility gate (§9)", () => {
  it("renders the app when the backend is compatible", async () => {
    installFetchMock();
    renderWithProviders(<App />, "/scenarios");
    expect(await screen.findByRole("heading", { name: /scenario catalog/i })).toBeInTheDocument();
  });

  it("blocks on an unsupported API contract", async () => {
    installFetchMock({ unsupportedContract: true });
    renderWithProviders(<App />, "/scenarios");
    expect(await screen.findByText(/not compatible/i)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /scenario catalog/i })).not.toBeInTheDocument();
  });

  it("blocks when the backend is not ready", async () => {
    installFetchMock({ notReady: true });
    renderWithProviders(<App />, "/scenarios");
    expect(await screen.findByText(/not compatible/i)).toBeInTheDocument();
  });

  it("blocks when the backend is unreachable", async () => {
    installFetchMock({ unreachable: true });
    renderWithProviders(<App />, "/scenarios");
    expect(await screen.findByText(/not compatible/i)).toBeInTheDocument();
  });
});
