# ADR — Cloud Scaling guard coverage: doctrine across packages that disclaim authority

**Status:** **RATIFIED — D-GC-1…D-GC-7 ratified as written by the owner, 2026-08-29.**

The owner also ruled the two questions this document scheduled for the same ratification:
§3's separate recommendation is ratified — `capacity-bounds-policy` gains a
`CapacityBoundsRejectionReason` enum before its first scored sweep — and §7.2's flag loops
are each inventoried as one static guard site with recorded semantic multiplicity 7, the
suite required to exercise every member of `_AUTHORITY_FLAGS`, not unrolled into seven
scored sites. Every `[R]` in §2–§6 is discharged by this ratification. No operator,
mint-site extension or detector change described below exists yet in
`scripts/cloud_scaling/guard_sweep.py`: ratification authorizes the implementation, it does
not assert it. Measurements were taken in a read-only audit at
`447221b9b5279813fe35fb7096062ee9b58485ec` and re-verified against `b0ea7cf3`; §8 lists
what did not survive re-verification, and every `[G]` not re-measured at ratification
stays `[G]`.

**Implemented and measured, 2026-08-30.** The doctrine is now in
`scripts/cloud_scaling/guard_sweep.py` and `cloud-scaling-risk-integration` is swept in
CI. Implementation put three questions back to the owner, all ruled the same day, and
converted most of §8 item 5's `[G]` mutation results into measurements. **§9 records what
was measured, and every figure below that it corrects or confirms is annotated in place.**

## §1. What this ADR does to Phase 5 §9

The load-bearing question is whether §9 of `ADR_CLOUD_SCALING_AUTHORIZATION_PHASE5.md`
governs two packages it never mentions. It does not, as written — its opening sentence
scopes it to the two packages that are swept, and its criterion is a vocabulary neither
package has. This ADR extends it rather than replacing it.

| §9 subsection | line | disposition |
|---|---|---|
| §9 preamble | 249 | **extended.** "Phase 5A and Phase 5B are both swept in CI" is a statement of fact about CI, not a scope limit on the doctrine. §2 makes the doctrine package-general. |
| §9.1 typed refusal | 256 | **extended, not superseded.** The definition stands verbatim. §3 says what the pair's second element is where the named enum does not exist; §6 adds a within-class criterion. |
| §9.2 distribution boundary | 304 | **survives unchanged.** It is a rule about evidence, already stated for every member of the closed vocabulary. It binds these two packages on adoption with no amendment. |
| §9.3 import- and test-time drift | 406 | **survives unchanged.** |
| §9.4 conditional expressions | 413 | **survives unchanged**, and is the template §4 follows: a class, then its authority-weakening operator, ratified rather than left to the sweep to imply. |

Nothing here reclassifies a guard in `authorization-contracts` or `policy-authenticity`.
Phase 5A and 5B keep every classification and exclusion §9 already settles for them
`[V: PACKAGES holds exactly those two keys, guard_sweep.py:114,179]`. Where §3–§6 propose
new classes, those classes are additive: a site already inventoried under §9.1 stays
inventoried under §9.1.

## §2. D-GC-1 — Scope, and the criterion for a package that disclaims authority

**Ruled: the doctrine is package-general, and the criterion is the package's own typed
outcome, not authority.** `[R]`

Both candidate packages fall outside §9's vocabulary. `cloud-scaling-capacity-bounds-policy`
and `cloud-scaling-risk-integration` are neither Phase 5A nor 5B, and
`ADR_CLOUD_SCALING_RISK_AUTHORITY_INTEGRATION_PHASE4.md:231` says of the risk adapter that
it "selects no policy, admits no evidence, and carries nothing authority-bearing"
`[V: quoted verbatim]`. Read literally, §9 has nothing to say about either, and every guard
in both is `outside-authority-bearing-definition`.

That reading is wrong about what the sweep measures. §9.1's real content is not the word
*authority*: it is that **a refusal has a typed identity, and a guard earns its place by
changing that identity**. The generalisation replaces "authority-bearing" with:

> A guard is **outcome-bearing** when there is at least one constructible input for which
> neutralising it changes the package's own typed outcome — including changing it to no
> refusal at all.

*Say which invariant is measured.* A fail-closed non-executability invariant is not an
authorization refusal, and this ADR does not conflate them:

* In `risk-integration` the sweep measures **the non-executability invariant and the typed
  rejection**, never an authorization refusal. `NonExecutableInvariantError` is raised by 16
  of the package's 74 inventoried guards and `ProjectionError` by 19 `[V: AST measurement
  over inventory(), §7.5]`; neither denies an authorization request, because the package
  issues none. A guard here is outcome-bearing when its removal lets an executable flag, a
  forged digest or an unauthenticated token past a boundary that must fail closed, or
  changes which `AdapterRejectionReason` a caller receives.
* In `capacity-bounds-policy` the measured outcome is **admission of a policy artifact**:
  whether a malformed bound, a mis-ordered pair or a duplicate is admitted into a
  `PolicyArtifactDescriptor`.

The disclaimer in Phase 4 and the doctrine are therefore not in tension: Phase 4 says the
adapter carries no authority, and this ADR says a package that carries no authority still
carries a fail-closed invariant, which is exactly the thing a sweep can measure. `[I]`

## §3. D-GC-2 — The pair's second element where there is no reason enum

**Ruled: the second element is the finest-grained typed discriminator the package publishes
at the refusal site, named per package; and guards sharing one exception class are *not*
thereby diagnostic-only.** `[R]`

The two packages fail §9.1's literal pair in opposite directions, both measured:

* `capacity-bounds-policy` publishes **no reason vocabulary at all** — three leaf classes
  under `CapacityBoundsPolicyError` and zero `Enum` subclasses
  `[V: errors.py:18,22,26,30; no match for 'Enum)' anywhere in the package]`. Fifteen of its
  23 guards raise the same `CapacityBoundsFieldError` `[V: measured, §7.5]`. Read literally,
  §9.1's "changing the reason is enough" clause has no referent, and those 15 guards
  collapse to a single indistinguishable outcome.
* `risk-integration` publishes **three parallel vocabularies**, none of them the enum §9.1
  names: 10 exception classes under `CloudScalingRiskIntegrationError`
  `[V: errors.py:40–119]`, `AdapterRejectionReason` with 8 members and `AdapterOutcomeStatus`
  with 3 `[V: outcomes.py:47,55, member counts measured]`.

The ruling has two parts.

**Per-package second element.** For `risk-integration` the pair is per-path and fully
determined by `CloudScalingRiskOutcome`: `AdapterRejectionReason` on the rejection path,
`AdapterOutcomeStatus` on the status path, and the controller-supplied `abstention_reason`
string on the abstention path `[V: outcomes.py:96,99,100]`. For `capacity-bounds-policy`
the pair **degenerates to the singleton `(exception class)`**, because the package publishes
nothing finer.

**A degenerate pair is a defect in the package, not a licence to stop scoring.** The
inference that most of `policy.py` is diagnostic-only does not follow, and this ADR forecloses
it: §9.1 makes `diagnostic-only` a *positive* showing — a named successor guard producing the
same typed outcome for every input reaching this one — and "shares an exception class with 14
others" is not that showing. Until a reason vocabulary exists, bounds guards are scored under
the within-class criterion in §6.

*Recommendation, ratified by the owner at ratification (2026-08-29):* give
`capacity-bounds-policy` a `CapacityBoundsRejectionReason` enum before its first scored
sweep, so its pair stops being degenerate. The alternative — sweeping it against a singleton
pair — is measurable but reports "something was refused", which §9.1 says explicitly cannot
distinguish a carried authority from a fail-closed accident.

## §4. Three decision classes the engine does not model

`inventory()` walks `ast.If` and `ast.IfExp` and nothing else
`[V: guard_sweep.py:513–572]`. `excluded()` discloses only extra boolean sub-terms and
`except` arms **that raise** `[V: guard_sweep.py:600–618]`. Sites outside both are invisible
in both directions — absent from the numerator and from the disclosed denominator. §4.1–§4.3
each name a class, give a test an implementer can apply to a single site without asking
anyone, and give an authority-weakening operator, following §9.4's template.

### §4.1 D-GC-3 — `except`-arm typed rejection

**Ruled: an `except` arm whose body returns a typed refusal is a decision point, and its
operator is reason collapse.** `[R]`

*The class.* An `except` handler qualifies when its body contains a `return` whose value
names a member of the package's reason vocabulary. The test is decidable from the AST alone.
In `risk-integration` it selects exactly the 10 arms of `adapter.evaluate` that
`return self._rejected(...)`, at adapter.py lines 187, 191, 195, 199, 211, 222, 230, 242,
248 and 254 `[V: AST enumeration returns exactly that list; those are all 10 except arms in
adapter.py]`. This is the whole documented gate-1/3/4 structure and the production site of
every `AdapterRejectionReason` member.

Their invisibility is exact, not approximate: `inventory()` gives them no row because they
are not `ast.If`, and `excluded()` counts them zero times because none of the 10 raises —
the package's 8 disclosed `except_arms` are 3 in `authenticity.py` and 5 in `projection.py`
`[V: per-module measurement; adapter.py contributes raising=0 of total=10]`.

*The operator — reason collapse.* Rewrite the `AdapterRejectionReason` member the arm
returns to a fixed sentinel member, chosen so it is not the member the arm already produces.

> **Ruled at implementation (2026-08-30): the sentinel is a fixed *pair*.** No single
> member satisfies "not the member the arm already produces" across ten arms naming eight
> members, and the audit's operator resolved that by skipping the arms already at its
> sentinel — which scores them `UNSCORED`, reporting nothing about two of the ten sites
> this class exists to measure. The rule is therefore: **each arm is rewritten to a
> deterministic, different rejection reason**, using a declared `(sentinel, alternate)`
> pair so no mutation is ever a no-op. What the operator measures is whether the suite
> distinguishes typed reasons. The sentinel carries §9.4's general-for-specific direction;
> for the two arms already at it the alternate is a lateral swap, and both are invisible
> to a suite that only asks whether something was rejected. `[V: guard_sweep.py,
> PackageConfig.reason_collapse_sentinels]`
This is authority-weakening in §9.4's sense: it reports a general reason where a specific one
was owed, and leaves the refusal itself intact, so a test that only asks "was something
rejected?" cannot see it.

*Evidence, cited to the audit and not re-run here.* An out-of-tree reason-collapse operator
ran on 8 arms (2 were already at the sentinel), killed 7 and survived 1 — adapter.py:222, the
gate-3 arm returning `RECOMMENDATION_DIGEST_MISMATCH`. **Reproduced exactly** at
implementation: over the audit's 8 arms, 7 killed and 1 survived, and the survivor is
adapter.py:222 `[V: §9]`. Over all 10, 8 killed and 2 survived; the extra survivor is
adapter.py:211, one of the two the audit's operator skipped. The site and its returned member are verified `[V: adapter.py:222–229]`. The audit's
reading — the suite does discriminate the reason half, and nothing enforces that it keeps
doing so — is the reason this class is worth ratifying, and it is `[I]` until a sweep re-runs.

### §4.2 D-GC-4 — Helper-admission call sites

**Ruled: an unconditional statement-level call to a raising helper is a decision point
distinct from the helper's own guard, and its operator is call deletion.** `[R]`

*The class.* An `ast.Expr` whose call target is a name in `_raising_helpers(config)` — the
engine's existing, already-computed transitive raising set `[V: guard_sweep.py:337]`. The
test needs no judgement. It selects 29 sites: 14 in `capacity-bounds-policy`, all in
`policy.py`, at lines 119, 120, 121, 124, 162, 163, 164, 167, 172, 180, 183, 204, 272 and 273
`[V: AST enumeration reproduces exactly that list]`, and 15 in `risk-integration`, 12 in
`authenticity.py` and 3 in `adapter.py` `[V: same measurement]`.

*Why a distinct decision point.* Neutralising the helper's internal `if` proves the check
works; it does not prove the check is *applied at this site*. One covering test of the
helper masks every other call site, and `if False:` cannot reach a site that has no `if`
header. A dropped call is the defect this class exists to catch: the artifact is admitted
without ever being checked.

*The operator — call deletion.* Replace the `Expr` statement with `pass`. Deleting a call
whose only effect is to raise is precisely the authority-weakening direction; where the call
also binds, it is an `ast.Assign` and not in this class.

*Evidence, cited to the audit.* Call deletion over all 29 sites killed 11 and survived 18,
including ten of bounds' fourteen, with all 90 tests green [G: not re-run. The 90-test suite size is confirmed — 34+18+38 collected, [V] — the mutation
result is not].

### §4.3 D-GC-5 — `else`-arm refusals

**Ruled: an implementation-only extension of §9.1, not a new class; the operator is else-arm
deletion. The class has exactly one member in these two packages, not two.** `[R]`

> **Clarified at implementation (2026-08-30): the class is *direct* refusals only.** An
> arm qualifies when its own statements refuse; an arm that merely *reaches* a refusal
> through a nested `if` does not. Implementing §9.1's reach language literally selected a
> second member, `outcomes.py:159`, whose mutation span `(160,12)-(171,17)` contains
> guards `outcomes.py:160`, `164` and `168` — all separately inventoried — so its mutant
> deleted three inventoried guards at once and was killed by the same tests that kill two
> of them: a row inflating numerator and denominator together while measuring nothing.
> The owner ruled with §8 item 3, which names that exact site as not a member. The class
> has one member, `authenticity.py:432`, and the inventory total is **100**, not 101.
> `[V: guard_sweep.py, _else_arm_sites and _direct_statements]`

§9.1 already governs these sites: "a body that can reach a refusal makes the `if` a guard",
and a terminal `else` is the last arm of that same `if`. Only the operator was missing,
because an `else` has no header to rewrite. Classifying it as new would invite the reader to
ask which of two rules applies; there is one.

*The operator — else-arm deletion.* Replace the `orelse` body with `pass`, so an exact-type
dispatch falls through silently instead of refusing. That is the weakening direction: an
unrecognised type is admitted rather than rejected.

*Correction to the audit's sizing.* An exhaustive AST scan of both packages finds **one**
headerless `else: raise` site: `authenticity.py`, `else:` at 432, `raise
UnsupportedRecommendationSourceError` at 433 `[V: enumeration; the audit's "authenticity.py:430"
points two lines above the dispatch's `if` at 428]`. The second site the audit named,
`outcomes.py:145`, is not one: line 145 is an `elif` on `AdapterOutcomeStatus`, and the
terminal `else:  # PROJECTION_REJECTED` at line 159 contains only three ordinary `if` guards,
all already inventoried `[V: outcomes.py:159–171]`. A class with one member is still worth
ratifying — the operator is three lines and the site is a type-dispatch boundary — but it
should not be ratified on a count that is twice the truth.

## §5. D-GC-6 — Mint sites

**Ruled: the mint-site definition extends to methods; inline constructions are not wrapped,
and partial mint coverage is accepted and recorded.** `[R]`

`_MINT_PLUGIN` resolves `getattr(importlib.import_module(module), function)`
`[V: guard_sweep.py:814, 823–828]`, so it patches module-level functions only. Both packages
mint outside that shape:

* `capacity-bounds-policy`'s true mint is `CapacityBoundsPolicyFamilyAdapter.describe`
  `[V: adapter.py:93]`, returning a `PolicyArtifactDescriptor` `[V: adapter.py:107]` — a
  method. Its only module-level candidate is `capacity_bounds_coordinate`
  `[V: adapter.py:53]`, and a coordinate is not the authority-bearing descriptor.
  **Rejected as a mint site**: counting it would report a number that answers a different
  question.
* `risk-integration`'s `project_recommendation` `[V: projection.py:267]` and
  `authenticate_controller_output` `[V: authenticity.py:560]` are module-level and are
  genuine mints. Its terminal decision mint,
  `CloudScalingRiskOutcome(status=AdapterOutcomeStatus.RISK_DECISION, …)`, is an inline class
  construction `[V: adapter.py:276–277]` and is not patchable by name.

**Extend to methods.** `mint_site` accepts `module:Class.method`, resolved by a second
`getattr`. This is a strict widening: existing `module:function` values keep their meaning.

**Do not wrap the inline construction.** Wrapping `CloudScalingRiskOutcome` would break
`isinstance` and the dataclass path, and a mint counter that changes the program under test
measures the instrumentation. **Partial coverage is accepted, and the uncovered mint is named
in the inventory** so a reader knows which mint the count does and does not cover — an
undisclosed partial count is worse than a disclosed one.

The signal is live under either resolution: the audit reports 8 bounds mutants and 5 risk
mutants minting more than baseline `[G: not re-run]`.

> **Measured at implementation: 7 risk mutants, against a 374-test suite `[V: §9]`.** The
> count is a property of the *suite*, not only of the package: a mint-signalling guard is
> one whose removal lets the package mint more than the baseline did, so a suite that
> exercises the mint path more can reveal more of them. Measured against the pre-existing
> 287-test suite the figure is **6**, and it was still 6 at 318; the seventh,
> `projection.py:357`, appeared once an isolating test drove `project_recommendation` with
> a non-string correlation id. The audit's 5 is not reproduced at any suite size tried,
> and `mint_site` here is `projection:project_recommendation` — §5 names two module-level
> mints and does not say which the audit measured, so the difference is not resolvable.

## §6. D-GC-7 — Message-only attribution

**Ruled: recalibrate `_TYPE_READS`, and yes — §9.1 needs a discrimination-within-a-class
criterion.** `[R]`

*The accessor gap, demonstrated.* `_TYPE_READS` matches
`\.reason\b|\.outcome\b|isinstance\s*\(|pytest\.raises\s*\(|\btype\s*\(`
`[V: guard_sweep.py:862]`. None of `risk-integration`'s actual accessors matches:
`.rejection_reason`, `.abstention_reason` and `.status` all miss, because `\.reason\b`
requires a literal `.reason` `[V: regex evaluated against each accessor]`. Those are the real
field names `[V: outcomes.py:96,99,100]`. The consequence is reproduced exactly: the statement
`assert outcome.rejection_reason is X and 'expired' in outcome.detail` matches
`_MESSAGE_READS` and not `_TYPE_READS`, so it is classified message-only even though it
asserts the typed reason `[V: both regexes evaluated]`. The error over-flags — it is stricter
than the contract, not unsafe — but it misreports which contract the suite tests.

*Recalibration.* Widen the typed half to admit qualified accessors:

```
\.\w*reason\b|\.\w*status\b|\.outcome\b|isinstance\s*\(|pytest\.raises\s*\(|\btype\s*\(
```

*The wrong axis for bounds.* A message-versus-type detector answers "did the suite assert the
typed half?". Where one exception class covers 15 guards `[V]` and the suite contains 14
identical `pytest.raises(CapacityBoundsFieldError)` assertions
`[V: tests/test_artifact.py, 14 occurrences]`, every one of those passes the type test while
discriminating nothing: `pytest.raises(C)` is satisfied by any of the 15 guards firing. The
detector cannot see failure to discriminate *within* a class, and no recalibration of a
message regex will make it.

*The criterion §9.1 needs, stated so it is falsifiable:*

> A guard's kill is **not** attributable to the typed refusal when every failing assertion
> reads only an exception class that at least one other guard on the same code path also
> raises. Such a kill shows the program refused; it does not show *this* guard decided the
> refusal. Scoring it requires either a finer discriminator in the pair (§3) or a test that
> distinguishes the two guards by a value they do not share.

Both full sweeps reported zero message-only kills `[G: not re-run]`. Under the criterion
above that number is not reassurance for bounds — it is what a detector reports when it is
measuring the wrong axis.

## §7. Recorded at proposal — §7.1 fixed and §7.2 ruled at ratification

### §7.1 Prerequisite defect — blocked any `risk-integration` sweep; fixed at `b5b07bca` `[V]`

`packages/integration/cloud-scaling-risk-integration/conftest.py:23` (as proposed, at
`332535dc`) set `REPO = HERE.parents[2]` and never read `UGENCE_REPO_ROOT`; the bounds
conftest honours it `[V: capacity-bounds-policy/conftest.py:27]`. The engine's `prepare_copy`
`[V: guard_sweep.py:924]` copies the package root to `_workdir` — `/tmp/ugence-sweep-<key>/<dir>`
`[V: guard_sweep.py:795–807]` — where `HERE.parents[2]` resolves to `/`. The controller path
and `tests/planning` then failed their `.exists()` guard, were never added to `sys.path`, and
`ph_helpers` — imported by `tests/conftest.py` and four test modules — was unreachable
`[V: path resolution computed directly; ph_helpers lives at
packages/capabilities/cloud-scaling-controller/tests/planning/ph_helpers.py]`.

Under the unmodified engine the audit reports bounds scoring 90 collected while risk returns
`scored=False`, `ImportError … import ph_helpers`, baseline unscorable, every mutant
`UNSCORED`. The 90 is confirmed `[V]`; the risk failure is now also confirmed by execution —
in a `_workdir`-shaped copy outside the repository the old conftest fails collection with
`ModuleNotFoundError: No module named 'ph_helpers'` even with `UGENCE_REPO_ROOT` set
`[V: reproduced at ratification]`. **Fixed at `b5b07bca`**, which replaces the
level-counting with the bounds conftest's marker-walk-plus-override convention; the same
copy then collects all 287 tests with `UGENCE_REPO_ROOT` set `[V: measured]`. This ADR
still implements no sweep of the package.

### §7.2 Flag-loop granularity — ruled at ratification

`outcomes.py:118` and `projection.py:127` are each a single `if` inside
`for flag in _AUTHORITY_FLAGS:` [V: both read as `for flag in _AUTHORITY_FLAGS:` / `if getattr(self, flag) is not False:` / `raise`]. One mutation therefore neutralises seven
non-executability invariants together, and a kill shows only that at least one of the seven
is tested. **Ruled by the owner at ratification (2026-08-29): each loop is inventoried as
one static guard site with recorded semantic multiplicity 7, not unrolled into seven scored
sites, and the suite must exercise every member of `_AUTHORITY_FLAGS`** — the
discrimination burden falls on the tests, per §6's within-class criterion, not on the
inventory count.

> **Corrected at implementation: there are four such loops, not two, and their
> multiplicities are 7, 6, 8 and 9 — not 7 for both.** `[V: measured by AST off the
> iterated constants; guard_sweep.py, _loop_multiplicity]`
>
> | site | iterates | multiplicity |
> |---|---|---|
> | `outcomes.py:118` | `_AUTHORITY_FLAGS` (7 members) | **7** — as recorded |
> | `outcomes.py:136` | `_DECISION_FLAGS` (6) | **6** — not named above |
> | `authenticity.py:267` | `_AUTHORITY_FLAGS` (8) | **8** — not named above |
> | `projection.py:127` | `_AUTHORITY_FLAGS` (9) | **9** — recorded as 7 |
>
> The "7" above is `outcomes.py`'s tuple applied to both named loops; `projection.py:75`
> holds nine flags and `authenticity.py:245` eight. So this package's 100 static guard
> sites decide **127** invariants. The multiplicity is read off the iterated constant
> rather than recorded by hand, for the reason this correction demonstrates.
>
> The suite obligation is discharged by
> `tests/test_authority_flag_multiplicity.py`, which forces each member of each loop's
> tuple `True` individually and requires the refusal to name that flag. It was not
> previously satisfied: measured against the pre-existing suite, `projection.py:127`
> **survived** — nothing exercised its nine members in a way that killed the loop
> `[V: §9]`.

### §7.3 Pre-declared exclusion candidates `[V]`

`capacity-bounds-policy` carries zero `# pragma: no cover`. `risk-integration` carries four:
`adapter.py:266`, `authenticity.py:543`, `identifiers.py:68`, `identifiers.py:88`. Each is a
candidate only; §9.2's bar applies unchanged, and `identifiers.py:68` in particular compares
against a value imported from a separately versioned distribution.

### §7.4 Sizing, so this is not read as expensive `[G: cited to the audit, not re-run]`

Measured full sweeps: 3.38 min (23 guards, 8.80 s/mutant, 17 killed / 6 survived) and
7.54 min (74 guards, 6.12 s/mutant, 41 killed / 33 survived); one shard each.

> **The risk half reproduces exactly.** Swept at implementation against the pre-existing
> 287-test suite, the `if` layer measures **74 guards, 41 killed, 33 survived** — the
> figure above, to the guard `[V: §9]`. This is the one mutation result of §8 item 5 that
> came back identical, and it is what licenses reading the rest of §7.4 as sound rather
> than as a number nobody could reproduce. The 23-guard bounds half was not re-run here;
> it stays `[G]`. Suites are 90
and 287 tests, green and stable across two clean runs. The 90 is confirmed `[V]`; the 287
is measured at ratification — 287 collected, 287 passed in 6.82s at `b5b07bca` `[V]`. The
timings and kill counts remain `[G]`.

### §7.5 Reconciliation — where the gaps actually are `[V]`

An independent AST enumeration run against out-of-tree `PackageConfig` objects reproduces
`inventory()` exactly on the `if` layer in both packages — 23 guards in bounds (19 in
`policy.py`, 4 in `adapter.py`) and 74 in risk (3/14/28/18/11 across `identifiers`,
`outcomes`, `authenticity`, `projection`, `adapter`), zero missed and zero over-counted — and
matches `excluded()`'s disclosed `boolean_subterms` (10, 12) and `except_arms` (0, 8).

The gaps are entirely in classes the engine does not model, and §4 covers them: 15 undisclosed
sites in bounds (14 helper-admission calls, and the boolean sub-terms already disclosed) and
32 in risk (10 `except`-arm rejections, 15 helper-admission calls, 1 `else`-arm refusal, plus
the flag-loop residual of §7.2). That the `if` layer reconciles exactly is the reason these
recommendations can be stated as additions rather than as a rebuild.

## §8. Corrections to the audit inputs

Five inputs did not survive re-verification at `b0ea7cf3`. They are recorded here rather than
silently restated, per this repository's evidence rule.

1. `[G]` `docs/architecture/` holds **47** `.md` files, not 48 (50 entries, of which three are
   non-Markdown). The load-bearing half is confirmed: there is no index and nothing else to
   update.
2. `[G]` The `else`-arm site is `authenticity.py:432`/`433`, not `430`.
3. `[G]` **`outcomes.py:145` is not an `else`-arm refusal.** It is an `elif`, and the terminal
   `else` at 159 holds only inventoried `if` guards. D-GC-5's class has one member, not two.
   This is the one correction that changes a ruling's scope.
4. The `risk-integration` suite size is measured at ratification: 287 collected and 287
   passed at `b5b07bca`, matching the audit's 287 `[V]`. (It was `[G]` when proposed — the
   container that wrote this ADR lacked `numpy`, so the suite could not be collected.)
