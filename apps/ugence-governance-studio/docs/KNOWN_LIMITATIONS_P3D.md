# Known Limitations (P3D)

Implemented: ranking, score decomposition, composition, assignment explanations,
team constraints/objectives, permission proposals, permission feasibility,
fallbacks, plan replay, plan comparison, controlled what-if (nine bounded
operations) and deterministic export.

NOT implemented: permission granting, runtime permission provisioning, agent
execution, action authorization, authentication, deployment, live enterprise
data, multi-workflow orchestration. Not pilot validated, not production certified.

- Comparison currently offers baseline-vs-control and baseline-vs-forbidden-provider
  right-hand sources; arbitrary two-plan selection beyond the same scenario contract
  is out of scope.
- The plan diff is rendered from the API's typed change lists; deep field-level
  semantic grouping beyond the API categories is not attempted (no browser diff).
