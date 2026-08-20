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

### Post-audit remediation (pre-merge, same 0.1.0)

Applied after a whole-PR audit of head `6f3b4cd6`. No signed bytes, canonical payload,
frozen digest or authority boundary changed; the v2 signing payload and the v2 attestation
digest are byte-identical, so no issued attestation is invalidated.

* **`mint_producer_attestation`'s production refusal is now inheritance-aware.**
  `production_mode=True` refuses `ReferenceEd25519ProducerAttestationSigner` **and every
  subclass of it**, matched by `isinstance` against the new exported
  `REFERENCE_GRADE_SIGNERS` tuple and evaluated **before** the `is_reference_signer` flag.
  A subclass that inherits the reference key custodian whole and sets
  `is_reference_signer = False` was previously admitted in production; it is now refused.
  A custodian that *composes* a reference signer rather than inheriting one stays admitted.
  This is the signer-side counterpart of the resolver-side correction already shipped as
  `REFERENCE_GRADE_RESOLVERS`, and is spelled the same way so the two cannot drift.
* **`ProducerAuthenticityResult` revalidates the artifact it is given.** Its only artifact
  gate was an exact-type check, which `object.__new__(VerifiedProducerAttestation)`
  satisfies — the result constructed and `.outcome` then read `VERIFIED`. Construction now
  routes the artifact through `require_verified_producer_attestation`, so the class's own
  statement that "the presence of an artifact is decided by this module, never supplied by
  a caller" is enforced rather than asserted.
* **Added to the curated API:** `REFERENCE_GRADE_SIGNERS` (56 exported symbols, was 55).

### Documented, with no behaviour change

* **What the signature covers.** `candidate_digest` is **not** covered by the producer's
  signature: one genuine attestation verifies against any candidate agreeing on
  `(recommendation_id, recommendation_digest, tenant_id, subject_id, subject_type)`,
  including candidates carrying a different policy binding, decision or scope. This is the
  ratified scope — the attestation is minted at the Controller's output boundary, before a
  candidate exists — and it is now stated in ADR §12.1, in the `verified.py` docstring and
  in a README section, and pinned by two properties rather than left to be discovered. The
  README's earlier claim that the v2 proof is "independently bound to" a candidate is
  corrected: it is bound to the *recommendation*.
* **A production composition root.** The README gains a worked example: `production_mode=True`
  at both boundaries (it defaults to `False`), a non-reference resolver and signer, and
  `require_verified_producer_attestation` at every consumption boundary.
* **The Trusted Evidence Authority floor** in ADR §14 said `>=0.2.0`; `pyproject.toml`
  correctly says `>=0.3.0`, which is the release that adds the dedicated capability member.
  The ADR was corrected, not the floor.

### Known limitation

**Policy authenticity remains unresolved.** A verified producer attestation says who
produced the recommendation and nothing about whether the policy binding the candidate
carries is genuine, in force, or issued by an authority anyone trusts. That is Phase
5B-0B's work and is not implemented here.
