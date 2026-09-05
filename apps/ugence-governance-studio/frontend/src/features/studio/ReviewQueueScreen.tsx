// Screen 7 — Review Queue (GAS-7 HR-D; owner ruling HR-1: display and transmit).
//
// The queue is what the review service lists: parked ESCALATE instances joined to
// their approval identity and proposal fingerprint. This screen renders it and relays
// a human's decision back, verbatim. It holds no approver identity, computes no
// eligibility, consumes no approval, signals nothing and resumes nothing. Whether an
// instance proceeds after a decision is settled by the governed composition at its
// next evaluation, never here.
//
// Two things are never shown as something they are not. An unreachable review
// service is a gap, not an empty queue. A HOLD is never presented as awaiting a
// human: it is released only by an upstream authority change (HR-5), so any HOLD
// entry is dropped and counted rather than listed.
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { GapNotice } from "./GapNotice";
import { ActionButton, Panel, ScreenFrame } from "./ScreenFrame";
import { useReviewQueue, useSubmitReviewDecision } from "./hooks";
import { Fingerprint } from "@/design-system/primitives";
import { LoadingState, QueryError } from "@/design-system/states";
import {
  isUnavailable,
  type ReviewDecisionOutcome,
  type ReviewQueue,
  type ReviewQueueEntry,
} from "@/api/types-v2";

type Decision = "GRANT" | "REJECT";

/** HR-5, applied a second time at the edge that renders. */
function presentable(entries: ReviewQueueEntry[]): { shown: ReviewQueueEntry[]; hold: number } {
  const shown = entries.filter((e) => String(e.governance_disposition).toUpperCase() !== "HOLD");
  return { shown, hold: entries.length - shown.length };
}

export function IdentityProofNotice({ proof }: { proof: string }) {
  return (
    <div
      role="note"
      aria-label="identity proof"
      className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-[12px] text-amber-950"
    >
      <span className="font-semibold">Approver identity:</span>{" "}
      <span className="font-mono text-[11px]">{proof || "PRESENTED_UNPROVEN"}</span>
      <p className="mt-1 leading-relaxed">
        The approver on a decision is a reference the review service listed as eligible
        and this screen relayed. No identity provider exists, so nothing here proves who
        decided; the review service records the decision as presented, not proven.
      </p>
    </div>
  );
}

export function HoldNotice({ count }: { count: number }) {
  if (count <= 0) return null;
  return (
    <div
      role="note"
      aria-label="hold instances not listed"
      className="rounded border border-slate-300 bg-slate-50 px-3 py-2 text-[12px] text-slate-900"
    >
      <span className="font-semibold">{count} parked on a HOLD, not listed.</span>{" "}
      A HOLD is released only by an upstream authority change. It is never awaiting a
      human, so it is not offered for a decision here.
    </div>
  );
}

