# Changelog — ugence-trusted-evidence-authority

## [0.2.0] — TEV-2: the verification authority, signed receipts and independent re-verification

Implements milestone **TEV-2** of ADR §30 — "TAP Verification Service and signed
receipts: the verification authority, trust anchors, key trust/revocation,
signing, independent verification". Additive over TEV-1: **every one of the 29
curated TEV-1 symbols remains exported unchanged**, all four TEV-1 pinned
digests are byte-identical, and the refusal vocabulary was extended by
appending, so TEV-1's nineteen codes keep their exact ordinal positions.

### Closure-audit corrections (F-01 … F-09; still 0.2.0, unreleased)

Findings from the independent TEV-2 closure audit, corrected before merge. The
package has never merged or released at this version, so unsafe APIs are
**removed** rather than preserved behind a compatibility alias.

**The safest correction was architectural: handwritten Ed25519 is gone from
every production path.** `authority/ed25519.py` — a pure-Python RFC 8032
implementation — is deleted and replaced by `authority/backend.py`, which calls
`cryptography` (OpenSSL) for signing, verification and public-key derivation and
libsodium through `PyNaCl` for strict point validation. There is no fallback,
no optional import and no vendored copy: if either backend is absent the package
fails to import.

The justification the earlier revision gave rested on reading ADR §23 as a
prohibition on third-party cryptographic libraries. **It is not one.** §23 is the
consumer and dependency matrix and governs the direction of dependencies
*between Ugence packages*; every entry in it names a Ugence component. Reading
it as covering maintained third-party primitives was an overread, and the
similar handwritten code in two other packages was a convention, not a security
argument.

| Finding | Correction |
|---|---|
| **F-01** non-canonical and small-order encodings not refused where RFC 8032 §5.1.3 requires | strict libsodium point validation; the full corpus is a permanent test |
| **F-02** no differential check against a second implementation | `cryptography` and libsodium are cross-checked over 1,800 valid triples, the RFC vectors, and the whole malformed corpus |
| **F-03** a worthless public key could become a trust anchor — an identity-point anchor admits a **universal forgery** | `TrustAnchorRecord` validates the point at construction, so such a key can never enter an anchor store |
| **F-04** signature-only and scope-bound verification returned the same type, so a result could report a scope it never checked | two operations, two never-equal result types; only `ScopeBoundVerificationResult` reports `CONTEXT_SYSTEM_BOUND` |
| **F-05** `expected_*=None` arguments meant `None`, `""`, `0` and `False` silently skipped their own checks | `verify_bound` requires exactly a `ReceiptScopeExpectation`, every coordinate mandatory and compared unconditionally |
| **F-06** the malformed corpus was never a standing test | `test_backend_strict_corpus.py` and `test_backend_differential.py`, both in CI |
| **F-07** documentation asserted authority the implementation did not have | the §23 claim, the zero-dependency claim, the "no seed accessor" claim and the gate count are all corrected here and in the README |
| **F-08** `TrustedEvidenceSigningKey` exposed its seed as a public dataclass field | not a dataclass, no `__dict__`, no accessor; pickling, copying and attribute assignment all raise; only a backend key object is retained |
| **F-09** the re-verifier's payload-digest gate was counted as load-bearing without proof | proved load-bearing — it is the only gate that catches an envelope whose `__post_init__` never ran — and the two genuinely unreachable gates are now reported as redundancy, not as gates |

**The pinned vectors did not move.** Every RFC 8032 §7.1 vector and every pinned
TEV-2 signature, digest and receipt id reproduces byte-for-byte after the
substitution. Nothing was re-pinned to match the new backend; the vectors are
what proves the substitution changed nothing a verifier depends on.

**Structural sweeps added.** No condition in the authority layer tests bare
truthiness, no `or`-default appears anywhere in the package, and no
`dict.get(key, fallback)` supplies a silent substitute — all AST-enforced, so a
new gate cannot be written the old way even when every behavioural test passes.

### The three roles, kept apart (ADR §8 — "no row may absorb another")

