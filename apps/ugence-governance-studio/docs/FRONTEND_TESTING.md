# Frontend Testing

- **Unit/component** (Vitest + Testing Library + jsdom, 24 tests): generated-client
  freeze, matrix/domain units, scenario catalog, overview, workflow graph + list,
  roles, registry, eligibility matrix, explanation drawer, compatibility gate, and
  axe accessibility checks. A fetch-level mock (fixtures captured from the real
  backend) exercises the real client + hooks.
- **E2E** (Playwright, 2 specs against the REAL backend): the Procurement flow
  (catalog → workflow → eligibility → explanation → registry) and the
  cybersecurity no-feasible-team honest rendering.
- **Verifiers**: `verify:openapi`, `verify:boundary`, `verify:terminology`.
