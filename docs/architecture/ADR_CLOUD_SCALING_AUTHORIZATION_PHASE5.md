# ADR — Cloud Scaling Phase 5: Authorization, Admission, Credentials and Bounded Execution

**Status:** Accepted (decomposition ratified by the owner). **Phase 5A implemented; 5B, 5C,
5X, 5D and Phase 6 are not.**

> **Amendment (Phase 5B-0A).** The first half of the deferred 5B row — **producer
> authenticity** — is now implemented and recorded separately in
> [ADR — Cloud Scaling Phase 5B-0A: Producer Authenticity](ADR_CLOUD_SCALING_PRODUCER_AUTHENTICITY_PHASE5B0A.md).
> Nothing in *this* ADR changes: Phase 5A stays at 0.1.0 with its contract, its frozen
> digests and its single `PRESENT_BUT_NOT_TRUST_VERIFIED` trust state untouched, and §3's
> ratified rules are what 5B-0A discharges rather than revises. The v2 proof travels
> alongside a candidate and is not bound inside it. **Policy authenticity (5B-0B) and
> signed envelope issuance remain deferred.**

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

**Updated by R-12b (2026-08-24): the snapshot's field set changed, and that prediction held.**
`RiskDecision` gained `evaluated_at`, so `decision_snapshot` now carries the evaluator's stamp
alongside `issued_at` and `expires_at` — previously it carried the latter two and *no*
`evaluated_at` at all, which left the instant Phase 5B's occurrence gate depends on travelling
only on `SubjectRiskDecision`'s unbound outer field. Phase 5A now sources both decision instants
from the snapshot and refuses one that carries no `evaluated_at`, rather than falling back.

The frozen digests did move, exactly as this section predicted they would, and the suite failed
rather than silently disagreeing. Nothing about the recomputation itself changed: it is still the
same two public primitives over whatever the snapshot contains.

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

## §9. Guard coverage: what is authority-bearing, and what a refusal is

Phase 5A and Phase 5B are both swept in CI by gate removal: each `if` guard is neutralised
to `if False:` in a disposable copy and the whole suite is run against the result. The sweep
is only as meaningful as the two definitions it rests on, and both were being decided
case-by-case inside a script. They are ratified here.

### §9.1 A guard is authority-bearing when removing it changes the typed refusal

**The typed refusal is the ordered pair `(exception class, AuthorizationCandidateRejectionReason)`.**
The message is prose written for a human reading a log. It is deliberately *not* part of the
contract: no consumer may branch on it, it may be reworded without a version bump, and a
test that asserts a substring of it is asserting something this package does not promise.

A guard is **authority-bearing** when there is at least one constructible input for which
neutralising it changes that pair — including changing it to *no refusal at all*. A guard
for which no such input exists is **diagnostic-only**: it chooses which of two identical
verdicts is reported, and removing it costs a clearer message and nothing else.

Two consequences, both deliberate:

* Changing the *reason* is enough. A refusal that reports `SUBJECT_DIGEST_MISMATCH` where
  the contract says `CONTEXT_DIGEST_MISMATCH` is a wrong answer, not a cosmetic one, because
  the reason is what a caller is entitled to act on.
* Failing closed is not sufficient. A guard whose removal still refuses, with the same class
  and the same reason, has not been shown to carry authority — and a suite that only asks
  "was something refused?" cannot tell the two cases apart.

**A guard refuses whether or not it also converts.** An `if` whose body calls an admission
helper is a guard, and it stays a guard when the call's result is bound.

An earlier revision of this section said otherwise: an `if` that *binds* a helper's result
was a normalisation branch, separated from a gate by whether the call was a statement or an
assignment, and `issued_at = _parse_ts(issued_at)` was named as the site that separation
excluded. Three claims carried that carve-out and all three were measured false at
`attestation.py:261`:

| claimed | measured |
|---|---|
| neutralising it produces no refusal to compare | it produces a typed `MALFORMED_CANONICAL_FIELD` |
| it changes what the suite can collect at all | collection is 407 either way |
| it is therefore neither a kill nor a survival | it survived the entire suite |

The carve-out was not describing a conversion. It was reasoning added to explain away an
`UNSCORED` result, and it hid a line no test executed: nothing rebuilt an attestation from a
canonical wire mapping, so the parse that lets `issued_at` cross the wire as a string and
arrive as a `datetime` had never run. The site is inventoried, and killed by a test that
round-trips an attestation through its canonical form.

