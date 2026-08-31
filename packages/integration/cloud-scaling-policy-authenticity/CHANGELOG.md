# Changelog — ugence-cloud-scaling-policy-authenticity

## 0.9.0 — carrying the authority's two supersession refusals

The change authorized by `ACC-LC-IA-BASE-A1` (see
`docs/architecture/ADR_UGENCE_AGENT_CONSTITUTION_LIFECYCLE_IMPLEMENTATION_AUTHORITY_AMENDMENT.md`).
Additive: two new outcome members, two new mapping entries, nothing removed and
no existing outcome re-pointed.

Policy Authority `0.2.0` added `PolicyResolutionReason.SUPERSEDED` and
`SUPERSESSION_INTEGRITY_INVALID`. This package's reason mapping is **total** over
the authority's refusals and **injective**, so each new reason needs its own
outcome member — which is precisely why the guards at
`tests/test_typed_outcomes.py:26` and `:32` failed the authority's change before
it could merge, and why they are left exactly as they are.

### Added

- `PolicyAuthenticityOutcome.POLICY_SUPERSEDED` — a verified supersession
  applies: a successor was issued over this version, which therefore no longer
  resolves. **Not** `REVOKED`: the version is replaced, not withdrawn, and the
  two are kept distinct because collapsing them would break injectivity and lose
  the distinction the authority draws.
- `PolicyAuthenticityOutcome.SUPERSESSION_INTEGRITY_INVALID` — a supersession
  record exists but does not itself verify; neither honoured nor ignored, on
  `REVOCATION_INTEGRITY_INVALID`'s exact precedent.
- The two corresponding `RESOLUTION_REASON_OUTCOMES` entries.

### Changed

- `tests/test_phase5a_untouched.py` pins the Policy Authority at `0.2.0` instead
  of `0.1.0`. The pin **moved**; it was not deleted or loosened. A consumer that
  stopped pinning the authority's version would destroy the tripwire that caught
  this in the first place (`ACC-LC-IA-BASE-A1`).

### Not changed

- Neither temporal-outcome membership nor any existing mapping entry: a
  superseded answer is not a temporal one, since it does not move back to
  `VERIFIED` as the clock advances.

## [Unreleased] — `diagnostic-only` fails across a distribution boundary too

*No version bump and no production behaviour change.*

### Guards 77 and 99 are scored

Both were excluded as `diagnostic-only`: a successor refuses with the same outcome, so
removing them costs a message and no authority. Both successors decide on operands the
Policy Authority owns, under an open-ended `>=0.1.0` — which makes each exclusion a claim
about the installed release, exactly what §9.2 already refused to accept for
`equivalent-mutant` and `unreachable-behind-earlier-guard`. Measured against 0.2.0s built
from real upstream source:

| | guard 77 — `verification.py:487` | guard 99 — `verification.py:706` |
|---|---|---|
| the drift | `implies_current_validity` → `return self.resolved` (`core/records.py:334`) | the frame drops `"adapter"` (`core/canonical.py:212`) |
| undrifted 0.1.0 | refused `HISTORICAL_RESOLUTION_REFUSED` | refused `POLICY_PROJECTION_DIGEST_MISMATCH` |
| drifted, guard present | refused `HISTORICAL_RESOLUTION_REFUSED` | refused `POLICY_PROJECTION_DIGEST_MISMATCH` |
| drifted, guard neutralised | refused `INVARIANT_VIOLATION` | **`VERIFIED`** |

Guard 99 is the serious one: under a resolution the pin admits, removing it lets a
descriptor naming one adapter be verified against a record naming another — a mint, not a
lost diagnosis. Guard 77 loses the clean refusal and reaches the artifact-pairing invariant
at `verification.py:266` instead, reporting an internal integrity failure for an ordinary,
expected, refusable answer.

Four tests replace the two exclusions' measuring tests, in the guard-78 pattern: each guard
gets one test that it fires under the drifted resolution and one that removing it changes
the answer, so a failure says which half broke.

### The rule, rather than a third case

