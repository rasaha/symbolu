#!/usr/bin/env python3
"""Guard inventory and gate-removal mutation sweep for the Cloud Scaling packages.

One engine, a configuration per package. `cloud-scaling-producer-attestation` already had a
sweep of its own; this generalises the method to `cloud-scaling-authorization-contracts` and
`cloud-scaling-policy-authenticity`, which had none — their guard inventories had never been
swept in CI at all — and, since the guard-coverage ADR, to
`cloud-scaling-capacity-bounds-policy`, a package that carries no authority but does carry a
fail-closed admission invariant, which is exactly the thing a sweep can measure (ADR §2).

**Not every decision point is an `if`.** The guard-coverage ADR ratified two additive
classes the engine could not see in either direction — absent from the numerator *and* from
the disclosed denominator: a statement-level call to a raising helper (§4.2, deleted rather
than disabled) and a terminal `else` that refuses (§4.3, replaced by `pass`). Each is opted
into per package through `PackageConfig.decision_classes`, because enabling one changes what
a package's checked-in inventory counts.

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
    #: ``"helper-admission"`` (guard-coverage ADR §4.2, D-GC-4) and ``"else-arm"`` (§4.3,
    #: D-GC-5). Opt-in per package rather than global, because the guard-coverage ADR §1
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
        recorded=(),
        exclusions={},
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
    kind: str = "if"
    span: tuple = ()
    recorded_in: str = ""
    outcome: str = ""
    scored: bool = False
    excluded_because: str = ""
    killed_by: list = field(default_factory=list)


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


def _raising_helpers(config: PackageConfig) -> frozenset:
    """Function names in this package that can raise, directly or through each other.

    Derived from the source, not hand-listed. A hand list is a second inventory to keep in
    step with the first, and the guards it forgets are exactly the ones nobody was thinking
    about — ``verification.py:327`` and ``verified.py:488`` are two that a raise-only
    reading missed, each an ``if`` whose entire body is a call to an admission helper.

    Transitive by fixpoint: ``require_policy_digest`` raises directly, and anything whose
    body calls it inherits that. One level would miss the second rank.
    """

    direct = {}
    calls = {}
    for path in sorted(config.src.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            raises = any(isinstance(inner, ast.Raise) for inner in ast.walk(node))
            named = set()
            for inner in ast.walk(node):
                if isinstance(inner, ast.Call):
                    name = getattr(inner.func, "id", None) or getattr(inner.func, "attr", None)
                    if name:
                        named.add(name)
            direct[node.name] = direct.get(node.name, False) or raises
            calls.setdefault(node.name, set()).update(named)

    raising = {name for name, raises in direct.items() if raises}
    changed = True
    while changed:
        changed = False
        for name, named in calls.items():
            if name not in raising and (named & raising):
                raising.add(name)
                changed = True
    return frozenset(raising)


def _is_elif(node) -> bool:
    """An ``elif`` is an ``If`` in its parent's ``orelse`` at the parent's own column."""

    return (
        len(node.orelse) == 1
        and isinstance(node.orelse[0], ast.If)
        and node.orelse[0].col_offset == node.col_offset
    )


def _statement_span(node) -> tuple:
    return (node.lineno, node.col_offset, node.end_lineno, node.end_col_offset)


def _helper_admission_sites(tree, helpers: frozenset) -> list:
    """Statement-level calls to a raising helper — guard-coverage ADR §4.2 (D-GC-4).

    The class is decidable from the AST with no judgement: an ``ast.Expr`` whose call
    target is a name in the engine's existing transitive raising set. A call whose result
    is *bound* is an ``ast.Assign`` and is deliberately not in this class — deleting it
    would change what the program computes rather than only what it refuses.

    Why this is a decision point distinct from the helper's own ``if``: neutralising the
    helper's internal guard proves the check works, not that it is applied at this site.
    A dropped call admits the artifact without ever checking it, and no ``if False:``
    reaches a site that has no ``if`` header.
    """

    sites = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        name = getattr(call.func, "id", None) or getattr(call.func, "attr", None)
        if name in helpers:
            sites.append(node)
    return sites


def _else_arm_sites(tree, config: PackageConfig, helpers: frozenset) -> list:
    """Terminal ``else`` arms whose body refuses — guard-coverage ADR §4.3 (D-GC-5).

    An implementation-only extension of §9.1, not a new class: "a body that can reach a
    refusal makes the ``if`` a guard", and a terminal ``else`` is the last arm of that
    same ``if``. Only the operator was missing, because an ``else`` has no header.

    ``elif`` chains are excluded: an ``elif`` is an ``If`` of its own and is already
    inventoried on the ``if`` layer with its own condition.
    """

    sites = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If) or not node.orelse or _is_elif(node):
            continue
        if _refusal_shape_of(node.orelse, config, helpers):
            sites.append(node)
    return sites


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
    # Computed once by the caller where there is one: ``_raising_helpers`` re-parses
    # every module in the package, and calling it per candidate node made the inventory
    # quadratic in the size of the source.
    helpers = _raising_helpers(config) if helpers is None else helpers
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
    helpers = _raising_helpers(config)
    for module in config.module_order:
        path = config.src / module
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        tree = ast.parse(source, filename=str(path))
        found = []
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                shape = _refusal_shape(node, config, helpers)
                if shape:
                    found.append((node.lineno, node, shape))
            elif isinstance(node, ast.IfExp) and _selects_an_outcome(node):
                found.append((node.lineno, node, "outcome selection"))
        # The two additive decision classes, each enabled per package rather than
        # engine-wide — see ``PackageConfig.decision_classes`` for why.
        if "helper-admission" in config.decision_classes:
            for node in _helper_admission_sites(tree, helpers):
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
    helpers = _raising_helpers(config)
    for module in config.module_order:
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
    """

    path = workdir / "src" / config.dist_name / guard.module
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
_MINT_PLUGIN = '''
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
    occupants = {}
    for guard in guards:
        occupants.setdefault((guard.module, guard.condition), []).append(guard.index)
    colliding = sorted(
        f"{module}: {condition} (guards {indices})"
        for (module, condition), indices in occupants.items()
        if len(indices) > 1 and (module, condition) in config.exclusions
    )

    classified = {}
    matched = set()
    for guard in guards:
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
    orphans = sorted(f"{module}: {condition}"
                     for module, condition in set(config.exclusions) - matched)
    invalid = sorted(
        f"{module}: {condition}"
        for (module, condition), (reason, detail, evidence) in config.exclusions.items()
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
        if (verdict["orphan_exclusions"] or verdict["invalid_exclusions"]
                or verdict["colliding_exclusions"]):
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
        workdir, suite_args=suite_args, require_green=True, mint_site=config.mint_site
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
