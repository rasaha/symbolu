# Ratification record — Cloud Scaling Phase 5B-1, decision-scope repair

**Status:** ratified. Rules on the five decisions of the 5B-1 decision-scope audit, at
`aa8d2b5e`, against `ADR_CLOUD_SCALING_POLICY_AUTHENTICITY_PHASE5B0B.md` and its
`_RATIFICATION.md`. No implementation is included or authorized by this document beyond the
sequence named under *Consequence*.

## Evidence re-measured for this ruling

Every number below was measured in this session at `aa8d2b5e`, not carried from the audit.
`[V]` verified by the command shown, `[I]` inferred from source read, `[R]` requires
ratification, `[G]` gap.

| Fact | Value | Command |
|---|---|---|
| Phase 5A suite | 242 passed, 0 failed, 0 skipped | `python3 -m pytest -p no:cacheprovider --no-header -q` in `packages/integration/cloud-scaling-authorization-contracts` |
| Phase 5B-0B suite | 259 passed, 0 failed, 0 skipped | `python3 -m pytest packages/integration/cloud-scaling-policy-authenticity/tests -p no:cacheprovider --no-header -q` |
| Phase 5A's ten pinned constants | all ten reproduce live | recomputed from the genuine Phase 3/4C/5A chain before any option was evaluated |
| Widen `PolicyTargetBindingReference` in place | **2** of ten move | `FROZEN_POLICY_BINDING_DIGEST` `sha256:8961f6b2…` → `sha256:b2d096c6…`; `FROZEN_CANDIDATE_DIGEST` `sha256:db72ffff…` → `sha256:8553927f…` (and the self-validating `binding_digest` field `sha256:227e6a19…` → `sha256:92b5796c…`) |
| Additive V2 field on the candidate | **1** of ten moves | `FROZEN_CANDIDATE_DIGEST` → `sha256:52ed63bc…`; the other nine unchanged |
| Alongside, as 5B-0B ships | **0** of ten move | the baseline |
| **Not in the audit:** 5B-0A's verified artifact digest | also moves, under *either* in-candidate option | `VerifiedProducerAttestation.digest_payload()` binds `candidate_digest`; recomputed with the V2-moved candidate, `FROZEN_VERIFIED_ARTIFACT_DIGEST` `sha256:519983d8…` → `sha256:e5baf677…` `[V]` |
| The partition guard is a pin, not a ratchet | **5 passed** | promoted `candidate_digest_fact` in `verified.py` *and* `verification.py`, updated `FROZEN_ARTIFACT_DIGEST` → `3217b3cb…` and `FROZEN_PARTITION_FINGERPRINT` → `2523b5a6…`, left `VERIFICATION_PROFILE_VERSION = "v1"`; `tests/test_frozen_digests.py` → 5 passed |

Two byproducts of the promotion probe are recorded because they bear on the work: the
verified/recorded maps are written out twice — in `verified.py` and again in
`_mint_verified_artifact` — so a promotion must edit both `[V]`; and editing only one is
caught, by the artifact's own `__post_init__` self-digest, as a refusal rather than a wrong
answer `[V]`.

---

## D-5B1-1 — bind the coordinate inside the candidate, via an additive V2 reference

**Ratified, with two conditions.** A new `PolicyTargetBindingReferenceV2` is carried as an
additional, **required** field of `CapacityAuthorizationCandidate`. The existing
`PolicyTargetBindingReference` is neither widened nor removed.

One pinned Phase 5A digest moves rather than two, and one is the floor: every field of the
candidate enters `digest_payload()`, so no in-candidate binding can move zero `[V]`.

That claim first carried the qualifier *"for a binding that is actually bound"*, because
nothing made a future binding be a field: a coordinate carried as a derived property or in a
side table would move zero digests, not being inside the candidate digest at all — and would
therefore bind nothing, since the candidate could then carry a different coordinate under an
unchanged digest. **5B-2 closed that hole (R-11)**, so the qualifier is retired: completeness
now enumerates the public attribute surface rather than `dataclasses.fields()`, and a
non-field attribute must either be digest-bound or named exempt under a rule that reads its
source. Removing
V1 instead would move `FROZEN_POLICY_BINDING_DIGEST` as well and would discard the
bounds-agreement and scope-digest checks Phase 5A already performs against the target scope.

