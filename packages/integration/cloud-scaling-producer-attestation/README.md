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
  **alongside** a candidate and is independently bound to it; binding one *inside* a
  candidate would need a Phase 5A 0.2.0, which is Phase 5B-0B's work.
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
`TrustAnchorCapability.EVIDENCE_PRODUCTION`. TEV ratifies exactly two capabilities and
exactly one per anchor: production ("signs on behalf of a **producer**") and receipt
issuance ("signs on behalf of the **verifying authority**"). A producer attestation is a
producer signing a claim about its own output, so it is the producer role — and choosing it
inherits ADR E-3's separation for free: a receipt-issuance key physically cannot verify a
producer attestation here.

**Reference versus production grade.** The repository classifies
`StaticTrustAnchorDirectory` as reference grade in its own words ("the deterministic
*reference* resolver … suitable for tests, for local use"). `require_production_resolver`
therefore **refuses it under `production_mode=True`**, following the Risk Authority's
`is_production_authoritative` convention. `DenyAllTrustAnchorDirectory` is admitted, because
it can only ever refuse — it is the ratified deny-by-default posture, and the only "no
anchors" shape that ships.

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

`GUARD_SWEEP.md` publishes the canonical guard inventory and the mutation sweep:
every security-relevant gate is neutralised independently in a disposable untracked copy,
and every survivor is classified.
