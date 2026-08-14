# Changelog — ugence-uvi-policy-contracts

## [0.1.0] — GV-2C-a: UVI policy & assessment-context contract shapes

**New internal technical package.** Additive to the monorepo; changes no
existing package. Implements milestone **M-2C.1** of the UVI ADR
(`docs/architecture/ADR_UGENCE_VALUE_INTELLIGENCE_GV2C_GV2E_GV3R.md`): the
immutable **contract shapes** for governed assessment context and the five
first-class UVI policy families — schema + IR only, **no authority minted**.

### Added
- The five policy shapes `GeographyPolicy`, `DomainPolicy`,
  `IntendedOutcomePolicy`, `ValuationPolicy`, `ReadinessPolicy` (plus
  `ComponentEvidenceRequirement`), each embedding a `PolicyArtifactMetadata`
  envelope whose `policy_family` must match.
- Identity / references: `PolicyArtifactMetadata` (id, family, version, content
  digest, scope, asserted lifecycle state, effective period, issuer/approval/
  supersession refs) and the immutable digest-bound `PolicyReference`
  (**no floating references** — the content digest is mandatory).
- `GovernedThreshold` — an immutable **policy literal XOR** a
  `BenchmarkReference` (never both, never neither); carries no evidence axes
  (a threshold is a policy artifact, not a metric claim). `PolicyGate` — a
  declared gate enforcing the **non-waivable mandatory** invariant structurally
  (only a `CONDITIONAL` gate may be conditionally compensable).
- `AssessmentContext` — the governed binding seam: mandatory Geography/Domain/
  Intended-Outcome references (each family-checked), optional Valuation/Readiness,
  **cross-tenant rejection**, distinct-artifact check, and a **fail-closed**
  `bind_policies(...)` classmethod that rejects non-`APPROVED_ACTIVE`,
  cross-tenant, or out-of-effective-period artifacts.
- Enums: `PolicyFamily`, `PolicyScope`, `PolicyLifecycleState`,
  `RequirementClass`, `ComparisonOperator`, `GateCategory`, `ReadinessTarget`,
  `ValueComponent`, `HeadlineClassificationPolicy` (single-value conservative
  lock), `MissingComponentBehavior`, `AssessmentPurpose`. `PolicyContractError`
  (subclasses `ValueError`) for structural rejections.
- Curated `ugence_uvi_policy_contracts.api` surface; machine-readable
  `public_api.json` + `tests/packaging/test_public_api.py`; dependency-boundary
  test (`stdlib + governance-contracts` only, never a downstream leaf);
  comprehensive contract tests; isolated multi-wheel distribution verifier
  (`--no-index`, resolving the `ugence-governance-contracts` dependency from
  local find-links); PEP 561 `py.typed`.

### Reuse (no competing types)
- Depends on `ugence-governance-contracts>=0.2.0` and reuses its
  `BenchmarkReference`, `AssessmentWindow`, and the GV-2E-a evidence axes
  (`SourceBasis` / `AttributionStatus` / `VerificationStatus`) as the evidential
  standard a `ComponentEvidenceRequirement` demands. The dependency arrow points
  only at the neutral leaf (ADR §21).

### Anti-gaming
- No policy shape exposes any caller-controlled ROI/value multiplier field; the
  only monetary levers are declared currency and Policy-Authority-governed
  benchmark references. A test asserts the absence structurally (ADR §23
  invariant 1, D-13).

### Non-goals (this phase)
- No Policy Authority, approval/signing/issuance/revocation, benchmark registry,
  readiness evaluator/state machine, `ConditionSet` execution, forecasting,
  attribution/verification engine, financial valuation, or `governed-value`
  integration. `AssessedSystemBinding`/`SubjectContext` (RA-owned, PR #1425,
  unmerged) are a deferred dependency and are intentionally excluded.

### Placement note
- `AssessmentContext` is placed here (rather than in `governance-contracts`, the
  ADR §20 neutral-seam listing) because it references `PolicyReference`, a
  UVI-policy type; the neutral leaf cannot hold it without a reverse dependency.
  Every arrow still points at a neutral-contract package (ADR §21).
