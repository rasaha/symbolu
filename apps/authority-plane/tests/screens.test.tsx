// The five screens over the worker's answers: every read answer is shown under the
// identity banner that says the read was not authenticated; a typed refusal and an
// unreachable worker look different from an empty list; a read never carries the proof
// header; without a presented token no write is sent; with one, a load and a revoke post
// once each with the proof header and show what the worker recorded, or its refusal.
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { App } from "@/App";

afterEach(() => vi.unstubAllGlobals());

const PROOF_HEADER = "X-Ugence-Approver-Proof";

const ENVELOPE = {
  result: "READ",
  plane: "authority",
  ruling: "AP-5",
  tenant_id: "tenant-a",
  as_of: "2026-09-05T09:00:00+00:00",
  read_authenticated: false,
  decision_identity_proof: "PRESENTED_UNPROVEN",
  issuer_validation: "IN_PROCESS_ISSUER_ONLY",
  provenance: "what an administrator loaded; the directory attests nothing about whether it should exist",
  maturity: "REFERENCE_GRADE_SHADOW_ONLY",
};

const GRANT = {
  grant_id: "grant_abc123",
  tenant_id: "tenant-a",
  principal: { principal_id: "https%3A%2F%2Fidp%7Calice", principal_kind: "HUMAN", display_ref: "", quorum: 0 },
  role: "risk-approver",
  scope: "approval/policy_pack",
  validity: { issued_at: "2026-09-04T09:00:00+00:00", expires_at: "2026-10-05T09:00:00+00:00", stale_after: "" },
  loaded_by: "e2e",
  revoked_at: null,
  revocation_reason: "",
};

const RECORDED = {
  result: "RECORDED", recorded: true, plane: "authority", ruling: "AW-1", tenant_id: "tenant-a",
  as_of: "2026-09-05T10:00:00+00:00", identity_proof: "IDP_AUTHENTICATED",
  subject: "https%3A%2F%2Fissuer.test%7Croot-admin", authentication_reference: "authn:sha256:abc",
  issuer_validation: "IN_PROCESS_ISSUER_ONLY", provenance: ENVELOPE.provenance, maturity: ENVELOPE.maturity,
};

type Route = { status?: number; body: unknown };
type Call = { method: string; url: string; headers: Record<string, string>; body: unknown };

