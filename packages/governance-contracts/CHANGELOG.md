# Changelog — ugence-governance-contracts

## [0.4.0] — neutral idempotency (G7) and validity (G8) contracts (additive)

**Additive, backward-compatible.** No existing public symbol, field, enum value,
default, constructor signature, serialization or authority meaning changed.
`CONTRACT_VERSION` (the **provider** contract surface) is **unchanged at
`1.0.0`** — as for the evidence and assessed-system identity families, these are
new additive *neutral contract families* that do not touch the provider
contract. Only the package `__version__` advances, to `0.4.0`. Remains a
stdlib-only leaf. Closes gaps **G7** and **G8** of
`docs/migrations/governance_contracts/CONTRACT_GAPS_AND_EVOLUTION_PLAN.md`,
sequenced first by
`docs/architecture/ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md`.

### Added — `contracts/idempotency.py` (G7)
- **`IdempotencyScope`** — `GLOBAL`, `ACTOR`, `TARGET_RESOURCE`,
  `ACTOR_AND_TARGET`: what a key is unique within, declared, never inferred.
- **`IdempotencyKey`** — the identity of one logical action: `key`, the
  coordinates the scope names, and an opaque `partition` token reserved for the
  tenant/environment coordinate that G1/G2 will name. A coordinate the scope
  does not name must be empty, so one identity has exactly one
  `canonical_digest()`. Keys and coordinates are stored stripped.
- **`IdempotencyDisposition`** and **`IdempotencyResolution`** — `FIRST`,
  `DUPLICATE`, `UNKNOWN`; `duplicate_of` is required exactly when the
  disposition is `DUPLICATE` and forbidden otherwise. `UNKNOWN` is never first
  and never determinate.
- **`IdempotencyContractError`** — structural rejections, subclassing
  `ValueError`, mirroring `EvidenceContractError`.

### Added — `contracts/validity.py` (G8)
- **`Validity`** — half-open `[issued_at, expires_at)` window with an optional
  `stale_after` soft bound strictly inside it; `expires_at` absent means no hard
  expiry. `status_at(as_of)` returns one **`ValidityStatus`** by precedence
  (`NOT_YET_VALID`, `EXPIRED`, `STALE`, `FRESH`); `is_valid_at`, `is_fresh_at`,
  `is_stale_at`, `is_expired_at` derive from it. Instants must be
  timezone-aware and canonicalize in UTC, exactly as `AssessedSystemBinding`.
- **`ValidityContractError`** — structural rejections, subclassing `ValueError`.

### Decided — staleness is derived, not stored
The evolution plan sketched `Validity{issued_at, expires_at, stale}`. A stored
`stale` boolean would itself go stale the moment it was written, so the contract
carries the bound (`stale_after`) and derives the answer at a caller-supplied
`as_of`. No clock is read anywhere in either module; a test asserts it.

### Decided — new families, not new fields on the frozen provider contracts
The plan allowed "additive optional fields" too. They were not used: the
provider dataclasses' fields, defaults, constructor signatures, `repr` and
`asdict` output are pinned byte-for-byte by the serialization-equivalence
baseline, and adding a key to a request's `asdict` output would silently move
every fingerprint a consumer computes over an existing request. The binding is
by value instead: a producer places `IdempotencyKey.canonical_digest()` in the
existing free-string `idempotency_key` field, and `ActionGovernanceResult.expiry`
/ `ActionGovernanceRequest.authorization_expired` map to `validity.expires_at` /
`not validity.is_valid_at(as_of)`. The legacy `governance_providers` shim is
untouched; it re-exports the provider surface only, as it did for the evidence
and identity families.

### What these contracts are not
Not a deduplication store, a reservation ledger, replay protection, a retention
window, a clock, a revocation service or an authority. Atomic one-time
reservation belongs to the execution ledger that Action Clearance's phase G
names; these contracts are its vocabulary.

## [0.3.1] — assessed-system binding instants canonicalize in UTC (fix)

