# Known Limitations (P3C)

Implemented: scenario catalog, scenario overview, workflow graph, node details,
role requirements, synthetic agent registry, eligibility matrix, elimination
explanations, evidence + provenance display, API compatibility gate, v1/v2
scenario display.

## Permission display boundary

P3C **displays** permission-related eligibility inputs: role-required permissions,
prohibited permissions, agent-requested permissions, authority ceilings and
policy-related permission failures shown in the eligibility explanation.

P3C does **not** implement (P3D+):

- permission-proposal UI
- proposed-permission bundle comparison
- permission-feasibility composition UI
- permission-granting UI
- runtime permission provisioning

> Displayed: permission requirements used during eligibility.
> Not displayed: AWC permission proposals produced during composition.

## Other not-implemented (P3D+)

Candidate ranking, team composition, fallback planning, plan replay, plan
comparison, controlled what-if, authentication, deployment, live enterprise data,
runtime handoff, agent execution, business-action authorization. None are pilot
validated or production certified.

## Verification notes

- **Contrast is programmatically measured** (`npm run verify:contrast`,
  `artifacts/contrast-report.json`): 21 critical design-token pairs are checked
  against WCAG 2.2 thresholds (normal 4.5:1, large 3:1, non-text 3:1). Token-level
  contrast is **measured**; full rendered-browser visual review remains
  supplemental. axe alone does not verify CSS color contrast (it cannot in jsdom).
- The custom SVG graph favors deterministic layout and accessibility over advanced
  graph interactions (edge routing is straight-line).
