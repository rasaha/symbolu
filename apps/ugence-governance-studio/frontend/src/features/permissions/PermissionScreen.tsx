// Permission Proposal Explorer (§18, §19). Composition-time proposals with
// categorization and feasibility. Proposals are planning artifacts — never
// described as granted, provisioned, active or authorized.
import { useParams } from "react-router-dom";
import { usePlan } from "@/hooks/queries";
import { PlanningNote } from "@/components/MaturityBanner";
import { Badge, Card, Field, Fingerprint, Section } from "@/design-system/primitives";
import { permissionCategory } from "@/lib/domain-p3d";
import { LoadingState, QueryError, EmptyState } from "@/design-system/states";
import type { PermissionProposal } from "@/api/types-p3d";

export function PermissionScreen() {
  const { scenarioId } = useParams<{ scenarioId: string }>();
  const plan = usePlan(scenarioId);

  if (plan.isLoading) return <LoadingState label="Loading permission proposals…" />;
  if (plan.error) return <QueryError error={plan.error} />;
  const proposals = plan.data?.agent_team_plan.permission_bound_proposals ?? [];
  if (proposals.length === 0)
    return (
      <div className="space-y-3">
        <PlanningNote />
        <EmptyState title="No permission proposals" detail="No assignment produced a permission-bound proposal (e.g. an infeasible plan)." />
      </div>
    );

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-lg font-semibold text-ink-0">Permission proposals</h1>
      </header>
      <PlanningNote />
      <p className="rounded border border-surface-border bg-surface-2/50 p-3 text-xs text-ink-2" data-testid="proposal-notice">
        Permission proposals are planning artifacts. They do not grant, provision or activate
        permissions, and they are not authorizations.
      </p>

      <div className="grid gap-4 lg:grid-cols-2">
        {proposals.map((p) => (
          <ProposalCard key={`${p.role_id}:${p.agent_id}`} p={p} />
        ))}
      </div>
    </div>
  );
}

function ProposalCard({ p }: { p: PermissionProposal }) {
  return (
    <Card className="p-4">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-ink-0">{p.role_id}</h3>
          <span className="text-[11px] text-ink-3">{p.agent_id} · v{p.agent_version}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Badge tone={p.feasible ? "eligible" : "ineligible"}>{p.feasible ? "Feasible" : "Infeasible"}</Badge>
          {p.requires_human_review && <Badge tone="review">Human review</Badge>}
        </div>
      </div>

      <Section title="Proposed permissions (least-privilege)">
        {p.proposed_permissions.length === 0 ? (
          <p className="text-xs text-ink-3">None</p>
        ) : (
          <ul className="flex flex-wrap gap-1.5">
            {p.proposed_permissions.map((perm) => (
              <li key={perm}><Badge tone="governance">{perm}</Badge></li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="Categorized" count={p.categorized.length}>
        <ul className="space-y-1">
          {p.categorized.map((c, i) => (
            <li key={`${c.permission}-${i}`} className="flex items-center justify-between gap-2 rounded border border-surface-border/60 px-2 py-1 text-xs">
              <span className="text-ink-1">{c.permission}</span>
              <Badge tone={permissionCategory(c.category).tone}>{permissionCategory(c.category).label}</Badge>
            </li>
          ))}
        </ul>
      </Section>

      <dl>
        <Field label="Authority scope">{p.proposed_authority_scope || "—"}</Field>
        {!p.feasible && <Field label="Infeasible reasons">{p.infeasible_reasons.join(", ") || "—"}</Field>}
        <Field label="Notice">{p.notice || "planning proposal only"}</Field>
        <Field label="Proposal fingerprint"><Fingerprint value={p.proposal_fingerprint} label="proposal" /></Field>
      </dl>
    </Card>
  );
}