**Patch.** No public symbol, field, enum value, default or authority meaning
changed, nothing was added to the curated API, and `CONTRACT_VERSION` (the
**provider** contract surface) is **unchanged at `1.0.0`** — this corrects a
defect inside an existing contract rather than changing a surface. Only the
package `__version__` advances, to `0.3.1`. Remains a stdlib-only leaf.

### Fixed — equality and digest disagreed about timezone-aware instants
Two timezone-aware datetimes naming the **same instant** are equal in Python and
hash alike, so two `AssessedSystemBinding` values differing only in the offset
their `effective_from` / `effective_to` were written with are the *same* binding.
Canonicalization did not agree: it serialized each instant with the offset it
arrived in, so equal bindings produced **three different canonical byte
sequences and three different digests**.

That is an inconsistency in an identity fingerprint the whole platform compares
on — a binding could fail a digest comparison against itself. Every aware
datetime participating in canonicalization is now re-expressed in UTC
(`astimezone(timezone.utc)`, pure arithmetic) immediately **before** the existing
sorted-key JSON serialization, which is otherwise untouched. So

| written as | canonicalizes as |
|---|---|
| `2026-08-17T10:00:00+00:00` | `2026-08-17 10:00:00+00:00` |
| `2026-08-17T15:30:00+05:30` | `2026-08-17 10:00:00+00:00` |
| `2026-08-17T06:00:00-04:00` | `2026-08-17 10:00:00+00:00` |

all three yield identical canonical bytes and one digest. The invariant now
holds unconditionally:

```python
if binding_a == binding_b:
    assert binding_a.canonical_bytes() == binding_b.canonical_bytes()
    assert binding_a.canonical_digest() == binding_b.canonical_digest()
```

A **genuinely different instant still changes** the bytes and the digest, down to
the microsecond, and every non-datetime coordinate — tenant, subject, context,
system, version, configuration, manifest — separates bindings exactly as before.

### Added — `AssessedSystemBinding.canonical_bytes()`
A method on the existing class, exposing the exact bytes `canonical_digest()`
hashes so a consumer can verify the digest independently. **No new public
contract symbol**: `api.__all__` is unchanged and no export was added.

### Unchanged — naive datetimes are still rejected
A value with no offset names no instant, so UTC is never assumed for it. Naive
values are refused at construction *and* again at canonicalization, and the
rejection is a `SystemIdentityContractError`, not a silent default.

### Compatibility — honest about what moves
Bindings already expressed in UTC keep their **exact** pre-correction canonical
bytes and digest: normalizing a UTC instant to UTC is the identity, and merged-
default byte and digest literals are pinned in the tests to prove no drift. A
digest previously recorded for a binding written with a **non-UTC offset** does
change — to the UTC-normalized value it should always have had. There is
deliberately **no** legacy-digest fallback, dual acceptance rule, alias or
translation layer: this is one deterministic canonicalization, not a second
protocol.

Canonicalization consults no system clock, locale or environment; an AST guard
asserts this over the module, including that `astimezone` is never called in its
local-timezone-inferring zero-argument form.

### Hardened — the distribution verifier removes stale build output
`verify_governance_contracts_distribution.py` now removes the package-local
`build/` tree immediately before building, so a module deleted from source
cannot be resurrected from `build/lib` into a fresh wheel. The removal target is
`<resolved package root>/build` and nothing else — never a broad path, an
environment variable or a repository-root walk — and a symlink there is refused
rather than followed. The verifier continues to inspect the completed **wheel**,
and now asserts it defines `AssessedSystemBinding` exactly once. A seeded
regression test plants the duplicate definition in `build/lib`, demonstrates an
unclean build really does ship it, then proves the hardened path does not.

## [0.3.0] — neutral assessed-system identity (additive)

**Additive, backward-compatible.** No existing public symbol, field, enum value,
default, serialization or authority meaning changed. `CONTRACT_VERSION` (the
**provider** contract surface) is **unchanged at `1.0.0`** — exactly as for the
GV-2E-a evidence family, this is a new additive *neutral contract family* that
does not touch the provider contract. Only the package `__version__` advances,
to `0.3.0`. Remains a stdlib-only leaf.

