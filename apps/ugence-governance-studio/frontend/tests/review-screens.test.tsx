// Screens 7 and 8 — Review Queue and Run Detail (GAS-7 HR-D, owner ruling HR-1).
//
// The recurring assertion is about what the screens can and cannot do: they render
// what the review service holds, relay a decision byte-for-byte, and never present a
// HOLD as awaiting a human or an unreachable service as an empty queue.
import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { App } from "@/app/App";
import { installV2FetchMock, renderStudio, unavailable } from "./studioTestUtils";

afterEach(() => vi.unstubAllGlobals());

const APPROVER = {
  approver_id: "approver-1",
  approver_kind: "HUMAN",
  role: "risk-approver",
  authority_reference: "directory://roles/risk-approver",
};

const entry = (over: Partial<Record<string, unknown>> = {}) => ({
  approval_id: "apr-1",
  approval_state: "PENDING",
  instance_id: "i1",
  task_id: "t1",
  fingerprint: "a".repeat(64),
  required_role: "risk-approver",
  requested_by: "governed-review",
  requested_at: "2026-09-05T09:00:00+00:00",
  expires_at: "2026-09-12T09:00:00+00:00",
  justification: "parked",
  workflow_id: "wf",
  workflow_status: "PAUSED",
  task_status: "WAITING",
  provider_id: "p",
  operation: "op",
  governance_disposition: "ESCALATE",
  eligible_approvers: [APPROVER],
  instance_known: true,
  ...over,
});

const queueOf = (entries: unknown[], excludedHold = 0) => ({
  available: true,
  result: { entries, maturity: "REFERENCE_GRADE_SHADOW_ONLY", identity_proof: "PRESENTED_UNPROVEN" },
  excluded_hold: excludedHold,
  identity_proof: "PRESENTED_UNPROVEN",
});