**Condition 1 — the field is required, not optional.** An optional binding leaves the A-59/R-4
residual open by default, which is the residual 5B-1 exists to close.

**Condition 2 — the two references cannot name different policies.** V1 and V2 both carry a
policy identity, so the candidate can state a contradiction that nothing today would detect
`[I]`. V2's validation must cross-check `policy_id` and `policy_version` against the V1
binding it accompanies, and `target_scope_digest` against the same scope V1 binds. Without
that check the repair adds a second policy name rather than binding the first.

**The audit's cost statement is incomplete and is corrected here.** "One pinned digest rather
than two" is true of Phase 5A's ten. Repository-wide, an in-candidate binding also moves 5B-0A's
`FROZEN_VERIFIED_ARTIFACT_DIGEST` `[V]`, and re-pins the Phase 5A candidate digest where 5B-0A
copies it (`tests/test_frozen_digests.py:93`, `tests/test_phase5a_invariants.py:233`). Option
(a) would move all of those *and* the second Phase 5A constant, so the ranking is unchanged —
but the work is a four-package edit, not a one-line one, and is authorized as such.

## D-5B1-2 — Phase 5A does not stay at `0.1.0`

**Ruled: Phase 5A moves to `0.2.0`.** D-5B0B-6's "Phase 5A stays at `0.1.0`" was conditional on
the proof travelling alongside; 5B-1 supersedes that premise, and a version is not a promise to
be kept by not making the change the phase exists to make.

The candidate digest is a value two merged packages pin `[V]`, and the public type set gains a
member. Pre-1.0, that is a minor bump. Changelog discipline, all four points mandatory:

1. Name every digest that moved, old → new, with the file that pins each.
2. Move `AUTHORIZATION_CANDIDATE_SCHEMA_VERSION` to `…-candidate-2` and give V2 its own
   `…-policy-target-binding-2`. This is what separates 5B-1 from the F-2 remediation, which
   moved the candidate digest while keeping schema `-1`: F-2 changed only what the payload
   covered, whereas a new field changes the serialized shape a strict `from_dict` accepts `[V]`.
3. Pin the superseded candidate digest as a negative anchor, exactly as
   `SUPERSEDED_PRE_F2_CANDIDATE_DIGEST` does, so a silent revert is caught rather than
   re-baselined.
4. `cloud-scaling-policy-authenticity` moves to `0.2.0` with its profile version (see D-5B1-3).
   `cloud-scaling-producer-attestation` stays at `0.1.0`: its source does not change and its
   behaviour is unchanged — only its fixture pins move — and its changelog records the re-pin.

5B-0B's `tests/test_phase5a_untouched.py` asserts `0.1.0` at line 36 and re-runs Phase 5A's
frozen suite at line 62. Those assertions encode D-5B0B-6 and must be amended by the same PR
that supersedes it, not deleted: the file's purpose — that a change to Phase 5A surfaces in the
package that caused it — survives the ruling.

## D-5B1-3 — the partition guard becomes a ratchet before any promotion

**Ratified, and ordered first.** The measurement holds: a promotion that updates both constants
under an unchanged `VERIFICATION_PROFILE_VERSION` passes at 5 passed `[V]`. The CI step that
calls this gate "mechanical rather than remembered"
(`.github/workflows/cloud-scaling-policy-authenticity-ci.yml`) re-runs the same file and
inherits the same weakness `[G]`.

A ratchet cannot be built from a constant that lives in the file being edited — updating the pin
is exactly as cheap as the change it is supposed to gate. The enforcement must derive the
"before" from repository history: compare the partition membership at the merge base against the
working tree, and fail on any of **three** conditions — when membership changed and the profile
version did not; when the version changed without a changelog entry naming it; and when a moved
fact is not disclosed in the changelog by name and direction.

