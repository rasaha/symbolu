#!/usr/bin/env python3
"""Guard inventory and gate-removal mutation sweep for the Cloud Scaling packages.

One engine, a configuration per package. `cloud-scaling-producer-attestation` already had a
sweep of its own; this generalises the method to `cloud-scaling-authorization-contracts` and
`cloud-scaling-policy-authenticity`, which had none — their guard inventories had never been
swept in CI at all — and, since the guard-coverage ADR, to
`cloud-scaling-capacity-bounds-policy`, a package that carries no authority but does carry a
fail-closed admission invariant, which is exactly the thing a sweep can measure (ADR §2).

**Not every decision point is an `if`.** The guard-coverage ADR ratified three additive
classes the engine could not see in either direction — absent from the numerator *and* from
the disclosed denominator: an `except` arm that returns a typed rejection (§4.1, its reason
collapsed to a sentinel), a statement-level call to a raising helper (§4.2, deleted rather
than disabled) and a terminal `else` that refuses (§4.3, replaced by `pass`). Each is opted
into per package through `PackageConfig.decision_classes`, because enabling one changes what
a package's checked-in inventory counts.

**A guard in a loop is one site, not `n`.** A guard inside `for flag in _AUTHORITY_FLAGS:`
decides as many invariants as the loop has iterations, and one mutation neutralises all of
them together. §7.2 rules it inventoried as **one** static site carrying a recorded semantic
multiplicity, read off the iterated constant rather than written down, with the burden of
telling the members apart falling on the suite. `risk-integration` has four such sites — of
multiplicity 7, 6, 8 and 9 — so its 101 static guards decide 127 invariants.

Two things this had to get right that a copy of the existing script would have got wrong.

**Refusal is not one shape.** Phase 5A refuses by ``raise``. Phase 5B refuses by *returning*
a typed value: ``return _refuse(outcome, detail)`` at a gate, and ``return (_Outcome.X, "…")``
from the helper that decided it. Applying Phase 5A's raise-only definition to Phase 5B misses
**47** real gates, including gate 13's exact-type instant check and all six branches of
R-8's bound reconciliation — precisely the gates most recently added. That figure was
"eleven" until it was measured: it was written from the gates this work had touched, not
counted from the inventory. The generated report computes it rather than quoting it, so it
cannot drift again. A definition is part of
the measurement, so each package declares its own and the report names which one it used.

**The decision and its effect are different lines.** Gate 13 decides in
``_candidate_instant_type_problem`` and refuses at ``if mistyped is not None:``. Neutralising
either disables the gate, so coverage is reachable either way — but an inventory that lists
only the call site never names the exact-type check, and a reader would not find the guard
they came looking for. Both are inventoried; the report says which is which.

Usage::

    python scripts/cloud_scaling/guard_sweep.py <package> --inventory-only
    python scripts/cloud_scaling/guard_sweep.py <package> --shard 3/8

A full sweep is sharded because it cannot be anything else: Phase 5A's suite runs 138s and
carries 104 guards, Phase 5B's 191s and 100 — four and five wall-clock hours if run one guard
at a time in one job. The shard count is a cost decision, disclosed in the report rather than
buried in a workflow file.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class PackageConfig:
    """Everything package-specific, in one place, so the engine stays one thing."""

    key: str
    package_dir: str
    dist_name: str
    #: Fixed module order — the order a value actually flows through the package.
    module_order: tuple
    #: Names whose ``return f(...)`` marks a refusal.
    refusal_calls: frozenset
    #: True when a bare ``return (_Outcome.X, ...)`` tuple is a refusal in this package.
    tuple_refusals: bool
    #: ``module:function`` whose successful return is an artifact this package mints. The
    #: sweep counts calls to it, so "removing this guard mints something the baseline did
    #: not" becomes a measured property instead of a thing a reader has to notice. Three
    #: such guards were found in this package by accident before this existed.
    mint_site: str
    #: The inventories this package already records, and what each is defined over.
    recorded: tuple
    #: Guards this operator cannot score, keyed by ``(module, condition)`` rather than by
    #: line number: a line shifts every time anything above it changes, and an exclusion
    #: that silently re-points at a different guard is worse than no exclusion at all.
    exclusions: dict = field(default_factory=dict)
    #: Decision classes beyond the ``if``/``IfExp`` layer that this package inventories.
    #: ``"except-arm"`` (guard-coverage ADR §4.1, D-GC-3), ``"helper-admission"`` (§4.2,
    #: D-GC-4) and ``"else-arm"`` (§4.3, D-GC-5).
    #: Opt-in per package rather than global, because the guard-coverage ADR §1
    #: states that nothing in it reclassifies a guard in ``authorization-contracts`` or
    #: ``policy-authenticity`` — those two keep every count and index §9 already settles
    #: for them, and switching a class on for them would renumber their checked-in
    #: inventories and re-open their sweeps under a different denominator. Enabling a
    #: class for a package is therefore a ratified decision, recorded here.
    decision_classes: frozenset = frozenset()
    #: Names this package uses for its reason vocabulary, read for the inventory's
    #: ``outcome`` column in addition to the two engine-wide ones. A package that
    #: publishes ``CapacityBoundsRejectionReason`` and imports it as ``Reason`` names it
    #: here rather than being read as having no typed outcome at all.
    reason_vocabularies: frozenset = frozenset()
    #: Mints this package performs that ``mint_site`` does **not** cover, each with the
    #: reason it is not covered. Guard-coverage ADR §5 accepts partial mint coverage and
    #: requires the uncovered mint to be *named* in the inventory: an undisclosed partial
    #: count is worse than a disclosed one, because a reader cannot tell which question
    #: the number answers.
    uncovered_mints: tuple = ()
    #: D-GC-3's operator, per vocabulary: ``{vocabulary: (sentinel, alternate)}``.
    #: Guard-coverage ADR §4.1 rules the operator to be "rewrite the member the arm
    #: returns to a fixed sentinel member, **chosen so it is not the member the arm
    #: already produces**". No single fixed member satisfies the second half for every
    #: arm — ``risk-integration``'s ten arms name eight distinct members, and whichever
    #: member is picked, the arms already producing it would be rewritten to themselves.
    #: The audit's out-of-tree operator resolved that by *skipping* those arms, which
    #: scores them ``UNSCORED``: the sweep would then report nothing at all about two of
    #: the ten sites it just ratified as decision points. So the sentinel is declared as
    #: a **pair** — both members fixed here rather than computed, and the operator takes
    #: the alternate exactly when the arm already produces the sentinel. Every arm is
    #: mutated, no mutation is a no-op, and which member each arm was collapsed to is
    #: read back from the source rather than assumed.
    #:
    #: **Ratified by the owner, 2026-08-30**, on exactly this reading: each ``except`` arm
    #: must be changed to a deterministic, *different* rejection reason, and the pair is
    #: what makes that possible without a no-op. The ruling states what the operator
    #: measures — whether the suite distinguishes typed reasons — rather than resting it
    #: on the word "weakening", which is the honest framing: the sentinel carries §4.1's
    #: general-for-specific direction, while for the two arms that already produce it the
    #: alternate substitutes a different *specific* reason, a lateral swap. Both are
    #: invisible to a suite that only asks whether something was rejected, which is the
    #: contract under test either way.
    #:
    #: A vocabulary with no entry here has no operator, so an arm naming only members of
    #: such a vocabulary is *not* silently mis-mutated into a different enum's member: it
    #: is reported by ``undeclared_except_arms`` and fails the inventory run.
    reason_collapse_sentinels: dict = field(default_factory=dict)
    #: Whether this package's inventory *discloses* semantic multiplicity — guard-coverage
    #: ADR §7.2, ruled at ratification. ``Guard.multiplicity`` is computed for every
    #: package regardless, because a number the engine declines to compute is a number
    #: nobody can check; this governs only whether the inventory reports it.
    #:
    #: Opt-in for the same reason the additive classes are. §7.2 was ruled inside the
    #: guard-coverage ADR, and §1 of that ADR says nothing in it changes what
    #: ``authorization-contracts`` or ``policy-authenticity`` record. Switching disclosure
    #: on for a package rewrites its checked-in inventory, so it is the owner's call, not
    #: a side effect of an engine fix.
    #:
    #: This is not hypothetical. Teaching the sizer to read annotated constants
    #: (``_CARRIED_INSTANTS: Final = (...)``) revealed two real loop-guards in
    #: ``policy-authenticity`` — ``verification.py:1026`` over six carried instants and
    #: ``verification.py:1076`` over three occurrence facts — that no inventory had
    #: disclosed. Held here for the owner while it waited; the owner ratified disclosure
    #: for that package on 2026-08-30 (ADR §10), so it now opts in alongside
    #: ``risk-integration``. The opt-in discipline itself is unchanged: every other
    #: package keeps a byte-identical inventory until its own ruling says otherwise.
    record_multiplicity: bool = False
    #: Prose the generated ``GUARD_INVENTORY.md`` must carry verbatim, directly under its
    #: header. Exists for ruled caveats a reader must not miss — the operations adoption
    #: requires the reference-HMAC caveat to stay explicit in the published record — and
    #: stays empty everywhere else, so every prior adopter's inventory is byte-identical.
    inventory_note: str = ""
    #: Whether a call to a ``refusal_calls`` name counts as a typed refusal *wherever it
    #: appears in the guard's body*, not only as ``return f(...)``. Ruled with the
    #: operations adoption (2026-08-31): that package's gates bind the typed receipt,
    #: record it, and return the bound name —
    #: ``r = self._receipt(..., ExecutionOutcome.DENIED, ...); self.outcomes.record(r);
    #: return r`` — an idiom none of the ratified shapes could see, which would have left
    #: the denial and duplicate gates of the very package whose authorization gates are
    #: the point outside the inventory. Opt-in per package: under the default every
    #: adopter's shape reading is byte-identical to before this field existed.
    bound_refusal_calls: bool = False
    #: Production modules deliberately outside ``module_order``, each with a concrete
    #: reason: ``{relative path: reason}``. Ruled with the nested-module hardening
    #: (2026-08-31): every module ``_production_modules`` discovers must be either walked
    #: by the inventory or excluded here — a module that is neither fails
    #: ``undeclared_modules`` and with it the inventory run. Before this, ``module_order``
    #: was a curated list nothing reconciled, which five flat adopters could survive by
    #: eyeball and a 78-module nested package could not: a module added later would have
    #: escaped the inventory silently. An exclusion here is a checkable statement — the
    #: reason should say what was *measured* about the module, not express confidence.
    excluded_modules: dict = field(default_factory=dict)
    #: Extra environment for every suite run of this package, baseline and mutant alike.
    #: Exists for exactly one ratified use so far: ``producer-attestation``'s packaging
    #: properties build five distributions and a virtualenv per run, and its own suite
    #: skips them under ``UGENCE_SKIP_SLOW_PACKAGING`` — a cost decision whose safety
    #: condition is measured by that package's ``tests/test_property_ledger.py`` PL-6
    #: (every module the sdist ships is also run directly, un-skipped, in the same run).
    #: Declared here rather than exported by the workflow so a local sweep and CI run the
    #: same suite; the engine's own variables still win over anything named here.
    suite_env: dict = field(default_factory=dict)

    @property
    def src(self) -> Path:
        return REPO / self.package_dir / "src" / self.dist_name

    @property
    def root(self) -> Path:
        return REPO / self.package_dir


#: The only reasons a guard may be excluded from scoring. Closed on purpose: "it survived"
#: is not on the list, and cannot be added by a reviewer in a hurry. Each entry must also
#: name the test that measures the claim, so an exclusion is a checkable statement rather
#: than an assertion of confidence.
EXCLUSION_REASONS = frozenset(
    {
        # Removing the guard yields a program that behaves identically on every path, for
        # every input. Scoring it would need a different operator, not a better test.
        "equivalent-mutant",
        # An earlier guard refuses every input that could reach this one.
        "unreachable-behind-earlier-guard",
        # The guard shapes a diagnosis; it changes no authorization outcome.
        "diagnostic-only",
        # Outside the ratified authority-bearing definition entirely.
        "outside-authority-bearing-definition",
        # The guard's condition can be true under a dependency resolution this package's
        # own pins permit, but the sweep fixture installs exactly one resolution and cannot
        # vary it. Not an equivalent mutant: the condition's falsity is a property of the
        # installation, not of the program. See ADR Phase 5 §9.2.
        "unscorable-by-single-checkout-fixture",
    }
)


#: The Cloud Scaling Controller modules **outside** the ratified `planning/` phase, each
#: with the number of ``raise`` statements measured in it at adoption. They are listed
#: here rather than inline so the count beside each name is generated from the tree and
#: cannot drift into a claim nobody re-measured. A module with a non-zero count is not a
#: guard-free module — it is refusal surface this phase deliberately does not score, and
#: a later phase must.
_CONTROLLER_DEFERRED = (
    ("__init__.py", 0),
    ("api.py", 1),
    ("cli.py", 2),
    ("config.py", 0),
    ("contracts.py", 12),
    ("controller.py", 0),
    ("core/__init__.py", 0),
    ("core/adaptive_gain.py", 0),
    ("core/coherence.py", 0),
    ("core/damping.py", 0),
    ("core/identity_ema.py", 2),
    ("core/plasticity_gate.py", 0),
    ("core/replay_buffer.py", 0),
    ("explain/__init__.py", 0),
    ("explain/explainer.py", 0),
    ("observability/__init__.py", 0),
    ("observability/benchmark.py", 0),
    ("observability/decision_log.py", 0),
    ("observability/edge_cases.py", 0),
    ("observability/efficiency_estimator.py", 0),
    ("observability/efficiency_observer.py", 0),
    ("observability/scaling_report.py", 0),
    ("recommend/__init__.py", 0),
    ("recommend/confidence.py", 0),
    ("recommend/safety.py", 0),
    ("replay/__init__.py", 0),
    ("replay/adapters/__init__.py", 0),
    ("replay/adapters/alibaba_microservices.py", 1),
    ("replay/adapters/azure_llm.py", 1),
    ("replay/adapters/azure_vm_noise.py", 1),
    ("replay/adapters/base.py", 1),
    ("replay/adapters/google_borg.py", 1),
    ("replay/adapters/partner_prometheus.py", 1),
    ("replay/efficiency_observer.py", 0),
    ("replay/harness.py", 0),
    ("replay/replay_source.py", 0),
    ("replay/report.py", 0),
    ("replay/tier_a.py", 0),
    ("shadow/__init__.py", 0),
    ("shadow/divergence.py", 0),
    ("shadow/hpa_watcher.py", 0),
    ("shadow/reporter.py", 0),
    ("signals/__init__.py", 0),
    ("signals/normalizer.py", 0),
    ("signals/pipeline.py", 1),
    ("signals/prometheus.py", 1),
    ("version.py", 0),
)

PACKAGES = {
    "authorization-contracts": PackageConfig(
        key="authorization-contracts",
        package_dir="packages/integration/cloud-scaling-authorization-contracts",
        dist_name="ugence_cloud_scaling_authorization_contracts",
        mint_site="ugence_cloud_scaling_authorization_contracts.candidate:"
                  "build_capacity_authorization_candidate",
        module_order=(
            "canonical.py",
            "identifiers.py",
            "target.py",
            "attestation.py",
            "reconciliation.py",
            "candidate.py",
        ),
        refusal_calls=frozenset(),
        tuple_refusals=False,
        # Measured at the hardening (2026-08-31): each carries zero refusal-shaped `if`
        # guards and zero `raise` statements, so excluding it moves no decision point.
        excluded_modules={
            "__init__.py": "re-exports only; measured zero guards and zero raises",
            "errors.py": "exception-class declarations; measured zero guards and zero raises",
            "trust.py": "a one-member trust-state enum and its constant — the state that "
                        "cannot be set has no guard to sweep; measured zero guards and "
                        "zero raises",
            "version.py": "the version constant; measured zero guards and zero raises",
        },
        recorded=(
            ("canonical-65", ("reconciliation.py", "candidate.py"), 65),
            ("peripheral-28", ("attestation.py", "target.py"), 28),
        ),
        exclusions={
            # --- identifiers.py: the D-4 drift assertions --------------------------------
            # The pair check one line above these is *not* here. It was excluded as
            # unscorable-by-single-checkout-fixture until the fixture was asked to vary
            # the resolution rather than assumed unable to: a `>=0.1.0` pin admits a
            # 0.2.0 that renames a ratified identifier, and under one the guard is the
            # difference between refusing to import and binding an unratified value.
            # Scored since, and killed.
            ("identifiers.py", "PRODUCER_SIGNING_PURPOSE == PURPOSE_CAPACITY_ACTION"): (
                "equivalent-mutant",
                "A collision assertion between two frozen literals defined in this module, "
                "in this distribution. No dependency resolution can move either, so the "
                "condition is false in every program this package can be part of and "
                "`if False:` is the same program on every path. The test below measures "
                "the inequality.",
                "tests/test_guard_coverage.py::"
                "test_the_in_tree_drift_assertions_hold",
            ),
            # --- reconciliation.py: diagnosis-only guards --------------------------------
            # Both are strict subsets of the guard immediately behind them, which carries
            # the *same* reason. Under ADR Phase 5 §9.1 the typed refusal is
            # (exception class, AuthorizationCandidateRejectionReason) and not the message,
            # so neither changes an authorization outcome for any input.
            ("reconciliation.py", "d_decision_snapshot is None"): (
                "diagnostic-only",
                "`None` is a strict subset of `not isinstance(d_decision_snapshot, "
                "Mapping)`, the guard on the next line, which raises ReconciliationError "
                "with the same MISSING_DECISION_SNAPSHOT reason. Removing this guard "
                "changes the message and nothing else. It is kept because the message is "
                "the better one for the commonest case.",
                "tests/test_guard_coverage.py::"
                "test_an_allow_family_decision_missing_a_binding_fact_is_refused",
            ),
            ("reconciliation.py", "d_expires_at is None"): (
                "diagnostic-only",
                "`None` is a strict subset of `not isinstance(value, datetime)` inside the "
                "`_require_datetime(\"expires_at\", ..., MISSING_EXPIRY_FACT)` call on the "
                "next line, which raises ReconciliationError with the same "
                "MISSING_EXPIRY_FACT reason. Removing this guard changes the message and "
                "nothing else.",
                "tests/test_guard_coverage.py::"
                "test_an_allow_family_decision_missing_a_binding_fact_is_refused",
            ),
        },
    ),
    "capacity-bounds-policy": PackageConfig(
        key="capacity-bounds-policy",
        package_dir="packages/integration/cloud-scaling-capacity-bounds-policy",
        dist_name="ugence_cloud_scaling_capacity_bounds_policy",
        # A method, reachable only since guard-coverage ADR §5 widened ``mint_site`` to
        # ``module:Class.method``. This is the family's true mint: ``describe`` returns the
        # ``PolicyArtifactDescriptor`` the shared authority signs and registers. The only
        # module-level candidate, ``capacity_bounds_coordinate``, returns a *coordinate* —
        # counting it would report a number that answers a different question, so §5
        # rejects it as a mint site rather than settling for the reachable one.
        mint_site="ugence_cloud_scaling_capacity_bounds_policy.adapter:"
                  "CapacityBoundsPolicyFamilyAdapter.describe",
        module_order=(
            "identifiers.py",
            "errors.py",
            "policy.py",
            "adapter.py",
        ),
        # This family refuses by raising, always. It publishes no ``_refuse`` gate and no
        # outcome tuple, so both Phase 5B shapes are off.
        refusal_calls=frozenset(),
        tuple_refusals=False,
        # Its reason vocabulary, imported as ``Reason`` at every refusal site, so the
        # inventory's outcome column names which decision each guard made rather than
        # reporting a package with no typed outcome at all.
        reason_vocabularies=frozenset({"CapacityBoundsRejectionReason", "Reason"}),
        # Both additive classes are enabled here and nowhere else: guard-coverage ADR §4.2
        # measures 14 helper-admission call sites in this package, all in ``policy.py``,
        # and §4.3's class has no member here. An empty class is still enabled — a class
        # that is off cannot report that it found nothing.
        decision_classes=frozenset({"helper-admission", "else-arm"}),
        # Fully covered: this family's only mint is ``describe``, and it is wrapped.
        uncovered_mints=(),
        # Measured at the hardening (2026-08-31): zero guards and zero raises in each.
        excluded_modules={
            "__init__.py": "re-exports only; measured zero guards and zero raises",
            "version.py": "the version constant; measured zero guards and zero raises",
        },
        recorded=(),
        exclusions={},
    ),
    "controller-evidence-planning": PackageConfig(
        key="controller-evidence-planning",
        package_dir="packages/capabilities/cloud-scaling-controller",
        dist_name="ugence_cloud_scaling_controller",
        # PHASE 1 OF A PHASED ADOPTION (owner ruling 3, 2026-08-31). This entry covers
        # `planning/` only. It is NOT controller coverage, and the inventory it generates
        # says so in its own words rather than leaving a reader to infer it from the
        # module list.
        #
        # The mint is a recommendation that exists. `CapacityActionRecommendation` is the
        # artifact this subpackage produces, and its `__post_init__` is where every
        # validation gate that can refuse one fires; the counter increments only after a
        # successful return, so "removing this guard mints something the baseline did not"
        # reads literally — a capacity action was recommended where the baseline abstained
        # or refused outright. Abstention is deliberately not a mint: declining to
        # recommend is the safe outcome this package is built to produce.
        mint_site=(
            "ugence_cloud_scaling_controller.planning.recommendation:"
            "CapacityActionRecommendation.__post_init__"
        ),
        # Ruled disclosure (owner, 2026-08-31): partial coverage reported honestly.
        inventory_note=(
            "**This is a phase, not controller coverage (phase 2, ruled 2026-08-31).** "
            "This inventory is defined over `canonical/`, `forecasting/` and `planning/` "
            "— 31 of the Cloud Scaling Controller's 78 production modules, carrying 401 "
            "of its 426 `raise` statements. The remaining 47 modules are *deferred to "
            "later ratified phases*, not judged guard-free, and every one is named in "
            "this package's `excluded_modules` with its measured refusal surface. "
            "Deferred subpackages, by name: `replay/` (13 modules, 6 raises), the "
            "top-level modules (7 modules, 15 raises), `core/` (7 modules, 2 raises), "
            "`observability/` (7 modules), `signals/` (4 modules, 2 raises), `shadow/` "
            "(4 modules), `recommend/` (3 modules) and `explain/` (2 modules). A reader "
            "must not read a green sweep here as evidence about any of them.\n\n"
            "**Phase 1 undercounted its own boundary.** Phase 1 covered `planning/` "
            "alone and recorded 219 guards. That figure omitted 33 decision points in "
            "`planning/pipeline.py`: its abstention helpers (`_abstain` and the `ab*` "
            "bindings built on it) were not declared in `refusal_calls`, so the gates "
            "selecting UNSUPPORTED_FORECAST_TARGET, INSUFFICIENT_FORECAST_CONFIDENCE, "
            "FUTURE_DATA_LEAKAGE, MISSING_CURRENT_CAPACITY and FORECAST_ABSTAINED were "
            "never enumerated. The corrected `planning/` figure is 252, and four of the "
            "33 were genuine survivors — so phase 1's published \'0 scored survivors\' "
            "was false when it was written. CI could not have caught this: the workflow "
            "pinned the total to 219 exactly, which is what a denominator error looks "
            "like from inside. The omission was found by testing the candidate rather "
            "than reasoning about it, and ADR §13 records it. Of this phase\'s 527 "
            "guards, 252 are the corrected `planning/` surface and 275 come from the "
            "`canonical/` and `forecasting/` widening."
        ),
        # `planning/` in the order a recommendation is actually built: the typed
        # abstention vocabulary first, then the evidence layers each gate reads
        # (topology, cost, constraints), then candidate generation, the policy and
        # scoring that rank them, the recommendation artifact itself, and the pipeline
        # entry point that ties them together.
        module_order=(
            # canonical/ — the observed-state layer every later layer reads.
            "canonical/__init__.py",
            "canonical/identity.py",
            "canonical/measurement.py",
            "canonical/provenance.py",
            "canonical/serialization.py",
            "canonical/normalization.py",
            "canonical/state.py",
            "canonical/sources.py",
            "canonical/projection.py",
            "canonical/evidence.py",
            # forecasting/ — the forecast-evidence layer built on canonical state.
            "forecasting/__init__.py",
            "forecasting/abstention.py",
            "forecasting/targets.py",
            "forecasting/series.py",
            "forecasting/window.py",
            "forecasting/uncertainty.py",
            "forecasting/forecasters.py",
            "forecasting/forecast.py",
            "forecasting/evidence.py",
            "forecasting/evaluation.py",
            "forecasting/replay.py",
            # planning/ — the recommendation built from both (phase 1).
            "planning/__init__.py",
            "planning/abstention.py",
            "planning/topology.py",
            "planning/cost.py",
            "planning/constraints.py",
            "planning/candidates.py",
            "planning/policy.py",
            "planning/scoring.py",
            "planning/recommendation.py",
            "planning/pipeline.py",
        ),
        # Every module outside the phase boundary, named individually with what was
        # measured about it. These are NOT "no decision point here" exclusions of the
        # producer-attestation kind — most of these modules carry substantial refusal
        # surface, which is exactly why they need their own ratified phase rather than
        # being swept in silently under this one.
        excluded_modules={
            **{
                m: (
                    "deferred to a later ratified controller phase; carries "
                    f"{n} raise statements this phase does not score"
                )
                for m, n in _CONTROLLER_DEFERRED
            },
        },
        # Eight typed refusal classes, all defined inside `planning/` and all
        # `ValueError` subclasses, plus the typed abstention the pipeline returns
        # instead of raising.
        refusal_calls=frozenset(
            {"_abstain", "ab", "abf", "abc", "abcost", "_unscored"}
        ),
        bound_refusal_calls=False,
        tuple_refusals=False,
        # Named as the *source* names them, which is the whole point of this field.
        # `pipeline.py` does `from .abstention import RecommendationAbstentionReason as R`
        # and then writes `R.CONTRADICTORY_EVIDENCE` at all 31 of its refusal sites;
        # declaring the class's real name here reads the package as having no typed
        # outcome at all and drops its one D-GC-3 arm from the denominator.
        # `ConstraintViolationKind` is the second vocabulary — `scoring.py`'s typed
        # reasons a candidate fails hard-constraint filtering. `RecommendationOutcome` is
        # deliberately absent: it is a `Union[...]` type alias, not an enum, so it names
        # no decision.
        reason_vocabularies=frozenset(
            {
                "R",
                "ConstraintViolationKind",
                "AbstentionReason",
                "SeriesErrorReason",
                "EvaluationStatus",
            }
        ),
        decision_classes=frozenset({"except-arm", "helper-admission", "else-arm"}),
        # D-GC-3's operator. Exactly one `except` arm in the phase returns a vocabulary
        # member — `pipeline.py`'s cost-scoring arm, which answers CONTRADICTORY_EVIDENCE
        # — and because that arm already produces the sentinel it is collapsed to the
        # lateral alternate. The other five arms re-raise a typed error rather than
        # returning a member, so they are outside the class and are scored as the
        # `raise` sites they are.
        reason_collapse_sentinels={
            "R": ("CONTRADICTORY_EVIDENCE", "NON_FINITE_INPUT"),
            # `forecasting/evidence.py`'s two abstaining `except` arms. INVALID_MEASUREMENT
            # is the general answer among the reasons these arms produce — reporting a unit
            # inconsistency or a missing normalization policy as a bare invalid measurement
            # is §9.4's general-for-specific weakening exactly. Neither arm can already
            # produce it (one is fixed at INCONSISTENT_UNIT, the other resolves through
            # `_APPLICABILITY_REASON`, whose three values do not include it), so the
            # alternate is the pair's formality rather than a live case.
            "AbstentionReason": ("INVALID_MEASUREMENT", "FORECAST_OUTSIDE_DOMAIN"),
        },
        record_multiplicity=False,
        uncovered_mints=(),
        recorded=(),
        # Written after a measured sweep, never before one.
        exclusions={
            # --- phase 2 (canonical/ + forecasting/) ------------------------------
            # Measured, never assumed: every entry below was scored SURVIVING by a full
            # 527-guard sweep AFTER its isolating probe was written. Four further phase-2
            # survivors turned out to be weak probes jacketed by a sibling gate and were
            # closed by re-routing the probe, not excluded.
            (
                "canonical/normalization.py",
                "else of: method in (NormalizationMethod.LATENCY_MS_TO_THRESHOLD, "
                "NormalizationMethod.LATENCY_S_TO_THRESHOLD, "
                "NormalizationMethod.QUEUE_TO_CAPACITY)",
            ): (
                "unreachable-behind-earlier-guard",
                "The exhaustive `else` closing the method dispatch, marked `pragma: no "
                "cover` in the source. The policy's own type gate refuses anything that "
                "is not a `NormalizationMethod`, and every declared member has an arm, "
                "so the only input that could reach the `else` is a member added "
                "without one. The evidence test asserts that exhaustiveness, so it "
                "fails the day such a member arrives.",
                "tests/canonical/test_guard_coverage_canonical.py::"
                "test_every_normalization_method_has_a_dispatch_arm",
            ),
            (
                "forecasting/evidence.py",
                "any((not math.isfinite(v) for v in probe.values))",
            ): (
                "unreachable-behind-earlier-guard",
                "The non-finite sweep over the probe window, which the source calls "
                "defensive. Every measurement-backed sample comes from a "
                "`Measurement`, whose `__post_init__` refuses NaN and infinity, and "
                "the replica count is validated as an int, so no non-finite value can "
                "reach a probe window.",
                "tests/forecasting/test_guard_coverage_evidence.py::"
                "test_a_non_finite_observation_cannot_be_built_at_all",
            ),
            (
                "forecasting/evidence.py",
                "not domain_for(s.unit).contains(s.value)",
            ): (
                "unreachable-behind-earlier-guard",
                "The per-sample input-domain sweep. `domain_for` reads the SAME "
                "Phase-1 `unit_domain` authority that `Measurement.__post_init__` "
                "enforces at construction — bounds and integer semantics alike — so a "
                "raw sample out of its own domain cannot be built in the first place. "
                "Kept because the forecasting layer must not depend on the canonical "
                "layer continuing to enforce it; a divergence re-opens this exclusion "
                "by construction, since the sweep fails on a stale exclusion.",
                "tests/forecasting/test_guard_coverage_evidence.py::"
                "test_an_out_of_domain_observation_cannot_be_built_at_all",
            ),
            (
                "forecasting/evidence.py",
                "forecast_space is ForecastValueSpace.NORMALIZED",
            ): (
                "equivalent-mutant",
                "The early NORMALIZED abstention for a target with no normalization "
                "signal. Neutralised, the working-window build is reached instead and "
                "raises `NormalizationApplicabilityError(reason='unsupported_target')`, "
                "which the except-arm maps straight back to `UNSUPPORTED_TARGET` over "
                "the same probe window — same reason, same bound window, same record. "
                "Kept because reaching a typed abstention without constructing and "
                "discarding a window is the honest shape.",
                "tests/forecasting/test_guard_coverage_evidence.py::"
                "test_an_unnormalizable_target_abstains_the_same_way_through_either_path",
            ),
            (
                "forecasting/evidence.py",
                "except NormalizationApplicabilityError: _abstain(_APPLICABILITY_REASON"
                ".get(exc.reason, AbstentionReason.MISSING_NORMALIZATION_POLICY), probe)",
            ): (
                "equivalent-mutant",
                "The arm itself is reachable and a later-sample normalization failure "
                "reaches it. What the except-arm mutation rewrites is the reason member "
                "the arm NAMES, and the only member named there is the `.get()` "
                "DEFAULT — dead code, because `_APPLICABILITY_REASON` is total over "
                "every reason `NormalizationApplicabilityError` is constructed with. "
                "Rewriting a default that never fires changes nothing observable. The "
                "evidence test parses the window module and asserts that totality.",
                "tests/forecasting/test_guard_coverage_evidence.py::"
                "test_every_applicability_reason_has_a_mapped_abstention",
            ),
            (
                "forecasting/evaluation.py",
                "self.status is EvaluationStatus.ABSTAINED",
            ): (
                "equivalent-mutant",
                "The ABSTAINED arm of the four-way status dispatch. It and the "
                "catch-all arm below it enforce an identical pair of rules — no "
                "scored/actual fields, and a reason is required — so a neutralised "
                "dispatch sends an ABSTAINED record to a fall-through that accepts and "
                "rejects exactly what it would. The two differ only in message text, "
                "and ADR §6 forbids attributing a kill to a message substring. Kept "
                "because naming ABSTAINED makes the dispatch read as four outcomes "
                "rather than three plus a remainder.",
                "tests/forecasting/test_guard_coverage_evaluation.py::"
                "test_abstained_and_the_catch_all_arm_enforce_the_same_two_rules",
            ),
            (
                "forecasting/replay.py",
                "actual is not None and _as_utc(actual.observed_at) <= _as_utc(cutoff)",
            ): (
                "unreachable-behind-earlier-guard",
                "The replay loop's second leakage guard, which the source calls "
                "belt-and-suspenders. `_match_actual`'s own eligibility rule already "
                "skips every observation at or before the cutoff, so no candidate the "
                "loop can receive is non-future. Kept precisely because it is the "
                "redundant half of a leakage check: the evidence test measures the "
                "first half with a tolerance ten times the horizon, the only width at "
                "which a past observation could otherwise fall inside the match window.",
                "tests/forecasting/test_guard_coverage_forecasting.py::"
                "test_the_matcher_never_returns_an_actual_at_or_before_the_cutoff",
            ),
            # --- phase 1 (planning/) ----------------------------------------------
            ("planning/constraints.py", "v is None"): (
                "diagnostic-only",
                "`_finite_number`'s None branch. No call site passes `allow_none=True` "
                "— all three call it bare — so for every reachable input the branch "
                "only chooses between the 'is required' and 'must be a finite number' "
                "messages, and both raise `ConstraintError`. The `allow_none` early "
                "return it also guards is dead at every call site; a caller that "
                "introduces one re-opens this exclusion by construction, because the "
                "sweep fails on a stale exclusion that gets killed.",
                "tests/planning/test_guard_coverage.py::"
                "test_a_none_cooldown_is_refused_as_a_constraint_error",
            ),
            ("planning/candidates.py", "not self.changes"): (
                "diagnostic-only",
                "The empty-plan guard. With it removed, the primary-count gate two "
                "lines below refuses the same empty plan with the same "
                "`CandidateError` — an empty tuple has zero 'primary' roles — and "
                "emptiness is the only condition that reaches it, so no input "
                "distinguishes the two. Kept because 'requires at least one resource "
                "change' is the honest diagnosis for the empty case.",
                "tests/planning/test_guard_coverage.py::"
                "test_an_empty_plan_is_refused_as_a_candidate_error",
            ),
            (
                "planning/candidates.py",
                "isinstance(current_capacity, bool) or not "
                "isinstance(current_capacity, int) or current_capacity < 0",
            ): (
                "diagnostic-only",
                "`generate_candidates`' current_capacity gate. The value flows "
                "unconditionally into the NO_CHANGE plan's `ResourceChange`, whose own "
                "validation refuses every value this gate refuses — bool, non-int and "
                "negative alike — with the same `CandidateError`. required_capacity's "
                "twin gate IS scored: required never lands in a ResourceChange, so its "
                "removal admits a fractional requirement outright.",
                "tests/planning/test_guard_coverage.py::"
                "test_an_invalid_current_capacity_is_refused_as_a_candidate_error",
            ),
            ("planning/policy.py", "k not in FEATURE_NAMES"): (
                "diagnostic-only",
                "ScoreBreakdown's per-key unknown-feature gate. Every key-set "
                "deviation it can see — a replaced name or an added one — is also "
                "refused by the exact-cover gate below it (`set(features) != "
                "set(FEATURE_NAMES)`), and a wrong-typed value under a bogus key by "
                "the finiteness gate between them; all three raise `PolicyError`, and "
                "the class is this package's typed half. Kept because naming the "
                "offending key is the better diagnosis.",
                "tests/planning/test_guard_coverage.py::"
                "test_an_unknown_feature_name_is_refused_as_a_policy_error",
            ),
            (
                "planning/pipeline.py",
                "except ScoringError: abcost(R.CONTRADICTORY_EVIDENCE, "
                "f'inconsistent evidence: {exc}')",
            ): (
                "unreachable-behind-earlier-guard",
                "The pipeline's ScoringError arm around `build_context`. Every "
                "condition that makes the context build raise is abstained by the "
                "pipeline's own pre-gates before the build is reached: an abstained "
                "forecast as FORECAST_ABSTAINED, a non-planning target as "
                "UNSUPPORTED_FORECAST_TARGET, a missing point estimate as "
                "NON_FINITE_INPUT, missing capacity as MISSING_CURRENT_CAPACITY, an "
                "evidence-free dependency edge as MISSING_DEPENDENCY_CAPACITY and a "
                "missing price as MISSING_COST_EVIDENCE. The arm is the fail-closed "
                "jacket for a context build the pre-gates keep unreachable, so its "
                "reason-collapse mutation has no observer; the evidence test drives "
                "the same inputs down both paths and records the pairing.",
                "tests/planning/test_guard_coverage.py::"
                "test_every_scoring_failure_is_pre_gated_into_a_typed_abstention",
            ),
            ("planning/recommendation.py", 'not self.evaluated_candidates'): (
                'diagnostic-only',
                "The empty-set guard. The canonical set-equality gate refuses an empty evaluated set "
                "with the same `RecommendationError` — the canonical generated set is never empty, "
                "NO_CHANGE always being in it — and emptiness is the only condition that reaches this "
                "guard."
                ,
                "tests/planning/test_guard_coverage.py::"
                "test_the_candidate_set_gates_behind_the_canonical_binding_are_evidenced",
            ),
            ("planning/recommendation.py", 'not float(fc.horizon.seconds) > 0'): (
                'unreachable-behind-earlier-guard',
                "The forecasting layer's `ForecastHorizon` constructor is the earlier guard: it "
                "refuses a non-positive horizon with `WindowError` at construction, so no forecast "
                "the record can embed carries one. For a hand-built impostor the temporal pair around "
                "this gate leaves no admissible recommendation_time either — with a non-positive "
                "horizon, forecast_for <= cutoff, and rec_time cannot be both >= cutoff and < "
                "forecast_for."
                ,
                "tests/planning/test_guard_coverage.py::"
                "test_a_non_positive_forecast_horizon_cannot_be_constructed_at_all",
            ),
            ("planning/recommendation.py", 'forecast_for_dt <= rec_time'): (
                'diagnostic-only',
                "The horizon-expiry guard. With it removed, the validity-window gate refuses every "
                "input this one refuses, with the same class: validity_seconds is validated > 0, so "
                "validity_end > rec_time >= forecast_for, and forecast_for is pinned to the canonical "
                "endpoint the validity gate compares against."
                ,
                "tests/planning/test_guard_coverage.py::"
                "test_a_record_timed_at_or_past_the_forecast_horizon_is_refused_either_way",
            ),
            ("planning/recommendation.py", 'len(canonical_by_id) != len(canonical_plans)'): (
                'equivalent-mutant',
                "Defensive check on the record's own canonical regeneration, and the source comment "
                "says so. `generate_candidates` derives each plan_id from its target and never emits "
                "two plans with one id — measured across a spread of configurations — so the two "
                "lengths are equal on every reachable path and removal changes nothing."
                ,
                "tests/planning/test_guard_coverage.py::"
                "test_canonical_candidate_generation_is_unique_by_construction",
            ),
            ("planning/recommendation.py", 'ec.plan.plan_id in evaluated_by_id'): (
                'diagnostic-only',
                "One half of a mutually jacketing pair with the recompute loop's duplicate guard: a "
                "duplicated candidate is refused by whichever of the two stands, with the same class, "
                "so neither guard's mutation is observable while the other exists. A duplicate with "
                "*different* content is refused by the set-equality gate instead, again with the same "
                "class."
                ,
                "tests/planning/test_guard_coverage.py::"
                "test_the_candidate_set_gates_behind_the_canonical_binding_are_evidenced",
            ),
            ("planning/recommendation.py", 'pid in seen_plan_ids'): (
                'diagnostic-only',
                "The other half of the mutually jacketing duplicate pair; see the by-id guard above. "
                "With that guard standing, no duplicate survives to reach this one."
                ,
                "tests/planning/test_guard_coverage.py::"
                "test_the_candidate_set_gates_behind_the_canonical_binding_are_evidenced",
            ),
            ("planning/recommendation.py", 'ec.feasible != exp_feasible'): (
                'diagnostic-only',
                "The feasibility-recompute guard interlocks with the violations-recompute guard and "
                "the candidate's own invariant: `feasible` is tied to the emptiness of `violations` "
                "at candidate construction, and expected feasibility is derived from expected "
                "violations — so any constructible forged flag carries a violations set the next gate "
                "refuses, with the same class. Both flip directions are measured in the evidence "
                "test."
                ,
                "tests/planning/test_guard_coverage.py::"
                "test_a_forged_feasibility_flag_is_refused",
            ),
            ("planning/recommendation.py", 'not has_no_change'): (
                'unreachable-behind-earlier-guard',
                "Canonical generation always emits the NO_CHANGE baseline, so an evaluated set "
                "without it fails the canonical set-equality gate before this baseline gate is "
                "reached."
                ,
                "tests/planning/test_guard_coverage.py::"
                "test_the_candidate_set_gates_behind_the_canonical_binding_are_evidenced",
            ),
            ("planning/recommendation.py", 'not selected.feasible'): (
                'diagnostic-only',
                "The winner-identity gate two lines below draws the winner from feasible triples "
                "only, so a selected id pointing at an infeasible candidate can never equal the "
                "winner and is refused there with the same class."
                ,
                "tests/planning/test_guard_coverage.py::"
                "test_the_candidate_set_gates_behind_the_canonical_binding_are_evidenced",
            ),
            ("planning/recommendation.py", 'ambiguous'): (
                'diagnostic-only',
                "`select_best` answers (None, True) on a tie, and the winner-identity gate on the "
                "next line refuses None != selected_plan_id with the same class, for every ambiguous "
                "input."
                ,
                "tests/planning/test_guard_coverage.py::"
                "test_an_all_tied_selection_is_refused_as_a_recommendation_error",
            ),
            (
                "planning/pipeline.py",
                "fc.point_estimate is None or not math.isfinite(float(fc.point_estimate))",
            ): (
                "unreachable-behind-earlier-guard",
                "Both halves are barred by contracts that fire first. `point_estimate is "
                "None` cannot hold: `CapacityForecast.__post_init__` refuses a "
                "FORECAST-status forecast without an estimate, and an ABSTAINED one is "
                "caught by the `fc.is_abstained` gate four lines above. `not isfinite(...)` "
                "cannot be reached either: the pipeline computes "
                "`forecast_evidence.digest()` *before* this gate, and the canonical "
                "serializer refuses to canonicalize a non-finite float, so a NaN forecast "
                "dies there with CanonicalizationError — a different contract. The gate is "
                "real defense in depth and is kept; the evidence test drives the NaN case "
                "and records where it actually stops.",
                "tests/planning/test_guard_coverage.py::"
                "test_a_non_finite_forecast_estimate_never_reaches_the_planner",
            ),
            ("planning/topology.py", "seen[key] != edge.kind"): (
                "diagnostic-only",
                "The guard chooses between two messages on a path that refuses either "
                "way: it sits inside `if key in seen:`, and neutralising it falls "
                "through to the `duplicate dependency edge` refusal on the very next "
                "line. Both are `TopologyError`, and this package's typed half is the "
                "exception class, so no input can distinguish them — a contradictory "
                "pair and a duplicate pair are refused under one contract. It is kept "
                "because 'contradictory kind' is the more useful diagnosis of the two.",
                "tests/planning/test_guard_coverage.py::"
                "test_a_duplicate_pair_and_a_contradictory_pair_are_both_refused_as_topology_errors",
            ),
        },
    ),
    "operations": PackageConfig(
        key="operations",
        package_dir="packages/capabilities/cloud-scaling-operations",
        dist_name="ugence_cloud_scaling_operations",
        # The mint is the mutation itself: the backend replica write the tests exercise.
        # For a CONTROLLED_EXECUTION package "removing this guard lets the package mint
        # something the baseline refused" reads literally — a guard whose removal lets a
        # replica write happen is the last obstacle before an infrastructure change.
        mint_site="ugence_cloud_scaling_operations.executors:FakeScalingBackend.set_replicas",
        # Ruled caveat (owner, 2026-08-31), carried into the generated inventory verbatim.
        inventory_note=(
            "**Reference-HMAC caveat (ruled 2026-08-31).** The authority gates this "
            "inventory scores are verified against `ReferenceAuthorityVerifier`, a "
            "deterministic HMAC for tests and local development — explicitly NOT a "
            "production KMS (`authority.py`). Every kill therefore proves **gate "
            "enforcement** — that the check is applied, discriminates its typed outcome, "
            "and fails closed — and none proves production cryptographic strength, which "
            "belongs to whatever verifier a deployment injects."
        ),
        # Every production module, in the order a request flows: contracts and
        # configuration, the authority gate, replay protection and audit, the executors,
        # the action layer, coordination, the recommend/shadow/observability periphery,
        # and the process entrypoints last. All 33 modules are walked — the completeness
        # gate holds with no exclusions — and modules whose decision points fall outside
        # every ratified class simply contribute zero rows.
        module_order=(
            "__init__.py",
            "version.py",
            "contracts.py",
            "config.py",
            "authority.py",
            "idempotency.py",
            "audit.py",
            "executors.py",
            "gate_executor.py",
            "k8s_executor.py",
            "action/__init__.py",
            "action/readiness.py",
            "action/policy.py",
            "action/gate_actuator.py",
            "action/k8s_actuator.py",
            "action/outcome.py",
            "action/feedback.py",
            "action/rollback.py",
            "rollback_coordinator.py",
            "orchestrator.py",
            "recommend/__init__.py",
            "recommend/engine.py",
            "recommend/approval.py",
            "recommend/webhook.py",
            "shadow/__init__.py",
            "shadow/live_efficiency.py",
            "shadow/runner.py",
            "observability/__init__.py",
            "observability/exporter.py",
            "observability/otel_exporter.py",
            "observability/metrics_server.py",
            "cli.py",
            "main.py",
        ),
        excluded_modules={},
        # This package's refusal is not one shape either (§9.1's lesson, again): most
        # gates raise (`ExecutionDenied`, `ExecutionIntegrityError`), and the executor's
        # own gates *bind* a typed receipt and return the name —
        # `r = self._receipt(..., ExecutionOutcome.DENIED, ...); return r` — while the
        # gate executor constructs a `GateOutcome` verdict. `bound_refusal_calls` is what
        # lets those call sites count as the typed-refusal evidence they are.
        refusal_calls=frozenset({"_receipt", "GateOutcome"}),
        bound_refusal_calls=True,
        tuple_refusals=False,
        reason_vocabularies=frozenset({"ExecutionOutcome"}),
        # All three additive classes. D-GC-4 selects exactly the package's two
        # authority-application sites — the statement-level `verify_authorization(...)`
        # calls in `executors.py` and `gate_executor.py` — plus the script entrypoint;
        # D-GC-3 selects the executor's three bound-return arms (denial, concurrency
        # conflict, backend failure). The 14 other returning `except` arms measured in
        # the adoption audit return booleans or exit codes, never a vocabulary member,
        # and are outside the ratified class — the re-derived denominator the owner
        # asked for is 55, not the audit's provisional 46.
        decision_classes=frozenset({"except-arm", "helper-admission", "else-arm"}),
        # D-GC-3's operator. FAILED is the general answer among the members these arms
        # produce — reporting a denial as a mere failure is precisely §9.4's
        # general-for-specific weakening; the two arms already at FAILED take the
        # lateral alternate DENIED.
        reason_collapse_sentinels={
            "ExecutionOutcome": ("FAILED", "DENIED"),
        },
        record_multiplicity=False,
        # Partial, and disclosed (ADR §5): only the fake backend the suite injects is
        # wrapped; the real mutation surfaces are named rather than counted.
        uncovered_mints=(
            (
                "ugence_cloud_scaling_operations.k8s_executor:*.set_replicas",
                "the production Kubernetes backend. The suite never mutates a real "
                "cluster, so its write path cannot be exercised by a sweep; the "
                "executor-level gates in front of it are scored against the fake "
                "backend, which implements the same ScalingBackend surface.",
            ),
            (
                "ugence_cloud_scaling_operations.action:GateActuator/K8sActuator apply paths",
                "the action-layer actuators. Their decision points fall outside every "
                "ratified class (returned verdict enums with no raise and no refusal "
                "call), so their mutation surfaces are disclosed here rather than "
                "counted; bringing them in needs an operator ruling, not a config entry.",
            ),
        ),
        recorded=(),
        # Four, all in the process-entrypoint layer, every one written *after* a measured
        # sweep. Each decides how a console process boots, not whether an execution is
        # admitted; the authority and executor gates they eventually wire are scored
        # directly above them, and no imported test run can reach a `__main__` dispatch
        # by Python's module-name semantics.
        exclusions={
            ("cli.py", "__name__ == '__main__'"): (
                "outside-authority-bearing-definition",
                "The console-script dispatch. It decides process bootstrap, not an "
                "execution outcome, and is unreachable in any imported run of the suite "
                "— the module imports under its own name.",
                "tests/execution/test_guard_coverage.py::"
                "test_the_console_entrypoints_do_not_run_on_import",
            ),
            ("main.py", "__name__ == '__main__'"): (
                "outside-authority-bearing-definition",
                "The same dispatch for the service entrypoint module.",
                "tests/execution/test_guard_coverage.py::"
                "test_the_console_entrypoints_do_not_run_on_import",
            ),
            ("main.py", "main()"): (
                "outside-authority-bearing-definition",
                "The statement the dispatch above guards — the call that boots the "
                "long-running service. Deleting it changes nothing an imported test run "
                "can observe, for the same module-name reason.",
                "tests/execution/test_guard_coverage.py::"
                "test_the_console_entrypoints_do_not_run_on_import",
            ),
            ("main.py", "args.config"): (
                "outside-authority-bearing-definition",
                "Config-source selection inside the service bootstrap: it picks where a "
                "long-running process reads configuration from, and decides no admission "
                "outcome. Exercising it means booting the service; the authority gates "
                "the configuration feeds are scored directly.",
                "tests/execution/test_guard_coverage.py::"
                "test_the_console_entrypoints_do_not_run_on_import",
            ),
        },
    ),
    "producer-attestation": PackageConfig(
        key="producer-attestation",
        package_dir="packages/integration/cloud-scaling-producer-attestation",
        dist_name="ugence_cloud_scaling_producer_attestation",
        # The package's one minting route (Phase 5B-0A): the module-level function every
        # attestation flows out of. The verification-side mint,
        # ``_mint_verified_artifact``'s caller, is an inline construction inside
        # ``verify`` and is not wrapped, per guard-coverage ADR §5.
        mint_site="ugence_cloud_scaling_producer_attestation.signing:"
                  "mint_producer_attestation",
        # The fork's flow order, kept verbatim: canonical primitives, frozen identifiers,
        # the attestation value, the signing boundary, trust-anchor handling, the verified
        # artifact, and only then the verifier.
        module_order=(
            "canonical.py",
            "identifiers.py",
            "attestation.py",
            "signing.py",
            "trust.py",
            "verified.py",
            "verification.py",
        ),
        # Phase 5B-0A refuses in two shapes: construction sites raise, and the verifier
        # *returns* ``_refuse(_Outcome.X, detail)`` inside a ``ProducerAuthenticityResult``.
        # The two result constructors are named alongside ``_refuse`` because a guard whose
        # body returns one is deciding the same typed outcome.
        refusal_calls=frozenset(
            {"_refuse", "ProducerAuthenticityResult", "ProducerAttestationRefusal"}
        ),
        # No ``(_Outcome.X, "…")`` tuple idiom; the verifier returns constructed results.
        tuple_refusals=False,
        # ``_Outcome`` is the engine-wide base name and is what this package imports its
        # ``ProducerAuthenticityOutcome`` as, so nothing extra is declared.
        reason_vocabularies=frozenset(),
        # All three additive classes, per the adoption ruling: D-GC-3 selects the four
        # verifier ``except`` arms that return ``_refuse(...)``, D-GC-4 selects the
        # ``require_*`` admission calls the fork's raise-only reading never inventoried,
        # and D-GC-5 is enabled empty — a class that is off cannot report that it found
        # nothing.
        decision_classes=frozenset({"except-arm", "helper-admission", "else-arm"}),
        # D-GC-3's operator. ``VERIFICATION_UNAVAILABLE`` is the general answer among the
        # members these arms produce — three of the four arms already return it, so they
        # take the alternate, a lateral swap to a different specific member; the fourth
        # (gate 9's ``MALFORMED_SIGNATURE``) is collapsed to the sentinel, which is
        # §9.4's general-for-specific direction.
        reason_collapse_sentinels={
            "_Outcome": ("VERIFICATION_UNAVAILABLE", "MALFORMED_SIGNATURE"),
        },
        # No §7.2/§10-style disclosure ruling exists for this package, and it carries no
        # loop-guards to disclose; the inventory stays multiplicity-silent.
        record_multiplicity=False,
        # The suite skips its packaging-distribution properties during sweep runs — the
        # fork's ratified cost decision, carried over. Safety is measured, not asserted:
        # ``tests/test_property_ledger.py`` PL-6 requires every module the sdist ships to
        # also run directly, un-skipped, in the same sweep run.
        suite_env={"UGENCE_SKIP_SLOW_PACKAGING": "1"},
        # Partial, and disclosed (guard-coverage ADR §5): the verified-artifact mint on the
        # success path is an inline construction and must not be wrapped.
        uncovered_mints=(
            (
                "ugence_cloud_scaling_producer_attestation.verification:"
                "_mint_verified_artifact(...) on the verify success path",
                "the verification-side mint. `mint_site` names the attestation mint, "
                "which is the artifact every verifier gate is about; the verified "
                "artifact is minted only after every gate has succeeded, and wrapping "
                "its construction would change the program under test.",
            ),
        ),
        # Measured at the hardening (2026-08-31): zero guards and zero raises in each —
        # the fork's MODULE_ORDER never walked these four either.
        excluded_modules={
            "__init__.py": "re-exports only; measured zero guards and zero raises",
            "errors.py": "exception-class declarations; measured zero guards and zero raises",
            "outcomes.py": "the ProducerAuthenticityOutcome enum declaration; measured "
                           "zero guards and zero raises",
            "version.py": "the version constant; measured zero guards and zero raises",
        },
        # The fork's GUARD_SWEEP.md carried the prior inventory (92 `if` guards) as prose;
        # this configuration's first inventory is the engine's own.
        recorded=(),
        # Fifteen, every one carried over from the fork's reviewed survivor
        # classifications and re-verified against a measured 116-site sweep of this
        # configuration, mapped onto the closed vocabulary. The fork's other survivors —
        # every site with a constructible isolating input, including the reference
        # signer's constructor checks, the trust-helper exact-type checks, the
        # result-shape checks and gate 9's reason collapse — are closed by isolating
        # tests in ``tests/test_guard_coverage.py`` rather than excluded.
        exclusions={
            # --- identifiers.py: the import-time separation call site --------------------
            ("identifiers.py", "_assert_domain_separation()"): (
                "unscorable-by-single-checkout-fixture",
                "Deleting the module-level call disables the import-time drift check, "
                "but every condition it tests compares constants that are frozen in this "
                "checkout — several against values imported from separately versioned "
                "distributions (TEV's capability enum, Phase 5A's identifiers) under "
                "open-ended `>=` pins. The sweep fixture installs exactly one "
                "resolution, in which every separation holds, so no input reaches the "
                "call with anything to refuse. The guards *inside* the function are all "
                "scored and killed, because the suite re-runs them with drifted values.",
                "tests/test_guard_coverage.py::"
                "test_the_import_time_separations_hold_for_the_installed_distributions",
            ),
            # --- attestation.py: the pre-decode type check -------------------------------
            ("attestation.py", "type(self.signature) is not str"): (
                "diagnostic-only",
                "Named successor: the `decode_signature` call two lines below, whose "
                "`except` arm raises the same ProducerAttestationCanonicalFieldError "
                "with the same MALFORMED_SIGNATURE outcome for every non-str value. "
                "Removing this guard changes which line refuses, and nothing a caller "
                "may branch on.",
                "tests/test_guard_coverage.py::"
                "test_a_non_str_signature_is_refused_by_decode_with_the_same_typed_pair",
            ),
            # --- signing.py: content checks behind the issuance token --------------------
            # The token guard at signing.py:121 runs first in `__post_init__` and refuses
            # every caller-assembled signing input outright; the one supported route,
            # `mint_producer_attestation`, passes `canonical_bytes()` output and the
            # pinned profile constant. No constructible input reaches any of these five
            # with a value it would reject.
            ("signing.py", "type(self.signed_input) is not bytes"): (
                "unreachable-behind-earlier-guard",
                "Behind the issuance-token guard at signing.py:121. "
                "mint_producer_attestation is the only route to a signing input and "
                "always passes canonical_bytes(); a caller cannot construct one at all.",
                "tests/test_guard_coverage.py::"
                "test_the_token_guard_precedes_every_signing_input_content_check",
            ),
            ("signing.py", "len(self.signed_input) == 0"): (
                "unreachable-behind-earlier-guard",
                "Behind the issuance-token guard at signing.py:121; the minted payload "
                "is never empty, and a caller-assembled input is refused before any "
                "content check runs.",
                "tests/test_guard_coverage.py::"
                "test_the_token_guard_precedes_every_signing_input_content_check",
            ),
            (
                "signing.py",
                "require_canonical_identifier("
                "'ProducerAttestationSigningInput.producer_id', self.producer_id)",
            ): (
                "unreachable-behind-earlier-guard",
                "Behind the issuance-token guard at signing.py:121; the minting routine "
                "validates the producer id before assembling the input, so the only "
                "values that reach this call are already canonical.",
                "tests/test_guard_coverage.py::"
                "test_the_token_guard_precedes_every_signing_input_content_check",
            ),
            (
                "signing.py",
                "require_canonical_identifier("
                "'ProducerAttestationSigningInput.issuer', self.issuer)",
            ): (
                "unreachable-behind-earlier-guard",
                "The same construction as the producer_id call above.",
                "tests/test_guard_coverage.py::"
                "test_the_token_guard_precedes_every_signing_input_content_check",
            ),
            (
                "signing.py",
                "require_canonical_identifier("
                "'ProducerAttestationSigningInput.producer_key_id', self.producer_key_id)",
            ): (
                "unreachable-behind-earlier-guard",
                "The same construction as the producer_id call above.",
                "tests/test_guard_coverage.py::"
                "test_the_token_guard_precedes_every_signing_input_content_check",
            ),
            ("signing.py", "self.signature_profile != PRODUCER_ATTESTATION_SIGNATURE_PROFILE"): (
                "unreachable-behind-earlier-guard",
                "Behind the issuance-token guard at signing.py:121; the minting routine "
                "passes the pinned constant, not a parameter, so there is no "
                "caller-supplied profile to get wrong.",
                "tests/test_guard_coverage.py::"
                "test_the_token_guard_precedes_every_signing_input_content_check",
            ),
            # --- trust.py: the None short-circuit ----------------------------------------
            ("trust.py", "resolver is None"): (
                "diagnostic-only",
                "Named successor: `None` fails the "
                "`getattr(resolver, 'is_production_authoritative', False) is not True` "
                "check at trust.py:238, which raises the same "
                "ProducerAttestationConfigurationError with the same default outcome. "
                "Removing this guard changes the message and nothing else; it is kept "
                "because 'there is no resolver at all' is the more useful diagnosis.",
                "tests/test_guard_coverage.py::"
                "test_a_none_resolver_is_refused_by_the_authority_check_with_the_same_error",
            ),
            # --- verified.py: checks behind the verification token -----------------------
            ("verified.py", "require_canonical_digest(name, getattr(self, name))"): (
                "unreachable-behind-earlier-guard",
                "Behind the construction-token guard at verified.py:238, which refuses "
                "every caller construction outright; the one minting route passes "
                "digests it computed itself. `object.__new__` fabrications bypass "
                "`__post_init__` entirely, so they reach neither this call nor the "
                "guard in front of it — they are refused by "
                "require_verified_producer_attestation at every consumption boundary, "
                "which is scored and killed.",
                "tests/test_guard_coverage.py::"
                "test_no_caller_construction_reaches_the_checks_behind_the_verification_token",
            ),
            ("verified.py", "self.artifact_digest != expected"): (
                "unreachable-behind-earlier-guard",
                "The same construction as the digest calls above: behind the "
                "construction-token guard at verified.py:238, and the minting routine "
                "computes the digest it passes. The consumption-boundary recomputation "
                "of the same digest is scored and killed.",
                "tests/test_guard_coverage.py::"
                "test_no_caller_construction_reaches_the_checks_behind_the_verification_token",
            ),
            # --- verification.py: the None short-circuits --------------------------------
            ("verification.py", "trust_anchor_resolver is None"): (
                "diagnostic-only",
                "Named successor: `hasattr(trust_anchor_resolver, 'resolve')` five lines "
                "below, which refuses None with the same "
                "ProducerAttestationConfigurationError and the same default outcome. "
                "Removing this guard changes the message and nothing else.",
                "tests/test_guard_coverage.py::"
                "test_a_none_collaborator_is_refused_with_the_same_configuration_error",
            ),
            ("verification.py", "signature_verifier is None"): (
                "diagnostic-only",
                "The same shape as the resolver guard above: a None verifier always "
                "fails `hasattr(signature_verifier, 'verify_producer_signature')` with "
                "the same typed configuration error.",
                "tests/test_guard_coverage.py::"
                "test_a_none_collaborator_is_refused_with_the_same_configuration_error",
            ),
            # --- verification.py: gate 8's byte-equality half ----------------------------
            ("verification.py", "recomputed_bytes != attestation.signed_bytes()"): (
                "diagnostic-only",
                "Named successor: the payload-digest comparison on the following line, "
                "a digest over the same two byte strings, which refuses the identical "
                "inputs with the identical PAYLOAD_MISMATCH outcome. Both are "
                "additionally fronted by the reconciliation group. Deliberately kept: "
                "it is the direct byte comparison the design specifies, and it would be "
                "the only remaining check if a future edit made the digest comparison "
                "cover a different projection of the payload.",
                "tests/test_gate_isolation.py::"
                "test_a_stale_payload_digest_fails_the_recomputation_gate",
            ),
            # --- verification.py: the anchor-record revalidation -------------------------
            ("verification.py", "type(anchor) is not TrustAnchorRecord"): (
                "unreachable-behind-earlier-guard",
                "TrustAnchorResolution refuses at construction to carry anything but a "
                "TrustAnchorRecord, and the resolution's own exact-type check at "
                "verification.py:475 — scored and killed — rejects a non-resolution "
                "before this line reads its anchor. This guard covers a resolver that "
                "returns a genuine resolution subverted after construction.",
                "tests/test_guard_coverage.py::"
                "test_a_resolution_cannot_carry_a_non_anchor_record",
            ),
        },
    ),
    "risk-integration": PackageConfig(
        key="risk-integration",
        package_dir="packages/integration/cloud-scaling-risk-integration",
        dist_name="ugence_cloud_scaling_risk_integration",
        # Guard-coverage ADR §5: ``project_recommendation`` is module-level and is a
        # genuine mint — the projection is the artifact every later gate is about. It is
        # not the package's *only* mint, and the two it does not cover are named in
        # ``uncovered_mints`` rather than left for a reader to notice. §5 accepts partial
        # coverage on exactly that condition.
        mint_site="ugence_cloud_scaling_risk_integration.projection:project_recommendation",
        # The order a value actually flows through the package: an identifier is frozen at
        # import, an outcome type is declared, an input is authenticated, the authenticated
        # input is projected, and only then does the adapter run its gates. Guard-coverage
        # ADR §7.5 reconciles the ``if`` layer against this order — 3/14/28/18/11 — and this
        # configuration reproduces that split exactly.
        module_order=(
            "identifiers.py",
            "outcomes.py",
            "authenticity.py",
            "projection.py",
            "adapter.py",
        ),
        # Phase 4C refuses in three shapes, not one. Most gates raise; the adapter's own
        # gates *return* a typed outcome. Only ``_abstained`` does so from an ``if`` body
        # — gate 2 at ``adapter.py:205`` — and declaring it names that idiom rather than
        # reporting it as a generic call to something that happens to raise. Every one of
        # the ten ``self._rejected(...)`` calls is inside an ``except`` arm, so on the
        # ``if`` layer that name is inert; it is declared because it *is* this package's
        # refusal call, and D-GC-3 reads the same vocabulary from the same sites. The
        # ``if``-layer count is 74 under either declaration.
        refusal_calls=frozenset({"_rejected", "_abstained"}),
        # No ``(_Outcome.X, "…")`` tuple idiom here: this package returns a constructed
        # ``CloudScalingRiskOutcome``, never a pair.
        tuple_refusals=False,
        # Guard-coverage ADR §3: this package publishes **three** parallel vocabularies,
        # and the pair's second element is per-path, fully determined by
        # ``CloudScalingRiskOutcome`` — ``AdapterRejectionReason`` on the rejection path,
        # ``AdapterOutcomeStatus`` on the status path, and the controller-supplied
        # ``abstention_reason`` string on the abstention path. The third is declared here
        # for the same reason the other two are — a reader must be able to see all three
        # the package publishes — while being honest that it contributes no enum member to
        # the outcome column: an abstention's reason is a string the controller chose, not
        # a member this package can name, so no operator can collapse it and none is
        # declared for it below.
        reason_vocabularies=frozenset(
            {"AdapterRejectionReason", "AdapterOutcomeStatus", "abstention_reason"}
        ),
        # All three additive classes. This is the package the guard-coverage ADR measured
        # every one of them against: §4.1's ten ``except``-arm rejections are the whole
        # gate-1/3/4 structure and the production site of every ``AdapterRejectionReason``
        # member, §4.2 finds 15 helper-admission calls here, and §4.3's single member in
        # either candidate package lives in this one, at ``authenticity.py:432``. An empty
        # class would still be enabled — a class that is off cannot report that it found
        # nothing — but none of the three is empty here.
        decision_classes=frozenset({"except-arm", "helper-admission", "else-arm"}),
        # D-GC-3's operator. ``UNSUPPORTED_INPUT_TYPE`` is the sentinel because it is the
        # *general* answer among the eight members these arms produce: collapsing a
        # specific diagnosis to it is precisely "reports a general reason where a specific
        # one was owed", which is §4.1's authority-weakening direction. Two of the ten arms
        # already produce it, so those take the alternate — see
        # ``reason_collapse_sentinels`` for why an arm is never rewritten to itself.
        reason_collapse_sentinels={
            "AdapterRejectionReason": ("UNSUPPORTED_INPUT_TYPE", "PROJECTION_FAILED"),
        },
        # §7.2's ruling is about this package's flag loops, so this package discloses them.
        record_multiplicity=True,
        # Partial, and disclosed. Guard-coverage ADR §5 accepts partial mint coverage only
        # when the uncovered mints are named.
        uncovered_mints=(
            (
                "ugence_cloud_scaling_risk_integration.authenticity:"
                "authenticate_controller_output",
                "the package's second module-level mint. `mint_site` names one function, "
                "and the projection is the artifact the later gates are about, so the "
                "authenticated token is counted only where it flows into a projection. A "
                "guard that is the last obstacle before an *authenticated token* and not "
                "before a projection is therefore not reported as minting.",
            ),
            (
                "ugence_cloud_scaling_risk_integration.adapter:"
                "CloudScalingRiskOutcome(status=RISK_DECISION, …) at adapter.py:276",
                "the terminal decision mint, and an inline class construction rather than "
                "a call to a name. ADR §5 rules it must **not** be wrapped: wrapping it "
                "would break `isinstance` and the dataclass path, and a mint counter that "
                "changes the program under test measures the instrumentation. The two "
                "other constructions in this module, at lines 312 and 356, are the "
                "rejection and abstention outcomes — refusals, not mints.",
            ),
        ),
        # Measured at the hardening (2026-08-31): zero guards and zero raises in each.
        excluded_modules={
            "__init__.py": "re-exports only; measured zero guards and zero raises",
            "errors.py": "exception-class declarations; measured zero guards and zero raises",
            "version.py": "the version constant; measured zero guards and zero raises",
        },
        # No prior inventory: this is the package's first.
        recorded=(),
        # Eight, every one written *after* a measured sweep rather than predicted before
        # it. The owner ruled the survivors closed by isolating tests wherever an
        # isolating input exists: 92 of the 100 sites are scored and killed, and these
        # eight are the residue where the input does not exist and the reason is shown
        # positively. Guard-coverage ADR §7.3's four `# pragma: no cover` candidates are
        # *not* granted automatically — `authenticity.py:543` and `identifiers.py:68` are
        # scored and killed, and only `identifiers.py:88` and `adapter.py:266` earned the
        # exclusion the pragma hinted at.
        exclusions={
            # --- identifiers.py -----------------------------------------------------
            ("identifiers.py", "value not in CANONICAL_ACTION_TYPES"): (
                "unreachable-behind-earlier-guard",
                "The value check can only fire for an `ActionKind` member whose value is "
                "outside the ratified set, and the import-time drift guard 20 lines above "
                "refuses to import at all when any such member exists. The `isinstance` "
                "check on the line above has already established that the argument is a "
                "genuine member, so between the two there is no input that reaches this "
                "one with a value it would reject. The import guard itself is scored, and "
                "killed by installing a controller resolution that renames a kind.",
                "tests/test_guard_coverage.py::"
                "test_every_ratified_action_kind_is_admitted_so_the_value_check_"
                "cannot_fire",
            ),
            # --- projection.py ------------------------------------------------------
            ("projection.py", "candidates[0][1] is None"): (
                "diagnostic-only",
                "Named successor: the `value is None` check inside the loop three lines "
                "below, which raises the same `ProjectionError` for the same input — "
                "`forecast_evidence_digest` is `candidates[0]`, so it is the first the "
                "loop reaches. Measured: with the guard removed the message changes from "
                "'required (ADR §6)' to 'required and must not be None' and nothing else "
                "does. ADR Phase 5 §9.1 makes the message prose, so this is a positive "
                "showing of diagnostic-only rather than an inference from a shared class.",
                "tests/test_guard_coverage.py::"
                "test_the_forecast_digest_guard_shares_its_outcome_with_the_loop_"
                "below_it",
            ),
            # --- adapter.py: the two defensive revalidations -------------------------
            # Keyed by enclosing function: both read `_validate_authenticated_output(
            # authenticated)` in the same module, so the two-element key names two guards
            # and `classify()` refuses to guess. Their reachability is identical, but the
            # key has to say which is which.
            (
                "adapter.py",
                "_validate_authenticated_output(authenticated)",
                "CloudScalingRiskAdapter.project",
            ): (
                "unreachable-behind-earlier-guard",
                "The token was produced by `authenticate_controller_output` on the line "
                "above, and every token it returns is built by one of the two "
                "`Authenticated*` constructors, each of which runs this same validation "
                "in its own `__post_init__`. An invalid token therefore cannot come into "
                "existence. `project` takes a *source*, never a token, so no "
                "caller-supplied value reaches this call. The package's own comment says "
                "as much — 'redundant *now* — which is the point' — and the guards inside "
                "the function it calls are scored and killed, because a forged token does "
                "reach *those*.",
                "tests/test_guard_coverage.py::"
                "test_no_invalid_authenticated_token_can_exist_to_reach_the_"
                "revalidations",
            ),
            (
                "adapter.py",
                "_validate_authenticated_output(authenticated)",
                "CloudScalingRiskAdapter.evaluate",
            ): (
                "unreachable-behind-earlier-guard",
                "The same construction as the call in `project` above, inside gate 1's "
                "`try` so a failure would produce a typed outcome rather than an escaping "
                "exception. The token is produced two lines above by "
                "`authenticate_controller_output`, so it has already been validated by "
                "the constructor that built it.",
                "tests/test_guard_coverage.py::"
                "test_no_invalid_authenticated_token_can_exist_to_reach_the_"
                "revalidations",
            ),
            # --- adapter.py: gate 3's two defence-in-depth handlers ------------------
            ("adapter.py", "except RecommendationInputError: self._rejected(AdapterRejectionReason.UNSUPPORTED_INPUT_TYPE, str(exc), tenant_id=_safe_tenant(authenticated), subject_id=_safe_subject(authenticated), recommendation_digest=getattr(authenticated, 'recommendation_digest', None))"): (
                "unreachable-behind-earlier-guard",
                "`projection.py` raises no `RecommendationInputError` anywhere — measured "
                "by AST over every `raise` in the module. The class is produced only by "
                "authenticity's serialized-reconstruction paths, which gate 1 has already "
                "run and which cannot run again inside `project_recommendation`. The arm "
                "is kept because gate 3 re-runs the token check independently, and if the "
                "two ever disagreed the stricter one must still produce a typed outcome.",
                "tests/test_guard_coverage.py::"
                "test_projection_raises_neither_input_nor_authenticity_errors_of_its_"
                "own",
            ),
            ("adapter.py", "except RecommendationAuthenticityError: self._rejected(AdapterRejectionReason.RECOMMENDATION_DIGEST_MISMATCH, str(exc), tenant_id=_safe_tenant(authenticated), subject_id=_safe_subject(authenticated), recommendation_digest=getattr(authenticated, 'recommendation_digest', None))"): (
                "unreachable-behind-earlier-guard",
                "The same shape as the arm above. `projection.py` raises no "
                "`RecommendationAuthenticityError` of its own; the only route to one is "
                "`_validate_authenticated_recommendation`, which cannot fail on a token "
                "that both the `Authenticated*` constructor and gate 1 have validated. "
                "This is the site guard-coverage ADR §4.1 reports as the audit's single "
                "survivor, and the sweep reproduces that survival exactly — the reason it "
                "survives is reachability, not a gap in the suite.",
                "tests/test_guard_coverage.py::"
                "test_projection_raises_neither_input_nor_authenticity_errors_of_its_"
                "own",
            ),
            # --- adapter.py: the trusted-time re-check and the seam-return check ------
            ("adapter.py", "request.evaluation_time is not None"): (
                "unreachable-behind-earlier-guard",
                "`projection.py:139` refuses any projection whose request carries an "
                "evaluation time, and the projection has no parameter through which to "
                "supply one, so the request re-checked here is always one that guard "
                "admitted. Kept as defence in depth: it is what stops a future refactor "
                "quietly forwarding a caller's clock.",
                "tests/test_guard_coverage.py::"
                "test_every_projection_carries_no_evaluation_time",
            ),
            ("adapter.py", "not isinstance(decision, SubjectRiskDecision)"): (
                "diagnostic-only",
                "Named successor: `outcomes.py:131`, which raises the same "
                "`NonExecutableInvariantError` for every value that would fail here — a "
                "seam return that is not a `SubjectRiskDecision` cannot satisfy the "
                "outcome's own check either. Measured: removing this guard changes the "
                "diagnosis from 'the evaluation seam must return a canonical "
                "SubjectRiskDecision' to 'a RISK_DECISION outcome requires a canonical "
                "SubjectRiskDecision', and nothing else. Naming the seam is what tells an "
                "integrator which collaborator broke its contract.",
                "tests/test_guard_coverage.py::"
                "test_the_seam_return_check_shares_its_outcome_with_the_outcome_"
                "dataclass",
            ),
        },
    ),
    "policy-authenticity": PackageConfig(
        key="policy-authenticity",
        package_dir="packages/integration/cloud-scaling-policy-authenticity",
        dist_name="ugence_cloud_scaling_policy_authenticity",
        mint_site="ugence_cloud_scaling_policy_authenticity.verification:"
                  "_mint_verified_artifact",
        module_order=(
            "canonical.py",
            "identifiers.py",
            "outcomes.py",
            "resolution_port.py",
            "verified.py",
            "verification.py",
        ),
        refusal_calls=frozenset({"_refuse", "PolicyAuthenticityRefusal"}),
        tuple_refusals=True,
        # Measured at the hardening (2026-08-31): zero guards and zero raises in each.
        excluded_modules={
            "__init__.py": "re-exports only; measured zero guards and zero raises",
            "errors.py": "exception-class declarations; measured zero guards and zero raises",
            "version.py": "the version constant; measured zero guards and zero raises",
        },
        recorded=(),
        exclusions={
            # --- identifiers.py: the import-time separations -----------------------------
            # Four of these five compare across a distribution boundary, under the
            # open-ended `ugence-policy-authority>=0.1.0` and
            # `ugence-cloud-scaling-authorization-contracts>=0.1.0` pins. ADR Phase 5 §9.2:
            # a condition that can be true under a permitted resolution is not an equivalent
            # mutant, however false it is in this checkout.
            ("identifiers.py",
             "len({POLICY_AUTHENTICITY_DIGEST_DOMAIN, POLICY_AUTHENTICITY_VERIFIED_FACTS_DOMAIN, POLICY_AUTHENTICITY_RECORDED_FACTS_DOMAIN}) != 3"): (
                "equivalent-mutant",
                "The one of the five that is genuinely equivalent: all three domains are "
                "frozen literals in this module, in this distribution, so no resolution can "
                "move any of them and the condition is false in every program this package "
                "can be part of.",
                "tests/test_guard_coverage.py::"
                "test_the_import_time_separations_hold_for_the_installed_distributions",
            ),
            # --- resolution_port.py / verified.py: guards their own successor subsumes ----
            # Each was attacked for isolation first and the attempt is recorded. None of the
            # three has an input that reaches it without also reaching the guard behind it,
            # and neither `PolicyAuthenticityConfigurationError` nor
            # `VerifiedPolicyArtifactIntegrityError` carries an outcome enum — so under ADR
            # Phase 5 §9.1 the typed refusal is the class alone, and the class does not move.
            ("resolution_port.py", "registry is None"): (
                "diagnostic-only",
                "`None` cannot reach this guard without also failing "
                "`hasattr(registry, 'get_issued')` thirteen lines below, which raises the "
                "same PolicyAuthenticityConfigurationError: a None registry never has the "
                "attribute, so no isolating input exists. Kept because 'there is no ambient "
                "registry' is the more useful thing to tell a composition root than 'your "
                "registry lacks get_issued'.",
                "tests/test_guard_coverage.py::"
                "test_a_resolution_port_built_without_a_registry_is_refused",
            ),
            ("resolution_port.py", "signature_verifier is None"): (
                "diagnostic-only",
                "The same shape as the registry guard above: a None verifier always fails "
                "`hasattr(signature_verifier, 'verify')` below it with the same error class, "
                "so no input isolates this one.",
                "tests/test_guard_coverage.py::"
                "test_a_resolution_port_built_without_a_signature_verifier_is_refused",
            ),
            # --- verification.py: guards that refine a diagnosis inside one outcome -------
            # Phase 5B's verify path is layered: several guards narrow the *message* while
            # sharing one PolicyAuthenticityOutcome with the guard behind them. Under ADR
            # Phase 5 §9.1 the outcome is the contract, so these change no authorization
            # answer. Each was attacked for isolation first and the attempt is recorded as
            # impossible by construction, not merely unsuccessful.
            ("verification.py", "missing"): (
                "diagnostic-only",
                "Each of the three published descriptor fields is backed by a successor "
                "carrying the same POLICY_PROJECTION_ABSENT outcome: a None adapter id or "
                "policy type fails the exact-str check on the next line, and a None "
                "projection fails the Mapping check below that. `None` cannot pass either, "
                "so no isolating input exists. Kept because naming *which* fields are absent "
                "is what tells a port author what to publish.",
                "tests/test_guard_coverage.py::"
                "test_a_resolution_publishing_no_descriptor_projection_is_refused",
            ),
            ("verification.py", "resolution_port is None"): (
                "diagnostic-only",
                "The same construction as the two resolution_port guards above: a None port "
                "always fails `hasattr(port, 'resolve_policy_version')` five lines below, "
                "with the same PolicyAuthenticityConfigurationError, so no input isolates "
                "it. Kept because 'a port is required' is the more useful diagnosis than "
                "'your port is the wrong shape'.",
                "tests/test_guard_coverage.py::"
                "test_a_verifier_built_without_a_resolution_port_is_refused",
            ),
            ("verified.py", "name in RECORDED_FACT_NAMES"): (
                "diagnostic-only",
                "Measured: with the guard removed, both recorded names fall through to the "
                "verified-fact lookup and raise the same VerifiedPolicyArtifactIntegrityError "
                "('is not a fact of a verification artifact'). The guard changes the "
                "diagnosis from 'not a fact' to 'a recorded fact, not a verified one' — which "
                "is the difference between a typo and a category error, and is why it is "
                "kept.",
                "tests/test_guard_coverage.py::"
                "test_reading_a_recorded_fact_through_verified_fact_is_refused",
            ),
            # --- verified.py: the partition's import guards -------------------------------
            # Genuinely equivalent: every operand is a frozen set or a `dataclasses.fields`
            # reading of a class in this module, so no resolution can move either side.
            ("verified.py", "VERIFIED_FACT_NAMES & RECORDED_FACT_NAMES"): (
                "equivalent-mutant",
                "A fact cannot be both verified and recorded. Both operands are frozen sets "
                "defined in this module, in this distribution, so the intersection is empty "
                "in every program this package can be part of. Kept because it is what makes "
                "a mis-classified new field fail at import rather than ship as a fact that "
                "is digest-covered and unattested.",
                "tests/test_guard_coverage.py::test_the_fact_partition_is_total_and_disjoint",
            ),
            ("verified.py", "_PARTITIONED != _DECLARED"): (
                "equivalent-mutant",
                "Every declared field of the artifact must be classified verified or "
                "recorded. Both sides are read from this module — the two frozen sets and "
                "`dataclasses.fields(VerifiedPolicyAuthenticity)` — so the comparison cannot "
                "be made true by anything outside this distribution.",
                "tests/test_guard_coverage.py::test_the_fact_partition_is_total_and_disjoint",
            ),
            # --- verification.py ---------------------------------------------------------
        },
        # Guard-coverage ADR §7.2, extended to this package by the owner's ruling of
        # 2026-08-30 (ADR §10): `verification.py:1026` and `:1076` stay one static site
        # each and disclose multiplicities 6 and 3, read off `_CARRIED_INSTANTS` and
        # `_OCCURRENCE_FACTS`. Disclosure-only — the sweep's denominator, indices and
        # classification do not move.
        record_multiplicity=True,
    ),
}


@dataclass
class Guard:
    index: int
    module: str
    lineno: int
    condition: str
    header_end: int
    is_elif: bool
    shape: str
    #: "if" — a statement guard, neutralised by rewriting its header to `if False:`.
    #: "outcome-selection" — a conditional *expression* choosing between two typed
    #: outcomes, neutralised by collapsing it to its ``else`` branch. The `if False:`
    #: operator cannot touch one, which is why they were invisible until an audit
    #: measured that they decide the reason a caller is entitled to act on.
    #: "helper-admission" — a statement-level call to a raising helper, neutralised by
    #: deleting the call (guard-coverage ADR §4.2). Neutralising the helper's own ``if``
    #: proves the check works; it does not prove the check is *applied here*, and one
    #: covering test of the helper masks every other call site.
    #: "else-arm" — the terminal ``else`` of a dispatch whose body refuses, neutralised
    #: by replacing that body with ``pass`` (guard-coverage ADR §4.3). An ``else`` has no
    #: header to rewrite, so ``if False:`` cannot reach it.
    #: "except-arm" — an ``except`` handler whose body returns a typed rejection,
    #: neutralised by collapsing the reason member it returns to a sentinel
    #: (guard-coverage ADR §4.1). The refusal itself is left intact, so a test that only
    #: asks "was something rejected?" cannot see the mutation; only a test that reads
    #: *which* reason the caller was owed can.
    kind: str = "if"
    span: tuple = ()
    recorded_in: str = ""
    outcome: str = ""
    scored: bool = False
    excluded_because: str = ""
    killed_by: list = field(default_factory=list)
    #: How many invariants this one static site decides — guard-coverage ADR §7.2, ruled
    #: at ratification. A guard inside ``for flag in _AUTHORITY_FLAGS:`` is **one** site
    #: with a recorded multiplicity, not seven scored sites: one mutation neutralises all
    #: of them together, so a kill shows only that at least one is tested. The number is
    #: read from the iterated constant rather than written down, because a multiplicity
    #: nobody can re-derive is a multiplicity nobody can defend — and because the audit
    #: that wrote "7" was reading one of the loops and generalising to the other.
    #: The discrimination burden this leaves on the tests is §6's within-class criterion,
    #: and it is what ``tests/test_authority_flag_multiplicity.py`` measures.
    multiplicity: int = 1
    #: For ``except-arm`` only: the vocabulary and member the arm returns, so ``mutate``
    #: collapses within the arm's own enum and the inventory names what was collapsed.
    collapse_vocabulary: str = ""
    collapse_member: str = ""
    #: The enclosing ``def`` (``Class.method`` where there is one), used *only* to
    #: disambiguate an exclusion key. Deliberately not emitted: adding it to the
    #: inventory would rewrite four checked-in files to disambiguate a handful of rows.
    function: str = ""


#: The vocabularies every package is read as publishing. A package that names its own
#: adds it through ``PackageConfig.reason_vocabularies`` — this set is not widened by
#: hand, because a name added here silently changes what every package's inventory says
#: its guards decide.
_BASE_REASON_VOCABULARIES = frozenset({"_Outcome", "_Reason", "Reason"})


def _reason_vocabularies(config: PackageConfig) -> frozenset:
    return _BASE_REASON_VOCABULARIES | config.reason_vocabularies


def _outcome_names(body, config: PackageConfig) -> list:
    """The typed outcomes this guard's body can produce, for the report's own reading.

    Reads a *body* rather than a node so an ``else`` arm — which has no node of its own —
    is read exactly as an ``if`` body is.
    """

    vocabularies = _reason_vocabularies(config)
    names = []
    for statement in body:
        for inner in ast.walk(statement):
            if isinstance(inner, ast.Attribute) and isinstance(inner.value, ast.Name):
                if inner.value.id in vocabularies:
                    names.append(inner.attr)
    return sorted(set(names))


def _production_modules(config: PackageConfig) -> tuple:
    """Every production module under ``src``, discovered recursively.

    Discovery, not curation: ``module_order`` says what the inventory *walks*, and this
    says what *exists*, so the two can be reconciled (``undeclared_modules``) instead of
    trusted. A nested layout (``planning/pipeline.py``) is a first-class citizen here —
    the flat ``glob("*.py")`` this replaced silently ignored every subpackage, which on a
    nested package under-counted the raising-helper set and, through it, the inventory.
    """

    return tuple(
        sorted(
            str(path.relative_to(config.src)).replace(os.sep, "/")
            for path in config.src.rglob("*.py")
            if "__pycache__" not in path.parts
        )
    )


def undeclared_modules(config: PackageConfig) -> dict:
    """Reconcile discovery against declaration; every mismatch is a failure, not a note.

    Four ways the two can disagree, each returned under its own key so the failure names
    the fix:

    * ``undeclared`` — a production module neither in ``module_order`` nor in
      ``excluded_modules``. The load-bearing case: it is how a module added after
      adoption fails the inventory run instead of silently escaping the sweep.
    * ``missing`` — a ``module_order`` entry naming no file on disk (a rename or delete
      the config did not follow).
    * ``orphan_exclusions`` — an ``excluded_modules`` entry naming no file on disk; an
      exclusion that outlived its module is a statement about nothing.
    * ``double_listed`` / ``unreasoned_exclusions`` — an entry in both lists, or an
      exclusion whose reason is empty: both make the declaration unreadable.
    """

    discovered = set(_production_modules(config))
    ordered = set(config.module_order)
    excluded = dict(config.excluded_modules)
    return {
        "undeclared": sorted(discovered - ordered - set(excluded)),
        "missing": sorted(ordered - discovered),
        "orphan_exclusions": sorted(set(excluded) - discovered),
        "double_listed": sorted(ordered & set(excluded)),
        "unreasoned_exclusions": sorted(
            module for module, reason in excluded.items() if not str(reason).strip()
        ),
    }


def _import_bindings(config: PackageConfig, module: str, node) -> dict:
    """``{local name: (source module, original name)}`` for one package-local ImportFrom.

    Resolves relative imports (``from .canonical import x``, ``from ..core.state import y``)
    and absolute ones spelled through the distribution name. Anything external returns no
    bindings. An alias that names a *submodule* (``from . import canonical``) is dropped:
    calls through it are attribute calls (``canonical.require_x(...)``), and cross-module
    attribute calls are deliberately not followed — that unnamed reach is exactly the
    contamination channel the module-qualified analysis exists to close.
    """

    if node.level == 0:
        dotted = node.module or ""
        if dotted != config.dist_name and not dotted.startswith(config.dist_name + "."):
            return {}
        dotted = dotted[len(config.dist_name):].lstrip(".")
    else:
        parts = module.split("/")[:-1]
        climb = node.level - 1
        if climb > len(parts):
            return {}
        parts = parts[: len(parts) - climb]
        dotted = ".".join(parts + (node.module.split(".") if node.module else []))

    base = dotted.replace(".", "/")
    source = None
    for candidate in ((f"{base}.py", f"{base}/__init__.py") if base else ("__init__.py",)):
        if (config.src / candidate).is_file():
            source = candidate
            break
    if source is None:
        return {}

    package_dir = base if source.endswith("__init__.py") else None
    bindings = {}
    for alias in node.names:
        if package_dir is not None:
            inner = f"{package_dir}/{alias.name}" if package_dir else alias.name
            if (config.src / f"{inner}.py").is_file() or (
                config.src / inner / "__init__.py"
            ).is_file():
                continue  # a submodule alias, not a name binding
        bindings[alias.asname or alias.name] = (source, alias.name)
    return bindings


def _helper_analysis(config: PackageConfig) -> tuple:
    """Per module: the names that resolve, *in that module*, to a raising callable.

    Derived from the source, not hand-listed, and — since the nested-module hardening —
    keyed by **module-qualified identity** ``(module, name)`` rather than by a bare name
    pooled across the package. Under the pooled set, a raising ``Ledger.append`` in one
    module made ``append`` look raising in every module; here, a name reaches across a
    module boundary only through an actual import binding (``_import_bindings``), so
    same-named helpers in different modules can never contaminate one another.

    Transitive by fixpoint over qualified nodes: ``require_policy_digest`` raises
    directly, and anything whose body calls it — locally or through an import — inherits
    that. One level would miss the second rank. Two defs sharing a name *within* one
    module (a function and a same-named method) still merge; per-module granularity is
    the ruled unit of identity, and no adopter carries that collision.

    Returns ``(visible, selectable)`` — two ``{module: frozenset}`` maps over every
    discovered production module, so helpers defined in a module outside
    ``module_order`` (an ``errors.py``, say) still resolve for the modules that import
    them. ``visible`` feeds the shape reading (any raising callable reachable by name in
    that module); ``selectable`` is its narrowing to names whose target is a
    **module-level function**, the only sites the helper-admission operator may delete —
    see ``_helper_admission_sites`` for why a method can never qualify.
    """

    modules = _production_modules(config)
    defs = {}
    module_level = {}
    imports = {}
    direct = set()
    edges = {}

    for module in modules:
        tree = ast.parse((config.src / module).read_text(encoding="utf-8"))
        module_level[module] = {
            n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        defs[module] = set()
        imports[module] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imports[module].update(_import_bindings(config, module, node))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            defs[module].add(node.name)
            if any(isinstance(inner, ast.Raise) for inner in ast.walk(node)):
                direct.add((module, node.name))
            named = set()
            for inner in ast.walk(node):
                if isinstance(inner, ast.Call):
                    name = getattr(inner.func, "id", None) or getattr(inner.func, "attr", None)
                    if name:
                        named.add(name)
            edges.setdefault((module, node.name), set()).update(named)

    resolved_edges = {}
    for (module, name), named in edges.items():
        targets = set()
        for callee in named:
            if callee in defs[module]:
                targets.add((module, callee))
            elif callee in imports[module]:
                source, original = imports[module][callee]
                if original in defs.get(source, ()):
                    targets.add((source, original))
        resolved_edges[(module, name)] = targets

    raising = set(direct)
    changed = True
    while changed:
        changed = False
        for qualified, targets in resolved_edges.items():
            if qualified not in raising and targets & raising:
                raising.add(qualified)
                changed = True

    visible = {}
    selectable = {}
    for module in modules:
        names = {name for name in defs[module] if (module, name) in raising}
        names |= {
            local
            for local, (source, original) in imports[module].items()
            if (source, original) in raising
        }
        visible[module] = frozenset(names)
        selectable[module] = frozenset(
            {name for name in module_level[module] if (module, name) in raising}
            | {
                local
                for local, (source, original) in imports[module].items()
                if original in module_level.get(source, ()) and (source, original) in raising
            }
        )
    return visible, selectable


def _is_elif(node) -> bool:
    """An ``elif`` is an ``If`` in its parent's ``orelse`` at the parent's own column."""

    return (
        len(node.orelse) == 1
        and isinstance(node.orelse[0], ast.If)
        and node.orelse[0].col_offset == node.col_offset
    )


def _statement_span(node) -> tuple:
    return (node.lineno, node.col_offset, node.end_lineno, node.end_col_offset)


def _helper_admission_sites(tree, module_level_helpers: frozenset) -> list:
    """Statement-level calls to a raising helper — guard-coverage ADR §4.2 (D-GC-4).

    The class is decidable from the AST with no judgement: an ``ast.Expr`` whose call
    target is a bare name resolving, **in this module**, to a module-level raising
    function (``_helper_analysis``'s ``selectable`` set — defined here at module level,
    or imported here from one). A call whose result is *bound* is an ``ast.Assign`` and
    is deliberately not in this class — deleting it would change what the program
    computes rather than only what it refuses. A bare ``ast.Name`` is required rather
    than any call whose name matches: an audit produced a working false positive on
    ``out.append(r)`` — under the old package-pooled name set, a raising
    ``Ledger.append`` anywhere made ``list.append`` match, and deleting that call changed
    what the program *computed*, crediting a kill the guard never earned. Module-qualified
    identity closes the pooled half of that hole; the bare-``Name`` rule closes the
    attribute-call half.

    Why this is a decision point distinct from the helper's own ``if``: neutralising the
    helper's internal guard proves the check works, not that it is applied at this site.
    A dropped call admits the artifact without ever checking it, and no ``if False:``
    reaches a site that has no ``if`` header.
    """

    sites = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            continue
        func = node.value.func
        # A bare name only. ``getattr(func, "attr", None)`` used to be a fallback here,
        # which is exactly what admitted method calls.
        if isinstance(func, ast.Name) and func.id in module_level_helpers:
            sites.append(node)
    return sites


def _except_arm_members(handler, vocabularies: frozenset) -> list:
    """Every ``(return, member)`` pair in this handler that names a reason member.

    Returned in source order, so a handler whose body names more than one member has a
    determinate first one rather than whichever ``ast.walk`` happened to reach first.
    """

    named = []
    returns = []
    for statement in handler.body:
        for inner in ast.walk(statement):
            if not isinstance(inner, ast.Return) or inner.value is None:
                continue
            returns.append(inner)
            for member in ast.walk(inner.value):
                if (
                    isinstance(member, ast.Attribute)
                    and isinstance(member.value, ast.Name)
                    and member.value.id in vocabularies
                ):
                    named.append((inner, member))
    if not named and returns:
        # Bound-return fallback, ruled with the operations adoption (2026-08-31): an arm
        # that *builds* its typed rejection and returns the binding —
        # ``r = self._receipt(..., ExecutionOutcome.FAILED, ...); return r`` — names its
        # member in the body rather than in the return expression. The member is still
        # the mutation target; the arm is selected only when it actually returns a value,
        # so a purely raising or falsy-returning handler stays outside the class. Arms
        # whose member sits in the return value are selected exactly as before, so every
        # prior adopter's inventory is unchanged.
        for statement in handler.body:
            for member in ast.walk(statement):
                if (
                    isinstance(member, ast.Attribute)
                    and isinstance(member.value, ast.Name)
                    and member.value.id in vocabularies
                ):
                    named.append((returns[0], member))
    return sorted(named, key=lambda row: (row[1].lineno, row[1].col_offset))


def _except_arm_sites(tree, config: PackageConfig) -> tuple:
    """``except`` arms that return a typed rejection — guard-coverage ADR §4.1 (D-GC-3).

    *The class, decidable from the AST alone:* an ``except`` handler whose body contains a
    ``return`` whose value names a member of the package's reason vocabulary. The member
    need not *be* the returned value — ``return self._rejected(Reason.X, str(exc))`` names
    it as an argument, which is the idiom every one of ``risk-integration``'s ten arms
    uses — so the whole returned expression is searched.

    *Why these are invisible in both directions today.* ``inventory()`` gives them no row
    because they are not ``ast.If``; ``excluded()`` counts them zero times because it
    discloses only ``except`` arms that **raise**, and none of the ten does. A site absent
    from the numerator *and* from the disclosed denominator is not a conservative
    omission — it is a coverage claim about gates nobody measured.

    *Why an arm with no declared sentinel is refused rather than skipped.* Collapsing a
    member of one vocabulary to a sentinel of another would not weaken the refusal, it
    would change the program into one that cannot type-check its own outcome — and the
    resulting failure would be scored as a kill the guard never earned. So an arm whose
    only reason members belong to a vocabulary with no entry in
    ``reason_collapse_sentinels`` is returned as *undeclared* and fails the inventory run,
    where a reader can see the vocabulary that needs an operator.

    *One row per handler.* Where a handler names more than one member, the first in source
    order is the one collapsed, and the rest are not separately inventoried — the same
    shape of limitation ``_else_arm_sites`` records, and latent for the same reason: no
    handler in either configured package names two. ``_except_arm_members`` also walks a
    nested ``def`` or ``lambda`` inside a handler, so a ``return`` from one would be
    attributed to the enclosing handler; likewise latent, and likewise recorded rather
    than narrowed here.

    Returns ``(sites, undeclared)``.
    """

    vocabularies = _reason_vocabularies(config)
    sites = []
    undeclared = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        named = _except_arm_members(node, vocabularies)
        if not named:
            continue
        collapsible = [
            row for row in named
            if row[1].value.id in config.reason_collapse_sentinels
        ]
        if not collapsible:
            undeclared.append((node.lineno, sorted({m.value.id for _, m in named})))
            continue
        statement, member = collapsible[0]
        sites.append((node, statement, member))
    return sites, undeclared


def undeclared_except_arms(config: PackageConfig) -> list:
    """``except`` arms in the class that no declared sentinel can collapse.

    Reported by ``--inventory-only`` as a hard failure rather than counted as zero: the
    alternative is a package that quietly inventories fewer arms than its own reason
    vocabularies produce.
    """

    if "except-arm" not in config.decision_classes:
        return []
    found = []
    for module in config.module_order:
        tree = ast.parse((config.src / module).read_text(encoding="utf-8"))
        _sites, undeclared = _except_arm_sites(tree, config)
        found += [
            f"{module}:{lineno} returns {', '.join(vocabularies)} — no sentinel declared"
            for lineno, vocabularies in undeclared
        ]
    return sorted(found)


def _enclosing_functions(tree) -> dict:
    """``id(node)`` → the ``def`` it sits in, as ``Class.method`` or ``function``.

    Exists for one job: telling two guards apart when their ``(module, condition)`` key
    does not. ``adapter.py`` calls ``_validate_authenticated_output(authenticated)`` from
    both ``project`` and ``evaluate``, so the key names two guards and ``classify()``
    refuses to guess which an exclusion means — correctly, since silently covering both
    is exactly the failure that check exists to prevent.

    Not part of the key by default. Every package here has colliding keys, so qualifying
    all of them would rewrite four checked-in inventories to disambiguate the few rows
    anyone actually needs to name.
    """

    functions = {}

    def descend(node, prefix: str, current: str) -> None:
        for child in ast.iter_child_nodes(node):
            inner = current
            inner_prefix = prefix
            if isinstance(child, ast.ClassDef):
                inner_prefix = f"{prefix}{child.name}."
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                inner = f"{prefix}{child.name}"
                # A nested ``def`` qualifies further; a method does not re-qualify.
                inner_prefix = ""
            functions[id(child)] = inner
            descend(child, inner_prefix, inner)

    descend(tree, "", "")
    return functions


def _loop_multiplicity(tree) -> dict:
    """``id(node)`` → how many times the enclosing loops run it — ADR §7.2's multiplicity.

    Only loops over a **module-level name bound once to a literal sequence** count,
    because only those have a length the engine can read off the source. ``for flag in
    _AUTHORITY_FLAGS:`` qualifies; ``for row in rows:`` does not, and gets multiplicity 1
    rather than a guess.

    Nested qualifying loops multiply. A ``for``-``else`` arm does not: it runs once
    regardless of the iterable's length.

    Three ways this used to be wrong, each measured on a synthetic tree before being
    closed. Two of them over-counted, which is the direction that matters: a multiplicity
    is a claim about how many invariants one mutation neutralises, and an inflated one
    credits a site with invariants it does not decide.

    * **Annotated constants were invisible.** ``FLAGS: Final = ("a", "b")`` is an
      ``AnnAssign``, not an ``Assign``, so a real constant read as multiplicity 1. This
      package already writes ``PROJECTION_SCHEMA_VERSION: Final[str]``, so the shape is
      one edit away from a flag tuple.
    * **A rebound name kept its first length.** A name assigned twice at module level, or
      extended with ``+=``, is not a constant this function can size, so any name bound
      more than once is dropped rather than sized from whichever binding came first.
    * **A local or parameter of the same name inherited the module's length.** The
      function does not resolve scopes, so a ``def f(_AUTHORITY_FLAGS):`` shadowing the
      module constant used to multiply by the module's length. Names bound anywhere
      inside the enclosing function — parameter, assignment, ``for`` target, ``with`` or
      comprehension target — are therefore dropped for that function's subtree.
    """

    counts = {}
    annotated = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = [t for t in node.targets if isinstance(t, ast.Name)]
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target]
            value = node.value
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            # ``FLAGS += (...)`` rebinds; the name is no longer a single literal.
            counts[node.target.id] = counts.get(node.target.id, 0) + 2
            continue
        else:
            continue
        for target in targets:
            counts[target.id] = counts.get(target.id, 0) + 1
        annotated.append((targets, value))

    sizes = {}
    for targets, value in annotated:
        if (
            isinstance(value, ast.Call)
            and getattr(value.func, "id", None) in {"frozenset", "tuple", "set", "list"}
            and value.args
        ):
            value = value.args[0]
        if not isinstance(value, (ast.Tuple, ast.List, ast.Set)) or not value.elts:
            continue
        if not all(isinstance(element, ast.Constant) for element in value.elts):
            continue
        for target in targets:
            sizes[target.id] = len(value.elts)
    # Bound more than once at module level: not a constant, whatever the first binding was.
    sizes = {name: size for name, size in sizes.items() if counts.get(name) == 1}

    multiplicity = {}

    def descend(node, factor: int, visible: dict) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            visible = {
                name: size for name, size in visible.items()
                if name not in _names_bound_in(node)
            }
        for name, value in ast.iter_fields(node):
            children = value if isinstance(value, list) else [value]
            inner = factor
            if (
                isinstance(node, ast.For)
                and name == "body"
                and isinstance(node.iter, ast.Name)
            ):
                inner = factor * visible.get(node.iter.id, 1)
            for child in children:
                if isinstance(child, ast.AST):
                    multiplicity[id(child)] = inner
                    descend(child, inner, visible)

    descend(tree, 1, sizes)
    return multiplicity


def _names_bound_in(node) -> set:
    """Every name this function binds — so a shadowed module constant stops being one.

    Parameters included, because a parameter is the case that made this necessary: a
    ``def f(_AUTHORITY_FLAGS):`` iterating its own argument was multiplied by the module
    constant's length, crediting one static guard with seven invariants it never decided.
    """

    bound = set()
    arguments = getattr(node, "args", None)
    if isinstance(arguments, ast.arguments):
        for group in (
            arguments.posonlyargs, arguments.args, arguments.kwonlyargs,
        ):
            bound.update(argument.arg for argument in group)
        for solo in (arguments.vararg, arguments.kwarg):
            if solo is not None:
                bound.add(solo.arg)
    for inner in ast.walk(node):
        if isinstance(inner, ast.Name) and isinstance(inner.ctx, (ast.Store, ast.Del)):
            bound.add(inner.id)
        elif isinstance(inner, (ast.Global, ast.Nonlocal)):
            bound.update(inner.names)
    return bound


def _else_arm_sites(tree, config: PackageConfig, helpers: frozenset) -> list:
    """Terminal ``else`` arms whose body refuses — guard-coverage ADR §4.3 (D-GC-5).

    An implementation-only extension of §9.1, not a new class: "a body that can reach a
    refusal makes the ``if`` a guard", and a terminal ``else`` is the last arm of that
    same ``if``. Only the operator was missing, because an ``else`` has no header.

    ``elif`` chains are excluded: an ``elif`` is an ``If`` of its own and is already
    inventoried on the ``if`` layer with its own condition.

    **Direct refusal only — ruled by the owner, 2026-08-30.** An arm qualifies when its
    *own* statements refuse. An arm that merely *contains* a nested ``if`` which refuses
    does not, even though §9.1's reach language would admit it.

    The ruling settled a real conflict rather than a stylistic one. Under the reach
    reading this package had two members, and the second was ``outcomes.py:159``, whose
    mutation span ``(160,12)-(171,17)`` contains guards ``outcomes.py:160``, ``164`` and
    ``168`` — all separately inventoried. Measured before the narrowing, its mutant was
    killed by the same two tests that kill 160 and 164: a row that inflated numerator and
    denominator together and measured nothing the three inner rows did not already
    measure. §8 item 3 named that exact site as not a member; the owner ruled with §8.3,
    so the reach reading is narrowed here and the class has one member, as ratified.

    ``elif`` chains stay excluded for the same reason they always were, and the nesting
    limitation this docstring used to record is closed rather than disclosed: an arm whose
    refusal is reached only through a nested dispatch is now outside the class, so no two
    rows can have nesting spans.
    """

    sites = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If) or not node.orelse or _is_elif(node):
            continue
        if _refusal_shape_of(_direct_statements(node.orelse), config, helpers):
            sites.append(node)
    return sites


def _direct_statements(body) -> list:
    """The arm's own statements, with any nested branch's *body* removed.

    ``_refusal_shape_of`` walks whatever it is handed, so handing it the arm unmodified
    asks "can this arm reach a refusal?". The ratified question is narrower — "does this
    arm refuse?" — so a nested ``If``/``Try``/loop contributes its test and its iterable
    but not the suites hanging off it. A ``with`` or a bare block is not a branch: its
    body always runs when the arm runs, so it stays.
    """

    direct = []
    for statement in body:
        if isinstance(statement, (ast.If, ast.Try, ast.For, ast.While, ast.Match)):
            # Keep the parts that execute unconditionally with the arm, drop the arms.
            for name in ("test", "iter", "subject"):
                held = getattr(statement, name, None)
                if isinstance(held, ast.AST):
                    direct.append(ast.Expr(value=held))
            continue
        direct.append(statement)
    return direct


def _else_lineno(lines, node) -> int:
    """The ``else:`` line itself, not the first line of its body.

    Found by walking back from the body rather than assuming ``body[0].lineno - 1``: a
    comment between ``else:`` and the first statement is ordinary, and an inventory row
    that points a reader at a comment is a row they cannot check.
    """

    for probe in range(node.orelse[0].lineno - 1, node.lineno - 1, -1):
        if lines[probe - 1].lstrip().startswith("else"):
            return probe
    return node.orelse[0].lineno


def _refusal_shape(node, config: PackageConfig, helpers=None) -> str:
    """How this guard refuses, or ``""`` when it does not."""

    return _refusal_shape_of(node.body, config, helpers)


def _refusal_shape_of(body, config: PackageConfig, helpers=None) -> str:
    """How this *body* refuses, or ``""`` when it does not.

    Defined over a body rather than an ``if`` node so the same definition of refusal
    applies to an ``else`` arm, which has no node of its own (guard-coverage ADR §4.3:
    a terminal ``else`` is the last arm of the same ``if``, not a new class).

    The shape is reported per guard rather than collapsed, because it is the thing that
    differs between the two packages and the thing a copied definition gets wrong.
    """

    raises = False
    call = False
    tuple_return = False
    outcome_return = False
    helper_call = False
    # The caller supplies this module's visible raising set from ``_helper_analysis`` —
    # computed once per package, because re-deriving it per candidate node would make the
    # inventory quadratic in the size of the source. ``None`` would silently mean "no
    # helper is raising", so it is refused instead of defaulted.
    if helpers is None:
        raise ValueError("_refusal_shape_of requires the module's visible raising set")
    for statement in body:
        for inner in ast.walk(statement):
            if isinstance(inner, ast.Raise):
                raises = True
            elif isinstance(inner, ast.Call):
                # Any call to a raising helper, whether or not its result is bound. This
                # used to exclude bound calls as "conversions". An audit measured all three
                # justifications false for the one site the carve-out excluded
                # (``attestation.py:261``): neutralising it produces a typed refusal, leaves
                # the collected population identical, and survives the entire suite — so the
                # carve-out was not describing a conversion, it was hiding an untested gate.
                name = getattr(inner.func, "id", None) or getattr(inner.func, "attr", None)
                if name in helpers:
                    helper_call = True
                # Bound-refusal idiom (``bound_refusal_calls`` — see PackageConfig): the
                # refusal call constructs the typed outcome and a later statement returns
                # the binding, so the call site rather than the return is the evidence.
                if config.bound_refusal_calls and name in config.refusal_calls:
                    call = True
            if isinstance(inner, ast.Return):
                value = inner.value
                if isinstance(value, ast.Call):
                    name = getattr(value.func, "id", None) or getattr(
                        value.func, "attr", None
                    )
                    if name in config.refusal_calls:
                        call = True
                elif isinstance(value, ast.Tuple) and config.tuple_refusals:
                    if value.elts and isinstance(value.elts[0], ast.Attribute):
                        base = value.elts[0].value
                        if isinstance(base, ast.Name) and base.id in {"_Outcome", "_Reason"}:
                            tuple_return = True
                elif _outcome_member(value):
                    # `return _Outcome.VERIFICATION_UNAVAILABLE` — a refusal that names its
                    # outcome directly rather than through `_refuse` or a tuple. The shape
                    # rules were written from the two packages' *gate* idioms and could not
                    # see it, which left `_terminal_outcome`'s own decision points outside
                    # both inventories while the suite was killing them.
                    outcome_return = True
    if raises:
        return "raise"
    if call:
        return "typed-refusal call"
    if tuple_return:
        return "typed-refusal tuple"
    if outcome_return:
        return "returned outcome"
    if helper_call:
        return "raising-helper call"
    return ""


def _outcome_member(value) -> bool:
    """``_Outcome.X`` / ``_Reason.X`` — a named member of a typed refusal vocabulary."""

    return (
        isinstance(value, ast.Attribute)
        and isinstance(value.value, ast.Name)
        and value.value.id in {"_Outcome", "_Reason", "Reason"}
    )


def _reads_an_outcome(value) -> bool:
    """An expression that reads an outcome *off an object* rather than naming one.

    ``getattr(exc, "outcome", None)`` and ``exc.outcome`` both qualify. This is the half of
    a conditional expression that decides whether a typed outcome is consulted at all.
    """

    if isinstance(value, ast.Attribute) and value.attr in {"outcome", "reason"}:
        return True
    if isinstance(value, ast.Call):
        name = getattr(value.func, "id", None)
        if name == "getattr" and len(value.args) >= 2:
            key = value.args[1]
            return isinstance(key, ast.Constant) and key.value in {"outcome", "reason"}
    return False


def _selects_an_outcome(node) -> bool:
    """A conditional expression that decides a typed outcome.

    Two shapes qualify, and both are decision points under §9.1 even though no ``if``
    statement is involved:

    * **choosing between two outcomes** — ``reason = A if cond else B`` decides which reason
      a caller is entitled to act on;
    * **deciding whether an outcome is read at all** — ``getattr(exc, "outcome", None) if
      isinstance(exc, _PackageError) else None``. Collapsed to its ``else``, every typed
      outcome flattens to one fallback: measured, a ``COORDINATE_MALFORMED`` and an
      ``INVARIANT_VIOLATION`` both become ``VERIFICATION_UNAVAILABLE``, telling a caller the
      check could not run when it ran and refused.

    The ``if False:`` operator cannot reach either, so both are collapsed to the ``else``
    branch instead — see ADR Phase 5 §9.4 for why that is the authority-weakening direction.
    """

    chooses_between = (
        _outcome_member(node.body)
        and _outcome_member(node.orelse)
        and node.body.attr != node.orelse.attr
    )
    gates_the_read = (
        _reads_an_outcome(node.body)
        and isinstance(node.orelse, ast.Constant)
        and node.orelse.value is None
    )
    return chooses_between or gates_the_read


def _selection_outcome(node) -> str:
    """What a conditional-expression decision point decides, for the inventory row.

    Two shapes reach here: one names both outcomes it chooses between, the other names the
    outcome it decides whether to read at all.
    """

    if _outcome_member(node.body) and _outcome_member(node.orelse):
        return ", ".join(sorted({node.body.attr, node.orelse.attr}))
    return f"{ast.unparse(node.body)} or none"


def _raise_alone(node) -> bool:
    """The canonical-65 shape: a ``raise`` alone in the body of its enclosing ``if``."""

    return len(node.body) == 1 and isinstance(node.body[0], ast.Raise)


def inventory(config: PackageConfig) -> list:
    guards = []
    index = 0
    recorded_scope = {
        name: (scope, count) for name, scope, count in config.recorded
    }
    visible_helpers, selectable_helpers = _helper_analysis(config)
    for module in config.module_order:
        path = config.src / module
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        tree = ast.parse(source, filename=str(path))
        helpers = visible_helpers[module]
        module_level_helpers = selectable_helpers[module]
        found = []
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                shape = _refusal_shape(node, config, helpers)
                if shape:
                    found.append((node.lineno, node, shape))
            elif isinstance(node, ast.IfExp) and _selects_an_outcome(node):
                found.append((node.lineno, node, "outcome selection"))
        multiplicity = _loop_multiplicity(tree)
        functions = _enclosing_functions(tree)
        # The three additive decision classes, each enabled per package rather than
        # engine-wide — see ``PackageConfig.decision_classes`` for why.
        if "except-arm" in config.decision_classes:
            for handler, statement, member in _except_arm_sites(tree, config)[0]:
                found.append(
                    (handler.lineno, (handler, statement, member), "except-arm rejection")
                )
        if "helper-admission" in config.decision_classes:
            for node in _helper_admission_sites(tree, module_level_helpers):
                found.append((node.lineno, node, "helper-admission call"))
        if "else-arm" in config.decision_classes:
            for node in _else_arm_sites(tree, config, helpers):
                found.append((_else_lineno(lines, node), node, "else-arm refusal"))
        for lineno, node, shape in sorted(found, key=lambda row: (row[0], row[2])):
            index += 1
            if shape == "outcome selection":
                guards.append(
                    Guard(
                        index=index,
                        module=module,
                        lineno=node.lineno,
                        condition=ast.unparse(node.test),
                        header_end=node.lineno,
                        is_elif=False,
                        shape=shape,
                        recorded_in="",
                        outcome=_selection_outcome(node),
                        kind="outcome-selection",
                        span=(
                            node.lineno,
                            node.col_offset,
                            node.end_lineno,
                            node.end_col_offset,
                        ),
                        multiplicity=multiplicity.get(id(node), 1),
                        function=functions.get(id(node), ""),
                    )
                )
                continue
            if shape == "except-arm rejection":
                handler, statement, member = node
                guards.append(
                    Guard(
                        index=index,
                        module=module,
                        # The ``except`` line, which is where a reader looks for the arm.
                        # The mutated span is the reason member several lines below it.
                        lineno=handler.lineno,
                        # Qualified by the whole returned expression, not just the handler
                        # type and the member: ``adapter.evaluate`` catches
                        # ``RecommendationAuthenticityError`` twice and returns
                        # ``RECOMMENDATION_DIGEST_MISMATCH`` from both, so a shorter key
                        # would name two arms at once and could not say which it meant.
                        condition=(
                            f"except {ast.unparse(handler.type) if handler.type else ''}: "
                            f"{ast.unparse(statement.value)}"
                        ),
                        header_end=handler.lineno,
                        is_elif=False,
                        shape="typed-refusal return",
                        recorded_in="",
                        outcome=f"{member.value.id}.{member.attr}",
                        kind="except-arm",
                        span=(
                            member.lineno,
                            member.col_offset,
                            member.end_lineno,
                            member.end_col_offset,
                        ),
                        multiplicity=multiplicity.get(id(handler), 1),
                                                function=functions.get(id(handler), ""),
                        collapse_vocabulary=member.value.id,
                        collapse_member=member.attr,
                    )
                )
                continue
            if shape == "helper-admission call":
                guards.append(
                    Guard(
                        index=index,
                        module=module,
                        lineno=lineno,
                        # The call text, not a condition: this decision point has no
                        # test. It is still the stable exclusion key, for the same
                        # reason a condition is — it survives every line shift above it.
                        condition=ast.unparse(node.value),
                        header_end=lineno,
                        is_elif=False,
                        shape=shape,
                        recorded_in="",
                        outcome=", ".join(_outcome_names([node], config)),
                        kind="helper-admission",
                        span=_statement_span(node),
                        multiplicity=multiplicity.get(id(node), 1),
                        function=functions.get(id(node), ""),
                    )
                )
                continue
            if shape == "else-arm refusal":
                guards.append(
                    Guard(
                        index=index,
                        module=module,
                        lineno=lineno,
                        # Qualified by the dispatch it terminates, so the key cannot
                        # collide with the ``if`` guard that owns the same test.
                        condition=f"else of: {ast.unparse(node.test)}",
                        header_end=lineno,
                        is_elif=False,
                        shape=_refusal_shape_of(node.orelse, config, helpers),
                        recorded_in="",
                        outcome=", ".join(_outcome_names(node.orelse, config)),
                        kind="else-arm",
                        span=(
                            node.orelse[0].lineno,
                            node.orelse[0].col_offset,
                            node.orelse[-1].end_lineno,
                            node.orelse[-1].end_col_offset,
                        ),
                        multiplicity=multiplicity.get(id(node), 1),
                        function=functions.get(id(node), ""),
                    )
                )
                continue
            header = lines[node.lineno - 1].lstrip()
            recorded_in = ""
            for name, (scope, _count) in recorded_scope.items():
                if module in scope and _raise_alone(node):
                    recorded_in = name
            guards.append(
                Guard(
                    index=index,
                    module=module,
                    lineno=node.lineno,
                    condition=ast.unparse(node.test),
                    header_end=node.body[0].lineno - 1,
                    is_elif=header.startswith("elif"),
                    shape=shape,
                    recorded_in=recorded_in,
                    outcome=", ".join(_outcome_names(node.body, config)),
                    multiplicity=multiplicity.get(id(node), 1),
                    function=functions.get(id(node), ""),
                )
            )
    return guards


def reconcile(config: PackageConfig, guards: list) -> dict:
    """Tie this inventory to the counts the package already records.

    A number nobody can re-derive is a number nobody can defend, so each recorded inventory
    is recomputed here from source and compared against its recorded value.
    """

    report = {}
    for name, scope, expected in config.recorded:
        measured = sum(
            1
            for guard in guards
            if guard.module in scope and guard.recorded_in == name
        )
        report[name] = {
            "scope": list(scope),
            "expected": expected,
            "measured": measured,
            "agrees": measured == expected,
        }
    return report


def excluded(config: PackageConfig) -> dict:
    """What the ``if``-guard denominator leaves out, measured rather than claimed."""

    except_arms = 0
    boolean_subterms = 0
    visible_helpers, _ = _helper_analysis(config)
    for module in config.module_order:
        helpers = visible_helpers[module]
        tree = ast.parse((config.src / module).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if any(
                    isinstance(inner, ast.Raise)
                    for statement in node.body
                    for inner in ast.walk(statement)
                ):
                    except_arms += 1
            elif isinstance(node, ast.If) and _refusal_shape(node, config, helpers):
                if isinstance(node.test, ast.BoolOp):
                    boolean_subterms += len(node.test.values) - 1
    return {"except_arms": except_arms, "boolean_subterms": boolean_subterms}


def _span_text(lines, span) -> str:
    """The exact source text of a node, from its (line, col, end_line, end_col) span."""

    start_line, start_col, end_line, end_col = span
    if start_line == end_line:
        return lines[start_line - 1][start_col:end_col]
    first = lines[start_line - 1][start_col:]
    middle = "".join(lines[start_line : end_line - 1])
    last = lines[end_line - 1][:end_col]
    return first + middle + last


def _replace_span(path: Path, span: tuple, replacement: str) -> None:
    """Overwrite exactly one node's source span, leaving every other byte untouched."""

    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    start_line, start_col, end_line, end_col = span
    prefix = "".join(lines[: start_line - 1]) + lines[start_line - 1][:start_col]
    suffix = lines[end_line - 1][end_col:] + "".join(lines[end_line:])
    path.write_text(prefix + replacement + suffix, encoding="utf-8")


