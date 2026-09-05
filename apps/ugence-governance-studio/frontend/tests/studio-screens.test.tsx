// The six studio screens.
//
// The recurring assertion is that a screen SHOWS the gap the backend reports. A screen
// that rendered an empty panel instead would be telling an operator that nothing is
// there, when what is true is that the capability is not configured — a materially
// different statement.
import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { App } from "@/app/App";
import { installV2FetchMock, renderStudio, unavailable } from "./studioTestUtils";
import {
  FROZEN_APPROVAL_RECORD,
  FROZEN_POLICY_PACK,
} from "@/features/studio/fixtures/frozenPack";

afterEach(() => vi.unstubAllGlobals());

describe("studio shell", () => {
  it("mounts all six screens under /studio without touching the v1 routes", async () => {
    installV2FetchMock();
    renderStudio(<App />, "/studio/constitution");
    for (const label of ["Constitution", "Policy", "Authority", "Simulate", "Publish", "Observe"]) {
      expect(await screen.findByRole("link", { name: label })).toBeInTheDocument();
    }
  });

  it("states the contract and the posture in the shell", async () => {
    installV2FetchMock();
    renderStudio(<App />, "/studio/constitution");
    expect(await screen.findByText(/governance_studio\.api\.v2/)).toBeInTheDocument();
    expect(
      screen.getByText(/no screen here issues, activates, revokes, grants, authorizes, clears or executes/i),
    ).toBeInTheDocument();
  });
});

describe("1 · Constitution", () => {
  it("offers validate and preflight, and no issue or activate control", async () => {
    installV2FetchMock();
    renderStudio(<App />, "/studio/constitution");
    expect(await screen.findByRole("button", { name: /validate/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /preflight issuance/i })).toBeInTheDocument();
    for (const forbidden of [/^issue$/i, /^activate$/i, /^revoke$/i, /^grant$/i]) {
      expect(screen.queryByRole("button", { name: forbidden })).toBeNull();
    }
  });

  it("shows the missing trust root rather than a disabled button", async () => {
    installV2FetchMock({
      results: {
        "/api/v2/constitution/preflight": unavailable(
          "constitution_preflight",
          "no ActivationRoot is configured: this repository ships no signing key and no trust root",
        ),
      },
    });
    renderStudio(<App />, "/studio/constitution");
    await userEvent.click(await screen.findByRole("button", { name: /preflight issuance/i }));
    const note = await screen.findByRole("note", { name: /capability unavailable/i });
    expect(note).toHaveTextContent(/constitution_preflight/);
    expect(note).toHaveTextContent(/no signing key and no trust root/i);
  });
});

