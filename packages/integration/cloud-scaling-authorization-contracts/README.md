# Ugence Cloud Scaling Authorization Contracts — Phase 5A

**A candidate grants nothing.**

This package turns a reconciled Phase 4C projection and its Risk Authority binding
decision — together with producer-attestation evidence and a policy/target binding — into
a canonical, explicitly **non-authoritative** `CapacityAuthorizationCandidate`.

The word *candidate* is the contract. The artifact represents a **reconciled request for
future authorization**. It is not an authorization, not an envelope, not an ActionGate
result, not a credential and not an execution order. Holding one entitles the holder to
*ask* Phase 5B for an envelope, and to nothing else.

---

## What Phase 5A does

1. Admits only **exact** `CapacityRiskSubjectProjection` and `SubjectRiskDecision`
   instances — subclasses, duck-typed look-alikes and `object.__new__` fabrications are
   refused before any attribute is read.
2. **Independently reconciles** the projection against the decision. Every digest is
   recomputed rather than trusted: the context, subject and request digests via Risk
   Authority's public `validate_subject_binding`, and `decision_digest` by recomputing
   `digest(to_canonical_obj(decision_snapshot))` from Risk Authority's public
   canonicalization primitives.
3. Structurally validates a **`ProducerAttestationEvidence`** and binds it to the exact
   `recommendation_digest`.
4. Structurally validates an account-bound **`ExecutionTargetScope`** and a
   **`PolicyTargetBindingReference`**, and enforces the magnitude and delta ceilings.
5. Emits one canonical `sha256:`-prefixed candidate digest over the whole chain.

Reconciliation completes **in full** before any part of a candidate is constructed, so a
rejection leaves no partial artifact.

## What Phase 5A does not do

It contains no capability to:

- verify a producer signature, a policy signature, a key entitlement or an issuer;
- reconstruct, mint or re-request a `RiskDecision`, or call Decision Authority;
- construct, sign or issue a `RiskAuthorizationEnvelope`, or invoke `EnvelopeIssuer`;
- invoke ActionGate or produce an `ActionAuthorization`;
- issue, broker or handle a credential;
- import a cloud SDK or Kubernetes client, or call Cloud Scaling Operations;
- mutate infrastructure, or emit an execution or effect-verification receipt;
- read a clock, or decide that anything is currently valid or fresh;
- learn from an outcome.

These are asserted **structurally** — over source imports, public exports, AST call
expressions, dataclass field sets, dependency metadata, the built wheel and the
installed-wheel import closure — not merely stated in prose and not encoded as
fixed-`False` booleans.

---

## The two unverified evidence states

Both signature-bearing inputs report exactly one state:

```
PRESENT_BUT_NOT_TRUST_VERIFIED
```

`EvidenceTrustState` has **one member**. There is no `TRUST_VERIFIED`, no `AUTHENTIC` and
no `VALID` to reach, so no caller, subclass, forged mapping or doctored instance dictionary
can put an artifact into a verified state — the state does not exist to be set. The state
is a read-only `property`, not a dataclass field, so `object.__setattr__` raises against it.

**Producer signatures are structurally bound but not trust-verified in Phase 5A.** The
same is true of policy signatures. Phase 5A checks that an attestation is present,
well-formed, names the dedicated producer-signing purpose and binds the exact
recommendation digest. Whether that signature actually verifies under an entitled key is
Phase 5B's, under its own trusted clock.

Key separation is ratified: the producer signs under a **dedicated producer-signing
purpose**, never Policy Authority's policy-signing identity. The controller may sign its
own output — a self-signature is a claim of origin, not a grant of trust, and it becomes
meaningful only when an independent Phase 5B verifier validates it.

## No authority representation

`CapacityAuthorizationCandidate` has no field named or meaning `authorized`,
`authority_granted`, `envelope_issued`, `actiongate_invoked`, `credential_issued`,
`actuation_performed`, `effect_verified` or `executable` — **not as `True`, and not as a
fixed `False`**. A fixed `False` still represents authority and is one commit away from
being flipped; absence cannot be flipped.

## No clock

