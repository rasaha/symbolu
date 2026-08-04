// Ranking Explorer (§12, §13). Canonical API rank order by default; score
// decomposition and tie-break from the API. No score is computed in the browser.
import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useRanking, useRegistry } from "@/hooks/queries";
import { useExplorerStore } from "@/state/store";
import { PlanningNote } from "@/components/MaturityBanner";
import { Card, Fingerprint, Section, StatusPill } from "@/design-system/primitives";
import { eligibilityState } from "@/lib/domain";
import { LoadingState, QueryError, EmptyState } from "@/design-system/states";
import type { AgentProfile } from "@/api/types";
import type { RankedCandidate } from "@/api/types-p3d";

type SortMode = "canonical" | "score" | "identity";

export function RankingScreen() {
  const { scenarioId } = useParams<{ scenarioId: string }>();
  const ranking = useRanking(scenarioId);
  const registry = useRegistry(scenarioId);
  const selectedRoleId = useExplorerStore((s) => s.selectedRoleId);
  const setSelectedRole = useExplorerStore((s) => s.setSelectedRole);
  const [sort, setSort] = useState<SortMode>("canonical");
  const [expanded, setExpanded] = useState<string | null>(null);

  const providers = useMemo(() => {
    const m = new Map<string, string>();
    for (const p of (registry.data?.registry_snapshot.agent_profiles ?? []) as AgentProfile[])
      m.set(`${p.agent_id}@${p.agent_version}`, p.provider_id);
    return m;
  }, [registry.data]);

  if (ranking.isLoading) return <LoadingState label="Loading ranking…" />;
  if (ranking.error) return <QueryError error={ranking.error} />;
  const rankings = ranking.data?.rankings ?? [];
  if (rankings.length === 0) return <EmptyState title="No rankings" detail="This scenario has no ranked roles." />;

  const role = rankings.find((r) => r.role_id === selectedRoleId) ?? rankings[0];
  if (role.role_id !== selectedRoleId) setTimeout(() => setSelectedRole(role.role_id), 0);

  const candidates = [...role.ranked_candidates];
  if (sort === "score") candidates.sort((a, b) => b.total_score - a.total_score || a.rank - b.rank);
  else if (sort === "identity") candidates.sort((a, b) => `${a.agent_id}`.localeCompare(b.agent_id));
  // canonical: leave in API order (already rank-ordered)

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-lg font-semibold text-ink-0">Ranking</h1>
        <p className="text-xs text-ink-3">
          role ranking fingerprint <Fingerprint value={role.ranking_fingerprint} label="ranking" />
        </p>
      </header>
      <PlanningNote />

      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Select a role">
        {rankings.map((r) => (
          <button
            key={r.role_id}
            type="button"
            aria-pressed={r.role_id === role.role_id}
            onClick={() => setSelectedRole(r.role_id)}
            className={
              "rounded border px-3 py-1.5 text-sm " +
              (r.role_id === role.role_id
                ? "border-[#6aa9ff] bg-surface-3 text-ink-0"
                : "border-surface-border bg-surface-1 text-ink-2 hover:bg-surface-2")
            }
          >
            {r.role_id}
          </button>
        ))}
      </div>

      <Card className="flex flex-wrap items-center gap-3 p-3 text-sm">
        <label htmlFor="ranksort" className="text-[11px] text-ink-3">Presentation order</label>
        <select
          id="ranksort"
          value={sort}
          onChange={(e) => setSort(e.target.value as SortMode)}
          className="rounded border border-surface-border bg-surface-0 px-2 py-1 text-sm text-ink-1"
        >
          <option value="canonical">Canonical rank (API)</option>
          <option value="score">Total score (presentation)</option>
          <option value="identity">Agent identity (presentation)</option>
        </select>
        {sort !== "canonical" && (
          <button type="button" onClick={() => setSort("canonical")} className="rounded border border-surface-border px-2 py-1 text-xs text-ink-2 hover:bg-surface-2">
            Reset to canonical rank
          </button>
        )}
        <span className="ml-auto text-[11px] text-ink-3">
          Presentation order does not change the canonical API rank. {role.eligible_candidate_count} eligible ·{" "}
          {role.excluded_candidate_count} excluded
        </span>
      </Card>

      <div className="overflow-x-auto rounded-lg border border-surface-border">
        <table className="min-w-[720px] w-full text-sm">
          <caption className="sr-only">Ranked candidates for role {role.role_id}</caption>
          <thead>
            <tr className="bg-surface-2 text-left text-xs text-ink-2">
              <th scope="col" className="px-3 py-2">Rank</th>
              <th scope="col" className="px-3 py-2">Agent</th>
              <th scope="col" className="px-3 py-2">Provider</th>
              <th scope="col" className="px-3 py-2">Total score</th>
              <th scope="col" className="px-3 py-2">Tie group</th>
              <th scope="col" className="px-3 py-2">Score breakdown</th>
            </tr>
          </thead>
          <tbody>
            {candidates.map((c) => {
              const key = `${c.agent_id}@${c.agent_version}`;
              const open = expanded === key;
              return (
                <RankRow
                  key={key}
                  c={c}
                  provider={providers.get(key) ?? ""}
                  open={open}
                  onToggle={() => setExpanded(open ? null : key)}
                />
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RankRow({ c, provider, open, onToggle }: { c: RankedCandidate; provider: string; open: boolean; onToggle: () => void }) {
  return (
    <>
      <tr className="border-t border-surface-border/60">
        <th scope="row" className="px-3 py-2 text-left font-mono">{c.rank}</th>
        <td className="px-3 py-2">
          <div className="font-medium text-ink-0">{c.agent_id}</div>
          <div className="text-[11px] text-ink-3">v{c.agent_version}</div>
        </td>
        <td className="px-3 py-2 text-ink-2">{provider}</td>
        <td className="px-3 py-2 font-mono">{c.total_score}</td>
        <td className="px-3 py-2 text-ink-2">{c.tie_group ?? "—"}</td>
        <td className="px-3 py-2">
          <button
            type="button"
            aria-expanded={open}
            onClick={onToggle}
            className="rounded border border-surface-border bg-surface-2 px-2 py-1 text-xs text-ink-0 hover:bg-surface-3"
            data-testid={`breakdown-${c.agent_id}`}
          >
            {open ? "Hide" : "Show"} breakdown
          </button>
        </td>
      </tr>
      {open && (
        <tr className="bg-surface-1/60">
          <td colSpan={6} className="px-3 py-3">
            <Section title="Score decomposition (API criterion contributions, basis points)">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[560px] text-xs">
                  <thead>
                    <tr className="text-left text-ink-3">
                      <th scope="col" className="py-1 pr-3">Criterion</th>
                      <th scope="col" className="py-1 pr-3">Raw</th>
                      <th scope="col" className="py-1 pr-3">Normalized (bp)</th>
                      <th scope="col" className="py-1 pr-3">Weight (bp)</th>
                      <th scope="col" className="py-1 pr-3">Contribution (bp)</th>
                      <th scope="col" className="py-1">Evidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {c.criterion_results.map((cr, i) => (
                      <tr key={`${cr.criterion}-${i}`} className="border-t border-surface-border/40">
                        <th scope="row" className="py-1 pr-3 text-left font-normal text-ink-1">{cr.criterion}</th>
                        <td className="py-1 pr-3 text-ink-2">{String(cr.raw_value)}</td>
                        <td className="py-1 pr-3 font-mono">{cr.normalized_bp}</td>
                        <td className="py-1 pr-3 font-mono">{cr.weight_bp}</td>
                        <td className="py-1 pr-3 font-mono">{cr.weighted_contribution_bp}</td>
                        <td className="py-1 text-ink-3">{cr.evidence_refs.length || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <dl className="mt-2 grid grid-cols-2 gap-x-4 text-[11px]">
                <div className="flex gap-2"><dt className="text-ink-3">Tie-break</dt><dd className="text-ink-1">{JSON.stringify(c.tie_break_values)}</dd></div>
                <div className="flex gap-2"><dt className="text-ink-3">Eligibility</dt><dd><StatusPill descriptor={eligibilityState("ELIGIBLE")} /></dd></div>
                <div className="flex gap-2"><dt className="text-ink-3">Result fingerprint</dt><dd><Fingerprint value={c.result_fingerprint} label="result" /></dd></div>
              </dl>
            </Section>
          </td>
        </tr>
      )}
    </>
  );
}
