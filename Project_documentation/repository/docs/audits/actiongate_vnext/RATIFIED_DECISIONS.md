# ActionGate vNext — ratified decisions and dimension matrix

Status: **owner-ratified**. Supersedes nothing; this is the first decision record
for the ActionGate vNext evaluator. It records what was decided, what was built
against it, and what remains open.

Second pass: the five items left open by the first pass are settled below as
D6-D10, and a regression the first pass did not measure is recorded with them.

Audit basis: the two read-only audits of `packages/providers/actiongate`,
`cyber_security/action_gate_reference`, `packages/governance-contracts`,
`packages/governance-provider-framework`, and
`packages/capabilities/action-clearance`.

## The defect this addresses

`[V]` The pre-vNext ActionGate engine branched solely on `action_type`
(`core.py:151-168`). Seven mapped governance dimensions — principal, authority,
resource, parameters, risk_context, evidence_refs, decision_refs — were never
read. Two requests differing in all seven, plus `authorization_expired`,
produced a byte-identical `AUTHORIZED` result with the identical fingerprint
`fff2e619615b`.

`[V]` Every test asserting those dimensions was a `map_request` *preservation*
assertion. Twelve such assertions existed; none asserted that changing a
dimension changed an outcome. A field can survive a mapping perfectly and still
be inert.

`[V]` `authorization_expired` was the one neutral field `map_request` dropped
entirely, while `ActionGovernanceControlPlaneAdapter` computes it
(`action_to_control_plane.py:91`) and the framework's own reference provider
honours it (`reference/action.py:64`).

## Ratified decisions

**D1 — collapsed outcome tiers: reason codes only.**
The reference evaluator's `REQUEST_MORE_EVIDENCE`, `SIMULATE_AND_RETRY` and
`ESCALATE_TO_HUMAN` are carried as reason codes on a single neutral
`INDETERMINATE`, not as new `ActionGovernanceOutcome` values. `[R]` Rationale:
adding neutral enum values is a MAJOR on the shared
`governance_providers.api` surface and would oblige every action provider and
the kernel `OUTCOME_MAP` to absorb it, not just ActionGate. Accepted cost: a
consumer reading only the outcome enum sees three distinct situations as one.

**D2 — dimension posture: hard/soft split.**
Authority, principal and decision-reference failures are boundary violations
(`DENIED`). Risk and evidence failures are uncertainty (`INDETERMINATE`).
`[R]` Rationale: mirrors the reference evaluator, where `_priv_monotonic` is a
hard pre-check yielding `DENY` but an unmet `MUST_HAVE` evidence rule yields
`REQUEST_MORE_EVIDENCE`; and honours `AUTHORIZATION_BOUNDARY.md`'s prohibition
on silently elevating missing authority.

**D3 — equivalence baseline: add a second, keep `before`.**
`actiongate_equivalence_before.json` remains the pre-migration proof; a
post-semantics baseline is added when semantics actually move. `[R]` Rationale:
regenerating in place would permanently destroy the only evidence that the
canonical package ever matched the legacy implementation byte-for-byte.
**Not yet acted on** — no semantics have moved (see "Gate status"), so a second
baseline would today be a duplicate of the first.

**D4 — CABP signing domain: deferred, recorded as a gap.**
`[G]` `grep -rn "CABP"` returns zero hits repository-wide. There is no CABP
domain tag, keyring entry, entitlement value, signing-input guard, verifier,
trust-anchor record, or revocation path. `[R]` Rationale for deferring: domain
ownership is a design decision, and the Trusted Evidence Authority's own ADR
§13.3 requires a domain tag be "fixed before signing exists" — pre-committing an
owner for an artifact class that has no definition inverts that rule.

**D5 — shared severity primitive: keep independent. Ratified (was default).**
`[R]` `ugence_action_clearance.combine_statuses` and `vnext.combine_tiers` stay
separate. See D8 for the evidence that settled it; the layering argument was
never the strongest one.

## Dimension matrix

`resource` and `parameters` were inferred from D2's posture rather than named in
it. Both are now ratified as the matrix states — see D6, which also records why
the hard/soft label carries less runtime force than this table implies.

