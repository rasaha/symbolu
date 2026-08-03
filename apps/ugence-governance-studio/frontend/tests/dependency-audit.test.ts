import { describe, expect, it } from "vitest";
import { evaluate, validateException } from "../scripts/verify-dependency-audit.mjs";

const NOW = "2026-08-03T00:00:00Z";
const FUTURE = "2027-01-01T00:00:00Z";
const PAST = "2025-01-01T00:00:00Z";

function report(vulns: Record<string, { severity: string; source?: number }>) {
  const vulnerabilities: Record<string, unknown> = {};
  const counts: Record<string, number> = { critical: 0, high: 0, moderate: 0, low: 0, total: 0 };
  for (const [name, v] of Object.entries(vulns)) {
    vulnerabilities[name] = { name, severity: v.severity, via: [{ source: v.source ?? 1 }], range: "<1.0.0" };
    counts[v.severity] = (counts[v.severity] ?? 0) + 1;
    counts.total += 1;
  }
  return { vulnerabilities, metadata: { vulnerabilities: counts } };
}

const FULL_EXCEPTION = {
  package: "pkgA",
  installed_version: "0.1.0",
  advisory_id: "1234",
  severity: "high",
  affected_range: "<1.0.0",
  dependency_class: "production",
  reachable_in_production: "no",
  exploitability: "not reachable in the offline demo build",
  compensating_control: "no network egress; synthetic data only",
  reason: "upstream fix pending",
  owner: "governance-studio",
  expiry_date: FUTURE,
  remediation_target: "bump when patched",
};

describe("dependency-audit policy (C3)", () => {
  it("passes a clean production audit", () => {
    const r = evaluate(report({}), [], NOW);
    expect(r.ok).toBe(true);
    expect(r.counts.high).toBe(0);
    expect(r.counts.critical).toBe(0);
  });

  it("passes when only moderate/low findings exist", () => {
    const r = evaluate(report({ pkgM: { severity: "moderate" }, pkgL: { severity: "low" } }), [], NOW);
    expect(r.ok).toBe(true);
    expect(r.violations).toHaveLength(0);
  });

  it("fails on an unexcepted HIGH production vulnerability", () => {
    const r = evaluate(report({ pkgA: { severity: "high", source: 1234 } }), [], NOW);
    expect(r.ok).toBe(false);
    expect(r.violations.map((v: { name: string }) => v.name)).toContain("pkgA");
  });

  it("fails on an unexcepted CRITICAL production vulnerability", () => {
    const r = evaluate(report({ pkgC: { severity: "critical", source: 9 } }), [], NOW);
    expect(r.ok).toBe(false);
    expect(r.counts.critical).toBe(1);
  });

  it("accepts a HIGH vuln covered by a valid, unexpired exception", () => {
    const r = evaluate(report({ pkgA: { severity: "high", source: 1234 } }), [FULL_EXCEPTION], NOW);
    expect(r.ok).toBe(true);
    expect(r.acceptedExceptions).toBe(1);
  });

  it("fails when the covering exception is expired", () => {
    const r = evaluate(report({ pkgA: { severity: "high", source: 1234 } }), [{ ...FULL_EXCEPTION, expiry_date: PAST }], NOW);
    expect(r.ok).toBe(false);
    expect(r.invalidExceptions[0].problems.join()).toMatch(/expired/);
  });

  it("fails when an exception is missing required fields", () => {
    const partial = { ...FULL_EXCEPTION, compensating_control: "" };
    const r = evaluate(report({ pkgA: { severity: "high", source: 1234 } }), [partial], NOW);
    expect(r.ok).toBe(false);
    expect(r.invalidExceptions[0].problems.join()).toMatch(/compensating_control/);
  });

  it("rejects wildcard advisory suppression", () => {
    const r = evaluate(report({ pkgA: { severity: "high", source: 1234 } }), [{ ...FULL_EXCEPTION, advisory_id: "*" }], NOW);
    expect(r.ok).toBe(false);
    expect(r.invalidExceptions[0].problems.join()).toMatch(/wildcard/);
  });

  it("refuses to except a CRITICAL production vulnerability", () => {
    const problems = validateException({ ...FULL_EXCEPTION, severity: "critical" }, NOW);
    expect(problems.join()).toMatch(/critical/i);
  });

  it("a valid exception has no validation problems", () => {
    expect(validateException(FULL_EXCEPTION, NOW)).toHaveLength(0);
  });
});
