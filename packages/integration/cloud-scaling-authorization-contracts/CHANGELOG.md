# Changelog — ugence-cloud-scaling-authorization-contracts

## [0.8.0] — ExecutionTargetScope schema 2: the cross-cloud vocabulary (ETS-1 … ETS-16)

**A versioned breaking change with no compatibility path, by ruling.** Schema 1 payloads
are refused with `UNSUPPORTED_SCHEMA_VERSION` and never inferred or upgraded (ETS-9).

### Why

`account_id` already carried an AWS account number, a GCP project and an Azure
subscription — undocumented, and indistinguishable. Nothing in the chain said which cloud
a value belonged to, so two clouds' identifiers could collide as strings, and an Azure
target was not addressable at all: an ARM resource id needs a subscription *and* a
resource group, and the scope carried nowhere to put the second.

### Contract

* **`cloud_provider`**, required, validated against a closed vocabulary
  `{"aws", "gcp", "azure", "self-hosted"}` exported as `CANONICAL_CLOUD_PROVIDERS`.
  `(cloud_provider, account_id)` is the governed account identity; neither half suffices
  alone. Canonical string form and pair semantics only — per-provider grammar (12-digit
  AWS, GCP project rules, Azure GUID) belongs to governed adapters, not here (ETS-11).
* **`resource_group`**, required when the provider is `azure`, required to be `None`
  otherwise (ETS-4, ETS-12). Must-be-absent rather than merely optional: canonicalization
  retains nulls, so a stray value would sit inside the digest as dead data, and a
  digest-bound field nothing reads is a substitution surface.
* Three typed reasons: `UNSUPPORTED_CLOUD_PROVIDER`, `MISSING_RESOURCE_GROUP_BINDING`,
  `RESOURCE_GROUP_NOT_APPLICABLE`. The last two are separate members because they are
  opposite failures and a reader triaging one must not be handed the other.

### Two limits, stated rather than implied

**Both new fields are scope-only and reconciled against nothing.** `CapacitySubject` stays
provider-neutral (ETS-8), so there is no projected fact to reconcile against — the shape
ETS-6 ratified for `namespace`. Their protection is the digest binding and `account_id`'s
presence gate, nothing more. A scope naming the wrong provider is caught only if the
digest it is bound into is checked.

**The implemented Azure rule is narrower than ETS-4's words.** ETS-4 scopes the
requirement to "resource-level scaling targets", but the scope carries no field
distinguishing one, and adding a discriminator was not ratified. The enforceable rule is
therefore provider-conditional: `cloud_provider == "azure"` requires a resource group,
every other provider forbids one. A narrower rule needs a discriminator and a further
ruling.

**`cloud_provider` keeps its name although `self-hosted` is not a cloud.** ETS-10 admitted
the token so a Kubernetes target belonging to no cloud is buildable; renaming the field was
not ratified and would be a second breaking change.

### Digests moved

| digest | from | to |
|---|---|---|
| `FROZEN_TARGET_SCOPE_DIGEST` | `b97f41c9…` | `1e9ebadf…` |
| `FROZEN_POLICY_BINDING_DIGEST` | `8961f6b2…` | `29ca00f9…` |
| `FROZEN_POLICY_COORDINATE_BINDING_DIGEST` | `ad1d1ad9…` | `4a83019d…` |
| `FROZEN_CANDIDATE_DIGEST` | `357bb3d4…` | `bbcd4ad7…` |

Only the scope's own field set changed; the binding, the coordinate and the candidate
moved *beneath* it because each covers a digest that moved. **The coordinate was not in
the ETS audit's predicted cascade** — that traced scope → binding → candidate, and the V2
coordinate binds the scope independently. It was found by measurement.

Unmoved, and asserted so: recommendation, context, subject, request, idempotency,
decision, and producer-signing-payload. That is the evidence schema 2 reached no Phase 4
contract. Each superseded value is pinned as a negative anchor.

### Guard inventory

The ratified counts moved and were **re-ratified, not silently re-pinned** (ETS-15):
total 114 → 118, peripheral 28 → 31. The peripheral inventory is renamed
`peripheral-attestation-target` (ETS-16) because a label encoding its own value goes stale
the moment the value moves.

Three of the four new guards fall inside the recorded peripheral shape; the fourth, the
`cloud_provider == "azure"` conditional itself, does not — which is why the two ratified
numbers moved by different amounts and were ratified separately.

`tests/test_peripheral_guard_sweep.py` pins six guards by index, and the insertions
shifted them. Re-derived by matching each old guard's identity **including its rank among
identically-worded conditions**: `type(value) is not int or value < 0` occurs twice, and a
first-match re-derivation moved `P_BINDING_CEILING_TYPE` from 28 to 10 — a different
guard, in a different class, which would then have been silently neutralised while the
suite stayed green.

### Fixtures

`"acct-000123456789"` was valid under no cloud at all, so no fixture exercised what a real
account identifier looks like on any provider. Now synthetic but format-realistic
(ETS-13): a reserved-range 12-digit AWS account, a project-number-shaped GCP value, a
nil-adjacent Azure subscription GUID with a resource group, and a local authority for
self-hosted. No fixture carries a real customer or cloud account identifier.

### Authority exclusion

`CANONICAL_CLOUD_PROVIDERS` collided with the guard forbidding any public export naming
`provider` — meaning an *authority* provider. A cloud-provider label is the opposite
category: descriptive, carried in a scope that grants and performs nothing. The exemption
is by exact name and is itself guarded — a new test asserts every exempted name is a
non-callable string or frozenset of strings, so a port or factory under a `CLOUD_PROVIDER`
spelling still fails.


