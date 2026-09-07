/**
 * The Ugence Authority Plane — step 3 of ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md §11.
 *
 * A read-only shell over the four AP-5 reads the governed runtime worker serves. This
 * is the administrators' surface, separate from the Governance Studio (AP-2), and at
 * this step it can look and not touch: the four AP-3 writes wait on the identity gate,
 * and this app's client cannot name them.
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
              Administrators&rsquo; surface · reads only at this step · over the governed runtime worker
            </p>
          </div>
          <span className="rounded border border-neutral-300 px-2 py-0.5 font-mono text-[11px]">
            AP-5 READS_FIRST
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
          <span className="font-semibold">Reads only.</span> Loading a grant, revoking one, activating a constitution
          and issuing a record are the plane&rsquo;s writes, and they are not served until the identity adapter is
          validated against a real issuer and every write carries an issuer-authenticated subject (AP-3). Nothing
          on this surface authorizes, clears or executes anything, at any step (AP-4).
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
        provisioned
      </footer>
    </div>
  );
}
