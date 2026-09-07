import { useState } from "react";
import { readCommittee, type CommitteeAnswer, type Outcome } from "@/api/client";
import { GrantTable } from "@/components/GrantTable";
import { IdentityBanner, Json, RefusalNotice, Unreachable } from "@/components/Identity";

export function CommitteeView({ onEvents }: { onEvents: (grantId: string) => void }) {
  const [committeeId, setCommitteeId] = useState("");
  const [role, setRole] = useState("");
  const [scope, setScope] = useState("");
  const [outcome, setOutcome] = useState<Outcome<CommitteeAnswer> | null>(null);
  const [busy, setBusy] = useState(false);
  const ready = committeeId.trim() !== "" && role.trim() !== "" && scope.trim() !== "";

  async function read() {
    if (!ready) return;
    setBusy(true);
    try {
      setOutcome(await readCommittee(committeeId.trim(), role.trim(), scope.trim()));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-3" aria-labelledby="committee-title">
      <h2 id="committee-title" className="text-base font-semibold">Committee report</h2>
      <p className="text-[12px] text-neutral-700">
        One committee's members holding one role in one scope, counted against the committee's quorum at the
        worker's clock. A member whose grant lapsed or was revoked is not counted.
      </p>
      <div className="flex flex-col gap-2 sm:flex-row">
        <label htmlFor="committee-id" className="sr-only">committee id</label>
        <input id="committee-id" className="field flex-1" placeholder="committee id" value={committeeId}
               onChange={(e) => setCommitteeId(e.target.value)} />
        <label htmlFor="committee-role" className="sr-only">role</label>
        <input id="committee-role" className="field flex-1" placeholder="role" value={role} onChange={(e) => setRole(e.target.value)} />
        <label htmlFor="committee-scope" className="sr-only">scope</label>
        <input id="committee-scope" className="field flex-1" placeholder="scope" value={scope}
               onChange={(e) => setScope(e.target.value)} onKeyDown={(e) => e.key === "Enter" && read()} />
        <button type="button" className="btn-action" onClick={read} disabled={busy || !ready}>
          Read committee
        </button>
      </div>
      {outcome?.kind === "unreachable" ? <Unreachable reason={outcome.reason} /> : null}
      {outcome?.kind === "refusal" ? <RefusalNotice status={outcome.status} refusal={outcome.refusal} /> : null}
      {outcome?.kind === "answer" ? (
        <div className="space-y-3" data-testid="committee-result">
          <IdentityBanner answer={outcome.answer} />
          <p role="status" aria-label="quorum" className="text-[12px]">
            <span className="font-mono">{outcome.answer.report.committee.principal_id}</span> · quorum{" "}
            {outcome.answer.report.quorum} · members counted {outcome.answer.report.member_count} ·{" "}
            <span className={outcome.answer.report.quorum_met_at_as_of ? "text-emerald-800" : "text-red-800"}>
              quorum {outcome.answer.report.quorum_met_at_as_of ? "met" : "not met"} at this instant
            </span>
          </p>
          <GrantTable grants={outcome.answer.report.members} label="committee members" onEvents={onEvents} />
          <Json value={outcome.answer} label="the worker's answer, verbatim" />
        </div>
      ) : null}
    </section>
  );
}
