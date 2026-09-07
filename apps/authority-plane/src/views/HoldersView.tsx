import { useState } from "react";
import { listHolders, type HoldersAnswer, type Outcome } from "@/api/client";
import { GrantTable } from "@/components/GrantTable";
import { IdentityBanner, Json, RefusalNotice, Unreachable } from "@/components/Identity";

export function HoldersView({ onEvents }: { onEvents: (grantId: string) => void }) {
  const [role, setRole] = useState("");
  const [scope, setScope] = useState("");
  const [outcome, setOutcome] = useState<Outcome<HoldersAnswer> | null>(null);
  const [busy, setBusy] = useState(false);
  const ready = role.trim() !== "" && scope.trim() !== "";

  async function read() {
    if (!ready) return;
    setBusy(true);
    try {
      setOutcome(await listHolders(role.trim(), scope.trim()));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-3" aria-labelledby="holders-title">
      <h2 id="holders-title" className="text-base font-semibold">Holders of a role in a scope</h2>
      <p className="text-[12px] text-neutral-700">
        Every principal of this tenant holding one role in one scope at the worker's clock, committees included.
      </p>
      <div className="flex flex-col gap-2 sm:flex-row">
        <label htmlFor="role" className="sr-only">role</label>
        <input id="role" className="field flex-1" placeholder="role" value={role} onChange={(e) => setRole(e.target.value)} />
        <label htmlFor="scope" className="sr-only">scope</label>
        <input id="scope" className="field flex-1" placeholder="scope" value={scope} onChange={(e) => setScope(e.target.value)}
               onKeyDown={(e) => e.key === "Enter" && read()} />
        <button type="button" className="btn-action" onClick={read} disabled={busy || !ready}>
          Read holders
        </button>
      </div>
      {outcome?.kind === "unreachable" ? <Unreachable reason={outcome.reason} /> : null}
      {outcome?.kind === "refusal" ? <RefusalNotice status={outcome.status} refusal={outcome.refusal} /> : null}
      {outcome?.kind === "answer" ? (
        <div className="space-y-3" data-testid="holders-result">
          <IdentityBanner answer={outcome.answer} />
          <p className="text-[12px]">
            {outcome.answer.holder_count} holder{outcome.answer.holder_count === 1 ? "" : "s"} of{" "}
            <span className="font-mono">{outcome.answer.role}</span> in <span className="font-mono">{outcome.answer.scope}</span>.
          </p>
          <GrantTable grants={outcome.answer.holders} label="holders" onEvents={onEvents} />
          <Json value={outcome.answer} label="the worker's answer, verbatim" />
        </div>
      ) : null}
    </section>
  );
}
