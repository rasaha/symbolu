# Changelog — ugence-cloud-scaling-producer-attestation

All notable changes to this distribution. This package follows the Cloud Scaling phase
numbering; each entry names the phase that produced it.

## 0.1.0 — Cloud Scaling Phase 5B-0A: producer authenticity foundation

First release. Makes a Cloud Scaling producer attestation **mintable and verifiable** for
the first time, and stops there.

### Added

* `ProducerAttestationV2` — a new, separately schema-tagged producer-attestation contract
  at `ugence.cloud-scaling/producer-attestation/v2`, whose canonical signing payload binds
  schema version, signing purpose, producer id, issuer, key id, algorithm, profile,
  encoding, tenant, subject, subject type, recommendation id, recommendation digest and
  issuance instant. The signature is excluded from the payload it covers.
* `mint_producer_attestation` — the one route to a producer signature, via a token-guarded
  `ProducerAttestationSigningInput`. There is no "sign arbitrary bytes" method on the port.
* `ProducerAttestationSignerPort` and `ReferenceEd25519ProducerAttestationSigner`, the
  latter marked `is_reference_signer = True` and refused under `production_mode=True`.
* `ProducerAttestationVerifier` — the authoritative ten-group verification routine, with
  the trust-anchor resolver and the signature verifier as required constructor arguments
  and no defaults.
* `Ed25519ProducerSignatureVerifier` — the production-grade signature check, over the
  Trusted Evidence Authority's maintained Ed25519 backends.
* `VerifiedProducerAttestation` and `require_verified_producer_attestation` — the
  exact-typed, immutable, non-authoritative verification artifact and its consumption-time
  revalidator.
* `ProducerAuthenticityOutcome` — a closed 27-member typed outcome vocabulary with exactly
  one success member.
* Re-exports of the Trusted Evidence Authority's trust-anchor contracts, unchanged, plus
  `producer_anchor_coordinate`, `anchor_coordinate_digest`, `anchor_record_digest`,
  `anchor_lifecycle_outcome` and `require_production_resolver`.

### Frozen

Three new fixtures, with independently recomputed pinned digests: one verified attestation,
one resolved trust anchor, and one refused attestation with its pinned refusal member. No
pre-existing digest is re-pinned.

### Unchanged by design

* Phase 5A (`ugence-cloud-scaling-authorization-contracts`) stays at **0.1.0**, with its
  242-test suite, its 37 exports, its ten frozen digests and its documented v1 limitation
  all untouched.
* The Cloud Scaling Controller stays at **0.4.0**, key-free and advisory.
* Risk Authority and the Trusted Evidence Authority take no version change; only their
  public APIs are consumed.

### Known limitation

**Policy authenticity remains unresolved.** A verified producer attestation says who
produced the recommendation and nothing about whether the policy binding the candidate
carries is genuine, in force, or issued by an authority anyone trusts. That is Phase
5B-0B's work and is not implemented here.