5. `[G]` No mutation run was reproduced: the D-GC-3 result (7 killed / 1 survived at
   adapter.py:222), the D-GC-4 result (11 / 18), the mint counts (8 and 5), the two sweep
   timings, and the zero message-only kills are all cited to the audit at `447221b9`. Every
   *structural* claim those results rest on — the sites, their line numbers, their returned
   reason members, the helper sets, the regexes and the counts — was re-verified and is marked
   `[V]`.

The seven rulings stand or fall on the structural claims, which reproduce. The mutation
results are corroboration, and the ratifying owner treated them as such: the conftest is
fixed (§7.1, `b5b07bca`), and the first post-ratification sweep of `risk-integration` will
convert them to measurements or corrections.

## §9. Post-ratification measurement — `risk-integration`, 2026-08-30

Ratification authorized the implementation and said so; this section records what the
implementation measured. Every figure here is a first measurement of something §8 item 5
left as `[G]`, taken with `scripts/cloud_scaling/guard_sweep.py risk-integration` against
a green baseline. Where a measurement contradicts an audit-cited figure above, the
contradiction is annotated at the figure rather than left for a reader to notice.

*Subsections are lettered, not numbered.* `§9.1`-`§9.4` already mean the four
subsections of Phase 5 §9 throughout this document, and reusing those labels here
would make every cross-reference above ambiguous.

