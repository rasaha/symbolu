# Ugence UVI Policy Authority (`ugence-uvi-policy-authority`)

**Internal technical package — not a customer-facing module, and not a
general-purpose governance authority.**

A narrow authority leaf that owns exactly one technical job: **issuing, signing,
registering, resolving, verifying and revoking UVI policy *versions*** for the
five merged UVI policy families.

Milestone **GV-2C-b** of the UVI ADR
([`docs/architecture/ADR_UGENCE_VALUE_INTELLIGENCE_GV2C_GV2E_GV3R.md`](../../docs/architecture/ADR_UGENCE_VALUE_INTELLIGENCE_GV2C_GV2E_GV3R.md)),
supplying the approval / signing-issuance / policy-version-revocation ownership
that ADR §19 recorded as a required dependency and §26.1 left as an open owner
ruling.

---

## The separation this package exists to enforce

| Responsibility | Owner | This package |
|---|---|---|
| Authoring policy content | humans / domain owners | **no** |
| Deciding whether policy content is *good* | humans / governance | **no** |
| **Approving** a policy version | an external approval authority | **no — verified, never performed** |
| Compiling policy → IR | `tooling/policy-workflow-compiler` | **no** |
| **Issuing + signing** a policy version | **this package** | yes |
| **Registering** issued versions | **this package** (reference registry) | yes |
| **Trusted resolution** of an exact version | **this package** | yes |
| **Policy-version revocation** | **this package** | yes |
| Envelope / runtime-authority revocation | `risk_authority` | **no — a distinct concept** |
| Readiness evaluation | `agent-value-readiness` | **no** |
| Financial valuation | `governed-value` | **no** |
| Benchmark values / registry | later milestone | **no — deferred** |

**Approval remains external.** The authority never approves its own policy. It
requires an externally produced approval artifact, verified through an injected
trusted boundary, and independently re-checks that the verification binds the
exact policy being issued — including that the approving authority is *not* the
issuing authority. This package does **not** implement the organizational
approval process; it implements the technical refusal to issue without one.

Explicitly **not** approval, and each proven by a test:

- a caller-supplied `approved=True` — no such parameter exists;
- a caller-supplied authority *name* — a bare string names nobody;
- `PolicyLifecycleState.APPROVED_ACTIVE` on the artifact — a self-assertion;
- any evidence-status enum.

The only approval verifier shipped in production code is
`DenyAllApprovalVerifier`. Deterministic fakes exist only under `tests/`.

---

## What a resolution does and does not prove

These six things are kept strictly apart. Conflating them is the failure mode
this package is designed to prevent.

1. **Structural validity** — the artifact satisfies the merged contract shapes.
   Owned by `ugence-uvi-policy-contracts`, not here. Proves nothing about trust.
2. **Cryptographic issuance authenticity** — this exact artifact, under this
   exact reference, was signed by the named key of the named issuing authority,
   and nothing bound into the signature has changed since.
3. **Approval verification** — an *external* approval authority verified this
   exact policy version, and the authority re-checked that binding.
4. **Lifecycle / effective-period validity** — the artifact is `APPROVED_ACTIVE`
   and `as_of` falls inside its half-open effective period.
5. **Registry resolution** — a record exists under the complete exact reference
   and has not been revoked. *Lookup alone is not validity*: a record a caller
   assembled by hand reaches exactly the same digest, key and signature checks
   and fails them.
6. **Business correctness of the policy content** — **not proven, at all, by
   anything here.**

> The authority proves **who issued the bound artifact under configured trust**.
> It does **not** prove the policy is wise, correct, lawful, or commercially
> sound, and it guarantees no business outcome. A resolved policy is an
> authenticated artifact, not a good decision.

---

## The content digest

The merged contracts declare `PolicyArtifactMetadata.content_digest` to be "the
authority-attested digest of the policy content" and deliberately leave the
computation to the Policy Authority — nothing in `uvi-policy-contracts` computes
it. This package supplies that missing rule. It introduces no competing one.