## [Unreleased] — the enforcement was inert, and two more exclusions were false

*No version bump and no production behaviour change.* A final audit found five
merge-blocking defects. All five are corrected here; the two that touch this package are
below, and the rest are in ADR Phase 5 §9 and the sweep.

### §9.1's message rule was never enforced

The sweep refuses to score a kill whose only failing assertion read a message. That check
never fired. It read `item.repr_failure(...)`, which renders under the configured tbstyle,
and the sweep runs pytest with `--tb=no` — under which what comes back is pytest's rewritten
*explanation*, never the source. No message idiom appears literally in
`where 'actual' = str(Boom('actual'))`, so nothing matched and `killed_only_by_message` was
False for every mutant in both packages, for this PR's whole history.

Three defects, one behind the other:

| defect | correction |
|---|---|
| the detector read a tbstyle-rendered explanation | it reads `excinfo.traceback[-1].statement`, which is source and ignores tbstyle, so `--tb=no` keeps its log-size benefit |
| it scored the whole displayed frame, so one `pytest.raises` anywhere above suppressed every finding below | it scores the **failing statement alone** — which is the case the rule exists for: the type assertion passed, the message assertion is what failed |
| its vocabulary was `.detail` and `str(excinfo.value)`; this package writes neither | the vocabulary is `str(<name>.value)`, `.detail` and `.args[`, and a test measures it against what both suites actually write — 48 message assertions here, all `str(exc.value)` |

`scripts/cloud_scaling/tests/` runs the **generated plugin itself** against a suite built to
fail in each shape: a plain message assertion, one inside a helper, a parameterised one, one
adjacent to a *passing* outcome assertion, a `.detail` read, and three negative controls.
Both packages' CI runs it.

### Guard 10 is scored, not unreachable

`identifiers.py:100` was excluded as `unreachable-behind-earlier-guard`: Phase 4C's
import-time check answers first. It does — in this installation. That check lives in
`ugence-cloud-scaling-risk-integration`, a separate distribution under `>=0.1.0`, so "which
guard fires first" is a fact about the resolution installed, not about the program.

Measured against a 0.2.0 that no longer refuses there, paired with a controller ratifying a
fifth `ActionKind`:

| | result |
|---|---|
| undrifted | imports; both vocabularies agree |
| drifted, guard present | `ImportError` — *Phase 5A fails closed* |
| drifted, guard neutralised | imports, binding four action types against a controller ratifying five |

**The split is 111 `SCORED` / 3 `EXCLUDED`, not 110 / 4.** The inventory is still 114.


## [Unreleased] — guard 9 is scored, not unscorable

*No version bump and no production behaviour change.* The exclusion vocabulary's newest
reason, `unscorable-by-single-checkout-fixture`, was applied to a guard that is scorable.

Guard 9 (`identifiers.py:93`, `ours != theirs`) compares this package's ratified
identifiers against Phase 4C's, which arrive from a separately-versioned distribution
under an open-ended `ugence-cloud-scaling-risk-integration>=0.1.0` pin. The exclusion
reasoned that the sweep fixture installs exactly one resolution and so cannot make the
condition true. That is true of the fixture and irrelevant to the guard: a test is free to
construct a second resolution, and a pin admitting any version at or above 0.1.0 admits a
0.2.0 that renames a ratified identifier.

So the test builds one — from the real Phase 4C source, not a stub, with the version
bumped and `PURPOSE_CAPACITY_ACTION` renamed — and places it first on `PYTHONPATH`, where
it *is* the installed Phase 4C. Under it:

| | guard present | guard removed |
|---|---|---|
| drifted resolution | `ImportError`, naming the drifted identifier | imports cleanly |

Removed, Phase 5A binds `cloud_scaling.capacity_action` into every candidate digest while
Phase 4C ratifies `cloud_scaling.capacity_action.v2` — the identifier substitution the
module docstring says fails closed. A refusal versus no refusal is a change to the typed
refusal under §9.1, so the guard is authority-bearing, and the sweep kills it against the
full suite.

**The split is 110 `SCORED` / 4 `EXCLUDED`, not 109 / 5.** The inventory is still 114.

The reason itself stands — two Phase 5B identifier guards still carry it — but it now has
a bar to clear. "The fixture installs one resolution" is not a reason; "no second
resolution the pin admits makes this condition true" is, and it has to be measured. The
in-tree drift test that previously carried guard 9's exclusion said all three import-time
guards were equivalent mutants because their conditions are False in this tree. For guard
11, whose operands are two frozen literals in this distribution, that argument holds. For
guard 9 it never did: agreement under one resolution says nothing about the others.

## [Unreleased] — 114 guards, and the carve-out that hid an untested one

*No version bump and no production behaviour change.* An independent adversarial
audit of the sweep found two of this package's definitions wrong. Both are corrected
by measurement rather than by argument.

### The conversion carve-out is withdrawn

§9.1 excluded an `if` whose body *binds* a raising helper's result, on the stated
grounds that neutralising it produces no refusal to compare and changes what the suite
can collect. For the single site it excluded — `attestation.py:261`,
`if isinstance(issued_at, str): issued_at = _parse_ts(issued_at)` — all three claims
are false. Neutralised, it produces a typed `MALFORMED_CANONICAL_FIELD` refusal, the
collected population is identical, and the mutant survives the entire suite.

The carve-out was not describing a conversion. It was reasoning added to explain away
an `UNSCORED` result, and it hid a line nothing executed: no test built an attestation
from a canonical wire mapping, so the parse that lets `issued_at` cross the wire as a
string and arrive as a `datetime` had never run. That round trip — serialize, transmit,
rebuild — is what a real consumer does, and it now has a test.