### Added — `contracts/system_identity.py`
- **`AssessedSystemBinding`** — the single canonical, platform-neutral answer to
  *which exact system, at which version, in which configuration, does this result
  describe?* Frozen, all-scalar, digest-bound. Binds binding id, tenant, subject,
  assessment-context id **and** its exact canonical digest, system id, system
  version, configuration id, configuration digest, three opaque deferred
  references, and an optional **half-open** `[effective_from, effective_to)`
  period.
- **`SystemBindingAuthenticityStatus`** — one member, `STRUCTURAL_UNVERIFIED`,
  because exactly one thing is provable today.
- **`SystemIdentityContractError`** — structural rejections, subclassing
  `ValueError`, mirroring `EvidenceContractError`.

### Why it lives here (UVI ADR §20)
The ADR's type-by-type ownership table places `AssessedSystemBinding` in
**governance-contracts** as a neutral seam. Keeping it here is what lets every
engine bind the *same* system identity instead of minting a parallel one:
`ugence-agent-value-readiness` (>= 0.4.0) **re-exports these exact objects**, so
`readiness_api.AssessedSystemBinding is governance_api.AssessedSystemBinding` —
one class identity, one canonical serialization, one digest. No copy, subclass,
adapter or translation model exists anywhere.

### No dependency cycle is possible
Every binding field is a platform-neutral primitive (`str` / `datetime`). This
leaf imports **no** UVI policy shape, readiness enum, indicator type, assessment
context, authority or risk package, so
`governance-contracts → uvi-policy-contracts → governance-contracts` is
structurally impossible rather than merely avoided. Comparing a binding against
an engine's own `AssessmentContext` is the **engine's** adapter responsibility,
performed against these stable ids and digests. The leaf-dependency test names
the higher-level packages explicitly so a regression fails as a test, not as an
import error.

### What a binding proves — and does not
It proves **internal consistency and digest-bound identity**: two different
systems, versions, configurations, tenants, subjects, contexts or manifest
digests can never share a `canonical_digest()`, so a result bound to one binding
is mechanically detectable when replayed under another.

It proves **nothing else** — not that the named system was ever deployed, that
`configuration_digest` was computed over the real configuration, that
`system_manifest_ref` resolves to anything, or that any authority attested any of
it. `authenticity_status` is a permanently `STRUCTURAL_UNVERIFIED` **property**
and `authenticity_verified` a permanently-`False` **property**; neither is a
settable field, and raising either requires a ratified system-binding verifier
that no merged contract defines.

### Nothing unratified was minted
`SystemManifest`'s home is an open owner decision (UVI ADR §26.3) and the
RA-owned `SubjectContext` is unmerged (D-14, §26.2). Neither is defined here:
both are carried as **opaque, co-required ref + digest tokens**, so a ratified
contract can be pointed at later with no shape change. No environment
enumeration is invented either.

## [0.2.0] — GV-2E-a neutral UVI evidence contracts (additive)

**Additive, backward-compatible.** No existing public field, enum value, default,
serialization, or authority meaning changed. `CONTRACT_VERSION` (the provider
contract surface) is **unchanged at `1.0.0`**; only the package `__version__`
advances to `0.2.0`. Remains a stdlib-only leaf with no dependency on any UVI leaf.

