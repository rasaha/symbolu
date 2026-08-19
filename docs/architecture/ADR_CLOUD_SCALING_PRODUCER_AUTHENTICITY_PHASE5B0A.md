# ADR — Cloud Scaling Phase 5B-0A: Producer Authenticity

**Status:** Implemented (Phase 5B-0A only). **Open for independent audit; not merged.**
**Supersedes nothing.** Amends nothing in
[ADR — Cloud Scaling Phase 5](ADR_CLOUD_SCALING_AUTHORIZATION_PHASE5.md); it discharges
the first half of that ADR's deferred §1 row for 5B.

Phase 5A ended at a `CapacityAuthorizationCandidate` that binds a producer attestation and
verifies nothing about it. This ADR records the decisions taken to make such an attestation
**mintable and verifiable**, and the boundaries that keep that from becoming anything more.

---

## §1. The blocker this closes, stated as a traversal

A self-consistent forged recommendation launders cleanly through the whole Cloud Scaling
chain. Every step is individually correct:

| Step | What passes | Why it passes |
|---|---|---|
| 1 | The controller's real Phase-3 pipeline | The forger invents the capacity facts, so they are internally consistent |
| 2 | The unkeyed content digest | An unkeyed digest is a function of content, and the forger controls the content |
| 3 | Phase 4C structural admission | It reconciles a digest against an expectation the forger also supplies |
| 4 | A genuine `SubjectRiskDecision` | The decision binds a digest, not a provenance |
| 5 | A valid Phase 5A candidate | Phase 5A validates the attestation **structurally** and never checks the signature |

Nothing in that chain establishes **who produced the recommendation**. Phase 5A says so
itself: its one trust state is `PRESENT_BUT_NOT_TRUST_VERIFIED`, and the vocabulary for
saying otherwise deliberately does not exist in that package.

Phase 5B-0A adds the missing step. `tests/test_authenticity_laundering.py` builds the whole
traversal from Phase 5A's own frozen fixture, submits it, and asserts a typed refusal with
zero envelope requests, zero signer calls, zero ActionGate calls, zero credential calls and
zero executor calls.

## §2. Scope: producer authenticity only

**In:** a new producer-attestation contract at a new schema tag; an injected signer port at
the Controller output boundary; producer trust-resolution and verification; a verified
producer-authenticity artifact; typed refusals; canonical digests; tests, packaging, CI and
documentation.

**Out, and structurally unreachable:** policy authenticity (5B-0B), Phase 5A v0.2.0, Risk
Decision reconstruction, Risk Authority v3, scope repair, nonce and replay ledgers, issuer
freshness and audience, envelope-request construction, envelope signing, containment
lifting, ActionGate, credentials, execution, effect verification and learning.
`tests/test_import_boundary.py` asserts each absence over source, AST, exports and the
dependency manifest.

## §3. Decision — a NEW schema tag, not a widened v1

Phase 5A's producer-signing payload is **frozen**, at
`cloud-scaling-producer-attestation-evidence-1`, with the frozen signing-payload digest
`sha256:1035d2fc2ab8f4b443f815562f9f6ad8e4ce0032633f03a12e04e691c24cf2d0`. Phase 5B-0A does
not widen it, reinterpret it, or re-verify it.

`ProducerAttestationV2` is a separate contract at
`ugence.cloud-scaling/producer-attestation/v2`. Its signing payload binds, at minimum:

```
schema_version, signing_purpose, producer_id, issuer, producer_key_id,
signature_algorithm, signature_profile, signature_encoding,
tenant_id, subject_id, subject_type,
recommendation_id, recommendation_digest, issued_at
```

The signature is **excluded** from the payload it covers, and `signing_payload_digest` is
excluded and re-derived at construction rather than believed.

**Why a new tag rather than widening v1.** v1 binds the recommendation and nothing about
*who the recommendation is for*. That is enough to detect a swapped recommendation and not
enough to detect a swapped **tenant** or **subject**: a genuine v1 attestation minted for
one workload would be equally valid alongside a candidate reconciled for another. Adding
those fields to v1 would move a frozen digest, and reusing v1's tag for the wider payload
would let a v1 signature be presented as a v2 proof.

