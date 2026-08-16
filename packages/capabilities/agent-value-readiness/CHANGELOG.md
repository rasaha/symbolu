# Changelog — ugence-agent-value-readiness

## [0.2.0] — GV-3R-b: deterministic readiness evaluator

**Additive material capability.** Adds the deterministic evaluator that consumes
the GV-3R-a contract shapes and **selects** one advisory readiness classification.
The GV-3R-a contract surface is unchanged; no other package is touched. Version
advances 0.1.0 → 0.2.0.

### Added
- `contracts/evaluation.py`: `ReadinessEvaluationCase` (immutable input; **no
  classification field**; validates tenant/subject/context consistency, binds the
  `ReadinessPolicy` body to its reference, and rejects a gate bound to another
  policy / a gate not in the policy / an embedded `PolicyGate` that doesn't match
  the policy's gate / duplicate or mismatched-target gates — as
  `ReadinessEvaluationError`; canonicalizes its sequences by stable id).
  `ReadinessEvaluationResult` (determination + trace), `EvaluationTrace`,
  `ReadinessRule`, `ReadinessReasonCode`, `ReadinessEvaluationError`.
- `services/evaluator.py`: `evaluate_readiness(case, *, evaluation_time) ->
  ReadinessEvaluationResult` (+ `EVALUATOR_VERSION = "gv3r-b-1.0.0"`). The single
  canonical entry point. Selects the tier from the complete applicable gate set;
  the caller supplies no classification.
- Fail-closed decision ordering: a definite applicable mandatory FAIL dominates ⇒
  `NOT_READY`; a missing applicable required (MANDATORY/CONDITIONAL) gate ⇒
  `NOT_ASSESSABLE` (never silent PASS); a mandatory INDETERMINATE ⇒
  `NOT_ASSESSABLE`; then conditional resolution. A conditional concern is
  compensable only when `PolicyGate.conditionally_compensable is True` and an
  active `ConditionSet` (`is_active_at(evaluation_time)`) references that exact
  gate. Full PILOT (`PILOT_READY` carries bounded pilot controls; production-only
  gates stay diagnostic) and PRODUCTION (`READY_WITH_CONDITIONS` /
  `DEPLOYMENT_READY`) tables.
- Deterministic, canonically-ordered outputs + evaluation trace (rule, reason
  codes, applicable/diagnostic/mandatory-fail/mandatory-indeterminate/unresolved-
  conditional gate ids, accepted/rejected conditions, assessability gaps, input
  digest). `evaluation_time` is mandatory + timezone-aware; the system clock is
  never read.

### Boundary (unchanged posture)
- Advisory only — authorizes no deployment; verifies no evidence/policy
  authenticity; resolves no benchmark; computes no metric-to-threshold; performs
  no attribution; **never** upgrades a MetricClaim evidence axis. Every result
  carries trust advisories. No money/ROI/forecast; an `AdvisoryComposite` is
  carried through unchanged and **never** consulted for the tier (proven by a
  min↔max invariance test). `GateResult.status` remains structurally supplied and
  authority-unverified.

### Verification
- New evaluator tests (`tests/contract/test_evaluator.py`, 29) cover the full
  PILOT/PRODUCTION tables, FAIL-over-INDETERMINATE precedence, omitted-gate and
  wrong-policy/tampered-gate attacks, conditional compensation/coverage/inactivity,
  determinism (input-order independence), composite non-influence, evidence-axis
  preservation, and the advisory/no-financial boundary. Distribution verifier
  extended with an evaluator smoke check.

## [0.1.0] — GV-3R-a: Agent Value Readiness contract shapes

### Pre-merge hardening (independent-audit corrections; still 0.1.0, unreleased)

Corrections to the GV-3R-a audit findings, applied before merge. No evaluator,
tier selection, authority, or financial behavior added — only stronger *local*
contract consistency. The public shape of `GateResult` and the determination
changed (acceptable for an unmerged v0.1.0; no deprecated bypass retained).

- **GV3R-F2/F4 — non-forgeable gate metadata.** `GateResult` now **embeds the
  actual immutable `PolicyGate` by value**. `gate_id`, gate kind, target
  applicability, owned threshold, `is_diagnostic`, and `is_blocking` are
  **derived** from it; the caller-settable `gate_kind`/`applicable`/`threshold_ref`/
  `benchmark_ref` fields are removed. A caller can no longer relabel a mandatory
  gate advisory, mark an applicable gate diagnostic, or swap its threshold. A
  `from_policy_gate()` factory is added for ergonomics (the direct constructor is
  already safe). `ConditionSet.is_active_at(as_of)` adds a time-aware activity
  check (`effective_from <= as_of < effective_to/expiry`).
- **GV3R-F1 — derived blocking sets + ready-class scan.** `blocking_gate_ids` /
  `indeterminate_gate_ids` are now **derived properties** computed from
  `gate_results` (removed as constructor fields). A ready classification is
  rejected if any `gate_result` is a blocking or applicable-mandatory-INDETERMINATE
  gate — an applicable mandatory failure can no longer be hidden by omission.
  Mixed FAIL/INDETERMINATE precedence compatibility is enforced (FAIL ⇒ only
  `NOT_READY`; INDETERMINATE-without-FAIL ⇒ only `NOT_ASSESSABLE`).
- **GV3R-F3/F4 — `READY_WITH_CONDITIONS` active coverage.** Requires every
  applicable unresolved CONDITIONAL concern in `gate_results` to be covered by a
  condition **active at the determination time** (`created_at`), and rejects a
  condition that covers no such concern or points at the wrong gate. Proposed/
  expired/revoked/satisfied/future-effective/expired-window conditions are not
  active coverage.
