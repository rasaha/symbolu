import { afterEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { App } from "@/app/App";
import { installFetchMock, renderWithProviders, fixtures } from "./testUtils";

afterEach(() => vi.unstubAllGlobals());

describe("role requirements (§16)", () => {
  it("shows role fields with source badges and a fingerprint", async () => {
    const role = fixtures.procWorkflow.role_requirements[0];
    installFetchMock();
    renderWithProviders(<App />, `/scenarios/procurement/roles/${role.role_id}`);
    await screen.findByRole("heading", { name: role.role_name });
    expect(screen.getByText(/functional requirements/i)).toBeInTheDocument();
    expect(screen.getByText(/enterprise constraints/i)).toBeInTheDocument();
    expect(screen.getByText(/authority & permission boundaries/i)).toBeInTheDocument();
    // source badges present
    expect(screen.getAllByText(/Compiler/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Enterprise policy/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/AWC-derived/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/role fingerprint/i)).toBeInTheDocument();
  });
});