**The third rule, ratified on the owner's ruling of 5B-2.** The decision as first written named
two rules, and two rules leave a free ride: a bump *earned* by one disclosed promotion carries a
second, undisclosed one for nothing. Measured twice, and the second measurement is the one that
settles it — reverting to the two-rule wording and promoting `resolved_as_of_fact`, the injected
and unvalidated clock, with only `candidate_digest_fact` disclosed goes green at **282 passed**,
while the changelog *affirmatively states* that the fact stays recorded `[V]`. A gate that lets
the code contradict the changelog it just checked is not enforcing disclosure. The two-rule
wording was underspecified rather than a ceiling, and the widening implements the decision's own
intent. Disclosure must be **structured** — `promoted: <fact> — …` / `demoted: <fact> — …` — because
a mention-anywhere check is satisfied by the very sentences that state the opposite. It runs in the package's CI and as a test
that skips only where there is no checkout, matching the existing `_find_repo_root` convention.

**Ordering:** the ratchet lands and is proven — a negative control that performs the promotion
without the bump and observes the failure — *before* `candidate_digest_fact` is promoted. Building
the guard after the first promotion would leave the one event it exists to catch untested.

**What that ordering is, precisely** `[I]`. The independent design review corrected an earlier
overstatement here. GitHub Actions runs `pull_request` workflows at the branch tip, not per
commit, so **nothing in CI re-verifies that the ordering held at each intermediate commit**, and
a squash-merge erases the sequence entirely. The ordering is author discipline and reviewer
legibility, not an enforced property. What the ratchet actually guarantees is narrower and still
correct: *this change's net effect* is disciplined, measured against the merge base.

## D-5B1-4 — V2 carries the bare Policy Authority digest, under its own validator

**Ratified.** `policy_body_digest` enters V2 as bare lowercase 64-hex, validated by a new Phase
5A predicate for that shape. It is not re-encoded with a `sha256:` prefix, and no converter is
added in either direction.

D-5B0B-2 measured that the two namespaces are incompatible, and 5B-0B ships the refusal to
convert as a rule with its reason: *"a re-prefixed digest is a digest nobody signed, over a frame
nobody hashed"* (`canonical.py` module docstring) `[V]`. A prefixed re-encoding would oblige
5B-0B to strip it back before comparing against the resolution, putting a string transform on the
one comparison the whole phase exists to make. The existing `policy_artifact_digest` field keeps
its Phase 5A shape and its Phase 5A meaning; V2's field is separately named and separately
validated, so the two are never confused for one another.

## D-5B1-5 — the reconciled coordinate must be complete on all six components

**Ratified.** All six of `policy_family`, `policy_id`, `version`, `content_digest`, `scope` and
`tenant_id` are required fields of V2, none optional, none defaulted.

D-5B0B-3 measured that exact-match lookup is the only lookup the registry performs, that all six
are signature-covered, and that a reference missing three of them is not a partially specified
coordinate but not a coordinate at all `[V]`. A five-component V2 would reconcile against a
coordinate the authority cannot address, which is a reconciliation in name only.

---

## Consequence

5B-1 is authorized as one draft PR, in this order:

1. The ratchet (D-5B1-3), with its negative control, at `cloud-scaling-policy-authenticity`
   `0.1.0` — no promotion yet, no digest moves.
2. `PolicyTargetBindingReferenceV2` and the candidate field (D-5B1-1, D-5B1-4, D-5B1-5), Phase
   5A to `0.2.0` with the schema ids and negative anchors of D-5B1-2.
3. Reconciliation in `cloud-scaling-policy-authenticity`: the verifier compares the candidate's
   V2 coordinate against the resolved coordinate, `candidate_digest_fact` is promoted to the
   verified half, the profile version moves to `v2`, and the distribution to `0.2.0`.
4. Re-pins and changelog entries in `cloud-scaling-producer-attestation` (fixtures only, staying
   at `0.1.0`) and the amendment of 5B-0B's `test_phase5a_untouched.py`.

## Residuals

