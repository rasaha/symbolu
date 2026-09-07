import { useState } from "react";
import { listGrants, type GrantsAnswer, type Outcome } from "@/api/client";
import { GrantTable } from "@/components/GrantTable";
import { IdentityBanner, Json, RefusalNotice, Unreachable } from "@/components/Identity";

export function GrantsView({ onEvents }: { onEvents: (grantId: string) => void }) {
  const [principalId, setPrincipalId] = useState("");
  const [outcome, setOutcome] = useState<Outcome<GrantsAnswer> | null>(null);
  const [busy, setBusy] = useState(false);

  async function read() {
    const id = principalId.trim();
    if (!id) return;
    setBusy(true);
    try {
      setOutcome(await listGrants(id));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-3" aria-labelledby="grants-title">
      <h2 id="grants-title" className="text-base font-semibold">Grants held by a principal</h2>
      <p className="text-[12px] text-neutral-700">
        The role grants one principal holds in this worker's tenant, active at the worker's clock. The principal id is
        the issuer-qualified subject the identity adapter presents, percent-encoded.
      </p>
      <div className="flex flex-col gap-2 sm:flex-row">
        <label htmlFor="principal-id" className="sr-only">principal id</label>
        <input
          id="principal-id"
          className="field flex-1"
          placeholder="principal id"
          value={principalId}
          onChange={(e) => setPrincipalId(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && read()}
        />
        <button type="button" className="btn-action" onClick={read} disabled={busy || !principalId.trim()}>
          Read grants
        </button>
      </div>
      {outcome?.kind === "unreachable" ? <Unreachable reason={outcome.reason} /> : null}
      {outcome?.kind === "refusal" ? <RefusalNotice status={outcome.status} refusal={outcome.refusal} /> : null}
      {outcome?.kind === "answer" ? (
        <div className="space-y-3" data-testid="grants-result">
          <IdentityBanner answer={outcome.answer} />
          <p className="text-[12px]">
            <span className="font-mono">{outcome.answer.principal_id}</span> holds {outcome.answer.grant_count} active grant
            {outcome.answer.grant_count === 1 ? "" : "s"}.
          </p>
          <GrantTable grants={outcome.answer.grants} label="grants held" onEvents={onEvents} />
          <Json value={outcome.answer} label="the worker's answer, verbatim" />
        </div>
      ) : null}
    </section>
  );
}
