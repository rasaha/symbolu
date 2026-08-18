# Changelog — ugence-trusted-evidence-authority

## [0.1.0] — TEV-1: trusted evidence contracts

### Closure-audit corrections (A-01, A-02, A-03; still 0.1.0, unreleased)

Three blocking findings from the independent TEV-1 closure audit, corrected
before merge. Each was confirmed against the ratified ADR and the source before
being acted on. The package has never merged or released, so the contracts are
corrected **directly** — no compatibility alias, migration shim or legacy-digest
acceptance path is introduced.

**A-01 — the TEV-1 receipt payload was missing.** ADR §30 assigns "receipt shape
(§13)" to TEV-1 and the §32 status ledger states *"shape = TEV-1, service =
TEV-2"*. The original implementation deferred the shape entirely, reading §13.3's
"no trusted but unsigned state" as a reason to omit it. That was the wrong
reading: §13.3 requires the canonical content, its canonicalization version and
its domain tag to be "unambiguous, versioned, and **fixed before signing
exists**" — which makes defining the shape now the *precondition* for TEV-2, not
a violation.

* Added **`EvidenceVerificationReceiptPayload`**, an immutable, deterministic,
  canonicalizable, digest-bound structural payload binding: receipt id and
  schema; source evidence identity digest and evidence content digest;
  verification-request digest; the §13.1.3 scope coordinates; **`verified_at`**
  (§9 row 6); **verifier authority and key identifier** (§9 row 14, the key id an
  opaque coordinate only); **verification protocol id and version** (§9 row 15);
  **declared outcome and refusal reasons** (§9 row 16); declared cleared and
  not-attempted stages (§13.1.1); and **two distinct half-open validity
  intervals** for the evidence and for the receipt (§13.1.6). ADR §9 rows 6 and
  14-16 are therefore no longer omitted — they moved to the artifact that
  describes the act, rather than the artifact that describes the evidence.
* Added **`DeclaredVerificationOutcome`** (`DECLARED_ADMITTED` /
  `DECLARED_REFUSED` / `DECLARED_INDETERMINATE`). The `DECLARED_` prefix is
  load-bearing: a payload's verification coordinates are content its caller
  wrote, never established fact. Coherence is enforced — an admission carries no
  refusal reason and must clear at least one stage; a non-admission must carry a
  reason; `DECLARED_INDETERMINATE` must name
  `TRUSTED_EVIDENCE_INDETERMINATE`; a stage cannot be both cleared and not
  attempted; and neither list may name `POLICY_SUFFICIENT`, because §12 rules
  that "a receipt records stages 1-5 and never asserts stage 6 globally"
  (`RECEIPT_REPORTABLE_TRUST_STAGES`).
* **No signature field** — not optional, not a placeholder. TEV-1 fixes the
  canonical content; TEV-2 adds the signature, envelope, key trust and revocation
  check. A payload declaring every reportable stage cleared under an
  authoritative-sounding verifier still reports `STRUCTURAL_UNVERIFIED`,
  `authenticity_verified is False`, `CRYPTOGRAPHICALLY_AUTHENTIC` in
  `unestablished_trust_stages`, and
  `TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED`.
* Added **`EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN`** under DD-9. The
  encoder now selects a domain per contract type from one declared registry, so
  a receipt digest can never be reused as an evidence digest (§26.6); the frame's
  `type` continues to separate contracts within a domain. Proved non-colliding
  against evidence identity, schema, scope, observation, provenance,
  applicability, claim and verification-request encodings.

**A-02 — ADR §9 rows 11-12 were absent**, and a source docstring wrongly claimed
rows 7-13 were represented.

* Added **`EvidenceClaimBinding`**: `applicability` (no default), `claim_ref`,
  `metric_ref`, `unit`, `measurement_semantics_ref`. Row 11 is "claim **or**
  metric identity", so `APPLICABLE` requires at least one of the two; row 12
  makes `unit` and `measurement_semantics_ref` **co-required** with it;
  `NOT_APPLICABLE` requires all four empty. Every other combination fails
  closed — proved exhaustively over all 16 populated/empty patterns under both
  declarations. Neither `""` nor `None` is ever read as "not applicable".