| Dimension | Posture | Condition | Tier | Reason code |
|---|---|---|---|---|
| `action_type` | hard | in denied set | DENIED | `POLICY_DENIED` |
| `action_type` | hard | in unknown set | ESCALATION_REQUIRED | `POLICY_UNKNOWN` |
| `authority` | hard | required, absent | DENIED | `AUTHORITY_ABSENT` |
| `authority` | hard | present, not accepted | DENIED | `AUTHORITY_INSUFFICIENT` |
| `principal` | hard | required, empty | DENIED | `PRINCIPAL_UNRESOLVED` |
| `principal` | hard | outside allowlist | DENIED | `PRINCIPAL_UNRECOGNIZED` |
| `decision_refs` | hard | required, absent | DENIED | `DECISION_REF_MISSING` |
| `resource` | hard | required, empty | DENIED | `RESOURCE_UNRESOLVED` |
| `resource` | hard | outside permitted prefixes | DENIED | `RESOURCE_NOT_PERMITTED` |
| `parameters` | mixed | exceeds `deny_above` | DENIED | `PARAMETER_LIMIT_EXCEEDED` |
| `parameters` | mixed | above `constrain_above` | AUTH_W_CONSTRAINTS | `PARAMETER_BOUND_APPLIED` |
| `parameters` | mixed | bound declared, unparseable | EVIDENCE_REQUIRED | `PARAMETER_UNRESOLVED` |
| `risk_context` | soft | required, absent | EVIDENCE_REQUIRED | `RISK_CONTEXT_UNAVAILABLE` |
| `risk_context` | soft | in deny scores | DENIED | `RISK_THRESHOLD_EXCEEDED` |
| `risk_context` | soft | in constrain scores | AUTH_W_CONSTRAINTS | `RISK_THRESHOLD_CONSTRAINED` |
| `evidence_refs` | soft | below minimum | EVIDENCE_REQUIRED | `EVIDENCE_INSUFFICIENT` |
| `policy_context` | soft | required, absent | ESCALATION_REQUIRED | `POLICY_NO_RULE` |
| `authorization_expired` | terminal | true | EXPIRED | `AUTHORIZATION_EXPIRED` |
| tenant / correlation / idempotency | binding only | — | — | not dispositive |

Precedence, non-compensatory and least-permissive-wins, ported from
`action_gate_ref/gate.py:37-38` with `EXPIRED` inserted below `DENIED` because
expiry is evaluated before policy is consulted at all:

    EXPIRED < DENIED < EVIDENCE_REQUIRED < SIMULATION_REQUIRED
            < ESCALATION_REQUIRED < AUTHORIZED_WITH_CONSTRAINTS < AUTHORIZED

A policy may **elevate** a soft finding; it may never **soften** any finding at
all, because a policy able to downgrade a boundary violation could authorize its
way around the boundary.

`[V]` That sentence previously read "may never soften a member of
`NON_SOFTENABLE`", and was wrong about the mechanism in a way worth recording,
because it is the same shape of defect this audit exists to remove.
`_Accumulator._tier_for` accepts an override only when it is strictly more
restrictive than the default (`evaluator.py`, the `TIER_PRECEDENCE` comparison),
so softening is refused for **every** code in the catalogue. Enumerated over the
whole catalogue, `NON_SOFTENABLE` membership changes the result in exactly five
cases, and all five are refused *hardenings* of `DENIED` to `EXPIRED` — so what
the set actually buys is that a policy can never relabel an authority, principal
or decision-binding failure as an expiry. It buys nothing at all against
softening.

## What was built

| Step | Delivered | Status |
|---|---|---|
| 2 | `cyber_security/action_gate_reference/pyproject.toml` (pytest rootdir only) and `.github/workflows/action-gate-reference-ci.yml` | done — 195 tests now gated, previously ungated |
| 3 | `ugence_actiongate_provider/vnext/` — closed reason-code catalogue, severity lattice, dimension policy model, evaluator | done — staged, not on the public API surface |
| 4 | `tests/vnext/` — 52 tests, each asserting an outcome *change* | done |
| 5 | `authorization_expired` wired through `map_request` + native `EXPIRED` outcome | done — MAJOR, in its own commit |

