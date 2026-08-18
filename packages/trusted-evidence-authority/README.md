# ugence-trusted-evidence-authority

**Ugence Trusted Evidence Authority — trusted-evidence contracts and the
verification authority.**

The platform **Trust Assurance** role's package, ratified in
[`ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md`](../../docs/architecture/ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md)
(E-1, E-2, §6.2), implementing milestones **TEV-1** (contract shapes) and
**TEV-2** (the verification authority, trust anchors, key trust and revocation,
signing, independent verification) of §30.

Internal platform infrastructure — **not** a customer-facing module, **not** a
product, **not** a fourth UVI engine (B-2).

**A verified receipt authorizes nothing.** Not deployment, not runtime action,
not policy sufficiency, not economic value, not causal attribution (§13.2,
E-12). Possession of one establishes nothing (§8.1.3), and a signature alone is
not trusted verification — whether the signing key was resolved, entitled,
in-window and unrevoked is a separate check, recomputed at an explicit instant
every time.

---

## What this package is

| | |
|---|---|
| **Canonical evidence identity** | `CanonicalEvidenceIdentity` plus the nested `EvidenceSchemaRef`, `EvidenceObservation`, `EvidenceScopeBinding`, `EvidenceClaimBinding`, `EvidenceProvenanceChain`, `ApplicabilityCoordinate` |
| **Receipt payload** | `EvidenceVerificationReceiptPayload` + `DeclaredVerificationOutcome` — the §13 receipt *shape*, unsigned and permanently unverified |
| **One canonicalization path, one digest path** | `canonical_bytes` / `canonical_digest`, versioned and domain-separated |
| **Trust-stage vocabulary** | `EvidenceTrustStage` — the six distinct ADR §12 stages, plus the ratified `EVIDENCE_TRUST_STAGE_ORDER` |
| **Lifecycle** | `EvidenceLifecycleState` and the closed ADR §28 relation `EVIDENCE_LIFECYCLE_TRANSITIONS` |
| **Typed refusal vocabulary** | `TrustedEvidenceRefusalReason` — 40 codes (19 from TEV-1, 21 appended by TEV-2), **every one a refusal** |
| **Typed contract errors** | `TrustedEvidenceContractError` and two subclasses |
| **Verification input** | `EvidenceVerificationRequest` — expectations in; **no verdict** |
| **Cryptographic profile** | One strict Ed25519 profile, one canonical encoding, two domain-separated signing frames |
| **Trust anchors** | `TrustAnchorRecord`, `TrustAnchorCoordinate`, `KeyRevocation`, a resolver port, a deterministic reference directory and an explicit deny-all default |
| **Verification authority** | `EvidenceVerificationAuthority` + `EvidenceVerificationProtocolPort` — typed admitted/refused determinations |
| **Signed receipt** | `SignedEvidenceVerificationReceipt` — the ADR E-11 artifact, wrapping the TEV-1 payload |
| **Issuance** | `ReceiptIssuer` + `ReceiptSignerPort` — the only route from an admission to a signature |
| **Independent re-verification** | `SignedReceiptVerifier` → `ReceiptVerification`, computed never stored |
| **Deterministic audit** | `EvidenceVerificationAuditRecord` — digests, never payloads |

## What this package is **not**

It is **not an authorizer**. E-14 keeps TAP off the runtime path entirely; Risk
Authority and ActionGate retain runtime authorization. Nothing here approves a
policy, computes readiness, resolves a benchmark, or calculates value.

There is no placeholder verifier, no permissive stub, no allow-all resolver and
no field reserved for a later milestone. When no trust anchor is configured the
answer is **deny** (E-8), and `DenyAllTrustAnchorDirectory` makes that default
explicit rather than implicit.

In particular, **`EvidenceVerificationReceiptPayload` is still not a receipt.**
TEV-2 did not change it. It remains the caller-constructible, permanently
`STRUCTURAL_UNVERIFIED` structural payload TEV-1 merged: it may carry a
caller-declared outcome, refusal reasons, stage declarations,
verifier/key/protocol identifiers and verification coordinates, and **none of
those declarations establishes authenticity**. It carries no signature field —
TEV-2 **wraps** it in `SignedEvidenceVerificationReceipt` rather than
retrofitting one.

The distinction is load-bearing. Reading a payload establishes nothing. What
establishes something is `SignedReceiptVerifier` resolving a trust anchor at an
exact coordinate, checking its lifecycle at an explicit instant, and verifying a
signature over reconstructed bytes — and even then, only that the receipt is
authentic under a currently-trusted key.

It is explicitly **not**:

* `ugence-tap-provider` — the assertion-support scorer. ADR §6.1: "assertion-
  support scoring and evidence verification are **different trust questions and
  are never merged**." Its `TapOutcome` vocabulary, `evidence_coverage` ratio and
  fingerprint are not reused here, and a test asserts their absence.