def mutate(config: PackageConfig, guard: Guard, workdir: Path) -> None:
    """Neutralise exactly this guard in the copy.

    One operator per kind, each chosen so the mutation is *authority-weakening* — it
    admits something the guard refused — rather than merely different:

    * ``if`` — the header is rewritten to ``if False:``.
    * ``outcome-selection`` — a conditional *expression* has no header to rewrite, so it
      is collapsed to its ``else`` branch. That is deliberate: the ``if`` branch is the
      more specific diagnosis, and losing it is the defect the guard exists to prevent.
    * ``helper-admission`` — the call statement is replaced by ``pass``. Deleting a call
      whose only effect is to raise is exactly the weakening direction; the artifact is
      then admitted without ever being checked (guard-coverage ADR §4.2).
    * ``else-arm`` — the ``else`` body is replaced by ``pass``, so an exact-type dispatch
      falls through silently instead of refusing: an unrecognised type is admitted rather
      than rejected (guard-coverage ADR §4.3).
    * ``except-arm`` — the reason member the arm returns is collapsed to the sentinel
      (guard-coverage ADR §4.1). The refusal is left intact and only its *reason* moves,
      so this is authority-weakening in §9.4's sense — the caller is told something
      general where a specific answer was owed — and a suite that only asserts "something
      was rejected" cannot see it. That is the whole point: it measures the half of §9.1's
      pair that a raise-or-not operator can never reach.
    """

    path = workdir / "src" / config.dist_name / guard.module
    if guard.kind == "except-arm":
        sentinel, alternate = config.reason_collapse_sentinels[guard.collapse_vocabulary]
        # Never a no-op: an arm already producing the sentinel is collapsed to the
        # alternate instead. A mutation that rewrote a member to itself would be scored
        # SURVIVED and read as a coverage defect in a suite that has none.
        target = sentinel if guard.collapse_member != sentinel else alternate
        _replace_span(path, guard.span, f"{guard.collapse_vocabulary}.{target}")
        return

    if guard.kind == "outcome-selection":
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        # The ``else`` branch read back from the source, never reconstructed from the
        # inventory, so a rename cannot silently substitute a different member. Parenthesised
        # because a multi-line conditional carries its continuation indentation with it.
        expression = ast.parse("(" + _span_text(lines, guard.span) + ")", mode="eval")
        _replace_span(path, guard.span, ast.unparse(expression.body.orelse))
        return

    if guard.kind in {"helper-admission", "else-arm"}:
        # ``pass`` rather than deletion: an ``else:`` or a suite whose only statement was
        # removed is a SyntaxError, and a mutant that cannot parse is scored UNSCORED —
        # which reports nothing about the guard.
        _replace_span(path, guard.span, "pass")
        return

    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    original = lines[guard.lineno - 1]
    indent = original[: len(original) - len(original.lstrip())]
    keyword = "elif" if guard.is_elif else "if"
    lines[guard.lineno - 1] = f"{indent}{keyword} False:\n"
    for offset in range(guard.lineno, guard.header_end):
        lines[offset] = ""
    path.write_text("".join(lines), encoding="utf-8")


