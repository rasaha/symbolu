// Screen 5 — Data use (front-door seam 8, FD-12).
//
// The screen sends typed fields and nothing else, shows the gap when no declarations
// file is configured, renders a typed refusal as a refusal, discloses that the declarer
// is presented and unproven and that a declaration confers nothing, states that no
// egress restriction is expressible, and offers no admit, authorize, verify, score,
// enforce, revoke, edit or delete control.
import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { App } from "@/app/App";
import { installV2FetchMock, renderStudio, unavailable } from "./studioTestUtils";

afterEach(() => vi.unstubAllGlobals());

const D = "b".repeat(64);
const PATH = "/api/v2/data-use/declarations";
const CONFERS =
  "nothing: a declaration is a record of what a declarer asserted, not an admission, an approval or a permission (data-egress ADR DE-1, FD-12.5)";
const EGRESS =
  "not expressible: no egress-authority package exists in this repository, so this seam records declared use and restricts nothing";
const RECORD = {
  declaration: {
    declaration_id: "dud_0123456789abcdef0123456789abcdef",
    tenant_id: "tenant-1",
    data_ref: "dataset://applicants/2026",
    classification_label: "candidate-personal-data",
    purpose_label: "shortlisting",
    residency_label: "",
    declared_by: "directory://people/declarer-1",
    supersedes: "",
  },
  binding: { binding_id: "bind-1", tenant_id: "tenant-1", system_id: "hiring-screener" },
};
const DECLARED = {
  available: true,
  declared: true,
  tenant_id: "tenant-1",
  store_kind: "SqliteDataUseDeclarations",
  declaration_id: RECORD.declaration.declaration_id,
  record: RECORD,
  record_digest: "c".repeat(64),
  declared_by: "directory://people/declarer-1",
  declared_by_status: "PRESENTED_UNPROVEN",
  recorded_by: "governance-studio-private-hosted/0.9.0",
  confers: CONFERS,
  egress_restrictions: EGRESS,
  result: RECORD,
};
const LISTED = {
  available: true,
  tenant_id: "tenant-1",
  store_kind: "SqliteDataUseDeclarations",
  as_of: "2026-09-06T00:00:00+00:00",
  as_of_source: "request",
  count: 1,
  declared_by_status: "PRESENTED_UNPROVEN",
  recorded_by: "governance-studio-private-hosted/0.9.0",
  confers: CONFERS,
  egress_restrictions: EGRESS,
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
  await type(/^Data reference/, "dataset://applicants/2026");
  await type(/^Classification label/, "candidate-personal-data");
  await type(/^Purpose label/, "shortlisting");
  await type(/^Issued at/, "2026-09-01T00:00:00+00:00");
  return user;
}

