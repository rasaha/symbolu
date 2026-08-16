# ADR — Ugence Value Intelligence: Governed Assessment Context, Evidence & Benchmark Contracts, and Pre-ROI Readiness (GV-2C / GV-2E / GV-3R)

## 1. Status, date, scope, decision owners

- **Status:** PROPOSED — architecture ratified in direction (owner rulings D-1…D-18 recorded); **design-only**, pending final ratification and separately-reviewed implementation phases.
- **Date:** 2026-08-13.
- **Scope:** milestones **GV-2C** (governed assessment context), **GV-2E** (evidence & benchmark contracts), **GV-3R** (Pre-ROI agent–outcome readiness) of the **Ugence Value Intelligence** capability. This ADR defines contracts, ownership, invariants and boundaries **only**. It introduces **no runtime code, no contracts, no packages, no authority, and no behavior**, and changes **no** existing package.
- **Decision owners:** Ugence architecture owners for Value Intelligence, Policy Authority, Risk Authority, Decision Authority, Agent Runtime, and Runtime Assurance. Unresolved items requiring an owner ruling are listed in §26.
- **Amendments:** **2026-08-16** — consistency-only amendment for the ratified [`ADR_UGENCE_POLICY_AUTHORITY.md`](ADR_UGENCE_POLICY_AUTHORITY.md) (one shared, platform-wide **Ugence Policy Authority**; UVI is its **first policy-family adapter**). It resolves the §26.1 open item and **strengthens** D-1 rather than weakening it. D-1's prohibition on a UVI-specific Policy Authority **stands unchanged**; D-2 … D-18 and all readiness/evidence/valuation semantics are **unchanged**.

## 2. Purpose and non-goals

**Purpose.** Convert an agent's assessment into two clearly-separated, honestly-classified outputs: a **non-financial Pre-ROI readiness determination** (GV-3R) and, downstream and independently, a **classified financial valuation** (the existing `governed-value` kernel), both grounded in **first-class, versioned, authority-resolved policy context** (GV-2C) and **orthogonally-classified evidence** (GV-2E). The design exists to prevent the recurring failure modes catalogued across prior audits: caller-controlled policy multipliers, a single linear evidence-maturity ladder, execution mistaken for effect, effect mistaken for verified value, and mandatory governance failures averaged away by a composite score.

**Non-goals (explicitly out of this ADR and its first milestones):**
- No implementation of the Pre-ROI evaluator, forecasting, financial valuation, context/evidence contracts, or benchmark registry.
- No new customer-facing Ugence module.
- No new authority. No minting, approval, signing, issuance, or revocation of any policy.
- No change to `governed-value` 0.2.0 or to PR #1426.
- No forecasting engine (deferred) and no post-deployment observed-effect integration (deferred).

## 3. Relationship to `governed-value` 0.2.0 and PR #1426

