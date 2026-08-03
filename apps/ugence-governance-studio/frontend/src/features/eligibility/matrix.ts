// Eligibility matrix builder (§18, §19). Pure presentation shaping of
// API-provided condition results — NO pass/fail/eligibility is computed here.
// Rows are agents; columns are the union of condition names the API reported.
import type { AgentProfile, RoleEligibilityReport } from "@/api/types";
import type { EligibilityFilters, SortKey } from "@/state/store";
import { conditionName } from "@/lib/domain";

export interface MatrixRow {
  agentKey: string;
  agentId: string;
  agentVersion: string;
  state: string;
  provider: string;
  residency: string;
  status: string;
  passed: Set<string>;
  failed: Set<string>;
  unknown: Set<string>;
  reasons: string[];
  evidenceCount: number;
  passedCount: number;
  failedCount: number;
  unknownCount: number;
  fingerprint: string;
}

export interface Matrix {
  columns: string[];
  rows: MatrixRow[];
}

export function buildMatrix(
  report: RoleEligibilityReport,
  profiles: Map<string, AgentProfile>,
): Matrix {
  const columnSet = new Set<string>();
  const rows: MatrixRow[] = report.results.map((r) => {
    const passed = r.passed_conditions.map(conditionName);
    const failed = r.failed_conditions.map(conditionName);
    const unknown = r.unknown_conditions.map(conditionName);
    for (const c of [...passed, ...failed, ...unknown]) columnSet.add(c);
    const key = `${r.agent_id}@${r.agent_version}`;
    const profile = profiles.get(key);
    return {
      agentKey: key,
      agentId: r.agent_id,
      agentVersion: r.agent_version,
      state: r.state,
      provider: profile?.provider_id ?? "",
      residency: profile?.residency ?? "",
      status: profile?.status ?? "",
      passed: new Set(passed),
      failed: new Set(failed),
      unknown: new Set(unknown),
      reasons: r.elimination_reasons,
      evidenceCount: r.evidence_refs.length,
      passedCount: passed.length,
      failedCount: failed.length,
      unknownCount: unknown.length,
      fingerprint: r.result_fingerprint,
    };
  });
  return { columns: [...columnSet].sort(), rows };
}

export function cellState(row: MatrixRow, column: string): "pass" | "fail" | "unknown" | "na" {
  if (row.failed.has(column)) return "fail";
  if (row.passed.has(column)) return "pass";
  if (row.unknown.has(column)) return "unknown";
  return "na";
}

function normalizeState(state: string): string {
  return state === "ELIMINATED" ? "INELIGIBLE" : state;
}

export function applyFilters(rows: MatrixRow[], f: EligibilityFilters): MatrixRow[] {
  return rows.filter((r) => {
    if (f.states.length && !f.states.includes(normalizeState(r.state))) return false;
    if (f.provider && r.provider !== f.provider) return false;
    if (f.residency && r.residency !== f.residency) return false;
    if (f.agentStatus && r.status !== f.agentStatus) return false;
    if (f.reason && !r.reasons.includes(f.reason)) return false;
    return true;
  });
}

const STATE_ORDER: Record<string, number> = { ELIGIBLE: 0, INDETERMINATE: 1, INVALID_INPUT: 2, INELIGIBLE: 3, ELIMINATED: 3 };

export function sortRows(rows: MatrixRow[], sort: SortKey): MatrixRow[] {
  const copy = [...rows];
  copy.sort((a, b) => {
    switch (sort) {
      case "state":
        return (STATE_ORDER[a.state] ?? 9) - (STATE_ORDER[b.state] ?? 9) || a.agentKey.localeCompare(b.agentKey);
      case "provider":
        return a.provider.localeCompare(b.provider) || a.agentKey.localeCompare(b.agentKey);
      case "failed":
        return b.failedCount - a.failedCount || a.agentKey.localeCompare(b.agentKey);
      case "unknown":
        return b.unknownCount - a.unknownCount || a.agentKey.localeCompare(b.agentKey);
      case "identity":
      default:
        return a.agentKey.localeCompare(b.agentKey);
    }
  });
  return copy;
}
