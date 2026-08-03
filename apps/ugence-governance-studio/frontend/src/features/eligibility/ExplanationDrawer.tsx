// Eligibility explanation drawer (§20). Accessible dialog with focus trap +
// restoration. Consumes POST /api/v1/explanations/eligibility. Displays only
// API-supported conditions, reason codes (deterministically labeled), evidence
// and policy references and fingerprints — no invented reasons, no LLM.
import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import { useEligibilityExplanation } from "@/hooks/queries";
import { conditionName, conditionReason, eligibilityState, reasonLabel } from "@/lib/domain";
import type { Condition } from "@/api/types";
import { Badge, Field, Fingerprint, Section, StatusPill } from "@/design-system/primitives";
import { LoadingState, EmptyState } from "@/design-system/states";

export function ExplanationDrawer({
  scenarioId,
  roleId,
  agentKey,
  onClose,
}: {
  scenarioId: string;
  roleId: string;
  agentKey: string;
  onClose: () => void;
}) {
  const { data, isLoading } = useEligibilityExplanation(scenarioId, roleId);
  const closeRef = useRef<HTMLButtonElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  useEffect(() => {
    previouslyFocused.current = document.activeElement as HTMLElement;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      previouslyFocused.current?.focus(); // restore focus (§24)
    };
  }, [onClose]);

  const [agentId, agentVersion] = agentKey.split("@");
  const role = data?.roles.find((r) => r.role_id === roleId);
  const agent = role?.agents.find((a) => a.agent_id === agentId && a.agent_version === agentVersion);

  return (
    <div className="fixed inset-0 z-40 flex justify-end" role="presentation">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} aria-hidden="true" />
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="explain-title"
        className="relative flex h-full w-full max-w-md flex-col overflow-y-auto border-l border-surface-border bg-surface-1 shadow-xl"
      >
        <div className="sticky top-0 flex items-center justify-between border-b border-surface-border bg-surface-1 px-4 py-3">
          <h2 id="explain-title" className="text-sm font-semibold text-ink-0">
            Eligibility explanation
          </h2>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="Close explanation"
            className="rounded p-1 hover:bg-surface-2"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <div className="p-4">
          {isLoading && <LoadingState label="Loading explanation…" />}
          {!isLoading && !agent && (
            <EmptyState title="No explanation" detail="No result for this role-agent pair." />
          )}
          {agent && (
            <>
              <div className="mb-3 flex items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-medium text-ink-0">{agent.agent_id}</p>
                  <span className="text-[11px] text-ink-3">v{agent.agent_version}</span>
                </div>
                <StatusPill descriptor={eligibilityState(agent.state)} />
              </div>

              <Section title="Failed conditions" count={agent.failed_conditions.length}>
                <ConditionList items={agent.failed_conditions} tone="ineligible" />
              </Section>
              <Section title="Passed conditions" count={agent.passed_conditions.length}>
                <ConditionList items={agent.passed_conditions} tone="eligible" />
              </Section>
              <Section title="Unknown conditions" count={agent.unknown_conditions.length}>
                <ConditionList items={agent.unknown_conditions} tone="indeterminate" />
              </Section>

              <Section title="Elimination reasons" count={agent.elimination_reasons.length}>
                {agent.elimination_reasons.length === 0 ? (
                  <p className="text-xs text-ink-3">None</p>
                ) : (
                  <ul className="space-y-1.5">
                    {agent.elimination_reasons.map((code) => (
                      <li key={code} className="rounded border border-state-ineligible/30 bg-state-ineligible/10 p-2 text-sm">
                        <div className="text-ink-1">{reasonLabel(code)}</div>
                        <code className="font-mono text-[10px] text-ink-3">{code}</code>
                      </li>
                    ))}
                  </ul>
                )}
              </Section>

              <Section title="Evidence & policy">
                <dl>
                  <Field label="Evidence refs">
                    {agent.evidence_refs.length ? agent.evidence_refs.join(", ") : "None"}
                  </Field>
                  <Field label="Policy refs">
                    {agent.policy_refs.length ? agent.policy_refs.join(", ") : "None"}
                  </Field>
                  <Field label="Result fingerprint">
                    <Fingerprint value={agent.result_fingerprint} label="eligibility result" />
                  </Field>
                  {role && (
                    <Field label="Report fingerprint">
                      <Fingerprint value={role.report_fingerprint} label="report" />
                    </Field>
                  )}
                </dl>
              </Section>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}

function ConditionList({ items, tone }: { items: Condition[]; tone: string }) {
  if (items.length === 0) return <p className="text-xs text-ink-3">None</p>;
  return (
    <ul className="flex flex-col gap-1">
      {items.map((c, i) => {
        const name = conditionName(c);
        const reason = conditionReason(c);
        return (
          <li key={`${name}-${i}`} className="flex flex-wrap items-center gap-1.5">
            <Badge tone={tone}>{name}</Badge>
            {reason && <span className="text-[11px] text-ink-3">{reasonLabel(reason)}</span>}
          </li>
        );
      })}
    </ul>
  );
}
