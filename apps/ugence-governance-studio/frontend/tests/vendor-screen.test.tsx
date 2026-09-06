// Screen 5b — Vendor dependencies (front-door seam 9, FD-13).
//
// The screen sends typed fields and nothing else, shows the gap when no declarations
// file is configured, renders a typed refusal as a refusal, discloses that the declarer
// is presented and unproven and that a declaration confers nothing, and — the point of
// FD-13.4 — states that the risk posture is recorded and never assessed, offering no
// approval, onboarding, tier, certification, score, rank, verify or enforce control.
import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { App } from "@/app/App";
import { installV2FetchMock, renderStudio, unavailable } from "./studioTestUtils";

afterEach(() => vi.unstubAllGlobals());

const D = "e".repeat(64);
const PATH = "/api/v2/vendor/declarations";
const CONFERS =
  "nothing: a vendor declaration is a record of what a declarer asserted, not an approval, an onboarding decision or a permission (vendor-risk ADR VR-1, FD-13.4)";
const POSTURE_NOTE =
  "uninterpreted: the posture is recorded exactly as the declarer typed it and is ordered, compared, ranked and scored nowhere; no vendor approval, onboarding status, tier or certification is implied, because no package computes one";
const RECORD = {
  declaration: {
    declaration_id: "vdd_0123456789abcdef0123456789abcdef",
    tenant_id: "tenant-1",
    vendor_ref: "vendor://acme-llm",
    risk_posture_label: "elevated",
    policy_ref: "policy://vendor-standard/v3",
    declared_by: "directory://people/declarer-1",
    supersedes: "",
  },
  binding: { binding_id: "bind-1", tenant_id: "tenant-1", system_id: "hiring-screener" },
};
const DECLARED = {
  available: true,
  declared: true,
  tenant_id: "tenant-1",
  store_kind: "SqliteVendorDeclarations",
  declaration_id: RECORD.declaration.declaration_id,
  record: RECORD,
  record_digest: "f".repeat(64),
  declared_by: "directory://people/declarer-1",
  declared_by_status: "PRESENTED_UNPROVEN",
  recorded_by: "governance-studio-private-hosted/0.10.0",
  risk_posture: POSTURE_NOTE,
  confers: CONFERS,
  result: RECORD,
};
const LISTED = {
  available: true,
  tenant_id: "tenant-1",
  store_kind: "SqliteVendorDeclarations",
  as_of: "2026-09-06T00:00:00+00:00",
  as_of_source: "request",
  count: 1,
  declared_by_status: "PRESENTED_UNPROVEN",
  recorded_by: "governance-studio-private-hosted/0.10.0",
  risk_posture: POSTURE_NOTE,
  confers: CONFERS,
  result: [RECORD],
};

async function fillForm() {
  const user = userEvent.setup();
  const type = async (label: RegExp, value: string) => {
    await user.type(screen.getByLabelText(label), value);
  };
  await type(/^Binding id/, "bind-1");
  await type(/^Subject id/, "subject-1");
  await type(/^Context id/, "ctx-1");
  await type(/^Context digest/, D);
  await type(/^System id/, "hiring-screener");
  await type(/^System version/, "1.0.0");
  await type(/^Configuration id/, "cfg-1");
  await type(/^Configuration digest/, D);
  await type(/^Vendor reference/, "vendor://acme-llm");
  await type(/^Risk posture label/, "elevated");
  await type(/^Policy reference/, "policy://vendor-standard/v3");
  await type(/^Issued at/, "2026-09-01T00:00:00+00:00");
  return user;
}