Phase 5A imports no wall clock, reads no ambient time, accepts no `now` and no
`evaluation_time`, and generates no timestamp. It carries Phase 4's validity facts, the
attestation's `issued_at` and the decision's `expires_at` forward under `…_fact` field
names, as **facts awaiting Phase 5B's trusted-clock evaluation**. A candidate never claims
that a recommendation, attestation, policy or decision is currently valid.

## The account binding is new

The frozen Phase 4 `CapacitySubject` has no account identity, and Phase 5A does not touch
it. `ExecutionTargetScope` is new Phase 5 vocabulary and makes `account_id` **required**: a
capacity action that reconciles perfectly against tenant, region and cluster but lands in
the wrong cloud account is exactly the substitution this field exists to prevent.

---

## What the candidate digest covers

**Everything the candidate carries.** The payload binds the *complete canonical form* of
`ExecutionTargetScope`, `PolicyTargetBindingReference` and `ProducerAttestationEvidence` —
not a derived digest standing in for them, and not a hand-picked subset of their fields.

That distinction is load-bearing. Binding only a digest while still *carrying* the object
lets the two disagree: the object can be swapped for a rogue one while the stale digest
continues to validate, and the candidate then carries evidence its digest never covered. A
candidate can never carry different policy or attestation evidence under the same digest —
substituting a policy issuer, a policy key, a signature byte, an account or a magnitude
ceiling moves the candidate digest.

This is **content binding, not trust**. It says the evidence you read is the evidence that
was bound. It says nothing about whether that evidence is genuine, which remains Phase 5B's.

## Gate coverage and mutation residue

Every security-relevant gate — one whose removal would let a new invalid candidate be
constructed — is covered by a test that exercises **that gate**, not a sibling. This was
established in stages, and the history is kept rather than smoothed over:

1. an exhaustive guard sweep closed six untested gaps in the builder, plus the
   schema-version, candidate exact-type and reconciler re-derivation gates;
2. an **independent closure audit then found two further lapses** the sweep had not
   reached — the projection-versus-decision **tenant** and **subject-digest** gates in
   `reconcile_phase4`. Removing either let a candidate be built across the mismatch under a
   byte-identical candidate digest, because the candidate takes both facts from the
   *projection*. Both are now closed by focused tests.

Mutations that still survive are classified, and qualify only because their removal creates
no new constructible invalid candidate: **sibling-backed** (the same property enforced twice,
so neither removal is observable), **unreachable defence in depth** (guarding a route no
public entry point can take, because the value is already inside a digest that is
re-derived), and **non-security validation** (removal changes only a message).

## Canonicalization

`risk_authority.crypto.canonical` and its hashing conventions, reached **only** through
public APIs. Phase 5A introduces no fourth canonicalization scheme: there is no local JSON
encoder, no `hashlib` use and no alternate digest path in this distribution. Every emitted
digest is `sha256:` + 64 lowercase hex characters, and a structural test proves the package
emits no bare-hex digest. Digests produced by the separate Cloud Scaling Operations
canonicalizer are never compared against these.

## Dependencies

Exactly three first-party packages, all already merged on the default branch:

| Package | Why |
|---|---|
| `ugence-risk-authority` | v2 seam contracts, `SubjectRiskDecision`, public canonicalization |
| `ugence-cloud-scaling-controller` | canonical `ActionKind` |
| `ugence-cloud-scaling-risk-integration` | the Phase 4C projection and the D-4 identifiers |

**No third-party runtime dependency is added.** There is deliberately no dependency on
Policy Authority, Decision Authority, ActionGate, a Credential Broker, Cloud Scaling
Operations, a cloud SDK or a Kubernetes client. None of the three dependencies imports this
package, so the leaf direction holds.

## Phase boundary

| Phase | Scope | Status |
|---|---|---|
| **5A** | non-authoritative authorization binding contracts | **this package** |
| 5B | producer/policy verification and signed envelope issuance | not implemented |
| 5C | production ActionGate admission | not implemented |
| 5X | short-lived Credential Broker materialization | not implemented |
| 5D | bounded Cloud Scaling execution | not implemented |
| 6 | independent effect verification and learning | not implemented |

**Production LIVE execution remains structurally blocked until 5X** supplies short-lived,
least-privilege credentials. Phase 5D may eventually support dry-run/reference execution
before 5X; live execution may not.

See `docs/architecture/ADR_CLOUD_SCALING_AUTHORIZATION_PHASE5.md`.