| # | Residual | Owner |
|---|---|---|
| R-2 `[R]` | Where `as_of` comes from and what makes it trustworthy. Unchanged by this ruling; `resolved_as_of_fact` stays in the recorded half | 5B-2 |
| R-3 `[G]` | `resolve_policy` does not re-enforce `coordinate.content_digest == policy_body_digest`; 5B-0B refuses the divergence at its own boundary, the authority still permits it | Policy Authority |
| R-7 `[G]` | The verified/recorded maps are written twice, in `verified.py` and `_mint_verified_artifact`. The self-digest catches drift as a refusal, so this is a maintenance hazard rather than a correctness one — but the first promotion is when it bites | 5B-1 |
| R-8 | Bound extraction — that the candidate's `max_permitted_*` are the bounds the verified policy body states — remains open after 5B-1. Binding the coordinate is not extracting the bounds | 5B-2 |

---

## As implemented

The four ordered steps landed as four commits on `claude/cloud-scaling-5b1-ratification-olctwy`.
Each leaves the whole repository green, so the mechanical consequences of a step (a neighbour's
fixture, a moved pin) sit in the commit that caused them rather than in a later one.

**1. The ratchet, before the promotion (D-5B1-3).** `tests/_partition_ratchet.py` and
`tests/test_partition_ratchet.py` read the partition at the merge base — parsed out of the
historical source with `ast`, never imported — and fail when the verified/recorded membership
moved without a `VERIFICATION_PROFILE_VERSION` bump, or when the version moved with no
changelog line naming it. A parser-fidelity property measures the AST reader against the
imported truth first, so a silent miss cannot leave the gate green and vacuous, and negative
controls drive a real promotion-without-a-bump and a bump-with-a-silent-changelog through the
gate and observe it fail. `[V]` The gate was also exercised end to end: promoting
`candidate_digest_fact` in the working tree without a bump fails it, naming the promoted fact.
CI resolves the baseline from the event's own default branch and sets
`UGENCE_RATCHET_REQUIRED=1`, so an unresolvable baseline fails the workflow instead of skipping.

**2. `PolicyTargetBindingReferenceV2` (D-5B1-1, D-5B1-4, D-5B1-5).** Six required coordinate
components, the bare-64-hex `policy_body_digest` under its own predicate with no converter in
either direction, the target-scope binding, and a self-validating digest. Carried as a
**required** candidate field beside the existing reference, which is unchanged. Two builder
guards refuse a candidate whose two policy references disagree on `policy_id`/`policy_version`
or whose coordinate binds another scope. Phase 5A → `0.2.0`, schema `…-candidate-2`.

**3. Gate 11 and the promotion.** The verification routine reconciles a supplied candidate's
coordinate against the resolved policy on all six components, the signed body digest and the
issuing identity, refusing a disagreement with `CANDIDATE_COORDINATE_MISMATCH`.
`candidate_digest_fact` moved to the verified half, `VERIFICATION_PROFILE_VERSION` → `v2`,
distribution → `0.2.0`.

**4. Neighbours.** `cloud-scaling-producer-attestation` re-pinned (fixtures and sdist payload
only, staying at `0.1.0`); 5B-0B's `test_phase5a_untouched.py` amended rather than deleted.

### Measured

| Fact | Value |
|---|---|
| Phase 5A suite | 242 → **277 passed**, 0 failed, 0 skipped |
| Producer-attestation suite | **437 passed**, 0 failed, 3 skipped, 440 collected (the skips need a built dist in the tree; pre-existing) |
| Policy-authenticity suite | 259 → **286 passed**, 0 failed, 0 skipped — *with a ratchet baseline supplied.* A bare clone with no `UGENCE_RATCHET_BASE` and no default-branch ref skips one: the ratchet gate itself, for want of history to compare against. CI supplies the baseline and sets `UGENCE_RATCHET_REQUIRED=1`, which is why the runner reports 0 skipped |
| Policy Authority suite | **331 passed**, 0 failed, 0 skipped |
| Phase 5A digests moved | **1 of 10**: `FROZEN_CANDIDATE_DIGEST` `sha256:db72ffff…` → `sha256:be06c653…` |
| New Phase 5A pin | `FROZEN_POLICY_COORDINATE_BINDING_DIGEST` `sha256:ad1d1ad9…` (ten pins → eleven) |
| Producer-attestation digest moved | `FROZEN_VERIFIED_ARTIFACT_DIGEST` `sha256:519983d8…` → `sha256:5a2a6648…` |
| Policy-authenticity digests moved | artifact `8b0ea25f…` → `f245511d…`; partition fingerprint `86d39d25…` → `242ac003…` |
| Gates | ten → **eleven** |
| Recorded facts | four → **three** |

