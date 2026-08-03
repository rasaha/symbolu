# Known Limitations (P3C)

Implemented: scenario catalog, scenario overview, workflow graph, node details,
role requirements, synthetic agent registry, eligibility matrix, elimination
explanations, evidence + provenance display, API compatibility gate, v1/v2
scenario display.

NOT implemented (P3D+): candidate ranking, team composition, permission proposals,
fallback planning, plan replay, plan comparison, controlled what-if,
authentication, deployment, live enterprise data, runtime handoff, agent
execution, permission granting, business-action authorization. None are pilot
validated or production certified.

- Color-contrast is enforced by the design tokens; axe cannot evaluate contrast in
  jsdom, so contrast is covered by the palette + manual review.
- The custom SVG graph favors deterministic layout and accessibility over advanced
  graph interactions (edge routing is straight-line).