def run_suite(
    workdir: Path,
    baseline_collected=None,
    timeout: int = 1800,
    suite_args: tuple = ("tests",),
    require_green: bool = False,
    mint_site: str = "",
    extra_env: "dict | None" = None,
) -> dict:
    """Run the suite in the copy, and score it only if it collected the same population.

    ``suite_args`` exists for local iteration only. CI always sweeps the whole suite, which
    is the scoring instrument of record; narrowing it to the one test module that attacks a
    guard turns a 2.5-minute mutant into a 3-second one while writing that attack. The
    narrowed run can only ever be *weaker* than the full one — every test it runs, the full
    suite also runs — so a kill it reports is a kill CI will reproduce, and a survivor it
    reports still has to be confirmed against the full suite before anyone believes it.
    """

    process = subprocess.run(
        [sys.executable, "-m", "pytest", *suite_args, "-p", "no:cacheprovider",
         "-p", "_ugence_mint_counter", "--tb=no"],
        cwd=str(workdir),
        capture_output=True,
        text=True,
        timeout=timeout,
        env={
            **os.environ,
            # Package-declared additions first, so the engine's own variables below can
            # never be overridden by a config entry.
            **(extra_env or {}),
            # The copy lives outside the repository and cannot find the checkout by walking
            # upward.
            "UGENCE_REPO_ROOT": str(REPO),
            # And it announces itself, so the inventory pins can stand down. Those tests
            # assert the guard *count* and the *condition text* of named guards — read from
            # whatever source they are pointed at. Inside a mutated copy one of those
            # conditions has been rewritten to `False`, so the pin fails and the sweep scores
            # a kill its own test manufactured. They skip rather than deselect, so the
            # collected population stays identical between baseline and mutant, which is what
            # the scorer compares.
            "UGENCE_GUARD_SWEEP": "1",
            "UGENCE_MINT_SITE": mint_site,
            "UGENCE_MINT_OUT": str(workdir / ".ugence-mints"),
        },
    )
    mint_path = workdir / ".ugence-mints"
    mints = None
    message_only = []
    if mint_path.exists():
        try:
            payload = json.loads(mint_path.read_text())
            mints = payload.get("mints")
            message_only = payload.get("message_only", [])
        except ValueError:
            mints = None
    output = process.stdout + process.stderr
    tail = " | ".join(line for line in output.strip().splitlines()[-6:])[:600]
    # Every non-scorable answer carries the tail. "collection error" on its own names a
    # category, not a cause, and a sweep that cannot say why it did not run is a sweep
    # nobody can fix.
    if "SyntaxError" in output:
        return {"scored": False, "why": f"syntax error; last lines: {tail}", "failed": []}
    if "during collection" in output.lower():
        return {"scored": False, "why": f"collection error; last lines: {tail}", "failed": []}
    counted = {
        outcome: int(value)
        for value, outcome in re.findall(
            r"(\d+) (passed|failed|skipped|errors?|xfailed|xpassed)\b", output
        )
    }
    collected = sum(counted.values()) if counted else None
    if collected is None:
        # Carry the tail. Without it "no outcome counts reported" says only that something
        # went wrong, which is exactly as useful as saying nothing.
        return {
            "scored": False,
            "why": f"no outcome counts reported; last lines: {tail}",
            "failed": [],
        }
    if baseline_collected is not None and collected != baseline_collected:
        return {
            "scored": False,
            "why": (
                f"collected {collected}, baseline {baseline_collected}; the mutation "
                "changed what could be collected, so this is not a valid kill"
            ),
            "failed": [],
        }
    if require_green and (counted.get("failed") or counted.get("error") or counted.get("errors")):
        # A red baseline makes every later kill unattributable: the scorer decides a mutant
        # died because *some* test failed, and a test that was already failing satisfies
        # that without the mutation having done anything. The whole sweep is void, so this
        # refuses rather than reporting numbers nobody can rely on.
        return {
            "scored": False,
            "why": (
                "the baseline suite is not green — "
                f"{counted.get('failed', 0)} failed, "
                f"{counted.get('error', 0) + counted.get('errors', 0)} errored; "
                f"last lines: {tail}"
            ),
            "collected": collected,
            "failed": _noticed(output),
        }
    return {
        "scored": True,
        "mints": mints,
        "message_only_failures": message_only,
        "why": "",
        "collected": collected,
        "failed": _noticed(output),
    }