describe("7 · Review Queue", () => {
  it("is reachable from the studio nav and states what it never does", async () => {
    installV2FetchMock();
    renderStudio(<App />, "/studio/review");
    expect(await screen.findByRole("link", { name: "Review" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /review queue/i })).toBeInTheDocument();
    expect(
      screen.getByText(/holds no approver identity, computes no eligibility, consumes no approval, signals nothing and resumes nothing/i),
    ).toBeInTheDocument();
  });

  it("shows an unreachable review service as a gap, never as an empty queue", async () => {
    installV2FetchMock({
      results: {
        "/api/v2/review/queue": unavailable(
          "review_service",
          "review service unreachable for GET /review/queue: URLError",
        ),
      },
    });
    renderStudio(<App />, "/studio/review");
    const note = await screen.findByRole("note", { name: /capability unavailable/i });
    expect(note).toHaveTextContent(/review_service/);
    expect(note).toHaveTextContent(/unreachable/i);
    expect(screen.queryByText(/lists no parked instance/i)).toBeNull();
    expect(screen.queryByRole("table", { name: /review queue/i })).toBeNull();
  });

  it("distinguishes an empty queue from an unreachable one", async () => {
    installV2FetchMock({ results: { "/api/v2/review/queue": queueOf([]) } });
    renderStudio(<App />, "/studio/review");
    expect(await screen.findByText(/empty queue, not a failure to read it/i)).toBeInTheDocument();
    expect(screen.queryByRole("note", { name: /capability unavailable/i })).toBeNull();
  });

  it("lists parked ESCALATE instances with approval identity and fingerprint as history", async () => {
    installV2FetchMock({ results: { "/api/v2/review/queue": queueOf([entry()]) } });
    renderStudio(<App />, "/studio/review");
    const table = await screen.findByRole("table", { name: /review queue/i });
    expect(within(table).getByRole("link", { name: "i1" })).toHaveAttribute("href", "/studio/review/i1");
    expect(within(table).getByText("ESCALATE")).toBeInTheDocument();
    expect(within(table).getByText("PENDING")).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: /fingerprint \(history\)/i })).toBeInTheDocument();
    expect(within(table).getByLabelText(/proposal fingerprint a{64}/)).toBeInTheDocument();
    const identity = screen.getByRole("note", { name: /identity proof/i });
    expect(identity).toHaveTextContent(/PRESENTED_UNPROVEN/);
    expect(identity).toHaveTextContent(/nothing here proves who decided/i);
  });

  it("never renders a HOLD as awaiting a human, and says how many it dropped", async () => {
    installV2FetchMock({
      results: {
        "/api/v2/review/queue": queueOf(
          [entry(), entry({ approval_id: "apr-h", instance_id: "ih", governance_disposition: "HOLD", workflow_status: "WAITING" })],
          1,
        ),
      },
    });
    renderStudio(<App />, "/studio/review");
    const table = await screen.findByRole("table", { name: /review queue/i });
    expect(within(table).queryByText("ih")).toBeNull();
    expect(within(table).queryByText("HOLD")).toBeNull();
    const note = screen.getByRole("note", { name: /hold instances not listed/i });
    expect(note).toHaveTextContent(/2 parked on a HOLD, not listed/);
    expect(note).toHaveTextContent(/never awaiting a human/i);
  });

  it("relays the decision verbatim: the approver as reported, the human's word, the justification, nothing else", async () => {
    const fetchMock = installV2FetchMock({
      results: {
        "/api/v2/review/queue": queueOf([entry()]),
        "/api/v2/review/decisions": {
          available: true,
          result: {
            result: "RECORDED", recorded: true, approval_id: "apr-1", instance_id: "i1", task_id: "t1",
            signal_delivered: true, resume_delivered: true, resume_skipped_reason: "", reason: "",
            identity_proof: "PRESENTED_UNPROVEN",
          },
        },
      },
    });
    renderStudio(<App />, "/studio/review");
    await userEvent.click(await screen.findByRole("button", { name: /^decide$/i }));

    const select = screen.getByLabelText(/presented approver \(as reported by the review service\)/i);
    expect([...select.querySelectorAll("option")].map((o) => o.textContent)).toEqual([
      "approver-1 · risk-approver · HUMAN",
    ]);
    const submit = screen.getByRole("button", { name: /submit decision/i });
    expect(submit).toBeDisabled();
    await userEvent.click(screen.getByRole("radio", { name: "GRANT" }));
    expect(submit).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/justification \(required\)/i), "reviewed the proposal");
    expect(submit).toBeEnabled();
    await userEvent.click(submit);

    const calls = fetchMock.mock.calls as unknown as [RequestInfo | URL, RequestInit?][];
    const post = calls.find(([, init]) => init?.method === "POST");
    expect(post).toBeDefined();
    expect(String(post![0])).toMatch(/\/api\/v2\/review\/decisions$/);
    const body = JSON.parse(String(post![1]?.body));
    expect(body).toEqual({
      approval_id: "apr-1",
      decision: "GRANT",
      presented_approver: APPROVER,
      justification: "reviewed the proposal",
    });
    expect(Object.keys(body).sort()).toEqual(["approval_id", "decision", "justification", "presented_approver"]);

    const answer = await screen.findByRole("status", { name: /review service answer/i });
    expect(answer).toHaveTextContent(/recorded by the review service/i);
    expect(answer).toHaveTextContent(/RECORDED/);
    expect(answer).toHaveTextContent(/PRESENTED_UNPROVEN/);
  });

  it("shows a refusal as the review service's answer, with its reason", async () => {
    installV2FetchMock({
      results: {
        "/api/v2/review/queue": queueOf([entry()]),
        "/api/v2/review/decisions": {
          available: true,
          result: {
            result: "REFUSED_INELIGIBLE", recorded: false, approval_id: "apr-1", instance_id: "i1",
            task_id: "t1", signal_delivered: false, resume_delivered: false, resume_skipped_reason: "",
            reason: "approver role 'auditor' is not the required 'risk-approver'",
            identity_proof: "PRESENTED_UNPROVEN",
          },
        },
      },
    });
    renderStudio(<App />, "/studio/review");
    await userEvent.click(await screen.findByRole("button", { name: /^decide$/i }));
    await userEvent.click(screen.getByRole("radio", { name: "REJECT" }));
    await userEvent.type(screen.getByLabelText(/justification/i), "no");
    await userEvent.click(screen.getByRole("button", { name: /submit decision/i }));
    const answer = await screen.findByRole("status", { name: /review service answer/i });
    expect(answer).toHaveTextContent(/refused by the review service/i);
    expect(answer).toHaveTextContent(/REFUSED_INELIGIBLE/);
    expect(answer).toHaveTextContent(/not the required/i);
  });

  it("offers nothing to relay when the review service reports no eligible approver", async () => {
    installV2FetchMock({ results: { "/api/v2/review/queue": queueOf([entry({ eligible_approvers: [] })]) } });
    renderStudio(<App />, "/studio/review");
    await userEvent.click(await screen.findByRole("button", { name: /^decide$/i }));
    expect(screen.getByText(/no eligible approver/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /submit decision/i })).toBeNull();
  });

  it("offers no resume, release, continue, signal, clear or execute control", async () => {
    installV2FetchMock({ results: { "/api/v2/review/queue": queueOf([entry()]) } });
    renderStudio(<App />, "/studio/review");
    await userEvent.click(await screen.findByRole("button", { name: /^decide$/i }));
    for (const forbidden of [/resume/i, /release/i, /continue/i, /signal/i, /clear/i, /execute/i, /^grant$/i, /authorize/i]) {
      expect(screen.queryByRole("button", { name: forbidden })).toBeNull();
    }
  });
});