### Conditional expressions that select an outcome are decision points

Four sites choose between two `AuthorizationCandidateRejectionReason` members with a
ternary: `FORGED_TRUST_STATE` vs `UNKNOWN_FIELD` in three deserializers, and
`MISSING_ACCOUNT_BINDING` vs `MALFORMED_CANONICAL_FIELD` in a fifth. §9.1 makes the
reason the contract, so these decide it as surely as any `if` — but an `ast.If`-only
shape rule cannot see them, and `if False:` cannot reach them.

They get a second operator: collapse the conditional to its `else` branch, which is the
more permissive half and therefore exactly the defect the guard prevents. All four are
killed by assertions that already existed, which is the point — they were load-bearing
and unmeasured, not untested.

**The inventory is 114, not 109.** The recorded 65 + 28 are unchanged and still
reconcile, because both are defined over a narrower shape than this inventory.

## [Unreleased] — the definitions the sweep rests on, ratified

*No version bump and no production behaviour change.* An independent adversarial audit of
the first sweep found that its two load-bearing definitions were being decided case by case
inside a script. Both are now ratified in ADR Phase 5 §9, and the classification is redone
under them.

### Ratified

- **The typed refusal is `(exception class, AuthorizationCandidateRejectionReason)`.** The
  message is prose: no consumer may branch on it and no test may assert it. A guard is
  authority-bearing when removing it changes that pair for some constructible input —
  including changing it to no refusal at all. Every coverage test now asserts the reason
  rather than a message substring.
- **`equivalent-mutant` may not be claimed across a distribution boundary.** A guard
  comparing against a value from a separately-versioned distribution admitted by an
  open-ended pin can be true under a resolution that pin permits, so its falsity is a
  property of the installation and not of the program.

### Fixed

- Guards 65 and 81 are `diagnostic-only`, not scored. Each is a strict subset of the guard
  behind it, which carries the *same* reason — `None` ⊂ `not isinstance(..., Mapping)` and
  `None` ⊂ `not isinstance(..., datetime)`. They were only ever killed by an assertion on
  the message, which the ratification says is not the contract.
- Guard 9's `equivalent-mutant` claim is withdrawn: it compares against Phase 4C across an
  open-ended `>=0.1.0` pin. Reclassified `unscorable-by-single-checkout-fixture`.
- Guard 10's reason is corrected to `unreachable-behind-earlier-guard`, with evidence that
  measures unreachability rather than falsity: a subprocess drifts the controller's enum and
  reads which guard's `ImportError` comes back. It is Phase 4C's, every time.
- Guards 50 and 75 survived once the tests stopped asserting messages — and were then shown
  to be authority-bearing after all, by sharper attacks. Both are scored, and
  `GUARD_SWEEP.md` records why the first attacks missed.

### Fixed — the sweep engine

- **A red baseline is refused.** This is the one that mattered: the copy was named
  `package`, Phase 5B's suite asserts its own directory name, and that test therefore failed
  in *every* run of that package's sweep. Since a mutant counted as killed whenever any test
  failed, **all 115 Phase 5B guards were reported killed regardless of the mutation.** The
  copy now keeps the package's directory name, the baseline must be green, and a kill counts
  only failures the baseline did not already have.
- An `if` whose body *binds* the result of a raising helper is a conversion, not a guard,
  and is not inventoried; an `if` whose body *calls* one is. That adds `verification.py:327`
  and `verified.py:488` to Phase 5B, which a raise-only reading missed.
- An exclusion whose `(module, condition)` key matches more than one guard is refused rather
  than silently applied to all of them — `target.py` carries three guards reading exactly
  `not isinstance(data, Mapping)`.
- A guard the sweep could not score is a blocking failure, not a line in a report.
- "eleven real Phase 5B gates" was written from the gates this work had touched rather than
  counted. The report computes the figure now; at this commit it is 47 of 117.

## [Unreleased] — the sweep is measured, and every guard is classified

*No version bump.* No production behaviour changes here: this is coverage, classification
and the CI that enforces both.

The first complete CI mutation sweep of this package neutralised all **109** authority-
bearing guards and ran the whole suite against each. **78 died; 31 survived.** A survivor
is not a guard the suite tests weakly — it is a guard the suite never reached, so removing
it changed nothing any test could see.

### Added

- `tests/test_guard_coverage.py` — 31 tests reaching 28 of the 31 survivors through the
  public surface each defends. Each asserts the specific typed refusal that guard alone
  produces, so a test that merely observed "something was refused" cannot stand in for it.
- `guard_classification.json` (generated, tracked) — every one of the 109 guards
  classified `SCORED` or `EXCLUDED`. Exclusions are declared in the engine, keyed by
  `(module, condition)` rather than by line so a shifted line cannot silently re-point one
  at a different guard, and each must name a reason from a closed four-item vocabulary and
  a test that measures the reason.
- Six blocking CI conditions on the aggregate: inventory drift, an unclassified guard, an
  invalid or orphaned exclusion, a `SCORED` guard that survived, an `EXCLUDED` guard that
  was in fact killed, a missing shard, a duplicated result, and a shard that collected a
  different population.
- The test-time half of the D-4 drift assertion (ADR Phase 5 §9), which was missing.
  Import-time alone is green in any process that imports a stale wheel.

### Measured

- Of the 28 newly-covered guards, **7 ADMIT their attack outright** when removed — the
  boundary produces no refusal at all — **5 fail closed through an untyped `AttributeError`
  or `KeyError`**, and 16 refuse with another guard's reason. `GUARD_SWEEP.md` records
  which is which, per guard, with the mutant's actual output.
