// Screen 8 — Run Detail (GAS-7 HR-D). A reader.
//
// One instance as the review service renders it: the checkpoint view, the engine's
// neutral status, the execution-state journal, the open approvals with their event
// chains, and the full runtime event log including the signal rows. Everything here
// is history. A fingerprint is what was evaluated; a valid_until is when that
// evaluation lapsed. Neither is a live permission, and a pre-park clearance is never
// reused: the next evaluation is fresh.
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { GapNotice } from "./GapNotice";
import { Json, Panel, ScreenFrame } from "./ScreenFrame";
import { useReviewApproval, useReviewRun, useReviewRunEvents } from "./hooks";
import { Fingerprint } from "@/design-system/primitives";
import { LoadingState, QueryError } from "@/design-system/states";
import { isUnavailable } from "@/api/types-v2";

type Rec = Record<string, unknown>;
const rec = (v: unknown): Rec => (typeof v === "object" && v !== null ? (v as Rec) : {});
const str = (v: unknown): string => (v === null || v === undefined ? "" : String(v));

function HistoryNotice() {
  return (
    <div
      role="note"
      aria-label="shown as history"
      className="rounded border border-surface-border bg-surface-2 px-3 py-2 text-[12px] text-ink-1"
    >
      <span className="font-semibold">Shown as history.</span> A fingerprint is what was
      evaluated and a <span className="font-mono">valid_until</span> is when that evaluation
      lapsed. Neither is a live permission: a pre-park clearance is never reused, and the next
      evaluation is fresh.
    </div>
  );
}

function ParkedNotice({ status, dispositions }: { status: string; dispositions: string[] }) {
  const hold = dispositions.some((d) => d.toUpperCase() === "HOLD");
  const escalate = dispositions.some((d) => d.toUpperCase() === "ESCALATE");
  if (status === "WAITING" && hold && !escalate) {
    return (
      <div role="note" aria-label="parked on a hold" className="rounded border border-slate-300 bg-slate-50 px-3 py-2 text-[12px] text-slate-900">
        <span className="font-semibold">Parked on a HOLD.</span> This instance is not awaiting a
        human; a HOLD is released only by an upstream authority change.
      </div>
    );
  }
  if (status === "PAUSED" && escalate) {
    return (
      <div role="note" aria-label="parked on an escalate" className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-[12px] text-amber-950">
        <span className="font-semibold">Parked on an ESCALATE.</span> A human decision is
        awaited; see the open approvals below and the <Link to="/studio/review" className="underline">Review Queue</Link>.
      </div>
    );
  }
  return null;
}

/**
 * The receipt linkages the review service returns since its 0.2.0 (HE-5). Each is the
 * service's typed answer about one decided approval: APPENDED or ALREADY_APPENDED
 * carry the linkage and its control-plane audit reference; NOT_YET means the round
 * trip is not complete yet; LEDGER_UNCONFIGURED means no ledger is wired. None of
 * those is an error, and none is rendered as an empty section. Everything shown is
 * history: what was joined, and where the entry was written.
 */
