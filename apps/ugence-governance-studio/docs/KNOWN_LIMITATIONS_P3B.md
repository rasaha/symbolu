# Governance Studio API — Known Limitations (P3B)

Implemented: deterministic demo API, v1/v2 workflow adaptation, scenario
execution, eligibility, ranking, composition, permission proposals, fallbacks,
plan replay, plan comparison, controlled what-if analysis, artifact export.

NOT implemented (honest maturity flags all `false`): frontend, authentication,
private deployment, database, live enterprise data, agent execution, runtime
handoff, permission provisioning, action authorization, pilot validation,
production certification.

- Every response carries a synthetic / planning-only / no-execution notice.
- The compiler is consumed indirectly via the AWC public adapter; the API does
  not depend on the compiler package directly.
- What-if is limited to nine typed, bounded perturbations — no arbitrary
  expressions, code or policy scripts.