**Consequence, accepted:** the v2 proof travels **alongside** a Phase 5A candidate and is
independently bound to it, rather than inside it. Binding one inside a candidate requires a
Phase 5A 0.2.0, which is 5B-0B's work.

## §4. Decision — `issuer` and `producer_id` are separate fields, not required to differ

`issuer` is the authority whose key signed; `producer_id` is the identity claiming to have
produced the recommendation. Both are signed fields, and the trust anchor is resolved by
**`issuer`**, never by `producer_id`.

They are deliberately **not** required to differ in value. Phase 5 ADR §3 ratifies that
"the controller may sign its own output — a self-signature is a claim of origin, not a grant
of trust", and forcing inequality would refuse that ratified case. What the separation buys
is that the identity a verifier resolves a key under is stated explicitly and covered by the
signature, rather than being inferred from the producer's own name.

## §5. Decision — Risk Authority's canonicalization, and no second scheme

Every byte signed and every digest emitted flows through
`risk_authority.crypto.canonical` and `risk_authority.crypto.hashing`, through their public
`__all__`. There is no local JSON encoder, no `sort_keys=True` call, no `hashlib` use, no
second digest prefix and no alternate digest path in the distribution. Digest format is
`sha256:` plus 64 lowercase hex; a bare-hex or uppercase spelling is a rejection.

**What was deliberately not adopted.** The Trusted Evidence Authority carries its signed
bytes in a length-prefixed frame with its own evidence and receipt domain tags. Adopting
that here would put a third framing convention into the Cloud Scaling chain — Phase 4C,
Phase 5A and this package would then disagree about what "the canonical bytes" means.
Domain separation is instead carried where Phase 5A already carries it: **inside the signed
bytes**, as the schema tag and the signing purpose, both ordinary canonical fields.

One consequence is explicit. TEV's `TrustAnchorCoordinate.canonical_digest()` and
`TrustAnchorRecord.canonical_digest()` emit bare lowercase hex under TEV's own scheme.
Storing those in a Phase 5B-0A artifact would introduce a second digest spelling into a
distribution that admits one, so `anchor_coordinate_digest` and `anchor_record_digest`
re-digest those objects under Risk Authority's scheme. That is a re-digest, not a second
canonicalization.

## §6. Decision — domain separation asserted at import, failing closed

Following Phase 5A's `identifiers.py`, three inequalities are checked when the module is
imported, and a failure is an `ImportError` rather than a runtime surprise:

1. the v2 schema tag is not Phase 5A's frozen v1 tag;
2. the v2 signing purpose is not the D-4 routing purpose `cloud_scaling.capacity_action`;
3. the v2 signing purpose is not any policy-signing purpose, and Phase 5A's v1 purpose is
   not admitted against the v2 contract.