function LinkagesPanel({ linkages }: { linkages: Rec[] }) {
  if (linkages.length === 0) {
    return (
      <p className="text-[12px] text-ink-2">
        The review service reports no decided approval for this instance, so there is no
        linkage to show.
      </p>
    );
  }
  return (
    <ul className="space-y-3" aria-label="receipt linkages">
      {linkages.map((l) => {
        const state = str(l.state);
        const appended = state === "APPENDED" || state === "ALREADY_APPENDED";
        const ref = rec(l.audit_reference);
        const link = rec(l.linkage);
        return (
          <li
            key={`${str(l.approval_id)}:${str(l.task_id)}`}
            className="rounded border border-surface-border bg-surface-2 p-3 text-[11px]"
            aria-label={`linkage ${str(l.approval_id)}`}
          >
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <span className="font-mono">{str(l.approval_id)}</span>
              <span className="text-ink-2">task</span>
              <span className="font-mono">{str(l.task_id)}</span>
              <span className="rounded border border-surface-border px-1.5 py-0.5 font-mono">{state}</span>
            </div>
            {appended ? (
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
                <dt className="text-ink-2">Linkage digest (history)</dt>
                <dd>
                  <Fingerprint value={str(l.linkage_digest) || null} label="linkage digest" />
                </dd>
                <dt className="text-ink-2">Audit store</dt>
                <dd className="font-mono">{str(ref.store_ref) || "—"}</dd>
                <dt className="text-ink-2">Audit entry</dt>
                <dd className="font-mono">{str(ref.entry_ref) || "—"}</dd>
                <dt className="text-ink-2">Entry digest (history)</dt>
                <dd>
                  <Fingerprint value={str(ref.entry_digest) || null} label="audit entry digest" />
                </dd>
                <dt className="text-ink-2">Recorded at</dt>
                <dd className="font-mono">{str(ref.recorded_at) || "—"}</dd>
                <dt className="text-ink-2">Proposal fingerprint (history)</dt>
                <dd>
                  <Fingerprint value={str(link.proposal_fingerprint) || null} label="proposal fingerprint" />
                </dd>
                <dt className="text-ink-2">Consumption</dt>
                <dd className="font-mono">{str(link.consumption_id) || "—"}</dd>
                <dt className="text-ink-2">Decided by</dt>
                <dd className="font-mono">
                  {str(link.decided_by) || "—"} · {str(link.decided_role) || "—"} · {str(link.decided_at) || "—"}
                </dd>
                <dt className="text-ink-2">Events (park · signal · resume)</dt>
                <dd className="font-mono">
                  {str(link.paused_event_seq) || "—"} · {str(link.signal_event_seq) || "none"} ·{" "}
                  {str(link.resumed_event_seq) || "—"}
                </dd>
                <dt className="text-ink-2">Evaluations (parked → resumed)</dt>
                <dd className="font-mono">
                  {str(link.parked_disposition) || "—"} → {str(link.resumed_disposition) || "—"}
                </dd>
              </dl>
            ) : (
              <p role="note" aria-label={`linkage ${state.toLowerCase().replace("_", " ")}`} className="text-ink-1">
                {state === "NOT_YET" ? (
                  <>
                    <span className="font-semibold">Not yet linked.</span> The review service reports
                    the round trip is not complete: {str(l.reason) || "the next evaluation has not run"}.
                    Nothing is written until it is.
                  </>
                ) : state === "LEDGER_UNCONFIGURED" ? (
                  <>
                    <span className="font-semibold">No audit ledger configured.</span> The review
                    service has no control-plane ledger to write to; the decision stands, the
                    linkage is not durably recorded.
                  </>
                ) : (
                  <>
                    <span className="font-semibold">{state}.</span> {str(l.reason)}
                  </>
                )}
              </p>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export function RunDetailScreen() {
  const { instanceId = "" } = useParams<{ instanceId: string }>();
  const run = useReviewRun(instanceId);
  const events = useReviewRunEvents(instanceId);
  const [approvalId, setApprovalId] = useState<string | null>(null);
  const approval = useReviewApproval(approvalId);

  return (
    <ScreenFrame
      title="Run Detail"
      subtitle={`Instance ${instanceId}, as the governed review service renders it.`}
      neverDoes="Reads only. This screen resumes, releases, continues and signals nothing; fingerprints and valid_until values are history, never a live permission."
    >
      <p className="text-[11px]">
        <Link to="/studio/review" className="underline">← Review Queue</Link>
      </p>

      <Panel title="Instance">
        {run.isLoading ? <LoadingState label="Reading the instance…" /> : null}
        {run.error ? <QueryError error={run.error} /> : null}
        {run.data ? (
          isUnavailable(run.data) ? (
            <GapNotice gap={run.data} />
          ) : (run.data as { found?: boolean }).found === false ? (
            <p className="text-[12px] text-ink-2" role="status">
              The review service is reachable and has no record of instance{" "}
              <span className="font-mono">{instanceId}</span>.
            </p>
          ) : (
            (() => {
              const result = rec((run.data as { result?: unknown }).result);
              const instance = rec(result.instance);
              const tasks = rec(instance.tasks);
              const states = rec(instance.execution_states);
              const dispositions = Object.values(states).map((s) => str(rec(s).governance_disposition));
              const status = str(instance.status);
              const openApprovals = Array.isArray(result.open_approvals) ? (result.open_approvals as Rec[]) : [];
              return (
                <div className="space-y-3">
                  <HistoryNotice />
                  <ParkedNotice status={status} dispositions={dispositions} />
                  <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[11px]">
                    <dt className="text-ink-2">Workflow</dt>
                    <dd className="font-mono">{str(instance.workflow_id)}</dd>
                    <dt className="text-ink-2">Status</dt>
                    <dd className="font-mono">{status}</dd>
                    <dt className="text-ink-2">Correlation id</dt>
                    <dd className="font-mono">{str(instance.correlation_id) || "—"}</dd>
                    <dt className="text-ink-2">Engine</dt>
                    <dd className="font-mono">{JSON.stringify(result.engine ?? {})}</dd>
                    <dt className="text-ink-2">Identity proof</dt>
                    <dd className="font-mono">{str(result.identity_proof)}</dd>
                  </dl>

                  <table className="w-full text-[11px]" aria-label="tasks and execution states">
                    <thead>
                      <tr className="text-left text-ink-2">
                        <th scope="col" className="py-1 pr-2">Task</th>
                        <th scope="col" className="py-1 pr-2">Status</th>
                        <th scope="col" className="py-1 pr-2">Attempts</th>
                        <th scope="col" className="py-1 pr-2">Disposition</th>
                        <th scope="col" className="py-1 pr-2">Operation</th>
                        <th scope="col" className="py-1 pr-2">Fingerprint (history)</th>
                        <th scope="col" className="py-1 pr-2">valid_until (history)</th>
                        <th scope="col" className="py-1">Evaluation ref</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(tasks).map(([taskId, t]) => {
                        const task = rec(t);
                        const state = rec(states[taskId]);
                        return (
                          <tr key={taskId} className="border-t border-surface-border">
                            <td className="py-1 pr-2 font-mono">{taskId}</td>
                            <td className="py-1 pr-2 font-mono">{str(task.status)}</td>
                            <td className="py-1 pr-2">{str(task.attempts)}</td>
                            <td className="py-1 pr-2 font-mono">{str(state.governance_disposition) || "—"}</td>
                            <td className="py-1 pr-2 font-mono">
                              {state.provider_id ? `${str(state.provider_id)}.${str(state.operation)}` : "—"}
                            </td>
                            <td className="py-1 pr-2">
                              <Fingerprint value={str(state.proposal_fingerprint) || null} label="proposal fingerprint" />
                            </td>
                            <td className="py-1 pr-2 font-mono">{str(state.valid_until) || "—"}</td>
                            <td className="py-1 font-mono">{str(state.evaluation_reference) || "—"}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>

                  <div>
                    <div className="mb-1 text-[11px] font-medium text-ink-2">Open approvals</div>
                    {openApprovals.length === 0 ? (
                      <p className="text-[12px] text-ink-2">No open approval is bound to this instance.</p>
                    ) : (
                      <ul className="flex flex-wrap gap-2">
                        {openApprovals.map((a) => (
                          <li key={str(a.approval_id)}>
                            <button
                              type="button"
                              onClick={() => setApprovalId(str(a.approval_id))}
                              className="rounded border border-surface-border bg-surface-2 px-2 py-1 font-mono text-[11px] text-ink-0 hover:bg-surface-3"
                            >
                              {str(a.approval_id)} · {str(a.state_at)}
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              );
            })()
          )
        ) : null}
      </Panel>

      {run.data && !isUnavailable(run.data) && (run.data as { found?: boolean }).found !== false ? (
        <Panel title="Receipt linkages">
          <p className="mb-2 text-[11px] text-ink-3">
            Shown as history. A linkage joins the proposal fingerprint, the approval, its
            consumption, the park, the decision signal, the resume and the two evaluations; the
            audit reference says where the review service wrote it. This screen writes nothing.
          </p>
          <LinkagesPanel
            linkages={
              (() => {
                const result = rec((run.data as { result?: unknown }).result);
                return Array.isArray(result.linkages) ? (result.linkages as Rec[]) : [];
              })()
            }
          />
        </Panel>
      ) : null}

      {approvalId ? (
        <Panel title={`Approval ${approvalId}`}>
          {approval.isLoading ? <LoadingState label="Reading the approval…" /> : null}
          {approval.error ? <QueryError error={approval.error} /> : null}
          {approval.data ? (
            isUnavailable(approval.data) ? (
              <GapNotice gap={approval.data} />
            ) : (
              <Json value={(approval.data as { result?: unknown }).result} label="Approval record and event chain" />
            )
          ) : null}
        </Panel>
      ) : null}

      <Panel title="Runtime events">
        {events.isLoading ? <LoadingState label="Reading the event log…" /> : null}
        {events.error ? <QueryError error={events.error} /> : null}
        {events.data ? (
          isUnavailable(events.data) ? (
            <GapNotice gap={events.data} />
          ) : (
            (() => {
              const result = rec((events.data as { result?: unknown }).result);
              const list = Array.isArray(result.events) ? (result.events as Rec[]) : [];
              if (list.length === 0) {
                return <p className="text-[12px] text-ink-2">No events recorded for this instance.</p>;
              }
              return (
                <table className="w-full text-[11px]" aria-label="runtime events">
                  <thead>
                    <tr className="text-left text-ink-2">
                      <th scope="col" className="py-1 pr-2">Seq</th>
                      <th scope="col" className="py-1 pr-2">Event</th>
                      <th scope="col" className="py-1 pr-2">Attempt</th>
                      <th scope="col" className="py-1">Body</th>
                    </tr>
                  </thead>
                  <tbody>
                    {list.map((e) => (
                      <tr key={str(e.seq)} className="border-t border-surface-border align-top">
                        <td className="py-1 pr-2 font-mono">{str(e.seq)}</td>
                        <td className="py-1 pr-2 font-mono">{str(e.event_type) || str(rec(e.body).type)}</td>
                        <td className="py-1 pr-2 font-mono">{str(e.attempt_token) || "—"}</td>
                        <td className="py-1 font-mono text-ink-2">{JSON.stringify(e.body)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              );
            })()
          )
        ) : null}
      </Panel>
    </ScreenFrame>
  );
}