- Three classifications in the earlier 49-guard `GUARD_SWEEP.md` are refuted. All three
  rest on attacks routed through the candidate builder; `reconcile_phase4` is exported in
  `__all__` and is a public entry point of its own, and on that path two of the three
  guards admit their attack with no refusal. The document is corrected in place rather
  than deleted.
- Guards 9, 10 and 11 (`identifiers.py`) are `EXCLUDED` as equivalent mutants: each
  compares two frozen constants that are equal in-tree, so `if False:` is the same program
  on every path. The claim is not asserted — a test measures that each condition is False,
  and the exclusion is void the moment it stops being.

## [Unreleased] — every value is admitted before it is compared

*No version bump.* `cloud-scaling-policy-authenticity` pins Phase 5A's version literal in
`test_phase_5a_is_at_the_version_5b1_moved_it_to`, and moving it would drag a second
package into a change that ratified none. The pin did its job — it caught the bump — and
the version moves when the owner rules on it, not as a side effect of a CHANGELOG heading.


`0.7.0` applied the exact-type doctrine to `datetime` and `int`. It never applied it to
`str`, which carries every digest and identifier in this package, and it never asked
whether a value reaching a comparison had been admitted *at all*. Both gaps were live.

### Fixed

- `canonical.py`'s three admissions (`is_canonical_digest`, `is_policy_authority_digest`,
  `require_nfc_text`) require `type(value) is str`. A subclass lying only in `__ne__` —
  `__eq__` left honest, so it clears the empty check and the NFC comparison — defeated
  every identity guard that decides with `!=`, with the carried digests byte-identical to
  the honest ones.
- `PolicyTargetBindingReference`'s two ceilings are admitted exactly. They are the only
  bound a request is enforced against, and `>` hands a subclass operand priority through
  its reflected `__lt__`.
- Values that reached a comparison without passing through any admission now pass through
  one first: `decision_snapshot`'s `tenant_id` and `domain`, the decision's own
  `tenant_id`, `idempotency_key`, `request_digest` and `subject_digest`, and the bound
  `expires_at` consumed by canonical guard 40.
- Every public Phase 5A artifact admits its `schema_version` as an exact plain string
  before comparing it. Two admitted an arbitrary identifier outright; three were caught
  only by a later digest binding computed over the honest constant.

### Changed — intentional narrowing of diagnosis precedence

**This is a deliberate behavioural change, not an accident of the repairs above.** For
the `decision.*` values above **and for `projection.tenant_id`**, the refusal a caller
receives now depends on which of two things is wrong:

| Input | Refusal |
|---|---|
| malformed or non-canonical (wrong type, bad shape) | `MALFORMED_CANONICAL_FIELD` — a canonical/identifier refusal |
| well-formed but unequal | the existing semantic mismatch (`TENANT_MISMATCH`, `IDEMPOTENCY_KEY_MISMATCH`, `REQUEST_DIGEST_MISMATCH`, `SUBJECT_MISMATCH`, `DECISION_INSTANT_NOT_BOUND`) |

A malformed value no longer receives a semantic mismatch reason, because the comparison
that would diagnose the mismatch is exactly the comparison a malformed value can subvert.
The semantic reasons are **not** restored for malformed inputs. Both branches are pinned
in the suite — A-52 and
`test_a_lying_bound_expiry_is_refused_before_guard_40_compares_it` each assert the honest
mismatch keeps its own reason and the malformed one does not inherit it — so a later
change cannot quietly widen either branch.

Admission is placed *after* any emptiness guard that owns its own typed diagnosis, so a
missing `idempotency_key` is still reported as missing rather than as malformed.

The tenant comparison admits **both** operands. An earlier revision admitted only the
decision's, which left `projection.tenant_id` values that `require_canonical_identifier`
itself refuses — `12345`, `b"acme-tenant"`, an embedded newline or tab, the empty string —
reaching the comparison and being answered with `TENANT_MISMATCH`: a semantic diagnosis of
a malformed input, and the same answer an honest foreign tenant receives. Both directions
are pinned in A-54.

### Coverage

`target.py` and `attestation.py` carry 28 guards no sweep executed. They are now
inventoried separately from the owner-ratified 65, with distinct entry points. **6 of 28
are neutralised and scored.** No exhaustive coverage is claimed anywhere, and the measured
figure is asserted in the suite so it cannot drift silently.

## [0.7.0] — canonical values only: the temporal guards refuse live objects

`0.6.0` fixed *how* the orderings compare and left *what* they accept. `_bound_instant` had an
`isinstance(value, datetime)` branch, so a `decision_snapshot` could carry a live object
instead of a canonical string.

That is not cosmetic. `to_canonical_obj` renders a `datetime` to exactly the string it would
have been, so **the digest cannot distinguish the two** — `_bind`, `digest_of_snapshot` and the
candidate payload are all blind to it. A `datetime` subclass overriding `__gt__` therefore
carried a valid `decision_digest` and satisfied both orderings by fiat, admitting an evaluation
stamped in year 999. The type is the only place the distinction survives.

### Fixed

- `_bound_instant` requires `type(value) is str`. A snapshot is a canonical artifact — a
  mapping of primitives the authority's digest covers — so a live object inside one is a
  refusal, not an input to trust.
- `_comparable_instant` uses `type(value) is not datetime`, matching the exact-type doctrine
  `reconcile_phase4` already applies to the projection and the decision.

### Removed

- The awareness check inside `_bound_instant`. With only canonical strings admitted, the parse
  is the sole thing that sets `tzinfo`, so the guard was unreachable — and an unreachable guard
  that reads as load-bearing is worse than none.