`[V]` The reference harness is **not** installable as a wheel:
`action_gate_ref.conformance` resolves fixtures as
`Path(__file__).parent.parent / "fixtures"`, a source-checkout layout. The
`pyproject.toml` added here declares no build system and no distribution
metadata for exactly that reason. Making it installable requires moving fixtures
into package data first.

`[V]` The vNext subpackage is deliberately absent from
`ugence_actiongate_provider.api.__all__`. Everything on that surface is covered
by a literal snapshot hash. Staging the evaluator off-surface keeps the
semantics reviewable while leaving the versioned decision to add it separate.

## Gate status

Steps 2–4 (MINOR) moved no frozen hash. Step 5 (MAJOR) re-baselined four, each
deliberately:

| Gate | Before | After step 5 |
|---|---|---|
| ActionGate `.api` snapshot | `9eeb66e3…` | `5334cca1…` |
| `public_api_manifests["actiongate_provider.api"]` | `9eeb66e3…` | `5334cca1…` |
| `core_tree_hashes["actiongate_provider"]` | `9cbeb833…` | `a0010fcf…` |
| `conformance_hashes[…ugence_actiongate_provider]` | `07e08bd4…` | `ff605bf9…` |
| behavioural-equivalence `capture_hash` | `d805e6cf…` (kept as `before`) | `e1ff5d2a…` (new `after_semantics` baseline) |
| ActionGate `.api` snapshot, again (D7 bump) | `5334cca1…` | `ee223129…` |
| `core_tree_hashes["actiongate_provider"]`, again (D7 bump) | `a0010fcf…` | `b5da5bfd…` |
| `components["dgm-actiongate-provider"]` (D7 bump) | `0.1.0` | `0.2.0` |
| `core_tree_hashes` for the other three trees | — | unmoved |
| `public_api_manifests` for the other three modules | — | unmoved |
| clean-wheel dependency verification | — | PASS, no dependency added |

`[V]` The facade tree moved exactly once: `actiongate_provider/tests/` was
touched only in the step-5 commit.

Suites: 351 passed (ActionGate packages, facade, provider framework and
`platform_freeze`, after the D6 and D9 tests and the D7 bump); 195 passed
(reference harness). Four `platform_freeze` failures and six elsewhere
(`governance-contracts` packaging, `ai-hiring` import-isolation) are
**pre-existing** — verified identical against the pre-change tree.

`[V]` This scope is narrower than it reads. It excludes the three frozen
behaviour trees, where 84 tests fail that passed before step 5. See "Regression
found while settling these items" above.

## Change classification

Steps 2–4 are **MINOR** — *"additive public APIs, new capabilities, new
conformance assertions"*. They added a subpackage and tests, changed no existing
API or semantics, and moved no frozen hash.

Step 5 is **MAJOR**, not PATCH. `PATCH` is defined as *"no API or semantic
change"*; `MAJOR` explicitly covers *"authority/lifecycle/dependency-direction/
fail-safe changes"*. A live input that previously yielded `AUTHORIZED` and now
yields a non-authorizing outcome is a fail-safe change by the manifest's own
words.

`[V]` **The platform's own classifier disagrees, and it is wrong to rely on.**
Settled in D10: the fix belongs in `classify_change`, not in `classify`.
`platform_freeze.compat.classify` reports this change as `MINOR`/`ADDITIVE`:
all eight API diffs are additions, with no removal or signature break. The
classifier compares API *shape*, and a semantic change that inverts an outcome
leaves shape untouched. Anything relying on that classifier to gate a release
would have waved this through as MINOR.

## Decisions taken on the open items

**D6 — `resource` and `parameters` postures: ratified as the matrix states.**
`[V]` The ratification is cheap because the hard/soft label has almost no
runtime expression. A dimension's posture is carried entirely by its
`DEFAULT_TIER` row; the evaluator branches on the tier, never on the label. The
one place the label appeared to matter — `NON_SOFTENABLE`, which omits every
`RESOURCE_*` and `PARAMETER_*` code — turns out not to be what refuses
softening (see the note under the matrix). `resource` and `parameters` are
therefore protected against policy downgrade exactly as strongly as `authority`
is, and their absence from that set costs them nothing.