### §9.a The inventory, and the three additive classes

**100 outcome-bearing guards** `[V]`, and the `if` layer reconciles with §7.5 exactly:
74 guards split 3/14/28/18/11 across `identifiers`, `outcomes`, `authenticity`,
`projection`, `adapter`, with `excluded()` disclosing 8 raising `except` arms and 12
boolean sub-terms — every number §7.5 states.

| class | sites | measured |
|---|---|---|
| Phase 5 §9.1 `if`/`IfExp` layer | 74 | 70 killed, 4 excluded |
| §4.1 D-GC-3 `except`-arm | 10 | 8 killed, 2 excluded |
| §4.2 D-GC-4 helper-admission | 15 | 13 killed, 2 excluded |
| §4.3 D-GC-5 `else`-arm | 1 | 1 killed |

§4.1's ten arms are at the line numbers §4.1 enumerates, returning the members it names
`[V]`. §4.2's risk half is 15 sites — 12 in `authenticity.py`, 3 in `adapter.py` — as
stated; the 11-killed/18-survived figure there is over both packages and was never split,
so the risk half's 13/2 is a first measurement, not a contradiction.

### §9.b The sweep

```
100 guards, 92 killed, 0 survived, 8 declared unscorable, 0 unscored
message-only kills: 0        baseline: 374 tests, green
```

**Zero surviving SCORED, zero unscored, zero message-only kills**, which is the bar the
owner set for CI adoption. The 8 exclusions are declared in `PACKAGES`, each with a reason
from the closed vocabulary and a test that measures the claim, and each written *after* a
measured sweep rather than predicted before one:

| site | reason |
|---|---|
| `identifiers.py:88` | `unreachable-behind-earlier-guard` — behind the import-time drift guard |
| `projection.py:252` | `diagnostic-only` — the loop below it raises the same class |
| `adapter.py:152`, `:186` | `unreachable-behind-earlier-guard` — the token's constructor already ran this validation |
| `adapter.py:211`, `:222` | `unreachable-behind-earlier-guard` — `projection.py` raises neither class |
| `adapter.py:266` | `unreachable-behind-earlier-guard` — behind `projection.py:139` |
| `adapter.py:271` | `diagnostic-only` — `outcomes.py:131` raises the same class |