```
policy_body_digest(P) = sha256( canonical_json( {
    "domain":      "ugence.uvi.policy-authority/policy-body/v1",
    "policy_type": <exact runtime dataclass name>,
    "body":        canonical(P) with the single path
                   metadata.content_digest REMOVED from the mapping,
} ) )
```

The self-referential field is **removed**, not blanked — no placeholder value
participates, and no iteration to a fixed point is needed. The digest is
computable in one pass, and setting `content_digest` to the result cannot change
the result. Everything else is bound: all governed content, and every metadata
identity field (`policy_id`, `policy_family`, `version`, `scope`, `tenant_id`,
`lifecycle_state`, the effective period, `issuer_ref` / `approval_ref` /
`supersedes_ref`, `created_at`).

A policy artifact has **no signature field**, so the body digest is structurally
incapable of depending on a signature. A syntactically perfect but arbitrary
64-hex string is never accepted as evidence that a body matches it.

---

## Signing

Signing and verification are **injected protocols** (`PolicySigner`,
`PolicySignatureVerifier`), so an HSM- or KMS-backed implementation drops in
without touching a caller.

The shipped reference implementation is **Ed25519 (RFC 8032), stdlib-only**,
following the repository's existing convention for an authority leaf
(`risk_authority/crypto/signing.py`) — reproduced rather than imported, because
importing another authority's internals would create the reverse dependency
ADR §21 forbids. It is a standard algorithm implemented to its RFC: **not**
bespoke cryptography, and **not** a hash or HMAC presented as a signature.

*Status: signing is **implemented**, not protocol-only.* As with the existing
convention, the pure-Python implementation is a correct but unoptimised
reference: a production deployment must verify with a vetted library and hold
signing keys in an HSM / managed KMS.

The signed payload is domain-separated and binds the authority protocol and
version, record id, policy family / id / version / scope / tenant, content
digest, canonical body digest, approving authority, approval reference and
digest, issuing authority, key id, signature algorithm, and the issuance
timestamp. Altering any one of them invalidates verification. Keys resolve by
**exact `key_id`**; unknown, revoked, out-of-window, wrong-authority and
wrong-tenant keys each fail closed with a distinct typed status. No private key
material can live in any record, result or registry entry.

---

## Registry

`InMemoryPolicyRegistry` is **reference-grade, not production persistence** — no
durability, no replication, no operational story. A production registry
implements the `PolicyRegistry` protocol against real storage.

- **exact resolution only**: id + family + version + content digest + scope +
  tenant. There is deliberately **no** `latest()`, `current()` or `find_by_id()`
  — a floating reference is unrepresentable in the trusted path, not merely
  discouraged;
- **append-only**; issued versions are never overwritten or deleted;
- byte-identical re-submission is **idempotent**; any other reuse of an
  identity/version slot is a typed conflict;
- cross-tenant lookup is a typed not-found that leaks nothing;
- returned records are deeply immutable frozen dataclasses, so a caller can
  neither mutate stored state nor reach it through a collection it handed in.

---

## Issuance ordering

One canonical entry point, `issue_policy`, in a fixed order:

1. structural request validation (including that `issued_at` is timezone-aware —
   the minimum validated operation timestamp);
2. supported-family and identity validation;
3. canonical body / digest verification;
4. **approval verification**;
5. explicit timestamp validation (lifecycle + effective period at `issued_at`);
6. signature production;
7. immutable record construction;
8. atomic registry append.

Proven by tests: the signer is never called when approval fails; the approval
verifier is never called after an earlier structural failure; and the registry is
byte-for-byte unchanged after a failure at *any* stage.

**The clock is injected.** No `datetime.now`, `utcnow`, or implicit wall clock
exists anywhere in the package — asserted by an AST scan over the whole source
tree. A successful issuance reads **exactly one caller-supplied instant**,
`issued_at`, and derives every timestamp from it, so identical inputs produce
byte-identical records.

---

## Revocation and historical resolution

Policy-version revocation targets one **complete exact** `PolicyReference`, is
append-only, and is timestamped with an injected instant. A raw boolean or a
lifecycle label cannot revoke anything. Revoking one version cannot reach
another version, and cross-tenant revocation is rejected.

