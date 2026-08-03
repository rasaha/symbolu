// Screen 6 — Eligibility matrix (§18-§20). The primary P3C screen. Rows are
// agents; columns are API-provided condition names. All states/conditions come
// from the API. No score, rank, recommendation or preference is shown.
import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useEligibility, useRegistry, useWorkflow } from "@/hooks/queries";
import { useExplorerStore, type SortKey } from "@/state/store";
import { eligibilityState } from "@/lib/domain";
import { EligibilityMeaningNote } from "@/components/MaturityBanner";
import { Card, Fingerprint, StatusPill } from "@/design-system/primitives";
import { LoadingState, QueryError, EmptyState } from "@/design-system/states";
import { applyFilters, buildMatrix, cellState, sortRows } from "./matrix";
import { ExplanationDrawer } from "./ExplanationDrawer";
import type { AgentProfile } from "@/api/types";

const CELL_GLYPH = { pass: "✓", fail: "✕", unknown: "?", na: "·" } as const;
const CELL_TITLE = { pass: "passed", fail: "failed", unknown: "unknown", na: "not applicable" } as const;
const CELL_CLASS = {
  pass: "text-state-eligible",
  fail: "text-state-ineligible",
  unknown: "text-state-indeterminate",
  na: "text-ink-3",
} as const;

const SORTS: { key: SortKey; label: string }[] = [
  { key: "identity", label: "Agent identity" },
  { key: "state", label: "Eligibility state" },
  { key: "provider", label: "Provider" },
  { key: "failed", label: "Failed conditions" },
  { key: "unknown", label: "Unknown conditions" },
];