The alternative was to ratify a narrower `diagnostic-only` bar that accepts
installed-release evidence. Rejected: it would have carved out most of the surviving
exclusions immediately after retiring the same asymmetry for
`unreachable-behind-earlier-guard`, and guard 99 shows what it would license. ADR Phase 5
§9.2 now states one rule for every member of the vocabulary — no exclusion reason may be
claimed across a distribution boundary on evidence about one installation — and its false
closing sentence ("every operand that decides them is defined in the distribution that
declares the guard") is corrected: the eleven remaining exclusions rest either on
same-distribution operands or on Python-language facts.

**The split is 111 `SCORED` / 8 `EXCLUDED`,** over an unchanged inventory of 119.


## [Unreleased] — two decision points were in no inventory, and one more exclusion was false

*No version bump and no production behaviour change.*

### `_terminal_outcome` decides two things, and neither was counted

`verification.py:1101` and `:1102` are authority-bearing and were in neither inventory. The
shape rules were written from this package's *gate* idioms — `raise`, `_refuse(...)`, a bare
outcome tuple — and could see neither an `if` that returns an outcome member directly nor a
conditional expression that decides whether an outcome is read at all. The suite was killing
both the whole time, so this is a denominator defect, not a coverage one: the total was
short by two and `test_guard_inventory.py` pinned the short number.

Measured, neutralising each:

| | `:1101` collapsed to `else` | `:1102` neutralised |
|---|---|---|
| typed `COORDINATE_MALFORMED` | → `VERIFICATION_UNAVAILABLE` | preserved |
| typed `INVARIANT_VIOLATION` | → `VERIFICATION_UNAVAILABLE` | preserved |
| stdlib `ValueError` | unchanged | → `None` |
| forged `.outcome = VERIFIED` | unchanged | → **`VERIFIED`** |

`:1102` is the more serious: without it an exception carrying an attacker-influenced
`outcome` attribute becomes a success, which is the one thing the routine's own docstring
says can never happen. `:1101` flattens every typed refusal to "the check could not run"
when the check ran and refused.

**The inventory is 119, not 117**, and the two new shapes are pinned by condition.

### Guard 78 is scored, not unreachable

`verification.py:494` was excluded as `unreachable-behind-earlier-guard`. Its operand is a
property of the Policy Authority's `PolicyResolution` — `core/records.py:334`, a separate
distribution under `>=0.1.0`. `is not True` reads like a defence against a truthy
non-`True`, and it is one: a 0.2.0 returning an `int` flag rather than the `bool` singleton
passes the status and historicity gates and arrives here as `1`.

| | result |
|---|---|
| undrifted 0.1.0 | **VERIFIED** |
| drifted 0.2.0, guard present | refused `HISTORICAL_RESOLUTION_REFUSED` |
| drifted 0.2.0, guard neutralised | refused `INVARIANT_VIOLATION` |

A changed typed pair. The neutralised case is worse than it looks: the pairing invariant at
`verification.py:266` catches it instead, reporting an internal integrity failure where the
guard would have given the caller the specific refusal.

The exclusion's measuring test asserted only that the attribute is a property and that the
exact-type gate exists — both still true under the drifted resolution, so it would have gone
on passing. It is replaced by two tests that measure the guard.

**The split is 109 `SCORED` / 10 `EXCLUDED`.**


## [Unreleased] — four exclusions withdrawn; the reason that held them is empty

*No version bump and no production behaviour change.* Phase 5A's guard 9 disproved the
rationale shared by every guard carrying `unscorable-by-single-checkout-fixture`: the
fixture installs one dependency resolution, but a test can construct another. The four
this package carried were re-measured under that instrument and all four are scorable.

| Guard | Condition | Upstream, constraint | Drift the second resolution applies | Present | Removed |
|---|---|---|---|---|---|
| 12 `identifiers.py:186` | `VERIFICATION_PROFILE == …PROTOCOL_ID` | `ugence-policy-authority>=0.1.0` | protocol renamed onto this package's profile | `AssertionError` | imports; profile and protocol are one string |
| 13 `identifiers.py:191` | `…DIGEST_DOMAIN == POLICY_BODY_DIGEST_DOMAIN` | same | policy-body domain adopts the artifact domain | `AssertionError` | imports; one tag serves both frames |
| 15 `identifiers.py:210` | `REQUIRED… is FORBIDDEN_KEY_ENTITLEMENT` | same | `REVOKE_POLICY = "ISSUE_POLICY"` | `AssertionError` | imports; the two are one member |
| 16 `identifiers.py:224` | `CANONICAL_ACTION_TYPES != _RATIFIED_…` | `…authorization-contracts>=0.1.0` | the chain ratifies a fifth action type | `ImportError` | imports; gate 16 selects by five |

Each resolution is built from the real upstream source, not a stub, with every edit
asserted to match exactly once so an upstream rename fails the test rather than quietly
producing an undrifted copy.

Full-suite sweep: **4 guards, 4 killed, 0 survived, 0 unscored**, baseline 476 collected.
**The split is 106 `SCORED` / 11 `EXCLUDED`, not 102 / 15.** The inventory is still 117.

### Two of these were load-bearing in ways the exclusion obscured

Guard 15's operands are *both* upstream's — the case where a single-resolution fixture is
least entitled to conclude anything. Python's `Enum` makes equal values aliases, so a
release merging the two entitlements collapses them to one member and the `is` comparison
goes true. Without the guard, D-5B0B-4's stated reason for choosing the Policy Authority's
key ring over a TEV trust anchor — that entitlement granularity is expressible — is gone,
and a revoke-only key satisfies the issuing requirement. The module docstring says this
cannot happen because there is no parameter to divert; there is no parameter, and this
guard is why that is enough.

Guard 16's first attack measured nothing, and the test records why: adding a fifth
`ActionKind` to the controller alone is refused by Phase 5A's drift guard one package
upstream, producing the identical `ImportError` with and without guard 16. Only a
coordinated drift across the controller, Phase 4C and Phase 5A reaches this guard.

Guard 14 (`identifiers.py:196`) keeps `equivalent-mutant` and was not inferred from the
others: all three of its operands are frozen literals in this distribution, so no
resolution can move any of them.


## [Unreleased] — two exclusions withdrawn; one was the last obstacle before a mint

*No version bump and no behaviour change.* An independent adversarial audit refuted two of
this package's seventeen exclusions. Both were recorded as **measurements** and both
measurements were wrong, so they are withdrawn rather than reworded. Classification is now
**102 SCORED / 15 EXCLUDED** of 117.

### `verification.py:775` — not diagnostic-only; it is the last obstacle before a mint

Recorded as changing only the message. Neutralised, the verifier does not produce a
different refusal: it mints a **VERIFIED** artifact whose `capacity_bounds_fact` carries a
delta ceiling no signature ever covered, and gate 16 then reconciles a candidate's carried
delta against that fabricated ceiling. R-8, defeated through the one guard declared not to
matter.

The isolating input needs nothing exotic. A `Mapping` is not obliged to make `in` and `[...]`
agree: a `collections.defaultdict` reports a missing key *absent*, so the canonical key set
is unchanged and gate 14 still reproduces the signed body digest, while fabricating a value
on subscript. The policy is genuinely issued and signed with a three-key bound; only the
published projection lies — which is precisely the compromised-port threat this boundary
re-checks for.

### `verification.py:772` — a scalar entry moves the outcome

Recorded as having no isolating input. All three recorded attempts were sequence-typed — a
string, a string containing the four field names, a list of them — and every one lands on
`POLICY_BOUNDS_MALFORMED`. A **scalar** does not: `"action_type" not in 5` raises
`TypeError`, and that line sits *outside* the `except Exception` backstop, which wraps only
the `VerifiedCapacityBound(...)` construction below. The outcome moves to
`VERIFICATION_UNAVAILABLE` — an availability failure inviting a retry, in place of a
determination about the policy.

### What both failures have in common

Each recorded a **universal** — "every non-Mapping entry", "no input separates it" — after
testing a handful of cases from a single family. A failed isolation attempt is evidence
about the inputs tried, never about the inputs not tried, and an exclusion that states
otherwise is a claim the sweep cannot check. The two reasons are replaced by killing tests.

## [Unreleased] — 56 survivors, and why this package excludes more than Phase 5A

*No version bump and no behaviour change.* The partition, the profile version and every
frozen digest are unmoved.

With the artefact gone, the first honest sweep of this package reported **117 inventoried,
61 killed, 56 survived**. Every survivor is now resolved: **100 SCORED, 17 EXCLUDED**.

### Why seventeen exclusions, against Phase 5A's five

Structural, not a difference in rigour. Phase 5A raises a distinct exception type per
failure, so removing a guard usually changes the class a caller sees. This package refuses
through a **coarse outcome vocabulary with fine-grained guards behind it**: several guards
narrow the *message* while sharing one `PolicyAuthenticityOutcome` with the guard on the
next line. ADR Phase 5 §9.1 ratifies the outcome as the contract and the message as prose,
so those guards change no authorization answer and are `diagnostic-only`.

Every one of them was attacked for isolation first, and each attempt was recorded as
impossible *by construction* rather than merely unsuccessful. Two of the four claims below
were not:

- ~~a historical resolution cannot also imply current validity — the attribute is a
  read-only property equal to `resolved and not historical`~~. **Withdrawn.** That property
  is the Policy Authority's, under `>=0.1.0`; a 0.2.0 dropping the historicity term makes
  the successor silent. Guard 77 is `SCORED` — see *Guards 77 and 99 are scored* above;
- `None` cannot pass an exact-`str` check or a `Mapping` check, so a missing descriptor
  field always trips its successor;
- ~~an adapter id that disagrees with the record cannot reframe to the signed body digest,
  because the adapter id is an input to the frame~~. **Withdrawn.** The frame is the Policy
  Authority's; a 0.2.0 that stops binding the adapter makes the reproduction independent of
  it and removing the guard **mints**. Guard 99 is `SCORED`;
- a `None` registry, verifier or port never satisfies the `hasattr` behind it.

The two surviving claims are facts about the Python language — `None` satisfies no
`isinstance`, `hasattr` or exact string comparison, whichever release supplies the type.
The two withdrawn ones were facts about the installed Policy Authority, offered as facts
about the program. ADR Phase 5 §9.2 now states the distinction as one rule for every
exclusion reason.

Four more are `unscorable-by-single-checkout-fixture` (§9.2) and three are genuine
equivalent mutants over this module's own frozen constants.

### Two guards that read as diagnostic-only and decide whether a candidate verifies

Both were reasoned into the exclusion pile before being measured, and both are the reason
the "record a failed isolation attempt before excluding" rule exists.

- **`verification.py:836`** — R-8's ratified-vocabulary check. Neutralised, a candidate does
  not get a different refusal: it **VERIFIES**. An authority can sign a capacity bound under
  an action type D-4 never ratified; a candidate carrying the same type then selects it. The
  first attack forged only the candidate's action type and left the signed bound ratified,
  which produced a selector miss with the same outcome and measured nothing.
- **`verification.py:758`** — the bounds-sequence check, one line above a guard that looks
  identical and *is* diagnostic-only. A dict or string is iterable and falls through to the
  entry check with the same outcome; an **int** is not iterable at all, so without this
  guard `enumerate(7)` raises and the outermost handler reports `VERIFICATION_UNAVAILABLE`.
  That tells a caller to retry a policy that will never become readable, instead of telling
  them the policy's bounds are malformed.

### Two findings worth more than the tests that found them

- **`canonical.py` had never been reached at all.** All ten of its guards survived. These
  are the admission primitives every field in the package passes through; the suite
  exercised the artifacts they protect and never the helpers themselves, so any of them
  could have been deleted without a test failing.
- **R-8's ceiling-typing guard has an unreachable loop position.** It checks four carried
  values, and `requested_delta` is a derived *property* of `ExecutionTargetScope`
  (`requested_magnitude - magnitude_before`) with no setter — always an `int` by
  construction. The other three are covered and the fourth is recorded as unreachable, so a
  later reader does not read its absence as an oversight. The `bool` case the guard names
  explicitly is not pedantry: `True > 1` is `False`, so a boolean ceiling would compare as
  satisfied against any authenticated bound above 1.

## [Unreleased] — the 115/115 result was an artefact, and is withdrawn

*No version bump and no behaviour change.* The partition, the profile version and every
frozen digest are unmoved. What moves is a claim.

### Withdrawn

The previous entry reported **all 115 guards killed, no survivors**. That result is void.
The sweep copies the package to a disposable directory, which was named `package`; this
package's own `test_phase5a_untouched.py` asserts `here.name ==
"cloud-scaling-policy-authenticity"`, so that test failed in **every** run of the sweep —
baseline and mutant alike. A mutant counted as killed whenever any test failed, so every
guard was credited with a kill it had not earned. The copy was not a faithful stand-in for
the package, and the sweep measured the copy.

It was found by the audit-mandated change that refuses a baseline which is not green, which
is exactly the failure that change exists to catch. The engine now also names the copy after
the package, and counts only failures the baseline did not already have.

### Added

- Two guards a raise-only reading missed, now inventoried: `verification.py:327`
  (`require_production_resolution_port`) and `verified.py:488` (`require_phase5a_digest`).
  Each is an `if` whose entire body is a call to an admission helper. The inventory is
  **117**, and a raise-only reading of this package would miss 47 of them.

## [Unreleased] — the sweep is measured, and every guard is classified

*No version bump and no behaviour change.* Coverage and CI only; the partition, the profile
version and every frozen digest are unmoved.

The first complete CI mutation sweep of this package neutralised all **115** authority-
bearing guards and ran the whole suite against each. **All 115 died. No survivors, none
unscored** — so every guard is classified `SCORED`, and this package declares no exclusion
at all.

That total depends on this package's own definition of a refusal. Phase 5A refuses by
`raise`; this package also refuses by *returning* `_refuse(outcome, detail)` at a gate and
`(_Outcome.X, "…")` from the helper that decided it. A raise-only inventory misses 17 real
gates here, gate 13's exact-type instant check and all six R-8 bound-reconciliation branches
among them — the gates most recently added. Each of those seven appears individually in the
aggregated result, and each was killed.

### Added

- `guard_classification.json` (generated, tracked) — all 115 guards, each `SCORED`.
- The same six blocking aggregate conditions as the Phase 5A workflow: inventory drift, an
  unclassified guard, an invalid or orphaned exclusion, a `SCORED` guard that survived, a
  stale exclusion, a missing shard, a duplicated result, and a shard that collected a
  different population.

## [0.8.0] — gate 13 re-checks the six carried instants by exact type

**No partition change and no profile bump.** `VERIFICATION_PROFILE_VERSION` stays `v4` and
every frozen digest is unmoved. This changes which inputs produce an artifact — a candidate
carrying a lying `datetime` subclass no longer produces one — not what an artifact contains,
nor what it establishes about an input that was already exactly typed.

### Fixed — the residual the ratification ADR ruled on and 5B-3 left open

Phase 5A admits the six carried instants exactly in `__post_init__`. This package accepts a
candidate object it did not build, and both `object.__new__` and `pickle` construct one
without running `__post_init__` at all — so that admission was never something this boundary
could inherit.

Measured before the repair, one field at a time, with a plain-`datetime` control for each:

| Carried instant | plain `datetime` at the same value | `datetime` subclass |
|---|---|---|
| `subject_valid_from_fact` | `CANDIDATE_RECOMMENDATION_NOT_YET_VALID` | **VERIFIED** |
| `subject_valid_until_fact` | `CANDIDATE_RECOMMENDATION_EXPIRED` | **VERIFIED** |
| `subject_asserted_at_fact` | `CANDIDATE_FACT_NOT_YET_OCCURRED` | **VERIFIED** |
| `decision_evaluated_at_fact` | `CANDIDATE_FACT_NOT_YET_OCCURRED` | **VERIFIED** |
| `decision_expires_at_fact` | `CANDIDATE_DECISION_EXPIRED` | **VERIFIED** |
| `attestation_issued_at_fact` | `CANDIDATE_FACT_NOT_YET_OCCURRED` | **VERIFIED** |

Four overridden comparison operators were the whole attack, and no digest could see it:
`to_canonical_obj` renders a subclass to exactly the string a plain `datetime` produces, so
`candidate_digest` never moved. The type is the only place the difference survives.

`CANDIDATE_FACT_NOT_EXACT_INSTANT` refuses it, **before** the window comparisons rather than
beside them — a value that lies about `<` and `>` cannot be caught by comparing it. Among
exactly-typed candidates the existing refusal order is untouched, which the suite asserts
rather than assumes.

`pickle` and `deepcopy` are covered too: the gate is written against the property, not
against `object.__new__`.

## [0.7.0] — R-8 reconciliation: the authenticated bound and the candidate's meet

**Profile bump with no partition change.** `VERIFICATION_PROFILE_VERSION` moves from `v3` to `v4` because gate 16 changes what a determination establishes about a candidate, and every frozen artifact digest moves with it.

No fact is promoted, demoted or added: gate 16 changes what a determination
*establishes*, not what an artifact contains. That is what a profile version names, and a
consumer must not read a `v3` and a `v4` artifact as making the same claim.

The cost is stated rather than hidden: the profile version is inside the artifact, so every
frozen artifact digest moved even though membership did not. Each was regenerated by
measurement and its `v3` value pinned as a negative anchor. `test_the_v3_digests_are_never_produced_again`
is the first supersession in this package that holds membership constant across the move,
which is what makes it a measurement of the fingerprint tracking the profile version.

### Added — gate 16, the candidate's ceilings against the authenticated ones

5B-3 added *extraction*: gates 14 and 15 reproduce the signed body digest and read the
capacity bounds out of it. Nothing compared those bounds against the candidate, so a
candidate self-asserting 20/5 verified `VERIFIED` against a genuinely issued bound of 5/1 for
its exact selector. Extraction is not reconciliation.

- A candidate's `max_permitted_magnitude`/`max_permitted_delta` may be **narrower** than the
  authenticated bound and must never exceed it — `<=`, not equality, so a caller may bind
  itself more tightly than the policy does.
- The **request** is compared against the authenticated bound too. Phase 5A already compares
  it against the candidate's own copy of the ceiling; this check does not depend on that copy
  being honest.
- Selector matching is **exact and fail-closed**: `(action_type, resource_class)`, with
  `action_type` one of D-4's four canonical values. `None`, `""`, case, whitespace and an
  unspecified selector are none of them equivalent, and none is a wildcard. A wildcard, if it
  is ever wanted, is an explicit schema addition.
- Four typed refusals — `CANDIDATE_POLICY_STATES_NO_BOUNDS`, `CANDIDATE_BOUND_SELECTOR_MISS`,
  `CANDIDATE_BOUND_SELECTOR_AMBIGUOUS`, `CANDIDATE_BOUND_EXCEEDED` — in a pinned precedence.
  Never `VERIFIED` without an applicable authenticated bound.
- Without a candidate there is nothing to reconcile, and a policy stating no bound remains a
  legitimate determination. It is the *pairing* that is refused.

No new fact. Which bound applied is derivable exactly from `capacity_bounds_fact` and the
candidate's selector, both already carried, and a redundant scalar is a second thing to keep
true.

### Fixed — a fixture that could never exercise the gate it existed for

The reference bounds body stated `action_type="cloud_scaling.scale_out"` with
`resource_class=""`. Neither can match a genuine candidate: `scale_out` is not one of D-4's
four canonical action types, and `""` is not the candidate's resource class. Under exact
matching that bound was unselectable, so every bounds test ran against a policy that could
never bound anything. It now states the candidate's own selector, plus a second selector so a
selector *miss* has something real to miss against.

### Measured, not assumed

`CANDIDATE_POLICY_STATES_NO_BOUNDS` is reachable only for a policy family that supplies no
bounds at all: an *empty* bounds tuple inside the bounds family is refused earlier, by gate
15. And neutralising the ambiguity branch does **not** admit — a duplicate selector trips the
artifact's own integrity check downstream as `INVARIANT_VIOLATION`. That branch supplies the
*diagnosis*, not the only refusal, and the suite says so rather than claiming otherwise.

## [Unreleased] — the ratchet's fourth rule: a fact that appears, not moves

*No partition change and no profile bump in this entry.* `VERIFICATION_PROFILE_VERSION` stays
`v3`: this extends the gate that guards the partition, not the partition.

### Added — D-5B1-3 rule 4

Rule 3 disclosed only facts that **moved** halves: `promoted` was
`current.verified ∩ baseline.recorded` and `demoted` its mirror. A name entering the verified
half from neither baseline half is in neither set. It had not moved, it had appeared — so it
was promoted by nobody, demoted by nobody, and the rule asked no question about it. The profile
bump such a change forces was already earned by whatever else moved, and the changelog line
that bump owes rule 2 says only that the version moved. A reader saw a version change and never
learned which fact had begun carrying authority.

`ratchet_problems` now also reports `current.verified − baseline.verified − baseline.recorded`,
disclosable only as `added: <fact> — …`. The direction is part of the claim: a `promoted:` line
for a fact that never moved asserts something false about where it came from and does not
satisfy the gate.

### Fixed — one historical disclosure reclassified

5B-3's `capacity_bounds_fact` line read `promoted:` while its own text said "new in this
release". Under rule 4 it is an addition; the line now reads `added:`. The gate refused the
working tree until it did, which is the rule working on the first real case it met.

## [0.5.0] — Cloud Scaling Phase 5B-3: close R-8, the authenticated capacity bound

Ratified as Route 1 + Route 2 as one isolated subphase. **Breaking**, pre-1.0: a determination
that verified at `0.4.0` may be refused at `0.5.0`, and every artifact digest moves.

**Partition change and profile bump.** `VERIFICATION_PROFILE_VERSION` moves from `v2` to `v3`,
because a fact moved between the verified and recorded halves and a new verified fact was
added. The artifact digest and the partition fingerprint move with it. Both prior values are
kept as negative anchors in `tests/test_frozen_digests.py`, so reverting the promotion fails
rather than passes.

- promoted: `policy_type` — gate 14 now reproduces `record.policy_body_digest` by reframing
  `(adapter_id, policy_type, projection)` through the Policy Authority's own
  `framed_body_digest`, and `policy_type` is one of the three inputs to that frame.
  Substituting it makes the record and the published projection disagree, and the
  determination is refused. It sat in the recorded half only because the pre-image was
  unavailable here — the value is committed inside `policy_body_digest`, but a hash is one-way
  and this package holds no adapter registry with which to re-derive the descriptor. Route 1
  supplied the pre-image by publishing the descriptor's projection on `PolicyResolution`.
  `tests/test_unattested_facts.py` keeps the test that measured the gap and **inverts** its
  assertion rather than deleting it.
- added: `capacity_bounds_fact` — new in this release, and verified from the moment it
  exists rather than parked in the recorded half first. Gate 15 reads the bounds out of a
  projection gate 14 has already reproduced, so they are the bounds the issuance signature
  covered. `None` means the resolved policy is not a capacity-bounds policy and states no
  bound; it never means the action is unbounded, and never means a bound was carried
  unchecked. Same posture as `candidate_digest_fact`: "verified" means the routine correctly
  evaluated the input including its absence.

### Added — gate 14, the projection reproduces the signed body digest (R-8)

Three new refusals, and the first is the load-bearing one:

* `POLICY_PROJECTION_ABSENT` — the resolution published no descriptor projection. Refused
  rather than degraded: a port whose answer cannot be independently reproduced here is one
  this package cannot check, and carrying the facts unchecked is exactly the posture 5B-3
  exists to end. The three fields arrive together or not at all upstream, but this boundary
  re-checks each — it accepts a `PolicyResolution` it did not construct.
* `POLICY_PROJECTION_DIGEST_MISMATCH` — the projection, the adapter id or the policy type is
  not what the signature covered.
* `POLICY_BOUNDS_MALFORMED` — gate 15. A digest match proves the bytes are the signed bytes;
  it does not make an unreadable structure readable. A bound carrying a field this profile
  does not know is refused rather than summarised, because a lossy reading of a signed body
  is not a verified fact.

### Added — `VerifiedCapacityBound`

This package's own exact-typed carrier for an authenticated ceiling. Deliberately **not** the
capacity-bounds family's `CapacityBound`: importing that would make the verifier depend on the
family it verifies. The bounds are read structurally out of the reproduced projection, keyed
on the resolved coordinate's `policy_family`, so a foreign family carrying a `bounds` key is
not read as a bounds statement.

### What R-8 actually required

Not "compare the bounds". The verified artifact carried 26 facts and not one was a bound, so
there was nothing to compare against — and no shipped policy family stated a capacity bound at
all. The prerequisite shipped alongside this release as
`ugence-cloud-scaling-capacity-bounds-policy`, a leaf distribution this package does **not**
depend on. Its declared-dependency set is unchanged.

### Deliberately not done

* **No comparison against the candidate.** The bounds are carried, not reconciled against
  `max_permitted_magnitude` / `max_permitted_delta`. That is a later subphase with its own
  ruling.
* **No change to the Phase 5A candidate contract**, and therefore no re-pin in
  `cloud-scaling-producer-attestation`. That package declares no dependency on the Policy
  Authority or on this one; its 5B-1 re-pin was caused by the candidate contract gaining a
  policy coordinate, which moved `PHASE_5A_CANDIDATE_DIGEST`. Nothing here touches it.
* **`FROZEN_TRUST_CONFIGURATION_DIGEST` does not move.** The subphase's own ruling predicted it
  would, on the grounds that the registered adapter set changes. It does not: the reference
  determination still resolves the same UVI fixture policy under the same registry. The
  adapter-set sensitivity is anchored instead by the new
  `FROZEN_BOUNDS_TRUST_CONFIGURATION_DIGEST`, under a registry whose only adapter is the
  bounds family's. Re-pinning the reference constant would have anchored a fiction.

## [0.4.0] — Cloud Scaling Phase 5B-2 part 2: R-2 and R-7

Ratified in `docs/architecture/ADR_CLOUD_SCALING_DECISION_SCOPE_PHASE5B1_RATIFICATION.md`,
owner ruling on the remaining residuals. **Breaking**, pre-1.0: a candidate-bearing
determination that verified at `0.3.0` may be refused at `0.4.0`.

**No partition change and no profile bump.** `VERIFICATION_PROFILE_VERSION` stays `v2`: no fact
moved between the verified and recorded halves, so the artifact digest and the partition
fingerprint are unchanged. What changed is which inputs produce an artifact.

### Added — gate 13, the candidate must be valid AT the verified instant (R-2)

`as_of` is the authoritative verification instant injected by the composition root; this
package still reads no clock. What is new is that the instant is reconciled against the
candidate's own carried validity rather than recorded beside it.

Four typed refusals, not one generic staleness:

- `CANDIDATE_RECOMMENDATION_NOT_YET_VALID` — `as_of` precedes `subject_valid_from_fact`.
- `CANDIDATE_RECOMMENDATION_EXPIRED` — `as_of` is past `subject_valid_until_fact`.
- `CANDIDATE_DECISION_EXPIRED` — `as_of` is past `decision_expires_at_fact`. Checked
  independently: a live recommendation can carry a dead decision.
- `CANDIDATE_FACT_NOT_YET_OCCURRED` — `as_of` precedes `subject_asserted_at_fact`,
  `decision_evaluated_at_fact` or `attestation_issued_at_fact`; the detail names which.

The six timestamps are classified from the upstream contracts rather than from their names:
the subject interval is inclusive on both ends, matching
`cloud-scaling-risk-integration`'s `_require_within_validity` (`now > valid_until` /
`now < valid_from`), and the decision bound matches Risk Authority's `now > expires_at`. A
boundary that disagreed with the seam above it about which instants are admissible would be a
second opinion, not a second check.

**R-2 was recorded wrongly and is corrected in the ADR.** It read as "whose clock supplies
`as_of`". Measurement showed `as_of` was already type-checked and round-tripped, and that the
authority already refuses a revoked policy *even at an instant before its revocation*. What was
open was the missing reconciliation, and this suite's own fixtures demonstrated it: every
candidate-bearing test verified at `T_MID`, five months after the fixture candidate's
recommendation expired, and nothing objected. Those fixtures now state an honest instant
(`T_CANDIDATE`).

### Added — the partition maps agree with one canonical declaration (R-7)

`DERIVED_FACT_NAMES` names the three digest-covered non-fields (`outcome`, `grants_authority`,
`historical`) that were previously reconciled by an unnamed tuple, and `VERIFIED_DIGEST_KEYS`
states the verified half's membership once. `require_partition_agreement` compares both payload
maps against the declaration before anything is minted, raising the package's
`INVARIANT_VIOLATION`. Membership went from three uncompared places to one declaration plus a
mint-time check. R-7 remains what it was recorded as — a maintenance hazard, not a correctness
one — but it now fails loudly and says which side is short.

### Changed

- Suite 289 → 309, 0 failed, 0 skipped. Both new guards were neutralised and observed to fail
  (7 properties for gate 13, 4 for the agreement check) before being trusted.

## [0.3.0] — Cloud Scaling Phase 5B-2 part 1: R-9

Ratified in `docs/architecture/ADR_CLOUD_SCALING_DECISION_SCOPE_PHASE5B1_RATIFICATION.md`,
owner ruling on the three residual decisions.

**No partition change and no profile bump.** `VERIFICATION_PROFILE_VERSION` stays `v2`: no
fact moved between the verified and recorded halves, and the artifact digest and partition
fingerprint are unchanged. What changed is which inputs produce an artifact at all, not what
an artifact contains.

### Added

- Gate 12, closing **R-9**: a `TENANT`-scoped policy bounds only its own tenant's action.
  Refused as the new outcome `CANDIDATE_CROSS_TENANT_POLICY`.
- Outcome member `CANDIDATE_CROSS_TENANT_POLICY`. Distinct from
  `CANDIDATE_COORDINATE_MISMATCH` on purpose: there the two artifacts are about different
  policies, here they agree about the policy and the disagreement is over whose action it may
  bound. Reporting one as the other would send a reader looking for a disagreement that is
  not there.

Phase 5A refuses the same pairing at construction, and neither site is redundant. This
boundary accepts a candidate object it did not build, so it cannot inherit that discipline: a
candidate is shape- and digest-validated by its type but carries no cross-field policy guard
there, so an internally consistent cross-tenant candidate can exist without the builder ever
having produced one. The suite constructs exactly that, and with gate 12 neutralised it
verifies `VERIFIED` — the residual, reproduced at this boundary.

The resolved coordinate is the authority for the comparison, not the candidate's copy of it:
gate 11 has already forced the two to agree, and reading the resolved side keeps the answer
independent of what the candidate claims about itself.

### Changed

- Depends on Phase 5A `0.3.0`. Suite 286 → 289, 0 failed, 0 skipped.

## 0.2.0 — Cloud Scaling Phase 5B-1: decision-scope repair

Ratified in `docs/architecture/ADR_CLOUD_SCALING_DECISION_SCOPE_PHASE5B1_RATIFICATION.md`.

### Added — gate 11, candidate reconciliation (D-5B1-1, closing ADR residual R-4)

- A supplied candidate's `PolicyTargetBindingReferenceV2` is reconciled against the resolved
  policy: all six coordinate components, `policy_body_digest`, and the issuing identity
  (`issuing_authority_id`, `key_id`, `signature_alg`). A disagreement is the new
  `CANDIDATE_COORDINATE_MISMATCH` — a refusal, because the proof and the candidate are handed
  to a consumer together and a proof about policy A beside a candidate about policy B is a
  misstatement however genuine each half is.
- The verification routine now runs **eleven** ordered gates, not ten. The candidate stays
  optional; omitting one is not a refusal.
- Before Phase 5A `0.2.0` this comparison could not be made at all: a Phase 5A binding carried
  three of the coordinate's six components and its fourth was in the wrong digest namespace,
  so one genuine policy proof verified alongside any candidate whatsoever. That was R-4.

### Changed — the promotion, and what it cost

- promoted: `candidate_digest_fact` — gate 11 reconciles a supplied candidate's policy
  coordinate against the resolved policy, so the fact this artifact carries about which
  candidate it accompanied is now checked rather than merely recorded. This line's shape is
  load-bearing: the ratchet requires every fact that changes halves to be disclosed as
  `promoted: <fact>` or `demoted: <fact>` on its own line, so that a version bump earned by
  one promotion cannot carry a second, undisclosed one along with it.
- `candidate_digest_fact` moved from the **recorded** half to the **verified** half.
  `VERIFICATION_PROFILE_VERSION` moves to `v2` in the same commit, as the ratchet requires,
  and the reference artifact digest moved with it:
  `8b0ea25f…` → `f245511d…`. The partition fingerprint moved `86d39d25…` → `242ac003…`.
  Both superseded values are pinned as negative anchors.
- `RECORDED_FACT_NAMES` is now three members: `resolved_as_of_fact` (R-2, still open),
  `policy_type` and `trust_configuration_digest`. The recorded half's domain tag does not
  move — the frame is unchanged, only its membership.
- `None` on `candidate_digest_fact` means **no candidate accompanied the determination**. It
  never means one was carried unchecked: a candidate that does not reconcile mints no artifact.
- The distribution moves to `0.2.0`. Phase 5A moves to `0.2.0` independently, and one of its
  frozen digests moved; `tests/test_phase5a_untouched.py` is amended rather than deleted,
  because its purpose — a change to Phase 5A surfaces in a package that depends on it —
  survives the superseded premise it was written for.
- `tests/test_candidate_not_bound.py` is replaced by `tests/test_candidate_reconciliation.py`.
  The old module measured the residual and asserted `VERIFIED` for a candidate naming another
  policy; the new one asserts the refusal.

### Still open

- **R-2** — `resolved_as_of_fact` stays in the recorded half. Whose clock supplies `as_of` is
  5B-2's work, and a determination reached at an attacker-chosen instant can still resolve a
  policy that is revoked, expired or not yet effective *now*.
- **A-59 (5B-0A)** — the producer attestation binds the recommendation, not the candidate.
  Reconciling the policy does not reconcile the producer's signature to this candidate.
- Bound extraction — that the candidate's `max_permitted_*` are the bounds the verified policy
  body states — remains 5B-2's.

### Added — the partition ratchet (D-5B1-3)

- `tests/test_partition_ratchet.py` and `tests/_partition_ratchet.py`. The partition
  fingerprint pinned in `tests/test_frozen_digests.py` was a **pin, not a ratchet**: the 5B-1
  audit measured that promoting `candidate_digest_fact`, updating the two pinned constants and
  leaving `VERIFICATION_PROFILE_VERSION` at `"v1"` passes that file at 5 passed. Updating a pin
  is exactly as cheap as the change it gates, because both land in the same commit.
- The ratchet takes its "before" from **repository history** — the membership recorded at the
  merge base, parsed out of the historical source rather than imported — and fails when the
  verified/recorded partition moved without a `VERIFICATION_PROFILE_VERSION` bump, or when the
  version moved with no changelog line naming it.
- It lands **before** the promotion it exists to catch, with negative controls that drive a
  promotion-without-a-bump and a bump-with-a-silent-changelog through the gate and observe it
  fail. A guard built after the first promotion would have missed the one event it is for.
- CI resolves the baseline from the event's own default branch and sets
  `UGENCE_RATCHET_REQUIRED=1`, so a baseline that cannot be resolved fails the workflow
  instead of skipping quietly. Outside a checkout the gate skips, as the suite's other
  repository-dependent properties do.

## 0.1.0 — Cloud Scaling Phase 5B-0B: policy authenticity

First release. Adds a distribution; changes none.

### Added

- `PolicyAuthenticityVerifier` — the authoritative routine. Ten ordered gates, stopping at the
  first failure, deterministic, fail-closed. An unexpected exception becomes
  `VERIFICATION_UNAVAILABLE`, which is a refusal.
- `PolicyResolutionPort` with `PolicyAuthorityResolutionPort` (the one production-grade seam
  to the Policy Authority's trusted-resolution path, pinning the fail-closed historical rule
  and reporting its trust-configuration identity) and `DenyAllPolicyResolutionPort` (the
  production-admissible "trust not configured" posture).
- `VerifiedPolicyAuthenticity` — the exact-typed, immutable, non-authoritative result. Minted
  only by the routine, guarded by a construction token, a self-digest, a provenance registry
  and `require_verified_policy_authenticity` revalidation at every consumption boundary.
- `PolicyAuthenticityOutcome` — a closed vocabulary with exactly one success. Every Policy
  Authority refusal reason maps across one-for-one and injectively; an unrecognised reason
  becomes `INDETERMINATE`, which is a refusal.
- `policy_trust_configuration_digest` — the identity of one policy trust configuration,
  computed from the anchors' governing attributes and never from key material.

### Ratified decisions implemented

- **D-5B0B-1** — the verified artifact is a `RESOLVED`, non-historical `PolicyResolution`.
- **D-5B0B-2** — `policy_body_digest` is the content binding. The two digest namespaces (bare
  64-hex for the Policy Authority, `sha256:`-prefixed for Phase 5A) are validated separately
  and never converted.
- **D-5B0B-3** — all six coordinate components are carried; a Phase 5A binding cannot name a
  coordinate, so none is derived from one.
- **D-5B0B-4, option (a)** — policy signatures are verified through the Policy Authority's own
  `PolicyKeyRing`. No Trusted Evidence Authority dependency exists, and an import-boundary test
  makes that unreachable rather than merely unused.
- **D-5B0B-5** — "is valid now", at an injected `as_of`. No clock is read anywhere.
- **D-5B0B-6** — the proof travels alongside the candidate. Phase 5A stays at `0.1.0`; this
  suite re-runs its frozen-digest tests to prove all ten are unmoved.

### Audit remediation (pre-merge, same version)

Three findings from the independent audit of this package, addressed without adding or
removing a verification gate and without touching Phase 5A.

- **The result pair is bound.** `PolicyAuthenticityResult` now cross-checks the verified
  artifact against the `PolicyResolution` it carries, on the coordinate and on
  `policy_body_digest`. Two individually genuine halves about different policies are a
  misstatement — a consumer reading the body out of the resolution would read a body the
  proof does not cover — and the pair is refused as one.
- **The trust identity is snapshotted at verifier construction** and every determination is
  minted from the snapshot, so a port cannot report one identity when it is admitted and
  another when the artifact is stamped.
- **Typed outcomes survive the terminal handler.** An escaping error of this package's own
  types keeps the member it carries (`COORDINATE_MALFORMED`, `INVARIANT_VIOLATION`, …);
  anything else is `VERIFICATION_UNAVAILABLE`. "The check could not run" and "the check ran
  and the artifact is bad" are different facts. An exception claiming `VERIFIED` never
  becomes one.

### D-5B0B-7 — the digest payload partitions (ratified, implemented at the same version)

`VerifiedPolicyAuthenticity.digest_payload()` is now two separately framed maps, each carrying
its own domain tag as a canonical field:

- **`verified`** — the facts a gate checked;
- **`recorded`** — carried and digest-covered but never attested. Exactly
  `resolved_as_of_fact` (R-2: injected, unvalidated) and `candidate_digest_fact` (R-4:
  recorded, never reconciled).

Both halves remain inside the artifact digest, so neither can be rewritten; what the partition
adds is that the frame a fact sits in is part of what the digest commits to. Promoting a fact
into the verified half — what 5B-1 and 5B-2 do when they close R-4 and R-2 — therefore moves
the artifact digest instead of silently relabelling it.

`verified_fact(name)` and `recorded_fact(name)` each refuse the other's half, so an unattested
value cannot be read through a call that reads as attested. `VERIFIED_FACT_NAMES` and
`RECORDED_FACT_NAMES` are exported, and an import-time guard refuses a field in neither set.

No gate was added or removed (still ten), the distribution stays at `0.1.0`, and no Phase 5A
frozen digest moved.

### Second audit round (pre-merge, same version)

Three further findings. **No verification gate was added or removed — the routine still runs
ten — so `VERIFICATION_PROFILE_VERSION` stays `v1`.** Two facts moved from the verified half
to the recorded half, which does move every artifact digest; that is safe only because nothing
downstream pins one yet and no verification artifact crosses a process boundary.

- **`policy_type` moves to `recorded`.** It is absent from the 21 keys of
  `IssuedPolicyRecord.signing_payload()` (`adapter_id` is present; this is not), and
  `resolve_policy` recomputes the body digest from the *descriptor's* `policy_type`, never the
  record's — so a record differing only in that field resolves `RESOLVED` and minted a
  `VERIFIED` artifact carrying the substituted value. No gate is available: the fact is
  transitively committed inside `policy_body_digest`, whose frame includes it, but a hash is
  one-way and this package holds no adapter registry with which to re-derive the descriptor.
- **`trust_configuration_digest` moves to `recorded`.** It was port-self-reported and checked
  only for shape, so a wrapper delegating to a genuine `PolicyAuthorityResolutionPort` while
  reporting an arbitrary well-formed digest minted an artifact carrying that value. No gate is
  available either: the port *is* the seam to the authority, so any check would be the port
  vouching for itself. The construction-time snapshot is kept — it stops drift between
  admission and minting — but it does not make the value true, and the docstrings now say so.
- **The result pair binds which answer, not only which policy.**
  `PolicyAuthenticityResult` now also requires the carried resolution to be non-historical and
  to have been reached at the instant the artifact reports. A genuine artifact previously
  paired cleanly with a genuine `historical=True` resolution of the same policy — same
  coordinate, same body digest, `implies_current_validity=False` — and with one reached at a
  different `as_of`.

### Residual closed at this boundary

- **R-3** — `resolve_policy` does not re-enforce `coordinate.content_digest ==
  policy_body_digest`. Reproduced with a synthetic decoupling adapter and refused here as
  `COORDINATE_DIGEST_UNBOUND`. `tests/test_coordinate_gap.py` also pins the residual itself, so
  a future Policy Authority fix surfaces as a failing test rather than as a silently redundant
  gate.

### Residuals carried, not closed

- **R-2** — whose clock supplies `as_of`, and what makes it trustworthy. Open by ruling; this
  implementation proceeds with `as_of` injected and unvalidated. 5B-2's work.
- **R-4** — binding the verified policy proof to the recommendation and target scope. 5B-1's
  decision-scope repair. `candidate_digest_fact` records scope, never a binding.
