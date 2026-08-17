# ugence-governance-contracts

The canonical, neutral, reusable **governance contract layer** for Ugence — a
**leaf** package that capabilities and the provider framework depend on, so they
never have to depend on each other.

- **Distribution:** `ugence-governance-contracts`
- **Namespace:** `ugence_governance_contracts`
- **Version:** 0.1.0 · **Contract version:** 1.0.0
- **Dependencies:** Python standard library only (no third-party, no other Ugence package)
- **Typing:** fully type-annotated; ships a PEP 561 `py.typed` marker
- **Ownership / maturity:** extracted verbatim from the frozen `governance_providers`
  contract core; stable, synthetic-neutral, no semantic change.
- **Public API snapshot:** `public_api.json` (machine-readable; asserted equal to the
  installed package by `tests/packaging/test_public_api.py`).

## What's in it

The provider-neutral contracts that describe *what a governance provider is asked
and what it returns*, independent of any concrete implementation:

| Group | Symbols |
|---|---|
| Requests / results | `ActionGovernanceRequest/Result`, `AssertionGovernanceRequest/Result`, `ExecutionDispatchRequest/Result`, `ExecutionObservation` |
| Authority / effect | `ActionGovernanceOutcome`, `AssertionCoverage`, `ExecutionBusinessOutcome` |
| Provider protocols | `Provider`, `BaseProvider`, `ActionGovernanceProvider`, `AssertionGovernanceProvider`, `ExternalExecutionProvider` |
| Provider metadata | `ProviderKind`, `ProviderDescriptor`, `ProviderCapabilities`, `ProviderCompatibility`, `ProviderHealth` |
| Lifecycle | `ProviderLifecycleState` |
| Errors | `FailureClass`, `ProviderError` (+8 subclasses) |

## Authority boundary

These are neutral **contracts**, not authority. The meaning of each result
(advisory vs binding, authorization vs clearance vs execution) is owned by the
capability that produces it. This package changes **no** authority boundary:
assertion governance stays advisory, action governance authorizes, execution stays
separate, and no result becomes "more binding" by living here.

## Install & use

```bash
python -m build packages/governance-contracts
pip install dist/ugence_governance_contracts-0.1.0-py3-none-any.whl   # no index needed
```

```python
from ugence_governance_contracts.api import (
    ActionGovernanceRequest, ActionGovernanceOutcome, ProviderKind)

req = ActionGovernanceRequest(action_type="deploy", actor="agent://x")
```

Independent-distribution proof:

```bash
python packages/governance-contracts/verify_governance_contracts_distribution.py
```

## Neutral UVI evidence contracts (GV-2E-a)

Additive, neutral, cross-package **evidence vocabulary** for the future Ugence
Value Intelligence engines (Agent Value Readiness, Value Forecasting, Governed
Value Verification). **Contracts and structural invariants only** — this is *not*
an evidence authority, attribution engine, verification engine, policy authority,
readiness evaluator, or financial calculator. It grants no action permission and
mints no authority. No ROI, readiness, or authorization behavior is implemented.

**Five orthogonal evidence dimensions** (never one linear maturity score):

| Axis | Values |
|---|---|
| `SourceBasis` | `REPORTED` · `OBSERVED` · `SYNTHETIC` · `MIXED` |
| `TransformationMethod` | `DIRECT` · `CALCULATED` · `MODELED` |
| `AttestationStatus` | `UNATTESTED` · `ATTESTED` |
| `AttributionStatus` | `NOT_APPLICABLE` · `NOT_ATTRIBUTED` · `PARTIALLY_ATTRIBUTED` · `ATTRIBUTED` |
| `VerificationStatus` | `UNVERIFIED` · `VERIFICATION_FAILED` · `VERIFIED` |

Guarantees: `ATTESTED` never implies `OBSERVED`, `ATTRIBUTED`, or `VERIFIED`;
`VERIFIED` never implies `ATTRIBUTED` (and vice-versa); verification always
concerns an exact declared claim (`verified_claim_ref`).

**`MetricClaim` vs `MetricObservation`.** `MetricClaim` is the neutral value
contract capable of representing reported, observed, calculated, and modeled
values. `MetricObservation` is a **constrained observed form**: its source basis
is fixed to `OBSERVED` internally (never caller-selected), an `AssessmentWindow`
is required, a `ForecastHorizon` is structurally impossible, and constructing one
does **not** make it attested, attributed, or verified.

