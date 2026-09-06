# ugence-risk-authority-effect-attestation — 0.2.0

**Signed external-effect verification, contracts first.** The wave 5 successor
to RA-8's non-cryptographic effect-source trust, scoped and ratified by
[`ADR_UGENCE_SIGNED_EFFECT_ATTESTATION_SCOPING.md`](../../../docs/architecture/ADR_UGENCE_SIGNED_EFFECT_ATTESTATION_SCOPING.md)
(SE-1 to SE-5).

> **A verified signature proves provenance and integrity, not factual
> correctness.** It establishes who signed an observation and that the bytes
> are the bytes they signed. It never establishes that the observed effect
> occurred. Every result says so on its face.

Maturity: **REFERENCE-GRADE / NOT PRODUCTION-READY.** Not wired into RA-8.

## What this package is

| Piece | What it does |
| --- | --- |
| `EffectAttestation` | An immutable wrapper binding one complete, **unmodified** governance-contracts `ExecutionObservation` with the attester's identity, role, key reference, algorithm, schema/domain version and signature. It adds, repairs and reinterprets no observation fact (SE-3) |
| `EffectAttesterRole` | `EXECUTING_PROVIDER` or `INDEPENDENT_OBSERVER` (SE-2). The role is inside the signed bytes and selects the trust-anchor capability; an anchor for one role never satisfies the other |
| `Ed25519EffectAttestationVerifier` | The one verifier. Resolves the attester's anchor through the Trusted Evidence Authority's `TrustAnchorResolverPort` at the exact `(identity, key_id, role capability)` coordinate (SE-4) and verifies through TEA's strictly validated Ed25519 key — the D-41 pair with the libsodium point check (SE-5). Returns a typed result; never raises for an invalid input |
| `EffectAttestationVerificationResult` | Pure and evidence-bound: outcome, one typed refusal reason, the role, identity, key, tenant, observation digest, payload digest, coordinate digest, anchor revision and instant. `establishes` is always `PROVENANCE_AND_INTEGRITY_ONLY`; `factual_correctness_established` is permanently `False` |
| `ReferenceEd25519EffectAttestationSigner` | Deterministic, seed-derived, **for tests and local composition only**; `mint_effect_attestation(..., production_mode=True)` refuses it and every subclass |

## What it establishes, by role

- **Executing provider**: which provider reported the effect. Not that the
  effect occurred. **Provider self-attestation is not independent effect
  verification.**
- **Independent observer**: the identity and authorized observer role of the
  party that signed. Not the truth of its observation.

## What it does not do

- It **does not produce, fetch, reconcile or admit** an observation. It
  verifies an attestation it is handed, against an anchor it is handed, at an
  instant it is handed. There is no clock.
- It does **not** alter `ExecutionObservation`; governance-contracts is
  unchanged.
- It is **not** the Third-Party Gateway, which remains **FUTURE**; it produces
  no connector and acquires no receipt.
- It holds **no second trust store**: anchors are TEA's, reused as the identical
  objects, under two capabilities TEA lends for this purpose. Evidence-verifier,
  producer-attester and effect-attester anchors are non-transferable.
- It ships **no production signer**, no key loading, no key generation, no
  network, filesystem, environment-variable, credential or discovery code, and
  imports no cryptographic library of its own.
- It is **not wired into RA-8**. Unsigned observations remain admissible only
  under RA-8's existing reference-grade posture, and this slice cannot make
  RA-8 production-ready. That integration is a later, separately validated step.

## Verification pipeline, in order

1. exact-type admission of the attestation, the caller's role, tenant,
   observation and aware instant;
2. contract admission: schema version, signing domain, algorithm, profile,
   encoding — all pinned, none negotiated;
3. reconciliation against the **caller's** facts: role, tenant, observation
   digest;
4. anchor resolution at the exact coordinate; the resolution and the record
   are both re-checked against the coordinate asked, so a record swapped in
   after construction refuses;
5. lifecycle at the caller's instant, in TEA's order: revoked, disabled, not
   yet valid, expired; then the optional expected anchor revision;
6. key admission through TEA's point check, payload recomputed from the
   caller's observation and compared byte for byte, signature decoded and
   verified.

A resolver that raises, returns the wrong type or answers another coordinate
refuses closed. Nothing is memoized.

## Trust state is distinguishable (TW-1 to TW-3)

Wiring this package to a signed-snapshot resolver is ruled by
[`ADR_UGENCE_TR5_EFFECT_ATTESTATION_RESOLVER_WIRING.md`](../../../docs/architecture/ADR_UGENCE_TR5_EFFECT_ATTESTATION_RESOLVER_WIRING.md).
Four conditions an operator must act on differently stay four typed reasons:

| Reason | What happened | Operator action |
| --- | --- | --- |
| `ANCHOR_SET_STALE` | the trust-anchor set is admitted but no longer fresh at the instant | publish a newer snapshot |
| `ANCHOR_SET_UNAVAILABLE` | its snapshot never loaded, or its window does not cover the instant, or the resolver declares it cannot serve | fix or republish the snapshot |
| `ANCHOR_UNKNOWN` | no anchor is configured at that exact coordinate | onboard the attester |
| `ANCHOR_UNAVAILABLE` | the resolver itself misbehaved | fix the resolver |

A resolver that declares `is_production_authoritative = False` — a snapshot that
failed to load, most plainly — is **admitted** at composition and refuses every
verification **before being consulted**, so a startup file problem is a typed
refusal rather than a crash. A resolver that declares no posture at all is still
refused, and the reference directory and its subclasses are still refused.

The composition root supplies five things and this package reads none of them
from disk: the complete snapshot bytes, the pinned publication root, the maximum
snapshot age, the last accepted set version, and a trusted `as_of` per
verification.

## Dependencies

```
ugence-governance-contracts (>=0.8.0)        ExecutionObservation, wrapped unchanged
ugence-trusted-evidence-authority (>=0.5.0)  trust-anchor contracts, resolver port,
                                             Ed25519 key/codec types — exact grant
        ▲
ugence-risk-authority-effect-attestation (this package)
```

## Verify

```bash
python -m pytest packages/integration/risk-authority-effect-attestation/tests -q
python packages/integration/risk-authority-effect-attestation/scripts/verify_isolated_install.py
python packages/integration/risk-authority-effect-attestation/scripts/mutation_sweep.py
```

Measured figures live in `CHANGELOG.md` and are re-run, never edited.
