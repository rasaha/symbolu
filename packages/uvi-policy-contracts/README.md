# ugence-uvi-policy-contracts

The narrow, internal **technical** package that holds the immutable contract
*shapes* for Ugence Value Intelligence (UVI) **governed assessment context** and
**policy artifacts** — the schema layer of milestone **M-2C.1** in the UVI ADR.
It is **not** a customer-facing module (D-2, D-18).

- **Distribution:** `ugence-uvi-policy-contracts`
- **Namespace:** `ugence_uvi_policy_contracts`
- **Version:** 0.1.0
- **Depends on:** Python standard library **+ `ugence-governance-contracts>=0.2.0`** (the neutral leaf) — nothing else
- **Typing:** fully type-annotated; ships a PEP 561 `py.typed` marker
- **Public API snapshot:** `public_api.json` (asserted equal to the installed package by `tests/packaging/test_public_api.py`)

## What this is — and is not

**Is:** immutable, frozen dataclass **contract shapes** with **structural
invariants**, per ADR
`docs/architecture/ADR_UGENCE_VALUE_INTELLIGENCE_GV2C_GV2E_GV3R.md` (D-2, D-13,
D-15, §15, §20, milestone M-2C.1).

**Is not:** a Policy Authority; policy approval / signing / issuance / revocation;
a benchmark registry; a readiness evaluator or state machine; a `ConditionSet`
executor; a forecasting engine; an attribution or verification engine; a
financial calculator; or any `governed-value` integration. Selecting a value
here **mints no authority** — trust evaluation (signature, approval, revocation,
freshness) belongs to the Policy Authority and later admission milestones, which
are explicitly out of scope. `AssessedSystemBinding` / `SubjectContext` (RA-owned,
PR #1425, unmerged) are a **deferred dependency** and are not defined here.

## What's in it

| Group | Symbols |
|---|---|
| Identity / references | `PolicyArtifactMetadata`, `PolicyReference` |
| Thresholds / gates | `GovernedThreshold`, `PolicyGate` |
| Policy families | `GeographyPolicy`, `DomainPolicy`, `IntendedOutcomePolicy`, `ValuationPolicy`, `ReadinessPolicy`, `ComponentEvidenceRequirement` |
| Assessment context | `AssessmentContext` |
| Enums | `PolicyFamily`, `PolicyScope`, `PolicyLifecycleState`, `RequirementClass`, `ComparisonOperator`, `GateCategory`, `ReadinessTarget`, `ValueComponent`, `HeadlineClassificationPolicy`, `MissingComponentBehavior`, `AssessmentPurpose` |
| Error | `PolicyContractError` |

## Structural invariants enforced

- **Envelope identity + no floating references.** Every `PolicyReference` and
  `PolicyArtifactMetadata` binds `policy_id + family + version + content_digest`;
  a reference with no content digest is rejected (ADR §23 invariant 5).
- **Literal XOR benchmark.** A `GovernedThreshold` is either an immutable policy
  literal **or** a `BenchmarkReference` — never both, never neither (ADR §15,
  D-3, §13). A threshold is a policy artifact, not a metric claim: it carries no
  evidence axes.
- **No caller multipliers (anti-gaming).** No policy shape has any field capable
  of expressing a caller-controlled ROI/value multiplier. Geography expresses
  currency, jurisdiction, benchmark references, and thresholds — never a scalar
  knob (ADR §23 invariant 1, D-13). A test asserts the absence structurally.
- **Mandatory ≠ conditional.** A `MANDATORY` (or `ADVISORY`) `PolicyGate` can
  never be marked `conditionally_compensable`; only a `CONDITIONAL` gate may be
  (ADR §8, D-6). `ReadinessPolicy.composite_is_advisory` must be `True` — a
  policy cannot declare the composite binding (D-5).
- **Mandatory Geography / Domain / Intended-Outcome.** An `AssessmentContext`
  always binds those three references, each of the correct family; Valuation and
  Readiness references are optional (ADR §6 precondition, §15).
- **Cross-tenant rejection.** A `TENANT`-scoped reference must belong to the
  context's tenant; `GLOBAL` references are always admissible.
- **Fail-closed binder.** `AssessmentContext.bind_policies(...)` builds a context
  from full artifacts and rejects any that is not `APPROVED_ACTIVE`, that belongs
  to another tenant, or (when `as_of` is given) that is outside its effective
  period. This is a *structural* fail-closed gate, not a trust check.
- **Deterministic digests.** Every shape exposes `canonical_digest()` — a
  sorted-key sha-256 over its canonical serialization, matching the
  governance-contracts evidence discipline.

## Reuse of the neutral evidence vocabulary (GV-2E-a)

Rather than mint competing types, this package **reuses** `governance-contracts`:
`BenchmarkReference` (threshold benchmarks, cost/domain benchmarks),
`AssessmentWindow` (context temporal binding), and the evidence axes
`SourceBasis` / `AttributionStatus` / `VerificationStatus` (as the evidential
standard a `ComponentEvidenceRequirement` demands per value component).

## Placement note (AssessmentContext)

The ADR §20 ownership table lists `AssessmentContext` among the neutral seams. It
is placed **here** for M-2C.1 because it references `PolicyReference` — a
UVI-policy concept — so a neutral leaf could not hold it without a reverse
dependency on UVI policy shapes. Every dependency arrow still points at a
neutral-contract package (ADR §21); `governed-value` and `agent-value-readiness`
are never imported.

## Install & use

```bash
python -m build packages/uvi-policy-contracts
pip install --find-links dist ugence-uvi-policy-contracts   # resolves ugence-governance-contracts
```

```python
from ugence_uvi_policy_contracts.api import (
    AssessmentContext, GeographyPolicy, DomainPolicy, IntendedOutcomePolicy)
```

Independent-distribution proof (builds both wheels, installs `--no-index`):

```bash
python packages/uvi-policy-contracts/verify_uvi_policy_contracts_distribution.py
```

## Deferred / out of scope

Policy Authority (approval/signing/issuance/revocation), benchmark registry,
readiness evaluator + target-relative state machine, `ConditionSet` execution,
value forecasting, attribution/verification engines, financial valuation +
`ValuationEvidenceManifest` (owned by `governed-value`), and
`SubjectContext`/`AssessedSystemBinding` (RA-owned, PR #1425). See ADR §24–§26.