**Structural validation vs authority verification.** Constructors enforce
*structure* — a caller can submit a claim, but **selecting an enum value never
creates authority or proves evidence**. Stronger statuses are only constructible
when the caller supplies the corresponding authority-produced references (an
attestation reference + attester identity; an attribution assessment +
counterfactual + causal method; a verification assessment + exact claim reference
+ verifier identity + time). Actual signature/authority verification belongs to
later admission and authority milestones — a dataclass constructor performs no
cryptographic or organizational verification.

**Synthetic-evidence limits.** `SourceBasis.SYNTHETIC` requires
`usage_scope = EVALUATION_ONLY` and cannot independently support an attributed or
verified realized result.

**Neutral references.** `EvidenceReference`, `EvidenceProvenance`,
`BenchmarkReference`, `AssessmentWindow`, `ForecastHorizon`, `PopulationSlice`,
`ConfidenceBasis` — immutable, digest-bound, timezone-aware, reusing the existing
plain `tenant_id`/`subject_id` convention.

**Assessed-system identity (M-3R.3).** `AssessedSystemBinding` **is owned by this
package** (UVI ADR §20) and lives in `contracts/system_identity.py` alongside
`SystemBindingAuthenticityStatus` and `SystemIdentityContractError`. It is the
single canonical answer to *which exact system, at which version, in which
configuration, does this result describe?* — `ugence-agent-value-readiness`
**re-exports these exact objects** and defines no copy, subclass or parallel
schema. Every field is a platform-neutral primitive (`str` / `datetime`), so this
leaf needs no UVI policy shape or readiness type to define it and no dependency
cycle is possible; comparing a binding against an engine's own assessment context
is that engine's adapter responsibility.

The binding is **structural**: `authenticity_status` is a permanently
`STRUCTURAL_UNVERIFIED` property and `authenticity_verified` a permanently-`False`
property, because no ratified system-binding verifier exists. The RA-owned
canonical neutral `SubjectContext` remains a **deferred dependency** (unmerged);
it and `SystemManifest` are **not** minted here — both are referenced by opaque,
co-required ref + digest tokens.

**Compatibility.** Purely additive; `CONTRACT_VERSION` (the provider contract
surface) is unchanged at `1.0.0`; the package version advances to `0.3.0`. The
`governed-value` 0.2.0 kernel is unchanged; its compatibility mapping is
**documentation only**: `EvidenceStatus.REPORTED → SourceBasis.REPORTED +
TransformationMethod.DIRECT`; `AuthorityStatus.UNVERIFIED → AttestationStatus.UNATTESTED
+ VerificationStatus.UNVERIFIED`; current effect classification →
`AttributionStatus.NOT_ATTRIBUTED`. This mapping is **not** wired into
`governed-value` in this phase.

## Compatibility paths

The neutral contracts previously lived in `governance_providers`. Those paths still
resolve to the **same objects** (identity preserved), now through a two-hop
compatibility bridge: the `governance_providers` namespace aliases the Governance
Provider Framework's submodules, and the framework's `errors`/`lifecycle`/
`metadata`/`contracts.*` modules re-export from this package. Verified by
`tests/compatibility/test_legacy_compat.py` importing the real legacy paths and
asserting object identity:

| Legacy (compatibility period) | Canonical |
|---|---|
| `from governance_providers.api import ActionGovernanceRequest` | `from ugence_governance_contracts.api import ActionGovernanceRequest` |
| `from governance_providers.contracts import Provider` | `from ugence_governance_contracts.contracts import Provider` |
| `from governance_providers.errors import FailureClass` | `from ugence_governance_contracts.errors import FailureClass` |
| `from governance_providers.metadata import ProviderKind` | `from ugence_governance_contracts.metadata import ProviderKind` |

Removal/review target: `governance_providers` 0.2.0. See `MIGRATION.md`.

## Known limitations / deferred

This phase is a **physical** extraction only. Known platform-contract gaps
(missing `tenant_id`/`environment_id`, no standard error *envelope*, no
idempotency/expiry *contract*, fragmented CER/audit shapes) are **documented, not
implemented** — see
`docs/migrations/governance_contracts/CONTRACT_GAPS_AND_EVOLUTION_PLAN.md`. A
versioned contract-evolution phase owns those.
