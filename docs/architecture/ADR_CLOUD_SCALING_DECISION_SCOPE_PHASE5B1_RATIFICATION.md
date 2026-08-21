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
candidate enters `digest_payload()`, so no in-candidate binding can move zero `[V]`. Removing
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
working tree, and fail when membership changed and the profile version did not, or when the
version changed without a changelog entry naming it. It runs in the package's CI and as a test
that skips only where there is no checkout, matching the existing `_find_repo_root` convention.

**Ordering, and it is load-bearing:** the ratchet lands and is proven — a negative control that
performs the promotion without the bump and observes the failure — *before* `candidate_digest_fact`
is promoted. Building the guard after the first promotion would leave the one event it exists to
catch untested.

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
| Producer-attestation suite | **440 passed**, 0 failed, 3 skipped (no built dist in the tree; pre-existing) |
| Policy-authenticity suite | 259 → **282 passed**, 0 failed, 0 skipped |
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

### Residuals after this change

| # | Residual | Owner |
|---|---|---|
| R-2 `[R]` | `resolved_as_of_fact` stays recorded; whose clock supplies `as_of` is unsettled | 5B-2 |
| R-3 `[G]` | The authority still does not re-enforce `coordinate.content_digest == policy_body_digest` at resolution. Three boundaries now refuse the divergence themselves | Policy Authority |
| R-7 `[G]` | The verified/recorded maps are still written twice — in `verified.py` and in `_mint_verified_artifact`. The promotion required editing both; editing one is caught by the artifact's self-digest as a refusal, so this is a maintenance hazard, not a correctness one | 5B-2 |
| R-8 | Bound extraction — that the candidate's `max_permitted_*` are the bounds the verified body states — is untouched | 5B-2 |
| R-9 `[R]` | Whether a candidate's tenant must equal its policy coordinate's tenant component, given that a global-scope policy carries the empty tenant | Owner / 5B-2 |
| R-10 `[G]` | Two Phase 5A suite weaknesses found while implementing, both pre-existing: `test_non_reachability.py` strips docstrings with `ast.get_docstring`, whose dedented result does not match the indented source, so an indented docstring naming a forbidden symbol trips the scan; and `test_phase5a_invariants.py::test_no_phase_5a_source_file_was_modified` reads `git status`, so it measures a clean working tree rather than an unmodified package | Phase 5A |
| A-59 (5B-0A) | The producer attestation binds the recommendation, not the candidate. Reconciling the policy does not reconcile the producer's signature to this candidate | 5B-2 |
