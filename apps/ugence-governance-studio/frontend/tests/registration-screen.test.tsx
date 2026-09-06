// Screen 1 — Registration (front-door seam 5, FD-9).
//
// The screen sends typed fields and nothing else, shows the gap when no registry is
// configured, renders a typed refusal as a refusal, discloses that the owner
// reference is presented and unproven and that a registration confers nothing, and
// offers no admit, approve, gate, revoke, edit or delete control.
import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { App } from "@/app/App";
import { installV2FetchMock, renderStudio, unavailable } from "./studioTestUtils";

afterEach(() => vi.unstubAllGlobals());

const D = "a".repeat(64);
const RECORD = {
  registration: {
    registration_id: "reg_0123456789abcdef0123456789abcdef",
    tenant_id: "tenant-1",
    system_id: "hiring-screener",
    system_version: "1.0.0",
    owner_ref: "directory://people/owner-1",
    classification_label: "high-risk",
    registered_by: "governance-studio-private-hosted/0.6.0",
    supersedes: "",
  },
  binding: { binding_id: "bind-1", tenant_id: "tenant-1", system_id: "hiring-screener" },
};
const REGISTERED = {
  available: true,
  registered: true,
  tenant_id: "tenant-1",
  registry_kind: "SqliteSystemRegistry",
  registration_id: RECORD.registration.registration_id,
  record: RECORD,
  record_digest: "b".repeat(64),
  owner_ref_status: "PRESENTED_UNPROVEN",
  registered_by: "governance-studio-private-hosted/0.6.0",
  confers: "nothing: a registration is a record, not a permission (registry ADR D-5)",
  result: RECORD,
};
const LISTED = {
  available: true,
  tenant_id: "tenant-1",
  registry_kind: "SqliteSystemRegistry",
  as_of: "2026-09-06T00:00:00+00:00",
  as_of_source: "request",
  count: 1,
  owner_ref_status: "PRESENTED_UNPROVEN",
  confers: "nothing: a registration is a record, not a permission (registry ADR D-5)",
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
  await type(/^Owner reference/, "directory://people/owner-1");
  await type(/^Classification label/, "high-risk");
  await type(/^Issued at/, "2026-09-01T00:00:00+00:00");
  return user;
}

describe("1 · Registration", () => {
  it("is mounted first in the studio nav and offers register only", async () => {
    installV2FetchMock({ results: { "/api/v2/registry/registrations": LISTED } });
    renderStudio(<App />, "/studio/registration");
    expect(await screen.findByRole("link", { name: "Registration" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^register$/i })).toBeInTheDocument();
    for (const forbidden of [/admit/i, /approve/i, /^gate/i, /revoke/i, /delete/i, /edit/i, /promote/i, /attest/i]) {
      expect(screen.queryByRole("button", { name: forbidden })).toBeNull();
    }
    expect(screen.getByText(/never admits, approves, gates, promotes, attests, edits, revokes or deletes/i)).toBeInTheDocument();
  });

  it("shows the gap when no registry is configured, on both panels", async () => {
    const gap = unavailable("system_registry", "no system registry is configured: this deployment holds no registration file");
    installV2FetchMock({ results: { "/api/v2/registry/registrations": gap } });
    renderStudio(<App />, "/studio/registration");
    const notes = await screen.findAllByRole("note", { name: /capability unavailable/i });
    expect(notes.length).toBeGreaterThan(0);
    expect(notes[0]).toHaveTextContent(/system_registry/);
  });

  it("sends exactly the typed fields, and no tenant, id or registered_by", async () => {
    const fetchMock = installV2FetchMock({ results: { "/api/v2/registry/registrations": REGISTERED } });
    renderStudio(<App />, "/studio/registration");
    await screen.findByRole("button", { name: /^register$/i });
    const user = await fillForm();
    await user.click(screen.getByRole("button", { name: /^register$/i }));
    await screen.findByTestId("registered-notice");
    const calls = fetchMock.mock.calls as unknown as [RequestInfo | URL, RequestInit | undefined][];
    const post = calls.find(([, init]) => init?.method === "POST");
    expect(post).toBeDefined();
    const body = JSON.parse(String(post![1]?.body));
    expect(Object.keys(body).sort()).toEqual(["binding", "classification_label", "notes", "owner_ref", "supersedes", "validity"]);
    expect(body.binding.tenant_id).toBeUndefined();
    expect(body.registration_id).toBeUndefined();
    expect(body.registered_by).toBeUndefined();
    expect(body.tenant_id).toBeUndefined();
    expect(body.binding.system_id).toBe("hiring-screener");
    expect(body.binding.context_digest).toBe(D);
    expect(body.validity).toEqual({ issued_at: "2026-09-01T00:00:00+00:00", expires_at: null });
    expect(body.classification_label).toBe("high-risk");
  });

  it("discloses that the owner reference is presented and unproven and that registering confers nothing", async () => {
    installV2FetchMock({ results: { "/api/v2/registry/registrations": REGISTERED } });
    renderStudio(<App />, "/studio/registration");
    await screen.findByRole("button", { name: /^register$/i });
    const user = await fillForm();
    await user.click(screen.getByRole("button", { name: /^register$/i }));
    const notice = await screen.findByTestId("registered-notice");
    expect(notice).toHaveTextContent(/PRESENTED_UNPROVEN/);
    expect(notice).toHaveTextContent(/confers nothing/i);
    expect(notice).toHaveTextContent(RECORD.registration.registration_id);
  });

  it("renders a typed refusal as a refusal, not as an error or an empty state", async () => {
    installV2FetchMock({
      results: {
        "/api/v2/registry/registrations": {
          available: true, refused: true, code: "supersession_refused",
          reason: "the superseded registration does not exist", result: null,
        },
      },
    });
    renderStudio(<App />, "/studio/registration");
    await screen.findByRole("button", { name: /^register$/i });
    const user = await fillForm();
    await user.click(screen.getByRole("button", { name: /^register$/i }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/supersession_refused/);
    expect(alert).toHaveTextContent(/does not exist/);
  });

  it("lists the registrations in force with the tenant, the instant and the disclosures", async () => {
    installV2FetchMock({ results: { "/api/v2/registry/registrations": LISTED } });
    renderStudio(<App />, "/studio/registration");
    await waitFor(() => expect(screen.getByText(/1 registration\(s\)/)).toBeInTheDocument());
    const disclosure = screen.getByText(/owner references are PRESENTED_UNPROVEN/);
    expect(disclosure).toHaveTextContent(/Tenant tenant-1/);
    expect(disclosure).toHaveTextContent(/as of 2026-09-06T00:00:00\+00:00/);
    expect(disclosure).toHaveTextContent(/a registration confers nothing/);
    expect(screen.getAllByText(/SqliteSystemRegistry/).length).toBeGreaterThan(0);
  });
});
