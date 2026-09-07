import { useEffect, useState } from "react";
import { readGrantEvents, type EventsAnswer, type Outcome } from "@/api/client";
import { GrantTable } from "@/components/GrantTable";
import { IdentityBanner, Json, RefusalNotice, Unreachable } from "@/components/Identity";

export function EventsView({ initialGrantId }: { initialGrantId: string }) {
  const [grantId, setGrantId] = useState(initialGrantId);
  const [outcome, setOutcome] = useState<Outcome<EventsAnswer> | null>(null);
  const [busy, setBusy] = useState(false);

  async function read(id: string) {
    const trimmed = id.trim();
    if (!trimmed) return;
    setBusy(true);
    try {
      setOutcome(await readGrantEvents(trimmed));
    } finally {
      setBusy(false);
    }
  }

  // Arriving from a grant table's "Events" button reads that grant once.
  useEffect(() => {
    if (initialGrantId) {
      setGrantId(initialGrantId);
      void read(initialGrantId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialGrantId]);

  return (
    <section className="space-y-3" aria-labelledby="events-title">
      <h2 id="events-title" className="text-base font-semibold">A grant's event history</h2>
      <p className="text-[12px] text-neutral-700">
        The append-only events of one grant: it was loaded, and it may have been revoked. A grant is never edited in
        place. A grant of another tenant reads as unknown here.
      </p>
      <div className="flex flex-col gap-2 sm:flex-row">
        <label htmlFor="grant-id" className="sr-only">grant id</label>
        <input id="grant-id" className="field flex-1" placeholder="grant id" value={grantId}
               onChange={(e) => setGrantId(e.target.value)} onKeyDown={(e) => e.key === "Enter" && read(grantId)} />
        <button type="button" className="btn-action" onClick={() => read(grantId)} disabled={busy || !grantId.trim()}>
          Read events
        </button>
      </div>
      {outcome?.kind === "unreachable" ? <Unreachable reason={outcome.reason} /> : null}
      {outcome?.kind === "refusal" ? <RefusalNotice status={outcome.status} refusal={outcome.refusal} /> : null}
      {outcome?.kind === "answer" ? (
        <div className="space-y-3" data-testid="events-result">
          <IdentityBanner answer={outcome.answer} />
          <GrantTable grants={[outcome.answer.grant]} label="the grant" />
          <ol aria-label="grant events" className="space-y-1 text-[12px]">
            {outcome.answer.events.map((e) => (
              <li key={String(e.event_id ?? e.sequence)} className="rounded border border-neutral-200 px-2 py-1">
                <span className="font-mono">{e.sequence}</span> · <span className="font-semibold">{e.event_type}</span> ·{" "}
                <span className="font-mono">{String(e.occurred_at ?? "")}</span>
                {e.actor ? <> · by <span className="font-mono">{String(e.actor)}</span></> : null}
                {e.detail ? <> · {String(e.detail)}</> : null}
              </li>
            ))}
          </ol>
          <Json value={outcome.answer} label="the worker's answer, verbatim" />
        </div>
      ) : null}
    </section>
  );
}