Every superseded value above is pinned as a negative anchor in the package that produces it.

### Where the implementation is narrower than a reader might assume

* **`candidate_digest_fact` is verified *when present*.** The candidate stays optional, so
  `None` means no candidate accompanied the determination. It never means one was carried
  unchecked — a candidate that does not reconcile mints no artifact — and both halves of that
  are measured. This is the one member of the verified half whose status is conditional, and
  it is documented as such on the artifact, in `RECORDED_FACT_NAMES`' neighbour and in the
  derivation ledger.
* **Three fields cross-checked between the two policy references, not five.** `policy_id`,
  `policy_version` and `target_scope_digest`, exactly as ratified. The issuer and key are not:
  Phase 5A's `policy_issuer`/`policy_key_id` have no ratified correspondence to the authority's
  `issuing_authority_id`/`key_id`, and inventing one would be Phase 5A asserting something
  about the Policy Authority no clause supports. Gate 11 does compare the issuing identity,
  because there the determination knows the truth.
* **The coordinate's tenant is not compared against the candidate's tenant.** The authority's
  global tenant is the empty string, so a global-scope policy legitimately bounds a
  tenant-scoped action. Recorded as R-9 below rather than decided silently.

### Corrections from the independent audit of `ed611fd2`

An independent audit re-measured the claims in this record. Two were overstated and are
corrected above: the producer-attestation suite reports **437 passed of 440 collected**, not
440 passed — the original figure read the junit `tests` attribute, which counts the 3 skips
inside the total; and the policy-authenticity **0 skipped** holds only where a ratchet baseline
is supplied, which CI does and a bare clone does not. The audit also refuted the unqualified
form of the floor claim, now restated under D-5B1-1 and carried as R-11.

Confirmed unchanged by that audit: no gate 11 bypass across five sub-checks; nothing in the diff
grants authority, resolves a policy inside Phase 5A, reads a clock or converts between the digest
namespaces; the two pins replaced by derivations were not weakened; and every digest count, gate
count, negative anchor and version pin in this record reproduces exactly. The attack on the
ratchet itself had not reported when these corrections were made.

### The audit's ratchet finding, and the repair `[V]`

The attack on the ratchet found the gate's own logic hole, and re-measuring it showed it was
worse than the audit reported. Rule 1 asked *whether the version moved*, not whether the
disclosure accounted for what moved. So once one legitimate promotion had bumped the version
and added its changelog line, a **second, undisclosed promotion in the same change was
invisible**: `version_moved` was already true, so rule 1 stayed silent, and the line the first
promotion added already satisfied rule 2.

The audit judged this a misleading-signal risk, on the grounds that the wider suite still
caught the extra fact. Measuring the harder case refutes that: with a second promotion applied
and every pinned constant and hardcoded fact name updated alongside it — four cheap edits — the
**entire 282-property suite went green and the ratchet passed 10/10** `[V]`. Every guard that
noticed was itself a pin, and updating a pin is exactly the edit this gate exists to render
insufficient.

**Repaired, and the first repair was itself too weak.** A third rule now requires every fact
that changed halves to be disclosed. The first form asked only whether the fact name appeared
anywhere in the changelog, and testing it end to end showed that vacuous:
`resolved_as_of_fact` already appears in this package's changelog in a sentence saying it
*stays* recorded, which silently satisfied the check for a promotion of that very fact. The
rule now demands a **structured** line — `promoted: <fact> — …` or `demoted: <fact> — …` — with
the direction matching. Three negative controls drive an undisclosed second promotion, a
demotion riding alongside a disclosed promotion, and the disciplined multi-fact change through
the gate and observe the first two fail and the third pass. Suite at the time of that
measurement: **285 passed**; **286** at `a2884dae`, which added the R-9 property below.

