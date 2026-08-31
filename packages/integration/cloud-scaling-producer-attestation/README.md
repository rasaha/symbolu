# Ugence Cloud Scaling Producer Attestation

**Cloud Scaling Phase 5B-0A — producer authenticity.**
Distribution `ugence-cloud-scaling-producer-attestation` · namespace
`ugence_cloud_scaling_producer_attestation` · version **0.1.0**.

> **A verified attestation grants nothing.**
> It establishes *who produced a recommendation*, and it stops there. It is not an
> authorization, not an envelope, not an ActionGate admission, not a credential, and not
> permission to execute anything.

---

## The gap this closes

Before this package, a self-consistent forged recommendation laundered cleanly through the
entire Cloud Scaling chain:

1. a forger invents capacity facts and runs them through the controller's **real** Phase-3
   pipeline, so the recommendation is internally consistent;
2. its unkeyed content digest matches its own content — an unkeyed digest is a function of
   content, and the forger controls the content;
3. Phase 4C's **structural** admission passes;
4. a genuine Risk Decision is minted for it;
5. a valid Phase 5A `CapacityAuthorizationCandidate` is built.

Every step is correct. None of them was ever specified to establish **provenance**. Phase
5A carries a producer attestation and says so plainly: it never checks the signature, and
its one trust state is `PRESENT_BUT_NOT_TRUST_VERIFIED`.

Phase 5B-0A makes such an attestation **mintable and verifiable for the first time**, and
`tests/test_authenticity_laundering.py` walks the whole traversal and proves it now ends in
a typed refusal.

## What it provides

| Piece | What it is |
|---|---|
| `ProducerAttestationV2` | A new, separately tagged contract. Its signed payload binds **issuer, tenant, subject and subject type** as well as the recommendation id and digest — the facts a verifier must reconcile before a signature means anything about *this* recommendation for *this* workload. |
| `mint_producer_attestation` | The one route to a producer signature, through a token-guarded signing input, at the Controller's **output boundary** and never inside it. |
| `ProducerAttestationSignerPort` | An injected signer port with **no** "sign arbitrary bytes" method. Exactly one reference signer ships, marked `is_reference_signer = True`. |
| `ProducerAttestationVerifier` | The authoritative routine. It **recomputes** the signed payload from the candidate's own reconciled facts and refuses unless the bytes match, resolves the key through the Trusted Evidence Authority's existing trust-anchor store, and checks the signature under a strictly validated public key. |
| `VerifiedProducerAttestation` | The exact-typed, immutable, **non-authoritative** result, constructible only by that routine and revalidated at every consumption boundary. |
| `ProducerAuthenticityOutcome` | A closed typed vocabulary. Security outcomes are told apart by member, never by message string. |

## The verification sequence

Ordered, stop at the first failing group, deterministic. No later group can rescue an
earlier failure, and only after all ten does an artifact exist.

1. **exact-type admission** — candidate, attestation and `as_of`
2. **contract admission** — schema tag, signing purpose, algorithm, profile, encoding
3. **reconciliation** — recommendation id and digest, tenant, subject, subject type, taken
   **from the candidate** and compared against the attestation's claims
4. **payload recomputation** — rebuild the canonical payload from the reconciled facts and
   require **byte equality** with the attestation's own signing payload
5. **anchor resolution** — at the exact `(issuer, key_id, capability)` coordinate
6. **anchor identity re-check** — a resolver may not answer a question it was not asked
7. **anchor lifecycle** — revoked, disabled, not-yet-valid, expired, at the injected instant
8. **profile and encoding agreement** — attestation against the resolved anchor
9. **signature decoding** — canonical lowercase base16 of exactly the Ed25519 length
10. **signature verification** — under the anchor's strictly validated public key

Step 4 is what separates this from a verifier that merely checks a signature over whatever
it was handed. A genuine attestation for a *different* recommendation, tenant or subject
fails before a key is even resolved.

## What it deliberately does not do