* `risk_authority.integrations.tap` — the **RA-scoped** `EvidenceAdmissionPort` /
  `ReferenceEvidenceAdmission` seam. RA-5 owns it, E-13 preserves it unchanged,
  and extending it platform-wide was considered and **rejected** (§25.3).
* `truth_assurance_pipeline` — a research corpus, not a platform capability.
* The Policy Authority, Benchmark Registry, Decision Authority, ActionGate,
  Readiness, or Governed Value.

**Nothing here authorizes anything** — not deployment, not runtime action, not
policy approval, not benchmark acceptance, not monetary value, not causal
attribution.

---

## Nothing here proves authenticity

Constructing any object in this package is a **structural** act. It establishes
ADR §12 stage 1 — *structurally constructible* — and nothing else. Every object
says so itself:

```python
ident.structural_status        # EvidenceStructuralStatus.STRUCTURAL_UNVERIFIED
ident.authenticity_verified    # False — always
ident.established_trust_stages # (STRUCTURALLY_CONSTRUCTIBLE,)
ident.unestablished_trust_stages
# (CRYPTOGRAPHICALLY_AUTHENTIC, PROVENANCE_VERIFIED, CONTEXT_SYSTEM_BOUND,
#  CURRENTLY_VALID, POLICY_SUFFICIENT)   ← never empty
```

`structural_status` is a read-only **property**, not a field — the discipline
ADR §14.5 already applies to `AssessedSystemBinding.authenticity_status`. There
is no constructor argument, assignment or subclass hook that raises it, because
`EvidenceStructuralStatus` has exactly **one** member. Adding an
authority-verified member would be caller-settable, which is exactly what §10.2
forbids consumers from trusting. TEV-2 did **not** add one: the trust question
is answered by re-verifying a signature against a resolved anchor, and that
answer is computed on demand rather than stored on the artifact.

Per ADR §10, none of the following is proof of verification, and the package
holds to that structurally: a `verified=True` flag (there is no such parameter);
a lifecycle label; an authority **name**; a caller-supplied confidence score
(there is no such field); and **an unsigned verification object** — which is
precisely what a caller-built `EvidenceVerificationReceiptPayload` is, which is
why it always reports `STRUCTURAL_UNVERIFIED` no matter what it declares.
**Possession, parsing, canonicalization and digest equality prove nothing**
(§8.1.3).

### The six stages are never collapsed

ADR E-10 forbids one boolean from standing in for six distinct questions, and
§25.7 records why. This package keeps them separate as named members and reports
per-stage. **Stage 6 (`POLICY_SUFFICIENT`) is requirement-relative** and is never
a property of evidence — asking TAP to establish it is a structural refusal:

```python
EvidenceVerificationRequest(..., requested_trust_stages=(EvidenceTrustStage.POLICY_SUFFICIENT,))
# TrustedEvidenceContractError: ... ADR §12 rules policy sufficiency
# requirement-relative and assigns it to the consuming evaluation engine ...
```

---

## Evidence coordinates

`CanonicalEvidenceIdentity` binds every coordinate below, and **every one
participates in the digest**, so replaying an evidence item across any scope is
mechanically detectable (ADR §26.5). Coordinates are never collapsed into a
free-form metadata dictionary — the canonical encoder rejects mappings outright.

| Coordinate | ADR | Notes |
|---|---|---|
| `evidence_id` | §9.1 | required |
| `evidence_type` | §9.2 | required |
| `schema` (id + version) | §9.2 | both halves required |
| `content_digest` | §9.3 | bare lowercase 64-hex sha-256 |
| `observation.producer_id` | §9.4 | naming a producer establishes nothing (§10.3) |
| `observation.issuer_id` | §9 | "issuer when distinct"; `""` = not distinct, and an issuer equal to the producer is refused |
| `observation.observed_from` / `observed_to` | §9.5 | instant, or half-open window `[from, to)` |
| `observation.collected_at` | §9.5 | distinct from observation; may not precede it |
| `scope.tenant_id` | §9.7 | mandatory, never inferred (§27.1) |
| `scope.assessment_context_ref` + `_digest` | §9.8 | digest-bound |
| `scope.subject_ref` | §9.9 | opaque; no subject payload crosses the seam (§27.4) |
| `scope.assessed_system_binding_ref` + `_digest` | §9.10 | co-required; absence is **explicit**, never defaulted |
| `scope.assessment_purpose_ref`, `usage_scope_ref` | §7.1 r5 | opaque tokens — no evidence-side vocabulary is ratified, so none is invented |
| `claim.claim_ref` / `claim.metric_ref` | §9.11 | "claim **or** metric identity"; at least one under `APPLICABLE` |
| `claim.unit`, `claim.measurement_semantics_ref` | §9.12 | **co-required** whenever row 11 is present; partial combinations fail closed |
| `claim.applicability` | §9.11 | "absent for raw non-metric evidence, **explicitly**" — never inferred from `""` or `None` |
| `provenance.chain_ref`, `custody_refs` | §9.13 | custody order is semantic; duplicates refused |
| `lifecycle_state` | §28 | what the artifact *asserts* — never verified here |
| `geography`, `domain`, `intended_outcome` | §15 r6–8, UVI D-13 | explicitly `APPLICABLE` with a value or `NOT_APPLICABLE` — **never omitted** |
| `valid_from` / `valid_to` | §9.17 | half-open `[valid_from, valid_to)` (§17.9) |