describe("2 · Policy", () => {
  it("renders the canvas from the frozen pack with only governance node kinds", async () => {
    installV2FetchMock();
    renderStudio(<App />, "/studio/policy");
    expect(await screen.findByTestId("policy-canvas")).toBeInTheDocument();
    const legend = screen.getByLabelText("canvas node kinds");
    for (const label of ["Capability", "Role", "Obligation", "Policy clause"]) {
      expect(legend).toHaveTextContent(label);
    }
    for (const banned of [/llm/i, /prompt/i, /\bAPI node\b/i]) {
      expect(legend.textContent ?? "").not.toMatch(banned);
    }
  });

  it("separates preview from compile, and says compile needs an approval", async () => {
    installV2FetchMock();
    renderStudio(<App />, "/studio/policy");
    expect(await screen.findByRole("button", { name: /preview workflow ir/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /compile with approval/i })).toBeInTheDocument();
    expect(
      screen.getByText(/Compile requires a human approval record/i),
    ).toBeInTheDocument();
  });

  it("shows the compiler's refusal when synthesis fails", async () => {
    installV2FetchMock({
      results: {
        "/api/v2/policy/synthesize": {
          available: true,
          synthesized: false,
          error_type: "CompilationError",
          result: { diagnostics: [] },
        },
      },
    });
    renderStudio(<App />, "/studio/policy");
    await userEvent.click(await screen.findByRole("button", { name: /preview workflow ir/i }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/compiler refused to synthesize/i);
    expect(alert).toHaveTextContent(/CompilationError/);
  });

  it("the mirrored fixture has not drifted from the backend's demo_data", async () => {
    const { readFileSync } = await import("node:fs");
    const path = await import("node:path");
    const source = JSON.parse(
      readFileSync(
        path.resolve(__dirname, "..", "..", "fixtures", "v2", "policy_pack.json"),
        "utf-8",
      ),
    );
    expect(JSON.parse(JSON.stringify(FROZEN_POLICY_PACK))).toEqual(source);
    const approvalSource = JSON.parse(
      readFileSync(
        path.resolve(__dirname, "..", "..", "fixtures", "v2", "approval_record.json"),
        "utf-8",
      ),
    );
    expect(JSON.parse(JSON.stringify(FROZEN_APPROVAL_RECORD))).toEqual(approvalSource);
  });
});

describe("3 · Authority", () => {
  it("shows the in-memory registry gap", async () => {
    installV2FetchMock();
    renderStudio(<App />, "/studio/authority");
    const note = await screen.findByRole("note", { name: /capability unavailable/i });
    expect(note).toHaveTextContent(/authority_registry/);
    expect(note).toHaveTextContent(/in-memory/i);
  });

  it("names which registry answered, and warns when it is in-memory", async () => {
    installV2FetchMock({
      results: {
        "/api/v2/authority/policies": {
          available: true,
          result: [],
          registry_kind: "InMemoryPolicyRegistry",
          identities_queried: [],
        },
      },
    });
    renderStudio(<App />, "/studio/authority");
    const note = await screen.findByRole("note", { name: /registry provenance/i });
    expect(note).toHaveTextContent("InMemoryPolicyRegistry");
    expect(note).toHaveTextContent(/one process/i);
    expect(note).toHaveTextContent(/empty list does not mean nothing was issued/i);
  });

  it("offers no issue or revoke control", async () => {
    installV2FetchMock();
    renderStudio(<App />, "/studio/authority");
    await screen.findByRole("note", { name: /capability unavailable/i });
    for (const forbidden of [/issue/i, /revoke/i, /supersede/i, /grant/i]) {
      expect(screen.queryByRole("button", { name: forbidden })).toBeNull();
    }
  });
});

describe("4 · Simulate", () => {
  it("offers only the non-mutating execution modes", async () => {
    installV2FetchMock();
    renderStudio(<App />, "/studio/simulate");
    const select = await screen.findByLabelText(/execution mode/i);
    const options = [...select.querySelectorAll("option")].map((o) => o.textContent);
    expect(options).toEqual(["DRY_RUN", "SIMULATION", "SHADOW"]);
    expect(options).not.toContain("LIVE");
  });

  it("shows a loud banner when a permissive hook cleared the run", async () => {
    installV2FetchMock({
      results: {
        "/api/v2/simulate/run": {
          available: true,
          execution_mode: "DRY_RUN",
          instance_id: "i1",
          governance_hook_configured: true,
          governance_hook_permissive: true,
          quanta: [{ progressed: true }],
        },
      },
    });
    renderStudio(<App />, "/studio/simulate");
    await userEvent.click(await screen.findByRole("button", { name: /run simulation/i }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/not a governance result/i);
    expect(alert).toHaveTextContent(/clears every proposal by construction/i);
  });

  it("explains the default blocking hook when none is configured", async () => {
    installV2FetchMock({
      results: {
        "/api/v2/simulate/run": {
          available: true,
          execution_mode: "DRY_RUN",
          instance_id: "i1",
          governance_hook_configured: false,
          governance_hook_permissive: false,
          quanta: [],
        },
      },
    });
    renderStudio(<App />, "/studio/simulate");
    await userEvent.click(await screen.findByRole("button", { name: /run simulation/i }));
    const note = await screen.findByRole("note", { name: /no governance adapter configured/i });
    expect(note).toHaveTextContent(/blocks every consequential transition/i);
  });
});

describe("5 · Publish", () => {
  it("says shadow on the control, and reports an unconfigured console", async () => {
    installV2FetchMock({
      results: {
        "/api/v2/publish/shadow": unavailable(
          "console_api",
          "no ugence_console_api base URL is configured",
        ),
      },
    });
    renderStudio(<App />, "/studio/publish");
    const button = await screen.findByRole("button", { name: /send to shadow loop/i });
    expect(button).toBeInTheDocument();
    await userEvent.click(button);
    const note = await screen.findByRole("note", { name: /capability unavailable/i });
    expect(note).toHaveTextContent(/console_api/);
  });

  it("offers no live or authorize control", async () => {
    installV2FetchMock();
    renderStudio(<App />, "/studio/publish");
    await screen.findByRole("button", { name: /send to shadow loop/i });
    for (const forbidden of [/live/i, /authorize/i, /clear/i, /execute/i]) {
      expect(screen.queryByRole("button", { name: forbidden })).toBeNull();
    }
  });
});

describe("6 · Observe", () => {
  it("distinguishes an unreachable console from an empty audit store", async () => {
    installV2FetchMock();
    renderStudio(<App />, "/studio/observe");
    const note = await screen.findByRole("note", { name: /capability unavailable/i });
    expect(note).toHaveTextContent(/console_api/);

    vi.unstubAllGlobals();
    installV2FetchMock({ results: { "/api/v2/observe/audit": { available: true, result: [] } } });
    renderStudio(<App />, "/studio/observe");
    await waitFor(() =>
      expect(
        screen.getByText(/reachable and reported no correlation ids/i),
      ).toBeInTheDocument(),
    );
  });

  it("lists correlation ids the console reported", async () => {
    installV2FetchMock({
      results: { "/api/v2/observe/audit": { available: true, result: ["corr-1", "corr-2"] } },
    });
    renderStudio(<App />, "/studio/observe");
    expect(await screen.findByRole("button", { name: "corr-1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "corr-2" })).toBeInTheDocument();
  });
});