### Changed

- The `_BOUND_TS_FMT` comment now states the round trip is deliberately partial: `strftime`
  writes three-digit years that `strptime` refuses. The asymmetry fails closed, which is the
  only direction it may fail.
- New negative controls are built **without** `to_canonical_obj`. The `0.5.0` defect survived a
  green suite because every attack value went through the primitive the guards were wrong in.

### Note on the guard inventory

It stays at **65**, not 64: removing the unreachable awareness check and adding the type gate
cancel out. Measured rather than predicted.

## [0.6.0] — R-12b ordering repair: instants, not canonical strings

Found by independent review against `0.5.0`, which was green including the gate-removal sweep.

`0.5.0`'s two new orderings compared canonical strings, claiming the format is "fixed-width,
zero-padded and UTC-normalised". `%Y` is not padded below year 1000, so a three-digit year
sorted above every four-digit one and both orderings inverted: backdating `evaluated_at` by one
year was refused, by a thousand years **admitted**. Since that instant bounds Phase 5B's
occurrence gate, the gate added to bound backdating admitted it without limit.

### Fixed

- `_bound_instant` parses each bound instant and both orderings compare **instants**. Equality
  (the outer-equals-bound gates) stays on strings: string equality is exact, and only *ordering*
  was wrong.
- `snapshot_issued_at` is type-checked. `issued_at = 0` previously reached a raw `>` and escaped
  as a bare `TypeError` — the unclassified-exception failure `_comparable_instant` exists to
  prevent, applied here at last.

### Changed

- Guard inventory 64 → 65; anchors after `_require_datetime` shift by +1.
- The awareness sweep's attack values are no longer built solely through `to_canonical_obj`,
  which is why the original defect was invisible to a green suite.

### Known asymmetry, recorded

`strptime`'s `%Y` requires four digits, so the canonical writer can emit a sub-1000 year the
reader refuses as non-canonical. Four-digit backdates lose on ordering; sub-1000 ones lose on
parsing. Both closed, and the asymmetry fails closed.

## [0.5.0] — Cloud Scaling R-12b: the decision instants come from the bound snapshot

R-12 re-sourced the three *subject* instants from the digest-bound context and stopped there.
The decision instants have the same shape and were never asked the same question. They failed
it, and unlike R-12's subject-ordering guard this one was **live**.

**Breaking**, pre-1.0, and unlike every release below it this one **moves digests**: a decision
snapshot minted before `ugence-risk-authority` `0.5.0` is refused, and two frozen values moved.

### The defect

`SubjectRiskDecision.evaluated_at` is an outer field. `decision_digest` covers
`decision_snapshot`, and that snapshot carried `issued_at` and `expires_at` but **no
`evaluated_at` at all**. Measured: `dataclasses.replace(decision, evaluated_at=… - 3650 days)`
— a public construction — succeeded with the digest unchanged, and the candidate carried the
backdated value.

Not inert. Phase 5B's occurrence gate refuses a determination whose `as_of` precedes an instant
the candidate says already happened, so moving this one earlier **widens what that gate admits**.

### Added

- Seven reconciliation guards (inventory 57 → 64): the snapshot must carry `evaluated_at`,
  `expires_at` and `issued_at`; each outer field must equal its bound value; and two orderings
  over the bound instants — the decision cannot have been evaluated before the recommendation it
  decides became valid, nor issued before the evaluation it binds was made. Equality legal, no
  tolerance window.
- Rejection reason `DECISION_INSTANT_NOT_BOUND`. Its own member, not `DECISION_DIGEST_MISMATCH`:
  the digest is intact and the snapshot is exactly what the authority bound; what is wrong is
  the *source* of a carried value. Named for binding, never authenticity — Phase 5A verifies no
  signature, and `test_no_rejection_reason_asserts_authenticity` caught this member under its
  first name.

### Changed

- **Both decision instants are sourced from `decision_snapshot`.** A snapshot with no
  `evaluated_at` is refused rather than fallen back from; a fallback would silently restore the
  unauthenticated path for exactly the artifacts that need it closed. The outer fields are kept
  as *validated projections*, compared through `to_canonical_obj` so no second timestamp format
  enters and an aware/naive difference cannot pass as agreement.
- Floor on `ugence-risk-authority` raised to `0.5.0`.
- `FROZEN_DECISION_DIGEST` and `FROZEN_CANDIDATE_DIGEST` moved. The candidate's own field set is
  unchanged — its payload has always covered `decision_digest` and `decision_snapshot_digest`,
  which moved beneath it. Both superseded values are pinned as negative anchors.
- **No schema identifier moves**, on this repository's established rule (the F-2 precedent at
  `candidate.py:68`): identifiers track which fields an artifact carries. The candidate's field
  set is unchanged, and `RiskDecision` carries no schema identifier at all.

### Not changed, deliberately

The L-1 timezone-awareness sweep keeps the two decision instants on the *outer* fields. The
snapshot stores instants as canonical UTC strings, so a naive snapshot timestamp is not
representable — and moving those rows would delete live coverage, because `to_canonical_obj`
formats a naive datetime by attaching UTC, so a naive outer value canonicalizes to exactly the
bound string and passes the outer-equals-bound gates. Guard 3 is the only thing refusing it.

## [0.4.0] — Cloud Scaling R-12: temporal coherence among the carried facts

Ratified in `docs/architecture/ADR_CLOUD_SCALING_DECISION_SCOPE_PHASE5B1_RATIFICATION.md`,
owner ruling on R-12. **Breaking**, pre-1.0: a candidate whose carried instants contradict each
other no longer constructs. No digest moves and no schema identifier moves.