* **`EvidenceVerificationAuthority`** — verifies an evidence submission against
  a TEV-1 `EvidenceVerificationRequest` and produces a typed
  `EvidenceVerificationDetermination`. Holds no signing key; has no method that
  signs or issues. Runs a fixed ordered sequence — structural, lifecycle,
  integrity and scope, temporal, protocol, stage coverage — and **re-checks
  independently** what the protocol reports, which is ADR §8.1's closing rule
  applied literally: "a lax or compromised verifier must still be unable to get
  a mismatched artifact admitted".
* **`ReceiptIssuer`** — turns an **admitted** determination into the ADR E-11
  signed envelope. Performs no verification, resolves no trust anchor, and
  raises rather than signing a refusal.
* **`SignedReceiptVerifier`** — independently re-verifies an envelope from its
  own fields plus a trust-anchor resolver and an explicit instant. Holds no key,
  issues nothing, and never trusts what the envelope asserts about itself.

* **`SignedReceiptVerifier`** answers two different questions with two
  operations: `verify_signature(envelope, evaluated_at=…)` and
  `verify_bound(envelope, expectation, evaluated_at=…)`. They return
  `SignatureOnlyVerificationResult` and `ScopeBoundVerificationResult`, which
  are structurally distinct and never compare equal, and only the bound form
  establishes `CONTEXT_SYSTEM_BOUND`.

An `EvidenceVerificationDetermination` and either verification result **cannot
be constructed by a caller at all**: each demands a private token the curated
API does not export. ADR §8.1.5 — "no consumer may manufacture verification" —
becomes unrepresentable rather than merely disbelieved.

### No arbitrary-signing capability

`ReceiptSignerPort` takes a package-minted `ReceiptSigningInput`, not free
bytes. The only route to one runs `verify → ADMITTED determination → issue`, so
there is no public oracle that will sign a caller's chosen bytes. An HSM- or
KMS-backed signer implements the same port and drops in without a caller change
(DD-10). Stated plainly rather than overclaimed: the token closes the *public
API* route; code that already imports private module attributes is not defended
against, and no Python-level mechanism could be — the load-bearing secret is the
signing key, which lives only behind the port.

### Cryptographic profile (DD-9)

One strict v1 profile — **Ed25519** (RFC 8032, PureEdDSA over edwards25519 with
SHA-512), one canonical encoding (bare lowercase base16), two domain-separated
length-prefixed signing frames. No `none`, no alias, no caller-selected
algorithm, no negotiation, no permissive fallback; an unsupported profile or
encoding is a refusal (§22.8).

Base16 over base64 because a byte string has exactly one lowercase-hex spelling,
matching TEV-1's digest convention; base64's unconstrained trailing bits would
let a different envelope carry the same signature.

Signed inputs are **length-prefixed frames**, never concatenations: the element
count is bound first, then each element's own big-endian length, so no boundary
can be moved and no frame can be extended or truncated into another valid one.
The domain tag is element 0 of each frame, so §13.3's "a signature valid in one
domain must not verify in another" holds by construction. The receipt frame
binds the payload twice — by digest and by full canonical bytes — so a swapped
payload, a swapped digest, or a disagreeing pair are all signature failures.

**Ed25519 is imported, not implemented.** `cryptography` (OpenSSL) supplies
signing, verification and public-key derivation; libsodium through `PyNaCl`
supplies the strict point validation `cryptography` defers to verify time and so
cannot perform when a trust anchor is constructed. Both are imported from
`authority/backend.py` and nowhere else, with no optional-import fallback.

All five published RFC 8032 §7.1 vectors reproduce byte-for-byte, including the
§5.1.7 malleability refusal, and the two backends are differentially cross-
checked against each other. This package makes no timing claim of its own: side-
channel resistance is the backends' property, not something asserted on top of
them. Production key custody stays behind `ReceiptSignerPort` (DD-10).

### Trust anchors, key lifecycle and revocation

* Exact-coordinate resolution over `(authority_id, key_id, capability)` only.
  No `latest()`, no default key, no partial match, no authority-name-only
  acceptance, no first-key-wins; duplicate coordinates refused at construction
  (§26.9 — guessing is an unsigned authority decision).
* `TrustAnchorCapability` is single-valued, so ADR E-3's producer/verifier
  separation is unrepresentable to violate: one key, one role.
* Key validity is half-open `[effective_from, effective_to)` (§17.9);
  `KeyRevocation` is **dated**, and revocation outranks every other lifecycle
  state (§13.3).