def _noticed(output: str) -> list:
    """Every test the suite reported as not passing — failures **and** errors.

    This read only ``^FAILED`` lines. A mutant that turns tests into setup or teardown
    ``ERROR``s therefore produced no noticed failures and was scored ``SURVIVED``. For a
    ``SCORED`` guard that is merely pessimistic — a survivor is a coverage defect that gets
    investigated. For an ``EXCLUDED`` one it is unsafe in the direction that matters: the
    stale-exclusion check asks whether an excluded guard was in fact killed, and a kill that
    only ever showed up as an ERROR would never contradict the exclusion.
    """

    return re.findall(r"^(?:FAILED|ERROR) (\S+)", output, re.M)


def _workdir(config: PackageConfig) -> Path:
    """The copy keeps the package's own directory name.

    It used to be called ``package``, and that was not cosmetic. Phase 5B's suite asserts
    its own directory name — ``assert here.name == "cloud-scaling-policy-authenticity"`` —
    so under the old name that test failed in *every* run of that package's sweep, baseline
    and mutant alike. Since a mutant was scored killed whenever any test failed, all 115
    Phase 5B guards were reported killed no matter what the mutation did. A copy that is
    not a faithful stand-in for the package measures the copy, not the package.
    """

    root = Path(tempfile.gettempdir()) / f"ugence-sweep-{config.key}"
    return root / config.package_dir.split("/")[-1]