So the question reduces to: are the `DEFAULT_TIER` rows right? Yes. An
unresolvable target resource, or one outside the permitted prefixes, is a
boundary the request failed to stay inside, not a shortage of evidence about
it — `DENIED`, like an absent authority. A declared parameter bound that cannot
be parsed is the opposite: the evaluator does not know whether the request is
inside the bound, which is uncertainty — `EVIDENCE_REQUIRED`, and never a silent
skip. Ratified unchanged; `[I]` removed from the matrix.

`[G]` Two corrections were made rather than deferred, both to false statements
about how the guarantee is enforced, neither changing behaviour:
`NON_SOFTENABLE`'s docstring, `_tier_for`'s docstring, `tier_overrides`' comment
and this document now describe the precedence comparison as the refusal.
`test_policy_may_never_soften_a_boundary_violation` is parametrized over
`NON_SOFTENABLE` and would still pass if the precedence comparison were deleted,
so it asserts the property against a surface that is not what makes it true.
`test_no_policy_override_softens_any_code_in_the_catalogue` was added to assert
it where it lives; deleting the comparison fails 44 of its cases. The constant's
name still understates what it does and should be renamed, which is left open
because a rename of a lattice constant deserves its own ratification.

**D7 — bump to `0.2.0`. Implementation and distribution, in lockstep.**
`[R]` A MAJOR change shipped under an unchanged version string is unresolvable
for any consumer. D10 establishes that the platform's classifier is structurally
blind to this change; with that blind, the version string is the only
machine-readable signal a downstream has that the semantics moved. Leaving it at
`0.1.0` would have made a fail-safe change invisible to every automated check.

Minor position, not `1.0.0`: the distribution is pre-1.0 and
`version_info().production_certified` is `False`. On a 0.x line the minor
position is the breaking position, and moving to `1.0.0` would assert a
certification this package explicitly denies.

`[V]` **The open item understated the blast radius.** It named three
touchpoints; the change needed thirteen, and two of them are frozen hashes:

| Touchpoint | Change |
|---|---|
| `ugence_actiongate_provider.version` | `__version__` and `DISTRIBUTION_VERSION` → `0.2.0` |
| `platform_freeze.version.COMPONENT_VERSIONS` | `dgm-actiongate-provider` → `0.2.0` |
| `packaging/dgm-actiongate-provider/pyproject.toml` | own version, and its `==` pin on the canonical |
| four `dgm-*` validation/benchmark `pyproject.toml` | `dgm-actiongate-provider==0.2.0`; an exact pin left at `0.1.0` becomes unresolvable |
| `enterprise_validation_pilot`, `comparative_governance_benchmark` `version.py` | `TARGET_ACTIONGATE_VERSION` |
| four version assertions in tests | facade packaging, canonical packaging, legacy-namespace re-export, `platform_freeze` |
| `cli.py` self-check, distribution verification script | hard-coded `0.1.0` equality |
| `platform/api-snapshots/actiongate_provider.api.json` | `__version__` is a `.api` constant, so the snapshot moves |
| `platform/PLATFORM_FREEZE_V1.json` | `components`, `public_api_manifests`, `core_tree_hashes`, `manifest_digest` |
| `.github/workflows/actiongate-provider-package-ci.yml` | pinned `.api` base hash |
| docs | `VERSIONING.md`, `MIGRATION.md`, `SOURCE_PROVENANCE.md`, `MIGRATION_POLICY.md`, two harness docs |

`[V]` The "ai-hiring provider-dependency metadata" the item named is
`packages/products/ai-hiring/pyproject.toml`, and it needed **no** edit: the
`actiongate` extra declares `ugence-actiongate-provider>=0.1.0`, a floor, which
resolves to `0.2.0` silently. `packages/integration/risk-authority-runtime` is
the same. Both floors are left alone deliberately — raising them to `>=0.2.0`
would be a compatibility claim about those two packages that this change did not
verify. It is worth stating plainly that **a version floor does not stop a
fail-safe change reaching a consumer**; the bump is a signal, not a barrier.

