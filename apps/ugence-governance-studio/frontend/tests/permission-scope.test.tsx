import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { App } from "@/app/App";
import { installFetchMock, renderWithProviders, fixtures } from "./testUtils";

afterEach(() => vi.unstubAllGlobals());

// C2 — permission REQUIREMENTS are displayed; composition-time permission
// PROPOSALS / granting / provisioning are not.
describe("permission scope (C2)", () => {
  it("displays role permission requirements + prohibited permissions with a scope note", async () => {
    const role = fixtures.procWorkflow.role_requirements[0];
    installFetchMock();
    renderWithProviders(<App />, `/scenarios/procurement/roles/${role.role_id}`);
    await screen.findByRole("heading", { name: role.role_name });
    expect(screen.getByText("Required permissions")).toBeInTheDocument();
    expect(screen.getByText("Prohibited permissions")).toBeInTheDocument();
    // the precise requirement-vs-proposal note is present
    const note = screen.getByTestId("permission-scope-note");
    expect(note).toHaveTextContent(/requirements/i);
    expect(note).toHaveTextContent(/P3D/);
  });

  it("displays agent requested permissions in the registry", async () => {
    installFetchMock();
    renderWithProviders(<App />, "/scenarios/procurement/registry");
    await screen.findByRole("heading", { name: /agent registry/i });
    expect(screen.getAllByText("Requested permissions").length).toBeGreaterThan(0);
  });

  it("exposes no P3D permission-proposal navigation or controls", async () => {
    installFetchMock();
    renderWithProviders(<App />, "/scenarios/procurement");
    await screen.findByTestId("verification-state");
    const nav = screen.getByRole("navigation", { name: /scenario sections/i });
    // P3D adds Ranking/Composition/Permissions/Fallbacks/Replay/Comparison/What-If.
    const links = within(nav).getAllByRole("link").map((l) => l.textContent);
    for (const expected of ["Eligibility", "Ranking", "Composition", "Permissions", "Fallbacks", "What-If"]) {
      expect(links.some((t) => t === expected)).toBe(true);
    }
  });
});

// Source-level guard: permission REQUIREMENTS and PROPOSALS are legitimate (P3C +
// P3D), but grant / provisioning / authorization language must never appear.
describe("no permission grant/provisioning language in src (C2 + §19)", () => {
  const SRC = path.resolve(__dirname, "..", "src");
  const BANNED = [
    "permission granted",
    "grant permission",
    "provision permission",
    "permission provisioning",
    "runtime provisioning",
    "access granted",
    "credentials issued",
    "permission activated",
    "authorized to execute",
  ];
  function walk(dir: string): string[] {
    const out: string[] = [];
    for (const name of readdirSync(dir)) {
      const full = path.join(dir, name);
      if (statSync(full).isDirectory()) out.push(...walk(full));
      else if (/\.(ts|tsx)$/.test(name)) out.push(full);
    }
    return out;
  }
  it("no banned permission-proposal phrase appears in src", () => {
    for (const file of walk(SRC)) {
      const text = readFileSync(file, "utf-8").toLowerCase();
      for (const phrase of BANNED) {
        expect(text.includes(phrase), `${path.basename(file)} contains "${phrase}"`).toBe(false);
      }
    }
  });
});