- Resolution fails closed **at and after** `revoked_at`.
- Strictly **before** `revoked_at`, behaviour is an explicit configured decision:
  `HistoricalResolutionRule.DENY_ALWAYS` (**the default** — a revoked version
  never resolves, at any `as_of`) or `ALLOW_BEFORE_REVOCATION` (an explicitly
  historical `as_of` may resolve).
- A revocation record **denies on presence**. Its own signature is not required
  to be verifiable — an unverifiable revocation still denies, so the failure
  direction is closed, never open.
- Authority/key revocation and policy-version revocation are distinct; neither
  implies the other. The Risk Authority's envelope authority-epoch is **not**
  reused here.

---

## Supersession — a deferred owner decision

`PolicyArtifactMetadata.supersedes_ref` is an unstructured `str` in the merged
contracts. It cannot bind a complete exact `PolicyReference` (no family, digest,
scope or tenant), so the authority **refuses to infer** a binding supersession
from it:

- `SupersessionRule.SELF_DECLARED_ONLY` (default) — only an artifact's own
  `SUPERSEDED` lifecycle invalidates it;
- `SupersessionRule.STRICT_UNDETERMINED_ON_SUCCESSOR` — fails closed with the
  typed `SUPERSESSION_UNDETERMINED` status when a successor exists whose
  `supersedes_ref` cannot be resolved to an exact reference.

Either way, supersession never mutates or deletes the older record. Making
successor-based supersession *binding* requires a structured successor reference
in the contracts — a separate contract milestone and an owner ruling, not
something this package invents.

---

## Time

All timestamps are timezone-aware; naive datetimes are refused everywhere. The
effective period is half-open: `effective_from` **inclusive**, `effective_to`
**exclusive**, a missing upper bound open-ended. A lifecycle label can never
override time, and a valid time window can never override an invalid lifecycle.

---

## Dependencies

```
ugence-uvi-policy-authority
      ├── ugence-uvi-policy-contracts >= 0.1.0
      └── ugence-governance-contracts >= 0.2.0
```

Standard library only otherwise. It imports **no** `agent-value-readiness`, **no**
`governed-value`, **no** Risk or Decision Authority internals, **no** Agent
Runtime, **no** Runtime Assurance, **no** forecasting, and **no** benchmark-value
service. Enforced by `tests/packaging/test_dependency_boundary.py`.

## Usage

```python
from ugence_uvi_policy_authority.api import (
    ApprovalEvidenceRef, Ed25519PolicySigner, InMemoryPolicyRegistry,
    PolicyKeyRing, SigningKey, issue_policy, resolve_policy,
)

signer = Ed25519PolicySigner(
    authority_id="ugence.uvi.policy-authority",
    key_id="uvi-pa-key-1",
    signing_key=SigningKey.generate(),
)
key_ring = PolicyKeyRing().with_key(signer.verification_key())
registry = InMemoryPolicyRegistry()

record = issue_policy(
    policy=policy,                        # one of the five merged families
    record_id="rec-2026-0001",
    approval=ApprovalEvidenceRef(
        approval_ref="APPROVAL-2026-0001",
        approval_digest=approval_artifact_sha256,
        approving_authority_id="ugence.governance.policy-approval-board",
    ),
    approval_verifier=trusted_verifier,   # injected; deny-all by default
    signer=signer,
    registry=registry,
    issued_at=operation_instant,          # injected; no clock is read
)

result = resolve_policy(
    reference=policy.reference,
    expected_tenant_id="",
    as_of=evaluation_instant,
    registry=registry,
    signature_verifier=key_ring,
)
if result.resolved:
    use(result.policy)                    # returned by value, with its proof
else:
    handle(result.reason)                 # a stable typed reason, never a string
```

## Verification

```bash
python -m pytest packages/uvi-policy-authority/tests -q
python packages/uvi-policy-authority/verify_uvi_policy_authority_distribution.py
python packages/uvi-policy-authority/adversarial_probes.py
```