The rule that replaces it is the one the sweep implements: **a body that can reach a refusal
makes the `if` a guard**, and binding a value on the way there does not change that.

A diagnostic-only guard is not a defect and is not to be deleted. It is excluded from
*scoring*, with the subsumption that makes it diagnostic-only recorded and measured.

### §9.2 `equivalent-mutant` may not be claimed across a distribution boundary

A guard is an **equivalent mutant** when its condition is false in every program the package
can be part of, so `if False:` is the same program on every path, for every input. That is a
claim about the program, and it may only be made when every operand is fixed by **the same
distribution as the guard**.

It may **not** be claimed for a guard comparing against a value imported from a separately
versioned distribution admitted by an open-ended pin. This package depends on
`ugence-cloud-scaling-controller>=0.4.0`, `ugence-risk-authority>=0.5.0` and
`ugence-cloud-scaling-risk-integration>=0.1.0`. Under a resolution any of those pins permits,
such a condition can be true — which is precisely why the drift guard exists. That the
condition is false in the checkout under test is a property of the installation, not of the
program, and calling it an equivalent mutant asserts the guard is pointless when it is in
fact the only thing standing between a permitted resolution and an unratified identifier
bound into a candidate digest.

Such guards were classified `unscorable-by-single-checkout-fixture`: real, reachable, and
beyond what a fixture installing one resolution can measure. **That last clause was wrong,
and the reason has since been emptied.**

The *fixture* installs one resolution. A *test* is free to construct another: an
open-ended pin admits later versions, so the test copies the real upstream source, applies
the drift the guard names, bumps the version, and puts it first on `PYTHONPATH`, where it
is the installed distribution for that process. Every guard the reason was ever applied to
— one in Phase 5A, four in Phase 5B — was measured that way and killed. Nought for five.

The reason stays in the closed vocabulary, because a guard could genuinely qualify, but it
now carries a bar that matches its name only when earned:

> `unscorable-by-single-checkout-fixture` requires evidence that **no resolution the
> declared constraint permits** makes the condition authority-relevant. "The fixture
> installs one resolution" is a fact about the fixture and is not sufficient. Where the
> constraint is open-ended and the operand is upstream's to move, the expected outcome is a
> constructed second resolution and a scored guard.

Constructing one is not always a single edit. Phase 5B's action-type guard sits behind
Phase 5A's own drift guards: moving the controller's enum alone is refused one package
upstream, giving the same refusal with and without the guard under test. Reaching it meant
drifting the controller, Phase 4C and Phase 5A together — a coordinated release the pins
admit. A second resolution has to reach the guard, not merely exist.

**The bar is a property of the boundary, not of the reason.** Stated once, for every
member of the vocabulary:

> **No exclusion reason may be claimed across a distribution boundary on evidence about one
> installation.** Where a guard's deciding operand is defined in a separately versioned
> distribution under an open-ended pin, the claim required is that *no resolution the
> declared constraint permits* makes the guard authority-bearing. Nothing observed of the
> installed release establishes that. Where every deciding operand is defined in the
> distribution that declares the guard, the same observation is a property of the program
> and the reason stands on it.

Each reason had been allowed to rest on something weaker, and each was withdrawn on the same
measurement. `unreachable-behind-earlier-guard` rested on measured evidence of *which guard
fires first*, in this distribution or an upstream one. Across a boundary that is the
identical mistake, wearing different clothes: which guard fires first is a fact about the
resolution that happens to be installed, and an upstream release is free to stop refusing.
Two exclusions were withdrawn on exactly that, both measured:

* Phase 5A's `identifiers.py:100` hid behind Phase 4C's import-time check, in
  `ugence-cloud-scaling-risk-integration` under `>=0.1.0`. Under a 0.2.0 that no longer
  refuses there, Phase 5A's own guard is the one that answers; removed, Phase 5A imports and
  binds a four-member action vocabulary against a controller ratifying five.
* Phase 5B's `verification.py:494` hid behind two gates said to make its condition
  unreachable. Its operand is a property of the Policy Authority's `PolicyResolution`, under
  `>=0.1.0`. Under a 0.2.0 returning a truthy non-`True`, the guard refuses
  `HISTORICAL_RESOLUTION_REFUSED` where removing it refuses `INVARIANT_VIOLATION`.