*On §7.3's four pre-declared candidates.* Two of them — `authenticity.py:543` and
`identifiers.py:68` — are **scored and killed**, so the pragma bought them nothing;
`identifiers.py:68` is killed by installing a controller resolution that renames an action
kind, which is Phase 5 §9.2's rule applied rather than quoted. Only `identifiers.py:88` and
`adapter.py:266` earned the exclusion the pragma hinted at. A candidate is not a grant.

*On the reason vocabulary.* Six of the eight are `unreachable-behind-earlier-guard`, which
is a third closed-vocabulary reason beyond the equivalent/diagnostic-only pair. It is the
accurate description of this adapter's defence-in-depth layer, and the distinction it
draws is real: the two calls to `_validate_authenticated_output` are excluded because no
caller-supplied token reaches them, while the three guards *inside* the function they call
(`authenticity.py:429`, `:431`, `:432`) are scored and killed, because a forged token does
reach those and the package's own `_assert_no_authority_fields` names forging as its
threat model.

### §9.c What discrimination cost

Three sites could not be closed by asserting a substring of the refusal, because the
*mutant's* message contained it too — a message-only kill, which §6 refuses and the owner's
ruling forbids outright. `authenticity.py:581`/`:582` have a genuine typed-outcome input
(an **unsupported source** with a malformed expectation yields a different exception class,
because those two run before the exact-type admission); the other two had none and are the
two `diagnostic-only` exclusions above, each on a positive showing measured by running the
mutant rather than inferred from a shared class. This is §6's within-class criterion
biting in practice, on a package that has a reason vocabulary.

### §9.d Prerequisite, same class as §7.1

§7.1's conftest fix was necessary but not sufficient. Two *tests* counted directory levels
instead of honouring `UGENCE_REPO_ROOT`, so in a `_workdir`-shaped copy the baseline was
red and `require_green` voided the sweep before it could run `[V]`. A third,
`test_the_controller_still_has_no_risk_authority_import`, had no `.exists()` assertion and
so passed *having asserted nothing* in every mutant run — a test failing open rather than
closed, contributing no killing power. All three are fixed the way §7.1 was.

### §9.e Carried forward, not decided here

Teaching the multiplicity sizer to read annotated constants revealed **two loop-guards in
`cloud-scaling-policy-authenticity` that no inventory has ever disclosed** —
`verification.py:1026` over six carried instants and `verification.py:1076` over three
occurrence facts `[V: measured]`. Disclosing them would rewrite an inventory §1 reserves,
so multiplicity disclosure is a per-package opt-in, on for `risk-integration` alone, and
these two are recorded here as a **Phase 5B follow-up requiring explicit ratification**
before that package's inventory moves. A test pins both sites so the finding cannot be
lost while it waits. *(Ruled 2026-08-30 — §10.)*

## §10. §9.e ruled — multiplicity disclosure for `policy-authenticity`, 2026-08-30

**Ruled by the owner, 2026-08-30: §7.2's static-site multiplicity doctrine extends to
`cloud-scaling-policy-authenticity`, for exactly the two sites §9.e carried forward.**
This is the explicit ratification §9.e required before that package's inventory moved.
§1's reservation is amended this far and no further: nothing else in what
`authorization-contracts` or `policy-authenticity` record changes.

* `verification.py:1026` remains one static guard site (inventory index 113) and
  discloses multiplicity **6**, read off `_CARRIED_INSTANTS`.
* `verification.py:1076` remains one static guard site (index 117) and discloses
  multiplicity **3**, read off `_OCCURRENCE_FACTS`.
* The package remains at **119 static guard sites** and now reports **126 protected
  invariants** `[V: regenerated with --inventory-only; guard_classification.json
  byte-identical]`.

Disclosure-only, in §7.2's sense: neither loop is unrolled, and the sweep's denominator
does not move — no guard index, condition, shape, kind, terminal classification, mutation
operator, or refusal behavior changes. `record_multiplicity` stays a per-package opt-in;
the ruled adopters are `risk-integration` (§7.2) and `policy-authenticity` (this section),
and `scripts/cloud_scaling/tests/test_decision_class_operators.py` pins that set together
with explicit negatives for the two packages that have no ruling.

The suite burden §7.2 places on a disclosed loop was **measured discharged before this
ruling**: each of the six carried instants and each of the three occurrence facts is
forged or violated individually, and the refusal must name that member — 9/9 passed
`[V: tests/test_candidate_instant_typing.py::test_a_lying_instant_cannot_satisfy_its_own_window ×6,
tests/test_candidate_validity.py::test_every_occurrence_fact_is_enforced_not_just_the_first ×3]`.
What changed at implementation is structural, matching `risk-integration`'s
`test_authority_flag_multiplicity.py`: both parametrizations now iterate the production
tuples themselves, and each tuple's exact membership is pinned independently
(`test_the_carried_instant_membership_is_frozen`,
`test_the_occurrence_fact_membership_is_frozen`), so a member added to production cannot
go silently untested and a member removed cannot silently shrink the suite.

Nothing else is decided here; in particular, no `else`-arm or nested-`if` classification
question is reopened or resolved by this ruling.

## §11. D-GC-1 widened — packages that verify and spend authority, 2026-08-31

**Ruled by the owner, 2026-08-31: the doctrine's universe widens from packages that
advise or disclaim authority to include — more importantly — packages that verify and
spend it, and `cloud-scaling-operations` adopts first.** This is the explicit,
§10-style extension the adoption audit required: §2's outcome-bearing criterion always
had referents in this package, but the ADR's stated universe ("packages that disclaim
authority") did not cover a package whose posture is CONTROLLED_EXECUTION /
INFRASTRUCTURE_MUTATION and whose `ExecutionDenied` gates decide whether infrastructure
is changed. Those gates are precisely outcome-bearing, and they are what this ruling
brings under measurement.

