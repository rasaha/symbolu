# Implementation Decisions (P3B)

1. **Thin orchestration.** `AwcOrchestrationService` replicates the exact public
   AWC call sequence used by the frozen P3A generator, so scenario execution is
   real and reproduces frozen fingerprints. No planning logic is reimplemented.
2. **Bundled read-only fixtures.** P3A `demo_data`/`expected_outputs` and the AWC
   v2 conformance bundle are copied into the wheel as package data (byte-identity
   drift-tested), so the API installs and executes outside the monorepo.
3. **Scenario-or-inline inputs.** Domain endpoints accept a `scenario_id` or
   inline pinned artifacts; no filesystem/code/script field exists.
4. **What-if = typed perturbations on copies.** Nine bounded operations mutate
   copies of the frozen inputs and re-run the same public pipeline; committed
   fixtures are never mutated.
5. **Seams, not features.** Authentication and rate-limiting are disabled seams;
   no hard-coded credentials. Frontend, deployment, DB, runtime handoff and agent
   execution are explicitly NOT implemented (maturity flags false).
6. **Frozen contracts.** OpenAPI (`contracts/openapi.json`) and the public Python
   API snapshot are generated deterministically and drift-verified in CI.