/** Routes keyed by "METHOD fragment" or a bare fragment; the first matching key answers. */
function mockWorker(routes: Record<string, Route>, opts: { unreachable?: boolean } = {}) {
  const calls: Call[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const method = init?.method ?? "GET";
    const headers = (init?.headers ?? {}) as Record<string, string>;
    calls.push({ method, url, headers, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (opts.unreachable) throw new TypeError("failed to fetch");
    const key = Object.keys(routes).find((k) => {
      const [m, frag] = k.includes(" ") ? k.split(" ", 2) : [undefined, k];
      return (!m || m === method) && url.includes(frag);
    });
    const route = key ? routes[key] : { status: 500, body: {} };
    return new Response(JSON.stringify(route.body), {
      status: route.status ?? 200,
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fn);
  return calls;
}

async function present(token: string) {
  await userEvent.type(screen.getByLabelText("issuer token"), token);
  await userEvent.click(screen.getByRole("button", { name: /present token/i }));
  expect(screen.getByRole("status", { name: /token presented/i })).toHaveTextContent(/a token is presented/);
}

describe("Authority Plane — reads, and two gated writes", () => {
  it("says on its face what it can and cannot do, and names all five screens", () => {
    mockWorker({});
    render(<App />);
    const note = screen.getByRole("note", { name: /can and cannot do/i });
    expect(note).toHaveTextContent(/recorded only for a human subject of this tenant/);
    expect(note).toHaveTextContent(/not served until the worker composes their stores/);
    for (const label of ["Grants", "Holders", "Committee", "Grant events", "Load grant"]) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
    }
    expect(screen.getByRole("status", { name: /token presented/i })).toHaveTextContent(/no token presented/);
    expect(document.body.textContent).toContain("no identity provider is provisioned");
  });

  it("reads a principal's grants and shows them under the identity banner, with no proof header on the read", async () => {
    const calls = mockWorker({
      "GET /authority/grants?principal_id=": { body: { ...ENVELOPE, principal_id: "https%3A%2F%2Fidp%7Calice", grants: [GRANT], grant_count: 1 } },
    });
    render(<App />);
    await userEvent.type(screen.getByLabelText("principal id"), "https%3A%2F%2Fidp%7Calice");
    await userEvent.click(screen.getByRole("button", { name: /read grants/i }));
    const result = await screen.findByTestId("grants-result");
    const banner = within(result).getByRole("note", { name: /identity and provenance/i });
    expect(banner).toHaveTextContent("read_authenticated: false");
    expect(banner).toHaveTextContent("decision proof: PRESENTED_UNPROVEN");
    expect(banner).toHaveTextContent("issuer validation: IN_PROCESS_ISSUER_ONLY");
    expect(banner).toHaveTextContent(/what an administrator loaded/);
    expect(within(result).getByRole("table", { name: /grants held/i })).toHaveTextContent("risk-approver");
    expect(calls).toHaveLength(1);
    expect(calls[0].method).toBe("GET");
    expect(calls[0].url).toContain("/authority/grants?principal_id=https%253A%252F%252Fidp%257Calice");
    expect(calls[0].headers[PROOF_HEADER]).toBeUndefined();
    // the revoke control is offered but disabled: no token is presented
    expect(within(result).getByRole("button", { name: /revoke grant_abc123/i })).toBeDisabled();
  });

  it("an empty list is shown as empty, a typed refusal as a refusal, an unreachable worker as unreachable", async () => {
    mockWorker({
      "/authority/holders?role=nobody": { body: { ...ENVELOPE, role: "nobody", scope: "s", holders: [], holder_count: 0 } },
      "/authority/committees/none": { status: 404, body: { result: "NOT_FOUND", plane: "authority", ruling: "AP-5", reason: "no committee 'none'", maturity: "REFERENCE_GRADE_SHADOW_ONLY" } },
    });
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "Holders" }));
    await userEvent.type(screen.getByRole("textbox", { name: "role", exact: true }), "nobody");
    await userEvent.type(screen.getByRole("textbox", { name: "scope", exact: true }), "s");
    await userEvent.click(screen.getByRole("button", { name: /read holders/i }));
    expect(await screen.findByRole("status", { name: /holders empty/i })).toHaveTextContent(/not a refusal/);

    await userEvent.click(screen.getByRole("button", { name: "Committee" }));
    await userEvent.type(screen.getByRole("textbox", { name: "committee id" }), "none");
    await userEvent.type(screen.getByRole("textbox", { name: "role", exact: true }), "r");
    await userEvent.type(screen.getByRole("textbox", { name: "scope", exact: true }), "s");
    await userEvent.click(screen.getByRole("button", { name: /read committee/i }));
    const refusal = await screen.findByRole("status", { name: /typed refusal/i });
    expect(refusal).toHaveTextContent("NOT_FOUND");
    expect(refusal).toHaveTextContent("HTTP 404");

    vi.unstubAllGlobals();
    mockWorker({}, { unreachable: true });
    await userEvent.click(screen.getByRole("button", { name: "Grant events" }));
    await userEvent.type(screen.getByRole("textbox", { name: "grant id" }), "grant_x");
    await userEvent.click(screen.getByRole("button", { name: /read events/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/not reachable/);
  });

  it("a committee report counts members against its quorum and links to a grant's events with one more GET", async () => {
    const calls = mockWorker({
      "/authority/committees/risk-committee": {
        body: {
          ...ENVELOPE, committee_id: "risk-committee",
          report: { committee: { principal_id: "risk-committee", principal_kind: "COMMITTEE", display_ref: "", quorum: 2 },
                    role: "risk-approver", scope: "approval/policy_pack", members: [GRANT], member_count: 1,
                    quorum_met_at_as_of: false, as_of: ENVELOPE.as_of },
        },
      },
      "/authority/grants/grant_abc123/events": {
        body: { ...ENVELOPE, grant_id: "grant_abc123", grant: GRANT,
                events: [{ event_id: "e1", grant_id: "grant_abc123", sequence: 1, event_type: "GRANTED", occurred_at: ENVELOPE.as_of, actor: "e2e", detail: "" }],
                event_count: 1 },
      },
    });
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "Committee" }));
    await userEvent.type(screen.getByRole("textbox", { name: "committee id" }), "risk-committee");
    await userEvent.type(screen.getByRole("textbox", { name: "role", exact: true }), "risk-approver");
    await userEvent.type(screen.getByRole("textbox", { name: "scope", exact: true }), "approval/policy_pack");
    await userEvent.click(screen.getByRole("button", { name: /read committee/i }));
    expect(await screen.findByRole("status", { name: /quorum/i })).toHaveTextContent(/quorum not met/);
    await userEvent.click(screen.getByRole("button", { name: "Events" }));
    const events = await screen.findByRole("list", { name: /grant events/i });
    expect(events).toHaveTextContent("GRANTED");
    expect(calls.map((c) => c.method)).toEqual(["GET", "GET"]);
    expect(calls[1].url).toContain("/authority/grants/grant_abc123/events");
  });

  it("without a presented token the load form is complete but disabled, and no request is made", async () => {
    const calls = mockWorker({});
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "Load grant" }));
    expect(screen.getByRole("note", { name: /no token for load/i })).toHaveTextContent(/Nothing is sent without one/);
    await userEvent.type(screen.getByLabelText("principal id"), "https%3A%2F%2Fidp%7Cbob");
    await userEvent.type(screen.getByLabelText("role", { exact: true }), "risk-approver");
    await userEvent.type(screen.getByLabelText("scope", { exact: true }), "approval/policy_pack");
    const submit = screen.getByRole("button", { name: /^load this grant$/i });
    expect(submit).toBeDisabled();
    await userEvent.click(submit);
    expect(calls).toHaveLength(0);
  });

  it("with a presented token a load posts once with the proof header and shows what the worker recorded; a read still carries no header", async () => {
    const calls = mockWorker({
      "POST /authority/grants": { body: { ...RECORDED, operation: "authority_grant_role", event: "GRANTED", grant: { ...GRANT, loaded_by: RECORDED.subject } } },
      "GET /authority/grants?principal_id=": { body: { ...ENVELOPE, principal_id: "https%3A%2F%2Fidp%7Calice", grants: [GRANT], grant_count: 1 } },
    });
    render(<App />);
    await present("tok-from-the-idp");
    await userEvent.click(screen.getByRole("button", { name: "Load grant" }));
    expect(screen.queryByRole("note", { name: /no token for load/i })).toBeNull();
    await userEvent.type(screen.getByLabelText("principal id"), "https%3A%2F%2Fidp%7Cbob");
    await userEvent.selectOptions(screen.getByLabelText("principal kind"), "HUMAN");
    await userEvent.type(screen.getByLabelText("role", { exact: true }), "risk-approver");
    await userEvent.type(screen.getByLabelText("scope", { exact: true }), "approval/policy_pack");
    await userEvent.type(screen.getByLabelText(/authority reference/), "directory://roles/risk-approver");
    await userEvent.click(screen.getByRole("button", { name: /^load this grant$/i }));
    const recorded = await screen.findByRole("status", { name: /write recorded/i });
    expect(recorded).toHaveTextContent("GRANTED");
    expect(recorded).toHaveTextContent("identity proof: IDP_AUTHENTICATED");
    expect(recorded).toHaveTextContent("issuer validation: IN_PROCESS_ISSUER_ONLY");
    expect(recorded).toHaveTextContent(RECORDED.subject);
    expect(recorded).toHaveTextContent(/in-process issuer only/);
    expect(calls).toHaveLength(1);
    expect(calls[0].method).toBe("POST");
    expect(calls[0].url).toMatch(/\/authority\/grants$/);
    expect(calls[0].headers[PROOF_HEADER]).toBe("tok-from-the-idp");
    expect(calls[0].body).toMatchObject({
      principal: { principal_id: "https%3A%2F%2Fidp%7Cbob", principal_kind: "HUMAN", quorum: 0 },
      role: "risk-approver", scope: "approval/policy_pack", authority_reference: "directory://roles/risk-approver",
    });
    expect(Object.keys(calls[0].body as object).sort()).toEqual(
      ["authority_reference", "expires_at", "issued_at", "member_of", "principal", "role", "scope"]);
    // the token never appears in the document
    expect(document.body.textContent).not.toContain("tok-from-the-idp");
    // a read after the token is presented still carries no header
    await userEvent.click(screen.getByRole("button", { name: "Grants" }));
    await userEvent.type(screen.getByLabelText("principal id"), "https%3A%2F%2Fidp%7Calice");
    await userEvent.click(screen.getByRole("button", { name: /read grants/i }));
    await screen.findByTestId("grants-result");
    expect(calls[1].method).toBe("GET");
    expect(calls[1].headers[PROOF_HEADER]).toBeUndefined();
  });

  it("a typed refusal from the worker is shown as refused with its reason, and as not recorded", async () => {
    mockWorker({
      "POST /authority/grants": { status: 409, body: { result: "REFUSED_NOT_HUMAN", recorded: false, plane: "authority", ruling: "AW-5", operation: "authority_grant_role", reason: "a SERVICE actor never administers a grant", issuer_validation: "IN_PROCESS_ISSUER_ONLY", maturity: ENVELOPE.maturity } },
    });
    render(<App />);
    await present("svc-token");
    await userEvent.click(screen.getByRole("button", { name: "Load grant" }));
    await userEvent.type(screen.getByLabelText("principal id"), "x");
    await userEvent.type(screen.getByLabelText("role", { exact: true }), "r");
    await userEvent.type(screen.getByLabelText("scope", { exact: true }), "s");
    await userEvent.click(screen.getByRole("button", { name: /^load this grant$/i }));
    const refused = await screen.findByRole("status", { name: /write refused/i });
    expect(refused).toHaveTextContent("REFUSED_NOT_HUMAN");
    expect(refused).toHaveTextContent("HTTP 409");
    expect(refused).toHaveTextContent(/never administers a grant/);
    expect(refused).toHaveTextContent(/Nothing was recorded/);
  });

  it("revoking from the grants table posts to the revoke path with the reason and the proof header, then re-reads", async () => {
    const calls = mockWorker({
      "POST /authority/grants/grant_abc123/revoke": { body: { ...RECORDED, operation: "authority_revoke_grant", event: "REVOKED", grant: { ...GRANT, revoked_at: RECORDED.as_of, revocation_reason: "left" } } },
      "GET /authority/grants?principal_id=": { body: { ...ENVELOPE, principal_id: "https%3A%2F%2Fidp%7Calice", grants: [GRANT], grant_count: 1 } },
    });
    render(<App />);
    await present("admin-token");
    await userEvent.type(screen.getByLabelText("principal id"), "https%3A%2F%2Fidp%7Calice");
    await userEvent.click(screen.getByRole("button", { name: /read grants/i }));
    await screen.findByTestId("grants-result");
    await userEvent.click(screen.getByRole("button", { name: /revoke grant_abc123/i }));
    const box = screen.getByRole("region", { name: /revoke grant_abc123/i });
    expect(within(box).getByRole("button", { name: /^revoke grant$/i })).toBeDisabled();
    await userEvent.type(within(box).getByLabelText("reason"), "left");
    await userEvent.click(within(box).getByRole("button", { name: /^revoke grant$/i }));
    const recorded = await screen.findByRole("status", { name: /write recorded/i });
    expect(recorded).toHaveTextContent("REVOKED");
    expect(calls.map((c) => c.method)).toEqual(["GET", "POST", "GET"]);
    expect(calls[1].url).toContain("/authority/grants/grant_abc123/revoke");
    expect(calls[1].headers[PROOF_HEADER]).toBe("admin-token");
    expect(calls[1].body).toEqual({ reason: "left" });
    expect(calls[2].headers[PROOF_HEADER]).toBeUndefined();
  });

  it("clearing the token disables every write control again", async () => {
    mockWorker({});
    render(<App />);
    await present("t");
    await userEvent.click(screen.getByRole("button", { name: /^clear$/i }));
    expect(screen.getByRole("status", { name: /token presented/i })).toHaveTextContent(/no token presented/);
    await userEvent.click(screen.getByRole("button", { name: "Load grant" }));
    expect(screen.getByRole("note", { name: /no token for load/i })).toBeInTheDocument();
  });
});