`diagnostic-only` rested on the narrowest-looking claim of the three, and failed the bar
just as squarely. The reason says a successor guard refuses with the same outcome, so
removing this one costs a message and no authority. Where the successor's decision is made
upstream, that is a claim about the installed release. Both withdrawals were measured
against a Policy Authority 0.2.0 built from real source under `>=0.1.0`:

* `verification.py:487` (`resolution.historical`). The successor is redundant only *because*
  `implies_current_validity` carries the historicity term (`core/records.py:334`). Under a
  0.2.0 where the property is `return self.resolved`, the successor goes silent on a genuine
  revocation: the guard refuses `HISTORICAL_RESOLUTION_REFUSED`, removing it refuses
  `INVARIANT_VIOLATION` — an internal-integrity report for an ordinary, expected answer.
* `verification.py:706` (`adapter_id != record.adapter_id`). The digest below it reproduces
  the same mismatch only while the authority's frame *binds* adapter identity
  (`core/canonical.py:212`). Under a 0.2.0 whose frame drops the adapter term, a projection
  naming another adapter reproduces the correct digest, and this guard is the last thing in
  the way: removing it turns `POLICY_PROJECTION_DIGEST_MISMATCH` into `VERIFIED`. Not a
  changed refusal — a mint.

The alternative was to ratify a narrower `diagnostic-only` bar that accepts installed-release
evidence. It was rejected. It would have carved out most of the surviving exclusions
immediately after retiring the same asymmetry for `unreachable-behind-earlier-guard`, and the
guard-99 measurement shows what the carve-out would license: not a lost diagnosis, a mint.

No reason survived the bar on the evidence it had been resting on:
`unscorable-by-single-checkout-fixture` nought for five, `unreachable-behind-earlier-guard`
nought for two, `diagnostic-only` nought for two of two attacked across a boundary. All stay
in the closed vocabulary, because a guard could genuinely qualify. Of the eleven exclusions
that remain, every one is `diagnostic-only` or `equivalent-mutant`, and each was re-checked
against the rule above when it was ratified: every operand deciding them is either defined in
the distribution that declares the guard, or fixed by the Python language itself — `None`
cannot satisfy an `isinstance`, a `hasattr`, or an exact string comparison, whichever release
supplies the type.

### §9.3 Drift assertions run at import *and* at test time

The ratified identifiers are asserted against their Phase 4C originals when
`identifiers.py` is imported, and again as an explicit test. Import-time alone is green in
any process that imports a stale wheel, an editable install pointing at an older checkout,
or a resolution that satisfied Phase 4C from elsewhere. `identifiers._assert_no_drift` cites
this section for that requirement; it is recorded here so the citation resolves.
### §9.4 Conditional expressions are decision points, and collapse to their `else`

§9.1 makes the outcome the contract. A conditional expression can decide one, and `if False:`
cannot reach it, so both the class and its operator are ratified here rather than left to the
sweep to imply.

**The class.** A conditional expression is a decision point when it decides a typed outcome.
Two shapes qualify:

* it **chooses between two outcomes** — `reason = FORGED_TRUST_STATE if forged else
  UNKNOWN_FIELD` decides which reason a caller may act on, exactly as an `if` would;
* it **decides whether an outcome is read at all** — `getattr(exc, "outcome", None) if
  isinstance(exc, _PackageError) else None`. Collapsed, every typed outcome flattens to one
  fallback: measured, `COORDINATE_MALFORMED` and `INVARIANT_VIOLATION` both become
  `VERIFICATION_UNAVAILABLE`, which tells a caller the check could not run when it ran and
  refused.

**The operator.** The expression is replaced by its `else` branch. That is the
authority-weakening direction in both shapes, and the direction matters: a mutation that
made the guard *stricter* would be caught by any test asserting the ordinary path and would
prove nothing about the guard.

* Choosing between outcomes, the `else` is the branch taken when the specific condition does
  *not* hold — the general, weaker answer. Collapsing to it reports the general reason where
  the specific one was owed, which is the defect the guard prevents.
* Gating the read, the `else` is the branch that declines to read the outcome, so collapsing
  discards the typed answer.