`[V]` Two frozen hashes moved beyond the four step 5 moved, both from the bump
alone: the `.api` snapshot `5334cca1…` → `ee223129…` (one line, the `__version__`
constant) and `core_tree_hashes["actiongate_provider"]` `a0010fcf…` →
`b5da5bfd…` (the facade tree hash includes its tests, and a version assertion
lives there). `conformance_hashes` did not move. Note that `compat` grades a
changed constant value `INFO`, so the version bump is invisible to the
classifier too; the workflow's pinned base-hash assertion is what catches it.

**D8 — `combine_statuses` and `combine_tiers` do not converge. D5 confirmed.**
`[V]` The two are not the same primitive, and the resemblance is superficial.
They order their middle tiers in opposite directions: Action Clearance ranks
`ESCALATE` (2) as less permissive than `HOLD` (1), while ActionGate ranks
`ESCALATION_REQUIRED` (4) as *more* permissive than `EVIDENCE_REQUIRED` (2). One
folds by maximum over an ascending-restriction map, the other by minimum over a
descending one. A shared primitive would have to be generic over the precedence
map — at which point it shares a four-line fold and nothing else.

`[V]` The cost side is worse than the layering argument suggested. Neither
package may depend on the other (Clearance is strictly downstream of ActionGate),
so sharing would require standing up a third package to hold four lines, and
that package would become a shared dependency of two layers deliberately kept
independent. Keep them separate.

`[G]` The ordering disagreement itself is recorded against the existing
reason-code-vocabulary gap below, not opened as a new one. It is not a fail-safe
divergence — both middle tiers are non-authorizing on both sides, so no
composition authorizes something it should not — but the two layers do disagree
about which non-authorizing situation is the more serious, and any future shared
vocabulary has to settle that.

**D9 — the control-plane adapter's inclusive boundary should have been split.**
`[R]` It is a `governance-provider-framework` change, and three facts say so:

`[V]` It is not covered by anything this commit re-baselined. The freeze does
not hash this package: `core_tree_hashes["governance_providers"]` covers
`governance_providers/__init__.py`, a single-file legacy facade. The framework
source under `packages/governance-provider-framework/` is hashed nowhere. So the
hunk moved no frozen hash and passed no freeze gate, while the four hashes step 5
did move all belong to ActionGate.

`[V]` It affects every action provider behind the adapter, not ActionGate —
including the reference `DeterministicActionGovernanceProvider` and any
third-party provider. A framework-wide fail-safe change rode inside a
provider-scoped commit.

`[V]` It arrived untested in its own package.
`tests/integration/test_adapters.py` exercised `expires_at=None` and
`expires_at = now - 1h`; nothing pinned the boundary instant, which is the only
thing the change moves.

`[V]` And the commit message overstates what was delivered: "`vnext.is_expired`
states the rule once and the control-plane adapter applies it". The adapter does
not call `is_expired` and cannot — the framework does not depend on a provider —
so it inlines the comparison. The rule is now written in three places
(Clearance, `vnext.expiry`, the adapter), not one.

Disposition: **do not revert to re-land identical bytes.** The exclusive form is
a one-instant window in which authorization and clearance disagree about whether
the same CER is live; reopening it to improve commit hygiene is the worse trade.
Instead the substance the split would have provided is supplied here — the
framework now owns a boundary-instant test with an injected clock
(`test_action_adapter_treats_the_expiry_instant_itself_as_expired`, which fails
against the exclusive form) and a `CHANGELOG` entry recording the change, its
framework-wide scope, and the fact that it bypassed the freeze. Future
framework-behaviour changes go through the framework's own record.

**D10 — `platform_freeze.compat.classify` should NOT gain a semantic-change
signal. `classify_change` should.**
`[R]` `classify` is the wrong seam. It consumes `Diff` objects derived purely
from two API snapshots; a semantic signal is not a fact it structurally has
access to, and threading one in would make a shape comparator lie about what it
compared. Its blindness is honest — it should be documented, not patched.

