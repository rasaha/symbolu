// Status panel (ADR_UGENCE_MODULE_ADMINISTRATION_SCOPING.md MA-2 as amended by MS-1 to
// MS-5).
//
// One read of the deployment's own startup attestation. The panel renders the six seam
// states, the checks and the pins as the gate attested them; it renders the ceiling
// that says a configured seam is not a reachable engine; it renders the typed gap when
// no report was handed; it shows no registry row and no certificate fact; and it
// issues exactly one GET and no write.
import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, within } from "@testing-library/react";

import { App } from "@/app/App";
import { installV2FetchMock, renderStudio, unavailable } from "./studioTestUtils";

afterEach(() => vi.unstubAllGlobals());

const PATH = "/api/v2/observe/deployment";

const CEILING =
  "STARTUP_ATTESTATION: what this deployment attested about itself before its port bound, handed to the studio once at composition and never re-read. A configured seam is not a reachable engine, a passed check is not a live one, and nothing here is probed at request time.";

const ATTESTED = {
  available: true,
  ceiling: CEILING,
  seam_state_fields: [
    "constitution_registry",
    "authority_reads",
    "simulation_provider",
    "system_registry",
    "data_use_declarations",
    "vendor_declarations",
  ],
  excluded_fields: ["cert_subject", "cert_expiry"],
  result: {
    seams: {
      constitution_registry: "configured",
      authority_reads: "unset",
      simulation_provider: "configured",
      system_registry: "unwritable",
      data_use_declarations: "unset",
      vendor_declarations: "unset",
    },
    checks: { config_valid: true, tls_certificate_valid: true, openapi_hash_unchanged: false },
    result: "FAIL",
    failure_code: "GOVERNANCE_STUDIO_P3E_OPENAPI_DRIFT",
    pins: {
      deployment: "governance-studio-private-hosted",
      deployment_version: "0.12.0",
      frontend_version: "0.2.0",
      frontend_build_hash: "f".repeat(64),
      backend_api_version: "0.1.0",
      api_contract: "governance_studio.api.v1",
      openapi_sha256: "d".repeat(64),
      synthetic_bundle_hash: null,
    },
  },
};

function callsTo(fetchMock: ReturnType<typeof installV2FetchMock>, path: string) {
  return fetchMock.mock.calls.filter(([u]) => String(u).includes(path));
}

describe("Status — MA-2 as amended (MS-1 to MS-5)", () => {
  it("is reachable from the studio nav at /studio/status", async () => {
    installV2FetchMock({ results: { [PATH]: ATTESTED } });
    renderStudio(<App />, "/studio/status");
    expect(await screen.findByRole("link", { name: "Status" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Status" })).toBeInTheDocument();
  });

  it("renders the typed gap when no report was handed at composition", async () => {
    const fetchMock = installV2FetchMock({
      results: {
        [PATH]: unavailable(
          "deployment_report",
          "no startup integrity report was handed to the studio at composition",
        ),
      },
    });
    renderStudio(<App />, "/studio/status");
    const note = await screen.findByRole("note", { name: /capability unavailable/i });
    expect(note).toHaveTextContent(/deployment_report/);
    expect(note).toHaveTextContent(/handed to the studio at composition/);
    expect(screen.queryByTestId("status-seams")).toBeNull();
    expect(callsTo(fetchMock, PATH)).toHaveLength(1);
  });

  it("renders the seam states, the checks, the gate result and the pins as attested, under the ceiling", async () => {
    const fetchMock = installV2FetchMock({ results: { [PATH]: ATTESTED } });
    renderStudio(<App />, "/studio/status");
    const ceiling = await screen.findByRole("note", { name: /startup attestation ceiling/i });
    expect(ceiling).toHaveTextContent(/not a reachable engine/);
    expect(ceiling).toHaveTextContent(/nothing here is probed at request time/);

    const seams = screen.getByTestId("status-seams");
    for (const name of ATTESTED.seam_state_fields) {
      expect(within(seams).getByText(name)).toBeInTheDocument();
    }
    expect(within(seams).getAllByText("configured")).toHaveLength(2);
    expect(within(seams).getAllByText("unset")).toHaveLength(3);
    expect(within(seams).getByText("unwritable")).toBeInTheDocument();

    const gate = screen.getByRole("status", { name: /gate result/i });
    expect(gate).toHaveTextContent(/FAIL/);
    expect(gate).toHaveTextContent(/GOVERNANCE_STUDIO_P3E_OPENAPI_DRIFT/);

    const checks = screen.getByRole("list", { name: /integrity checks/i });
    expect(within(checks).getAllByText("passed")).toHaveLength(2);
    expect(within(checks).getAllByText("failed")).toHaveLength(1);
    expect(checks).toHaveTextContent(/openapi_hash_unchanged/);

    const pins = screen.getByTestId("status-pins");
    expect(pins).toHaveTextContent(/governance-studio-private-hosted/);
    expect(pins).toHaveTextContent(/0\.12\.0/);
    expect(pins).toHaveTextContent(/governance_studio\.api\.v1/);
    expect(screen.getByText(/Not shown by ruling MS-4/)).toHaveTextContent(/cert_subject, cert_expiry/);

    // one GET, no write, nothing else asked of the API by this panel
    const calls = callsTo(fetchMock, PATH);
    expect(calls).toHaveLength(1);
    const [, init] = calls[0] as unknown as [unknown, RequestInit | undefined];
    expect(init?.method ?? "GET").toBe("GET");
    expect(init?.body).toBeUndefined();
    expect(callsTo(fetchMock, "/api/v2/observe/audit")).toHaveLength(0);
    expect(callsTo(fetchMock, "/v1/modules")).toHaveLength(0);
  });

  it("shows no registry row and no certificate fact (MS-1, MS-4)", async () => {
    installV2FetchMock({ results: { [PATH]: ATTESTED } });
    renderStudio(<App />, "/studio/status");
    await screen.findByTestId("status-seams");
    const main = document.body.textContent ?? "";
    for (const word of ["maturity", "wiring", "Hybrid LLM", "ActionGate", "CN=", "notAfter"]) {
      expect(main).not.toContain(word);
    }
  });
});
