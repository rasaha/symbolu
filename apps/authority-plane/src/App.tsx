/**
 * The Ugence Authority Plane — step 3 of ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md §11.
 *
 * A read-only shell over the four AP-5 reads the governed runtime worker serves. This
 * is the administrators' surface, separate from the Governance Studio (AP-2). The
 * worker implements the two grant writes (§16, AW-2 to AW-5) but serves neither under
 * AP-3, which the owner confirmed as controlling on 2026-09-07 (§18, AW-1 reversed):
 * no write is served until the identity adapter is validated end to end against a
 * real enterprise issuer. Until then this app has no write control and its client
 * cannot name a write.
 */
import { useState } from "react";
import { GrantsView } from "./views/GrantsView";
import { HoldersView } from "./views/HoldersView";
import { CommitteeView } from "./views/CommitteeView";
import { EventsView } from "./views/EventsView";

type Tab = "grants" | "holders" | "committee" | "events";

const TABS: { id: Tab; label: string }[] = [
  { id: "grants", label: "Grants" },
  { id: "holders", label: "Holders" },
  { id: "committee", label: "Committee" },
  { id: "events", label: "Grant events" },
];

export function App() {
  const [tab, setTab] = useState<Tab>("grants");
  const [eventsGrantId, setEventsGrantId] = useState("");

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
              Administrators&rsquo; surface · reads only until enterprise issuer validation · over the governed
              runtime worker
            </p>
          </div>
          <span className="rounded border border-neutral-300 px-2 py-0.5 font-mono text-[11px]">
            AP-5 READS_FIRST · AP-3 IDP_VALIDATED_FIRST
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

      <div className="mx-auto max-w-6xl px-4 py-3">
        <div role="note" aria-label="what this plane cannot do yet"
             className="rounded border border-neutral-300 bg-neutral-50 px-3 py-2 text-[12px]">
          <span className="font-semibold">Reads only.</span> Loading a role grant and revoking one are implemented on
          the worker behind its identity gate, but are not served until the identity adapter has been validated end
          to end against a real enterprise issuer (AP-3); the worker&rsquo;s in-process issuer evidence is
          implementation and conformance evidence only. Activating a constitution and issuing a record act on stores
          the worker does not compose (AW-2). Nothing on this surface authorizes, clears or executes anything, at any
          step (AP-4).
        </div>
      </div>

      <main className="mx-auto max-w-6xl px-4 py-4">
        {tab === "grants" ? <GrantsView onEvents={goToEvents} /> : null}
        {tab === "holders" ? <HoldersView onEvents={goToEvents} /> : null}
        {tab === "committee" ? <CommitteeView onEvents={goToEvents} /> : null}
        {tab === "events" ? <EventsView initialGrantId={eventsGrantId} /> : null}
      </main>

      <footer className="border-t border-neutral-300 px-4 py-3 text-center text-[11px] text-neutral-700">
        REFERENCE_GRADE_SHADOW_ONLY · a grant shown here is what an administrator loaded · no identity provider is
        provisioned · no write is served before enterprise issuer validation
      </footer>
    </div>
  );
}