#: A pytest plugin dropped into the copy. It replaces the mint function everywhere it is
#: already bound — not just on its defining module — because a test that did
#: ``from pkg import build_x`` holds its own reference, and patching one name would count
#: nothing. Written into the copy rather than the package: the tracked tree is never touched.
#:
#: ``UGENCE_MINT_SITE`` accepts ``module:function`` and, since guard-coverage ADR §5
#: (D-GC-6), ``module:Class.method``. That is a strict widening — an existing
#: ``module:function`` value keeps its meaning exactly — and it exists because a package's
#: true mint is not always module-level: ``capacity-bounds-policy`` mints its
#: ``PolicyArtifactDescriptor`` in ``CapacityBoundsPolicyFamilyAdapter.describe``, and its
#: only module-level candidate returns a *coordinate*, which answers a different question.
#: An inline class construction is deliberately still not wrappable by name: §5 rules that
#: wrapping one would break ``isinstance`` and the dataclass path, so a mint counter that
#: changed the program under test would be measuring the instrumentation. Where that leaves
#: a mint uncovered the package names it in ``uncovered_mints`` and the inventory discloses
#: it.
#: A RAW literal, and that is load-bearing: the plugin's detector regexes carry ``\b`` and
#: ``\.``, and a non-raw triple-quote processed every ``\b`` into a backspace byte on the
#: way into the copy — so ``\btype\s*\(``, ``\.outcome\b`` and ``\.\w*reason\b`` never
#: matched at runtime, and every statement they exist to recognise as a typed read was
#: flagged message-only. The engine's own detector tests compile the pattern from this
#: *source* text, where the escapes are intact, which is exactly why they could not see
#: it; ``test_the_plugin_literal_survives_escape_processing`` now checks the literal the
#: copy actually receives.
_MINT_PLUGIN = r'''
import atexit
import os
import sys


_COUNT = [0]


def pytest_configure(config):
    import importlib

    module_name, target = os.environ["UGENCE_MINT_SITE"].split(":")
    module = importlib.import_module(module_name)

    # ``Class.method`` resolves by a second getattr; a bare name keeps its old meaning.
    owner, _, attribute = target.rpartition(".")
    holder = getattr(module, owner) if owner else module
    original = getattr(holder, attribute)

    def counting(*args, **kwargs):
        result = original(*args, **kwargs)
        _COUNT[0] += 1
        return result

    counting.__wrapped__ = original

    if owner:
        # A method is reached through exactly one attribute — its class — so there is no
        # second binding to chase. Set on the class the name resolved through, which is
        # the class the tests instantiate.
        #
        # The descriptor has to be put back the way it was found. ``getattr`` on a class
        # unwraps ``staticmethod``/``classmethod``, so writing the plain wrapper back
        # re-introduces an implicit first argument and every call raises TypeError. That
        # fails loudly — the baseline goes red and ``require_green`` voids the whole sweep
        # rather than manufacturing a kill — but it voids a sweep that should have run.
        # ``adapter.py``'s ``_canonical_projection`` is a staticmethod, so this is the
        # next mint site in the very package this was written for.
        import inspect

        declared = inspect.getattr_static(holder, attribute)
        if isinstance(declared, staticmethod):
            setattr(holder, attribute, staticmethod(counting))
        elif isinstance(declared, classmethod):
            # ``original`` is already bound to the class, so the wrapper must not receive
            # it a second time; it is re-wrapped as a staticmethod to keep the call shape
            # callers use while counting exactly once.
            setattr(holder, attribute, staticmethod(counting))
        else:
            setattr(holder, attribute, counting)
        return

    for bound in list(sys.modules.values()):
        if bound is None:
            continue
        try:
            names = vars(bound)
        except TypeError:
            continue
        for name, value in list(names.items()):
            if value is original:
                setattr(bound, name, counting)


import re as _re

_MESSAGE_ONLY = []
_ANY_FAILURE = []


#: An assertion that reads the refusal's prose. `str(<name>.value)` is the pytest.raises
#: idiom, `.detail` the outcome-tuple one, `.args[` the bare-exception one. All three are
#: message reads under ADR Phase 5 §9.1.
_MESSAGE_READS = _re.compile(r"str\(\s*\w+(\.value)?\s*\)|\.detail\b|\.args\[")

#: An assertion that reads the typed half of the refusal. `pytest.raises` counts: a
#: statement that both raises-checks and message-checks has asserted the exception class,
#: so its failure is not attributable to the message alone.
#:
#: Recalibrated per guard-coverage ADR §6 (D-GC-7). `\.reason\b` required a *literal*
#: `.reason`, so every qualified accessor a real package publishes missed it —
#: `.rejection_reason`, `.abstention_reason` and `.status` all read the typed half and
#: were all classified message-only. The error over-flagged rather than under-flagged, so
#: nothing unsafe shipped behind it, but it misreported which contract the suite tests.
_TYPE_READS = _re.compile(
    r"\.\w*reason\b|\.\w*status\b|\.outcome\b|isinstance\s*\(|"
    r"pytest\.raises\s*\(|\btype\s*\("
)


def _failing_statement(call):
    """The source of the statement that actually failed, independent of ``--tb=no``.

    ``item.repr_failure`` renders under the configured tbstyle, and under ``--tb=no`` what
    comes back is pytest's *rewritten explanation* — `assert 'a' in 'b'` with its `where`
    lines — never the source. No message idiom appears literally in that text, so a detector
    reading it matches nothing and every mutant looks type-killed. The traceback entry's
    ``statement`` is the source itself and does not depend on tbstyle, so ``--tb=no`` keeps
    its log-size benefit and the detector still sees what the test wrote.

    The last entry is the frame the assertion is in, which is the right frame even when the
    assertion lives in a helper the test called.
    """

    try:
        return str(call.excinfo.traceback[-1].statement)
    except Exception:  # noqa: BLE001
        return ""


def pytest_runtest_makereport(item, call):
    """Record, per failing test, whether the assertion that failed reads only a *message*.

    §9.1 makes the typed refusal the contract and the message prose. A guard whose kill is
    attributable only to a message assertion has not been shown to carry authority — it is a
    diagnostic-only guard being scored.

    The judgement is made on the **failing statement alone**, not the displayed frame. A
    frame contains the whole test: scoring on it means one `with pytest.raises(...)` line
    anywhere above suppresses every message-only finding below it, which is exactly the
    case this rule exists to catch — the type assertion passed and the message assertion is
    what failed.
    """

    if call.when != "call" or call.excinfo is None:
        return
    _ANY_FAILURE.append(item.nodeid)
    statement = _failing_statement(call)
    if _MESSAGE_READS.search(statement) and not _TYPE_READS.search(statement):
        _MESSAGE_ONLY.append(item.nodeid)


def pytest_sessionfinish(session, exitstatus):
    import json

    with open(os.environ["UGENCE_MINT_OUT"], "w", encoding="utf-8") as handle:
        json.dump(
            {
                "mints": _COUNT[0],
                "failed": _ANY_FAILURE,
                "message_only": _MESSAGE_ONLY,
            },
            handle,
        )
'''


