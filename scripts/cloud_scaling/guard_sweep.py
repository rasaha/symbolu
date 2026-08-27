#!/usr/bin/env python3
"""Guard inventory and gate-removal mutation sweep for the Cloud Scaling packages.

One engine, three configurations. `cloud-scaling-producer-attestation` already had a sweep
of its own; this generalises the method to `cloud-scaling-authorization-contracts` and
`cloud-scaling-policy-authenticity`, which had none — their guard inventories had never been
swept in CI at all.

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
    #: The inventories this package already records, and what each is defined over.
    recorded: tuple
    #: Guards this operator cannot score, keyed by ``(module, condition)`` rather than by
    #: line number: a line shifts every time anything above it changes, and an exclusion
    #: that silently re-points at a different guard is worse than no exclusion at all.
    exclusions: dict = field(default_factory=dict)

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
            ("identifiers.py", "ours != theirs"): (
                "unscorable-by-single-checkout-fixture",
                "Compares this package's ratified identifiers against Phase 4C's, which "
                "live in a separately-versioned distribution admitted by an open-ended "
                "`ugence-cloud-scaling-risk-integration>=0.1.0` pin. Under a resolution "
                "that pin permits, the condition is true and the guard fires — so this is "
                "not an equivalent mutant, and the earlier claim that it was is withdrawn. "
                "It is unscorable only because the sweep fixture installs one checkout and "
                "cannot vary the resolution. The test named below re-runs the assertion "
                "against whatever is actually installed.",
                "tests/test_guard_coverage.py::"
                "test_the_ratified_identifiers_have_not_drifted_from_phase_4c",
            ),
            ("identifiers.py", "controller_actions != CANONICAL_ACTION_TYPES"): (
                "unreachable-behind-earlier-guard",
                "Cannot observe an ActionKind drift, because the import that supplies its "
                "left operand fails first: reaching Phase 4C for `_PHASE4C_ACTION_TYPES` "
                "runs Phase 4C's own import-time ActionKind guard, which raises before "
                "this module finishes importing. Measured, not reasoned — the test below "
                "drifts the controller's enum in a subprocess and reads which guard's "
                "ImportError comes back. If it ever names this guard, this exclusion is "
                "void.",
                "tests/test_guard_coverage.py::"
                "test_the_action_kind_drift_guard_is_unreachable_behind_phase_4c",
            ),
            ("identifiers.py", "PRODUCER_SIGNING_PURPOSE == PURPOSE_CAPACITY_ACTION"): (
                "equivalent-mutant",
                "A collision assertion between two frozen literals defined in this module, "
                "in this distribution. No dependency resolution can move either, so the "
                "condition is false in every program this package can be part of and "
                "`if False:` is the same program on every path. The test below measures "
                "the inequality.",
                "tests/test_guard_coverage.py::"
                "test_the_drift_guards_are_equivalent_mutants_because_their_conditions_are_false",
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
    "policy-authenticity": PackageConfig(
        key="policy-authenticity",
        package_dir="packages/integration/cloud-scaling-policy-authenticity",
        dist_name="ugence_cloud_scaling_policy_authenticity",
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
            ("identifiers.py", "VERIFICATION_PROFILE == POLICY_AUTHORITY_PROTOCOL_ID"): (
                "unscorable-by-single-checkout-fixture",
                "The right operand is `AUTHORITY_PROTOCOL_ID`, imported from "
                "`ugence_policy_authority.api`. A Policy Authority release that renamed its "
                "protocol identifier to this package's verification profile would make the "
                "condition true, and this package consumes that protocol rather than being "
                "a version of it. Real and reachable; only unscorable by a fixture that "
                "installs one resolution.",
                "tests/test_guard_coverage.py::"
                "test_the_import_time_separations_hold_for_the_installed_distributions",
            ),
            ("identifiers.py", "POLICY_AUTHENTICITY_DIGEST_DOMAIN == POLICY_BODY_DIGEST_DOMAIN"): (
                "unscorable-by-single-checkout-fixture",
                "The right operand is the Policy Authority's own `POLICY_BODY_DIGEST_DOMAIN`. "
                "Collapsing the two domains would let a verification artifact's digest be "
                "read as a policy body digest, and an upstream release controls one side of "
                "the comparison.",
                "tests/test_guard_coverage.py::"
                "test_the_import_time_separations_hold_for_the_installed_distributions",
            ),
            ("identifiers.py", "REQUIRED_KEY_ENTITLEMENT is FORBIDDEN_KEY_ENTITLEMENT"): (
                "unscorable-by-single-checkout-fixture",
                "Both operands are members of the Policy Authority's `KeyEntitlement`. An "
                "upstream release that aliased ISSUE_POLICY and REVOKE_POLICY to one member "
                "would make the condition true and let a revoke-only key authenticate an "
                "issued policy.",
                "tests/test_guard_coverage.py::"
                "test_the_import_time_separations_hold_for_the_installed_distributions",
            ),
            ("identifiers.py", "CANONICAL_ACTION_TYPES != _RATIFIED_ACTION_TYPES"): (
                "unscorable-by-single-checkout-fixture",
                "The left operand is Phase 5A's `CANONICAL_ACTION_TYPES`, from a separately "
                "versioned distribution. Gate 16 selects an authenticated bound by this "
                "vocabulary, so a drifted set is exactly what this guard exists to refuse.",
                "tests/test_guard_coverage.py::"
                "test_the_import_time_separations_hold_for_the_installed_distributions",
            ),
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
            ("verification.py", "resolution.historical"): (
                "diagnostic-only",
                "Removing it leaves `implies_current_validity` — a read-only property equal "
                "to `resolved and not historical` — False on the next line, refusing with the "
                "same HISTORICAL_RESOLUTION_REFUSED outcome. Isolation would need a "
                "resolution that is historical *and* implies current validity, which the "
                "property makes impossible. Kept for the better message: 'this describes an "
                "instant before a verified revocation'.",
                "tests/test_guard_coverage.py::test_a_historical_resolution_is_refused",
            ),
            ("verification.py", "resolution.implies_current_validity is not True"): (
                "unreachable-behind-earlier-guard",
                "The mirror of the guard above. `implies_current_validity` is a read-only "
                "property of the authority's PolicyResolution, `verification.py:460` admits "
                "the resolution by exact type so no subclass can override it, and both ways "
                "to make it non-True are refused above: a non-RESOLVED status by the status "
                "gate and `historical` by the guard on the previous line. The two are a "
                "redundant pair defending one property, and neither single removal changes "
                "the typed refusal.",
                "tests/test_guard_coverage.py::"
                "test_the_current_validity_guard_is_unreachable_behind_the_historicity_guard",
            ),
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
            ("verification.py", "adapter_id != record.adapter_id"): (
                "diagnostic-only",
                "`adapter_id` is an input to the frame the body digest is reproduced from, "
                "so any value that trips this guard also fails the reproduction below it "
                "with the same POLICY_PROJECTION_DIGEST_MISMATCH outcome — there is no "
                "adapter id that disagrees with the record and still reframes to the signed "
                "digest. Kept because 'the projection names adapter X and the record names "
                "Y' is a diagnosis a port author can act on; 'the digest did not reproduce' "
                "is not.",
                "tests/test_guard_coverage.py::"
                "test_a_descriptor_naming_another_adapter_than_the_records_is_refused",
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
            ("verification.py", "absent"): (
                "diagnostic-only",
                "Every input this guard refuses is refused identically without it. A bound "
                "missing a field reaches `entry[name]` nineteen lines below, inside a "
                "deliberate `except Exception` backstop that re-raises as the same "
                "`_BoundsShapeError` and therefore the same POLICY_BOUNDS_MALFORMED "
                "outcome; only the message changes, from \"bounds[0] omits "
                "['max_permitted_delta']\" to \"bounds[0]: 'max_permitted_delta'\". Under "
                "ADR Phase 5 §9.1 the message is not the contract. The guard is kept "
                "because it names every absent field at once rather than the first one "
                "`entry[...]` happens to reach.",
                "tests/test_guard_coverage.py::"
                "test_a_signed_bound_this_profile_cannot_read_is_refused",
            ),
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
    recorded_in: str = ""
    outcome: str = ""
    scored: bool = False
    excluded_because: str = ""
    killed_by: list = field(default_factory=list)


def _outcome_names(node) -> list:
    """The typed outcomes this guard's body can produce, for the report's own reading."""

    names = []
    for statement in node.body:
        for inner in ast.walk(statement):
            if isinstance(inner, ast.Attribute) and isinstance(inner.value, ast.Name):
                if inner.value.id in {"_Outcome", "_Reason", "Reason"}:
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


def _refusal_shape(node, config: PackageConfig) -> str:
    """How this guard refuses, or ``""`` when it does not.

    The shape is reported per guard rather than collapsed, because it is the thing that
    differs between the two packages and the thing a copied definition gets wrong.
    """

    raises = False
    call = False
    tuple_return = False
    helper_call = False
    helpers = _raising_helpers(config)
    for statement in node.body:
        for inner in ast.walk(statement):
            if isinstance(inner, ast.Raise):
                raises = True
            elif isinstance(inner, ast.Expr) and isinstance(inner.value, ast.Call):
                # A *statement* call, never one whose result is bound. An admission is
                # called for its refusal and its return value is discarded;
                # ``issued_at = _parse_ts(issued_at)`` calls the same kind of helper for
                # its value, and that ``if`` is a normalisation branch rather than a gate.
                # Counting it made the sweep unscorable: neutralising a conversion changes
                # what the suite can even collect, which is not a kill and not a survival.
                call_node = inner.value
                name = getattr(call_node.func, "id", None) or getattr(
                    call_node.func, "attr", None
                )
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
    if raises:
        return "raise"
    if call:
        return "typed-refusal call"
    if tuple_return:
        return "typed-refusal tuple"
    if helper_call:
        return "raising-helper call"
    return ""


def _raise_alone(node) -> bool:
    """The canonical-65 shape: a ``raise`` alone in the body of its enclosing ``if``."""

    return len(node.body) == 1 and isinstance(node.body[0], ast.Raise)


def inventory(config: PackageConfig) -> list:
    guards = []
    index = 0
    recorded_scope = {
        name: (scope, count) for name, scope, count in config.recorded
    }
    for module in config.module_order:
        path = config.src / module
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        tree = ast.parse(source, filename=str(path))
        found = []
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                shape = _refusal_shape(node, config)
                if shape:
                    found.append((node, shape))
        for node, shape in sorted(found, key=lambda pair: pair[0].lineno):
            index += 1
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
                    outcome=", ".join(_outcome_names(node)),
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
            elif isinstance(node, ast.If) and _refusal_shape(node, config):
                if isinstance(node.test, ast.BoolOp):
                    boolean_subterms += len(node.test.values) - 1
    return {"except_arms": except_arms, "boolean_subterms": boolean_subterms}


def mutate(config: PackageConfig, guard: Guard, workdir: Path) -> None:
    """Rewrite exactly this guard's ``if`` header to ``if False:`` in the copy."""

    path = workdir / "src" / config.dist_name / guard.module
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
        [sys.executable, "-m", "pytest", *suite_args, "-p", "no:cacheprovider", "--tb=no"],
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
        },
    )
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
            "failed": re.findall(r"^FAILED (\S+)", output, re.M),
        }
    return {
        "scored": True,
        "why": "",
        "collected": collected,
        "failed": re.findall(r"^FAILED (\S+)", output, re.M),
    }


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