* **Phase 5A stays at 0.1.0, unmodified.** This package does not change its canonical
  dictionaries, its candidate digest, or the documented limitation of its v1 attestation,
  and it does not reinterpret that unverified field as verified. The v2 proof travels
  **alongside** a candidate; binding one *inside* a candidate would need a Phase 5A 0.2.0,
  which is Phase 5B-0B's work. What it is bound to is stated precisely below — the
  *recommendation*, by id and content digest, and **not** the candidate: see
  [What the signature covers](#what-the-signature-covers).
* **The Cloud Scaling Controller stays at 0.4.0**, key-free and advisory. It gains no
  private key, no signer, no crypto dependency and no new export. Its own statement stands:
  its recommendation digest is not a signature, not an authorization and not a proof of
  effect.
* **Policy authenticity remains unresolved.** Nothing here establishes that the policy
  binding a candidate carries is genuine or in force. That is Phase 5B-0B's, and it is
  open.

Not implemented and not reachable from here: Risk Decision reconstruction, Risk Authority
v3, scope repair, nonces and replay ledgers, audience, envelope-request construction,
envelope signing, containment lifting, ActionGate, credentials, execution, effect
verification and learning. `tests/test_import_boundary.py` asserts each absence
structurally.

## Reuse, and what was not reused

Trust anchors are the Trusted Evidence Authority's, reused unchanged and re-exported:
`TrustAnchorCoordinate`, `TrustAnchorRecord`, `TrustAnchorCapability`,
`TrustAnchorResolution`, `TrustAnchorResolverPort`, `KeyRevocation`,
`StaticTrustAnchorDirectory`, `DenyAllTrustAnchorDirectory`. There is **no second
trust-anchor store** in this repository, and `tests/test_trust_reuse.py` asserts each
symbol is the *identical object*.

TEV's evidence and receipt **verifiers** are not reused. A producer attestation is not an
evidence item — different schema tag, different signing purpose, different field set — and
a verifier specified against one payload has not verified another. Its evidence framing and
domain tags stay TEV's too: this package signs Risk Authority's canonical bytes, and domain
separation is carried inside them by the schema tag and the signing purpose.

**Trust-anchor capability.** `PRODUCER_ATTESTATION_CAPABILITY` is
`TrustAnchorCapability.CLOUD_SCALING_RECOMMENDATION_ATTESTATION` — a **dedicated**
capability for this signing domain, not a borrowed evidence one.

An earlier revision used `EVIDENCE_PRODUCTION`, reasoning that a producer attestation is
"the producer role". Because the repository keeps **one** trust-anchor store, that made a
key provisioned purely to sign Trusted Evidence equally entitled to attest a capacity
recommendation — an independent closure audit demonstrated it with a telemetry-agent key
holding no Cloud Scaling grant. The capability is not a label on a role; it is the part of
the coordinate the anchor is resolved by, so it is where the entitlement has to be named.
Domain separation inside the signed bytes prevents signature *replay* across domains; it
does not decide which *keys* a domain trusts, and neither does an anchor-set id, a naming
convention or deployment documentation.

The three capabilities are mutually disjoint and exactly compared: a receipt-issuance key
cannot verify a producer attestation here, an evidence-production key cannot either, and
the dedicated capability produces no TEV evidence and issues no TEV receipt. One key may
hold several grants, but each is a separate, explicitly configured anchor record.

What a verified attestation establishes is bounded and worth stating plainly: the
publisher's signature is authentic, and the recommendation's content and context are
cryptographically bound to it. No risk decision, authorization, envelope, ActionGate
grant, credential or execution permission is created. TEV does not approve or admit the
recommendation — it defines the coordinate and verifies nothing under it. Which keys
receive the capability is the composition root's decision.

**Reference versus production grade.** The repository classifies
`StaticTrustAnchorDirectory` as reference grade in its own words ("the deterministic
*reference* resolver … suitable for tests, for local use"). `require_production_resolver`
therefore **refuses it under `production_mode=True`** — and **every subclass of it**,
before the opt-in is even read. A subclass inherits the reference implementation whole, so
declaring `is_production_authoritative = True` on one does not make it production grade;
matching the exact type instead, as an earlier revision did, let a three-line subclass
through while refusing the base class it was identical to. The denial is scoped to
inheritance only: an independently implemented resolver that opts in is admitted, and so is
one that merely holds a reference directory as a delegate. Otherwise the Risk Authority's
`is_production_authoritative` convention applies unchanged.

The **signer** side is the same mechanism, spelled the same way.
`mint_producer_attestation(production_mode=True)` refuses
`ReferenceEd25519ProducerAttestationSigner` and every subclass of it, matched by `isinstance`
against `REFERENCE_GRADE_SIGNERS`. That match is what closes the hole — a subclass inherits
the reference key custodian whole, so setting `is_reference_signer = False` on one relabels
it without changing what holds the key.

The `is_reference_signer` check remains alongside it and earns its place independently: it
catches a *non*-inheriting custodian that honestly declares itself reference grade. Both
raise, so neither depends on running first; the `isinstance` match is placed first for the
**message**, so a subclass is named as reference grade rather than reported through the flag
it set for itself. A custodian that *composes* a signer rather than inheriting from one is
admitted, because composition is a decision about where the key lives and such a custodian
never declared itself reference grade.

`DenyAllTrustAnchorDirectory` is admitted, because it can only ever refuse — it is the
ratified deny-by-default posture, and the only "no anchors" shape that ships. That exemption
is matched on the **exact** type: subclassing narrows nothing, so a subclass of it is not
known to deny everything and does not inherit the exemption.

## What the signature covers

The producer's signature and the artifact's own integrity digest are **not** the same
coverage, and reading one for the other over-claims the guarantee.

`artifact_digest` covers every field on `VerifiedProducerAttestation`. That is an integrity
digest this package computes; its job is to stop a field being rewritten after construction.

The **producer's signature** covers exactly the fourteen keys of the v2 signing payload:

| | |
|---|---|
| identity of the statement | `schema_version`, `signing_purpose` |
| who signed, under which key | `producer_id`, `issuer`, `producer_key_id` |
| how | `signature_algorithm`, `signature_profile`, `signature_encoding` |
| **what it is about** | `tenant_id`, `subject_id`, `subject_type`, `recommendation_id`, `recommendation_digest` |
| when | `issued_at` |

Every other field on the artifact **records the scope of the determination** — which
candidate it was reached against (`candidate_digest`), which anchor answered, when, and
under which verification profile. Honest, digest-protected facts about the check; not
assertions the producer made.

> **`candidate_digest` is not signature-covered.** One genuine attestation verifies against
> **any** candidate agreeing on `(recommendation_id, recommendation_digest, tenant_id,
> subject_id, subject_type)`. Both verifications return `VERIFIED`, with the same
> `attestation_digest` and different `candidate_digest`s.

**The rule, not a list.** The verifier reconciles **exactly those five facts and directly
reconciles no other candidate facts**. Stated as the claim it supports: for two independently
valid objects of exact type `CapacityAuthorizationCandidate`, the producer-attestation layer
does not independently compare facts outside those five when the five reconciled values remain
equal. Two earlier revisions of this section tried to enumerate the dimensions instead, and
each got it wrong in a different direction.

`candidate_digest` is read **after** verification succeeds, to bind the resulting artifact to
the candidate the determination was reached against. It is neither producer-signature-covered
nor independently reconciled — the verifier never compares it against anything.

`A-59` is the load-bearing evidence: it varies real candidates through the genuine chain and
observes the outcome. `A-60` is a syntactic tripwire over the reconciliation section, useful
but not a proof that no sixth fact can ever be read; its limits are stated with it.

Measured instances:

| Candidate differs in | Still verifies? | |
|---|---|---|
| policy binding | **yes** | outside the reconciled five |
| execution target scope | **yes** | outside the reconciled five |
| permitted magnitude bounds | **yes** | scope and binding must vary *together* — Phase 5A refuses a binding contradicting its scope |
| `disposition` / `risk_outcome`, within the ALLOW family | **yes** | outside the reconciled five |
| the risk decision itself (`decision_digest` and `decision_snapshot_digest` both move) | **yes** | outside the reconciled five |
| the recommendation's own magnitudes | **no** — `RECOMMENDATION_DIGEST_MISMATCH` | they move `recommendation_digest`, which **is** one of the five |

So the uncovered surface is the **authorization envelope built around a recommendation** —
the policy bound to it, the scope it would execute in, the bounds that policy sets — and not
the recommendation's own content, which is pinned.

This is the ratified scope, not a defect. The *recommendation* is pinned by id and content
digest, which is what stops a forged recommendation laundering. The authorization envelope
it was later placed into is not pinned, because binding that would mean signing the Phase 5A
candidate — minting the attestation after the candidate instead of at the Controller's output
boundary, and making the v2 payload depend on Phase 5A. Both were rejected.

So **do not read `VERIFIED` as saying anything about the policy binding, the decision or the
scope** the recommendation was bound into. Establishing those is Phase 5B-0B's work and the
authorization subphases'. ADR §12.1 records the ruling and `tests/test_adversarial.py` pins
the behaviour with a property.

## Key custody

No production private key exists anywhere in this repository. The only shipped signer is
the reference Ed25519 one, structurally marked and refused in production minting. Private
key material never reaches a contract object, a canonical dict, a digest, a `repr`, an
exception message or a record — the signing key lives only behind
`ProducerAttestationSignerPort`, and an HSM- or KMS-backed custodian implements the same
port and drops in without any caller change.

Stated plainly rather than over-claimed: in-process code that reaches into a private module
attribute is not defended against, and no Python-level mechanism defends against it. What
is closed is the **public API** route. The load-bearing secret remains the signing key.

## Standing this up in production

**`production_mode` defaults to `False`, everywhere it appears.** That default is right for
tests and for a local composition root, and it is wrong for a deployment: with it left alone,
this package will accept the shipped reference resolver, the shipped reference signer and a
non-production signature verifier, and the artifacts it mints will look exactly like
production ones. Nothing warns you. Passing `production_mode=True` is what turns the
reference components into refusals, so a production composition root must set it explicitly
at **both** boundaries — minting and verifying.

A composition root that stands this up correctly does three things: it sets
`production_mode=True`, it injects a non-reference resolver and a non-reference signer, and
it calls `require_verified_producer_attestation` at every point a verified artifact is
consumed rather than trusting the object it was handed.

```python
from ugence_cloud_scaling_producer_attestation import (
    PRODUCER_ATTESTATION_SIGNATURE_PROFILE,
    Ed25519ProducerSignatureVerifier,
    ProducerAttestationVerifier,
    mint_producer_attestation,
    require_verified_producer_attestation,
)

# --- 1. the signer: a key custodian over your managed key service ----------------------
# Implements ProducerAttestationSignerPort. It must NOT subclass
# ReferenceEd25519ProducerAttestationSigner — subclasses are refused in production, and
# relabelling one with is_reference_signer = False does not lift that.
class KmsProducerSigner:
    is_reference_signer = False

    def __init__(self, kms, *, producer_id, issuer, producer_key_id):
        self._kms = kms
        self.producer_id = producer_id
        self.issuer = issuer
        self.producer_key_id = producer_key_id

    @property
    def signature_profile(self) -> str:
        # The one ratified profile. There is no second value to return.
        return PRODUCER_ATTESTATION_SIGNATURE_PROFILE

    def sign_producer_attestation(self, signing_input) -> str:
        # The port has no "sign arbitrary bytes" method by design: the package builds the
        # bytes, and the custodian signs what it is handed. Return canonical lowercase
        # base16 of the raw Ed25519 signature.
        return self._kms.sign_ed25519(
            key_id=self.producer_key_id, message=signing_input.signed_bytes()
        ).hex()


# --- 2. the resolver: your trust-anchor store, not the shipped reference directory ------
# Implements TrustAnchorResolverPort. Again: not a subclass of StaticTrustAnchorDirectory.
class ManagedTrustAnchorDirectory:
    is_production_authoritative = True

    def __init__(self, store):
        self._store = store

    def resolve(self, coordinate):
        # Return a TrustAnchorResolution for exactly this (issuer, key_id, capability).
        return self._store.resolve(coordinate)


# --- 3. minting, at the Controller's output boundary ------------------------------------
attestation = mint_producer_attestation(
    signer=KmsProducerSigner(kms, producer_id=..., issuer=..., producer_key_id=...),
    tenant_id=recommendation.tenant_id,
    subject_id=recommendation.subject_id,
    recommendation_id=recommendation.recommendation_id,
    recommendation_digest=recommendation.recommendation_digest,
    issued_at=clock.now(),          # injected; this package never reads a clock
    production_mode=True,           # <-- not the default
)

# --- 4. verifying ------------------------------------------------------------------------
verifier = ProducerAttestationVerifier(
    trust_anchor_resolver=ManagedTrustAnchorDirectory(store),
    # The shipped Ed25519 verifier already declares is_production_authoritative = True;
    # it holds no key material and does its own strict public-key validation.
    signature_verifier=Ed25519ProducerSignatureVerifier(),
    production_mode=True,           # <-- not the default
)
result = verifier.verify(
    candidate=candidate, attestation=attestation, as_of=clock.now()
)

# --- 5. every consumption boundary ------------------------------------------------------
if result.refusal is not None:
    # Branch on result.refusal.outcome — a closed typed vocabulary, never on a message.
    return deny(result.refusal.outcome)

artifact = require_verified_producer_attestation(result.verified_attestation)
```

**Step 5 is not ceremony.** `require_verified_producer_attestation` re-checks the exact type,
field presence, the construction token, provenance-registry membership and the recomputed
self-digest. Call it every time an artifact crosses a boundary — a queue, a cache, a function
that received one as an argument, a service layer — not once at the point of minting. A
consumer that skips it is trusting an object's *shape*, which is the thing
`VerifiedProducerAttestation` exists to say is not enough. Note in particular that it refuses
a `copy.deepcopy`d or unpickled artifact: a determination reached in another process is not a
determination reached in this one, and there is deliberately no deserializer. Re-verify there
instead of shipping the artifact.

Three things this checklist does **not** buy you, and they are the ones that matter:

* a verified artifact still **grants nothing** — `grants_authority` hard-returns `False`;
* the producer is not independently resolved: `attested_producer_id` is a signed *claim by
  the issuer*, and the anchor was resolved by **issuer**, not by producer;
* the signature does not cover the candidate — see
  [What the signature covers](#what-the-signature-covers) before treating `VERIFIED` as
  saying anything about the policy binding, the decision or the scope.

## No clock

Every instant is injected. `as_of` and `issued_at` are required parameters, a naive
datetime is refused rather than assumed UTC, and `tests/test_time_authority.py` asserts
over source imports and AST call expressions that no wall-clock source is reachable.
Attestation *freshness* — a maximum age, a TTL, a skew allowance — is deliberately **not**
invented here: an unratified freshness window would be an unratified authority decision.
The artifact carries the issuance instant so a later phase can judge it.

## Running the suite

```bash
python -m pytest packages/integration/cloud-scaling-producer-attestation/tests
python packages/integration/cloud-scaling-producer-attestation/scripts/verify_isolated_install.py
python -m build packages/integration/cloud-scaling-producer-attestation
```

`GUARD_INVENTORY.md` publishes the canonical guard inventory and classification, and the
gate-removal mutation sweep runs through the shared Cloud Scaling engine:

```bash
python scripts/cloud_scaling/guard_sweep.py producer-attestation --inventory-only
python scripts/cloud_scaling/guard_sweep.py producer-attestation --shard 1/1
```

Every decision point — the `if` layer plus the ratified additive classes (`except`-arm
typed rejections, helper-admission calls, `else`-arm refusals) — is neutralised
independently in a disposable untracked copy, and every site is either killed by the
suite or carries a declared exclusion from the closed vocabulary in
`scripts/cloud_scaling/guard_sweep.py`, each naming the test that measures its claim.
