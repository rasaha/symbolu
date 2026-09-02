# ugence-workflow-fit-pilot

Phase 4A of the reasoning-method governance thread
(`docs/architecture/WORKFLOW_FIT_PILOT_4A_COMMISSIONING_SPEC.md`, owner-ratified
2026-09-02): the **research-only Trusted Workflow-Fit Pilot**.

The pilot preregisters a `PilotStudyManifest` (plan, advisory and rule-set
digests, deduplicated methods with non-exclusive roles, benchmark manifest with
its exact case digests, capture-boundary and evaluator declarations, aggregation
references), validates it against the full catalog, rule set and advisory before
any run, executes each method behind a **separate-process capture boundary**
that is the workflow's only client, recomputes telemetry from its own capture
records and attests it on the digested execution record, scores quality under a
declared and **unverified** evaluator, calls the Slice 1 comparison engine, and
keeps a neutral five-state research-only ledger with one-way, derived-scope
lineage.

Every judgment is `RESEARCH_ONLY` and labelled on its evidence axes. Nothing here
is verified by any authority, preregistration is `DECLARED_UNVERIFIED`, evaluator
independence is `DECLARED_UNVERIFIED`, and `approval_status` is the constant
`"NONE"`. No owner-supplied numeric default, threshold, sample size, coverage
target or acceptance figure exists in this package.