Policy Authority is a **forbidden import** for this phase (it is 5B-0B's dependency), so the
policy-signing purposes are named locally as a conservative closed set of the spellings this
repository uses. That is a widening of what is refused, never a narrowing: adding a spelling
can only reject more.

## §7. Decision — reuse TEV's trust anchors; do not reuse its evidence verifier

Every trust contract is TEV's, re-exported unchanged and asserted to be the *identical
object*: `TrustAnchorCoordinate`, `TrustAnchorRecord`, `TrustAnchorCapability`,
`TrustAnchorResolution`, `TrustAnchorResolverPort`, `KeyRevocation`,
`StaticTrustAnchorDirectory`, `DenyAllTrustAnchorDirectory`. There is **no second
trust-anchor store** in the repository, and none is created here. They are reusable because
they are payload-neutral: not one of them imports an evidence contract or presumes anything
about what the signed bytes contain.

TEV's evidence and receipt **verifiers** are not reused. A producer attestation is not an
evidence item — different schema tag, different signing purpose, different field set — and a
verifier specified against one payload has not verified another. A new verification protocol
is therefore required, and it resolves every key through the established anchor store.

**Capability ruling (revised).** `PRODUCER_ATTESTATION_CAPABILITY` is
`TrustAnchorCapability.CLOUD_SCALING_RECOMMENDATION_ATTESTATION` — a **dedicated**
capability, added to TEV's trust-anchor contract for this signing domain and used by
nothing else.

The first revision of this ADR ruled for `EVIDENCE_PRODUCTION`, reasoning that a producer
attestation "is the producer role". An independent closure audit rejected that ruling with
a demonstration. Because this repository deliberately keeps **one** trust-anchor store, the
capability is not a label describing a role — it is the component of the coordinate an
anchor is actually resolved by. Sharing it made a key provisioned purely to sign Trusted
Evidence, such as a telemetry agent holding no Cloud Scaling grant of any kind, equally
entitled to attest a capacity recommendation. The audit signed and verified exactly that.

Domain separation inside the signed bytes does not close it, and §5 above should be read
with that limit in mind: the schema tag and the signing purpose stop a *signature* from
being replayed across domains, but they say nothing about which *keys* a domain trusts.
Neither does `trust_anchor_set_id`, a naming convention or deployment documentation — none
of them is what the anchor is resolved by. Only the capability is, so the entitlement is
named there.

The three capabilities are mutually disjoint and compared by exact identity in both
directions:

* a receipt-issuance key cannot verify a producer attestation here;
* an evidence-production key cannot either — the refusal is a typed `ANCHOR_UNKNOWN`
  reached before any artifact is constructed;
* the dedicated capability grants nothing back inside TEV: it produces no evidence and
  issues no receipt, and TEV's own suite asserts both.

The capability is still not a parameter of the lookup — a caller cannot ask for
verification under another domain's capability, because there is nothing to pass. One key
may hold several capabilities, but each is a separate, explicitly configured anchor record;
nothing derives one grant from another. Which keys receive this capability is the
composition root's decision, not this package's and not TEV's.

**What TEV does and does not do here.** TEV supplies a reusable trust-anchor contract and
the capability coordinate. It performs no Cloud Scaling verification, and it neither admits
nor approves a Cloud Scaling recommendation. The verification routine in §10 is this
package's, over this package's payload.

**The TEV dependency is an exact symbol grant.** The authorization recorded in TEV's
`tests/packaging/test_dependency_boundary.py` names one consumer package *and* the exact
public trust-anchor symbols it may import: fifteen production symbols, one reference-grade
symbol listed separately, one test-only contract-error type. Every evidence, observation,
measurement, claim, receipt, trust-stage, admission and verification-engine surface fails
that boundary, as do module bindings in production source, internal-submodule imports, star
imports, dynamic imports and aliased forbidden symbols. An earlier revision exempted the
consumer's whole directory, which the audit showed let the entire TEV public API through
unreported.

## §8. Ruling — `StaticTrustAnchorDirectory` is reference grade, and is refused in production

The repository classifies it in its own words: "the deterministic **reference**
`TrustAnchorResolverPort` … suitable for tests, for local use, and as the shape a production
resolver should present."

`require_production_resolver` therefore refuses it under `production_mode=True`, and every
other resolver must **explicitly opt in** with `is_production_authoritative = True`,
following the Risk Authority convention. Silence is refusal, so a resolver that has never
considered the question cannot drift into production by default.

The refusal covers **every subclass** of a reference-grade resolver, and it is evaluated
**before** the opt-in. A subclass inherits the reference implementation whole — the same
in-memory dict, populated by the same caller — so it is reference grade by construction,
and setting `is_production_authoritative = True` on it declares something its inherited
behaviour does not support. An earlier revision matched the exact type, which meant a
three-line subclass carrying that attribute was admitted in production while the base class
it was identical to was refused; an independent closure audit found it, and the ordering
above is what closes it. The refusal is scoped to inheritance and nothing wider: an
independently implemented resolver that opts in is admitted, and so is one that merely
*holds* a reference directory as a delegate, because neither inherits the implementation.

The `DenyAllTrustAnchorDirectory` exemption below stays matched on the **exact** type, and
the asymmetry is the same rule applied consistently rather than an inconsistency: subclassing
narrows nothing, so a subclass of the deny-all directory is not known to deny everything and
does not inherit its exemption.

`DenyAllTrustAnchorDirectory` is exempt from the opt-in and admitted in production, because
it refuses every coordinate unconditionally: admitting it cannot widen anything, and
refusing it would leave a composition root with no ratified deny-by-default posture at all.
It is the only "no anchors" shape that ships, and it is not permissive.

## §9. Decision — the signer boundary has no oracle, and the Controller gains nothing

The Cloud Scaling Controller stays at **0.4.0**, key-free and advisory: no private key, no
signer, no crypto dependency, no trust-anchor resolution, no authorization semantics and no
new export. Nothing here imports a controller module, and the controller declares no
dependency on this distribution. The attestation is produced **at** the controller's output
boundary by an injected signer in *this* distribution, wired by the deployment — never **by**
the controller. The controller's own statement stands unchanged: its recommendation digest is
not a signature, not an authorization and not a proof of effect.

`ProducerAttestationSignerPort` has **no** "sign arbitrary bytes" method. A signer receives a
`ProducerAttestationSigningInput` — a token-guarded, package-minted value object, following
TEV's `ReceiptSigningInput` pattern — and there is exactly one route to one:

```
validated attestation body  ->  mint_producer_attestation()  ->  signature
```

A signer cannot choose or alter any recommendation fact, cannot widen the tenant or subject
identity, cannot select the signing purpose or schema tag, cannot mint authorization and
cannot issue an envelope: none of those are inputs it receives or outputs it returns. It may
refuse; it may not redirect.

*Stated plainly rather than over-claimed:* in-process code that reaches into a private module
attribute is not defended against, and no Python-level mechanism defends against it. What is
closed is the **public API** route. The load-bearing secret remains the signing key.

**Key custody.** No production private key exists anywhere in this repository. Exactly one
signer ships, marked `is_reference_signer = True` and refused by `mint_producer_attestation`
under `production_mode=True`. Private key material never reaches a contract object, a
canonical dict, a digest, a `repr`, an exception message or a record.

## §10. Decision — the verifier recomputes; it never trusts a supplied payload

Ten ordered groups, stop at the first failing one, deterministic:

1. exact-type admission — candidate, attestation, `as_of`
2. contract admission — schema tag, signing purpose, algorithm, profile, encoding
3. reconciliation — recommendation id and digest, tenant, subject, subject type, taken
   **from the candidate**
4. payload recomputation — rebuild the canonical payload from those reconciled facts and
   require **byte equality** with the attestation's own signing payload
5. anchor resolution at the exact `(issuer, key_id, capability)` coordinate
6. anchor identity re-check — a resolver may not answer a question it was not asked
7. anchor lifecycle at the injected instant — revoked, disabled, not-yet-valid, expired
8. profile and encoding agreement with the resolved anchor
9. signature decoding — canonical lowercase base16 of exactly the Ed25519 length
10. signature verification under the anchor's strictly validated public key

Group 4 is the decision that matters. A verifier that checks a signature over whatever it was
handed proves only that *someone* signed *something*. Recomputing from the candidate's own
reconciled facts means a genuine attestation for a different recommendation, tenant or
subject fails before a key is even resolved.

**Fail-closed vocabulary.** Unknown issuer, unknown key, wrong capability, algorithm
mismatch, revoked key, expired key, not-yet-valid key, malformed signature, payload mismatch,
recommendation substitution, tenant substitution and subject substitution each map to a
distinct typed member. Security outcomes are never disambiguated by message string.
`INDETERMINATE` is the default arm of every exhaustive match; `VERIFICATION_UNAVAILABLE` and
`INVARIANT_VIOLATION` cover the two ways verification can fail to reach a conclusion. None of
the three is a success.

**No exception becomes a success.** An unexpected exception, a resolver that raises and a
signature verifier that raises all become `VERIFICATION_UNAVAILABLE`. A structural test walks
every `except` handler in the distribution and fails if one can reach a verified artifact.

## §11. Decision — no clock, and no invented freshness window

`as_of` and `issued_at` are injected, required, timezone-aware parameters. A naive datetime
is refused rather than assumed UTC. No module imports `time` or `calendar`, and no AST call
expression reads a wall clock; both are asserted structurally.

Attestation **freshness** — a maximum age, a TTL, a skew allowance — is deliberately **not**
invented here. An unratified freshness window would be an unratified authority decision. Time
enters exactly one determination: the anchor's lifecycle. The verified artifact carries the
issuance instant so a later phase can judge it under its own ratified bounds.

## §12. Decision — a verification artifact is not an authorization

`VerifiedProducerAttestation` is exact-typed, immutable and non-authoritative. It binds the
candidate digest, the recommendation id and digest, tenant, subject and subject type, the
attestation digest, the verified producer, issuer and key id, the anchor coordinate and record
digests, the anchor capability, the profile and encoding, the issuance and verification
instants, the anchor window bounds, the verification profile and version, and its own digest.

It carries **no** field named authorized, executable, envelope, ActionGate, admitted,
credential or execution-permitted, because those concepts do not exist in this package.
`outcome` and `grants_authority` are read-only **properties**, not fields, so
`object.__setattr__` raises against the data descriptor and a doctored instance dictionary
loses to it. There is no `from_dict`: a serialized verification artifact would be a forgeable
one.

**A frozen dataclass is not a security boundary** — following Phase 4C's
`AuthenticatedRecommendation`. The boundary is **four** independent parts: a package-private
construction token, a self-digest recomputed over every bound fact, a **provenance registry**
of the determinations this process actually reached, and
`require_verified_producer_attestation`, which re-checks the exact type, field presence, the
token, registry membership and the digest at every consumption boundary. Constructor bypass,
`object.__new__` fabrication, `object.__setattr__` mutation, subclasses with diverting
properties, duck-typed look-alikes and metaclass equality attacks are each covered by a named
property in the suite.

**Why the registry, given the token.** The token alone makes *possession of one genuine
artifact* equivalent to the capability to mint arbitrary ones: it is a dataclass field, so it
can be read off a real artifact, and a forger who also recomputes `artifact_digest` produces
something the token and digest checks both accept. A determination this process never reached
has a digest it never recorded. The registry keys on the **determination**, not on object
identity — a determination is its facts, so a faithful copy is the same determination and
still revalidates, while a forger's differing facts do not. A `weakref.WeakSet` keyed on
value would be wrong here, and was the first attempt: `add` is a no-op for an equal member,
so the recorded reference can die while an equal, live artifact goes unregistered.

Stated plainly rather than over-claimed: in-process code that reaches into a private module
attribute can add to the registry exactly as it can import the token, and no Python-level
mechanism prevents that — the same residual the Trusted Evidence Authority documents for its
own signing boundary. What is closed is every route that does not require reaching into this
module's privates.

## §13. What remains open

**Policy authenticity is unresolved.** A verified producer attestation says who produced the
recommendation and nothing about whether the policy binding the candidate carries is genuine,
in force, or issued by an authority anyone trusts. That is **Phase 5B-0B**, and it is not
implemented here. Until it is, the Phase 5B verdict — *blocked on producer **or** policy
authenticity* — is half discharged, not discharged.

Also still open, and unchanged by this ADR: the binding Risk Decision cannot monotonically
authorize a Cloud Scaling action (`tools_allow` is empty and `Scope` carries none of the
operational dimensions), which is the second ratified blocker and belongs to a later subphase.

## §14. Package topology

```
packages/integration/cloud-scaling-producer-attestation
  distribution  ugence-cloud-scaling-producer-attestation
  namespace     ugence_cloud_scaling_producer_attestation
  version       0.1.0
  depends on    ugence-risk-authority>=0.4.0                      (public canonicalization only)
                ugence-trusted-evidence-authority>=0.2.0          (trust-anchor types + Ed25519 backend)
                ugence-cloud-scaling-authorization-contracts>=0.1.0 (the candidate, read-only)
```

No third-party runtime dependency is added: the Ed25519 backends arrive transitively as the
Trusted Evidence Authority's own declared requirements. Nothing upstream depends on this
package; it is a one-way leaf, and a test asserts it.