* `TrustAnchorResolverPort` plus a deterministic `StaticTrustAnchorDirectory`
  and an explicit `DenyAllTrustAnchorDirectory` — E-8's "the production default
  is deny", made constructible rather than implicit. **No network retrieval.**
* A record carries a public key as canonical hex and nothing else. The encoder
  rejects `bytes` outright and no public contract declares a bytes field, so
  private material cannot reach a record, digest, canonical byte sequence,
  `repr` or audit trail even by mistake.

### Time and revocation semantics — the delegated choice, and why

Every instant is an explicit parameter with no default; no clock is read
anywhere (§22.9, §22.10); naive datetimes are refused at every boundary.

Re-verification answers the **current** trust question. ADR §13.3 settles it:
"key revocation is checked **at verification time**; a receipt signed by a key
that was later revoked is **not silently honoured**." Key window, revocation and
receipt validity are all evaluated at the caller's `evaluated_at`, never at the
payload's `verified_at`, so a previously valid receipt stops verifying once its
key is revoked. The refusal retains typed evidence — the reason, the evaluation
instant and the resolved coordinate — so it can be explained rather than merely
asserted.

**Historical re-verification is deliberately not offered.** It would need an
as-of-T trust semantics no merged clause defines for evidence; §17.1's
historical resolution is a Benchmark Registry concept and is BR-2's. Offering a
plausible answer would resolve a question the ADR retains elsewhere.

### Refusal vocabulary — additive, one namespace

Twenty-one codes **appended** to `TrustedEvidenceRefusalReason`, discharging the
ADR §11 rows TEV-1 recorded as "**TEV-2.**" — producer attribution (row 4), the
key-lifecycle family (row 5), `SIGNATURE_INVALID` (row 6) — plus the envelope,
profile, encoding, trust-anchor, protocol and receipt-validity conditions §13.3
requires.

A separate TEV-2 enum was considered and **rejected**: DD-1 delegates "the exact
typed reason-code vocabulary … for evidence verification" in the singular, and
§22.11 requires a namespace "stable across versions, never reused for a
different meaning" — two parallel enums would be exactly the duplicate,
conflicting namespace that rule prevents.

TEV-1's nineteen keep their **exact declaration order and ordinal positions**,
pinned by the new `TEV1_TRUSTED_EVIDENCE_REFUSAL_REASONS`; the additive block is
`TEV2_TRUSTED_EVIDENCE_REFUSAL_REASONS`. §22.13's ordering sorts by declaration
index, so interleaving would have silently re-ordered a refusal sequence a
merged receipt was issued under.

Still **no success state**. `TRUSTED_EVIDENCE_INDETERMINATE` remains a refusal,
and both new outcome enums (`EvidenceAdmissionOutcome`,
`ReceiptVerificationOutcome`) have exactly two members, so no
`UNKNOWN`/`PARTIAL`/`PENDING`/`BEST_EFFORT` state exists to read optimistically.

`UNIT_MISMATCH` / `METRIC_MISMATCH` remain absent — requirement-relative, so §12
assigns them to the consuming evaluation engine — as do benchmark refusals
(BR-1/BR-2).

### Canonicalization

Five new domain tags, minted in the one module that owns domain selection.
**Every TEV-1 entry is untouched**: adding keys to the map left each existing
key's value byte-identical, so `54b9bd61…`, `26ee959e…`, `d381c723…` and
`53b4c28c…` all reproduce exactly — the first three in the suite, the fourth in
the distribution verifier. The canonicalization version is unchanged at `v1`,
and no encoding rule moved.

Two token-guarded findings — `EvidenceVerificationDetermination` and
`ReceiptVerification` — are deliberately **not canonicalizable**. They carry a
private capability token, and §22.2's total-field-inclusion rule admits no
conditional omission, so rather than weaken a ratified invariant the types
simply have no digest. The auditable counterpart is
`EvidenceVerificationAuditRecord`.

### TEV-1 compatibility

* All **29** curated TEV-1 symbols remain exported, from `api` and from the
  package root, with the same kind, the same dataclass fields **in the same
  order** and the same enum members **in the same order** — asserted by name and
  positionally, not merely as sets.
