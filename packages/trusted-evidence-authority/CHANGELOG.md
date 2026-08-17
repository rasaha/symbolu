# Changelog — ugence-trusted-evidence-authority

## [0.1.0] — TEV-1: trusted evidence contracts

**New internal platform-infrastructure package.** Additive to the monorepo;
changes **no** existing package, public symbol, version or dependency. Implements
milestone **TEV-1** of
[`ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md`](../../docs/architecture/ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md)
§30 at the package home ratified in §6.2: canonical evidence identity and its
deterministic identity/lifecycle foundations — **contract shapes only, no
verifier, no authority minted**.

### Added

* **Canonical evidence identity.** `CanonicalEvidenceIdentity` binding every
  ratified evidence-side coordinate of ADR §9 — identifier, type, schema
  (id + version), content digest, producer and distinct-issuer identity,
  observation instant or half-open window, collection instant, tenant, assessment
  context reference + digest, subject reference, assessed-system binding
  reference + digest, declared purpose and usage scope, provenance chain and
  ordered custody references, asserted lifecycle state, the geography / domain /
  intended-outcome applicability triple, and a half-open validity interval.
  Every coordinate participates in the digest, so cross-tenant, cross-system,
  cross-context and cross-purpose/scope replay is mechanically detectable
  (§26.5). Nested shapes: `EvidenceSchemaRef`, `EvidenceObservation`,
  `EvidenceScopeBinding`, `EvidenceProvenanceChain`, `ApplicabilityCoordinate`.
* **One canonicalization path and one digest path.** `canonical_bytes` /
  `canonical_digest`, framed with `TRUSTED_EVIDENCE_CANONICALIZATION_VERSION` and
  `EVIDENCE_IDENTITY_DIGEST_DOMAIN` plus the contract type name, so two contract
  types can never collide. Sorted-key tight-separator UTF-8 JSON; total
  deterministic field inclusion; explicit `null` for `None`; UTC-normalized
  datetimes preserving microseconds; NFC required; `float`, mappings, `bytes` and
  every unknown type rejected. **No `default=` hook, no `str()`/`repr()`
  fallback, no legacy or alternate digest path, no dual-acceptance fallback.**
  No clock, locale, timezone database, environment variable, filesystem or
  network input.
* **Trust-stage vocabulary.** `EvidenceTrustStage` — the six *distinct* ADR §12
  stages — with `EVIDENCE_TRUST_STAGE_ORDER`. `EvidenceStructuralStatus` has
  exactly one member, `STRUCTURAL_UNVERIFIED`, exposed as a read-only
  **property**, mirroring the merged
  `AssessedSystemBinding.authenticity_status` discipline (§14.5). Objects report
  `established_trust_stages` and `unestablished_trust_stages`; the latter is
  never empty.
* **Lifecycle.** `EvidenceLifecycleState` (the ADR §28 nodes) and the closed
  transition relation `EVIDENCE_LIFECYCLE_TRANSITIONS`, exposed as a read-only
  mapping of frozensets, with `is_valid_lifecycle_transition` /
  `require_valid_lifecycle_transition`. `EXPIRED` and `REVOKED` are terminal; no
  self-transition exists.
* **Typed refusal vocabulary.** `TrustedEvidenceRefusalReason` — **19 codes**,
  neutral `TRUSTED_EVIDENCE_…` namespace, no aliases, no deprecated spellings, no
  milestone branding, deterministic declaration order (§22.13). Every member is a
  refusal; `TRUSTED_EVIDENCE_REFUSAL_REASONS` equals the whole enum, so there is
  no success state to return. `TRUSTED_EVIDENCE_INDETERMINATE` is a refusal, not
  a pass (§11). This discharges **DD-1** for the TEV-1 surface, which §11
  explicitly delegates to the implementation milestone.
* **Typed contract errors.** `TrustedEvidenceContractError` (subclasses
  `ValueError`, matching the merged evidence/system-identity contract
  convention) plus `TrustedEvidenceCanonicalizationError` and
  `TrustedEvidenceLifecycleError`, each carrying the corresponding stable
  refusal code.
* **TEV-2 input contract.** `EvidenceVerificationRequest` carries the caller's
  expected coordinates, a mandatory timezone-aware `as_of` with no default, and
  an order-irrelevant `requested_trust_stages` set normalized into ratified
  order. `structural_scope_mismatches()` returns **only** typed refusals in
  deterministic order; an empty tuple is documented as *not* a pass.
  `unperformed_verification_reason` always reports
  `TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED`.
* Curated `ugence_trusted_evidence_authority.api` surface with explicit
  `__all__` and matching top-level re-exports; machine-readable
  `public_api.json` snapshotting symbols, enum members **and order**, dataclass
  fields **and order**, and pinned constant values; PEP 561 `py.typed`; README;
  this CHANGELOG.
* **Tests and probes.** 395 package tests covering every constructor invariant,
  every enum and reason-code value, field order and immutability, pinned
  canonical bytes and digests (one reconstructed independently from hand-written
  literal bytes and `hashlib`), UTC-offset equivalence, microsecond preservation,
  naive-datetime rejection, a mutation matrix over **every** load-bearing
  coordinate with structural coverage of the field list, cross-tenant /
  cross-system / cross-context / cross-purpose-scope replay, half-open temporal
  boundaries, the exhaustive 5×5 lifecycle relation, anti-forgery probes,
  no-clock/no-environment AST scans, dependency direction in both directions, the
  milestone boundary, and public-API parity. Plus **34 independent adversarial
  probes** (`adversarial_probes.py`) that import only the curated public API —
  no test module, helper, fixture or conftest — and run against the installed
  wheel.