- **GV3R-F5 — `DEPLOYMENT_READY` cleanliness.** Rejects any unresolved conditional
  concern or open (active) condition; historical `SATISFIED` conditions permitted.
- **GV3R-F6 — single-policy gates.** Every `gate_result.readiness_policy_ref` must
  equal the determination's `readiness_policy_ref` (id/version/digest/tenant/family).
- **GV3R-F7 — extensibility documented.** README states the dimension enums are the
  initial shared taxonomy (domain metrics via governed `metric_id`; new dimensions
  are versioned contract evolution), and clarifies that the embedded `PolicyGate`
  prevents internal metadata contradiction but does not prove policy authenticity.
- Adversarial tests added (`tests/contract/test_determination_consistency.py`)
  covering every finding; distribution verifier extended with the F1 guard.

## [0.1.0] — GV-3R-a: Agent Value Readiness contract shapes (original)

**New internal technical leaf.** Additive to the monorepo; changes no existing
package. Implements milestone **M-3R.1** of the UVI ADR
(`docs/architecture/ADR_UGENCE_VALUE_INTELLIGENCE_GV2C_GV2E_GV3R.md`, §5–§10,
§20): the **non-financial contract shapes** for the Agent Value Readiness engine.
**Contracts only — no evaluator, no deployment authority, no money.** Evaluation
(precedence calculus, tier selection, authority resolution) is GV-3R-b (M-3R.2).

### Added
- Three distinct indicator result types — `IntelligenceFitnessResult`,
  `CapabilityReadinessResult`, `AdoptionReadinessResult` — each binding a GV-2E-a
  `MetricClaim` by value (five orthogonal evidence axes preserved, never
  elevated), tagged with a `ReadinessIndicatorClass`. Capability distinguishes
  demonstration state (`CapabilityDemonstration`), evidence sufficiency, and
  target-relative requirement class. `AdoptionReadinessResult.pre_deployment` is
  locked `True` (adoption readiness ≠ observed post-deployment adoption).
- `GateResult` — a recorded evaluation that **references** an existing
  `PolicyGate` (does not redefine one), preserving requested target, applicability
  (diagnostic vs blocking), status, threshold/benchmark and evidence references.
- `ConditionSet` — compensating-control record; only a `CONDITIONAL` concern is
  eligible (mandatory is non-waivable, D-6); `APPROVED_ACTIVE` requires complete
  authority/owner/monitoring/evidence/time; `EXPIRED`/`REVOKED` never active.
- `AdvisoryComposite` — optional, `Decimal`-only (floats rejected), explicit
  scale, declared method+version, `is_advisory` locked; can never determine a
  tier, override a mandatory failure, or be multiplied into ROI; no default
  weights.
- `AgentValueReadinessDetermination` — the advisory envelope with local
  target/classification consistency invariants (`PILOT_READY`⇒PILOT;
  `DEPLOYMENT_READY`/`READY_WITH_CONDITIONS`⇒PRODUCTION; ready classes carry no
  blocking/indeterminate gates; `NOT_READY`/`NOT_ASSESSABLE` need a reason;
  blocking/indeterminate references must point at applicable-mandatory
  FAIL/INDETERMINATE gates; cross-tenant/context binding rejected). The
  classification is a caller **input**; it is **not** computed from the gates.
- Enums: `ReadinessClassification` (5 target-relative values), `GateStatus`,
  `ConditionStatus`, `ReadinessIndicatorClass`, `CapabilityDemonstration`,
  `IntelligenceDimension`, `CapabilityDimension`, `AdoptionDimension`.
  `ReadinessContractError` (subclasses `ValueError`).
- Curated `ugence_agent_value_readiness.api`; machine-readable `public_api.json`
  + parity test; dependency-boundary test (stdlib + the two contract leaves,
  never `governed-value`); contract + immutability + anti-gaming tests; isolated
  multi-wheel `--no-index` distribution verifier; PEP 561 `py.typed`.

### Reuse (no forking)
- Depends on `ugence-governance-contracts>=0.2.0` (MetricClaim/BenchmarkReference/
  AssessmentWindow/evidence axes) and `ugence-uvi-policy-contracts>=0.1.0`
  (AssessmentContext/PolicyReference/ReadinessTarget/RequirementClass/PolicyFamily).
  `ReadinessTarget`/`RequirementClass` are **re-exported** for convenience but
  remain canonically owned by `uvi-policy-contracts`.

### Type placement
- Readiness result vocabulary (`GateStatus`, `ReadinessClassification`, the
  determination) is placed in **this leaf** rather than `governance-contracts`
  because `ReadinessTarget` is already owned by `uvi-policy-contracts` (GV-2C-a)
  and the ADR §20 "multi-consumer" precondition is not met in GV-3R-a.
  `governance-contracts` is **unchanged** (no version / `CONTRACT_VERSION` bump).
  Promotion to a neutral seam is a documented forward path for a second consumer.

### Non-goals (this milestone)
- No readiness evaluator/state machine, precedence selector, tier selection, or
  deployment authorization. No Policy Authority, signing/approval/issuance/
  revocation, registry/resolver, evidence admission/verification,
  `SubjectContext`/`AssessedSystemBinding`, forecasting, realization-probability
  modeling, attributed/verified ROI, financial valuation, `governed-value`
  integration, or `ConditionSet` runtime enforcement.
