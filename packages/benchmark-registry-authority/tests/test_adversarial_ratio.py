"""At least 2:1 adversarial-to-happy **distinct properties**.

Counted as distinct test *functions*, never as parametrizations: a happy path
parametrized fifty ways is one property, and so is an adversarial one. Counting
generated cases would let a single well-parametrized happy test swamp the ratio
while proving nothing new.

The convention is mechanical and checkable: a property whose function name
begins ``test_happy_`` asserts that the intended thing works; every other
property asserts that something a careless consumer or an attacker would try is
refused, is absent, is unconstructible, or is detectable.

Happy properties are not padding — a suite with none of them is a suite whose
adversarial assertions might all be passing because the fixtures are broken. The
ratio bounds them rather than banning them.
"""

from __future__ import annotations

import ast
import pathlib

TESTS = pathlib.Path(__file__).resolve().parent
REQUIRED_RATIO = 2.0


def _properties():
    happy, adversarial = [], []
    for path in sorted(TESTS.rglob("test_*.py")):
        if path.name == pathlib.Path(__file__).name:
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if not node.name.startswith("test_"):
                continue
            entry = f"{path.name}::{node.name}"
            if node.name.startswith("test_happy_"):
                happy.append(entry)
            else:
                adversarial.append(entry)
    return happy, adversarial


def test_the_suite_has_a_meaningful_number_of_properties_at_all():
    happy, adversarial = _properties()
    assert len(happy) + len(adversarial) >= 200


def test_there_is_at_least_one_happy_property_per_test_module():
    """An adversarial suite with no happy path may be passing on broken fixtures."""

    happy, _adversarial = _properties()
    modules_with_happy = {entry.split("::")[0] for entry in happy}
    all_modules = {
        path.name
        for path in sorted(TESTS.rglob("test_*.py"))
        if path.name != pathlib.Path(__file__).name
    }
    missing = sorted(all_modules - modules_with_happy)
    # Modules that are entirely structural assertions about absence have no
    # meaningful happy path; they are listed explicitly rather than exempted by
    # a pattern, so adding one is a deliberate act.
    allowed_without_happy = {
        "test_constructor_bypass.py",
        "test_no_authority.py",
        "test_chain_integrity.py",
        "test_transition_binding.py",
        "test_public_api.py",
        "test_inventories.py",
        "test_dependency_boundary.py",
        "test_milestone_boundary.py",
        "test_two_lifecycle_authorities.py",
        "test_supersession.py",
        "test_refusal_vocabulary.py",
        "test_confusable_and_ports.py",
        "test_requests.py",
        "test_scope_expectations.py",
        "test_read_payloads.py",
        "test_tenancy.py",
        "test_envelopes.py",
        "test_timestamps.py",
        "test_chain_substitution.py",
        "test_canonicalization.py",
        "test_hostile_objects.py",
        "test_chain_state_machine.py",
    }
    assert set(missing) <= allowed_without_happy, missing


def test_the_adversarial_to_happy_ratio_is_at_least_two_to_one():
    happy, adversarial = _properties()
    assert happy, "no happy-path property at all"
    ratio = len(adversarial) / len(happy)
    assert ratio >= REQUIRED_RATIO, (
        f"{len(adversarial)} adversarial : {len(happy)} happy = {ratio:.2f}:1, "
        f"below the required {REQUIRED_RATIO}:1"
    )


def test_the_ratio_is_reported_for_the_delivery_record():
    happy, adversarial = _properties()
    print(
        f"\nBR-2C-0 distinct properties: {len(adversarial)} adversarial, "
        f"{len(happy)} happy, "
        f"ratio {len(adversarial) / len(happy):.2f}:1, "
        f"total {len(adversarial) + len(happy)}"
    )
