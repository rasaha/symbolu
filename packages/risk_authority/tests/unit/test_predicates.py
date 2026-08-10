"""Bounded predicate language evaluation (spec §2, §7.4)."""

from __future__ import annotations

import pytest

from risk_authority.domain import Predicate, PredicateOp


@pytest.mark.parametrize(
    "op,value,fact,expected",
    [
        (PredicateOp.EQ, "FINANCE", "FINANCE", True),
        (PredicateOp.EQ, "FINANCE", "HR", False),
        (PredicateOp.NE, "HR", "FINANCE", True),
        (PredicateOp.GT, 2, 3, True),
        (PredicateOp.GT, 3, 2, False),
        (PredicateOp.GTE, 2, 2, True),
        (PredicateOp.LT, 5, 3, True),
        (PredicateOp.LTE, 3, 3, True),
        (PredicateOp.IN, ["HIGH", "CRITICAL"], "HIGH", True),
        (PredicateOp.IN, ["HIGH"], "LOW", False),
        (PredicateOp.NOT_IN, ["HIGH"], "LOW", True),
    ],
)
def test_scalar_operators(op, value, fact, expected):
    assert Predicate("f", op, value).evaluate({"f": fact}) is expected


def test_subset_of():
    p = Predicate("data", PredicateOp.SUBSET_OF, ["A", "B", "C"])
    assert p.evaluate({"data": ["A", "B"]}) is True
    assert p.evaluate({"data": ["A", "Z"]}) is False


def test_all_of_and_any_of():
    all_of = Predicate("tools", PredicateOp.ALL_OF, ["a", "b"])
    assert all_of.evaluate({"tools": ["a", "b", "c"]}) is True
    assert all_of.evaluate({"tools": ["a"]}) is False
    any_of = Predicate("tools", PredicateOp.ANY_OF, ["x", "b"])
    assert any_of.evaluate({"tools": ["a", "b"]}) is True
    assert any_of.evaluate({"tools": ["a"]}) is False


def test_exists():
    p = Predicate("model_id", PredicateOp.EXISTS)
    assert p.evaluate({"model_id": "m"}) is True
    assert p.evaluate({"model_id": None}) is False
    assert p.evaluate({}) is False


def test_missing_fact_fails_closed_for_positive_ops():
    # An absent fact never satisfies a positive operator.
    assert Predicate("missing", PredicateOp.EQ, "x").evaluate({}) is False
    assert Predicate("missing", PredicateOp.IN, ["x"]).evaluate({}) is False
    assert Predicate("missing", PredicateOp.GT, 1).evaluate({}) is False


def test_nested_path_resolution():
    p = Predicate("subject.model_id", PredicateOp.EQ, "m")
    assert p.evaluate({"subject": {"model_id": "m"}}) is True


def test_type_mismatch_comparison_is_false():
    # A string fact compared with GT to an int must not raise; fail closed.
    assert Predicate("f", PredicateOp.GT, 5).evaluate({"f": "abc"}) is False