export function EligibilityScreen() {
  const { scenarioId } = useParams<{ scenarioId: string }>();
  const eligibility = useEligibility(scenarioId);
  const registry = useRegistry(scenarioId);
  const workflow = useWorkflow(scenarioId);

  const selectedRoleId = useExplorerStore((s) => s.selectedRoleId);
  const setSelectedRole = useExplorerStore((s) => s.setSelectedRole);
  const selectedAgentKey = useExplorerStore((s) => s.selectedAgentKey);
  const setSelectedAgent = useExplorerStore((s) => s.setSelectedAgent);
  const filters = useExplorerStore((s) => s.filters);
  const setFilters = useExplorerStore((s) => s.setFilters);
  const resetFilters = useExplorerStore((s) => s.resetFilters);
  const sort = useExplorerStore((s) => s.sort);
  const setSort = useExplorerStore((s) => s.setSort);
  const [announce, setAnnounce] = useState("");

  const reports = useMemo(() => eligibility.data?.role_reports ?? [], [eligibility.data]);
  const roleName = useMemo(
    () => new Map((workflow.data?.role_requirements ?? []).map((r) => [r.role_id, r.role_name])),
    [workflow.data],
  );
  const profiles = useMemo(() => {
    const m = new Map<string, AgentProfile>();
    for (const p of registry.data?.registry_snapshot.agent_profiles ?? [])
      m.set(`${p.agent_id}@${p.agent_version}`, p);
    return m;
  }, [registry.data]);

  useEffect(() => {
    if (!selectedRoleId && reports.length > 0) setSelectedRole(reports[0].role_id);
  }, [reports, selectedRoleId, setSelectedRole]);

  if (eligibility.isLoading) return <LoadingState label="Loading eligibility…" />;
  if (eligibility.error) return <QueryError error={eligibility.error} />;
  if (reports.length === 0)
    return <EmptyState title="No AI-agent roles" detail="This scenario has no agent-eligible roles." />;

  const report = reports.find((r) => r.role_id === selectedRoleId) ?? reports[0];
  const matrix = buildMatrix(report, profiles);
  const visibleRows = sortRows(applyFilters(matrix.rows, filters), sort);

  const providers = [...new Set(matrix.rows.map((r) => r.provider).filter(Boolean))].sort();
  const residencies = [...new Set(matrix.rows.map((r) => r.residency).filter(Boolean))].sort();
  const statuses = [...new Set(matrix.rows.map((r) => r.status).filter(Boolean))].sort();
  const reasons = [...new Set(matrix.rows.flatMap((r) => r.reasons))].sort();

  const totals = {
    eligible: report.eligible_agent_ids.length,
    ineligible: report.eliminated_agent_ids.length,
    indeterminate: report.indeterminate_agent_ids.length,
    total: report.results.length,
  };

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-lg font-semibold text-ink-0">Eligibility matrix</h1>
        <p className="text-xs text-ink-3">
          {totals.total} role-agent pairs · {totals.eligible} eligible · {totals.ineligible} ineligible ·{" "}
          {totals.indeterminate} indeterminate
        </p>
      </header>

      <EligibilityMeaningNote />

      {/* role selector */}
      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Select a role">
        {reports.map((r) => (
          <button
            key={r.role_id}
            type="button"
            aria-pressed={r.role_id === report.role_id}
            onClick={() => setSelectedRole(r.role_id)}
            className={
              "rounded border px-3 py-1.5 text-sm " +
              (r.role_id === report.role_id
                ? "border-[#6aa9ff] bg-surface-3 text-ink-0"
                : "border-surface-border bg-surface-1 text-ink-2 hover:bg-surface-2")
            }
          >
            {roleName.get(r.role_id) ?? r.role_id}
          </button>
        ))}
      </div>

      {/* filters + sort */}
      <Card className="flex flex-wrap items-end gap-3 p-3">
        <Filter label="Provider" value={filters.provider} options={providers} onChange={(v) => setFilters({ provider: v })} />
        <Filter label="Residency" value={filters.residency} options={residencies} onChange={(v) => setFilters({ residency: v })} />
        <Filter label="Agent status" value={filters.agentStatus} options={statuses} onChange={(v) => setFilters({ agentStatus: v })} />
        <Filter label="Elimination reason" value={filters.reason} options={reasons} onChange={(v) => setFilters({ reason: v })} />
        <div className="flex flex-col gap-1">
          <label htmlFor="sort" className="text-[11px] text-ink-3">Sort by</label>
          <select
            id="sort"
            value={sort}
            onChange={(e) => setSort(e.target.value as SortKey)}
            className="rounded border border-surface-border bg-surface-0 px-2 py-1 text-sm text-ink-1"
          >
            {SORTS.map((s) => (
              <option key={s.key} value={s.key}>{s.label}</option>
            ))}
          </select>
        </div>
        <button type="button" onClick={resetFilters} className="rounded border border-surface-border px-2 py-1 text-sm text-ink-2 hover:bg-surface-2">
          Reset
        </button>
        <p className="ml-auto text-[11px] text-ink-3">
          Display order is not a selection decision. No agent is ranked or preferred.
        </p>
      </Card>

      <p aria-live="polite" className="sr-only">{announce}</p>

      {/* matrix */}
      {visibleRows.length === 0 ? (
        <EmptyState title="No agents match the filters" detail="Adjust or reset the filters." />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-surface-border">
          <table className="min-w-[820px] border-collapse text-sm">
            <caption className="sr-only">
              Eligibility conditions per agent for role {roleName.get(report.role_id) ?? report.role_id}
            </caption>
            <thead>
              <tr className="bg-surface-2 text-left text-xs text-ink-2">
                <th scope="col" className="sticky left-0 z-10 bg-surface-2 px-3 py-2">Agent</th>
                <th scope="col" className="px-2 py-2">State</th>
                <th scope="col" className="px-2 py-2" title="passed / failed / unknown">P / F / U</th>
                {matrix.columns.map((c) => (
                  <th key={c} scope="col" className="px-2 py-2 font-normal" title={c}>
                    <span className="inline-block max-w-[92px] truncate align-bottom">{c}</span>
                  </th>
                ))}
                <th scope="col" className="px-2 py-2">Explain</th>
              </tr>
            </thead>
            <tbody>
              {visibleRows.map((row) => (
                <tr key={row.agentKey} className="border-t border-surface-border/60">
                  <th scope="row" className="sticky left-0 z-10 bg-surface-1 px-3 py-2 text-left font-normal">
                    <div className="font-medium text-ink-0">{row.agentId}</div>
                    <div className="text-[11px] text-ink-3">{row.provider} · v{row.agentVersion}</div>
                  </th>
                  <td className="px-2 py-2">
                    <StatusPill descriptor={eligibilityState(row.state)} />
                  </td>
                  <td className="px-2 py-2 font-mono text-[11px] text-ink-2">
                    {row.passedCount}/{row.failedCount}/{row.unknownCount}
                  </td>
                  {matrix.columns.map((c) => {
                    const st = cellState(row, c);
                    return (
                      <td key={c} className="px-2 py-2 text-center">
                        <span className={CELL_CLASS[st]} title={`${c}: ${CELL_TITLE[st]}`}>
                          <span aria-hidden="true">{CELL_GLYPH[st]}</span>
                          <span className="sr-only">{c}: {CELL_TITLE[st]}</span>
                        </span>
                      </td>
                    );
                  })}
                  <td className="px-2 py-2">
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedAgent(row.agentKey);
                        setAnnounce(`Opened explanation for ${row.agentId}`);
                      }}
                      className="rounded border border-surface-border bg-surface-2 px-2 py-1 text-xs text-ink-0 hover:bg-surface-3"
                      data-testid={`explain-${row.agentId}`}
                    >
                      Explain
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-[11px] text-ink-3">
        Result fingerprint (first visible row):{" "}
        <Fingerprint value={visibleRows[0]?.fingerprint} label="result" />
      </p>

      {selectedAgentKey && (
        <ExplanationDrawer
          scenarioId={scenarioId!}
          roleId={report.role_id}
          agentKey={selectedAgentKey}
          onClose={() => setSelectedAgent(null)}
        />
      )}
    </div>
  );
}

function Filter({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string | null;
  options: string[];
  onChange: (v: string | null) => void;
}) {
  const id = `filter-${label.replace(/\s+/g, "-").toLowerCase()}`;
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-[11px] text-ink-3">{label}</label>
      <select
        id={id}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
        className="rounded border border-surface-border bg-surface-0 px-2 py-1 text-sm text-ink-1"
      >
        <option value="">All</option>
        {options.map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
    </div>
  );
}