This was a strengthening beyond D-5B1-3's literal wording, which named two rules. It was offered
as implementing that decision's intent — a promotion cannot ship without disclosure — rather than
as a new decision. **The owner ratified it as-is in 5B-2**, on the measurement above; D-5B1-3 is
restated as three rules and the `[R]` is discharged. One limit is recorded rather than repaired
`[G]`: rule 3 forces a promotion to be *disclosed*, and cannot make the disclosure *true*. That
is the right ceiling for a changelog gate.

### The independent design review, and what it changed

A second, independent review — a different model, deliberately, because these are judgment calls
that a same-model session would share blind spots on — ruled on the five boundaries. It upheld
four: `candidate_digest_fact`'s conditional verification (with the reasoning that "verified"
means the routine correctly evaluated the input including its absence, which no other verified
field claims more strongly), the three-field cross-check between the two Phase 5A references
(forcing agreement on issuer and key, which have no ratified correspondence, would be false
rigor), gate 11's ten-field set (the issuing identity establishes *who asserts this version under
what key*, which the coordinate alone does not), and the ratchet's merge-base source of truth.

It pushed back on two things, and both are corrected above: R-9's framing was too narrow, and the
"load-bearing" label on the commit ordering claimed an enforcement CI does not perform.

### Residuals after this change

| # | Residual | Owner |
|---|---|---|
| R-2 `[R]` | `resolved_as_of_fact` stays recorded; whose clock supplies `as_of` is unsettled | 5B-2 |
| R-3 `[G]` | The authority still does not re-enforce `coordinate.content_digest == policy_body_digest` at resolution. Three boundaries now refuse the divergence themselves | Policy Authority |
| R-7 `[G]` | The verified/recorded maps are still written twice — in `verified.py` and in `_mint_verified_artifact`. The promotion required editing both; editing one is caught by the artifact's self-digest as a refusal, so this is a maintenance hazard, not a correctness one | 5B-2 |
| R-8 | Bound extraction — that the candidate's `max_permitted_*` are the bounds the verified body states — is untouched | 5B-2 |
| R-9 `[R]` | **Broadened by the independent design review, and measured.** The first framing asked only about the empty-string global tenant, which read as an edge case. It is not: **nothing anywhere in the tree ties a candidate's *action* tenant to the tenant of the policy it reconciles against.** A candidate describing an action for `tenant-1`, carrying a coordinate for a `TENANT`-scoped policy belonging to `tenant-elsewhere`, verifies `VERIFIED` `[V]` — gate 11 compares the candidate's coordinate against the *resolved* policy, and that policy is genuinely the other tenant's. Phase 5A does not compare them either. Inert today because no composition root calls `verify()`, which is exactly why it must be ruled on **before** 5B-2 wires one rather than discovered while wiring it. Pinned as executable behaviour by `test_a_candidate_reconciles_against_another_tenants_policy`, which measures today's permissive behaviour without endorsing it | Owner, before 5B-2 |
| R-10 `[G]` | Two Phase 5A suite weaknesses found while implementing, both pre-existing: `test_non_reachability.py` strips docstrings with `ast.get_docstring`, whose dedented result does not match the indented source, so an indented docstring naming a forbidden symbol trips the scan; and `test_phase5a_invariants.py::test_no_phase_5a_source_file_was_modified` reads `git status`, so it measures a clean working tree rather than an unmodified package | Phase 5A |
| R-11 `[G]` | The floor claim holds only for digest-covered bindings, and nothing enforces that a future in-candidate binding is digest-covered: the completeness test enumerates dataclass fields, so a coordinate added as a derived property or side table would escape it while appearing to bind | Phase 5A |
| A-59 (5B-0A) | The producer attestation binds the recommendation, not the candidate. Reconciling the policy does not reconcile the producer's signature to this candidate | 5B-2 |

## The residual ratification round, and what this session verified of it

A third independent session ruled on the three residual decisions this record left open, and
re-measured before ruling. Every load-bearing citation in that ruling was checked against the
repository here rather than accepted; all of them hold. What follows separates what is now
**measured** from what still **awaits the owner**, because the two are not the same and one of
these rulings is not a model's to make.

### R-9 — the rule the ruling found is not a new one `[V]`

The ruling's decisive finding is that the scope-guarded comparison R-9 asks for **already
exists in this repository, ratified, in exactly the shape that avoids the trap**:

```python
if ref.scope is PolicyScope.TENANT and ref.tenant_id != self.tenant_id:
    raise PolicyContractError(f"cross-tenant policy binding: ...")
```

— `uvi-policy-contracts/.../contracts/context.py:118`, and again at `:223` inside
`bind_policies` `[V]`. Guarding on `scope is TENANT` is what lets the authority's empty-string
global tenant pass untouched, which is why a bare equality would have been wrong and this is
not. So R-9 is not "invent a cross-tenant rule"; it is "**Phase 5A and 5B-0B do not carry a
rule the rest of the tree already does**". That reframing is the round's real contribution.

Two inputs the ruling says a repair would need are already present: V2 carries `policy_scope`
and `policy_tenant_id` (`target.py:498`, `:501`) `[V]`, and the builder already reads
`facts.tenant_id` a few lines above the existing cross-check `[V]`. A refusal changes what is
constructible, not what is hashed, so no digest moves.

The ruling's second half — that the obligation is **not** the composition root's, because
nothing outside the package imports the verifier today `[V]`, so an obligation placed there
would be unenforceable and untestable — follows from that measurement and is sound.

**Still `[R]`.** Whether a `TENANT`-scoped policy may bound only its own tenant's action is
product intent. A fresh session can establish, as this one did, that the rest of the tree
already answers yes; it cannot rule that Cloud Scaling must. The owner's word closes R-9.

### D-5B1-3 — the widening, measured against a stronger attack `[V]`

The ruling reproduced the free ride the third rule closes, and chose a worse fact to move than
this session did: reverting to the two-rule wording and promoting **`resolved_as_of_fact`** —
R-2, the injected and unvalidated clock — with only `candidate_digest_fact` disclosed goes
green at **282 passed** `[V]`. The changelog does not merely fail to mention it; it
*affirmatively states* that the fact stays recorded, so a mention-anywhere narrowing is not
available either. Rule 3 restored against that same tree fails as the sole guard.

That measurement settles the factual question the `[R]` above turns on: the two-rule wording
was underspecified, not a ceiling. **Still `[R]` for one reason only** — whether a gate may
exceed its ratified wording is a governance call, and the session that widened it and the
session that endorsed the widening are both models. The owner's word discharges it.

One limit is recorded rather than repaired `[G]`: rule 3 forces a promotion to be *disclosed*;
it cannot make the disclosure *true*. That is the correct ceiling for a changelog gate.

### R-11 — settled on evidence, and cheaper to exploit than the ratchet was `[V]`

Reproduced independently here at `a2884dae`, in a scratch worktree since removed. Adding one
per-instance, semantically load-bearing property to `CapacityAuthorizationCandidate` outside
`digest_payload()`:

```
tests=277  failures=0  errors=0  skipped=0     — one source file touched, zero test edits
```

The ratchet's free ride cost six edits; this costs none. The class already carries two
non-field properties, `trust_state` and `grants_authority` (`candidate.py:275`, `:285`) `[V]`,
both constants — so today's surface is benign, but benign by accident: adding a property is
established practice here, and `test_digest_completeness.py:106` enumerates
`__dataclass_fields__`, which a property is not `[V]`.

This one is a fact about the repository, not a judgment call, so it needs no further
ratification. **R-11 is settled: required, in 5B-2** — the completeness test enumerates the
public attribute surface (fields, properties, `cached_property`) against `digest_payload()`,
carrying a frozen allowlist naming exactly the two exempt properties and why, pinned the way
`FROZEN_FIELD_EXCLUSIONS` is at `test_digest_completeness.py:57`. D-5B1-1's floor claim loses
its "for a binding that is actually bound" qualifier once it lands — which it now has.

### Where the three now stand

| Decision | Status |
|---|---|
| R-9 | **Ruled and closed in 5B-2** `[V]` — a `TENANT`-scoped policy bounds only its own tenant's action; `GLOBAL` bounds any |
| D-5B1-3 widening | **Ratified as-is** `[V]` — restated above as three rules, `[R]` discharged |
| R-11 | **Closed in 5B-2** `[V]` — completeness enumerates the public attribute surface |

## Phase 5B-2 part 1 — what closing them actually took

