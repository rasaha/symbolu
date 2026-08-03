// Plan Comparison Explorer (§23). Diffs two deterministically-produced plans from
// the same scenario contract using the API diff — no browser-side semantic diff.
import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useCompare, useRegistry } from "@/hooks/queries";
import { PlanningNote } from "@/components/MaturityBanner";
import { Card, Field, Fingerprint, Section } from "@/design-system/primitives";
import { LoadingState, QueryError } from "@/design-system/states";
import type { PlanSource } from "@/api/client";
import type { AgentProfile } from "@/api/types";

type RightMode = "identical" | "forbid_provider";

export function CompareScreen() {
  const { scenarioId } = useParams<{ scenarioId: string }>();
  const registry = useRegistry(scenarioId);
  const [mode, setMode] = useState<RightMode>("forbid_provider");

  const providers = useMemo(
    () => [...new Set((registry.data?.registry_snapshot.agent_profiles ?? []).map((p: AgentProfile) => p.provider_id))].sort(),
    [registry.data],
  );
  const [provider, setProvider] = useState<string>("");
  const effProvider = provider || providers[0] || "anthropic";

  const left: PlanSource | null = scenarioId ? { scenario_id: scenarioId } : null;
  const right: PlanSource | null = scenarioId
    ? mode === "identical"
      ? { scenario_id: scenarioId }
      : { scenario_id: scenarioId, perturbation: { operation: "FORBID_PROVIDER", params: { provider: effProvider } } }
    : null;

  const compare = useCompare(left, right);

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-lg font-semibold text-ink-0">Plan comparison</h1>
      </header>
      <PlanningNote />

      <Card className="flex flex-wrap items-end gap-3 p-3">
        <div className="flex flex-col gap-1">
          <label htmlFor="cmp-mode" className="text-[11px] text-ink-3">Right-hand plan</label>
          <select id="cmp-mode" value={mode} onChange={(e) => setMode(e.target.value as RightMode)} className="rounded border border-surface-border bg-surface-0 px-2 py-1 text-sm text-ink-1">
            <option value="identical">Identical baseline (control)</option>
            <option value="forbid_provider">Baseline with a provider forbidden</option>
          </select>
        </div>
        {mode === "forbid_provider" && (
          <div className="flex flex-col gap-1">
            <label htmlFor="cmp-provider" className="text-[11px] text-ink-3">Forbidden provider</label>
            <select id="cmp-provider" value={effProvider} onChange={(e) => setProvider(e.target.value)} className="rounded border border-surface-border bg-surface-0 px-2 py-1 text-sm text-ink-1">
              {providers.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
        )}
        <span className="ml-auto text-[11px] text-ink-3">Both plans are produced deterministically by the API; the diff is API-computed.</span>
      </Card>

      {compare.isLoading && <LoadingState label="Comparing plans…" />}
      {compare.error && <QueryError error={compare.error} />}
      {compare.data && <DiffView data={compare.data} />}
    </div>
  );
}

function DiffView({ data }: { data: import("@/api/types-p3d").CompareResult }) {
  const d = data.diff;
  const groups: { label: string; items: unknown[] }[] = [
    { label: "Assignment changes", items: d.assignment_changes },
    { label: "Constraint changes", items: d.constraint_changes },
    { label: "Permission changes", items: d.permission_changes },
    { label: "Fallback changes", items: d.fallback_changes },
    { label: "Policy digest changes", items: d.policy_digest_changes },
  ];
  const identical = groups.every((g) => g.items.length === 0) && !d.snapshot_changed;
  return (
    <Card className="p-4" data-testid="plan-diff">
      <dl>
        <Field label="Same workflow">{d.same_workflow ? "Yes" : "No"}</Field>
        <Field label="Plan A fingerprint"><Fingerprint value={d.plan_a_fingerprint} label="plan A" /></Field>
        <Field label="Plan B fingerprint"><Fingerprint value={d.plan_b_fingerprint} label="plan B" /></Field>
        <Field label="Registry snapshot changed">{d.snapshot_changed ? "Yes" : "No"}</Field>
      </dl>
      {identical ? (
        <p className="mt-2 rounded border border-state-eligible/30 bg-state-eligible/10 p-2 text-sm text-ink-1">
          The two plans are identical — no assignment, constraint, permission, fallback or policy change.
        </p>
      ) : (
        <div className="mt-2 space-y-2">
          {groups.map((g) => (
            <Section key={g.label} title={g.label} count={g.items.length}>
              {g.items.length === 0 ? (
                <p className="text-xs text-ink-3">Unchanged</p>
              ) : (
                <ul className="space-y-1 text-xs">
                  {g.items.map((it, i) => (
                    <li key={i} className="rounded border border-surface-border/60 bg-surface-2/40 px-2 py-1 font-mono text-[11px] text-ink-2">
                      {JSON.stringify(it)}
                    </li>
                  ))}
                </ul>
              )}
            </Section>
          ))}
        </div>
      )}
    </Card>
  );
}
