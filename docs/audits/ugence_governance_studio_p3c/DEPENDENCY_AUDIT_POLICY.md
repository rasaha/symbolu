# Dependency-Audit Policy (C3)

**Blocking production policy.** `npm run audit:dependencies`
(`node scripts/verify-dependency-audit.mjs`, over `npm audit --omit=dev --json`)
FAILS on any unexcepted HIGH or CRITICAL vulnerability in a production/runtime
dependency. Moderate/low findings are reported, not blocking. npm's non-zero exit
(any vuln) is ignored; the JSON is parsed and the documented policy applied.

Current state: 18 production dependencies · critical 0 · high 0 · moderate 2 · low 0
· accepted exceptions 0 · **PASS**.

**Exceptions** (`security/dependency-audit-exceptions.json`) are bounded and
expiring. Each requires: package, installed_version, advisory_id, severity,
affected_range, dependency_class, reachable_in_production, exploitability,
compensating_control, reason, owner, expiry_date, remediation_target. Rules:
no open-ended or wildcard suppression; expired or undocumented exceptions fail;
critical production vulnerabilities may not be excepted. CI job
`production-dependency-audit` is blocking; `dependency-exception-validation` runs
the policy tests (clean/high/critical/valid-exception/expired/missing-field/
wildcard) driven by captured audit JSON — no vulnerable dependency is introduced.
