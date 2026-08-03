// Composition Explorer (§14-§17). Plan state, assignments, team-level facts,
// non-greedy explanation, distinct selection states and an honest
// NO_FEASIBLE_TEAM view. The browser never reruns the composition search.
import { useMemo } from "react";
import { useParams } from "react-router-dom";
import { usePlan, useExplainPlan, useRanking } from "@/hooks/queries";
import { PlanningNote } from "@/components/MaturityBanner";
import { Card, Field, Fingerprint, Section, StatusPill } from "@/design-system/primitives";
import { displayOrUnresolved } from "@/lib/domain";
import { planState, selectionState } from "@/lib/domain-p3d";
import { LoadingState, QueryError, EmptyState } from "@/design-system/states";
import type { RoleRanking } from "@/api/types-p3d";

export function CompositionScreen() {
  const { scenarioId } = useParams<{ scenarioId: string }>();
  const plan = usePlan(scenarioId);
  const explain = useExplainPlan(scenarioId);
  const ranking = useRanking(scenarioId);

  const topRanked = useMemo(() => {
    const m = new Map<string, { id: string; version: string }>();
    for (const r of (ranking.data?.rankings ?? []) as RoleRanking[]) {
      const first = r.ranked_candidates.find((c) => c.rank === 1) ?? r.ranked_candidates[0];
      if (first) m.set(r.role_id, { id: first.agent_id, version: first.agent_version });
    }
    return m;
  }, [ranking.data]);

  if (plan.isLoading) return <LoadingState label="Loading composition…" />;
  if (plan.error) return <QueryError error={plan.error} />;
  if (!plan.data) return null;

  const p = plan.data.agent_team_plan;
  const state = planState(p.plan_state);
  const stats = p.search_statistics;

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-lg font-semibold text-ink-0">Composition</h1>
        <StatusPill descriptor={state} title={`plan state ${p.plan_state}`} />
      </header>
      <PlanningNote />

      {p.plan_state === "NO_FEASIBLE_TEAM" ? (
        <NoFeasibleTeam plan={p} />
      ) : (
        <>
          {/* assignments */}
          <div className="overflow-x-auto rounded-lg border border-surface-border">
            <table className="min-w-[760px] w-full text-sm">
              <caption className="sr-only">Team role assignments</caption>
              <thead>
                <tr className="bg-surface-2 text-left text-xs text-ink-2">
                  <th scope="col" className="px-3 py-2">Role</th>
                  <th scope="col" className="px-3 py-2">Selected primary</th>
                  <th scope="col" className="px-3 py-2">Score</th>
                  <th scope="col" className="px-3 py-2">Top-ranked</th>
                  <th scope="col" className="px-3 py-2">Non-greedy?</th>
                  <th scope="col" className="px-3 py-2">Assignment fingerprint</th>
                </tr>
              </thead>
              <tbody>
                {p.role_assignments.map((a) => {
                  const top = topRanked.get(a.role_id);
                  const nonGreedy = top && (top.id !== a.primary_agent_id || top.version !== a.primary_agent_version);
                  return (
                    <tr key={a.role_id} className="border-t border-surface-border/60">
                      <th scope="row" className="px-3 py-2 text-left font-normal text-ink-1">{a.role_id}</th>
                      <td className="px-3 py-2">
                        <StatusPill descriptor={selectionState("SELECTED_PRIMARY")} />
                        <div className="mt-1 text-ink-0">{a.primary_agent_id}</div>
                        <div className="text-[11px] text-ink-3">v{a.primary_agent_version}</div>
                      </td>
                      <td className="px-3 py-2 font-mono">{a.total_score}</td>
                      <td className="px-3 py-2 text-ink-2">{top ? `${top.id}` : "—"}</td>
                      <td className="px-3 py-2">{nonGreedy ? <span className="text-state-indeterminate">Yes</span> : "No"}</td>
                      <td className="px-3 py-2"><Fingerprint value={a.assignment_fingerprint} label="assignment" /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <NonGreedyExplanation plan={p} topRanked={topRanked} />
          <SelectionStates explain={explain.data?.selection_states} />
        </>
      )}

      <TeamFacts plan={p} />
      <Card className="p-4">
        <Section title="Search statistics">
          <dl className="grid grid-cols-2 gap-x-6">
            <Field label="Algorithm">{stats.algorithm}</Field>
            <Field label="Optimality">{stats.optimality_status}</Field>
            <Field label="Search space">{stats.search_space_size}</Field>
            <Field label="Explored">{stats.assignments_explored}</Field>
            <Field label="Pruned">{stats.assignments_pruned}</Field>
            <Field label="Feasible teams">{stats.feasible_team_count}</Field>
            <Field label="Termination">{stats.termination_reason}</Field>
            <Field label="Plan fingerprint"><Fingerprint value={p.plan_fingerprint} label="plan" /></Field>
          </dl>
        </Section>
      </Card>
    </div>
  );
}

function NonGreedyExplanation({ plan, topRanked }: { plan: import("@/api/types-p3d").AgentTeamPlan; topRanked: Map<string, { id: string; version: string }> }) {
  const differing = plan.role_assignments.filter((a) => {
    const top = topRanked.get(a.role_id);
    return top && (top.id !== a.primary_agent_id || top.version !== a.primary_agent_version);
  });
  return (
    <Card className="p-4" data-testid="non-greedy">
      <Section title="Role ranking vs. team composition">
        <p className="mb-2 text-sm text-ink-2">
          Candidate ranking evaluates role-level suitability. Team composition applies additional
          workflow-wide constraints and objectives, so the selected team may differ from independently
          choosing each role's top-ranked candidate. A lower-ranked selected candidate is not a mistake.
        </p>
        {differing.length === 0 ? (
          <p className="text-sm text-ink-2">Every selected primary is also its role's top-ranked candidate for this scenario.</p>
        ) : (
          <ul className="space-y-1 text-sm">
            {differing.map((a) => {
              const top = topRanked.get(a.role_id)!;
              return (
                <li key={a.role_id} className="rounded border border-state-indeterminate/30 bg-state-indeterminate/10 p-2">
                  <span className="text-ink-1">{a.role_id}</span>: top-ranked{" "}
                  <span className="text-ink-2">{top.id}</span> · selected{" "}
                  <span className="text-ink-0">{a.primary_agent_id}</span> — see team constraints/objectives below.
                </li>
              );
            })}
          </ul>
        )}
      </Section>
    </Card>
  );
}

function SelectionStates({ explain }: { explain: Record<string, Record<string, string>> | undefined }) {
  if (!explain) return null;
  return (
    <Card className="p-4">
      <Section title="Candidate selection states">
        <div className="space-y-2">
          {Object.entries(explain).map(([role, agents]) => (
            <div key={role}>
              <p className="text-xs font-medium text-ink-1">{role}</p>
              <ul className="mt-1 flex flex-wrap gap-1.5">
                {Object.entries(agents).map(([agent, st]) => (
                  <li key={agent} className="flex items-center gap-1">
                    <StatusPill descriptor={selectionState(st)} />
                    <span className="text-[11px] text-ink-3">{agent.split("@")[0]}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Section>
    </Card>
  );
}

function TeamFacts({ plan }: { plan: import("@/api/types-p3d").AgentTeamPlan }) {
  return (
    <Card className="p-4">
      <Section title="Team-level facts">
        <dl>
          <Field label="Unfilled roles">{displayOrUnresolved(plan.unfilled_roles, "list")}</Field>
          <Field label="Total team score">{plan.total_team_score}</Field>
        </dl>
        <div className="mt-2 grid gap-3 lg:grid-cols-2">
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-ink-3">Hard constraints</p>
            <ul className="space-y-1 text-xs">
              {plan.team_constraint_results.map((c, i) => (
                <li key={i} className="flex items-center justify-between gap-2 rounded border border-surface-border/60 px-2 py-1">
                  <span className="text-ink-1">{c.constraint}</span>
                  <span className={c.satisfied ? "text-state-eligible" : "text-state-ineligible"}>
                    {c.satisfied ? "satisfied" : "violated"} ({String(c.measured_value)}/{String(c.limit_value)})
                  </span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-ink-3">Team objectives</p>
            <ul className="space-y-1 text-xs">
              {plan.team_objective_results.map((o, i) => (
                <li key={i} className="flex items-center justify-between gap-2 rounded border border-surface-border/60 px-2 py-1">
                  <span className="text-ink-1">{o.objective}</span>
                  <span className="text-ink-2">contribution {String(o.weighted_contribution)}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Section>
    </Card>
  );
}

function NoFeasibleTeam({ plan }: { plan: import("@/api/types-p3d").AgentTeamPlan }) {
  if (!plan) return <EmptyState title="No plan" />;
  return (
    <Card className="border-state-ineligible/40 p-4" data-testid="no-feasible-team">
      <Section title="No feasible team">
        <p className="mb-2 text-sm text-ink-1">
          Eligible candidates may exist for individual roles, but no team satisfies all workflow-wide
          constraints under the pinned registry and policies. This is a valid planning outcome — not an
          error, and not an empty successful team.
        </p>
        <dl>
          <Field label="Unfilled roles">{displayOrUnresolved(plan.unfilled_roles, "list")}</Field>
          <Field label="Blocking constraints">
            {plan.team_constraint_results.filter((c) => !c.satisfied).map((c) => c.constraint).join(", ") || "see search statistics"}
          </Field>
          <Field label="Search termination">{plan.search_statistics.termination_reason}</Field>
          <Field label="Plan fingerprint"><Fingerprint value={plan.plan_fingerprint} label="plan" /></Field>
        </dl>
      </Section>
    </Card>
  );
}
