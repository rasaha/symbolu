// Mandatory maturity language (§21). Rendered persistently in the app chrome —
// never hidden behind an About page. Distinguishes eligibility from selection,
// assignment, authorization and execution.
import { ShieldAlert } from "lucide-react";

const LABELS = [
  "Synthetic demonstration data",
  "Deterministic planning only",
  "No live agent execution",
  "No permission granting",
  "No business-action authorization",
  "Not pilot validated",
  "Not production certified",
];

export function MaturityBanner() {
  return (
    <div className="border-b border-surface-border bg-surface-2/70 px-4 py-2 text-xs text-ink-2" role="note">
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-3 gap-y-1">
        <span className="inline-flex items-center gap-1.5 font-semibold text-ink-1">
          <ShieldAlert className="h-3.5 w-3.5 text-state-indeterminate" aria-hidden="true" />
          Eligibility ≠ Selected ≠ Assigned ≠ Authorized ≠ Executed
        </span>
        <span className="hidden text-ink-3 sm:inline">·</span>
        <ul className="flex flex-wrap gap-x-3 gap-y-0.5">
          {LABELS.map((l) => (
            <li key={l} className="whitespace-nowrap">
              {l}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export function EligibilityMeaningNote() {
  return (
    <p className="rounded border border-surface-border bg-surface-2/50 p-3 text-xs text-ink-2">
      <strong className="text-ink-1">Eligibility</strong> means an agent remains permitted for
      consideration under the pinned workflow, registry and enterprise policies. It does{" "}
      <strong className="text-ink-1">not</strong> mean the agent was selected, assigned, authorized or
      executed.
    </p>
  );
}