**When the specific reason sits in the `else` instead.** Nothing forces an author to write
the weaker branch second, and `A if not cond else B` inverts it. The operator is defined by
authority, not by position: collapse to whichever branch is the **more permissive** — the one
reporting the more general outcome, or the one declining to read an outcome at all. Where the
two branches are equally specific and neither is more permissive, the expression is not a
decision point under this section; it is a naming choice, and is not inventoried. A guard
whose direction cannot be decided by that rule must be recorded as `[R]` and ratified
explicitly rather than swept under whichever branch happens to be second.


## §10. ExecutionTargetScope schema 2 — the cross-cloud vocabulary, ratified 2026-09-01

Ratified as ETS-1 … ETS-16 after a read-only audit. §5's scope was account-bound but not
*cloud*-bound, and the gap was structural rather than cosmetic.

### §10.a What was wrong

`account_id` was one opaque string carrying, undocumented, an AWS account number, a GCP
project or an Azure subscription. Nothing in the chain named the cloud, so two providers'
identifiers could collide as strings, and reconciliation never compared `account_id`
against anything upstream — it was presence-checked and digest-bound only. Worse, an Azure
target was **not addressable at all**: an ARM resource id needs a subscription *and* a
resource group, and the scope had nowhere for the second.

`compute_group` was considered and rejected as that home (ETS-5). It is written from
`subject.cluster` by the projection and equality-gated against it at the candidate seam, so
putting a resource group there either changes what the frozen Phase 4 seam means or is
refused as a target substitution. An AKS cluster also *lives inside* a resource group, so
one slot cannot hold both.

### §10.b What was ratified

`cloud_provider`, required, against the closed vocabulary
`{"aws", "gcp", "azure", "self-hosted"}`. `(cloud_provider, account_id)` is the governed
account identity. `resource_group`, required for Azure and required absent elsewhere.
Schema `-2`; v1 refused, never upgraded, and provider inference forbidden.

**Per-provider grammar was deliberately excluded** (ETS-11). Validating that an AWS account
is twelve digits would put provider-specific format knowledge inside a package whose whole
posture is provider-neutral structure, and buys nothing the pair does not.

### §10.c Two limits this section states rather than implies

**Neither new field is reconciled against anything.** ETS-8 keeps `CapacitySubject`
provider-neutral, so no projected fact exists to reconcile against. Both are scope-only,
the shape ETS-6 ratified for `namespace`. Their protection is the digest binding and
`account_id`'s presence gate — a scope naming the wrong provider is caught only if the
digest it is bound into is checked. That is weaker than the reconciliation §6 relies on
elsewhere, and it is recorded here so no reader infers otherwise.

**The implemented Azure rule is narrower than ETS-4's words.** ETS-4 scopes the requirement
to "resource-level scaling targets"; the scope carries no field distinguishing one, and
adding a discriminator was not ratified. The enforceable rule is provider-conditional.
A narrower rule needs a discriminator field and a further ruling.

**`cloud_provider` names a field whose value is sometimes not a cloud.** ETS-10 admitted
`self-hosted` — the repository's existing spelling — so a Kubernetes target belonging to no
cloud is buildable. Renaming the field was not ratified and would be a second breaking
change.

### §10.d The ratified guard counts moved, and were re-ratified

Adding validation adds guards. The total went 114 → 118 and the peripheral inventory
28 → 31, and **both were put back to the owner rather than re-pinned as arithmetic**
(ETS-15). A ratified count is not a derived one: a pin computed *from* the inventory cannot
tell you the inventory was right, which is the failure the guard-coverage ADR records at
§13.a.

The two numbers moved by *different* amounts. Three of the four new guards fall inside the
recorded peripheral shape; the `cloud_provider == "azure"` conditional does not. Ratifying
one would not have settled the other.

The peripheral inventory is renamed `peripheral-attestation-target` (ETS-16). Its old label
encoded its own value, so it went stale the moment the value moved — and renaming it to
`peripheral-31` would only defer the same problem.

### §10.e What the audit's predicted cascade missed

The pre-implementation audit traced the digest cascade as scope → binding → candidate. The
**policy coordinate binding also moved**: it carries the scope digest independently, and no
prediction caught it. Five digests moved in total, including this package's downstream
verified-artifact digest.

The lesson is §13.a's, one package over: a cascade reasoned about is not a cascade
measured, and the difference is exactly the sort of thing that looks right until something
recomputes it.
