# Ugence Cloud Scaling Envelope Issuance

**Cloud Scaling Phase 5B-4 — the composition root for signed envelope issuance.**
Distribution `ugence-cloud-scaling-envelope-issuance` · namespace
`ugence_cloud_scaling_envelope_issuance` · version **0.1.0**.

> **An envelope is authority, not execution.**
> This package turns the ladder's verified facts into one call on Risk Authority's Phase 5
> issuance seam. The seam signs. Nothing here admits an action (5C), brokers a credential
> (5X), touches a cloud provider, or grants anything a candidate could not already ask for.

Ratified by `docs/architecture/ADR_RISK_AUTHORITY_PHASE5_ENVELOPE_ISSUANCE_RATIFICATION.md`
(decisions D-1 … D-5) and grounded on the 5B-2 trusted-instant ruling.

---

## What it composes

| Input | From | What it establishes |
|---|---|---|
| `CapacityAuthorizationCandidate` | Phase 5A | a reconciled, digest-bound request that grants nothing |
| `ProducerAttestationVerifier` | Phase 5B-0A | who produced the recommendation, at an instant |
| `PolicyAuthenticityVerifier` | Phase 5B-0B | that the candidate's named policy was authentically issued and is in force at an instant |
| `EnvelopeIssuanceSeam` | Risk Authority 0.6.0 | the only place a Phase 5 envelope is signed |

## The act

`CloudScalingEnvelopeIssuance.issue(request)`:

1. builds one `CloudScalingArtifactVerification` port for the request's candidate and
   attestation, and one seam over it;
2. hands the seam a request whose tenant, decision id and decision digest are read off the
   candidate — the caller supplies only an audience, a session id, a nonce and an optional ttl;
3. the seam reads the clock **once**, finds the decision in the application that evaluated
   it, recomputes its digest, and calls the port with that instant as `as_of`;
4. the port runs both verifiers at that instant, revalidates each verified artifact at this
   boundary, checks it names this candidate and recorded this instant, re-derives the
   candidate's own digests, and reports five bindings in the ratified order;
5. the seam refuses unless all five report `VERIFIED`, then signs them into
   `EnvelopeBindings.artifact_bindings`, caps expiry by the decision, and persists the
   envelope.

### The five bindings (ADR D-2)

| Kind | Digest |
|---|---|
| `cloud-scaling.authorization-candidate` | `candidate_digest`, re-derived |
| `cloud-scaling.policy-authenticity` | `VerifiedPolicyAuthenticity.artifact_digest` |
| `cloud-scaling.producer-attestation` | `VerifiedProducerAttestation.artifact_digest` |
| `cloud-scaling.execution-target-scope` | `target_scope_digest`, re-derived |
| `cloud-scaling.idempotency-key` | the D-6 key the candidate carries |

`sha256:`-prefixed ladder digests are projected to the seam's bare 64-hex form by
`bare_digest`; the kind names the namespace a binding came from.

### What a refusal looks like

The outcome carries the seam's typed `EnvelopeIssuanceRefusal` beside the port's
`CloudScalingVerificationReport`, whose per-binding `ArtifactBindingStatus` and the upstream
verifiers' own outcome tokens say why. A verifier that raises is `VERIFICATION_UNAVAILABLE`,
never a pass. A decision that has expired or drifted refuses before any verifier runs.

## Production posture

`CloudScalingEnvelopeIssuance.production(...)` refuses a reference-mode Risk Authority
application, the reference envelope signer, a signer that has not opted in with
`is_production_authoritative = True`, and either verifier built outside `production_mode`.
`reference(...)` refuses a production application. The seam repeats its own gates on every
act. A production application must stand on Risk Authority's durable store
(`SqliteRiskAuthorityStore`, Risk Authority 0.7.0); any application over the store that holds
the decision may issue, which lifts the same-instance restriction ADR D-5 recorded.

## What it does not do

Read a clock; accept a caller-supplied instant, decision, scope, binding, coordinate or
signer; hold a key; mint a nonce or keep a replay ledger; call `authorize_action` or the
case-based `issue_envelope`; map a capacity action to a `CanonicalAction`; call a cloud
provider; learn from an outcome. Those absences are asserted over the AST and the
dependency manifest in `tests/test_import_boundary.py` and `tests/test_time_authority.py`.

## Run the suite

```
python -m pytest packages/integration/cloud-scaling-envelope-issuance
```

The suite drives the genuine chain from a repository checkout: controller Phase-3
recommendation, 4C projection, a real Risk Authority decision held in its application, a
real issued bounds policy, and a v2 attestation minted through 5B-0A's one route.