def prepare_copy(config: PackageConfig) -> Path:
    """A disposable copy **outside the repository**, so no repo-wide scan ever sees it."""

    workdir = _workdir(config)
    if workdir.parent.exists():
        shutil.rmtree(workdir.parent)
    workdir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(config.root, workdir, ignore=shutil.ignore_patterns(
        "__pycache__", "*.pyc", ".pytest_cache", "build", "dist", "*.egg-info"
    ))
    (workdir / "_ugence_mint_counter.py").write_text(_MINT_PLUGIN, encoding="utf-8")
    return workdir


def write_inventory(
    config: PackageConfig, guards: list, agreement: dict, leftout: dict, verdict: dict
) -> None:
    """The checked-in inventory: every guard, its shape, and its classification.

    Checked in on purpose. The *sweep* is a pass/fail gate and its output belongs in CI
    artifacts; the *inventory* is the thing that drifts silently — a guard added without a
    classification, or removed without anyone noticing — so it is a file a reviewer diffs.
    """

    lines = [
        f"# Guard inventory — `{config.package_dir.split('/')[-1]}`",
        "",
        "Generated by `scripts/cloud_scaling/guard_sweep.py --inventory-only`. Do not edit by",
        "hand: CI regenerates this and fails on any difference.",
        "",
        *((config.inventory_note, "") if config.inventory_note else ()),
        f"**{len(guards)} outcome-bearing guards.** A guard is a decision point whose body can",
        "reach a refusal. What counts as a refusal differs by package and is recorded per guard",
        "below: Phase 5A raises; Phase 5B also returns `_refuse(...)` at a gate and",
        "`(_Outcome.X, …)` from the helper that decided it. Applying one package's definition to",
        "another is not a stylistic choice — a raise-only reading of this package would miss",
        f"{sum(1 for g in guards if g.shape != 'raise')} of the guards below.",
        "",
    ]
    if config.decision_classes:
        counts = {
            kind: sum(1 for g in guards if g.kind == kind)
            for kind in sorted(config.decision_classes)
        }
        lines += [
            "Beyond the `if`/conditional-expression layer this package also inventories the",
            "decision classes the guard-coverage ADR ratified, each with its own operator:",
            "",
        ]
        described = {
            "except-arm": (
                "`except` arms that return a typed rejection, neutralised by collapsing "
                "the reason member to a sentinel (ADR §4.1). The refusal survives and "
                "only the reason moves, so a suite that asks only whether *something* "
                "was rejected cannot see the mutation"
            ),
            "helper-admission": (
                "statement-level calls to a raising helper, neutralised by deleting the call "
                "(ADR §4.2). Neutralising the helper's own `if` proves the check works, not "
                "that it is applied here"
            ),
            "else-arm": (
                "terminal `else` arms that refuse, neutralised by replacing the arm with "
                "`pass` (ADR §4.3). An `else` has no header, so `if False:` cannot reach it"
            ),
        }
        for kind, count in counts.items():
            lines.append(f"* **{count} `{kind}`** — {described.get(kind, '')}.")
        lines.append("")
    multiple = [g for g in guards if g.multiplicity > 1] if config.record_multiplicity else []
    if multiple:
        # Emitted only where a site actually carries more than one invariant, so a package
        # with no such loop keeps a byte-identical inventory. The guard-coverage ADR §1
        # forecloses renumbering the two Phase 5 inventories, and a section that appeared
        # in every file saying "every multiplicity is 1" would rewrite all four.
        lines += [
            "## Static sites that decide more than one invariant",
            "",
            "Guard-coverage ADR §7.2, ruled at ratification: a guard inside a loop over a",
            "fixed set of flags is **one** static site with a recorded semantic",
            "multiplicity, not unrolled into one scored site per flag. One mutation",
            "neutralises all of them together, so a kill shows only that *at least one* is",
            "tested — the discrimination burden falls on the suite (§6's within-class",
            "criterion), not on this count. Each multiplicity below is read from the",
            "iterated constant in the source, not recorded by hand.",
            "",
            "| Module:line | Decides | Iterated over |",
            "|---|---|---|",
        ]
        for g in multiple:
            lines.append(
                f"| `{g.module}:{g.lineno}` | {g.multiplicity} invariants | "
                f"`{g.condition[:60]}` |"
            )
        lines += [
            "",
            f"So this package's {len(guards)} static guard sites decide "
            f"{sum(g.multiplicity for g in guards)} invariants in total.",
            "",
        ]
    if config.uncovered_mints:
        lines += [
            "## Mint coverage, and what it does not cover",
            "",
            f"The mint counter wraps `{config.mint_site}`. Coverage is **partial**, and the",
            "uncovered mints are named here rather than left for a reader to notice — an",
            "undisclosed partial count is worse than a disclosed one (ADR §5):",
            "",
        ]
        for site, why in config.uncovered_mints:
            lines.append(f"* `{site}` — {why}")
        lines.append("")
    lines += [
        "## Reconciliation with the recorded inventories",
        "",
    ]
    if agreement:
        lines += ["| Recorded | Defined over | Recorded count | Re-derived here | Agrees |",
                  "|---|---|---|---|---|"]
        for name, row in agreement.items():
            lines.append(
                f"| `{name}` | {', '.join(f'`{m}`' for m in row['scope'])} | {row['expected']} "
                f"| {row['measured']} | {'yes' if row['agrees'] else '**NO**'} |"
            )
        lines += [
            "",
            "Both are re-derived from source here rather than trusted: a count nobody can",
            "reproduce is a count nobody can defend. They are defined over a *subset* of the",
            "modules and a *narrower* shape than this inventory — a `raise` alone in the body of",
            "its enclosing `if` — which is why this total is larger and neither number moves.",
            "",
        ]
    else:
        lines += ["This package records no prior inventory; this is the first one.", ""]

    excluded_rows = [
        row for row in verdict["classified"].values() if row["status"] == "EXCLUDED"
    ]
    lines += [
        "## Classification",
        "",
        f"Every guard is classified: **{len(guards) - len(excluded_rows)} `SCORED`** — the",
        "sweep neutralises it and the suite must fail — and",
        f"**{len(excluded_rows)} `EXCLUDED`**, each with a reason from a closed vocabulary and",
        "a test that measures the reason. A guard is never excluded because it survived; a",
        "survivor with no prior declaration fails the sweep.",
        "",
    ]
    if excluded_rows:
        lines += ["| Module:line | Reason | Why | Measured by |", "|---|---|---|---|"]
        for row in excluded_rows:
            lines.append(
                f"| `{row['module']}:{row['line']}` | `{row['reason']}` | "
                f"{row['detail']} | `{row['evidence']}` |"
            )
        lines.append("")
    else:
        lines += ["No guard in this package is excluded: every one is scored.", ""]

    lines += [
        "## Not counted, and why",
        "",
        f"* **{leftout['except_arms']} `except` arms** that raise. The `if False:` operator",
        "  cannot neutralise a handler, so they are outside this operator rather than overlooked.",
        f"* **{leftout['boolean_subterms']} extra sub-terms** of boolean guards. `if a and b:` is",
        "  neutralised and scored as one guard; scoring each side independently is a different",
        "  operator.",
        "",
        "## Every guard",
        "",
        "| # | Module:line | Kind | Shape | Class | Recorded in | Condition |",
        "|---|---|---|---|---|---|---|",
    ]
    for g in guards:
        condition = g.condition.replace("|", "\\|")
        if len(condition) > 78:
            condition = condition[:75] + "…"
        status = verdict["classified"][g.index]["status"]
        lines.append(
            f"| {g.index} | `{g.module}:{g.lineno}` | {g.kind} | {g.shape} | {status} | "
            f"{g.recorded_in or '—'} | `{condition}` |"
        )
    lines.append("")
    (config.root / "GUARD_INVENTORY.md").write_text("\n".join(lines), encoding="utf-8")