### Coordinates that live on the receipt payload instead

ADR §9 rows 6 and 14–16 — the **verification instant**, the **verifier authority
and key identifier**, the **verification protocol/version**, and the
**verification status and reason codes** — describe an act a verifier performs,
so they are not coordinates *of the evidence*. They live on
`EvidenceVerificationReceiptPayload` (below), which keeps every declared
verification coordinate in one object that is explicitly, permanently unverified.

**No `SystemManifest`** is defined, named as owned, or placed (DD-11 stays open).
**No supersession** exists: the ratified *evidence* lifecycle (§28) has no
supersession arrow — that is the *benchmark* lifecycle (§29), itself deferred to
DD-4 — so no supersession state and no supersession refusal code is minted.

---

## The receipt payload

ADR §30 assigns "receipt shape (§13)" to **TEV-1**, and the §32 status ledger is
explicit: *"Signed, immutable TAP verification receipt (§13) … shape = TEV-1,
service = TEV-2."* `EvidenceVerificationReceiptPayload` is that shape.

**Payload, not receipt.** §13.3 rules that "a receipt that is unsigned … is
**not** a receipt. There is no 'trusted but unsigned' state." The payload is
unsigned, so it is not called a receipt. It is the canonical content the TEV-2
signer signs — and §13.3 required exactly that content, its canonicalization
version and its domain tag to be "unambiguous, versioned, and **fixed before
signing exists**", which is why TEV-1 fixed them.

