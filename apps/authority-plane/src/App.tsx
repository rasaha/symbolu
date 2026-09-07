/**
 * The Ugence Authority Plane — steps 2 and 3 of ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md
 * §11, and §16 for the two gated writes.
 *
 * The administrators' surface, separate from the Governance Studio (AP-2). It reads the
 * four AP-5 reads the governed runtime worker serves and, since AW-1, loads and revokes
 * role grants behind the identity gate: a write is sent only with the issuer token the
 * operator presents for this session (AW-3) and recorded only for a human subject of the
 * worker's tenant its adapter proved (AW-5). The plane's other two writes, activate and
 * issue, act on stores the worker does not compose and cannot be named by this app
 * (AW-2). Nothing on this surface authorizes, clears or executes anything (AP-4).
 */
import { useState } from "react";
import { ProofPanel } from "./components/Proof";
import { GrantsView } from "./views/GrantsView";
import { HoldersView } from "./views/HoldersView";
import { CommitteeView } from "./views/CommitteeView";
import { EventsView } from "./views/EventsView";
import { LoadGrantView } from "./views/LoadGrantView";

type Tab = "grants" | "holders" | "committee" | "events" | "load";

const TABS: { id: Tab; label: string }[] = [
  { id: "grants", label: "Grants" },
  { id: "holders", label: "Holders" },
  { id: "committee", label: "Committee" },
  { id: "events", label: "Grant events" },
  { id: "load", label: "Load grant" },
];

export function App() {
  const [tab, setTab] = useState<Tab>("grants");
  const [eventsGrantId, setEventsGrantId] = useState("");
  // The presented issuer token: memory only, this session only, never stored (AW-3).
  const [proof, setProof] = useState("");

  function goToEvents(grantId: string) {
    setEventsGrantId(grantId);
    setTab("events");
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-neutral-300">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <div>
            <h1 className="text-sm font-semibold">Ugence Authority Plane</h1>
            <p className="text-[11px] text-neutral-700">
              Administrators&rsquo; surface · reads, and the two grant writes behind the identity gate · over the
              governed runtime worker
            </p>
          </div>
          <span className="rounded border border-neutral-300 px-2 py-0.5 font-mono text-[11px]">
            AP-5 READS_FIRST · AW-1 GATED_WRITES
          </span>
        </div>
        <nav aria-label="authority plane screens" className="mx-auto flex max-w-6xl gap-1 px-4 pb-2">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              aria-current={tab === t.id ? "page" : undefined}
              className={
                tab === t.id
                  ? "rounded border border-action bg-action px-3 py-1.5 text-[12px] font-medium text-white"
                  : "rounded border border-neutral-300 bg-white px-3 py-1.5 text-[12px] font-medium text-black hover:bg-neutral-100"
              }
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <div className="mx-auto max-w-6xl space-y-3 px-4 py-3">
        <ProofPanel proof={proof} onChange={setProof} />
        <div role="note" aria-label="what this plane can and cannot do"
             className="rounded border border-neutral-300 bg-neutral-50 px-3 py-2 text-[12px]">
          <span className="font-semibold">Reads, and two gated writes.</span> Loading a role grant and revoking one are
          recorded only for a human subject of this tenant the worker&rsquo;s identity adapter proved from the token you
          present; without one nothing is sent, and the worker records nothing as presented (AW-1, AW-5). Activating a
          constitution and issuing a record are not served until the worker composes their stores (AW-2). Nothing on
          this surface authorizes, clears or executes anything, at any step (AP-4).
        </div>
      </div>

      <main className="mx-auto max-w-6xl px-4 py-4">
        {tab === "grants" ? <GrantsView onEvents={goToEvents} proof={proof} /> : null}
        {tab === "holders" ? <HoldersView onEvents={goToEvents} proof={proof} /> : null}
        {tab === "committee" ? <CommitteeView onEvents={goToEvents} /> : null}
        {tab === "events" ? <EventsView initialGrantId={eventsGrantId} proof={proof} /> : null}
        {tab === "load" ? <LoadGrantView proof={proof} onEvents={goToEvents} /> : null}
      </main>

      <footer className="border-t border-neutral-300 px-4 py-3 text-center text-[11px] text-neutral-700">
        REFERENCE_GRADE_SHADOW_ONLY · a grant shown here is what an administrator loaded · the identity adapter is
        validated against an in-process issuer only · no identity provider is provisioned
      </footer>
    </div>
  );
}