describe("5 · Data use", () => {
  it("is reachable from the studio nav and offers declare only", async () => {
    installV2FetchMock({ results: { [PATH]: LISTED } });
    renderStudio(<App />, "/studio/data-use");
    expect(await screen.findByRole("link", { name: "Data use" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^declare$/i })).toBeInTheDocument();
    for (const forbidden of [
      /admit/i,
      /authorize/i,
      /verify/i,
      /score/i,
      /enforce/i,
      /revoke/i,
      /delete/i,
      /edit/i,
      /redact/i,
      /minimi/i,
    ]) {
      expect(screen.queryByRole("button", { name: forbidden })).toBeNull();
    }
    expect(
      screen.getByText(
        /never inspects, classifies, redacts, minimizes, admits, authorizes, verifies, scores or enforces/i,
      ),
    ).toBeInTheDocument();
  });

  it("shows the gap when no declarations file is configured, on both panels", async () => {
    const gap = unavailable(
      "data_use_declarations",
      "no data-use declarations file is configured: this deployment holds no declarations file",
    );
    installV2FetchMock({ results: { [PATH]: gap } });
    renderStudio(<App />, "/studio/data-use");
    const notes = await screen.findAllByRole("note", { name: /capability unavailable/i });
    expect(notes.length).toBeGreaterThan(0);
    expect(notes[0]).toHaveTextContent(/data_use_declarations/);
  });

  it("sends exactly the typed fields, and no tenant, id, recorded_by or data", async () => {
    const fetchMock = installV2FetchMock({ results: { [PATH]: DECLARED } });
    renderStudio(<App />, "/studio/data-use");
    await screen.findByRole("button", { name: /^declare$/i });
    const user = await fillForm();
    await user.click(screen.getByRole("button", { name: /^declare$/i }));
    await screen.findByTestId("declared-notice");
    const calls = fetchMock.mock.calls as unknown as [RequestInfo | URL, RequestInit | undefined][];
    const post = calls.find(([, init]) => init?.method === "POST");
    expect(post).toBeDefined();
    const sent = JSON.parse(String(post![1]?.body));
    expect(Object.keys(sent).sort()).toEqual([
      "binding",
      "classification_label",
      "correlation_id",
      "data_ref",
      "declared_by",
      "notes",
      "purpose_label",
      "residency_label",
      "supersedes",
      "validity",
    ]);
    expect(sent.binding.tenant_id).toBeUndefined();
    expect(sent.declaration_id).toBeUndefined();
    expect(sent.recorded_by).toBeUndefined();
    expect(sent.tenant_id).toBeUndefined();
    // FD-12.5: an opaque reference travels, never the data
    expect(sent.data_ref).toBe("dataset://applicants/2026");
    for (const forbidden of ["payload", "content", "rows", "bytes", "blob", "sample"]) {
      expect(JSON.stringify(sent)).not.toContain(forbidden);
    }
    expect(sent.validity).toEqual({
      issued_at: "2026-09-01T00:00:00+00:00",
      expires_at: null,
    });
    expect(sent.classification_label).toBe("candidate-personal-data");
    expect(sent.purpose_label).toBe("shortlisting");
  });

  it("discloses that the declarer is presented and unproven and that declaring confers nothing", async () => {
    installV2FetchMock({ results: { [PATH]: DECLARED } });
    renderStudio(<App />, "/studio/data-use");
    await screen.findByRole("button", { name: /^declare$/i });
    const user = await fillForm();
    await user.click(screen.getByRole("button", { name: /^declare$/i }));
    const notice = await screen.findByTestId("declared-notice");
    expect(notice).toHaveTextContent(/PRESENTED_UNPROVEN/);
    expect(notice).toHaveTextContent(/confers nothing/i);
    expect(notice).toHaveTextContent(RECORD.declaration.declaration_id);
  });

  it("states that no egress restriction is expressible rather than offering one", async () => {
    installV2FetchMock({ results: { [PATH]: DECLARED } });
    renderStudio(<App />, "/studio/data-use");
    await screen.findByRole("button", { name: /^declare$/i });
    const user = await fillForm();
    await user.click(screen.getByRole("button", { name: /^declare$/i }));
    const notes = await screen.findAllByRole("note", { name: /egress restrictions/i });
    expect(notes[0]).toHaveTextContent(/not expressible/);
    expect(notes[0]).toHaveTextContent(/restricts nothing/);
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
    renderStudio(<App />, "/studio/data-use");
    await screen.findByRole("button", { name: /^declare$/i });
    const user = await fillForm();
    await user.click(screen.getByRole("button", { name: /^declare$/i }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/supersession_refused/);
    expect(alert).toHaveTextContent(/does not exist/);
  });

  it("lists the declarations in force with the tenant, the instant and the disclosures", async () => {
    installV2FetchMock({ results: { [PATH]: LISTED } });
    renderStudio(<App />, "/studio/data-use");
    await waitFor(() => expect(screen.getByText(/1 declaration\(s\)/)).toBeInTheDocument());
    const disclosure = screen.getByText(/declarers are PRESENTED_UNPROVEN/);
    expect(disclosure).toHaveTextContent(/Tenant tenant-1/);
    expect(disclosure).toHaveTextContent(/as of 2026-09-06T00:00:00\+00:00/);
    expect(disclosure).toHaveTextContent(/a declaration confers nothing/);
    expect(screen.getAllByText(/SqliteDataUseDeclarations/).length).toBeGreaterThan(0);
  });

  it("records the labels exactly as typed, saying they are interpreted nowhere", async () => {
    installV2FetchMock({ results: { [PATH]: LISTED } });
    renderStudio(<App />, "/studio/data-use");
    await screen.findByRole("button", { name: /^declare$/i });
    expect(
      screen.getByText(/what the declarer called it, never what that means/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Recorded as metadata and evaluated nowhere in this deployment/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/An opaque locator/i)).toBeInTheDocument();
  });
});
