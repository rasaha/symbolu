"""Every test carries one property category; the adversarial-to-happy ratio is counted."""

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
        default = MODULE_PROPERTY_CATEGORY.get(path.stem)
        assert default in PROPERTY_CATEGORIES, f"{path.stem} has no property category"
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                marks = {d.attr for d in node.decorator_list
                         if isinstance(d, ast.Attribute) and d.attr in PROPERTY_CATEGORIES}
                assert len(marks) <= 1
                counts[next(iter(marks), default)] += 1
    return counts


def test_every_category_is_populated():
    counts = _ledger()
    assert all(counts[c] > 0 for c in PROPERTY_CATEGORIES), dict(counts)


def test_the_adversarial_to_happy_ratio_holds():
    counts = _ledger()
    assert counts["adversarial"] >= REQUIRED_RATIO * counts["happy"], dict(counts)