`classify_change` is where the gate actually decides, and it already reads
everything needed. `[V]` Its current resolution of a core-source change with no
breaking API diff is `PATCH`, commented "semantic-preserving core edit (still
needs review)" — an assumption of semantic preservation from the absence of a
shape break, which is exactly how this MAJOR would have been waved through.

Specified remedy, not implemented here: a core-source change that moves
`conformance_hashes` or `core_tree_hashes` while `api_classification` is not
`MAJOR` resolves to `UNCLASSIFIED`, not `PATCH`. `UNCLASSIFIED` already sets
`requires_approval`, so the change lands as "a human must classify this" rather
than as a silent PATCH. Implementation is deferred because it changes the
classification of every in-flight core change at once, and the rollout is an
owner call rather than a consequence of this audit.

`[G]` **A sharper version of the same blind spot.** The gate set does not run
the behaviour trees' tests at all — it hashes them
(`behaviour_tree_hashes`) and stops. See the regression below, which no gate
caught.

## Regression found while settling these items

`[V]` **The vNext MAJOR breaks 84 tests across all three frozen behaviour
trees.** Measured on identical machine and interpreter:

| Tree state | `enterprise_validation_pilot` + `comparative_governance_benchmark` + `provider_heterogeneity_validation` |
|---|---|
| `6fbb9e2f` (pre-vNext base) | 271 passed, 0 failed |
| `e32f9838` (step 5 head) | 187 passed, **84 failed** |
| this branch | 187 passed, 84 failed — unchanged; the version bump adds none |

The "Gate status" section below reports "258 passed … Six failures elsewhere …
pre-existing". That count covers the ActionGate packages, the facade and the
provider framework. It does not cover the behaviour trees, and the 84 failures
there are new, not pre-existing.

`[V]` **Cause: a clock-domain mismatch, not a policy defect.** Every failure is
`actual='EXPIRED'`. The harnesses build CERs on a frozen scenario clock —
`expires_at = 2026-01-01T01:00:00Z` — and construct
`ActionGovernanceControlPlaneAdapter(action_provider)` with its default wall
clock (`workflow.py:149`). Every scenario CER is therefore months expired by the
adapter's reckoning. Once `authorization_expired` is honoured, every scenario
retires. Confirmed by pinning the adapter's clock to the scenario time, which
restores the expected outcome.

`[V]` Not caused by the inclusive boundary. Reverting the adapter to
`expires_at < now` leaves all 84 failing — the CERs are months stale, not one
instant stale. D9 stands on its own evidence.

`[V]` **This was a latent, date-dependent defect that the vNext change detonated
rather than introduced.** The scenario expiry is a fixed instant in the past; the
comparison against wall-clock `now` would have been false before
2026-01-01T01:00:00Z and has been true since. The pre-vNext engine dropped
`authorization_expired`, so the mismatch was inert.

Recommended fix, not applied here: inject the scenario clock at each
`ActionGovernanceControlPlaneAdapter` construction in the three harnesses, so the
CER and the adapter share one time domain. It is a change to three behaviour
trees and it turns on which clock is authoritative for a replayed scenario, which
is a decision this audit was not asked to take.

## Still open

1. `[R]` **Reason-code rename is a consumer-visible break.** Any consumer
   string-matching `policy_allow` / `policy_denied` / `policy_unknown` /
   `policy_allow_with_constraints` must be updated. No in-repo consumer does —
   verified — but external ones cannot be checked from here.
2. `[G]` CABP signing domain and trust model — unowned, undesigned (D4).
3. `[G]` ActionGate and `action-clearance` share no reason-code vocabulary, and
   order their middle severities in opposite directions (D8).
4. `[G]` `NON_SOFTENABLE` is misnamed for what it does; the rename is deferred
   to its own ratification (D6).
5. `[G]` The behaviour-tree regression above, and the gate gap that let it
   through (D10).

## Resolved by step 5

- `[G]` The behavioural-equivalence probe now varies all eleven governance
  dimensions in permissive/offending pairs, asserts every pair differs, and
  asserts request mapping is total against the neutral dataclass's own fields.
  The old probe varied `action_type` alone and never set
  `authorization_expired`, so it could not have detected the defect it was
  supposed to guard.
