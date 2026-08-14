# Changelog — ugence-agent-value-readiness

## [0.1.0] — GV-3R-a: Agent Value Readiness contract shapes

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
