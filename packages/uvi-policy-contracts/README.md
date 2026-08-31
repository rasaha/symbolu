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
are explicitly out of scope. `AssessedSystemBinding` is **owned by
`ugence-governance-contracts`** (UVI ADR §20) and is not defined here; the
RA-owned `SubjectContext` (PR #1425, unmerged) remains a **deferred dependency**
and is likewise not defined here.

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
  a reference with no content digest is rejected (ADR §23 invariant 5). The
  `content_digest` is **format/identity-validated only** (a lowercase 64-char
  sha-256) — it is *not* compared against a resolved policy body; body
  resolution and digest verification belong to a future registry (see
  *Deferred*).
- **Immutable sequences.** Every tuple-typed field is normalized to a real
  `tuple` at construction (a caller `list` is copied; `str`/`bytes`/mappings and
  non-iterables are rejected, never silently iterated element-by-element), so
  mutating a caller-owned list afterward cannot alter a constructed contract or
  its `canonical_digest()`.
- **Literal XOR benchmark.** A `GovernedThreshold` is either an immutable policy
  literal **or** a `BenchmarkReference` — never both, never neither (ADR §15,
  D-3, §13). A threshold is a policy artifact, not a metric claim: it carries no
  evidence axes. `literal_value` is an **opaque governed literal** (a portable
  string) and `governed_unit` an opaque unit label — this package *stores* them;
  it does **not** parse numbers, reject NaN/inf, or guarantee unit-compatible
  comparison. A downstream evaluator must validate numeric meaning and unit
  compatibility when it compares a threshold against a `MetricClaim`.
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
  context's tenant; `GLOBAL` references are always admissible. (Policies are
  tenant-scoped, not subject-scoped, so there is **no cross-subject** rejection —
  only cross-tenant.)
- **Fail-closed binder with mandatory evaluation time.**
  `AssessmentContext.bind_policies(...)` takes a **required, keyword-only,
  timezone-aware `as_of`** (no default; never read from the system clock, so
  binding is deterministic). It rejects any bound artifact — required *or* a
  supplied optional Valuation/Readiness — that is not `APPROVED_ACTIVE`, belongs
  to another tenant, or is outside its effective period
  (`effective_from <= as_of < effective_to`, an absent `effective_to` meaning no
  upper bound). This is a *structural* fail-closed gate, not a trust check: the
  lifecycle label and content digest remain caller-supplied structural inputs
  until a Policy Authority and registry exist.
- **`as_of` ≠ `assessment_window`.** `as_of` is *when policy applicability is
  evaluated*; `assessment_window` is *the period the assessment evidence was
  drawn from*. `as_of` is never derived from the window, and the policy effective
  period is **not** required to cover the evidence window — an older evidence
  window may legitimately be evaluated under a policy applicable at `as_of`;
  whether evidence is fresh enough is a downstream evidence/readiness rule.
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
`ValuationEvidenceManifest` (owned by `governed-value`), and the RA-owned
`SubjectContext` (PR #1425, unmerged). `AssessedSystemBinding` is **not** deferred
— it is owned by `ugence-governance-contracts` (ADR §20) and consumed by
`ugence-agent-value-readiness`. See ADR §24–§26.

Two related consistency checks are also deferred, by design:

- **Lifecycle ↔ time consistency beyond binder-time applicability.** A
  `PolicyArtifactMetadata` may carry any `lifecycle_state` alongside any
  effective period (they are caller-asserted). The binder enforces applicability
  at `as_of`; reconciling a *label* like `EXPIRED`/`SUPERSEDED` with wall-clock
  time, and authoritative revocation/supersession, is Policy-Authority work.
- **Policy-body resolution / digest verification.** `content_digest` is checked
  for format/identity only; verifying that it matches a resolved policy body is a
  registry responsibility.