* **Distribution verifier** (`verify_trusted_evidence_authority_distribution.py`)
  — safe package-local `build/` cleanup that refuses symlinked or out-of-package
  targets; wheel-content assertions (exactly one top-level namespace plus
  dist-info and `py.typed`; no tests, probes, fixtures, build tree, foreign
  package or duplicate module); isolated `--no-index` virtualenv install with no
  monorepo path; surface-parity and adversarial probes re-run against the
  installed runtime.

### Anti-forgery posture

No caller can obtain an authority-authentic verified state, because **no
verified state exists to reach**. Proven closed for each route ADR §10 names:
`verified=True` (no such parameter); truthy non-booleans (`1`, `"true"`, `[1]`);
direct enum construction (`EvidenceStructuralStatus` has one member and lookup of
anything else raises); subclassing (exact-type checks refuse a subclass wherever
contract identity matters, and the type name is bound into the canonical frame);
property override (status is a property and never participates in the digest);
an authority-looking issuer or producer name (§10.3); a matching content digest
(§8.1.3); a duck-typed lookalike; and copying a valid contract across tenants,
systems, contexts, purposes or scopes. No public object exposes an
authorize/approve/sign/verify/revoke/resolve/register surface.

### Deliberately **not** implemented (ADR §30)

Trust-anchor resolution, signature creation or verification, key management /
rotation / revocation, evidence authenticity decisions, a verifier service or
adapter, and **signed evidence-verification receipts** — all **TEV-2**. The
receipt *shape* is deferred with the signing that makes it meaningful: E-11 makes
the receipt signed and §13.3 rules that "a receipt that is unsigned … is **not**
a receipt. There is no 'trusted but unsigned' state", so a caller-constructible
receipt type would be precisely the artifact §10.5 forbids consumers from
trusting. ADR §9 rows 6 and 14–16 (verification instant, verifier authority and
key identifier, protocol/version, verification status) are omitted for the same
reason.

Also absent: Benchmark Registry contracts or resolution (**BR-1/BR-2**), Policy
Authority integration, RA-5 replacement or generalization, Readiness integration
(**UVI-EV-1 / M-3R.4**), deployment or action authorization, and forecasting,
attribution, valuation or ROI (**GV-F → GV-V**). No placeholder service, fake
verifier, permissive stub or reserved public field for a later milestone.

`SystemManifest` is not defined (**DD-11** stays open). No evidence-supersession
state or refusal code is minted: the ratified *evidence* lifecycle (§28) has no
supersession arrow — supersession belongs to the *benchmark* lifecycle (§29) and
is itself deferred to **DD-4**. No `SubjectContext` is minted.

### Dependencies and boundaries

**Zero runtime dependencies** — standard library only. ADR §23 permits TAP to
depend on `ugence-governance-contracts`; TEV-1 takes the narrower option because
**DD-2** is explicitly blocked on "the concrete contract shapes from TEV-1/BR-1",
and importing that leaf now would decide DD-2 by implementation.

`AssessedSystemBinding` remains Governance Contracts' sole definition (§14.1);
this package references it by opaque reference + digest and never redefines it.
Nothing imports Risk Authority, Policy Authority, Readiness, Governed Value,
ActionGate, Decision Authority, Agent Runtime, Cloud Scaling, a Benchmark
Registry, or `ugence-tap-provider`. **No consumer imports this package** — TEV-1
authorizes no integration — and a test asserts it.

This package is **not** `ugence-tap-provider` (§6.1), **not**
`risk_authority.integrations.tap` (RA-scoped; preserved unchanged by E-13, whose
platform-wide extension was rejected at §25.3), and **not** the
`truth_assurance_pipeline` research corpus. No assertion-support vocabulary
(`TapOutcome` members, `evidence_coverage`, fingerprint) is reused; a test
asserts their absence.

### Versioning judgement

Package version **0.1.0**. **No separate `CONTRACT_VERSION` constant is minted.**
In this repository that constant is the *provider* convention
(`ugence-tap-provider`, `ugence-actiongate-provider`, the provider framework),
naming a provider contract version against a kernel/framework major; the
contract-shape packages (`ugence-governance-contracts`,
`ugence-uvi-policy-contracts`, `ugence-policy-authority`) carry only
`__version__`. TEV-1 follows the contract-shape convention rather than inventing
a constant for symmetry. The versioning that *is* load-bearing here is bound into
the digest as `TRUSTED_EVIDENCE_CANONICALIZATION_VERSION`, so changing an
encoding rule requires a new version string. Fixing that constant and the
evidence-identity domain tag is authorized: **DD-9 explicitly leaves the exact
byte constants to TEV-1/TEV-2.** The receipt and benchmark domain tags are not
minted, since their artifacts do not exist.

### Nothing here authorizes anything

No TEV-1 result authorizes deployment, runtime action, policy approval,
benchmark acceptance, monetary value or causal attribution.