* Added the mandatory `claim` field to `CanonicalEvidenceIdentity`, positioned
  between `scope` (rows 7-10) and `provenance` (row 13) so the declared field
  order follows the ADR's own row order. It participates in the digest and in
  `coordinate_identity`, so cross-claim and cross-unit replay is detectable.
* Corrected the `identity.py` coverage statement to enumerate what is actually
  carried, and to explain where rows 6 and 14-16 now live.
* This records identity and semantics only. No conversion, normalization,
  dimensional analysis, comparison or evaluation exists — §18 assigns comparison
  to the consuming evaluation engine.

**A-03 — Unicode NFC was enforced only during canonicalization.** A non-NFC
identifier constructed successfully with every structural invariant apparently
satisfied, and failed only later when something asked for its bytes.

* `require_canonical_str` now rejects non-NFC input **at construction**, applying
  the two-boundary discipline ADR §22.4 already fixes for naive datetimes
  ("rejected at the boundary **and again** at canonicalization"). It rejects
  rather than normalizes, preserves the existing padded-string and `str`-subclass
  rejections, and the encoder keeps its own NFC check as defense in depth — a
  value reaching it via `object.__setattr__` still fails closed.
* Applied uniformly to every string coordinate including nested contracts and
  custody-chain elements, with a structural coverage test asserting no `str`
  field escapes the matrix. Fixtures are built from explicit codepoints and
  **asserted to be genuinely non-NFC before use**.

**Digest impact, stated openly.** `EvidenceSchemaRef`'s pinned canonical bytes
and digest are **unchanged**
(`54b9bd615aa13dd133f88580128b4c4094363c75f96b6bcf1d3b2f582683fa62`) — A-03
rejects values that were never canonicalizable and leaves every valid NFC value
exactly as it was. `CanonicalEvidenceIdentity`'s pinned digest **changed**, from
`5fec72b52d13264c31519013a74704fee03cea66f5ebfa22258a3d51f562cf40` to
`26ee959e4c87cc0660895a269c2805af1065ba4f634c9c73070848de7bf51029`, because A-02
adds the mandatory `claim` key to its canonical body. A test proves the cause:
removing that single key from the current body reproduces the old digest exactly.
Receipt-payload digests are additive and newly pinned. There is no legacy-digest
acceptance path.

**Verification.** 649 package tests (from 395) and 49 independent adversarial
probes (from 34), including the audit's A-03 probe reproduced and passing from
both source and wheel; extended mutation matrices over every evidence coordinate
*and* every receipt-payload field, with mechanical coverage checks; receipt
anti-forgery probes covering `verified=True`, truthy non-booleans, forged cleared
stages, a trusted-sounding verifier name, plausible key ids, matching digests,
subclassing, property override, `object.__setattr__`, instance-dict shadowing,
duck-typed lookalikes, cross-scope copying, pickle/copy/deepcopy round-trips,
unknown outcome and reason values, omitted required coordinates, and
evidence-versus-receipt validity confusion. Curated surface grew from 24 to **29**
symbols; `public_api.json`, the distribution verifier, README and this changelog
were updated together, and source, manifest, wheel and isolated install agree.

Package version remains **0.1.0** — the package has never merged or released. No
other package is touched.

### Original TEV-1 contents

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
adapter, **signing**, **signed envelopes**, **receipt issuance** and **receipt
re-verification** — all **TEV-2**.

> **Superseded before merge.** This section originally stated that the receipt
> *shape* and ADR §9 rows 6 and 14–16 were deferred to TEV-2. **That rationale
> was withdrawn by the A-01 correction above and does not describe the shipped
> package.** The corrected boundary is: **TEV-1 exports
> `EvidenceVerificationReceiptPayload`**, which carries ADR §9 rows 6 and 14–16.
> It is a structural, declarative payload contract — **not** an authority-issued
> receipt and **not** proof of verification. It may carry a caller-declared
> outcome, refusal reasons, stage declarations, verifier/key/protocol
> identifiers and verification coordinates; **none of those declarations
> establishes authenticity**. It always reports `STRUCTURAL_UNVERIFIED` and
> `authenticity_verified` remains `False`. What stays with TEV-2 is signing,
> signed envelopes, cryptographic verification, trust-anchor resolution, key
> validation, key revocation, receipt issuance and receipt re-verification.

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