* `EvidenceVerificationReceiptPayload` gained **no field**. The envelope
  **wraps** it. Its `structural_status` is still permanently
  `STRUCTURAL_UNVERIFIED`, its `authenticity_verified` still `False`, and
  `CRYPTOGRAPHICALLY_AUTHENTIC` still appears in its
  `unestablished_trust_stages`. §13.3's signature-exclusion rule is satisfied
  literally: the content digest covers payload bytes containing no signature.
* The `contracts` subpackage is newly asserted to define **no** signing, key or
  trust-anchor code, and to import nothing from the authority layer — the seam
  that keeps the envelope a wrapper rather than a retrofit.

### What TEV-2 still does not do

A verified receipt authorizes nothing — not deployment, not runtime action, not
policy sufficiency, not economic value, not causal attribution (§13.2, E-12).
Possession is not validity (§8.1.3). Stage 6 is never asserted (§12).

Not implemented, per ADR §30 and §31: Benchmark Registry (BR-1/BR-2), policy
applicability resolution, Readiness / UVI-EV-1 / M-3R.4 integration, RA-5
replacement (E-13; alignment is DD-6), Cloud Scaling integration, ActionGate or
deployment authorization, credential issuance, forecasting/attribution/
valuation/ROI (GV-F → GV-V), network trust-anchor retrieval, cloud KMS (DD-10),
certificate-authority infrastructure, receipt persistence or distribution
services, and generic multi-algorithm cryptographic agility. **No package in the
monorepo imports this one**, and a test enforces that.

### Verification

| Check | Result |
|---|---|
| Package suite | **1 158 passed** (TEV-1 baseline 649) |
| Independent adversarial probes | **83 passed** — source and inside the wheel |
| RFC 8032 §7.1 conformance | all **5** published vectors reproduce byte-for-byte, under both backends |
| Strict malformed corpus | every untrustworthy point refused at construction; every malformed signature a fail-closed `False` |
| Differential agreement (`cryptography` vs libsodium) | **1 800** valid triples, the RFC vectors and the full mutation corpus — zero disagreements |
| Gate-deletion mutants | **18 run, 16 killed.** The two survivors are structurally unreachable and are reported as redundancy, not as gates |
| TEV-1 pinned digests | all **4** unchanged |
| TEV-1 curated symbols | all **29** present, same field and member order |
| Public API parity (source · manifest · wheel · isolated install) | **PASS** — 87 symbols |
| Wheel build, isolated `--no-index` install from a prepared wheelhouse | **VERIFIED** — backends resolved from the wheelhouse, versions reported |
| Dependency and reverse-dependency guards | **PASS** — exactly two runtime dependencies, imported from one module |
| Truthiness / `or`-default / silent-`get` AST sweeps | **PASS** |
| No-clock / nondeterminism AST scans | **PASS** |
| Platform-freeze substantive digest | **unchanged** |

### Dedicated CI

`.github/workflows/trusted-evidence-authority-ci.yml` — resolves the Low finding
carried from the TEV-1 closure audit (F-03). Five jobs covering the package
suite (including the strict corpus, the differential backend suite, the
re-verification gate proofs and the truthiness sweep), the independent probes,
the wheel build with isolated wheelhouse installation, public-API parity, and
the platform-freeze verifier. Both cryptographic backends are installed
explicitly and their versions printed. It publishes nothing, uses
no secret and contacts no external trust service; all key material it touches is
fixed, hard-coded and unmistakably non-production.


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
encoding rule requires a new version string. Fixing that constant and **both**
domain tags is authorized: **DD-9 explicitly leaves the exact byte constants to
TEV-1/TEV-2.** TEV-1 therefore mints the evidence-identity domain tag **and the
receipt-payload domain tag** — the latter because the structural
`EvidenceVerificationReceiptPayload` contract exists in this release, and §13.3
requires its canonical content, canonicalization version and domain tag to be
fixed *before signing exists*. Minting that tag separates byte spaces and
confers no trust: signed receipt issuance and cryptographic verification remain
**TEV-2**. The **Benchmark Registry** domain tag remains unminted, since no
benchmark artifact exists (BR-1/BR-2).

### Nothing here authorizes anything

No TEV-1 result authorizes deployment, runtime action, policy approval,
benchmark acceptance, monetary value or causal attribution.
