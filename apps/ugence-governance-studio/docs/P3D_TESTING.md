# P3D Testing

- **Vitest (61 total)**: decoder contract tests (accept valid, fail-closed on
  missing/incompatible, no domain defaulting); ranking, composition (incl.
  NO_FEASIBLE_TEAM + non-greedy), permission-proposal, fallback, replay,
  comparison and what-if component tests (nine allowlisted ops); plus the P3C
  suite, dependency-audit and contrast math.
- **Playwright (8 specs, real backend)**: 4 P3C eligibility flows + 4 P3D planning
  flows (Procurement full flow, Customer Support, Cybersecurity feasible,
  Cybersecurity no-feasible-team) with a live baseline/modified what-if + reset.
- **Verifiers**: verify:openapi, verify:boundary, verify:terminology,
  verify:contrast (34 pairs), audit:dependencies.
