# Changelog — ugence-governance-contracts

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