### Added
- `contracts/evidence.py`: the neutral UVI evidence vocabulary.
  - Five **orthogonal** axes: `SourceBasis`, `TransformationMethod`,
    `AttestationStatus`, `AttributionStatus`, `VerificationStatus` (plus
    `EvidenceUsageScope`). No numeric ordering / no single maturity score.
  - Immutable, digest-bound, timezone-aware references: `EvidenceReference`,
    `EvidenceProvenance`, `BenchmarkReference`, `AssessmentWindow`,
    `ForecastHorizon`, `PopulationSlice`, `ConfidenceBasis`.
  - `MetricClaim` (neutral value: reported/observed/calculated/modeled) and
    `MetricObservation` (constrained OBSERVED form, `AssessmentWindow` required,
    `ForecastHorizon` impossible). `EvidenceContractError` for structural
    rejections (subclasses `ValueError`).
  - Structural invariants: CALCULATED/MODELED require input evidence (+
    calculation/model reference); ATTESTED/ATTRIBUTED/VERIFIED require their
    authority-produced references; SYNTHETIC is `EVALUATION_ONLY` and cannot be
    attributed/verified; cross-tenant/cross-subject evidence mixing, duplicate
    references, malformed digests, and invalid time windows are rejected. Caller
    enum labels alone never satisfy the requirements.
- Curated public surface extended in `api.py` / top-level `__init__` /
  `public_api.json`; comprehensive `tests/contract/test_evidence_contracts.py`;
  distribution verifier extended with an evidence smoke-check.

### Non-goals (this phase)
- No evidence authority, attribution engine, verification engine, policy
  authority, readiness evaluator, or financial calculator; no runtime
  authorization. `AssessedSystemBinding`/`SubjectContext` are deferred (RA-owned,
  unmerged) and intentionally excluded. `governed-value` 0.2.0 is unchanged; its
  compatibility mapping is documentation only.
  *(Historical, accurate as of 0.2.0 — `AssessedSystemBinding` is **owned by this
  package** as of 0.3.0 below, per UVI ADR §20. `SubjectContext` remains deferred.)*

## [Unreleased] — package hardening (audit follow-up, no contract change)

Bounded packaging/CI/typing/documentation hardening from the live audit
(`docs/GOVERNANCE_CONTRACTS_LIVE_AUDIT.md`). **No contract field, enum value,
default, serialization, or authority meaning changed.**

### Added
- Scoped CI workflow `.github/workflows/governance-contracts-ci.yml` (package
  suite + GPF compatibility surface, isolated wheel install, platform-freeze).
- PEP 561 `py.typed` marker (shipped in the wheel via package-data) — the leaf is
  fully type-annotated.
- Machine-readable `public_api.json` + `tests/packaging/test_public_api.py`
  asserting the documented API equals the actual package surface.

### Changed
- `verify_governance_contracts_distribution.py` now also asserts `py.typed` ships
  in the wheel and is installed.
- README: note typing support, the public-API snapshot, and the precise (two-hop)
  legacy-compatibility mechanism.

## [0.1.0] — canonical-package extraction

**Physical restructuring and packaging change with ZERO semantic change.** The
neutral governance contracts were extracted verbatim from `governance_providers`
into this canonical leaf package. All fields, defaults, enum values, verdict
names, serialization keys, canonical hashes, digests, equality, validation, and
authority meanings are **unchanged**.

### Added
- Canonical leaf package `ugence_governance_contracts` (stdlib-only) containing the
  provider-neutral request/result contracts, provider protocols, provider
  metadata, lifecycle states, and the error taxonomy.
- Curated `ugence_governance_contracts.api` public surface.
- `pyproject.toml` (independent wheel, zero third-party deps),
  `verify_governance_contracts_distribution.py` (clean-venv `--no-index` proof).
- Equivalence/compatibility/contract/leaf test suite.

### Changed
- `governance_providers` contract modules (`errors`, `lifecycle`, `metadata`,
  `contracts/*`) are now logic-free re-export shims importing from this package;
  `governance_providers.api` is byte-identical (api-snapshot hash unchanged).
- `dgm-provider-framework` wheel now depends on `ugence-governance-contracts`.
- Platform freeze re-baselined for the `governance_providers` core-tree hash only
  (a structural PATCH; no API or contract-semantic change).

### Deferred (documented, not implemented)
- Tenant/environment identity, standard error envelope, idempotency/expiry
  contracts, CER/audit unification — see the contract-gap evolution plan.
