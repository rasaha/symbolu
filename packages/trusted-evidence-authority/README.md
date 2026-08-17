# ugence-trusted-evidence-authority

**Ugence Trusted Evidence Authority — TEV-1 trusted-evidence contracts.**

The platform **Trust Assurance** role's contract package, ratified in
[`ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md`](../../docs/architecture/ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md)
(E-1, E-2, §6.2) and implementing milestone **TEV-1** of §30.

Internal platform infrastructure — **not** a customer-facing module, **not** a
product, **not** a fourth UVI engine (B-2). It holds immutable contract *shapes*
and mints **no authority**.

---

## What this package is

| | |
|---|---|
| **Canonical evidence identity** | `CanonicalEvidenceIdentity` plus the nested `EvidenceSchemaRef`, `EvidenceObservation`, `EvidenceScopeBinding`, `EvidenceProvenanceChain`, `ApplicabilityCoordinate` |
| **One canonicalization path, one digest path** | `canonical_bytes` / `canonical_digest`, versioned and domain-separated |
| **Trust-stage vocabulary** | `EvidenceTrustStage` — the six distinct ADR §12 stages, plus the ratified `EVIDENCE_TRUST_STAGE_ORDER` |
| **Lifecycle** | `EvidenceLifecycleState` and the closed ADR §28 relation `EVIDENCE_LIFECYCLE_TRANSITIONS` |
| **Typed refusal vocabulary** | `TrustedEvidenceRefusalReason` — 19 codes, **every one a refusal** |
| **Typed contract errors** | `TrustedEvidenceContractError` and two subclasses |
| **TEV-2 input contract** | `EvidenceVerificationRequest` — expectations in; **no verdict** |

## What this package is **not**

It is **not a verifier**. It performs no trust-anchor resolution, no
cryptography, no key management or revocation, no authenticity decision, and it
issues no receipt. There is no placeholder verifier, no permissive stub, and no
field reserved for a later milestone. All of that is **TEV-2** (ADR §30).

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
authority-verified member requires a verifier, trust anchors and signature
verification, which is TEV-2.

Per ADR §10, none of the following is proof of verification, and the package
holds to that structurally: a `verified=True` flag (there is no such parameter);
a lifecycle label; an authority **name**; a caller-supplied confidence score
(there is no such field); an unsigned verification object (there is no such
type). **Possession, parsing, canonicalization and digest equality prove
nothing** (§8.1.3).

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
| `provenance.chain_ref`, `custody_refs` | §9.13 | custody order is semantic; duplicates refused |
| `lifecycle_state` | §28 | what the artifact *asserts* — never verified here |
| `geography`, `domain`, `intended_outcome` | §15 r6–8, UVI D-13 | explicitly `APPLICABLE` with a value or `NOT_APPLICABLE` — **never omitted** |
| `valid_from` / `valid_to` | §9.17 | half-open `[valid_from, valid_to)` (§17.9) |

### Coordinates deliberately **not** here

ADR §9 rows 6 and 14–16 — the **verification instant**, the **verifier authority
and key identifier**, the **verification protocol/version**, and the
**verification status and reason codes** — describe an act TAP performs. No TEV-1
object performs it. Carrying them on a caller-constructible contract would
produce exactly the artifact §10 forbids consumers from trusting: a structurally
valid object naming an authority, a protocol and a status that nobody issued.

**No receipt type ships either.** ADR E-11 makes the receipt *signed*, and §13.3
is unambiguous: "a receipt that is unsigned … is **not** a receipt. There is no
'trusted but unsigned' state." TEV-1 cannot sign, so the receipt shape lands with
the signing that makes it meaningful — **TEV-2**.

**No `SystemManifest`** is defined, named as owned, or placed (DD-11 stays open).
**No supersession** exists: the ratified *evidence* lifecycle (§28) has no
supersession arrow — that is the *benchmark* lifecycle (§29), itself deferred to
DD-4 — so no supersession state and no supersession refusal code is minted.

---

## Canonicalization (`v1`)

One encoder, one digest path. No alternate path, no legacy digest, no
dual-acceptance fallback.

```
{"body":{…}, "canonicalization":"ugence.trusted-evidence-authority/canonicalization/v1",
 "domain":"ugence.trusted-evidence-authority/evidence-identity/v1", "type":"<ContractName>"}
```

* UTF-8 JSON, `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`.
* **Field inclusion is total** — nothing is dropped when empty; `None` is an
  explicit JSON `null`, distinct from `""`.
* Datetimes must be **timezone-aware**, are normalized to UTC via an explicit
  `astimezone(timezone.utc)`, and render `%Y-%m-%dT%H:%M:%S.%fZ` — **microseconds
  preserved**. Naive datetimes are **rejected**, never assumed UTC (§22.4).
* Strings must be **NFC**; non-canonical input is rejected, never silently
  normalized — folding NFD onto NFC would map two different artifacts onto one
  digest.
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

The evidence-identity domain tag and canonicalization version are fixed here
because **DD-9 explicitly leaves the exact byte constants to TEV-1/TEV-2**. The
receipt and benchmark domains are *not* minted — their artifacts do not exist.

---

## Refusal vocabulary

19 codes, namespace `TRUSTED_EVIDENCE_…`, no aliases and no deprecated
spellings. Declaration order is the deterministic reason ordering of §22.13.

**Every member is a refusal.** There is no success member, so
`TRUSTED_EVIDENCE_REFUSAL_REASONS == frozenset(TrustedEvidenceRefusalReason)`.
`TRUSTED_EVIDENCE_INDETERMINATE` is a **refusal, not a pass** — ADR §11: "*a
verifier that cannot decide has not verified*."

Codes for checks TEV-1 cannot perform are deliberately **absent**: producer
authorization and every key/signature code (trust anchors and cryptography —
TEV-2), and unit/metric mismatch (requirement-relative, so §12 assigns it to the
consuming evaluation engine). A code advertises a check; none is shipped for a
check that does not exist.

---

## Dependencies

**Zero.** Standard library only — no Ugence package, no third-party package.

ADR §23 permits TAP to depend on `governance-contracts`. TEV-1 takes the
narrower option because **DD-2** — which contracts land in that leaf — is
explicitly blocked on "the concrete contract shapes from TEV-1/BR-1", and
importing it now would decide DD-2 by implementation. `AssessedSystemBinding`
remains Governance Contracts' single definition (§14.1); this package references
it by opaque reference and digest and never redefines it.

Tests enforce both directions: nothing outside the standard library is imported,
and **no package in the monorepo imports this one** — TEV-1 authorizes no
consumer integration (UVI-EV-1 is DEFERRED).

### Versioning judgement

Package version **0.1.0**. **No separate `CONTRACT_VERSION` constant is minted.**
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
    EvidenceLifecycleState, EvidenceObservation, EvidenceProvenanceChain,
    EvidenceSchemaRef, EvidenceScopeBinding,
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

**TEV-1 implemented.** TEV-2 (verification service, trust anchors, key trust and
revocation, signing, signed receipts, independent verification), BR-1/BR-2
(Benchmark Registry), UVI-EV-1 / M-3R.4 (Readiness integration) and GV-F → GV-V
remain **DEFERRED** per ADR §30. No consumer integration exists.