**Coherence is not freshness.** These guards read no clock — they compare carried facts against
each other. Freshness stays Phase 5B's, and `test_time_authority.py` still proves no clock is
consulted; only its illustration changed, for the reason below.

### Added

- `TemporalOrderingError` and three reasons — `SUBJECT_TEMPORAL_ORDERING`,
  `DECISION_TEMPORAL_ORDERING`, `ATTESTATION_TEMPORAL_ORDERING`. Separate from
  `PROJECTION_RECONCILIATION_FAILED`: the values reconcile against their sources and are
  individually well-formed; the relationship between them is what fails.
- `decision_evaluated_at <= decision_expires_at`. **A newly ratified candidate-coherence
  invariant, not an upstream one** — the decision's own contract does not bound its ttl. The
  ground is the sibling principle at `risk_authority/domain/controls.py:64`, which refuses a
  control result whose `valid_until` precedes its `evaluated_at`.
- `subject_asserted_at <= attestation_issued_at <= subject_valid_until`. A producer cannot
  attest a recommendation before it exists, and an attestation first issued after it expired
  must not make it usable again. This does not broaden the producer's authority and does not
  close A-59.
- `subject_valid_from <= subject_asserted_at <= subject_valid_until`, mirroring the seam
  contract at `evaluation_contracts.py:880`. **See the finding below: this one cannot fire.**
- `_comparable_instant`, one shared helper. Malformed or naive instants get the package's
  existing `CanonicalFieldError` / `MALFORMED_CANONICAL_FIELD`; the R-12 reasons are reserved
  for well-formed instants in an impossible order.

### Changed

- `test_a_long_expired_decision_still_builds_a_candidate` → `test_a_long_expired_candidate_
  still_builds`. **Correction of an internally impossible fixture, not a relaxation of the
  no-clock invariant.** The old illustration used an attestation stamped 3650 days *before the
  recommendation it attests* — not merely stale but impossible. The property is unchanged and
  now demonstrated with a coherent-but-ancient candidate. The old case is pinned separately as
  an R-12 refusal, so the distinction cannot collapse back.
- `test_the_awareness_gate_is_the_only_thing_refusing_a_naive_timestamp` →
  `..._is_now_sibling_backed_rather_than_solely_attributed`. `_comparable_instant` re-checks
  awareness, so guard 3 is no longer solely attributed. Neither guard was weakened to preserve
  a kill count; correct fail-closed classification is worth more than exclusive attribution.
- Guard inventory 52 → 57.
- The L-1 timezone-awareness sweep attacks the three subject instants on the **context** rather
  than the projection's outer copy, following the corrected source. Guard 3 is no longer
  reachable for them by ordinary construction; it remains so for the two decision instants.

### Correction — reconciliation was reading an unauthenticated copy

The finding first recorded here — that the subject-ordering guard is unreachable defence in
depth — was **wrong**, and wrong in a way that hid a live defect. Corrected 2026-08-24 on two
independent audits, before this version was released.

`CapacityRiskSubjectProjection` carries `valid_from`, `valid_until` and `asserted_at` as an
outer copy of the subject context's three instants. Nothing binds that copy: no digest covers
it, and the projection's `__post_init__` does not order it. `reconcile_phase4` read the outer
copy while reading every sibling placement fact from the context, so a plain
`dataclasses.replace` — a public, `__post_init__`-valid construction — diverged the two, and
both directions were measured:

- `valid_from = asserted_at + 1µs` tripped the ordering guard on a value `context_digest`
  never covered — so the guard *was* reachable;
- widening `valid_until` admitted a producer attestation issued **eight years after** the
  recommendation expired, and recorded a `subject_valid_until_fact` a decade past the
  digest-bound value.

**Fixed** — reconciliation now reads all three from `context.subject_valid_from` /
`subject_valid_until` / `subject_asserted_at`, agreeing with every sibling field. This is a
source-of-truth correction: `CapacityRiskSubjectProjection` is unchanged, no schema moves and
no frozen digest moves.

**Fixed** — the attestation's `recommendation_digest` binding check now runs *before* the
temporal block, so a misbound attestation is always `PRODUCER_ATTESTATION_CONTENT_MISMATCH`
whatever its `issued_at`. Identity precedes coherence.

With the context as the sole source, the subject-ordering guard is unreachable on a ground the
original argument did not name: `validate_subject_binding` **reconstructs** `SubjectContext`
via `from_dict`, re-running `__post_init__` and the seam's own ordering rule. It is kept per
owner ruling as defence in depth, and its status is now measured by neutralising it in the
mutation sweep rather than argued — because it was argued once and the argument was wrong.

The other two guards **are** load-bearing and were demonstrated as such.

## [0.3.0] — Cloud Scaling Phase 5B-2 part 1: R-9

Ratified in `docs/architecture/ADR_CLOUD_SCALING_DECISION_SCOPE_PHASE5B1_RATIFICATION.md`,
owner ruling on the three residual decisions. **Breaking**, pre-1.0: a candidate that was
constructible at `0.2.0` may be refused at `0.3.0`. No schema identifier moves and **no digest
moves** — a refusal changes what is constructible, not what is hashed.

### Added

- `POLICY_SCOPE_TENANT` — the one `policy_scope` value that constrains which tenant a policy
  may bound. A literal rather than an import: this package depends on neither the Policy
  Authority nor the UVI contracts, which is why the coordinate travels as strings at all.
- Rejection reason `CROSS_TENANT_POLICY_BINDING`. Its own member, deliberately not folded into
  `POLICY_COORDINATE_CONTENT_MISMATCH`: the two references agree perfectly and the coordinate
  is bound to this very scope. What is wrong is whose action the policy may bound, which is a
  scope violation rather than a content disagreement.