The owner ruled all three, and the two that were `[R]` were ruled on grounds no session could
supply: that Cloud Scaling has no managed-service-provider or parent/child tenancy case, and
that a gate may exceed its ratified wording when it implements that wording's intent.

**R-9 needed two sites, not one.** Phase 5A's builder refuses to construct the pairing; gate 12
refuses one that arrived anyway. The second is not belt-and-braces: a candidate is shape- and
digest-validated by its type but carries **no cross-field policy guard there**, so an internally
consistent cross-tenant candidate can exist without the builder ever having produced one. The
suite constructs exactly that, and with gate 12 neutralised it verifies `VERIFIED` `[V]` — the
residual reproduced at the boundary rather than argued about. Both sites key on the scope, and
the `GLOBAL` carve-out is pinned on both, because a bare equality would refuse every global
policy in the platform. No digest moves: a refusal changes what is constructible, not what is
hashed `[V]`.

**R-11 took three attempts, and the first two were the same mistake.** The first compared two
candidates and asserted the exempt values agreed — and passed against a planted property
reading `self.tenant_id`, because the fixtures happened to differ only in `account_id` `[V]`.
The second read each exempt property's source and refused one touching `self`. Both are
*source classification*, and "derives from instance state" is a semantic property: every
syntactic approximation has a bypass class. A renamed receiver, a helper delegate, `getattr`,
a custom descriptor and a class-attached attribute all walk through a scan for the literal name
`self`, and broadening the scan only moves the boundary.

**The ruled correction abandons classification.** Enumeration became total over *names* —
static, via `inspect.getmembers_static` (falling back to `dir()` plus
`inspect.getattr_static`), so it never executes a descriptor and a member that raised on
access cannot hide by breaking enumeration. Whatever a member is implemented as, it must be
named. Methods are included: pinning the public surface is the point, and a binding smuggled
in as a zero-argument method would otherwise be exempt by category.

**R-11's claim, stated precisely.** *Every public attribute declared on
`CapacityAuthorizationCandidate` or inherited through its MRO is either a dataclass field
covered by `digest_payload()` or an explicitly named non-field surface member. The allowlist
cannot grow without a disclosed, reviewed change.* It does **not** claim coverage of every
attribute an instance could ever expose: the class is a frozen dataclass without `__slots__`,
so `object.__setattr__` can staple an attribute onto a live instance, and no static check sees
that `[G]`.

`trust_state` and `grants_authority` stay properties rather than becoming digest-covered
fields. A read-only property cannot be forged by `object.__setattr__` on a frozen dataclass and
a field can, so converting them would trade a completeness hole for a forgery one — which is
why "eliminate instance-derived exemptions entirely" was the wrong correction.

**Two protections, measured separately, because they are not the same protection** `[V]`:

| Attacker path | Outcome | Refused by |
|---|---|---|
| Plant the attribute only — *accidental drift* | **Refused** | `test_digest_completeness.py` |
| Plant it and exempt it, silently | **Refused** | `test_surface_ratchet.py` |
| Plant it, exempt it, **and disclose it** | **Bypassed** | nothing — by design |

The third row is not a defect and is recorded rather than repaired. No test in this tree can
close it: tests and production code share one trust domain, so a contributor editing both is
indistinguishable from a contributor doing the right thing. What the ratchet buys is what it
bought the partition — the baseline lives in history and cannot be edited by the commit that
changes the current state, so widening becomes a **disclosed** event rather than a silent one.
It cannot make the disclosure true. That is the identical `[G]` D-5B1-3's third rule carries.

The five bypass constructs are now parametrised acceptance tests over the enumerator rather
than a one-off audit, so the redesign's argument is a measurement that reruns.

That is the second time in this ADR's history that a guard written to close a residual was
itself hollow on the first attempt, and the second time an end-to-end negative control was what
exposed it. The pattern is worth naming: a guard is not evidence until something has been driven
through it and observed to fail.

### Residuals after 5B-2 part 1

R-9 and R-11 are closed. **R-2** (whose clock supplies `as_of`), **R-3**, **R-7**, **R-8**,
**R-10** and **A-59** are untouched and out of scope for part 1.