describe("8 · Run Detail", () => {
  const RUN = {
    available: true,
    result: {
      instance: {
        instance_id: "i1", workflow_id: "wf", status: "PAUSED", correlation_id: "c-i1",
        tasks: { t1: { status: "WAITING", attempts: 1 } },
        execution_states: {
          t1: {
            workflow_status: "PAUSED", task_status: "WAITING", attempt: 1, provider_id: "p",
            operation: "op", idempotency_key: "i1:t1", proposal_fingerprint: "b".repeat(64),
            governance_disposition: "ESCALATE", evaluation_reference: "eval-1",
            valid_until: 1757062800,
          },
        },
        checkpoint_digest: "d",
      },
      engine: { known: true, engine_id: "dbos" },
      open_approvals: [{ approval_id: "apr-1", state_at: "PENDING", instance_id: "i1", task_id: "t1" }],
      identity_proof: "PRESENTED_UNPROVEN",
    },
  };
  const EVENTS = {
    available: true,
    result: {
      instance_id: "i1",
      events: [
        { seq: 1, event_type: "", body: { seq: 1, type: "WORKFLOW_PAUSED", detail: {} }, attempt_token: "a1" },
        { seq: 2, event_type: "EXTERNAL_SIGNAL:review_decision", body: { signal: "review_decision" }, attempt_token: null },
      ],
    },
  };

  it("renders the instance as history and links back to the queue", async () => {
    installV2FetchMock({
      results: { "/api/v2/review/runs/i1": RUN, "/api/v2/review/runs/i1/events": EVENTS },
    });
    renderStudio(<App />, "/studio/review/i1");
    expect(await screen.findByRole("heading", { name: /run detail/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /review queue/i })).toHaveAttribute("href", "/studio/review");
    const history = await screen.findByRole("note", { name: /shown as history/i });
    expect(history).toHaveTextContent(/never a live permission|neither is a live permission/i);
    expect(screen.getByRole("note", { name: /parked on an escalate/i })).toHaveTextContent(/human decision is awaited/i);
    const table = screen.getByRole("table", { name: /tasks and execution states/i });
    expect(within(table).getByRole("columnheader", { name: /valid_until \(history\)/i })).toBeInTheDocument();
    expect(within(table).getByText("1757062800")).toBeInTheDocument();
    expect(within(table).getByLabelText(/proposal fingerprint b{64}/)).toBeInTheDocument();
    const events = screen.getByRole("table", { name: /runtime events/i });
    expect(within(events).getByText("WORKFLOW_PAUSED")).toBeInTheDocument();
    expect(within(events).getByText("EXTERNAL_SIGNAL:review_decision")).toBeInTheDocument();
  });

  it("never renders a HOLD as awaiting a human", async () => {
    const hold = JSON.parse(JSON.stringify(RUN));
    hold.result.instance.status = "WAITING";
    hold.result.instance.execution_states.t1.governance_disposition = "HOLD";
    hold.result.open_approvals = [];
    installV2FetchMock({
      results: { "/api/v2/review/runs/i1": hold, "/api/v2/review/runs/i1/events": EVENTS },
    });
    renderStudio(<App />, "/studio/review/i1");
    const note = await screen.findByRole("note", { name: /parked on a hold/i });
    expect(note).toHaveTextContent(/not awaiting a human/i);
    expect(screen.queryByRole("note", { name: /parked on an escalate/i })).toBeNull();
    expect(screen.queryByText(/human decision is awaited/i)).toBeNull();
  });

  it("shows an unknown instance as the review service's answer, and an unreachable one as a gap", async () => {
    installV2FetchMock({
      results: {
        "/api/v2/review/runs/i1": { available: true, found: false, result: null, reason: "no record" },
        "/api/v2/review/runs/i1/events": unavailable("review_service", "review service unreachable"),
      },
    });
    renderStudio(<App />, "/studio/review/i1");
    expect(await screen.findByText(/has no record of instance/i)).toBeInTheDocument();
    const note = await screen.findByRole("note", { name: /capability unavailable/i });
    expect(note).toHaveTextContent(/review_service/);
  });

  const LINKAGE_APPENDED = {
    state: "APPENDED", appended: true, approval_id: "apr-1", instance_id: "i1", task_id: "t1",
    linkage_digest: "e".repeat(64),
    linkage: {
      linkage_version: "governed_review.linkage.v1", tenant_id: "tenant-a", instance_id: "i1", task_id: "t1",
      consumer_ref: "i1:t1", correlation_id: "c-i1", proposal_fingerprint: "b".repeat(64),
      approval_id: "apr-1", approval_state: "CONSUMED", decided_by: "approver-1", decided_role: "risk-approver",
      decided_at: "2026-09-05T09:05:00+00:00", consumption_id: "cons-1", consumed_at: "2026-09-05T09:06:00+00:00",
      consumed_event_sequence: 4, parked_disposition_event_seq: 6, paused_event_seq: 8, signal_event_seq: 9,
      resumed_event_seq: 10, resumed_disposition_event_seq: 14, parked_evaluation_reference: "",
      parked_state_digest: "1".repeat(64), parked_disposition: "ESCALATE", resumed_evaluation_reference: "",
      resumed_state_digest: "2".repeat(64), resumed_disposition: "CLEAR",
    },
    audit_reference: {
      tenant_id: "tenant-a", store_ref: "ugence_control_plane_root:audit_ledger", entry_ref: "tenant-a/1",
      entry_digest: "f".repeat(64), correlation_id: "c-i1", recorded_at: "2026-09-05T09:07:00+00:00",
    },
    reason: "",
  };

  function withLinkages(linkages: unknown[]) {
    const run = JSON.parse(JSON.stringify(RUN));
    run.result.linkages = linkages;
    return run;
  }

  it("renders an appended linkage as history with its audit reference", async () => {
    installV2FetchMock({
      results: { "/api/v2/review/runs/i1": withLinkages([LINKAGE_APPENDED]), "/api/v2/review/runs/i1/events": EVENTS },
    });
    renderStudio(<App />, "/studio/review/i1");
    const list = await screen.findByRole("list", { name: /receipt linkages/i });
    const item = within(list).getByLabelText("linkage apr-1");
    expect(item).toHaveTextContent("APPENDED");
    expect(item).toHaveTextContent("ugence_control_plane_root:audit_ledger");
    expect(item).toHaveTextContent("tenant-a/1");
    expect(within(item).getByLabelText(/linkage digest e{64}/)).toBeInTheDocument();
    expect(within(item).getByLabelText(/audit entry digest f{64}/)).toBeInTheDocument();
    expect(within(item).getByLabelText(/proposal fingerprint b{64}/)).toBeInTheDocument();
    expect(item).toHaveTextContent("cons-1");
    expect(item).toHaveTextContent("approver-1 · risk-approver");
    expect(item).toHaveTextContent("8 · 9 · 10");
    expect(item).toHaveTextContent("ESCALATE → CLEAR");
    expect(screen.getByText(/This screen writes nothing/i)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("renders NOT_YET and LEDGER_UNCONFIGURED as the review service's answer, never as an error", async () => {
    installV2FetchMock({
      results: {
        "/api/v2/review/runs/i1": withLinkages([
          { state: "NOT_YET", appended: false, approval_id: "apr-1", instance_id: "i1", task_id: "t1",
            linkage_digest: null, linkage: null, audit_reference: null,
            reason: "approval apr-1 is GRANTED; no consumption to link" },
          { state: "LEDGER_UNCONFIGURED", appended: false, approval_id: "apr-2", instance_id: "i1", task_id: "t2",
            linkage_digest: null, linkage: null, audit_reference: null,
            reason: "no control-plane audit ledger is configured" },
        ]),
        "/api/v2/review/runs/i1/events": EVENTS,
      },
    });
    renderStudio(<App />, "/studio/review/i1");
    const list = await screen.findByRole("list", { name: /receipt linkages/i });
    const notYet = within(list).getByRole("note", { name: /linkage not yet/i });
    expect(notYet).toHaveTextContent(/round trip is not complete/i);
    expect(notYet).toHaveTextContent(/GRANTED; no consumption/);
    expect(notYet).toHaveTextContent(/Nothing is written until it is/i);
    const unconfigured = within(list).getByRole("note", { name: /linkage ledger unconfigured/i });
    expect(unconfigured).toHaveTextContent(/No audit ledger configured/i);
    expect(unconfigured).toHaveTextContent(/the decision stands/i);
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByText(/no linkage to show/i)).toBeNull();
  });

  it("says plainly when the review service reports no decided approval", async () => {
    installV2FetchMock({
      results: { "/api/v2/review/runs/i1": withLinkages([]), "/api/v2/review/runs/i1/events": EVENTS },
    });
    renderStudio(<App />, "/studio/review/i1");
    expect(await screen.findByText(/no decided approval for this instance/i)).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: /receipt linkages/i })).toBeNull();
  });

  it("reads an approval and its event chain on request", async () => {
    installV2FetchMock({
      results: {
        "/api/v2/review/runs/i1": RUN,
        "/api/v2/review/runs/i1/events": EVENTS,
        "/api/v2/review/approvals/apr-1": {
          available: true,
          result: { approval_id: "apr-1", state_at: "PENDING", events: [{ event_type: "REQUESTED" }] },
        },
      },
    });
    renderStudio(<App />, "/studio/review/i1");
    await userEvent.click(await screen.findByRole("button", { name: /apr-1 · PENDING/ }));
    await waitFor(() => expect(screen.getByText(/approval record and event chain/i)).toBeInTheDocument());
    expect(screen.getByText(/"REQUESTED"/)).toBeInTheDocument();
  });
});
