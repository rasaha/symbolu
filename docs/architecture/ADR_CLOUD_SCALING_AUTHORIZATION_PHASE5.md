# ADR — Cloud Scaling Phase 5: Authorization, Admission, Credentials and Bounded Execution

**Status:** Accepted (decomposition ratified by the owner). **Phase 5A implemented; 5B, 5C,
5X, 5D and Phase 6 are not.**

Phase 4 ended at a non-executable `SubjectRiskDecision`. This ADR records the ratified
decomposition of everything that follows, and specifies Phase 5A — the only part built.

---

## §1. The ratified decomposition

| Phase | Scope | Status |
|---|---|---|
| **5A** | Non-authoritative authorization **binding contracts** | **Implemented** |
| 5B | Producer/policy **verification** and signed **envelope issuance** | Deferred |
| 5C | Production **ActionGate admission** | Deferred |
| 5X | Short-lived **Credential Broker** materialization | Deferred |
| 5D | **Bounded Cloud Scaling execution** | Deferred |
| 6 | Independent **effect verification and learning** | Separate phase |

Phase 5 includes bounded provider execution (5D). Phase 6 remains separate: verifying that
an effect occurred, and learning from it, must not be performed by the component that
caused it.

**Live execution is structurally blocked until 5X.** Phase 5D may eventually support
dry-run or reference execution before 5X exists, but production LIVE execution must remain
blocked until 5X supplies short-lived, least-privilege credentials. A long-lived or
broadly-scoped credential in a scaling executor is the failure mode 5X exists to prevent,
and shipping 5D first would create exactly that.

## §2. Why Decision Authority is not called a second time

Phase 4C already obtained a binding `SubjectRiskDecision` through the Risk Authority
evaluation seam. Phase 5A does **not** re-request, reconstruct or re-derive one.

Calling Decision Authority again would be actively harmful, not merely redundant:

* **It would create a second decision for one subject.** Two decisions for the same
  request digest is an ambiguity — which one did the envelope bind? — and ambiguity in an
  authority record is resolved by whoever reads it last.
* **It would let a caller retry until it liked the answer.** A component that can ask
  again can ask differently. The D-6 idempotency key exists precisely so one recommendation
  yields one decision.
* **It would move the authority boundary.** Phase 4C's contract is that risk evaluation
  happens once, in Risk Authority, under its own trusted clock, policy resolver and
  evaluator identity. A Phase 5 caller re-entering that path would be selecting its own
  evaluation conditions.

Phase 5A therefore **verifies** the decision it was handed — recomputing
`decision_digest` over `decision_snapshot` from Risk Authority's public canonicalization
primitives — and never mints one. It holds no Decision Authority import, no seam, and no
port through which one could be reached.

## §3. Producer signature versus independent verification

The Phase 4C authenticity boundary reconciled a recommendation digest against an
independent expectation. It did not establish **who produced** the recommendation.

Ratified rules:

* The producer signs under a **dedicated producer-signing key purpose**
  (`cloud_scaling.recommendation_producer_attestation`).
* It **must not** reuse Policy Authority's policy-signing identity. A key entitled to sign
  a controller recommendation must not thereby be entitled to sign policy, and vice versa.
* **The controller may sign its own output.** A self-signature is a claim of origin, not a
  grant of trust.
* **Trust is established only when an independent Phase 5B verifier validates that
  signature** under a key it already trusts for this purpose.
* **Phase 5A performs structural and content-binding validation only** — presence, syntax,
  the exact `recommendation_digest`, a supported signing purpose, and self-consistency of
  the signing-payload digest.
* **Phase 5A must never label the producer trusted, authentic or verified.**

The last rule is enforced by construction rather than by discipline: the vocabulary for
saying so does not exist in the package.

## §4. The two fixed unverified evidence states in 5A

`EvidenceTrustState` has **exactly one member**:

```
PRESENT_BUT_NOT_TRUST_VERIFIED
```

Both signature-bearing artifacts — `ProducerAttestationEvidence` and
`PolicyTargetBindingReference` — report it, and nothing else.

**Why absence rather than a fixed `False`.** A `verified: bool = False` field still
*represents* the concept of verification. It is one commit, one deserializer bug or one
`object.__setattr__` away from being `True`, and every reader must then decide whether to
trust it. A vocabulary with no verified member cannot be flipped: there is no value to
assign. The state is exposed as a read-only `property` rather than a dataclass field, so
`object.__setattr__` — the usual frozen-dataclass bypass — raises against the data
descriptor, and a doctored instance dictionary loses to it.

Phase 5B will independently verify Policy Authority provenance and freshness before any
envelope is issued. Phase 5A does not call a policy resolver, and has no resolver port.

## §5. The new account-bound `ExecutionTargetScope`

The Phase 4 `CapacitySubject` is frozen and has **no account identity**. Phase 5A does not
modify it.

`ExecutionTargetScope` is new Phase 5 vocabulary. `account_id` is **required**, because a
capacity action that reconciles perfectly against tenant, region and cluster but lands in
the wrong cloud account is exactly the substitution the scope exists to prevent — and an
optional field would not prevent it.

`compute_group` and `resource_class` are **optional**, mirroring the frozen Phase 4
contract where `cluster` and `resource_id` are optional. Requiring them would make a
legitimate projection unbuildable. They are not a loophole: when either side has a value,
both must agree, so `None` against a value is a target substitution and is refused.

The scope also carries the requested magnitude and the maximum permitted magnitude and
delta. `PolicyTargetBindingReference` carries the policy's own maxima and binds one exact
scope by digest, so a scope claiming a higher ceiling than the policy grants is refused.