- A third builder guard in that family (inventory 51 → 52), closing **R-9**: a `TENANT`-scoped
  policy may bound only its own tenant's action. Keyed on the scope, never on a bare tenant
  equality — a `GLOBAL` policy carries the empty tenant, so `!=` alone would refuse every
  global policy in the platform. Mirrors the ratified shape at
  `uvi-policy-contracts/.../contracts/context.py:118` and `:223`.

### Changed

- The commentary at the two-reference cross-check said the coordinate's tenant was not
  compared at all, reasoning from the empty global tenant. That is a correct reason not to
  compare *unconditionally* and not a reason not to compare; it is corrected in place rather
  than deleted, because the reasoning it records is what shaped the guard.

### Tests

- **R-11 closed.** The completeness test enumerated `__dataclass_fields__`, and a property is
  not a field, so a binding could arrive outside the digest while appearing to bind. Measured:
  one per-instance property outside `digest_payload()` left the suite green with zero test
  edits.

  R-11 is now stated precisely: *every public attribute declared on
  `CapacityAuthorizationCandidate` or inherited through its MRO is either a dataclass field
  covered by `digest_payload()` or an explicitly named non-field surface member, and the
  allowlist cannot grow without a disclosed, reviewed change.* It does not claim coverage of
  every attribute an instance could ever expose: the class is a frozen dataclass without
  `__slots__`, so `object.__setattr__` can still staple an attribute onto a live instance, and
  no static check sees that.

  Enumeration is static — `inspect.getmembers_static`, falling back to `dir()` plus
  `inspect.getattr_static` — so it never executes a descriptor, and total over *names*, so it
  asks nothing about how a member is implemented. A first attempt classified instead, reading
  an exempt property's source for the name `self`; that is source classification, and every
  syntactic approximation of "derives from instance state" has a bypass class. The five that
  defeated it — renamed receiver, helper delegate, `getattr`, custom descriptor, inherited or
  class-attached — are now parametrised acceptance tests over the enumerator.

  The allowlist is ratcheted against the merge base (`tests/_surface_ratchet.py`), so it
  cannot grow silently. That closes accidental drift; it does not close a contributor editing
  the class and the allowlist together, which no test in one trust domain can. What it buys is
  that widening becomes disclosed rather than silent — the same residual D-5B1-3's third rule
  carries, recorded rather than repaired.

- The public non-field surface, disclosed in full because nothing was exempt before it existed:
  - surface: digest — a method, computes the canonical digest and stores nothing.
  - surface: digest_payload — a method, returns the payload the digest is taken over.
  - surface: to_canonical_dict — a method, the canonical serialisation.
  - surface: trust_state — constant `PRESENT_BUT_NOT_TRUST_VERIFIED`; a read-only property
    rather than a field so `object.__setattr__` cannot forge it on a frozen dataclass.
  - surface: grants_authority — constant `False`, and no branch in this package returns `True`.
- Suite 277 → 298, 0 failed, 0 skipped. (283 was the count before the enumeration was
  rebuilt: the surface ratchet and the bypass-construct acceptance tests came after.)

## [0.2.0] — Cloud Scaling Phase 5B-1: decision-scope repair

Ratified in `docs/architecture/ADR_CLOUD_SCALING_DECISION_SCOPE_PHASE5B1_RATIFICATION.md`.
**Breaking**, pre-1.0: the candidate gains a required field, its digest moves, and its schema
identifier moves with it.

### Added

- `PolicyTargetBindingReferenceV2` — the complete six-component Policy Authority coordinate
  the bounding policy lives at, plus the framed body digest its issuance signature covers and
  the issuing key, bound to one exact execution target scope. Carried **beside**
  `PolicyTargetBindingReference`, which is unchanged. All six components are required; a
  reference carrying five of them cannot address a policy version (D-5B1-5).
- `CapacityAuthorizationCandidate.policy_coordinate_binding` and
  `policy_coordinate_binding_digest` — **required**, because an optional coordinate would
  leave the residual it closes open by default (D-5B1-1).
- `is_policy_authority_digest` / `require_policy_authority_digest` — the Policy Authority's
  bare 64-hex digest shape, validated separately from Phase 5A's `sha256:`-prefixed one. The
  two namespaces are never interchanged and **no converter exists in either direction**: a
  re-prefixed digest is a digest nobody signed, over a frame nobody hashed (D-5B1-4).
- `POLICY_COORDINATE_COMPONENTS`, `POLICY_TARGET_BINDING_V2_SCHEMA_VERSION`, and three
  rejection reasons — `MISSING_POLICY_COORDINATE_BINDING`,
  `MALFORMED_POLICY_COORDINATE_BINDING`, `POLICY_COORDINATE_CONTENT_MISMATCH`.
- Two builder guards: the candidate's two policy references must agree on `policy_id` and
  `policy_version`, and the coordinate must bind this scope. A candidate could otherwise carry
  a V1 binding for policy A beside a coordinate for policy B — two well-formed halves stating
  a contradiction.

### Changed — digests that moved, and who pins each

- `FROZEN_CANDIDATE_DIGEST`: `sha256:db72ffff…` → `sha256:be06c653…`. Every field of a
  candidate enters its digest payload, so this is the floor: no in-candidate binding moves
  none, and widening the existing binding in place would have moved
  `FROZEN_POLICY_BINDING_DIGEST` as well. Pinned in `tests/test_frozen_digests.py`, in
  `cloud-scaling-producer-attestation` (`tests/test_frozen_digests.py`,
  `tests/test_phase5a_invariants.py`, `tests/data/phase5a_candidate.json`), and re-run by
  `cloud-scaling-policy-authenticity` (`tests/test_phase5a_untouched.py`).
