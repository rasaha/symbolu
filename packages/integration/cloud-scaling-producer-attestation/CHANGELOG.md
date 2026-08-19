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
  revalidator. The boundary is four independent parts: a package-private construction
  token, a self-digest over every bound fact, a provenance registry of the determinations
  this process actually reached, and revalidation at every consumption boundary. The
  registry exists because the token alone made *possession* of one genuine artifact
  equivalent to the capability to mint arbitrary ones.
* `ProducerAuthenticityOutcome` — a closed 27-member typed outcome vocabulary with exactly
  one success member.
* Re-exports of the Trusted Evidence Authority's trust-anchor contracts, unchanged, plus
  `producer_anchor_coordinate`, `anchor_coordinate_digest`, `anchor_record_digest`,
  `anchor_lifecycle_outcome` and `require_production_resolver`.

### Packaging

* The sdist ships a **runnable** suite, not merely a suite-shaped set of paths.
  `MANIFEST.in` includes the package-root `conftest.py`, `tests/conftest.py`, the shared
  fixture helper and a frozen Phase 5A candidate payload alongside the test modules, so an
  extracted sdist collects and runs against the declared distributions alone. Properties
  that are genuinely *about* the monorepo chain skip there, visibly and with a reason.
  `tests/packaging/test_sdist_payload.py` proves it by extracting the archive outside the
  repository and running it in a fresh virtualenv holding only non-editable wheels.

### Frozen

Three new fixtures, with independently recomputed pinned digests: one verified attestation,
one resolved trust anchor, and one refused attestation with its pinned refusal member. No
pre-existing digest is re-pinned.

### Unchanged by design

* Phase 5A (`ugence-cloud-scaling-authorization-contracts`) stays at **0.1.0**, with its
  242-test suite, its 37 exports, its ten frozen digests and its documented v1 limitation
  all untouched.
* The Cloud Scaling Controller stays at **0.4.0**, key-free and advisory.
* Risk Authority takes no version change; only its public API is consumed.
* The Trusted Evidence Authority takes **no behaviour change**, and moves **0.2.0 → 0.3.0**
  for one additive `TrustAnchorCapability` member,
  `CLOUD_SCALING_RECOMMENDATION_ATTESTATION`, lent to this package under the ADR §30
  amendment. TEV verifies nothing under it and admits it on no evidence or receipt path;
  the member is vocabulary, not authority. (An earlier revision of this entry said TEV took
  no version change, which was true only before the borrowed `EVIDENCE_PRODUCTION`
  capability was replaced by the dedicated one.)

### Residual, stated rather than left to be found

In-process code that reaches into a private module attribute can import the construction
token or add to the provenance registry, and no Python-level mechanism prevents that. This
is the same residual the Trusted Evidence Authority documents for its own signing boundary.
What is closed is every route that does not require reaching into the module's privates.

The provenance registry grows by one 71-byte digest per **distinct** determination reached;
repeat verifications of the same candidate add nothing. A process verifying unboundedly many
distinct recommendations should hold the boundary somewhere with its own lifecycle.

### Known limitation

**Policy authenticity remains unresolved.** A verified producer attestation says who
produced the recommendation and nothing about whether the policy binding the candidate
carries is genuine, in force, or issued by an authority anyone trusts. That is Phase
5B-0B's work and is not implemented here.