describe("5b · Vendor dependencies", () => {
  it("is reachable from the studio nav and offers declare only", async () => {
    installV2FetchMock({ results: { [PATH]: LISTED } });
    renderStudio(<App />, "/studio/vendor");
    expect(await screen.findByRole("link", { name: "Vendor dependencies" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^declare$/i })).toBeInTheDocument();
    for (const forbidden of [
      /approve/i,
      /onboard/i,
      /score/i,
      /rank/i,
      /grade/i,
      /verify/i,
      /resolve/i,
      /certif/i,
      /revoke/i,
      /delete/i,
      /edit/i,
    ]) {
      expect(screen.queryByRole("button", { name: forbidden })).toBeNull();
    }
    expect(
      screen.getByText(
        /never resolves, verifies, scores, grades, ranks, approves, onboards or contacts/i,
      ),
    ).toBeInTheDocument();
  });

  it("shows the gap when no vendor declarations file is configured, on both panels", async () => {
    const gap = unavailable(
      "vendor_declarations",
      "no vendor declarations file is configured: this deployment holds no vendor declarations file",
    );
    installV2FetchMock({ results: { [PATH]: gap } });
    renderStudio(<App />, "/studio/vendor");
    const notes = await screen.findAllByRole("note", { name: /capability unavailable/i });
    expect(notes.length).toBeGreaterThan(0);
    expect(notes[0]).toHaveTextContent(/vendor_declarations/);
  });

  it("sends exactly the typed fields, and no tenant, id, recorded_by or vendor reachability", async () => {
    const fetchMock = installV2FetchMock({ results: { [PATH]: DECLARED } });
    renderStudio(<App />, "/studio/vendor");
    await screen.findByRole("button", { name: /^declare$/i });
    const user = await fillForm();
    await user.click(screen.getByRole("button", { name: /^declare$/i }));
    await screen.findByTestId("vendor-declared-notice");
    const calls = fetchMock.mock.calls as unknown as [RequestInfo | URL, RequestInit | undefined][];
    const post = calls.find(([, init]) => init?.method === "POST");
    expect(post).toBeDefined();
    const sent = JSON.parse(String(post![1]?.body));
    expect(Object.keys(sent).sort()).toEqual([
      "binding",
      "correlation_id",
      "declared_by",
      "notes",
      "policy_ref",
      "risk_posture_label",
      "supersedes",
      "validity",
      "vendor_ref",
    ]);
    expect(sent.binding.tenant_id).toBeUndefined();
    expect(sent.declaration_id).toBeUndefined();
    expect(sent.recorded_by).toBeUndefined();
    expect(sent.tenant_id).toBeUndefined();
    // FD-13.4: an opaque reference travels; nothing that could reach or rank the vendor
    expect(sent.vendor_ref).toBe("vendor://acme-llm");
    for (const forbidden of [
      "endpoint",
      "address",
      "credential",
      "approved",
      "onboarding",
      "risk_score",
      "tier",
      "certification",
      "contract_terms",
    ]) {
      expect(JSON.stringify(sent)).not.toContain(forbidden);
    }
    expect(sent.validity).toEqual({
      issued_at: "2026-09-01T00:00:00+00:00",
      expires_at: null,
    });
  });

  it("discloses that the declarer is presented and unproven and that declaring confers nothing", async () => {
    installV2FetchMock({ results: { [PATH]: DECLARED } });
    renderStudio(<App />, "/studio/vendor");
    await screen.findByRole("button", { name: /^declare$/i });
    const user = await fillForm();
    await user.click(screen.getByRole("button", { name: /^declare$/i }));
    const notice = await screen.findByTestId("vendor-declared-notice");
    expect(notice).toHaveTextContent(/PRESENTED_UNPROVEN/);
    expect(notice).toHaveTextContent(/confers nothing/i);
    expect(notice).toHaveTextContent(RECORD.declaration.declaration_id);
  });

  it("states that the risk posture is recorded and never assessed", async () => {
    installV2FetchMock({ results: { [PATH]: DECLARED } });
    renderStudio(<App />, "/studio/vendor");
    await screen.findByRole("button", { name: /^declare$/i });
    const user = await fillForm();
    await user.click(screen.getByRole("button", { name: /^declare$/i }));
    const notes = await screen.findAllByRole("note", { name: /risk posture/i });
    expect(notes[0]).toHaveTextContent(/uninterpreted/);
    expect(notes[0]).toHaveTextContent(/ranked and scored nowhere/);
    expect(notes[0]).toHaveTextContent(/no package computes one/);
  });

  it("renders a typed refusal as a refusal, not as an error or an empty state", async () => {
    installV2FetchMock({
      results: {
        [PATH]: {
          available: true,
          refused: true,
          code: "supersession_refused",
          reason: "the superseded declaration does not exist",
          result: null,
        },
      },
    });
    renderStudio(<App />, "/studio/vendor");
    await screen.findByRole("button", { name: /^declare$/i });
    const user = await fillForm();
    await user.click(screen.getByRole("button", { name: /^declare$/i }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/supersession_refused/);
    expect(alert).toHaveTextContent(/does not exist/);
  });

  it("lists the declarations in force with the tenant, the instant and the disclosures", async () => {
    installV2FetchMock({ results: { [PATH]: LISTED } });
    renderStudio(<App />, "/studio/vendor");
    await waitFor(() => expect(screen.getByText(/1 declaration\(s\)/)).toBeInTheDocument());
    const disclosure = screen.getByText(/declarers are PRESENTED_UNPROVEN/);
    expect(disclosure).toHaveTextContent(/Tenant tenant-1/);
    expect(disclosure).toHaveTextContent(/as of 2026-09-06T00:00:00\+00:00/);
    expect(disclosure).toHaveTextContent(/a declaration confers nothing/);
    expect(screen.getAllByText(/SqliteVendorDeclarations/).length).toBeGreaterThan(0);
  });

  it("says the posture is uninterpreted and the policy reference never resolved", async () => {
    installV2FetchMock({ results: { [PATH]: LISTED } });
    renderStudio(<App />, "/studio/vendor");
    await screen.findByRole("button", { name: /^declare$/i });
    expect(
      screen.getByText(/nothing orders, ranks or scores it/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Recorded and never resolved/i)).toBeInTheDocument();
    expect(screen.getByText(/An opaque locator in your own spelling/i)).toBeInTheDocument();
    // the paragraph carries inline markup, so match the clause's own text node
    expect(
      screen.getByText(/due-diligence workflow/i, { exact: false }),
    ).toBeInTheDocument();
  });
});
