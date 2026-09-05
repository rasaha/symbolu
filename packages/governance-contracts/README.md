# ugence-governance-contracts

The canonical, neutral, reusable **governance contract layer** for Ugence — a
**leaf** package that capabilities and the provider framework depend on, so they
never have to depend on each other.

- **Distribution:** `ugence-governance-contracts`
- **Namespace:** `ugence_governance_contracts`
- **Version:** 0.5.0 · **Contract version:** 1.0.0
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
| Audit correlation (G4) | `AuditReference`, `AuditContractError` |

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

**Canonicalization (0.3.1).** Every timezone-aware datetime in the binding is
normalized to UTC before serialization, so equal bindings are byte-equal:
`2026-08-17T10:00:00+00:00`, `2026-08-17T15:30:00+05:30` and
`2026-08-17T06:00:00-04:00` produce identical `canonical_bytes()` and one
`canonical_digest()`. **Naive datetimes are rejected** — a value with no offset
names no instant, and UTC is never assumed for it. A genuinely different instant
still changes both. This fixes an equality/digest inconsistency in which equal
bindings produced different digests; no readiness classification or authorization
semantics changed. Digests previously recorded for a **non-UTC-offset**
representation now resolve to their UTC-normalized value — there is no
legacy-digest fallback or dual acceptance rule.

**Compatibility.** Purely additive; `CONTRACT_VERSION` (the provider contract
surface) is unchanged at `1.0.0`; the package version advances to `0.3.1`. The
`governed-value` 0.2.0 kernel is unchanged; its compatibility mapping is
**documentation only**: `EvidenceStatus.REPORTED → SourceBasis.REPORTED +
TransformationMethod.DIRECT`; `AuthorityStatus.UNVERIFIED → AttestationStatus.UNATTESTED
+ VerificationStatus.UNVERIFIED`; current effect classification →
`AttributionStatus.NOT_ATTRIBUTED`. This mapping is **not** wired into
`governed-value` in this phase.

## Neutral idempotency and validity contracts (G7, G8)

Additive, neutral vocabulary for two questions every execution seam asks and
the frozen provider contracts left to free strings and ad-hoc fields: *is this
the same logical action again?* and *is this artifact still good?* **Contracts
and structural invariants only** — neither family is a deduplication store, a
reservation ledger, a clock, a verifier or an authority. Atomic one-time
reservation and replay protection belong to the execution ledger that Action
Clearance's phase G names; these contracts give it one vocabulary.

**Idempotency (G7)** — `IdempotencyKey` is the identity of one logical action:
the caller's `key`, the coordinates its `IdempotencyScope` names, and an opaque
`partition` token reserved for the tenant/environment coordinate (G1, G2).

| `IdempotencyScope` | identity |
|---|---|
| `GLOBAL` | `key` |
| `ACTOR` | `actor` + `key` |
| `TARGET_RESOURCE` | `target_resource` + `key` |
| `ACTOR_AND_TARGET` | `actor` + `target_resource` + `key` |

A coordinate the scope does not name must be empty, so one identity has exactly
one `canonical_digest()`. A producer that adopts the contract places that digest
in the existing free-string `idempotency_key` field, which makes the field
scope-bound and fixed-width without changing its type or default.
`IdempotencyResolution` reports how a receiver classified the identity:
`FIRST`, `DUPLICATE` (then `duplicate_of` names the original and is required) or
`UNKNOWN`, which is never first and never determinate — a consumer that cannot
tell whether it has already acted fails closed.

**Validity (G8)** — `Validity` is a half-open `[issued_at, expires_at)` window
with an optional `stale_after` soft bound strictly inside it. `status_at(as_of)`
returns exactly one `ValidityStatus` by precedence: `NOT_YET_VALID`, `EXPIRED`,
`STALE`, `FRESH`. Staleness is **derived at an explicit instant, never stored**
and never read from a clock; every instant must be timezone-aware and a naive
one is rejected. Instants canonicalize in UTC exactly as `AssessedSystemBinding`
does. Mapping to the frozen fields is documentation only:
`ActionGovernanceResult.expiry == validity.expires_at` and
`ActionGovernanceRequest.authorization_expired == not validity.is_valid_at(as_of)`.

## Neutral audit reference (G4)

**Audit reference (G4)** — `AuditReference` is a digest-bound pointer to **one
entry in one audit store**: `audit_id`, `tenant_id`, `store_ref`, `entry_ref`,
`entry_digest`, plus an optional `correlation_id` and a `recorded_at` that must be
timezone-aware when present. It exists so a governance record can cite the audit
entry that explains it, and so two records citing one entry can be recognised as
doing so — `points_to_same_entry()` compares the location, `agrees_with()` also
compares the digest, which is how a consumer detects that one of them saw
different content.

**It does not unify the audit stores.** The gap statement named three shapes; the
platform now has more — the kernel's `AuditRepository` port, a durable hash-linked
log in storygraph, and separate append-only event tables in policy-authority,
risk_authority, execution-reservation, approval-workflow and authority-directory.
This contract gives them one way to be *pointed at*, so entries correlate across
stores without any store changing, merging or moving. Convergence is a migration
this contract deliberately does not attempt.

Three things it deliberately does not carry: the entry **body** (a reference that
embedded the record would be a second copy of the audit — the fragmentation G4
describes, not a fix for it); an **event-type vocabulary** (Decision Authority's
`AuditEventType` is frozen at 1.0.0 and owns those names); and a **chain head or
previous-entry hash** (hash-linking is each store's own property, and requiring it
here would oblige every store to change). It is not a log, a sink, a hash chain, a
verifier or an authority.

**The evidence half of G4 was already closed.** D-4 names an `AuditRef`/`EvidenceRef`
pair, but `EvidenceReference` — digest-bound, tenant- and subject-scoped, with a
`supersedes_ref` — already is that evidence pointer. No second evidence reference is
minted, and a test asserts only one exists.

**Why new families rather than new fields.** The provider dataclasses' fields,
defaults, constructor signatures and serialized forms are pinned byte-for-byte
by the serialization-equivalence tests, and any key added to their `asdict`
output would silently move every fingerprint a consumer computes over an
existing request. So `CONTRACT_VERSION` stays `1.0.0`; the package version
advances to `0.4.0`, and to `0.5.0` for G4.

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

This phase is a **physical** extraction only. Of the platform-contract gaps
in `docs/migrations/governance_contracts/CONTRACT_GAPS_AND_EVOLUTION_PLAN.md`,
**G7 (idempotency) and G8 (validity) landed in 0.4.0**, and **G4's contract half
(the neutral audit reference) landed in 0.5.0**, all as additive neutral families.
G4's *unification* half did not: six durable audit stores plus the kernel port stay
exactly where they are, and converging them is an unscoped migration. The rest
(missing `tenant_id`/`environment_id`, no standard error *envelope*, G5 CER
fragmentation, no cross-product result envelope) remain **documented, not
implemented**; the versioned contract-evolution phase owns them.
