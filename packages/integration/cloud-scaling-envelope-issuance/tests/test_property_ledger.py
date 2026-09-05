"""Every test carries one property category, and the adversarial-to-happy ratio is counted.

Counted over the source of the suite (one distinct property per test function; a
parametrised test is one property), against the module defaults in ``tests/conftest.py``
and any explicit ``@pytest.mark.<category>`` override.
"""

from __future__ import annotations

import ast
import collections
import pathlib

import pytest

from conftest import MODULE_PROPERTY_CATEGORY, PROPERTY_CATEGORIES

pytestmark = pytest.mark.invariant

TESTS = pathlib.Path(__file__).resolve().parent
REQUIRED_RATIO = 2.0


def _ledger() -> collections.Counter:
    counts: collections.Counter = collections.Counter()
    for path in sorted(TESTS.rglob("test_*.py")):
        module = path.stem
        default = MODULE_PROPERTY_CATEGORY.get(module)
        assert default in PROPERTY_CATEGORIES, f"{module} has no property category"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                marks = {
                    d.attr for d in node.decorator_list
                    if isinstance(d, ast.Attribute) and d.attr in PROPERTY_CATEGORIES
                }
                assert len(marks) <= 1, f"{module}.{node.name} declares {marks}"
                counts[next(iter(marks), default)] += 1
    return counts


def test_every_category_is_populated():
    counts = _ledger()
    assert all(counts[c] > 0 for c in PROPERTY_CATEGORIES), dict(counts)


def test_the_adversarial_to_happy_ratio_holds():
    counts = _ledger()
    assert counts["adversarial"] >= REQUIRED_RATIO * counts["happy"], dict(counts)