def prepare_copy(config: PackageConfig) -> Path:
    """A disposable copy **outside the repository**, so no repo-wide scan ever sees it."""

    workdir = _workdir(config)
    if workdir.parent.exists():
        shutil.rmtree(workdir.parent)
    workdir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(config.root, workdir, ignore=shutil.ignore_patterns(
        "__pycache__", "*.pyc", ".pytest_cache", "build", "dist", "*.egg-info"
    ))
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
        f"**{len(guards)} authority-bearing guards.** A guard is an `if` whose body can reach a",
        "refusal. What counts as a refusal differs by package and is recorded per guard below:",
        "Phase 5A raises; Phase 5B also returns `_refuse(...)` at a gate and `(_Outcome.X, …)`",
        "from the helper that decided it. Applying one package's definition to the other is not",
        f"a stylistic choice — a raise-only reading of this package would miss "
        f"{sum(1 for g in guards if g.shape != 'raise')} of the guards below.",
        "",
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
        "| # | Module:line | Shape | Class | Recorded in | Condition |",
        "|---|---|---|---|---|---|",
    ]
    for g in guards:
        condition = g.condition.replace("|", "\\|")
        if len(condition) > 78:
            condition = condition[:75] + "…"
        status = verdict["classified"][g.index]["status"]
        lines.append(
            f"| {g.index} | `{g.module}:{g.lineno}` | {g.shape} | {status} | "
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
    baseline = run_suite(workdir, suite_args=suite_args, require_green=True)
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
            workdir, baseline_collected=baseline["collected"], suite_args=suite_args
        )
        # Differential, not absolute. ``require_green`` already refuses a red baseline, so
        # this should never subtract anything — it is here because the failure it guards
        # against (a test that fails identically in every run, crediting every guard with a
        # kill it did not earn) is not one the numbers reveal on their own.
        new_failures = [f for f in outcome["failed"] if f not in baseline_failures]
        killed = outcome["scored"] and bool(new_failures)
        results.append(
            {
                "index": guard.index,
                "module": guard.module,
                "line": guard.lineno,
                "condition": guard.condition,
                "shape": guard.shape,
                "recorded_in": guard.recorded_in,
                "scored": outcome["scored"],
                "why_not": outcome["why"],
                "killed": killed,
                "killed_by": new_failures[:5],
            }
        )
        state = "KILLED" if killed else ("SURVIVED" if outcome["scored"] else "UNSCORED")
        print(f"  [{guard.index:>3}] {guard.module}:{guard.lineno} {state}", flush=True)

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