export function ReviewQueueScreen() {
  const queue = useReviewQueue();
  const submit = useSubmitReviewDecision();
  const [selected, setSelected] = useState<ReviewQueueEntry | null>(null);
  const [approverId, setApproverId] = useState<string>("");
  const [decision, setDecision] = useState<Decision | null>(null);
  const [justification, setJustification] = useState<string>("");

  const view = useMemo(() => {
    if (!queue.data || isUnavailable(queue.data)) return null;
    const data = queue.data as ReviewQueue;
    const entries = Array.isArray(data.result?.entries) ? data.result.entries : [];
    const { shown, hold } = presentable(entries);
    return { shown, hold: hold + (Number(data.excluded_hold) || 0), proof: data.identity_proof };
  }, [queue.data]);

  const approver = selected?.eligible_approvers.find((a) => a.approver_id === approverId) ?? null;
  const canSubmit =
    selected !== null && approver !== null && decision !== null && justification.trim() !== "" && !submit.isPending;

  const choose = (entry: ReviewQueueEntry) => {
    setSelected(entry);
    setApproverId(entry.eligible_approvers[0]?.approver_id ?? "");
    setDecision(null);
    setJustification("");
    submit.reset();
  };

  return (
    <ScreenFrame
      title="Review Queue"
      subtitle="Parked ESCALATE instances awaiting a human decision, as the governed review service lists them."
      neverDoes="This screen displays and relays. It holds no approver identity, computes no eligibility, consumes no approval, signals nothing and resumes nothing."
    >
      <Panel title="Awaiting a decision">
        {queue.isLoading ? <LoadingState label="Reading the review queue…" /> : null}
        {queue.error ? <QueryError error={queue.error} /> : null}
        {queue.data && isUnavailable(queue.data) ? <GapNotice gap={queue.data} /> : null}
        {view ? (
          <div className="space-y-2">
            <IdentityProofNotice proof={view.proof} />
            <HoldNotice count={view.hold} />
            {view.shown.length === 0 ? (
              <p className="text-[12px] text-ink-2" role="status">
                The review service is reachable and lists no parked instance. That is an
                empty queue, not a failure to read it.
              </p>
            ) : (
              <table className="w-full text-[11px]" aria-label="review queue">
                <thead>
                  <tr className="text-left text-ink-2">
                    <th scope="col" className="py-1 pr-2">Instance</th>
                    <th scope="col" className="py-1 pr-2">Task</th>
                    <th scope="col" className="py-1 pr-2">Operation</th>
                    <th scope="col" className="py-1 pr-2">Fingerprint (history)</th>
                    <th scope="col" className="py-1 pr-2">Disposition</th>
                    <th scope="col" className="py-1 pr-2">Approval</th>
                    <th scope="col" className="py-1 pr-2">Role</th>
                    <th scope="col" className="py-1 pr-2">Requested</th>
                    <th scope="col" className="py-1 pr-2">Expires</th>
                    <th scope="col" className="py-1 pr-2">Eligible</th>
                    <th scope="col" className="py-1"></th>
                  </tr>
                </thead>
                <tbody>
                  {view.shown.map((e) => (
                    <tr key={e.approval_id} className="border-t border-surface-border align-top">
                      <td className="py-1 pr-2 font-mono">
                        <Link to={`/studio/review/${encodeURIComponent(e.instance_id)}`} className="underline">
                          {e.instance_id}
                        </Link>
                        {e.instance_known ? null : (
                          <span className="ml-1 text-ink-3">(no durable state)</span>
                        )}
                      </td>
                      <td className="py-1 pr-2 font-mono">{e.task_id}</td>
                      <td className="py-1 pr-2 font-mono">
                        {e.provider_id ? `${e.provider_id}.${e.operation}` : e.operation || "—"}
                      </td>
                      <td className="py-1 pr-2">
                        <Fingerprint value={e.fingerprint} label="proposal fingerprint" />
                      </td>
                      <td className="py-1 pr-2 font-mono">{e.governance_disposition || "—"}</td>
                      <td className="py-1 pr-2 font-mono">{e.approval_state}</td>
                      <td className="py-1 pr-2 font-mono">{e.required_role}</td>
                      <td className="py-1 pr-2">{e.requested_at}</td>
                      <td className="py-1 pr-2">{e.expires_at}</td>
                      <td className="py-1 pr-2">{e.eligible_approvers.length}</td>
                      <td className="py-1">
                        <ActionButton onClick={() => choose(e)}>Decide</ActionButton>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ) : null}
      </Panel>

      {selected ? (
        <Panel title={`Decision for ${selected.instance_id}:${selected.task_id}`}>
          <dl className="mb-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[11px]">
            <dt className="text-ink-2">Approval</dt>
            <dd className="font-mono">{selected.approval_id}</dd>
            <dt className="text-ink-2">Proposal fingerprint (history)</dt>
            <dd>
              <Fingerprint value={selected.fingerprint} label="proposal fingerprint" />
            </dd>
            <dt className="text-ink-2">Required role</dt>
            <dd className="font-mono">{selected.required_role}</dd>
          </dl>

          {selected.eligible_approvers.length === 0 ? (
            <p className="text-[12px] text-ink-2" role="status">
              The review service reports no eligible approver for{" "}
              <span className="font-mono">{selected.required_role}</span>. Nothing can be
              relayed until the authority directory reports one.
            </p>
          ) : (
            <div className="space-y-3">
              <div>
                <label htmlFor="presented-approver" className="mb-1 block text-[11px] text-ink-2">
                  Presented approver (as reported by the review service)
                </label>
                <select
                  id="presented-approver"
                  value={approverId}
                  onChange={(e) => setApproverId(e.target.value)}
                  className="rounded border border-surface-border bg-surface-0 px-2 py-1 font-mono text-[11px] text-ink-0"
                >
                  {selected.eligible_approvers.map((a) => (
                    <option key={a.approver_id} value={a.approver_id}>
                      {a.approver_id} · {a.role} · {a.approver_kind}
                    </option>
                  ))}
                </select>
              </div>

              <fieldset>
                <legend className="mb-1 text-[11px] text-ink-2">Decision (the human's word, relayed verbatim)</legend>
                <div className="flex gap-4 text-[12px]">
                  {(["GRANT", "REJECT"] as Decision[]).map((d) => (
                    <label key={d} className="flex items-center gap-1">
                      <input
                        type="radio"
                        name="decision"
                        value={d}
                        checked={decision === d}
                        onChange={() => setDecision(d)}
                      />
                      <span className="font-mono">{d}</span>
                    </label>
                  ))}
                </div>
              </fieldset>

              <div>
                <label htmlFor="justification" className="mb-1 block text-[11px] text-ink-2">
                  Justification (required)
                </label>
                <textarea
                  id="justification"
                  value={justification}
                  onChange={(e) => setJustification(e.target.value)}
                  rows={3}
                  className="w-full rounded border border-surface-border bg-surface-0 px-2 py-1 text-[12px] text-ink-0"
                />
              </div>

              <ActionButton
                onClick={() => {
                  if (!canSubmit || !approver || !decision) return;
                  submit.mutate({
                    approval_id: selected.approval_id,
                    decision,
                    presented_approver: approver,
                    justification,
                  });
                }}
                disabled={!canSubmit}
              >
                Submit decision
              </ActionButton>
              <p className="text-[11px] text-ink-3">
                Submitting relays the decision to the review service exactly as entered. The
                review service records it and re-arms the instance; whether it proceeds is
                settled by the governed composition at its next evaluation, not by this screen.
              </p>
            </div>
          )}

          {submit.data ? (
            isUnavailable(submit.data) ? (
              <div className="mt-3">
                <GapNotice gap={submit.data} />
              </div>
            ) : (
              <DecisionAnswer outcome={(submit.data as { result?: ReviewDecisionOutcome }).result} />
            )
          ) : null}
          {submit.error ? <QueryError error={submit.error} /> : null}
        </Panel>
      ) : null}
    </ScreenFrame>
  );
}

function DecisionAnswer({ outcome }: { outcome: ReviewDecisionOutcome | undefined }) {
  if (!outcome) return null;
  const recorded = Boolean(outcome.recorded);
  return (
    <div
      role="status"
      aria-label="review service answer"
      className={`mt-3 rounded border px-3 py-2 text-[12px] ${
        recorded ? "border-surface-border bg-surface-2 text-ink-1" : "border-amber-300 bg-amber-50 text-amber-950"
      }`}
    >
      <div className="font-semibold">
        {recorded ? "Recorded by the review service" : "Refused by the review service"}:{" "}
        <span className="font-mono text-[11px]">{outcome.result}</span>
      </div>
      {outcome.reason ? <p className="mt-1">{outcome.reason}</p> : null}
      <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 text-[11px]">
        <dt className="text-ink-2">Signal delivered</dt>
        <dd className="font-mono">{String(Boolean(outcome.signal_delivered))}</dd>
        <dt className="text-ink-2">Bounded resume delivered</dt>
        <dd className="font-mono">
          {String(Boolean(outcome.resume_delivered))}
          {outcome.resume_skipped_reason ? ` — ${outcome.resume_skipped_reason}` : ""}
        </dd>
        <dt className="text-ink-2">Identity proof</dt>
        <dd className="font-mono">{outcome.identity_proof}</dd>
      </dl>
    </div>
  );
}