## §6. Phase 5A's non-authoritative boundary

`CapacityAuthorizationCandidate` is a **reconciled request for future authorization**. It
grants nothing. It has no field named or meaning `authorized`, `authority_granted`,
`envelope_issued`, `actiongate_invoked`, `credential_issued`, `actuation_performed`,
`effect_verified` or `executable` — not as `True`, and not as a fixed `False`.

Phase 5A holds **no clock**: no wall-clock import, no ambient time read, no `now`, no
`evaluation_time`, no generated timestamp. It carries Phase 4's validity facts, the
attestation's `issued_at` and the decision's `expires_at` forward under `…_fact` names as
facts awaiting Phase 5B's trusted-clock evaluation. It never claims anything is currently
valid or fresh.

Canonicalization is `risk_authority.crypto.canonical` through public APIs only. Phase 5A
introduces no fourth canonicalization scheme and never compares against digests produced by
the separate Cloud Scaling Operations canonicalizer.

### §6.0 Why the projection↔decision binding gates are load-bearing

A closure audit found that two `reconcile_phase4` gates — the direct
projection-versus-decision **tenant** comparison and the **subject-digest** comparison —
were unexercised, and that removing either let a candidate be built across the mismatch.

The reason they matter more than they look is worth recording as design rationale. A
`CapacityAuthorizationCandidate` takes its `tenant_id` and `subject_digest` from the
**projection**, never from the decision. So a decision issued for another tenant, or made
about another workload, leaves *no trace whatsoever* in the resulting candidate — the
candidate digest is byte-identical to a legitimate one. These two comparisons are therefore
the only point in the entire chain at which such a disagreement is observable at all. They
are not redundant with the request-digest check between them: a decision can be replayed or
mis-routed with a matching request digest and a differing tenant or subject.

Both are now covered by focused tests that isolate each gate, measured to fail only when
that specific gate is removed.

### §6.1 Revalidating the decision snapshot without a private symbol

Risk Authority binds `decision_digest == digest(to_canonical_obj(decision_snapshot))`
inside a private `SubjectRiskDecision._bind`. Phase 5A does **not** call that private
method and does not re-implement it from guesswork. It recomputes the same equality from
the two *public* primitives the private method is itself built from —
`risk_authority.crypto.canonical.to_canonical_obj` and
`risk_authority.crypto.hashing.digest`, both in their modules' `__all__`.

This is an independent recomputation over the published canonicalization contract, not a
copy of a private internal. If Risk Authority ever changed that contract, Phase 5A's own
frozen digests would move and its suite would fail rather than silently disagree. **No
public reconciliation contract was found to be missing**, so no blocker was raised.

### §6.2 The recommendation identifier

**Corrected by the F-5 audit finding.** An earlier revision of this section claimed Phase
4C's digest chain "carries no recommendation id". That was **wrong**, and the corrected
statement is:

> The recommendation ID **is transitively bound** by the Phase 4C canonical digest chain,
> but it is **not directly recoverable** from the resulting digest and is **not exposed as
> an independently cross-checkable decision field**.

Changing the recommendation ID changes `recommendation_digest`, and therefore
`request_digest` and every digest downstream of it. What the closed v2 `SubjectContext`
lacks is a *field* holding the ID, so Phase 5A has no Phase 4 attribute to compare a
supplied ID against — which is a different and much narrower statement than "the chain does
not carry it".

The Phase 5A conclusion is unchanged by the correction:

* candidate construction carries the recommendation ID explicitly;
* it must reconcile with the projection/recommendation source — a substituted ID paired
  with a re-derived chain yields a different `recommendation_digest`, and paired with a
  stale digest fails the same cross-check;
* producer-attestation evidence binds the ID inside its signed payload;
* Phase 5A establishes **structural and content consistency only**;
* **Phase 5B must independently verify the producer signature.** A fully self-consistent
  but unverified attestation remains non-authoritative here.

## §7. Deferred decisions

**Phase 5B** — trust-anchor resolution for producer keys; key entitlement and revocation;
signature verification; policy resolution and freshness against Policy Authority; the
trusted clock; envelope schema, signing and issuance; what an envelope binds beyond the
candidate digest.

**Phase 5C** — ActionGate admission semantics; retry and state-change handling; the
`ActionAuthorization` shape; idempotent admission under the D-6 key.

**Phase 5X** — credential lifetime and scope; least-privilege role derivation from
`ExecutionTargetScope`; broker trust model; credential binding to an admitted action.

**Phase 5D** — provider adapters; dry-run versus LIVE gating; bounded blast radius;
rollback; the execution-request and execution-record shapes.

**Phase 6** — independent effect verification; the effect-verification receipt; attribution
and learning. Deliberately not Phase 5's, and deliberately not the executor's.

None of these is silently resolved by Phase 5A. No placeholder verifier, permissive stub or
reserved field for any of them exists in the package.

## §8. Fixtures

Phase 5A freezes one production-shaped end-to-end fixture, beginning at a canonical Cloud
Scaling recommendation and ending at a `CapacityAuthorizationCandidate`, with ten
independently computed and pinned digests.

The Risk Authority illustrative canonicalization fixture
`sha256:eb4526a6679470e603bbc757cde7cfac9c7b2258256eaecef729e356a1df6c38` is **not**
replaced or reinterpreted. It is an **RA canonicalization fixture using the older
illustrative subject-type value**, and it is **not the production Phase 4C adapter-output
fixture**. No Phase 5A digest is expected to equal it, and a test asserts they are distinct.
