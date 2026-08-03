// Blocking production dependency-audit policy (§C3).
//
// FAILS when an unresolved HIGH or CRITICAL vulnerability affects a
// production/runtime dependency, unless covered by a valid, unexpired, fully
// documented exception. Moderate/low findings are reported but do not block the
// production gate. Dev-only findings are handled by a separate advisory audit.
//
//   node scripts/verify-dependency-audit.mjs   (runs `npm audit --omit=dev --json`)
//
// `evaluate()` is pure and exported so tests can drive it with captured audit
// JSON — no vulnerable dependency is ever introduced to test CI.
import { execSync } from "node:child_process";
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.dirname(HERE);
const EXCEPTIONS_PATH = path.join(FRONTEND, "security", "dependency-audit-exceptions.json");
const REPORT_PATH = path.join(FRONTEND, "artifacts", "dependency-audit-report.json");

export const BLOCKING_SEVERITIES = ["high", "critical"];

const REQUIRED_EXCEPTION_FIELDS = [
  "package",
  "installed_version",
  "advisory_id",
  "severity",
  "affected_range",
  "dependency_class",
  "reachable_in_production",
  "exploitability",
  "compensating_control",
  "reason",
  "owner",
  "expiry_date",
  "remediation_target",
];

function collectAdvisoryIds(vuln) {
  const ids = new Set();
  for (const via of vuln.via ?? []) {
    if (via && typeof via === "object" && via.source != null) ids.add(String(via.source));
  }
  return [...ids];
}

export function validateException(ex, nowIso) {
  const problems = [];
  for (const field of REQUIRED_EXCEPTION_FIELDS) {
    if (ex[field] === undefined || ex[field] === null || ex[field] === "") {
      problems.push(`missing required field '${field}'`);
    }
  }
  if (String(ex.advisory_id).includes("*")) problems.push("wildcard advisory suppression is not allowed");
  if (String(ex.package).includes("*")) problems.push("wildcard package suppression is not allowed");
  if (String(ex.severity).toLowerCase() === "critical") {
    problems.push("critical production vulnerabilities must not be excepted");
  }
  if (ex.expiry_date) {
    const expiry = Date.parse(ex.expiry_date);
    if (Number.isNaN(expiry)) problems.push("expiry_date is not a valid date");
    else if (expiry < Date.parse(nowIso)) problems.push(`exception expired on ${ex.expiry_date}`);
  }
  return problems;
}

export function evaluate(report, exceptions, nowIso) {
  const vulns = report?.vulnerabilities ?? {};
  const blocking = [];
  for (const [name, v] of Object.entries(vulns)) {
    if (BLOCKING_SEVERITIES.includes(v.severity)) {
      blocking.push({ name, severity: v.severity, advisoryIds: collectAdvisoryIds(v), range: v.range });
    }
  }

  const invalidExceptions = [];
  const validExceptions = [];
  for (const ex of exceptions ?? []) {
    const problems = validateException(ex, nowIso);
    if (problems.length) invalidExceptions.push({ package: ex.package, advisory_id: ex.advisory_id, problems });
    else validExceptions.push(ex);
  }

  const accepted = [];
  const violations = [];
  for (const vuln of blocking) {
    const match = validExceptions.find(
      (ex) =>
        ex.package === vuln.name &&
        (vuln.advisoryIds.includes(String(ex.advisory_id)) || vuln.advisoryIds.length === 0),
    );
    if (match) accepted.push({ vuln, exception: match });
    else violations.push(vuln);
  }

  const meta = report?.metadata?.vulnerabilities ?? {};
  return {
    ok: violations.length === 0 && invalidExceptions.length === 0,
    productionTotal: meta.total ?? Object.keys(vulns).length,
    counts: {
      critical: meta.critical ?? 0,
      high: meta.high ?? 0,
      moderate: meta.moderate ?? 0,
      low: meta.low ?? 0,
    },
    acceptedExceptions: accepted.length,
    violations,
    invalidExceptions,
  };
}

function loadExceptions() {
  if (!existsSync(EXCEPTIONS_PATH)) return [];
  const doc = JSON.parse(readFileSync(EXCEPTIONS_PATH, "utf-8"));
  return doc.exceptions ?? [];
}

function runAudit() {
  try {
    // npm exits non-zero when ANY vulnerability exists; we parse JSON regardless.
    const out = execSync("npm audit --omit=dev --json", { cwd: FRONTEND, encoding: "utf-8" });
    return JSON.parse(out);
  } catch (err) {
    if (err.stdout) return JSON.parse(err.stdout);
    throw err;
  }
}

function main() {
  const nowIso = new Date().toISOString();
  const report = runAudit();
  const exceptions = loadExceptions();
  const result = evaluate(report, exceptions, nowIso);

  const artifact = {
    generated_at: nowIso,
    command: "npm audit --omit=dev --json",
    policy: "block on unexcepted HIGH or CRITICAL production vulnerabilities",
    production_total: result.productionTotal,
    counts: result.counts,
    accepted_exceptions: result.acceptedExceptions,
    violations: result.violations,
    invalid_exceptions: result.invalidExceptions,
    result: result.ok ? "PASS" : "FAIL",
  };
  if (!existsSync(path.dirname(REPORT_PATH))) mkdirSync(path.dirname(REPORT_PATH), { recursive: true });
  writeFileSync(REPORT_PATH, JSON.stringify(artifact, null, 2) + "\n");

  console.log("production dependency audit (npm audit --omit=dev)");
  console.log(`  counts: critical=${result.counts.critical} high=${result.counts.high} ` +
    `moderate=${result.counts.moderate} low=${result.counts.low}`);
  console.log(`  accepted exceptions: ${result.acceptedExceptions}`);
  if (result.invalidExceptions.length) {
    console.error("  INVALID EXCEPTIONS:");
    for (const ie of result.invalidExceptions) console.error(`    ${ie.package}#${ie.advisory_id}: ${ie.problems.join("; ")}`);
  }
  if (result.violations.length) {
    console.error("  UNEXCEPTED HIGH/CRITICAL PRODUCTION VULNERABILITIES:");
    for (const v of result.violations) console.error(`    ${v.name} (${v.severity}) ${v.range ?? ""}`);
  }
  console.log(`  result: ${result.ok ? "PASS" : "FAIL"}`);
  process.exit(result.ok ? 0 : 1);
}

if (import.meta.url === `file://${process.argv[1]}`) main();