- `FROZEN_VERIFIED_ARTIFACT_DIGEST` in `cloud-scaling-producer-attestation`:
  `sha256:519983d8…` → `sha256:5a2a6648…`. That artifact binds the candidate digest, so it
  moved with it. No source in that distribution changed and its version does not move.
- **New pin** `FROZEN_POLICY_COORDINATE_BINDING_DIGEST`:
  `sha256:ad1d1ad9…`. Eleven frozen digests where there were ten.
- Nothing else moved. The nine other Phase 5A constants, the v2 signing payload and the v2
  attestation are asserted unchanged from both sides of the boundary.
- `AUTHORIZATION_CANDIDATE_SCHEMA_VERSION` → `cloud-scaling-capacity-authorization-candidate-2`.
  A new **field set** is a new schema identifier; the F-2 remediation moved the candidate
  digest without moving this identifier, and correctly so — it changed what the payload
  covered, not which fields the artifact carries.

### Superseded, pinned as negative anchors

- `SUPERSEDED_PRE_5B1_CANDIDATE_DIGEST` — the candidate digest while nothing in a candidate
  could name a policy version. Reproducing it would mean the coordinate had left the payload.

### Still not added

No resolution, no signature verification, no clock, no envelope, no authority. Carrying a
complete coordinate is not resolving it: both policy references still report
`PRESENT_BUT_NOT_TRUST_VERIFIED`, and reconciling the coordinate against a verified policy
proof is `ugence-cloud-scaling-policy-authenticity`'s work, not this package's.

## [0.1.0] — Cloud Scaling Phase 5A

Initial release. Never previously released.

### Added

- `CapacityAuthorizationCandidate` — an immutable, exact-typed, explicitly
  **non-authoritative** reconciled request for future authorization, with a canonical
  schema identifier and a deterministic `sha256:`-prefixed digest binding the whole Phase
  4 chain, the D-4 identifiers, the exact action parameters, the execution target, the
  policy binding and the producer attestation's signing identity.
- `build_capacity_authorization_candidate` — the production entry point. Admits only exact
  types, reconciles Phase 4 in full before constructing anything, and consumes the
  validated values returned by the reconciler rather than re-reading its sources.
- `reconcile_phase4` / `ReconciledPhase4Facts` — independent Phase 4 reconciliation,
  recomputing every digest including `decision_digest` over `decision_snapshot`.
- `ProducerAttestationEvidence` — a required, immutable, non-authoritative evidence
  artifact carrying a producer signature over the recommendation digest, under a dedicated
  producer-signing purpose.
- `ExecutionTargetScope` — new Phase 5 vocabulary carrying the **required** `account_id`
  the frozen Phase 4 subject has no field for, plus the magnitude and delta ceilings.
- `PolicyTargetBindingReference` — a structural reference to the bounding policy, tied to
  one exact target scope by digest.
- `EvidenceTrustState` — a **single-member** vocabulary,
  `PRESENT_BUT_NOT_TRUST_VERIFIED`. There is no verified state to reach.
- `AuthorizationCandidateRejectionReason` and eleven typed errors. Every reason is a
  refusal; there is no success member.

### Deliberately not added

No signature verification, no policy resolution, no decision minting, no envelope, no
ActionGate, no credential, no executor, no clock, no effect verification and no learning.
Phase 5B, 5C, 5X, 5D and Phase 6 are all excluded, and no capability toward any of them is
introduced. No placeholder trust verifier and no reserved field for one.

### Audit remediation (pre-merge, same unreleased 0.1.0)

Findings F-1 – F-5 from the independent adversarial audit, fixed before merge. The
distribution has never been released, so the version does not move.

- **F-1 (test-suite defect, TEV-1).** TEV-1's consumer-boundary test scanned raw file text
  for its own package name, so it flagged this package's *forbidden-import denylist* — a
  statement that TEV-1 is **not** imported — as if it were an import. Replaced with AST
  semantic import detection covering plain, dotted, aliased, multiline, `from`-form and
  string-literal dynamic imports, and proven both directions: it fires on a genuine
  injected import and ignores denylists, prose, error messages and negative controls.
- **F-2 (production defect, this package).** `_digest_payload()` accepted 37 parameters and
  read 35: `policy_binding` and `producer_attestation` were passed in and ignored. A rogue
  policy issuer or forged producer signature could be carried under an unchanged,
  self-validating candidate digest. Both artifacts are now bound in full. **The candidate
  digest moved** as a result; the superseded value is pinned as a negative anchor.
- **F-3 (test-suite defect).** Gates that no test exercised, plus mutation kills previously
  attributed to the wrong gate. Focused behavioural tests added that isolate each gate.
- **F-4 (production defect, this package).** `_ALLOWED_KEYS` / `_REQUIRED_KEYS` were
  annotated `Final` inside dataclass bodies, which makes them real **fields** — constructor
  keywords a caller could override. Four occurrences across three classes, now `ClassVar`.
- **F-5 (documentation defect).** The claim that Phase 4C "carries no recommendation id"
  was wrong. The ID *is* transitively bound by the Phase 4C digest chain; it is simply not
  recoverable from the digest and not an independently cross-checkable field.

### Versioning judgement

`0.1.0` — a new, never-released distribution, matching the Phase 4C and TEV-1 convention
for a first contract package. No `CONTRACT_VERSION` is minted: that is the *provider*
convention in this repository, not the contract-shape convention. No other package's
version changes, and no existing package's source is modified.
