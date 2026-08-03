# Frontend Testing

- **Unit/component** (Vitest + Testing Library + jsdom, 46 tests): generated-client
  freeze, matrix/domain units, scenario catalog, overview, workflow graph + list,
  roles, registry, eligibility matrix, explanation drawer, compatibility gate, axe
  accessibility, permission-scope, dependency-audit policy and contrast math. A
  fetch-level mock (fixtures captured from the real backend) exercises the real
  client + hooks.
- **Direct scenario E2E** (Playwright, 4 specs against the REAL backend): all four
  scenarios — Procurement guided flow, Customer Support smoke, Cybersecurity
  feasible (eligible + ineligible explanations) and Cybersecurity no-feasible-team
  honest rendering. No mocked eligibility; live frozen scenario data.
- **Verifiers**: `verify:openapi`, `verify:boundary`, `verify:terminology`,
  `verify:contrast`, `audit:dependencies`.

## Blocking policies

- **Dependency audit** (`npm run audit:dependencies`): fails on unexcepted HIGH or
  CRITICAL production vulnerabilities. Exceptions are bounded/expiring/documented
  in `security/dependency-audit-exceptions.json`; expired, wildcard, undocumented
  or critical exceptions fail. Tested with captured audit JSON (no vulnerable
  dependency is ever introduced).
- **Contrast** (`npm run verify:contrast`): measures 21 critical token pairs
  against WCAG 2.2 thresholds and fails on any violation or missing required pair;
  emits `artifacts/contrast-report.json`.
