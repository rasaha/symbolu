# Risk Authority Phase 5 — signed envelope issuance, ratified

**Status:** ratified 2026-09-04 by the repository owner. Sequenced by
`ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (wave 1, cloud-scaling
ladder) and grounded on `ADR_CLOUD_SCALING_PHASE5B2_TRUSTED_INSTANT_RATIFICATION.md`
(the clock rules) and `ADR_CLOUD_SCALING_AUTHORIZATION_PHASE5.md` §7 (the deferred
list). This record authorizes the **Risk Authority half only**; the cloud-scaling
composition package (5B-4) is scoped by it and built separately.

## The question

Where does Phase 5 envelope issuance live, and what does it take to lift the
containment? **Inside Risk Authority, as an issuance seam that fires only when
injected verifiers agree, with the cloud-scaling ladder gaining one composition
package that calls it.** Risk Authority already owns the issuer, the verifier,
revocation epochs, the clock and the signed envelope shape; what it lacked was a
seam that takes verified inputs instead of a case id, bindings for the artifacts
Phase 5 produced, a signer port, and durable decisions.

## What existed `[V]`

| Finding | Where |
|---|---|
| `EnvelopeIssuer.issue` refuses a non-granting or expired decision, enforces scope subset, binds workflow, evidence and model digests plus the RA-6 epoch, signs over the whole envelope minus the signature | `services/envelope_issuer.py` |
| `RiskAuthorityApplication.issue_envelope` reads the clock once, then raises `ProductionContainmentError` in production mode | `api/dependencies.py:719` |
| The Phase 4C seam creates a case and a `RiskDecision` in the same application; the candidate's `decision_id` comes from the digest-bound decision snapshot | `api/evaluation_seam.py`, `cloud-scaling-authorization-contracts/reconciliation.py:413` |
| Signing called `key_record.signing_key.sign` directly; no signer port; `not_before` was caller-suppliable | `services/envelope_issuer.py` |
| RA-8 correlates on `envelope_id`; RA-6 revokes by epoch or targeted envelope; the envelope is the sole machine-execution artifact | RA-6, RA-8 READMEs |

## Ratified decisions

| # | Decision | Ruling |
|---|---|---|
| D-1 | Home | **`EnvelopeIssuanceSeam` in `risk_authority.api`**, beside `RiskEvaluationSeam`, is the only place a Phase 5 envelope is signed. A new integration package `cloud-scaling-envelope-issuance`, ladder name **5B-4**, composes the 5A candidate with the 5B-0A and 5B-0B verifiers and calls the seam through an `ArtifactVerificationPort`. Risk Authority imports no cloud-scaling type and hard-codes no binding kind; the composition root declares the kinds it requires. |
| D-2 | Bindings | **`EnvelopeBindings.artifact_bindings`**, an additive tuple of `ArtifactBinding(kind, digest)` pairs, unique by kind, sha-256 hex digests. For cloud scaling the composition package supplies at least the authorization-candidate digest, the policy-authenticity artifact digest, the producer-attestation verification digest, the target-scope digest and the D-6 idempotency key. The generic `Scope` is unchanged; bounds travel by digest, never by reinterpreting scope fields. |
| D-3 | Time | **One clock read per act.** The seam reads its clock once; that instant is passed to the verification port as `as_of`, becomes `issued_at`, and sets `not_before` equal to `issued_at`. Expiry is `min(issued_at + ttl, decision.expires_at)`. Every verified binding must report `resolved_as_of == issued_at` or issuance is refused (`INSTANT_MISMATCH`). No caller-supplied instant exists on the seam. |
| D-4 | Preconditions and containment | Issuance requires: the decision exists for the tenant, its recomputed digest equals the caller's `decision_digest`, it grants authority, it has not expired at the instant, every required binding kind is present and reports `VERIFIED`, and the requested scope is a subset of the decision's. Anything else is a typed `EnvelopeIssuanceRefusal`. `authorize_action` and the case-based `issue_envelope` stay contained; an envelope authorizes no execution without 5C admission and 5X credentials. |
| D-5 | Custody and persistence | **`EnvelopeSignerPort`** mirrors Trusted Evidence Authority's receipt signer; `ReferenceEnvelopeSigner` wraps a `SigningKeyRecord` and is refused by the production seam. Production issuance is allowed only in the application instance that evaluated the decision, because decision and envelope repositories are in-memory; durable Risk Authority persistence under the D-3 posture is added to wave 1. |

## Gaps that survive `[G]`

In-memory decision and envelope repositories; no HSM or KMS signer exists yet (the
port is the seam for one); no mapping from a capacity action to `CanonicalAction`
(5C's); the 5B-4 composition package is not yet built.

## Next step

Build `cloud-scaling-envelope-issuance` (5B-4) against the seam.