**No signature field**, not even optional, not even a placeholder — and TEV-2
added none. TEV-1 owns the payload and its canonical bytes; TEV-2 owns the
signature, the envelope, the key trust and the revocation check, and keeps them
in a separate artifact so the payload's digest still covers bytes that contain
no signature (§13.3's signature-exclusion rule, satisfied literally).

| Field group | ADR |
|---|---|
| `receipt_id`, `schema` | receipt identity and version |
| `source_evidence_identity_digest`, `evidence_content_digest` | §13.1.2, §9.3 — binds digests, never payloads (§27.5) |
| `verification_request_digest` | what was asked |
| `scope` | §13.1.3 — tenant / context / subject / system / purpose / usage scope |
| `verified_at` | §9 row 6, §13.1.5 |
| `verifier_authority_id`, `verifier_key_id` | §9 row 14 — the key id is an **opaque coordinate**; no key format, algorithm or trust-anchor semantics is implied |
| `verification_protocol_id`, `verification_protocol_version` | §9 row 15 |
| `declared_outcome`, `declared_refusal_reasons` | §9 row 16 |
| `declared_cleared_stages`, `declared_unattempted_stages` | §13.1.1 — stages **1–5 only** (§12) |
| `evidence_valid_from` / `_to`, `receipt_valid_from` / `_to` | §13.1.6 — two **distinct** half-open intervals |

The canonicalization version and the receipt domain tag are bound by the
canonical **frame**, not carried as fields, so a caller cannot edit them and a
receipt digest can never be mistaken for an evidence-identity digest.

### Declared is not established

Every verification coordinate on a payload is a **declaration written by whoever
built the object**. `DeclaredVerificationOutcome` members carry a `DECLARED_`
prefix for exactly that reason, and the honest properties are unmoved by them:

```python
payload = EvidenceVerificationReceiptPayload(...)   # declaring every stage cleared,
                                                    # under an authoritative name
payload.declares_admission          # True  — what the payload SAYS
payload.declared_cleared_stages     # all five reportable stages — what it SAYS

payload.structural_status           # STRUCTURAL_UNVERIFIED — what is ESTABLISHED
payload.authenticity_verified       # False. Always.
payload.unestablished_trust_stages  # still contains CRYPTOGRAPHICALLY_AUTHENTIC
payload.envelope_verification_reason # TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED
```

`structural_status` and `authenticity_verified` are read-only **properties**, so
they have no backing field: `object.__setattr__` — the usual frozen-dataclass
bypass — raises rather than shadowing them, and a doctored instance dictionary
loses to the data descriptor.

A payload authorizes nothing (§13.2): not deployment, not runtime action, not
policy approval, not benchmark acceptance, not readiness classification, not
economic value, not causal attribution.

---

## Canonicalization (`v1`)

One encoder, one digest path. No alternate path, no legacy digest, no
dual-acceptance fallback.

```
{"body":{…}, "canonicalization":"ugence.trusted-evidence-authority/canonicalization/v1",
 "domain":"ugence.trusted-evidence-authority/evidence-identity/v1", "type":"<ContractName>"}
```

* Two domains, one encoder: evidence identity and its nested coordinates use
  `EVIDENCE_IDENTITY_DIGEST_DOMAIN`; the receipt payload uses
  `EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN`. A receipt digest can
  therefore never be reused as an evidence digest (§26.6), and the frame's
  `type` separates every contract within a domain.
* UTF-8 JSON, `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`.
* **Field inclusion is total** — nothing is dropped when empty; `None` is an
  explicit JSON `null`, distinct from `""`.
* Datetimes must be **timezone-aware**, are normalized to UTC via an explicit
  `astimezone(timezone.utc)`, and render `%Y-%m-%dT%H:%M:%S.%fZ` — **microseconds
  preserved**. Naive datetimes are **rejected**, never assumed UTC (§22.4).
* Strings must be **NFC**, enforced **at construction and again at
  canonicalization** — the two-boundary discipline ADR §22.4 fixes for naive
  datetimes. Non-canonical input is rejected, never silently normalized: folding
  NFD onto NFC would map two different artifacts onto one digest.
* `bool` is dispatched before `int`. **`float` is rejected outright**, which
  subsumes `nan`/`inf`/`-inf`.
* Mappings and `bytes` are rejected — no TEV-1 contract carries either, and
  rejecting mappings structurally enforces the no-metadata-dictionary rule.
* **Unknown types fail closed** (§22.8). There is no `default=` hook, no `str()`
  fallback and no `repr()` in the encoder.
* **No clock, locale, timezone database, environment variable, filesystem or
  network** input. Asserted by AST scans over the whole source tree.

The digest is sha-256 over exactly those bytes. The package tests pin a
hand-written literal byte string and reconstruct its digest with `hashlib`
alone, so a third party can recompute any digest without package internals.

**DD-9 explicitly leaves the exact byte constants to TEV-1/TEV-2**, and both
milestones fix theirs here, in the one module that owns domain selection.

**TEV-1 minted two**, and TEV-2 changed neither:
`EVIDENCE_IDENTITY_DIGEST_DOMAIN` for the evidence-identity family, and
`EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN` for the receipt payload —
because §13.3 required its tag "fixed before signing exists". It now is, and the
TEV-2 signer binds exactly that tag.

**TEV-2 minted five more**, one per artifact class it introduced:
`TRUST_ANCHOR_RECORD_DIGEST_DOMAIN`,
`SIGNED_EVIDENCE_SUBMISSION_DIGEST_DOMAIN`,
`SIGNED_RECEIPT_ENVELOPE_DIGEST_DOMAIN`,
`EVIDENCE_VERIFICATION_RESULT_DIGEST_DOMAIN` and
`EVIDENCE_VERIFICATION_AUDIT_RECORD_DIGEST_DOMAIN`. Adding keys to the domain
map left every existing key's value byte-identical, so **all four TEV-1 pinned
digests are unchanged** and a test pins each one.

Domain separation is what §26.6 buys with them: an evidence digest can never be
read as a receipt digest, an envelope digest can never be presented as the
payload content digest it wraps, and a verification *finding* can never be read
as an artifact an authority attested.

Only the **Benchmark Registry** domain remains unminted: no benchmark artifact
exists, and its tag belongs to its own ratified milestone (BR-1/BR-2).

---

## Refusal vocabulary

**40 codes** in **one** namespace — 19 from TEV-1, 21 appended by TEV-2. No
aliases, no deprecated spellings. Declaration order is the deterministic reason
ordering of §22.13.

TEV-1's nineteen keep their **exact ordinal positions**. That is not cosmetic:
§22.13's ordering sorts by declaration index, so interleaving new members among
them would silently re-order a refusal sequence a merged receipt was issued
under. `TEV1_TRUSTED_EVIDENCE_REFUSAL_REASONS` pins the original set and
`TEV2_TRUSTED_EVIDENCE_REFUSAL_REASONS` the additive block; tests assert the
first nineteen members are the TEV-1 nineteen, in order.

**One vocabulary, not two.** A separate TEV-2 enum was considered and rejected:
DD-1 delegates "the exact typed reason-code vocabulary … for evidence
verification" in the singular, and §22.11 requires a namespace "stable across
versions, never reused for a different meaning" — two parallel refusal enums
would be exactly the duplicate, conflicting namespace that rule prevents.

The TEV-2 block discharges the ADR §11 rows TEV-1 recorded as "**TEV-2.**" —
producer attribution (row 4), the key-lifecycle family (row 5) and
`SIGNATURE_INVALID` (row 6) — plus the envelope, profile, encoding,
trust-anchor, protocol and receipt-validity conditions §13.3 requires.

**Every member is still a refusal.** There is no success member, so
`TRUSTED_EVIDENCE_REFUSAL_REASONS == frozenset(TrustedEvidenceRefusalReason)`.
`TRUSTED_EVIDENCE_INDETERMINATE` is a **refusal, not a pass** — ADR §11: "*a
verifier that cannot decide has not verified*." Both TEV-2 outcome enums have
exactly two members, so no `UNKNOWN`/`PARTIAL`/`PENDING`/`BEST_EFFORT` state
exists for a consumer to read optimistically.

Codes for checks this package still cannot perform remain deliberately
**absent**: unit/metric mismatch is requirement-relative, so §12 assigns it to
the consuming evaluation engine, and benchmark refusals belong to BR-1/BR-2. A
code advertises a check; none is shipped for a check that does not exist.

---

## Dependencies

**Zero.** Standard library only — no Ugence package, no third-party package.
**TEV-2 signs, and this is still true.**

ADR §23 permits TAP to depend on `governance-contracts`. TEV-1 took the
narrower option because **DD-2** — which contracts land in that leaf — is
explicitly blocked on "the concrete contract shapes from TEV-1/BR-1", and
importing it now would decide DD-2 by implementation. TEV-2 keeps that posture.

### Why Ed25519 is implemented here rather than imported

The instruction for TEV-2 was to prefer Ed25519 **through the maintained
cryptography library** *unless the ADR or repository constraints require
otherwise*. Three constraints require otherwise, and **the algorithm profile is
unchanged either way — this is Ed25519, RFC 8032, PureEdDSA over edwards25519
with SHA-512**:

1. **ADR §23 fixes the dependency matrix.** TAP "may consume
   `governance-contracts` only"; a third-party runtime dependency is not an
   arrow the ratified matrix draws. TEV-1 shipped narrower still, with a merged
   test asserting the distribution declares no dependencies and no module
   imports anything but the standard library. Adding `cryptography` would break
   a merged, ratified test.
2. **The isolated `--no-index` install proof depends on it.** The distribution
   verifier installs the wheel into a clean virtualenv with `--no-index` and
   runs the adversarial probes inside it. A compiled third-party dependency
   cannot resolve there, so the strongest packaging proof this package has would
   have to be weakened.
3. **DD-10 keeps production key custody deferred** — "reference-grade first".

This is the convention two merged authorities already established for the same
reasons: `risk_authority/crypto/signing.py` and
`ugence_policy_authority/core/ed25519.py` each ship the same pure-Python RFC
8032 implementation, and Policy Authority's records that it "reproduces this
convention rather than importing `risk_authority`, which would create a reverse
dependency on another authority's internals".

It is a **standard algorithm implemented to its RFC**, using the RFC's own
extended-coordinate group law (§5.1.4), and all five published §7.1 test vectors
reproduce byte-for-byte. It is **not** constant-time — Python's integers offer
no constant-time arithmetic — and a production deployment must verify with a
vetted library and hold signing keys in an HSM or managed KMS (DD-10). The
signer is behind a port precisely so that substitution needs no caller change. `AssessedSystemBinding`
remains Governance Contracts' single definition (§14.1); this package references
it by opaque reference and digest and never redefines it.

Tests enforce both directions: nothing outside the standard library is imported,
and **no package in the monorepo imports this one** — TEV-1 authorizes no
consumer integration (UVI-EV-1 is DEFERRED).

### Versioning judgement

Package version **0.2.0** — an additive minor bump from TEV-1's 0.1.0. Every one
of TEV-1's 29 curated symbols remains exported with the same kind, the same
dataclass fields in the same order and the same enum members in the same order;
all four TEV-1 pinned digests are byte-identical; and the refusal vocabulary was
extended by appending, so TEV-1's nineteen codes keep their exact ordinal
positions. A major bump would misdescribe that; a patch bump would misdescribe
the grown public surface. **No separate `CONTRACT_VERSION` constant is minted.**
In this repository `CONTRACT_VERSION` is the *provider* convention
(`ugence-tap-provider`, `ugence-actiongate-provider`, the provider framework),
naming the version of a provider contract implemented against a kernel/framework
major. The contract-shape packages — `ugence-governance-contracts`,
`ugence-uvi-policy-contracts`, `ugence-policy-authority` — carry only
`__version__`. TEV-1 follows the contract-shape convention rather than inventing
a constant for symmetry. Versioning that *is* load-bearing here is carried where
it belongs: `TRUSTED_EVIDENCE_CANONICALIZATION_VERSION` is bound into every
digest, so changing an encoding rule requires a new version string.

---

## Usage

```python
from ugence_trusted_evidence_authority.api import (
    ApplicabilityCoordinate, ApplicabilityDeclaration, CanonicalEvidenceIdentity,
    EvidenceClaimBinding, EvidenceLifecycleState, EvidenceObservation,
    EvidenceProvenanceChain, EvidenceSchemaRef, EvidenceScopeBinding,
)
from datetime import datetime, timezone

ident = CanonicalEvidenceIdentity(
    evidence_id="ev-1",
    evidence_type="CONTROL_TEST_RESULT",
    schema=EvidenceSchemaRef(schema_id="ugence.evidence.control-test", schema_version="1"),
    content_digest=content_sha256_hex,
    observation=EvidenceObservation(
        producer_id="scanner-a",
        collected_at=datetime(2026, 3, 1, 12, tzinfo=timezone.utc),
        observed_from=datetime(2026, 3, 1, 10, tzinfo=timezone.utc),
    ),
    scope=EvidenceScopeBinding(
        tenant_id="tenant-1",
        assessment_context_ref="ctx-1", assessment_context_digest=ctx_sha256_hex,
        subject_ref="subject-1",
        assessment_purpose_ref="purpose-readiness", usage_scope_ref="scope-general",
        assessed_system_applicability=ApplicabilityDeclaration.APPLICABLE,
        assessed_system_binding_ref="bind-1", assessed_system_binding_digest=bind_sha256_hex,
    ),
    claim=EvidenceClaimBinding.applicable(
        metric_ref="control-pass-rate", unit="ratio",
        measurement_semantics_ref="semantics/control-pass-rate/v1",
    ),
    provenance=EvidenceProvenanceChain(chain_ref="chain-1", custody_refs=("collector-a",)),
    lifecycle_state=EvidenceLifecycleState.SUBMITTED,
    geography=ApplicabilityCoordinate.applicable("US"),
    domain=ApplicabilityCoordinate.not_applicable(),
    intended_outcome=ApplicabilityCoordinate.applicable("ticket-resolution"),
    valid_from=datetime(2026, 3, 1, tzinfo=timezone.utc),
    valid_to=datetime(2026, 9, 1, tzinfo=timezone.utc),
)

ident.canonical_digest()          # identity fingerprint — not evidence, not a signature
ident.authenticity_verified       # False. Always.
ident.unestablished_trust_stages  # five stages TEV-1 cannot establish
```

Import the curated surface from `ugence_trusted_evidence_authority.api` (or the
equivalently-exported top-level package). `public_api.json` snapshots it —
symbols, enum members **and order**, dataclass fields **and order**, and pinned
constant values.

## The TEV-2 verification authority

### Three roles, three objects

ADR §8's role matrix says "no row may absorb another", so the three TEV-2
responsibilities are three separate types even though a deployment wires them in
sequence:

| Object | Does | Cannot |
|---|---|---|
| `EvidenceVerificationAuthority` | verifies; produces a typed determination | hold a signing key, sign, issue |
| `ReceiptIssuer` | signs an **admitted** determination | verify, resolve a trust anchor |
| `SignedReceiptVerifier` | independently re-verifies an envelope | hold a key, issue anything |

A determination **cannot be constructed by a caller at all** — its constructor
demands a private token the curated API does not export — so the issuer never
has to decide whether to believe one. ADR §8.1.5: "no consumer may manufacture
verification."

### There is no "sign arbitrary bytes" capability

The obvious signer port shape, `sign(payload: bytes)`, is a public signing
oracle. Instead a signer receives a package-minted `ReceiptSigningInput`, and
the only route to one is:

```
verify evidence → an ADMITTED determination → issue → signature
```

An HSM- or KMS-backed signer implements the same `ReceiptSignerPort` and drops
in without touching a caller (DD-10). What it cannot be handed is bytes of the
caller's choosing.

*What this does not claim:* code executing in-process can import a private
module attribute, and no Python-level mechanism prevents that — the same is true
of the merged Policy Authority and Risk Authority signers. The token closes the
**public API** route, which is what it is for. The load-bearing secret is the
signing key, which lives only behind the port.

### The signature profile (DD-9)

One strict v1 profile. Not selectable, not negotiable, no `none`, no alias, no
fallback, no downgrade path:

| | |
|---|---|
| Algorithm | Ed25519 — RFC 8032, PureEdDSA over edwards25519 with SHA-512 |
| Signature encoding | bare lowercase base16, 128 characters |
| Public-key encoding | bare lowercase base16, 64 characters |

Base16 rather than base64 because a byte string has exactly **one** lowercase
hex spelling, and TEV-1 already uses bare lowercase hex for every digest. Base64
does not have that property — the trailing bits of a final quantum are
unconstrained by most decoders — which would let an attacker mint a different
envelope carrying the same signature. Uppercase hex, a `0x` prefix, whitespace
and any non-hex character are refused rather than normalized.

### Signed bytes are length-prefixed, never concatenated

Signing `a + b` is ambiguous: `("ab", "c")` and `("a", "bc")` produce the same
bytes. Every signed input is therefore a framed sequence:

```
frame = count(8 bytes, big-endian)
        ‖ for each element: length(8 bytes, big-endian) ‖ element bytes
```

The element count is bound first, so a frame cannot be extended or truncated
into another valid frame and no element boundary can be moved. There is no
separator an element could impersonate.

Two frames exist, and the **domain tag is element 0 of each**, so §13.3's "a
signature valid in one domain must not verify in another" holds by construction:

* `signed_evidence_input_bytes` — a producer's signature over an evidence item
  (establishes ADR §12 stage 2);
* `signed_receipt_input_bytes` — the authority's signature over a receipt
  payload (the ADR E-11 receipt).

The receipt frame binds the payload **twice**, by digest and by its full
canonical bytes, so a swapped payload, a swapped digest, or a payload/digest
pair that disagree are all signature failures rather than merely field
mismatches. Both functions are public and pure: a third party can reconstruct
either frame from the rules above and check a signature without package
internals.

### Trust anchors resolve by exact coordinate only

A trust anchor is found by the exact triple `(authority_id, key_id, capability)`
and nothing else. There is deliberately **no** `latest()`, no "current key", no
implicit default, no partial or prefix match, no acceptance on an authority
**name** alone (§10.3 lists that among the enumerated non-proofs), and no
first-key-wins — duplicate coordinates are refused at construction, so the
choice never arises. ADR §26.9: guessing is an unsigned authority decision.

`TrustAnchorCapability` holds **one** value, `EVIDENCE_PRODUCTION` or
`RECEIPT_ISSUANCE`. This makes ADR E-3 — "an evidence producer cannot verify its
own evidence" — structural rather than conventional: an anchor that both
produces and issues is not spellable.

A `TrustAnchorRecord` carries a **public** key as canonical hex and nothing
else. The canonical encoder rejects `bytes` outright and no public contract
declares a bytes field, so private material cannot reach a record, a digest, a
canonical byte sequence, a `repr` or an audit trail even by mistake.

### Time and revocation are explicit, and conservative

No clock is read anywhere (§22.9). Every instant is a parameter with no default
(§22.10): the verification instant, the evaluation instant, the key-validity
instant and the revocation-effective instant. Naive datetimes are refused at
every boundary. Intervals are half-open `[from, to)` per §17.9.

**Re-verification answers the *current* trust question.** ADR §13.3 settles the
delegated choice: "key revocation is checked **at verification time**; a receipt
signed by a key that was later revoked is **not silently honoured**." So the key
window, the revocation and the receipt's own validity are all evaluated at the
caller's `evaluated_at`, never at the payload's `verified_at`. A previously
valid receipt stops verifying once its key is revoked — **a signature is never
grandfathered**.

The refusal keeps enough typed evidence to be *explained* rather than merely
reported: it names `TRUSTED_EVIDENCE_KEY_REVOKED`, and carries the evaluation
instant and the resolved coordinate, so a reader can see the receipt was signed
before the revocation and is refused because trust is being asked about *now*.

**Historical re-verification is deliberately not offered.** "Was this trusted at
instant T" needs an as-of-T trust semantics — which anchors were configured
then, which revocations were known then — that no merged clause defines for
evidence. §17.1's historical resolution is a Benchmark Registry concept and is
BR-2's. Offering a plausible-looking answer would resolve a question the ADR
retains elsewhere, so the API offers none.

### Verified means verified — and nothing more

`ReceiptVerification.verified` is a read-only property derived from a closed
two-member outcome, and the only code path that produces `VERIFIED` is the one
that reaches an actual signature check returning true. It is never stored and
never caller-settable; a `ReceiptVerification` cannot be constructed by a caller
at all.

`True` means: an anchor resolved at the exact coordinate, was entitled to issue
receipts, was in its validity window, was not disabled, was not revoked at the
evaluation instant, and its public key verified the reconstructed frame; and the
payload digest, the caller's expected coordinates and the receipt's own validity
all agreed.

It does **not** mean the evidence is true, that a claim is valuable, that
attribution holds, or that anything is authorized (§13.2, E-12). Stage 6 is
never established, by anything, ever (§12).

> **One documented weakening.** Every `expected_*` argument to
> `SignedReceiptVerifier.verify` defaults to *not checked*, so the §13.3 third
> party holding only an envelope can still verify a signature. A verified result
> is therefore **not** a scope decision unless a scope was asserted: a consumer
> binding evidence to its own tenant, context, subject, system, purpose or scope
> must pass those coordinates. §26.5's replay detection is only mechanical for
> coordinates someone actually asserts. Tests exercise both forms.

---

## TEV-2 delegated decisions

Each decision below was delegated to this milestone by the ADR, and is recorded
with the clause that delegates it. No decision retained for another milestone is
resolved here.

| Decision | Taken | Authority |
|---|---|---|
| Signature algorithm profile | Ed25519, RFC 8032 PureEdDSA/SHA-512, single strict v1 | DD-9 ("algorithm identifiers"), §22.8 |
| Signed-byte construction | length-prefixed frame, domain tag as element 0 | §13.3 domain separation; §22.1 |
| Signature encoding | bare lowercase base16, one spelling | DD-9 ("encodings") |
| Signer-authority identity | `signer_authority_id`, bound into the frame | §9 row 14 |
| Key identifiers | `signing_key_id`, exact-match, bound into the frame | §9 row 14, §10.3 |
| Trust-anchor representation | immutable `TrustAnchorRecord`, public material only | §30 TEV-2; E-5 composition root |
| Key validity intervals | half-open `[effective_from, effective_to)` | §17.9 |
| Revocation representation and effective time | dated `KeyRevocation`, revoked at `t >= effective_at` | §13.3, §26.8 |
| Historical vs current re-verification | **current only**; no historical API | §13.3 ("checked at verification time"); §17.1 is BR-2's |
| Protocol identity / version | `EvidenceVerificationProtocolPort`, id and version bound separately | §9 row 15 |
| Receipt-envelope canonicalization | own digest domain; payload digest excludes the signature | §13.3, §22.1, §26.6 |
| Typed refusal reasons | 21 codes appended to the one vocabulary | DD-1, §11 rows 4-6, §22.11 |
| Verification-time inputs | every instant an explicit parameter, no defaults | §22.9, §22.10 |
| Receipt identifier | deterministic digest over the act's coordinates | DD-9; forced by the ban on clocks and randomness |
| Envelope issuance time | **none minted** — `verified_at` is the ratified instant | §9 rows 5-6, §13.1.5 |
| Key tenant scoping | **none minted** — no ratified clause scopes a *key* to a tenant | §9 binds tenant to evidence and receipt; DD-3 open |

---

## Build and verify

```bash
python -m build packages/trusted-evidence-authority
python packages/trusted-evidence-authority/verify_trusted_evidence_authority_distribution.py
python -m pytest packages/trusted-evidence-authority -q
python packages/trusted-evidence-authority/adversarial_probes.py
```

The distribution verifier builds the wheel, asserts it ships exactly one
top-level namespace plus dist-info and `py.typed` (no tests, probes, fixtures,
build tree, foreign package or duplicate module), installs it into a fresh
`--no-index` virtualenv with no monorepo path, and re-runs the surface-parity
check and the independent adversarial probes against that installed runtime.

`adversarial_probes.py` imports **only** the curated public API — no test
module, helper, fixture or conftest — and recomputes every expected digest with
`hashlib` alone, so it cannot merely re-confirm the test suite's assumptions.

## Status

**TEV-1 implemented** — the contract shapes, including the §13 receipt *payload
shape* that §30 and the §32 ledger assign to that milestone.

**TEV-2 implemented** — evidence-verification orchestration, an explicit
verification-protocol boundary, trust-anchor and public-key resolution, key
validity and revocation evaluation, receipt-payload issuance only after
successful verification, cryptographic signing of the already-ratified payload,
the immutable signed envelope, independent envelope re-verification, typed
fail-closed outcomes, deterministic audit records, and dedicated package CI.

**Still DEFERRED**, per ADR §30 and the deferred-decisions ledger §31:

| Deferred | Owner |
|---|---|
| Benchmark Registry packages, definitions and resolution | BR-1 / BR-2 |
| Readiness evidence integration | UVI-EV-1 / M-3R.4 |
| Forecast, observed, attributed and verified ROI | GV-F → GV-V |
| Policy applicability resolution | Ugence Policy Authority |
| RA-5 `EvidenceAdmissionPort` alignment | DD-6 (E-13 keeps RA-5 unchanged) |
| Production persistence, HSM/KMS posture, distributed concurrency | DD-10 |
| A trusted `AssessedSystemBinding` verifier | DD-5 |
| `SystemManifest` home | DD-11 |
| Provenance / chain-of-custody disclosure scope | DD-7 |

Also absent by design: network trust-anchor retrieval, certificate-authority
infrastructure, credential issuance, receipt persistence or distribution
services, ActionGate or deployment authorization, Cloud Scaling integration, and
generic multi-algorithm cryptographic agility. **No consumer imports this
package**, and a test enforces that.
