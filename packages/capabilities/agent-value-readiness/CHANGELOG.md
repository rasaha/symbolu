# Changelog — ugence-agent-value-readiness

## [0.2.0] — GV-3R-b: deterministic readiness-determination evaluator

**Additive.** Milestone **M-3R.2** of the UVI ADR
(`docs/architecture/ADR_UGENCE_VALUE_INTELLIGENCE_GV2C_GV2E_GV3R.md`, §6–§9).
Minor bump because this is a material new capability on top of a merged 0.1.0;
every 0.1.0 symbol keeps its shape and behaviour, so existing callers are
unaffected. **No other package is touched** — `governance-contracts`,
`uvi-policy-contracts` and `governed-value` are unchanged.

The determination stays **advisory, non-financial and fail-closed**: it is not a
deployment authorization, not a Policy Authority, and it verifies no evidence.

### Added
- `evaluate_readiness(case, *, evaluation_time)` — the **single canonical
  entry point** that selects one `ReadinessClassification` from a complete
  applicable gate set. `evaluation_time` is mandatory, keyword-only and must be
  timezone-aware; the **system clock is never read**.
- `ReadinessEvaluationCase` — the immutable input. It carries the bound
  `AssessmentContext`, the complete `ReadinessPolicy` **by value**, its exact
  `PolicyReference`, the requested target, the Intelligence/Capability/Adoption
  results, the `GateResult` tuple, `ConditionSet` records, an optional
  `AdvisoryComposite`, and evidence/window references — and deliberately **no
  classification field**. Rejects self-contradictory inputs with a typed
  `ReadinessEvaluationError`: a gate bound to another policy, a gate absent from
  the supplied policy, a redefined `PolicyGate`, duplicate gate/condition/result
  ids, a gate evaluated for another target, cross-tenant/subject binding, or a
  policy reference that is not the supplied policy's. `canonical_input_digest()`
  is order-independent.
- `ReadinessEvaluationResult` / `ReadinessEvaluationTrace` / `ConditionDecision`
  — the advisory determination plus a deterministic, explanatory-only trace
  (evaluator id, formula version, selected rule, applicable and diagnostic gate
  ids, missing required gates, mandatory failures and indeterminates, unresolved
  conditional concerns, per-condition accept/reject decisions, assessability
  gaps, reason and advisory codes, input digest and reference set).
  `authorizes_deployment` is permanently `False`.
- Stable code enums: `ReadinessRuleId` (R1–R8), `ReadinessReasonCode`,
  `ReadinessAdvisoryCode`, `ConditionDecisionCode`. Codes are emitted in enum
  declaration order, never input order.

### Determination algorithm (first matching rule wins)
1. any applicable mandatory `FAIL` → `NOT_READY`
2. a structural assessability gap → `NOT_ASSESSABLE`
3. an applicable mandatory `INDETERMINATE` with no `FAIL` → `NOT_ASSESSABLE`
4. an unresolved conditional concern that is not compensable → `NOT_READY`
5. a compensable concern without active coverage → `NOT_READY`
6. PILOT, everything above satisfied → `PILOT_READY` (carries its bounded pilot
   controls; the enum has no `PILOT_READY_WITH_CONDITIONS` tier)
7. PRODUCTION with concerns fully covered → `READY_WITH_CONDITIONS`
8. PRODUCTION with nothing unresolved and no open active condition →
   `DEPLOYMENT_READY`

`R1` precedes `R2` because ADR §8/D-6 make a mandatory `FAIL` unconditional and
`AgentValueReadinessDetermination` structurally rejects any other classification
while a blocking gate is present; the gaps are still reported in the trace.

### Invariants proven by tests
- Gate-set completeness is derived from the `ReadinessPolicy`, so an omitted
  applicable mandatory or conditional gate is `NOT_ASSESSABLE`, never `PASS`.
- `{FAIL, INDETERMINATE, PASS}` ⇒ `NOT_READY`; `{INDETERMINATE, PASS}` ⇒
  `NOT_ASSESSABLE`; `{PASS, PASS}` ⇒ conditional resolution.
- `CONDITIONAL` alone is not compensable — the policy must set
  `conditionally_compensable=True`; an uncovered concern is `NOT_READY`.
- Proposed / expired / revoked / satisfied / not-yet-effective / window-ended
  controls are not coverage; the half-open interval is preserved.
- An active control over an applicable gate that is not unresolved is
  internally inconsistent → `NOT_ASSESSABLE`; a `SATISFIED` control over a
  passing gate is retained and permits `DEPLOYMENT_READY`.
- Production-only gates stay diagnostic during PILOT and never block it.
- Evidence axes are preserved exactly (`REPORTED`/`UNATTESTED`/
  `NOT_ATTRIBUTED`/`UNVERIFIED` are never upgraded); no evidence type is
  constructed anywhere in the evaluator.
- The `AdvisoryComposite` is inert: minimum vs maximum score yields an identical
  classification, rule and reason-code tuple.
- Deterministic and order-independent: reversing the input tuples leaves the
  classification, reason codes, gate sets, condition coverage, trace digest and
  determination digest unchanged.

### Not implemented (deliberate)
No evidence admission or verification, no benchmark resolution, **no
metric-to-threshold calculation** (the merged `GovernedThreshold` keeps opaque
literal/unit semantics and none are invented), no policy-authenticity or
condition-authority verification, no causal attribution, no deployment
authorization, no durable event bus or signing, no money/return/forecast.
`ConditionSet` carries no tenant/subject field, so condition **scope is not
matched** against the assessed tenant — recorded as a standing advisory.

### Also updated
Curated `api` exports, `public_api.json` (version + 10 new symbols), README,
distribution verifier (isolated multi-wheel `--no-index` proof now exercises the
evaluator), and 87 new tests.

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