*The re-derived denominator is 55, not the audit's provisional 46* `[V: measured;
guard_sweep.py operations --inventory-only]` — 49 `if`-layer guards, the two
statement-level `verify_authorization(...)` authority-application sites plus the script
entrypoint (D-GC-4), and the executor's three bound-return `except` arms (D-GC-3). The
owner's instruction not to assume the 17 returning `except` arms qualify was applied in
both directions: 14 of them return booleans or exit codes, never a vocabulary member,
and stay outside the ratified class `[V: AST census]`; the executor's three
(`executors.py:229`, `:287`, `:296`) name their `ExecutionOutcome` member in the arm
body and return the binding, which the class definition now selects through a
bound-return fallback that leaves every prior adopter's selection — members named in
the return value — untouched `[V: all five prior inventories byte-identical]`.

Two engine widenings carry the package's refusal shapes, both opt-in and both measured
as no-ops for every prior adopter: `bound_refusal_calls` (a gate that binds its typed
receipt and returns the name — `r = self._receipt(..., ExecutionOutcome.DENIED, ...);
return r` — is a typed-refusal guard) and the D-GC-3 bound-return fallback above. The
mint site reads literally for this package: the counter wraps the fake backend's
`set_replicas`, so "removing this guard lets the package mint something the baseline
refused" means *an infrastructure mutation happened that the baseline denied* — and the
sweep measures **14** such guards across the authority and executor layers
`[V: aggregate, minting_guards]`.

**The reference-HMAC caveat is part of the record, not a footnote.** The gates are
verified against `ReferenceAuthorityVerifier`, a deterministic HMAC for tests and local
development that is explicitly not a production KMS; every kill proves gate
*enforcement* — the check is applied, discriminates its typed outcome, and fails
closed — and none proves production cryptographic strength, which belongs to the
verifier a deployment injects. The generated `GUARD_INVENTORY.md` carries this caveat
verbatim (`PackageConfig.inventory_note`).

Measured at adoption, after closing the survivors: **55 guards, 51 killed, 0 survived,
0 unscored, 0 message-only kills**, against a green 157-test baseline `[V: aggregate]`.
The first sweep measured 26 killed / 29 survived — nine of the nineteen `authority.py`
denial gates among the survivors, the §6 within-class story exactly: the pre-existing
suite asserted "denied" and never the code, so gate removals cascaded into later
denials no assertion could tell apart. The survivors were closed by isolating tests
asserting the typed half (`ExecutionDenied.code`, the `ExecutionOutcome` member on the
receipt *and* the audit event, the `GateOutcome` action, the exception class), and the
four exclusions are the process-entrypoint layer, each on
`outside-authority-bearing-definition` with a named evidence test. Two §7.1/§9.d-class
prerequisites surfaced and were fixed the same way those were: the tests' conftest
located the sibling controller by directory hops and skipped path setup when any
installation was importable (a copy would have measured unmutated code), and a
duplicate `test_cli.py` basename kept the suite from collecting outside the
repository at all.

## §12. Controller phase 1 — `planning/` adopted, honestly partial, 2026-08-31

> **WITHDRAWN IN PART, 2026-09-01 (see §13.a).** Two numeric claims in this section
> were false when written and are withdrawn here so that a reader of §12 alone is not
> misled. **The denominator "219" is withdrawn; the measured figure is 252.** **The
> result "0 survived" is withdrawn; four guards survived at the boundary as it should
> have been declared.** The cause was an undeclared refusal helper, not a mis-sweep:
> `planning/pipeline.py` reaches its abstentions through `_abstain` and five bindings
> built on it, none of which phase 1 declared in `refusal_calls`, so 33 decision points
> were never enumerated. Everything else in this section — the boundary rationale, the
> exclusion doctrine, the prerequisite findings — stands as written. The withdrawn
> figures are left in place below rather than silently rewritten, because a record that
> quietly corrects itself teaches nothing about how the error was possible.

Ruling 3 of 2026-08-31 ordered the Cloud Scaling Controller adopted **in phases**,
starting with `planning/` and "report it honestly as partial controller coverage",
each phase CI-blocking before the next. This section records phase 1.

**The boundary is declared, not implied.** The `controller-planning` entry walks the
10 `planning/` modules in the order a recommendation is built. The other 68 production
modules are named individually in `excluded_modules`, each with the `raise` count
measured in it at adoption (generated from the tree by `_CONTROLLER_DEFERRED`, so the
numbers cannot drift into a claim nobody re-measured): the phase covers 205 of the
package's 426 `raise` statements, and the generated inventory's own preamble names
every deferred subpackage with its size and states that a green sweep here is not
evidence about any of them. A module added outside `planning/` fails the inventory's
completeness gate rather than escaping it.

**The denominator was re-derived by measurement: 219** *(withdrawn — the measured
figure is 252; see §13.a)* — 213 `if`-layer guards, 4
helper-admission sites, 1 except-arm, 1 else-arm. The first derivation measured 218:
the entry named the reason vocabulary by its class, but `pipeline.py` imports it as
`RecommendationAbstentionReason as R` and writes `R.MEMBER` at all 31 of its refusal
sites, so the engine read the module as having no typed outcome and dropped its one
D-GC-3 arm. Naming the alias as the source names it — the documented contract of
`reason_vocabularies` — recovered the arm. `ConstraintViolationKind` is the second
vocabulary; `RecommendationOutcome` is deliberately absent (a `Union` type alias names
no decision).

**The first sweep measured 63 killed / 156 survived** — by far the weakest guard-level
coverage of any adopter, and the §6 story at scale: the 493-test Phase-3 suite proves
the pipeline *behaves*, and `topology.py:89`'s `isinstance` gate could be deleted
outright with every test staying green. The owner ratified closing all of it. The
survivors were closed by 153 isolating tests, each constructing an input valid in
every respect except the one field its target guard reads, so exactly one gate can
refuse it and the typed exception class attributes without any message assertion.
Recurring discriminators, recorded in the tests themselves: the field-name-list probe
for mapping gates (every later gate passes on it and the fallback is a `TypeError`);
`inf`/`NaN`/`None` chosen per gate so the mutant either admits the value outright or
dies on a different contract; a truthy non-sequence iterating to a fully valid payload
for sequence gates; a second deliberate fault where a `from_dict` gate is repeated by
a dataclass gate with the same class, moving the mutant's fallback into a different
error type; a delegating impostor for a type gate whose plain-probe failure would be
re-raised under the same class by an except-jacket; and perturbation of a genuine
pipeline-built record via `dataclasses.replace`, with forgeries aimed at losing
candidates so the selection outcome cannot mask the recompute gate under test.

**16 defense-in-depth exclusions, every one measured.** The re-validation machinery in
`recommendation.py` deliberately checks the same conditions at multiple depths, and
this package's typed half is the exception class alone — so several guards are
*jacketed*: for every input that reaches them mutated, a sibling gate refuses under
the same contract. Ten are in `recommendation.py` (the empty-set, duplicate-pair,
feasibility-interlock, NO_CHANGE-baseline, infeasible-selected, ambiguity,
horizon-expiry, horizon-positivity, and defensive-uniqueness guards), plus
`topology.py`'s conflicting-kind arm, `constraints.py`'s `_finite_number` None branch,
two in `candidates.py` and one each in `policy.py` and `pipeline.py` (the ScoringError
arm the pipeline's own typed pre-gates keep unreachable). Each carries the reason from
the closed vocabulary — `diagnostic-only`, `unreachable-behind-earlier-guard`, or
`equivalent-mutant` — and an evidence test that measures the jacket rather than
asserting it. None was written before a sweep measured the guard surviving its
isolating probe.

**Measured at adoption, after closing the survivors: 219 guards, 203 killed, 0
survived, 0 unscored, 16 excluded, 0 message-only kills**, against a green 646-test
baseline `[V: aggregate]`. *(Withdrawn — the "219" and the "0 survived" are both false;
the boundary was 252 and four guards survived it. The aggregate was a true measurement
of a surface that had been enumerated incompletely, which is precisely why "measured"
is not the same as "complete". See §13.a.)* The mint site is `CapacityActionRecommendation.__post_init__`
— a recommendation that exists is the artifact, and abstention is deliberately not a
mint. Two §7.1/§9.d-class prerequisites surfaced and were fixed with the repository's
own conventions: the suite did not collect outside the repository at all (three test
basenames duplicated across subdirectories; fixed with `--import-mode=importlib` in
the package's pyproject, as seven sibling packages already declare), and the tests'
conftest preferred an installed distribution over the source beside it (the exact
defect §11 fixed for operations; latent here, fixed unconditionally).

**CI.** `cloud-scaling-controller-phase3-ci.yml` — already scoped to Phase 3, which
is `planning/` — gains the shared-engine jobs: inventory regeneration (which now also
enforces the 68-module boundary disclosure), engine tests, a four-shard sweep, and an
aggregate pinning the totals above with the 16 exclusions named individually. The
engine-filter floor test rises from five workflows to seven, and the raise closed a
real gap: `cloud-scaling-risk-integration-ci.yml` had run the shared engine since its
own adoption without ever being named in the floor.

**Next phases.** `forecasting/` (102 raises) and `canonical/` (94) carry most of the
deferred refusal surface and are the natural phase 2; each later phase re-derives its
own denominator and meets this same bar before the boundary widens.

## §13. Controller phase 2 — `canonical/` and `forecasting/` adopted, 2026-09-01

Ruling 3 of 2026-08-31 ordered the controller adopted in phases, each CI-blocking
before the next. Phase 1 (§12) took `planning/`. This section records phase 2, which
widens the boundary to `canonical/` and `forecasting/` and renames the entry to
`controller-evidence-planning`, the key naming what it now walks rather than what it
walked first. It remains **partial** controller coverage: 31 of 78 production modules.

### §13.a §12's denominator was an undercount, and CI could not have caught it

Phase 1 published 219 guards and "0 scored survivors". Both figures were wrong.

`planning/pipeline.py` reaches its typed abstentions through a helper, `_abstain`, and
through five bindings built on it (`ab`, `abf`, `abc`, `abcost`). Phase 1's entry did
not declare those names in `refusal_calls`, so the engine did not recognise their
`return f(...)` sites as refusals and enumerated none of them. Declaring them adds **33
guards**, all in `pipeline.py`, and they are not peripheral: they are the gates
selecting `UNSUPPORTED_FORECAST_TARGET`, `INSUFFICIENT_FORECAST_CONFIDENCE`,
`FUTURE_DATA_LEAKAGE`, `MISSING_CURRENT_CAPACITY` and `FORECAST_ABSTAINED` — the
pipeline's whole abstention surface. **The corrected `planning/` figure is 252, not
219.** Four of the 33 were genuine survivors, so §12's "0 scored survivors" was false
when it was written, and the four are closed in this phase.

The failure mode is worth naming because the gate that should have caught it is the one
that hid it. The phase-1 workflow pins `inventory_total` to 219 exactly. A denominator
error moves the total, so the pin fails — and the natural reading of a failing pin is
"someone added a guard", not "the previous count was short". An exact pin is excellent
at catching drift in a surface whose *boundary* is right and useless against a boundary
that was never right. Nothing in the sweep can detect a decision point it was never
told to look for; only re-deriving the refusal vocabulary against the source can.

**The rule this yields: a phased adoption must re-derive `refusal_calls` from the source
at every phase, never inherit the previous phase's set.**

`[G]` **That rule is prose, and nothing enforces it.** No engine test derives a refusal
idiom set from the boundary and reconciles it against the declaration, the way
`test_module_completeness.py::test_every_excluded_adopter_module_reason_still_holds`
already reconciles the deferred `raise` counts. Every CI pin here is computed *from* the
inventory, so all of them are conditional on the boundary being right — which is exactly
the failure this section describes. Making the rule mechanical is the obvious next
hardening and is deliberately not attempted in this phase. §12's own §12-equivalent
lesson was the aliased-import one (`RecommendationAbstentionReason as R`); this is the
same lesson one level up — the engine sees the names it is given, and a refusal it
cannot name is a refusal it cannot count. Both were found by testing the candidate
rather than reasoning about it.

### §13.b The measured boundary

**527 guards.** 252 are the corrected `planning/` surface; 275 come from the widening
(`canonical/` 10 modules, `forecasting/` 11). The remaining 47 production modules stay
named individually in `excluded_modules` with their measured `raise` counts, and the
generated inventory's preamble names every deferred subpackage and states that a green
sweep here is not evidence about any of them.

**First-sweep survival: 165 of 527, 31.3%** (reported from the run, not archived — no
first-sweep artifact is checked in, so a reader cannot re-derive this one figure). That is the honest number for a surface
adopted without its tests having been written against a sweep — three times phase 1's
rate over `planning/` alone, which is what a layer built for canonical correctness
rather than for gate coverage looks like when it is first measured.

**Final: 503 killed, 24 excluded, 0 survivors, 0 unscored, 0 message-only kills.**

Both of those figures moved after an adversarial audit of the phase-2 PR, and §13.f
records why — a coverage phase that cannot survive an adversarial read of its own
exclusions has not finished.

### §13.c Four survivors were weak probes, not equivalent mutants

The full sweep left 12 of the widened surface surviving. Seven are excluded in §13.d;
an eighth, `normalization.py:197`, was excluded and then withdrawn under audit (§13.f)
and is now SCORED. The other four were tests that passed
whether or not their guard existed, because each probe was routed into a *sibling* gate
refusing the same input under the same typed contract. They are recorded because the
mistake is systematic, not incidental — the same author wrote a correct probe for the
identical pattern in `canonical/state.py` and an incorrect one in `canonical/identity.py`
in the same sitting:

| Guard | Probe that failed to kill | Probe that kills |
|---|---|---|
| `identity.py:78` | `from_dict(["checkout"])` — dies on the unknown-field check | `from_dict(["workload_id"])` — passes both earlier checks |
| `normalization.py:203` | non-finite with `clamp=False` — the range check refuses it too | `clamp=True` — neutralised, the overflow is clamped to a confident `1.0` |
| `forecast.py:88` | unknown status on a forecast — the abstained arm rejects its point estimate | unknown status on an abstention — the arm accepts it |
| `evaluation.py:335` | `unscored_record(status=EVALUATED)` — rejected one frame deeper anyway | `status=ABSTAINED` — a well-formed record nothing objects to |

**The rule: a probe must be chosen against the code the neutralised guard falls through
to, not against the guard itself.** A gate-removal sweep is the only thing that
distinguishes the two, which is why no exclusion in this repository may be written
before a sweep has measured that guard surviving its isolating probe.

### §13.d The eight new exclusions

Phase 1 carried 16. Phase 2 adds eight — seven in `canonical/`/`forecasting/` and one,
`planning/pipeline.py:147`, in the newly-enumerated pipeline surface — for 24. That
`planning/` entry is **new, not pre-existing**: it is one of the 33 guards phase 1 never
counted, so it could not have been excluded before this phase existed.

Four are `unreachable-behind-earlier-guard`, three are `equivalent-mutant`, and one
(`pipeline.py:147`) is `unreachable-behind-earlier-guard` in the pipeline. Every one
carries an evidence test that measures the *jacket* — the thing that makes the guard
unreachable or redundant — so the exclusion fails the day the jacket goes away:

* `normalization.py:200` (exhaustive `else`) — every declared `NormalizationMethod` has
  a dispatch arm; the evidence test asserts that, so it fails when one is added without.
* `evidence.py:240` (non-finite sweep) and `evidence.py:246` (domain sweep) — `domain_for`
  reads the *same* `unit_domain` authority `Measurement.__post_init__` enforces, so
  neither a non-finite nor an out-of-domain sample can be constructed at all.
* `replay.py:191` (second leakage guard) — `_match_actual`'s eligibility rule already
  skips every observation at or before the cutoff; measured with a tolerance ten times
  the horizon, the only width at which a past observation could otherwise match.
* `evidence.py:277` (NORMALIZED early abstention) — the window builder it falls through
  to produces the identical reason over the identical window.
* `evidence.py:287` (normalization except-arm) — **the arm is reachable; the mutation
  target is not.** The except-arm mutation rewrites the reason member the arm *names*,
  and the only member named there is the `.get()` default — dead code, because
  `_APPLICABILITY_REASON` is total over every reason the error carries. Reaching an arm
  and reaching its mutation target are different questions, and a first reading
  conflated them.
* `evaluation.py:204` (ABSTAINED dispatch) — the ABSTAINED arm and the catch-all below
  it enforce an identical pair of rules, differing only in message text, which §6
  forbids attributing a kill to.

### §13.e Carried forward, not decided here

The 47 deferred modules remain deferred. Whether `signals/` should be adopted next — it
feeds canonical state, so the boundary drawn here is arguably one layer short — is a
judgment call about boundary placement, not a fact the repository settles, and is left
to a later ruling.

### §13.f What an adversarial audit of this phase found, and why it is recorded

The phase-2 PR was submitted claiming 502 killed / 25 excluded / 0 message-only kills.
An independent read-only adversarial audit falsified two of those claims. Both are
recorded here rather than quietly corrected, because each is a *different* way for a
coverage phase to be wrong while every number it publishes looks right.

**1. A message-only kill, produced by the evidence test written to prevent one.**
`canonical/measurement.py:121` — the non-finite check — was killed by exactly one test,
whose assertion was `assert "finite" in str(exc.value)`. §6 forbids attributing a kill
to a message substring, and the engine's own detector flags it; the PR nonetheless
claimed zero. The cause is the jacket pattern of §13.c, one level over: the probe used
`Unit.PERCENT`, and `0.0 <= nan <= 100.0` is False, so the *range* check refuses NaN
whether or not the finiteness gate exists. The typed half was therefore unkillable and
only the message differed. `Unit.MILLISECONDS` is unbounded above and its only other
check is `value < 0.0`, False for both NaN and infinity — so under that unit the gate is
the sole refusal, and a typed assertion kills it. **The lesson is not "avoid message
assertions"; it is that a message assertion is what a jacketed probe degrades into, and
the message-only detector is therefore a jacket detector.**

**2. An exclusion whose unreachability claim was false.** `canonical/normalization.py:197`
(`threshold <= 0`) was excluded as `unreachable-behind-earlier-guard` on the reading that
`NormalizationPolicy` refuses a non-positive threshold at construction. It does. But
`__post_init__` freezes its mappings with `object.__setattr__(self, "thresholds",
dict(self.thresholds))`, and a `dict` is not immutable — the comment above that line says
"immutable copies" and is wrong. The dataclass is frozen against attribute rebinding, not
against mutation of the mapping it hands out. Mutating `policy.thresholds` after
construction reaches the division, and neutralising the guard then CLAMPS `5.0 / -1.0`
to `0.0` under a default policy: a normalized signal reading as zero saturation, produced
by dividing by a negative divisor. The guard is load-bearing, not defensive; it is now
SCORED with a probe, and the totals moved to **503 killed / 24 excluded**.

**The general rule: "an earlier guard validates this" is a claim about a value's whole
lifetime, not about one instant.** Construction-time validation bounds an object when it
is built; if a mutable structure survives construction, the bound does not survive with
it. Every `unreachable-behind-earlier-guard` exclusion should be read against that test.

**The rule is a prompt to measure, not a conclusion — and a re-audit falsified the
stronger form using this ADR's own exclusion set.** A first draft of this paragraph said
that a surviving mutable structure *makes* a later-frame guard reachable, full stop.
`NormalizationPolicy.method_by_signal` is frozen by the same defective `dict(...)` line
as `thresholds`, one line above it, and `normalization.py:200` reads it — yet `:200` is
still correctly excluded, because every post-construction mutation of that mapping dies
on an untyped `KeyError` at `_METHOD_UNITS[method]` before the dispatch is reached. Same
defect, same shape of argument, opposite answer.

So a surviving mutable structure makes an exclusion **suspect**, and suspicion is
discharged by a probe and a sweep, never by the argument alone. That is §13.c's lesson
restated one level up: the difference between the two exclusions is a fact about the
code, and only measurement settles it.

Neither defect was found by the sweep, by CI, or by the author. Both were found by
attacking the exclusions specifically — which is why an adversarial pass on the exclusion
set, not merely a green aggregate, is what finishes a phase.

**A footnote on the pins, earned in this phase.** Fixing the two defects above added one
test, moving the suite from 812 to 813, and the first CI run after the fix failed on
exactly that: `baseline collected 813, expected 812 per shard`. Every other assertion in
the same block passed — inventory 527, killed 503, excluded 24, unscored 0, **message-only
0**. That is the pin doing precisely the job §13.a says it is good at: catching drift in a
surface whose boundary is right. It remains no help at all against a boundary that is
wrong, which is why both statements belong in the record together.

### §13.g The `match=` blind spot — measured, partly closed, and deliberately not closed in the engine

A second adversarial audit, of the head that fixed §13.f's two defects, found that the
phase **still** had message-only kills and that CI could not have reported them.

**The blind spot.** `_TYPE_READS` matches `pytest.raises(` unconditionally, on the
reasoning recorded beside it: a statement that also raises-checks has asserted the
exception class, so its failure is not attributable to prose. **That reasoning holds only
while the class differs between the guarded and unguarded paths.** Where one module
raises one error type with several prose messages, the class check passes under mutation
and the `match=` regex alone fails — a message-only kill wearing a typed statement.

**Two live instances in this phase, both closed here.** Both are in `forecasting/
series.py`, both SCORED, both put into the scored set by this phase's widening, and both
load-bearing rather than diagnostic:

* `:166` collapses `CROSS_SUBJECT` into `CROSS_TENANT`. `_SERIES_ERROR_ABSTENTION` maps
  those to **different** typed abstentions, so the collapse loses a distinction a service
  boundary acts on.
* `:218` silently admits two observations that share a timestamp and disagree on content
  under `COLLAPSE_IDENTICAL`; its mutant then reports "multiple *identical* observations",
  which is false of the input it just accepted.

Six `match=` probes in `test_series.py` now assert `SeriesErrorReason` — a vocabulary this
package's own engine entry declares in `reason_vocabularies` and which **no test in the
suite read**. Two were sole killers; four were latent by the same mechanism.
`test_uncertainty.py`'s `pytest.raises(Exception)` sole killer is likewise typed now:
bare `Exception` asserts no contract, and it was the whole published evidence for the
coverage gate.

**The engine fix is measured, correct, and deliberately NOT in this phase.** Reading the
*failure* rather than the statement source distinguishes the two cases exactly — pytest
signals a regex-only failure with its own `AssertionError`, raised after the class already
matched, so a `match=` test whose mutant raised nothing still scores as the typed kill it
is. Applied to the neighbours, it turns `risk-integration` red: **10 message-only kills**
(`authenticity.py` ×6, `adapter.py` ×2, `outcomes.py`, `projection.py`), because the
aggregate refuses any (`guard_sweep.py`, the `message_only_kills` problem).

`[G]` **That figure is a lower bound on the follow-up's scope, not the whole of it.**
`risk-integration` is the only neighbour actually measured under the strengthened
detector; the `authorization-contracts` run was terminated by its host before writing a
result, and the remaining four adopters were never started. `authorization-contracts`
carries 14 `pytest.raises(Exception)` sites and is the most likely of the four to carry
further instances. The follow-up must measure every adopter before it claims a scope.

Landing it here would break a passing gate on a package this phase does not otherwise
touch, and would forfeit the adopter-isolation property the phase is audited against.
**Owner ruling, 2026-09-01: split.** The controller's own defects are closed at the test
level and hold under either detector, so this phase loses nothing by deferring; the engine
change plus every adopter's fixes are a follow-up whose scope is now measured rather than
guessed.

`[G]` **Until that follow-up lands, `message_only_kills == 0` means "no kill matched the
detector", not "no kill is attributable to prose."** Nineteen `match=` sites remain in
this package's evaluation, window and replay tests. None is a sole killer — an exhaustive
mutation of all 480 `if`-kind scored guards found only the two above — and none can be
converted today: `EvaluationError`, `WindowError` and `ReplayError` are bare `ValueError`
subclasses with no typed discriminator to assert. Giving them one is a production change
a coverage phase must not make, and is part of the same follow-up.