def shard_of(index: int, shard_n: int) -> int:
    """Which shard owns this guard. One function, so assignment and aggregation agree.

    ``(index - 1) % n`` partitions ``1..N`` into ``n`` classes that are disjoint and cover
    every index — but the aggregator proves that against the actual results rather than
    trusting the arithmetic, because a shard that never ran also produces no duplicate.
    """

    return (index - 1) % shard_n + 1


def classify(config: PackageConfig, guards: list) -> dict:
    """Every inventoried guard, with its declared classification.

    A guard is ``SCORED`` unless it is declared excluded, and a declared exclusion that
    matches no guard is an error rather than a no-op — that is what catches an exclusion
    left behind after the guard it named was rewritten or removed.
    """

    # ``(module, condition)`` is stable across line shifts, which is why it is the key —
    # but it is not unique. ``target.py`` carries three guards reading exactly
    # ``not isinstance(data, Mapping)``. An exclusion on such a key would silently cover
    # all three, so a key matching more than one guard is refused rather than resolved.
    #
    # A three-element key ``(module, condition, function)`` names the enclosing ``def``
    # as well, for the case where the two-element one genuinely cannot say which guard is
    # meant: ``adapter.py`` calls ``_validate_authenticated_output(authenticated)`` from
    # both ``project`` and ``evaluate``, and the two have different reachability. This is
    # a strict widening — every existing two-element key keeps its exact meaning, and the
    # inventory is unchanged, because the function is used for matching only and is never
    # emitted. Collision is still refused, now against whichever key length is declared.
    occupants = {}
    for guard in guards:
        occupants.setdefault((guard.module, guard.condition), []).append(guard.index)
        occupants.setdefault(
            (guard.module, guard.condition, guard.function), []
        ).append(guard.index)
    colliding = sorted(
        f"{key[0]}: {key[1]} (guards {indices})"
        for key, indices in occupants.items()
        if len(indices) > 1 and key in config.exclusions
    )

    classified = {}
    matched = set()
    for guard in guards:
        key = (guard.module, guard.condition, guard.function)
        if key not in config.exclusions:
            key = (guard.module, guard.condition)
        if key in config.exclusions and len(occupants[key]) > 1:
            # Ambiguous: classified SCORED so the sweep still demands a kill, and reported
            # as invalid below so the run fails rather than quietly under-scoring.
            classified[guard.index] = {
                "status": "SCORED",
                "module": guard.module,
                "line": guard.lineno,
                "condition": guard.condition,
            }
            matched.add(key)
            continue
        if key in config.exclusions:
            matched.add(key)
            reason, detail, evidence = config.exclusions[key]
            classified[guard.index] = {
                "status": "EXCLUDED",
                "reason": reason,
                "detail": detail,
                "evidence": evidence,
                "module": guard.module,
                "line": guard.lineno,
                "condition": guard.condition,
            }
        else:
            classified[guard.index] = {
                "status": "SCORED",
                "module": guard.module,
                "line": guard.lineno,
                "condition": guard.condition,
            }
    orphans = sorted(f"{key[0]}: {key[1]}"
                     for key in set(config.exclusions) - matched)
    invalid = sorted(
        f"{key[0]}: {key[1]}"
        for key, (reason, detail, evidence) in config.exclusions.items()
        if reason not in EXCLUSION_REASONS or not detail.strip() or not evidence.strip()
    )
    return {
        "classified": classified,
        "orphan_exclusions": orphans,
        "invalid_exclusions": invalid,
        "colliding_exclusions": colliding,
    }


