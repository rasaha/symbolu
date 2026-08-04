// Fallback Explorer (§20, §21). Every role's fallback coverage or gap is explicit;
// coverage summary counts API-returned states only.
import { useParams } from "react-router-dom";
import { usePlan } from "@/hooks/queries";
import { PlanningNote } from "@/components/MaturityBanner";
import { Card, Field, Fingerprint, Section, StatusPill } from "@/design-system/primitives";
import { fallbackState } from "@/lib/domain-p3d";
import { LoadingState, QueryError, EmptyState } from "@/design-system/states";
import type { FallbackPlan } from "@/api/types-p3d";

export function FallbackScreen() {
  const { scenarioId } = useParams<{ scenarioId: string }>();
  const plan = usePlan(scenarioId);

  if (plan.isLoading) return <LoadingState label="Loading fallbacks…" />;
  if (plan.error) return <QueryError error={plan.error} />;
  const plans = plan.data?.agent_team_plan.role_fallback_plans ?? [];
  if (plans.length === 0)
    return (
      <div className="space-y-3">
        <PlanningNote />
        <EmptyState title="No fallback plans" detail="This scenario produced no fallback plans (e.g. an infeasible team)." />
      </div>
    );

  const withPrimary = plans.length;
  const withFallback = plans.filter((p) => p.candidates.length > 0).length;
  const noFallback = plans.filter((p) => p.fallback_state === "NO_FALLBACK_AVAILABLE").length;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-lg font-semibold text-ink-0">Fallbacks</h1>
      </header>
      <PlanningNote />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4" data-testid="fallback-summary">
        <Metric label="Roles with primaries" value={withPrimary} />
        <Metric label="Roles with ≥1 fallback" value={withFallback} />
        <Metric label="Roles with no fallback" value={noFallback} tone={noFallback ? "ineligible" : undefined} />
        <Metric label="Fallback candidates" value={plans.reduce((n, p) => n + p.candidates.length, 0)} />
      </div>

      <div className="space-y-3">
        {plans.map((p) => (
          <FallbackCard key={p.role_id} p={p} />
        ))}
      </div>
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <Card className="p-3">
      <div className={"text-2xl font-semibold " + (tone === "ineligible" ? "text-state-ineligible" : "text-ink-0")}>{value}</div>
      <div className="mt-1 text-xs text-ink-2">{label}</div>
    </Card>
  );
}

function FallbackCard({ p }: { p: FallbackPlan }) {
  return (
    <Card className="p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-ink-0">{p.role_id}</h3>
          <span className="text-[11px] text-ink-3">primary {p.primary_agent_id} · v{p.primary_agent_version}</span>
        </div>
        <StatusPill descriptor={fallbackState(p.fallback_state)} title={`fallback ${p.fallback_state}`} />
      </div>
      {p.candidates.length === 0 ? (
        <p className="rounded border border-state-ineligible/30 bg-state-ineligible/10 p-2 text-xs text-ink-1">
          This role has no independent fallback under the pinned registry and policies.
        </p>
      ) : (
        <Section title="Ordered fallback candidates" count={p.candidates.length}>
          <ol className="space-y-1 text-xs">
            {p.candidates.map((c) => (
              <li key={`${c.agent_id}@${c.agent_version}`} className="flex items-center justify-between gap-2 rounded border border-surface-border/60 px-2 py-1">
                <span>
                  <span className="text-ink-3">#{c.fallback_order}</span>{" "}
                  <span className="text-ink-1">{c.agent_id}</span>{" "}
                  <span className="text-ink-3">v{c.agent_version}</span>
                </span>
                <span className="text-ink-2">{c.selection_reason || `rank ${c.rank}`}</span>
              </li>
            ))}
          </ol>
        </Section>
      )}
      <dl><Field label="Fallback fingerprint"><Fingerprint value={p.plan_fingerprint} label="fallback" /></Field></dl>
    </Card>
  );
}
