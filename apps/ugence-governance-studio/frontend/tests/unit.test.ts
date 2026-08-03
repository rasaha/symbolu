import { describe, expect, it } from "vitest";
import { buildMatrix, cellState, applyFilters, sortRows } from "@/features/eligibility/matrix";
import { EMPTY_FILTERS } from "@/state/store";
import { disposition, eligibilityState, reasonLabel, DISPOSITIONS } from "@/lib/domain";
import type { AgentProfile, RoleEligibilityReport } from "@/api/types";
import procEligibility from "./fixtures/procurement.eligibility.json";
import procRegistry from "./fixtures/procurement.registry.json";

const report = (procEligibility as { role_reports: RoleEligibilityReport[] }).role_reports[0];
const profiles = new Map<string, AgentProfile>(
  (procRegistry as unknown as { registry_snapshot: { agent_profiles: AgentProfile[] } }).registry_snapshot.agent_profiles.map(
    (p) => [`${p.agent_id}@${p.agent_version}`, p],
  ),
);

describe("matrix builder", () => {
  it("accounts for every role-agent pair exactly once", () => {
    const m = buildMatrix(report, profiles);
    expect(m.rows.length).toBe(report.results.length);
    const keys = new Set(m.rows.map((r) => r.agentKey));
    expect(keys.size).toBe(m.rows.length);
  });

  it("derives cell state only from API condition results", () => {
    const m = buildMatrix(report, profiles);
    const row = m.rows[0];
    for (const c of m.columns) {
      const st = cellState(row, c);
      const expected = row.failed.has(c) ? "fail" : row.passed.has(c) ? "pass" : row.unknown.has(c) ? "unknown" : "na";
      expect(st).toBe(expected);
    }
  });

  it("filters by provider without changing domain results", () => {
    const m = buildMatrix(report, profiles);
    const provider = m.rows[0].provider;
    const filtered = applyFilters(m.rows, { ...EMPTY_FILTERS, provider });
    expect(filtered.every((r) => r.provider === provider)).toBe(true);
    // filtering never mutates the underlying rows
    expect(m.rows.length).toBeGreaterThanOrEqual(filtered.length);
  });

  it("sorts deterministically and stably", () => {
    const m = buildMatrix(report, profiles);
    const a = sortRows(m.rows, "identity").map((r) => r.agentKey);
    const b = sortRows(m.rows, "identity").map((r) => r.agentKey);
    expect(a).toEqual(b);
    expect(a).toEqual([...a].sort());
  });
});

describe("domain mappings", () => {
  it("maps the eight canonical dispositions", () => {
    expect(Object.keys(DISPOSITIONS)).toHaveLength(8);
    expect(disposition("AI_AGENT_ELIGIBLE").label).toBe("AI-agent role");
    expect(disposition("ZZZ_UNKNOWN").code).toBe("ZZZ_UNKNOWN");
  });

  it("maps eligibility states with non-color glyphs", () => {
    expect(eligibilityState("ELIGIBLE").glyph).toBeTruthy();
    expect(eligibilityState("INELIGIBLE").label).toBe("Ineligible");
  });

  it("labels known reason codes deterministically and falls back for unknown", () => {
    expect(reasonLabel("PROVIDER_FORBIDDEN")).toBe("Provider is forbidden by enterprise policy");
    expect(reasonLabel("SOMETHING_NEW")).toBe("Something new");
  });
});
