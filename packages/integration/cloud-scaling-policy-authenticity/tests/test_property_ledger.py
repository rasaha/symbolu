"""Every test carries exactly one property category, and the ratio is counted, not claimed.

A boundary suite that is mostly happy paths measures that the boundary works, not that it
holds. The ledger below is machine-counted from the collected suite, so the claim cannot
drift from the tests.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

CATEGORIES = ("happy", "adversarial", "invariant")
TESTS = pathlib.Path(__file__).resolve().parent
MODULES = sorted(p for p in TESTS.glob("test_*.py"))


def _test_functions(module: pathlib.Path) -> list:
    """``(name, categories)`` for every top-level test function, read from the AST.

    Parsed rather than pattern-matched: a multi-line ``parametrize`` decorator defeats a
    line-oriented regex, and a ledger that silently sees no markers would report a compliant
    suite.
    """

    tree = ast.parse(module.read_text())
    found = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        categories = set()
        for decorator in node.decorator_list:
            target = decorator.func if isinstance(decorator, ast.Call) else decorator
            if isinstance(target, ast.Attribute) and target.attr in CATEGORIES:
                categories.add(target.attr)
        found.append((node.name, categories))
    return found


@pytest.mark.invariant
@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_every_test_carries_exactly_one_property_category(module):
    for name, categories in _test_functions(module):
        assert len(categories) == 1, f"{module.name}::{name} -> {sorted(categories)}"


@pytest.mark.invariant
def test_the_suite_is_adversarial_first():
    counts = dict.fromkeys(CATEGORIES, 0)
    for module in MODULES:
        for _name, categories in _test_functions(module):
            for category in categories:
                counts[category] += 1
    assert counts["happy"] >= 5, counts
    assert counts["invariant"] >= 10, counts
    # The ratified posture: attacks and absent-capability checks outnumber positive controls.
    assert counts["adversarial"] >= 2 * counts["happy"], counts


@pytest.mark.invariant
def test_the_declared_markers_are_the_ones_the_suite_uses():
    pyproject = (TESTS.parent / "pyproject.toml").read_text()
    for category in CATEGORIES:
        assert f'"{category}:' in pyproject
