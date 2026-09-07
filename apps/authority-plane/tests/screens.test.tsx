// The four screens over the worker's answers: every answer is shown under the
// identity banner that says the read was not authenticated; a typed refusal and an
// unreachable worker look different from an empty list; the app issues GETs only, has
// no write control, and never sends a proof header (AP-3 controlling, ADR §18).
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

type Route = { status?: number; body: unknown };
type Call = { method: string; url: string; headers: Record<string, string> };

function mockWorker(routes: Record<string, Route>, opts: { unreachable?: boolean } = {}) {
  const calls: Call[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    calls.push({ method: init?.method ?? "GET", url, headers: (init?.headers ?? {}) as Record<string, string> });
    if (opts.unreachable) throw new TypeError("failed to fetch");
    const key = Object.keys(routes).find((k) => url.includes(k));
    const route = key ? routes[key] : { status: 500, body: {} };
    return new Response(JSON.stringify(route.body), {
      status: route.status ?? 200,
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fn);
  return calls;
}

describe("Authority Plane — reads only", () => {
  it("says on its face what it cannot do, names the four screens, and offers no write control", () => {
    mockWorker({});
    render(<App />);
    const note = screen.getByRole("note", { name: /cannot do yet/i });
    expect(note).toHaveTextContent(/not served until the identity adapter has been validated end to end/);
    expect(note).toHaveTextContent(/implementation and conformance evidence only/);
    for (const label of ["Grants", "Holders", "Committee", "Grant events"]) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
    }
    expect(screen.queryByRole("button", { name: /load grant/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /revoke/i })).toBeNull();
    expect(screen.queryByLabelText(/issuer token/i)).toBeNull();
    expect(document.body.textContent).toContain("no write is served before enterprise issuer validation");
  });

  it("reads a principal's grants and shows them under the identity banner, with no proof header and no revoke", async () => {
    const calls = mockWorker({
      "/authority/grants?principal_id=": { body: { ...ENVELOPE, principal_id: "https%3A%2F%2Fidp%7Calice", grants: [GRANT], grant_count: 1 } },
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
    expect(within(result).queryByRole("button", { name: /revoke/i })).toBeNull();
    expect(calls).toHaveLength(1);
    expect(calls[0].method).toBe("GET");
    expect(calls[0].url).toContain("/authority/grants?principal_id=https%253A%252F%252Fidp%257Calice");
    expect(calls[0].headers[PROOF_HEADER]).toBeUndefined();
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
    for (const c of calls) expect(c.headers[PROOF_HEADER]).toBeUndefined();
  });
});