def aggregate(config: PackageConfig, shard_dir: Path, shard_n: int) -> dict:
    """Combine shard results and prove the sweep was total and non-overlapping.

    Three separate claims, each measured:

    * **assignment** — every inventory index belongs to exactly one shard;
    * **completeness** — every index produced exactly one terminal result, so nothing is
      missing and nothing was swept twice;
    * **baseline agreement** — every shard measured the same collected population, since a
      shard that collected a different suite was scoring against a different denominator.
    """

    guards = inventory(config)
    expected = {g.index for g in guards}
    seen = {}
    duplicates = []
    baselines = {}
    missing_shards = []
    for k in range(1, shard_n + 1):
        path = shard_dir / f"guard_sweep.shard{k}of{shard_n}.json"
        if not path.exists():
            missing_shards.append(k)
            continue
        payload = json.loads(path.read_text())
        baselines[k] = payload.get("baseline")
        for row in payload["results"]:
            index = row["index"]
            if index in seen:
                duplicates.append(index)
            seen[index] = row
            if shard_of(index, shard_n) != k:
                row["_misassigned_to"] = k
    misassigned = sorted(r["index"] for r in seen.values() if "_misassigned_to" in r)

    verdict = classify(config, guards)
    classified = verdict["classified"]
    survived = sorted(i for i, r in seen.items() if r.get("scored") and not r.get("killed"))
    killed = sorted(i for i, r in seen.items() if r.get("killed"))
    # A survivor is a coverage defect unless it was declared unscorable *before* it
    # survived. Reading the exclusion off the result would make every survivor its own
    # excuse, so the declaration is checked against the result rather than derived from it.
    return {
        "package": config.key,
        "shard_n": shard_n,
        "inventory_total": len(guards),
        "missing_shards": missing_shards,
        "missing_guards": sorted(expected - set(seen)),
        "duplicate_guards": sorted(set(duplicates)),
        "misassigned_guards": misassigned,
        "baselines": baselines,
        "baseline_agrees": len(set(baselines.values())) <= 1,
        "killed": killed,
        "survived": survived,
        "unscored": sorted(i for i, r in seen.items() if not r.get("scored")),
        "classification": {str(i): classified[i] for i in sorted(classified)},
        "unclassified_guards": sorted(set(expected) - set(classified)),
        "orphan_exclusions": verdict["orphan_exclusions"],
        "invalid_exclusions": verdict["invalid_exclusions"],
        "colliding_exclusions": verdict["colliding_exclusions"],
        "surviving_scored_guards": [
            i for i in survived if classified.get(i, {}).get("status") != "EXCLUDED"
        ],
        "message_only_kills": [
            i for i, r in seen.items() if r.get("killed_only_by_message")
        ],
        "minting_guards": [i for i, r in seen.items() if r.get("mints_more_than_baseline")],
        "stale_exclusions": [
            i for i in killed if classified.get(i, {}).get("status") == "EXCLUDED"
        ],
        "results": {str(i): seen[i] for i in sorted(seen)},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", choices=sorted(PACKAGES))
    parser.add_argument("--inventory-only", action="store_true")
    parser.add_argument("--shard", default="1/1", help="k/n — this shard of n")
    parser.add_argument("--aggregate", metavar="DIR",
                        help="combine shard results from DIR and prove the sweep was total")
    parser.add_argument("--shards", type=int, default=8, help="shard count for --aggregate")
    # Local iteration only; CI passes neither. See ``run_suite`` for why narrowing is safe.
    parser.add_argument("--only", help="sweep only these guard indices (comma-separated)")
    parser.add_argument("--suite", help="pytest target(s) instead of the whole suite")
    args = parser.parse_args()

    config = PACKAGES[args.package]
    # Reconciled before anything else runs, inventory and sweep alike: an inventory over
    # an incomplete module set answers a question about a different package, and a sweep
    # against one publishes coverage nothing measured.
    module_problems = {
        kind: entries for kind, entries in undeclared_modules(config).items() if entries
    }
    if module_problems:
        for kind, entries in sorted(module_problems.items()):
            for entry in entries:
                print(f"  MODULE {kind.upper().replace('_', ' ')}: {entry}", file=sys.stderr)
        print(
            "every discovered production module must be in module_order or in "
            "excluded_modules with a concrete reason",
            file=sys.stderr,
        )
        return 1
    guards = inventory(config)
    agreement = reconcile(config, guards)
    leftout = excluded(config)

    if args.inventory_only:
        payload = {
            "package": config.key,
            "total": len(guards),
            "reconciliation": agreement,
            "excluded": leftout,
            "guards": [
                {
                    "index": g.index,
                    "module": g.module,
                    "line": g.lineno,
                    "condition": g.condition,
                    "kind": g.kind,
                    "shape": g.shape,
                    "recorded_in": g.recorded_in,
                    "outcome": g.outcome,
                    # Present only where the package discloses multiplicity and the site
                    # decides more than one invariant, so every other package keeps a
                    # byte-identical inventory file.
                    **(
                        {"multiplicity": g.multiplicity}
                        if config.record_multiplicity and g.multiplicity > 1
                        else {}
                    ),
                }
                for g in guards
            ],
        }
        (config.root / "guard_inventory.json").write_text(json.dumps(payload, indent=2) + "\n")
        verdict = classify(config, guards)
        (config.root / "guard_classification.json").write_text(
            json.dumps(
                {
                    "package": config.key,
                    "total": len(guards),
                    "scored": sum(
                        1 for r in verdict["classified"].values() if r["status"] == "SCORED"
                    ),
                    "excluded": sum(
                        1 for r in verdict["classified"].values() if r["status"] == "EXCLUDED"
                    ),
                    "classification": {
                        str(i): verdict["classified"][i] for i in sorted(verdict["classified"])
                    },
                },
                indent=2,
            )
            + "\n"
        )
        write_inventory(config, guards, agreement, leftout, verdict)
        undeclared = undeclared_except_arms(config)
        for problem in undeclared:
            print(f"  EXCEPT ARM HAS NO COLLAPSE SENTINEL: {problem}", file=sys.stderr)
        if (verdict["orphan_exclusions"] or verdict["invalid_exclusions"]
                or verdict["colliding_exclusions"] or undeclared):
            for problem in verdict["colliding_exclusions"]:
                print(f"  EXCLUSION KEY IS AMBIGUOUS: {problem}", file=sys.stderr)
            for problem in verdict["orphan_exclusions"]:
                print(f"  EXCLUSION NAMES NO GUARD: {problem}", file=sys.stderr)
            for problem in verdict["invalid_exclusions"]:
                print(f"  INVALID EXCLUSION: {problem}", file=sys.stderr)
            return 1
        print(f"{config.key}: {len(guards)} guards; reconciliation "
              + ", ".join(f"{k}={'ok' if v['agrees'] else 'DRIFTED'}" for k, v in agreement.items())
              + (" (no prior inventory)" if not agreement else ""))
        return 0 if all(v["agrees"] for v in agreement.values()) else 1

    if args.aggregate:
        report = aggregate(config, Path(args.aggregate), args.shards)
        (config.root / "guard_sweep_aggregate.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        total = report["inventory_total"]
        excluded_n = sum(
            1 for row in report["classification"].values() if row["status"] == "EXCLUDED"
        )
        if report["minting_guards"]:
            print(
                "  the last obstacle before a mint — removing any of these lets the package "
                f"produce an artifact the baseline refused: {report['minting_guards']}"
            )
        print(f"{config.key}: inventory {total}; "
              f"killed {len(report['killed'])}, survived {len(report['survived'])}, "
              f"unscored {len(report['unscored'])}; "
              f"classified {total - excluded_n} SCORED / {excluded_n} EXCLUDED")
        problems = []
        if report["missing_shards"]:
            problems.append(f"shards never reported: {report['missing_shards']}")
        if report["missing_guards"]:
            problems.append(f"guards with no result: {report['missing_guards']}")
        if report["duplicate_guards"]:
            problems.append(f"guards swept twice: {report['duplicate_guards']}")
        if report["misassigned_guards"]:
            problems.append(f"guards in the wrong shard: {report['misassigned_guards']}")
        if not report["baseline_agrees"]:
            problems.append(f"shards disagreed on the baseline: {report['baselines']}")
        if report["unclassified_guards"]:
            problems.append(f"guards with no classification: {report['unclassified_guards']}")
        if report["orphan_exclusions"]:
            problems.append(
                "exclusions naming no guard in the current inventory — the guard was "
                f"rewritten or removed and the exclusion outlived it: {report['orphan_exclusions']}"
            )
        if report["invalid_exclusions"]:
            problems.append(
                "exclusions with a reason outside the closed vocabulary, or with no detail "
                f"or no evidence: {report['invalid_exclusions']}"
            )
        if report["surviving_scored_guards"]:
            problems.append(
                "guards classified SCORED that survived — an open coverage defect, not an "
                f"exclusion: {report['surviving_scored_guards']}"
            )
        if report["message_only_kills"]:
            problems.append(
                "guards whose kill is attributable only to a message assertion — §9.1 makes "
                "the message prose, so these are diagnostic-only guards being scored: "
                f"{report['message_only_kills']}"
            )
        if report["colliding_exclusions"]:
            problems.append(
                "exclusions whose (module, condition) key matches more than one guard, so "
                "the exclusion cannot say which it means: "
                f"{report['colliding_exclusions']}"
            )
        if report["unscored"]:
            problems.append(
                "guards the sweep could not score at all — the mutant did not run, so "
                f"nothing is known about them: {report['unscored']}"
            )
        if report["stale_exclusions"]:
            problems.append(
                "guards classified EXCLUDED that were in fact killed; the exclusion is "
                f"stale and the guard is scored: {report['stale_exclusions']}"
            )
        for problem in problems:
            print(f"  INCOMPLETE: {problem}", file=sys.stderr)
        return 1 if problems else 0

    shard_k, shard_n = (int(part) for part in args.shard.split("/"))
    mine = [g for g in guards if shard_of(g.index, shard_n) == shard_k]

    suite_args = tuple(args.suite.split()) if args.suite else ("tests",)
    if args.only:
        wanted = {int(part) for part in args.only.replace(",", " ").split()}
        mine = [g for g in mine if g.index in wanted]

    workdir = prepare_copy(config)
    baseline = run_suite(
        workdir, suite_args=suite_args, require_green=True, mint_site=config.mint_site,
        extra_env=config.suite_env,
    )
    if not baseline["scored"]:
        print(f"baseline is not scorable: {baseline['why']}", file=sys.stderr)
        return 2
    baseline_failures = set(baseline["failed"])
    print(f"baseline collected {baseline['collected']}", flush=True)

    results = []
    for guard in mine:
        prepare_copy(config)
        mutate(config, guard, workdir)
        outcome = run_suite(
            workdir,
            baseline_collected=baseline["collected"],
            suite_args=suite_args,
            mint_site=config.mint_site,
            extra_env=config.suite_env,
        )
        # Differential, not absolute. ``require_green`` already refuses a red baseline, so
        # this should never subtract anything — it is here because the failure it guards
        # against (a test that fails identically in every run, crediting every guard with a
        # kill it did not earn) is not one the numbers reveal on their own.
        new_failures = [f for f in outcome["failed"] if f not in baseline_failures]
        killed = outcome["scored"] and bool(new_failures)
        # Did neutralising this guard let the package MINT something the baseline refused?
        # That is a different and worse class than "the refusal changed": it means the guard
        # was the last obstacle before an artifact. Three such guards were found by accident
        # before this was measured; this makes the class visible rather than lucky.
        # A kill attributable ONLY to message assertions is not a kill under §9.1: the
        # message is prose, so the guard changed no answer a caller may act on. It is a
        # diagnostic-only guard being scored, and the aggregate refuses it.
        message_only = set(outcome.get("message_only_failures") or ())
        killed_only_by_message = bool(new_failures) and set(new_failures) <= message_only
        baseline_mints = baseline.get("mints")
        mutant_mints = outcome.get("mints")
        mints_more = (
            baseline_mints is not None
            and mutant_mints is not None
            and mutant_mints > baseline_mints
        )
        results.append(
            {
                "index": guard.index,
                "module": guard.module,
                "line": guard.lineno,
                "condition": guard.condition,
                "kind": guard.kind,
                "shape": guard.shape,
                "recorded_in": guard.recorded_in,
                "scored": outcome["scored"],
                "why_not": outcome["why"],
                "killed": killed,
                "killed_by": new_failures[:5],
                "mints": mutant_mints,
                "mints_more_than_baseline": mints_more,
                "killed_only_by_message": killed_only_by_message,
            }
        )
        state = "KILLED" if killed else ("SURVIVED" if outcome["scored"] else "UNSCORED")
        note = "  MINTS" if mints_more else ""
        if killed_only_by_message:
            note += "  MESSAGE-ONLY KILL"
        print(
            f"  [{guard.index:>3}] {guard.module}:{guard.lineno} {state}{note}", flush=True
        )

    # Outside the repository, deliberately. A sweep that wrote into the tracked tree would
    # make the very check that proves it did not mutate anything (`git diff --exit-code`)
    # report its own output as a mutation.
    narrowed = bool(args.only or args.suite)
    name = "guard_sweep.local.json" if narrowed else f"guard_sweep.shard{shard_k}of{shard_n}.json"
    out = workdir.parent / name
    out.write_text(json.dumps({"baseline": baseline["collected"], "results": results}, indent=2))
    print(f"wrote {out}")

    verdict = classify(config, guards)["classified"]
    survivors = [
        r for r in results
        if r["scored"] and not r["killed"]
        and verdict.get(r["index"], {}).get("status") != "EXCLUDED"
    ]
    declared = [
        r for r in results
        if r["scored"] and not r["killed"]
        and verdict.get(r["index"], {}).get("status") == "EXCLUDED"
    ]
    unscored = [r for r in results if not r["scored"]]
    print(f"\nshard {shard_k}/{shard_n}: {len(results)} guards, "
          f"{len(results) - len(survivors) - len(declared) - len(unscored)} killed, "
          f"{len(survivors)} survived, {len(declared)} declared unscorable, "
          f"{len(unscored)} unscored")
    for row in declared:
        reason = verdict[row["index"]]["reason"]
        print(f"  EXCLUDED  {row['module']}:{row['line']}  {reason}")
    for row in survivors:
        print(f"  SURVIVED {row['module']}:{row['line']}  {row['condition'][:70]}")
    for row in unscored:
        print(f"  UNSCORED {row['module']}:{row['line']}  {row['why_not'][:70]}")
    # A survivor is a defect unless it was *declared* unscorable before it survived, with a
    # reason from the closed vocabulary and a test that measures the claim. Anything else
    # this shard found is unaccounted for, and the shard says so with its exit code.
    return 1 if survivors or unscored else 0


if __name__ == "__main__":
    raise SystemExit(main())