`governed-value` 0.2.0 (PR #1426, draft) is the **independent, experimental downstream reported-value calculation kernel** — one engine of Ugence Value Intelligence (Governed Value Verification), operating over **caller-reported, unverified** inputs and honestly emitting `POST_DEPLOYMENT_VALUE / REPORTED / UNVERIFIED`. This ADR **does not modify it** and **does not depend on it for GV-2C/GV-2E/GV-3R**. Its compatibility projection onto the new evidence model is fixed in §22 (D-17). PR #1426 proceeds through its own review, independently.

## 4. One customer-facing capability and its internal engines

There is exactly **one** customer-facing capability: **Ugence Value Intelligence (UVI)**. It contains three **internal technical engines** (not products, not customer-facing modules):

1. **Agent Value Readiness** — GV-3R; non-financial leading-indicator readiness (this ADR).
2. **Value Forecasting** — deferred; opportunity/scenario/uncertainty (not this ADR).
3. **Governed Value Verification** — the existing `governed-value` kernel is its downstream calculator.

The internal packages named throughout are **technical architecture**, not additional products (D-18).

## 5. Ratified decisions D-1 … D-18

### D-1 — Policy Authority
The existing/planned **Ugence Policy Authority** owns policy **approval, signing/issuance, authorized publishers, effective periods, supersession, and revocation**. `policy-workflow-compiler` is **only a compiler** — it never approves, signs, issues, revokes, or mints policy authority. **No** UVI-specific Policy Authority and **no** new customer-facing module. Policy Authority is **not yet implemented in the repository for UVI value-policies** and is recorded here as an **explicit required dependency** (§19, §26). Reference implementations must never self-approve or self-sign UVI policies and must **fail closed** on unsigned/unapproved/expired/revoked/superseded/digest-mismatched policy artifacts.

> *Amendment (2026-08-16) — D-1 unchanged and upheld.* The "existing/planned Ugence Policy Authority" is ratified in [`ADR_UGENCE_POLICY_AUTHORITY.md`](ADR_UGENCE_POLICY_AUTHORITY.md) as **one shared, platform-wide** authority — **internal platform infrastructure, not a customer-facing module** — with **UVI policy schemas as its first policy-family adapter**. This **satisfies** D-1 as written; it grants **no** exception to it. The prohibition on a **UVI-specific** Policy Authority **remains in force**, and a UVI-owned authority package/distribution is now prohibited **by name**. The Policy Authority remains an **external platform dependency** of UVI engines: engines consume exact resolved, digest-bound policy artifacts **by value** and import **no** authority internals (§21).

### D-2 — UVI policy representation
`GeographyPolicy`, `DomainPolicy`, `IntendedOutcomePolicy`, `ValuationPolicy`, `ReadinessPolicy` are **not** forced into workflow-specific `WorkflowIR`. They live in a narrow internal **`uvi-policy-contracts`** technical package (schema + IR representation), governed by the Policy Authority. Not a customer-facing module.

### D-3 — Benchmark registry
An internal **UVI benchmark registry**: domain owners curate candidates; **Policy Authority governs admission and permitted uses**; **benchmark versions are immutable**; updates produce new versions; assessments bind exact **benchmark id + version + content digest**; expired/revoked/superseded benchmarks are **never silently substituted**; **registry resolution creates no policy authority**. Thresholds are either **immutable policy literals** (intrinsic to the signed policy) or **`BenchmarkReference`** (separately maintained, reusable, or frequently-updated data).

### D-4 — Readiness engine
Placed provisionally at **`packages/capabilities/agent-value-readiness`**, an internal UVI engine. It evaluates `PreROIReadiness = f(IntelligenceFitness, CapabilityReadiness, AdoptionReadiness | GeographyPolicy, DomainPolicy, IntendedOutcomePolicy)` — **non-financial** leading indicators — and produces an **evidence-based advisory determination**. It does **not** authorize deployment, approve policy, mint runtime authority, or calculate financial ROI. Deployment/human-governance processes consume determinations; Risk Authority and ActionGate retain runtime authorization.

### D-5 — Readiness target
`ReadinessTarget ∈ {PILOT, PRODUCTION}`. Only gates applicable to the requested target determine the headline (§6). A composite score is advisory only — it may compare systems **within** a tier but can **never** change the tier. After context validity, a definite applicable mandatory `FAIL` takes precedence over an unrelated `INDETERMINATE` (§7).

### D-6 — Non-waivable mandatory gates
Mandatory gates are **non-compensatory and non-waivable**: `MANDATORY FAIL ⇒ NOT_READY`. No `ConditionSet`, waiver, compensating control, positive ROI, high composite, forecast, or human preference may convert a mandatory failure into readiness. Only concerns **explicitly classified by policy as conditionally compensable** may be governed through a `ConditionSet` (§9).

### D-7 — ConditionSet / compensating controls
`ConditionSet` (fields in §9) with `current_status ∈ {PROPOSED, APPROVED_ACTIVE, EXPIRED, REVOKED, SATISFIED}`. `READY_WITH_CONDITIONS` requires: all applicable mandatory gates `PASS`; every **permitted** unresolved concern has an `APPROVED_ACTIVE` `ConditionSet`; every required compensating control is active and evidenced; scope, monitoring, owner, expiry and revocation trigger present. A condition without an approved active control **blocks** the target; expired/revoked controls **invalidate** the conditional determination on re-evaluation.

### D-8 — Evidence model (orthogonal axes, not one ladder)
`SourceBasis ∈ {REPORTED, OBSERVED, SYNTHETIC, MIXED}`; `TransformationMethod ∈ {DIRECT, CALCULATED, MODELED}`; `AttestationStatus ∈ {UNATTESTED, ATTESTED}`; `AttributionStatus ∈ {NOT_APPLICABLE, NOT_ATTRIBUTED, PARTIALLY_ATTRIBUTED, ATTRIBUTED}`; `VerificationStatus ∈ {UNVERIFIED, VERIFICATION_FAILED, VERIFIED}`. Rules in §11–§13. Use a neutral **`MetricClaim`** for reported/observed/calculated/modeled values; reserve **`MetricObservation`** for genuinely observed claims.

### D-9 — Synthetic evidence
`SourceBasis.SYNTHETIC` is permitted **only** for pre-deployment testing/readiness/evaluation, carrying `EVALUATION_ONLY` usage scope, generator/dataset identity+version, population/domain assumptions, known domain-shift limitations, provenance, and content digest. It is **never sufficient by itself** for observed/attributed/verified realized ROI (§14).

### D-10 — Execution → effect → attribution → verification
Honest chain (§17). Existing semantics are preserved and **not renamed**: `RiskAuthorizationEnvelope` = permission; Agent Runtime results = an attempt ran (not effect); `ExecutionObservation` = provider-reported outcome claim (not verified); DA `ReconciliationResult` = intent↔observation consistency (not causal attribution); Runtime-Assurance `TrajectoryAssessment` = runtime risk (not claim verification). Two **new UVI assessment contracts** — `AttributionAssessment`, `VerificationAssessment` — are defined (§17), consuming existing artifacts as inputs **without distorting their semantics**.

### D-11 — Financial valuation
`governed-value` owns `FinancialValuation`, financial calculations, and classified value/ROI outputs. Eligibility comes from approved `IntendedOutcomePolicy` and/or `ValuationPolicy` — **not** a hard-coded `VERIFIED`-effect prerequisite. Valuation may run over reported/modeled/observed/attributed/verified inputs, but the output **preserves their exact evidential meaning**; a `VERIFIED ROI` claim is admissible **only** when every policy-required component meets the required attribution and verification standards (§18).

### D-12 — Valuation evidence manifest
`ValuationEvidenceManifest` carries **component-level** classifications and evidence references for every input class (§18). Conservative headline rule: **a verified component never elevates** a reported/modeled/unattested/unattributed/unverified component; the headline classification is the **weakest required** component's classification.

### D-13 — Geography / Domain / Intended Outcome
First-class, versioned policy context — **not** caller-controlled numeric modifiers. Required determinations/references in §15.

### D-14 — Assessed system & subject context
**No second subject-context authority.** Reuse the canonical neutral subject-context work from the Risk Authority / cloud-scaling integration ADR **if ratified/available**; it is currently **draft-only (PR #1425, not merged, RA-owned, pending ratification)**, so it is recorded as an **explicit dependency** (§16, §26). Prefer `AssessedSystemBinding` referencing `canonical_subject_context_ref` + a UVI `SystemManifest` bound by digest. Do **not** mint a competing subject-context contract.

### D-15 — Contract & package placement
Boundaries fixed in §20; dependency rules in §21.

### D-16 — Policy roles
Distinguish author → approval authority → compiler → signing/issuing authority → registry/resolver → revocation owner (§19); do not conflate. Repository has a compiler but lacks approval/issuance/revocation ownership for UVI policies — recorded as dependencies on the Policy Authority.

### D-17 — Compatibility with governed-value 0.2.0
Projection fixed in §22; kernel unchanged; `DomainProfile`/`GeographyProfile` → policy-reference migration is a future, separately-reviewed breaking change.

### D-18 — Product boundary
One customer-facing capability (UVI); internal packages/engines are technical architecture, not products. PR #1426 remains independent.

## 6. Target-relative readiness state machine

Each `ReadinessGate` carries `kind ∈ {MANDATORY, CONDITIONAL, ADVISORY}` and `applicability ⊆ {PILOT, PRODUCTION}`. For a requested `ReadinessTarget`, the **applicable set** = gates whose `applicability` includes that target; all other gate results are computed and reported as **diagnostic** and can never block.

**Precondition (both targets):** if `AssessmentContext` (or any required policy/benchmark it resolves) is missing, expired, revoked, superseded, or digest-mismatched ⇒ `NOT_ASSESSABLE(context)`; no headline is asserted (diagnostic gate results may still be reported).

**Target = PILOT** (applicable set = `PILOT` gates):
- any applicable pilot-mandatory `FAIL` ⇒ `NOT_READY`;
- else any applicable pilot-mandatory `INDETERMINATE` ⇒ `NOT_ASSESSABLE`;
- else (all applicable pilot-mandatory `PASS`) ⇒ `PILOT_READY`, operated under **bounded pilot controls** (inherent scope, exposure, duration, monitoring limits — distinct from the PRODUCTION `ConditionSet` mechanism);
- production-only gate results remain **diagnostic** and can never make `PILOT_READY` unreachable.

**Target = PRODUCTION** (applicable set = `PRODUCTION` gates; pilot-safety mandatory gates are typically also production-applicable):
- any applicable production-mandatory `FAIL` ⇒ `NOT_READY`;
- else any applicable production-mandatory `INDETERMINATE` ⇒ `NOT_ASSESSABLE`;
- else all applicable mandatory `PASS` **and** every **permitted** unresolved concern covered by an `APPROVED_ACTIVE` `ConditionSet` ⇒ `READY_WITH_CONDITIONS`;
- else all applicable mandatory **and** required conditional gates `PASS`, with no unresolved active conditions ⇒ `DEPLOYMENT_READY`.

Determination ordering (strongest headline first): `NOT_ASSESSABLE > NOT_READY > {PILOT_READY, READY_WITH_CONDITIONS} > DEPLOYMENT_READY`. Invariant: `DEPLOYMENT_READY ⇒ every applicable mandatory ∪ required-conditional gate = PASS`.

## 7. Mixed FAIL / INDETERMINATE precedence

Evaluated over the **applicable mandatory set**, after context validity. A definite `FAIL` is never masked by an unrelated `INDETERMINATE`.

| # | Condition | Determination |
|---|---|---|
| 0 | context invalid / expired / revoked / superseded / digest-mismatch | `NOT_ASSESSABLE(context)` |
| 1 | ≥1 applicable-mandatory `FAIL` | `NOT_READY` (FAIL dominates INDETERMINATE) |
| 2 | no mandatory `FAIL`, ≥1 applicable-mandatory `INDETERMINATE` | `NOT_ASSESSABLE(gate)` |
| 3 | all applicable-mandatory `PASS` | → conditional / target resolution (§6, §9) |

Worked cases: `{FAIL, INDETERMINATE, PASS}` ⇒ `NOT_READY`; `{INDETERMINATE, PASS}` ⇒ `NOT_ASSESSABLE`; `{PASS, PASS}` + conditional `FAIL` with no approved active control ⇒ `NOT_READY`; `{PASS, PASS}` + conditional `FAIL` with `APPROVED_ACTIVE` control ⇒ `READY_WITH_CONDITIONS`.

## 8. Non-waivable mandatory-gate invariant (D-6)

```
MANDATORY gate FAIL  ⇒  determination = NOT_READY   (for that target)
```
No `ConditionSet`, waiver, compensating control, positive ROI, high composite score, forecast, or human preference may convert a mandatory `FAIL` into any readiness tier. `ConditionSet` governs **only** concerns that policy has explicitly classified as `CONDITIONAL` (conditionally compensable). A concern that is `MANDATORY` in the governing `DomainPolicy`/`ReadinessPolicy` is never eligible for a `ConditionSet`.

## 9. ConditionSet and compensating-control semantics (D-7)

`ConditionSet { condition_id, source_finding_or_gate, approved_mitigation_or_waiver, approving_authority, accountable_owner, scope_exposure_limit, monitoring_requirement, evidence_ref, effective_period, expiry, revocation_trigger, current_status }`, `current_status ∈ {PROPOSED, APPROVED_ACTIVE, EXPIRED, REVOKED, SATISFIED}`.

`READY_WITH_CONDITIONS` is produced **only** when **all** hold: (1) all applicable mandatory gates `PASS`; (2) every permitted unresolved concern has an `APPROVED_ACTIVE` `ConditionSet`; (3) every required compensating control is active and evidenced (`evidence_ref` present; not `EXPIRED`/`REVOKED`); (4) scope, monitoring, accountable owner, expiry, and revocation trigger are present. A conditional concern with **no** `APPROVED_ACTIVE` control is an **unmet condition** → the target drops to `NOT_READY` (never a silent `READY_WITH_CONDITIONS`). An `EXPIRED`/`REVOKED` control **invalidates** the conditional determination on re-evaluation. `ConditionSet` never applies to a `MANDATORY` concern (D-6).

## 10. Intelligence / Capability / Adoption readiness taxonomy (GV-3R)

Non-financial leading indicators, each a `MetricClaim` (§11) bound to evidence and evaluated against `GeographyPolicy`/`DomainPolicy`/`IntendedOutcomePolicy` thresholds/benchmarks.

| IntelligenceFitness (task-specific) | CapabilityReadiness | AdoptionReadiness (pre-deployment) |
|---|---|---|
| reasoning/decision quality; accuracy; reliability & consistency; confidence calibration; exception handling; uncertainty recognition; language/population/regional performance | required functional coverage; tool & integration readiness; workflow completion; execution reliability; autonomy boundaries; escalation & human fallback; security & governance readiness; observability & auditability | eligible population & workflow coverage; expected utilization; workflow suitability; user acceptance/trust readiness; training readiness; change-management readiness; expected override/rejection/abandonment; conditions for sustained use |

`AdoptionReadiness` (pre-deployment, predicted) is **distinct** from post-deployment `ObservedAdoption` (a GV-3+ evidence class); they are never merged.

## 11. SourceBasis and TransformationMethod (D-8)

Two orthogonal axes on every `MetricClaim` (resolving the prior `MODELED`/`DERIVED` overlap):

| Axis | Values | Meaning |
|---|---|---|
| `SourceBasis` | `REPORTED` · `OBSERVED` · `SYNTHETIC` · `MIXED` | where the ground inputs come from |
| `TransformationMethod` | `DIRECT` · `CALCULATED` · `MODELED` | how the value was produced from those inputs |

A model-based causal estimate over measured inputs = `(OBSERVED, MODELED)`. **`CALCULATED` and `MODELED` claims MUST cite `input_evidence_refs`.** `MIXED` source basis carries per-input basis in the manifest. `SYNTHETIC` is constrained by §14.

`MetricClaim { metric_id, value, governed_unit, source_basis, transformation_method, input_evidence_refs[], provenance_ref, window_or_horizon (AssessmentWindow | ForecastHorizon), population_slice, confidence_basis, attestation_status, attribution_status, verification_status, claim_ref? }`. `MetricObservation` is the profile of `MetricClaim` constrained to `source_basis = OBSERVED`, `transformation_method ∈ {DIRECT, CALCULATED}`, with a required `AssessmentWindow` (D-8, §13).

## 12. Attestation / Attribution / Verification separation (D-8)

Three **independent** axes; none elevates another:
- **Attestation** signs the provenance of whatever basis exists. It **never** converts `REPORTED` into `OBSERVED`, and **never** implies attribution.
- **Attribution** requires a declared **counterfactual + causal method + assumptions + evidence**. It is **not** prohibited for `MODELED` claims — causal attribution is routinely model-based. `ATTRIBUTED`/`PARTIALLY_ATTRIBUTED` require `SourceBasis ∈ {OBSERVED, MIXED}` grounding and a declared method; `REPORTED`-only / `SYNTHETIC` claims are `NOT_APPLICABLE` or `NOT_ATTRIBUTED`.
- **Verification** must bind a specifically declared **`claim_ref`** and does **not** imply attribution. `VERIFIED`/`VERIFICATION_FAILED` without a `claim_ref` are invalid. `VERIFICATION_FAILED` is terminal-negative (retained for audit; never consumed as valid).

**Caller-provided labels alone never elevate any axis** — elevation is a function of provenance + method + authority, not of a caller-supplied string.

## 13. `MetricClaim` versus `MetricObservation` (D-8)

`MetricClaim` is the neutral contract for **any** value (reported, observed, calculated, modeled). `MetricObservation` is **reserved** for genuinely observed measurements (`source_basis = OBSERVED`) and must not be used for predicted, modeled, or reported values. **Policy thresholds are policy artifacts, not metric evidence claims** — they carry no `SourceBasis`/axes and are compared *against* `MetricClaim`s by gates (a signed threshold is a `PolicyThreshold` literal or a `BenchmarkReference`, never a `MetricClaim`).

## 14. Synthetic-evidence restrictions (D-9)

`SourceBasis.SYNTHETIC` is admissible **only** for pre-deployment testing/readiness/evaluation and must carry: `usage_scope = EVALUATION_ONLY`; generator/dataset identity + version; population and domain assumptions; known domain-shift limitations; provenance; content digest. Synthetic evidence is **never** sufficient by itself to support `OBSERVED`, `ATTRIBUTED`, or `VERIFIED` **realized** ROI. Whether `SYNTHETIC` is admitted at all beyond readiness is an owner decision (§26).

## 15. Geography / Domain / Intended-Outcome policy matrices (D-13)

Each cell is a **defined value or a versioned reference**; none is a caller multiplier.

| GeographyPolicy | DomainPolicy | IntendedOutcomePolicy |
|---|---|---|
| jurisdiction & applicable regulations | governed outcome units | target outcome |
| reporting & functional currency | task & capability taxonomy | task definition |
| wage & operating-cost benchmarks (refs) | benefit & loss taxonomy | success criteria |
| language/population/regional requirements | permitted valuation methods | value function (ref) |
| residency & localization requirements | domain benchmarks (refs) | counterfactual specification |
| local counterfactual baselines | evidence & confidence requirements | measurement & observation windows |
| regional performance thresholds | consequence & criticality classification | realization lag |
| valuation-policy references | mandatory safety/fairness/quality/compliance gates | attribution method; normalization basis; required effect evidence; acceptance thresholds |

Thresholds are **immutable policy literals** when intrinsic to the signed policy (e.g. a fairness bar, a minimum-accuracy acceptance threshold decided by the policy), and **`BenchmarkReference`** when drawn from separately-maintained, reusable, or frequently-updated data (e.g. regional wage table, regulatory loss table, language-performance benchmark) (D-3).

## 16. Assessed-system binding and neutral subject-context dependency (D-14)

`AssessedSystemBinding { canonical_subject_context_ref, system_manifest_ref, system_manifest_digest, deployment_target, workflow_policy_refs[], assessment_context_refs[] }`.

`SystemManifest` binds the actually-assessed configuration: agent/system identity; model/model-set identities & versions; prompt/configuration versions & digests; tool & capability-set versions & digests; relevant workflow & policy references. **Immutable references + canonical digests** (mirroring the content-digest discipline of `risk_authority.ControlEvidenceRecord`).

**Dependency (explicit):** the canonical neutral `SubjectContext` is defined by the **RA-owned** design in PR #1425 (schema `risk-subject-context-1`, `SubjectBinding risk-subject-binding-1`), which is **draft-only, not merged, and not implemented**. UVI **reuses** that contract via `canonical_subject_context_ref` once ratified/merged; it does **not** mint a competing subject-context contract. Because the RA v2 fact set is scaling-oriented and carries no model/prompt/tool identity, the UVI `SystemManifest` is an **additive, non-competing** artifact bound by digest alongside the canonical subject context. Final placement/shape of `SystemManifest` and confirmation of the reuse boundary are owner decisions (§26).

## 17. Authorization → execution evidence → effect claim → attribution → verification → valuation

Honest chain; existing modules provide inputs, not the downstream determinations (D-10).

| Step | Contract | What existing modules actually provide | New? |
|---|---|---|---|
| Authorization | `RiskAuthorizationEnvelope` (Risk Authority) | signed **permission** to act | reuse |
| ExecutionEvidence | Agent Runtime `RuntimeResult` / `ProviderAttempt` / `WorkflowAdvanceOutcome` | an attempt **ran** with an outcome — not external effect | reuse |
| EffectClaim / EffectObservation | `governance-contracts.ExecutionObservation` (`business_outcome`, `observed_parameters`, `final`, `external_result_id`) | provider-**reported** outcome claim — not verified | reuse |
| **AttributionAssessment** | *new UVI contract* | DA `ReconciliationResult {RECONCILED, MISMATCHED, PARTIALLY_RECONCILED}` = intent↔observation **consistency** — an input, not a causal determination | **new** |
| **VerificationAssessment** | *new UVI contract* | Runtime-Assurance `TrajectoryAssessment` = runtime **risk/trajectory** — not claim-specific verification | **new** |
| **FinancialValuation** | *new, owned by `governed-value`* | no contract maps eligible effect + value policy → classified money | **new** |

`AttributionAssessment { declared_effect_claim, counterfactual_specification, causal_method, assumptions, evidence_refs[], attribution_fraction_or_result, limitations, responsible_producer }`.
`VerificationAssessment { claim_ref, verification_method, verifier_identity, independence_status, verification_evidence[], result, limitations, timestamp, expiry_or_freshness }`.

**DA reconciliation is not renamed `AttributedEffect`; Runtime-Assurance observation is not renamed `VerifiedEffect`.** Their outputs are consumed as inputs by the two new assessments without distorting their semantics.

## 18. `ValuationEvidenceManifest` and mixed-input classification (D-11, D-12)

A financial result combining inputs of different evidential quality must **not** be assigned one misleading label. `ValuationEvidenceManifest` carries, **per component** (benefits; avoided losses; actual losses; residual expected losses; operating costs; investment; normalization units; counterfactual inputs; attribution inputs): `source_basis`, `transformation_method`, `attestation_status`, `attribution_status`, `verification_status`, `evidence_refs[]`; and exposes aggregate `evidence_coverage`, `attribution_coverage`, `verification_coverage`, and `missing_or_degraded_components[]`.

**Conservative headline rules:**
- The headline classification of a result is the **weakest classification among its policy-required components** (a verified component never elevates a reported/modeled/unattested/unattributed/unverified component).
- A `VERIFIED ROI` headline is admissible **only** when every `IntendedOutcomePolicy`/`ValuationPolicy`-required component is `ATTRIBUTED` (where attribution is required) **and** `VERIFIED` against its declared `claim_ref`.
- A reported or modeled calculation remains clearly classified as reported/modeled; eligibility is defined by policy (D-11), not by a hard-coded `VERIFIED`-effect prerequisite. `governed-value` 0.2.0's current `REPORTED` emission is exactly the weakest-cell case (§22).

## 19. Policy authorship / approval / compiler / issuer / registry / revocation roles (D-16)

| Role | Existing owner (repository evidence) | Status for UVI value-policies |
|---|---|---|
| Policy / domain author | humans (content) | expected; no package |
| **Approval authority** | none (Decision Authority approves decision cases, not policy artifacts) | **required dependency on Policy Authority** |
| Compiler | `tooling/policy-workflow-compiler` (policy → IR) — **not an authority** | reuse (compilation only) |
| **Signing / issuing authority** | `risk_authority` signs **envelopes** (runtime authorization), **not** policy issuance | **required dependency on Policy Authority** |
| Registry / resolver | reference resolvers exist; UVI benchmark registry to be built (D-3) | internal registry; resolution mints no authority |
| **Revocation owner** | `risk_authority` owns envelope/authority revocation, **not** policy-version revocation | **required dependency on Policy Authority** |

Reference implementations must **fail closed** on unsigned, unapproved, expired, revoked, superseded, or digest-mismatched policy artifacts and must never self-approve/self-sign.

> *Amendment (2026-08-16).* The three rows marked **required dependency on Policy Authority** are owned by the shared, platform-wide **Ugence Policy Authority** ratified in [`ADR_UGENCE_POLICY_AUTHORITY.md`](ADR_UGENCE_POLICY_AUTHORITY.md) — approval **verification** (approval itself stays external), signing/issuance, and policy-version revocation — with UVI as its first policy-family adapter. Building that authority is a **platform dependency milestone**, **not** a UVI engine milestone; UVI's milestones (§25) are unchanged.

## 20. Type-by-type package ownership (D-15)

| Type | Owner package | Rationale |
|---|---|---|
| `SourceBasis`, `TransformationMethod`, `AttestationStatus`, `AttributionStatus`, `VerificationStatus` | **governance-contracts** | neutral cross-package axes |
| `MetricClaim`, `MetricObservation`, `EvidenceReference`, `EvidenceProvenance`, `BenchmarkReference`, `AssessmentWindow`, `ForecastHorizon`, `PopulationSlice`, `ConfidenceBasis`, `AssessedSystemBinding` (references), `AssessmentContext` | **governance-contracts** | neutral seams consumed by ≥2 engines |
| `ReadinessTarget`, `GateStatus`, minimal `ReadinessDetermination` envelope | **governance-contracts** (minimal, multi-consumer only) | externally-consumed result surface |
| `AttributionAssessment`, `VerificationAssessment` (contract shapes) | **governance-contracts** (shapes); producers per §26 | neutral determinations consumed by valuation |
| `GeographyPolicy`, `DomainPolicy`, `IntendedOutcomePolicy`, `ValuationPolicy`, `ReadinessPolicy` (schema + IR) | **uvi-policy-contracts** | UVI policy schema, Policy-Authority-governed |
| `IntelligenceFitness`, `CapabilityReadiness`, `AdoptionReadiness` catalogs; `ReadinessGate`, `GateResult`, `ReadinessPolicy` machinery; `ConditionSet` handling; target-relative state machine; advisory composite logic | **agent-value-readiness** | readiness-internal taxonomy/machinery (kept local) |
| `FinancialValuation`, financial calculation, `ValuationEvidenceManifest`, classified value/ROI outputs | **governed-value** | downstream financial types |
| `BenchmarkReference` **values** | internal **benchmark registry** | governed data, not a contract |
| opportunity sizing, scenario construction, realization probability, uncertainty ranges | **deferred forecasting leaf** | out of scope |
| `SystemManifest` (final home) | TBD — governance-contracts vs uvi | owner decision (§26) |

## 21. Dependency rules — no leaf imports another leaf's internals

```
governance-contracts        (depends on nothing)
      ▲            ▲            ▲              ▲
      │            │            │              │
uvi-policy-   agent-value-   governed-value   benchmark-registry
contracts     readiness      (0.2.0; later)   (service)
              │  └── uvi-policy-contracts (policy shapes, by value)
              └── governance-contracts
governed-value ── governance-contracts + uvi-policy-contracts   (later, optional, additive)
RA-owned SubjectContext (PR #1425)  ◀── referenced by governance-contracts AssessedSystemBinding (once ratified)
```

Invariants: **every arrow points at a neutral-contract package**; `agent-value-readiness` does **not** import `governed-value`; `governed-value` does **not** import `agent-value-readiness`; neither imports the other's internals; all cross-package communication uses neutral contracts. The benchmark registry depends only on `governance-contracts`. No leaf imports a Policy Authority internal — policies arrive as signed, digest-bound artifacts.

## 22. Compatibility boundary for `governed-value` 0.2.0 (D-17)

`governed-value` 0.2.0 and PR #1426 remain **unchanged and independent**. Compatibility projection (documentation only):

- `EvidenceStatus.REPORTED → (SourceBasis.REPORTED, TransformationMethod.DIRECT)`;
- `AuthorityStatus.UNVERIFIED → (AttestationStatus.UNATTESTED, VerificationStatus.UNVERIFIED)`;
- current effect classification `→ AttributionStatus.NOT_ATTRIBUTED`.

The kernel remains an experimental downstream calculation engine over caller-reported, unverified inputs, emitting exactly this weakest cell. Adoption of the four axes and `FinancialValuation`/`ValuationEvidenceManifest` is **additive** and behavior-preserving. Migrating its `DomainProfile`/`GeographyProfile` to policy references is a **future, separately-reviewed breaking change**, explicitly out of GV-2C/GV-2E/GV-3R.

## 23. Security and anti-gaming invariants

1. **No caller-elevated evidence.** No caller-supplied label elevates any of the five axes (D-8); elevation requires provenance + method + authority.
2. **Fail closed on policy trust.** Reference implementations fail closed on unsigned/unapproved/expired/revoked/superseded/digest-mismatched policy or benchmark artifacts (D-1, D-3, D-16); no silent substitution of an expired/revoked/superseded benchmark (D-3).
3. **Mandatory gates are non-waivable** (D-6); no control/waiver/ROI/composite/forecast/preference converts a mandatory `FAIL` into readiness.
4. **Composite is advisory** (D-5); it can never change a readiness tier.
5. **Determinations bind exact identity + digests** — `AssessedSystemBinding`/`SystemManifest` and benchmark/policy references bind ids, versions, and content digests (D-3, D-14), preventing swap/replay/misattribution.
6. **Execution ≠ effect ≠ attribution ≠ verification ≠ value** (D-10); no artifact is promoted across those boundaries by renaming.
7. **Conservative valuation headline** (D-12); a verified component never elevates a weaker required component.
8. **Synthetic is evaluation-only** (D-9); never sufficient for realized observed/attributed/verified ROI.
9. **Readiness is not authority** (D-4); the engine produces an advisory determination and mints no runtime or deployment authority.
10. **Reference producers never self-attest/self-verify/self-approve** — attestation, verification, and policy approval require the respective authority; a producer cannot elevate its own outputs.

## 24. Deferred forecasting and post-deployment integration

Deferred to separate, reviewed phases (not this ADR): the Value Forecasting engine (opportunity sizing, scenario construction, realization probability, uncertainty ranges); post-deployment `ObservedAdoption` and observed-effect integration; the producers/wiring of `AttributionAssessment` and `VerificationAssessment`; `governed-value`'s adoption of the four axes and its `DomainProfile`/`GeographyProfile` → policy-reference migration.

## 25. Small, reviewable implementation milestones

1. **M-2E.1** — evidence axes + `MetricClaim`/`MetricObservation` + `EvidenceReference`/`EvidenceProvenance` + `BenchmarkReference` + `AssessmentWindow`/`ForecastHorizon`/`PopulationSlice`/`ConfidenceBasis` **contract shapes** in `governance-contracts` (with axis-rule tests). No engine.
2. **M-2C.1** — `AssessmentContext` + `GeographyPolicy`/`DomainPolicy`/`IntendedOutcomePolicy`/`ValuationPolicy`/`ReadinessPolicy` **schemas + IR** in `uvi-policy-contracts` (envelope, effective period, supersession, revocation, digest binding; **fail-closed on untrusted artifacts**). No authority minted.
3. **M-2C.2** — internal **benchmark registry** (immutable versions, digest-bound resolution, no silent substitution); Policy-Authority-governed admission recorded as a dependency.
4. **M-3R.1** — `agent-value-readiness` contracts: `ReadinessGate`/`GateResult`/`GateStatus`/`ReadinessPolicy`/`ConditionSet` + `ReadinessTarget` + minimal `ReadinessDetermination` envelope.
5. **M-3R.2** — the **target-relative state machine + non-compensatory gate evaluator** (§6–§9), with adversarial tests (mandatory `FAIL` cannot be waived; composite cannot change tier; expired control invalidates conditional readiness).
6. **M-3R.3** — `IntelligenceFitness`/`CapabilityReadiness`/`AdoptionReadiness` catalogs + `AssessedSystemBinding` wiring; conformance/isolated-wheel verifier (mirroring `governed-value`).
7. **M-VAL.1** *(governed-value, later, additive)* — `FinancialValuation` + `ValuationEvidenceManifest` + conservative headline rules, consuming eligibility from `IntendedOutcomePolicy`/`ValuationPolicy`.

Each milestone is independently reviewable, fails closed by default, and mints no authority.

## 26. Unresolved issues (implementation detail only — no boundary/ownership change)

1. ~~**Policy Authority for UVI value-policies**~~ — **RESOLVED (2026-08-16)** by [`ADR_UGENCE_POLICY_AUTHORITY.md`](ADR_UGENCE_POLICY_AUTHORITY.md): the **platform-wide Ugence Policy Authority** owns approval **verification**, signing/issuance, exact registration/resolution, and policy-version revocation, and **UVI is its first policy-family adapter**. It stays an **external platform dependency** of UVI engines. It remains **DEFERRED as implementation** — no such package exists yet, and building it is a **platform dependency milestone**, not a UVI engine milestone (D-1, D-16, §19).
2. **RA-owned `SubjectContext` dependency** — PR #1425 is draft-only; owner to ratify/merge before UVI references `canonical_subject_context_ref` (D-14).
3. **`SystemManifest` home** — `governance-contracts` vs `uvi-policy-contracts` vs an assessed-system contract, and confirmation it is a non-competing additive artifact (D-14, §20).
4. **Producers of `AttributionAssessment` / `VerificationAssessment`** — a new attribution capability / DA extension, and a Runtime-Assurance extension vs new; whether `PARTIALLY_ATTRIBUTED` needs a DA reconciliation-contract extension (D-10).
5. **Benchmark registry home & attestation cadence** (D-3).
6. **`agent-value-readiness` placement** — `packages/capabilities/*` (provisional, D-4) vs top-level leaf.
7. **`FinancialValuation` eligibility & classification-stamping** location — `IntendedOutcomePolicy` vs a distinct `ValuationPolicy` (D-11).
8. **Whether `SourceBasis.SYNTHETIC` is admitted beyond readiness** (D-9).
9. **`governance-contracts` `contract_version` bump scope** and the sequencing of evidence axes relative to policy/context shapes.

None of these alters the ratified ownership or semantic boundaries (D-1…D-18); they are implementation details for the milestones in §25.

---

*Design-only ADR. No runtime behavior, no authority minted, no contracts or packages created, and no change to `governed-value` 0.2.0 or PR #1426. Implementation requires separate reviewed phases.*
