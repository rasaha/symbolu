"""The single predicate evaluator: every comparator, and every way one can fail.

The evaluator was extracted from a reference harness that handled eight of twelve
comparators and returned False for the rest. These tests cover all twelve, plus the
two ways a predicate becomes unevaluable — a missing fact and an operand of the
wrong shape — because those are exactly the cases a silent False used to hide.
"""

from __future__ import annotations

import pytest

from ugence_policy_workflow_compiler.evaluation import (
    UnsupportedComparator,
    evaluate_all,
    evaluate_any,
    evaluate_predicate,
)
from ugence_policy_workflow_compiler.models.rules import Comparator, Predicate


def _p(comparator, value=None, key="fact"):
    return Predicate(fact_key=key, comparator=comparator, value=value)


def _eval(comparator, fact=..., value=None):
    facts = {} if fact is ... else {"fact": fact}
    return evaluate_predicate(_p(comparator, value), facts)


# -- ordering ------------------------------------------------------------------


@pytest.mark.parametrize(
    "comparator,fact,value,expected",
    [
        (Comparator.LT, 5, 10, True),
        (Comparator.LT, 10, 10, False),
        (Comparator.LTE, 10, 10, True),
        (Comparator.LTE, 11, 10, False),
        (Comparator.GT, 11, 10, True),
        (Comparator.GT, 10, 10, False),
        (Comparator.GTE, 10, 10, True),
        (Comparator.GTE, 9, 10, False),
        # strings order too, so a policy may bound a version or a label
        (Comparator.LT, "a", "b", True),
        (Comparator.GT, "b", "a", True),
    ],
)
def test_ordering(comparator, fact, value, expected):
    assert _eval(comparator, fact, value) is expected


@pytest.mark.parametrize("comparator", [Comparator.LT, Comparator.LTE,
                                        Comparator.GT, Comparator.GTE])
def test_ordering_across_types_is_unsatisfied_not_an_error(comparator):
    # A number against a string is a policy-authoring mistake; it must not raise
    # and must not accidentally hold.
    assert _eval(comparator, "text", 10) is False
    assert _eval(comparator, 10, "text") is False


@pytest.mark.parametrize("comparator", [Comparator.LT, Comparator.LTE,
                                        Comparator.GT, Comparator.GTE])
def test_a_flag_is_never_ordered_against_a_threshold(comparator):
    # bool is an int in Python. Comparing a flag to a number would answer a
    # question the policy author did not mean to ask.
    assert _eval(comparator, True, 0) is False
    assert _eval(comparator, False, 1) is False


# -- equality and truth --------------------------------------------------------


def test_equality():
    assert _eval(Comparator.EQ, "APPROVED", "APPROVED") is True
    assert _eval(Comparator.EQ, "APPROVED", "DENIED") is False
    assert _eval(Comparator.NE, "APPROVED", "DENIED") is True
    assert _eval(Comparator.NE, "APPROVED", "APPROVED") is False


def test_truth_is_identity_not_truthiness():
    assert _eval(Comparator.IS_TRUE, True) is True
    assert _eval(Comparator.IS_TRUE, 1) is False
    assert _eval(Comparator.IS_TRUE, "yes") is False
    assert _eval(Comparator.IS_FALSE, False) is True
    assert _eval(Comparator.IS_FALSE, 0) is False
    assert _eval(Comparator.IS_FALSE, "") is False


# -- membership: silently False before the extraction --------------------------


def test_membership():
    assert _eval(Comparator.IN, "x", ["x", "y"]) is True
    assert _eval(Comparator.IN, "z", ["x", "y"]) is False
    assert _eval(Comparator.NOT_IN, "z", ["x", "y"]) is True
    assert _eval(Comparator.NOT_IN, "x", ["x", "y"]) is False


def test_membership_accepts_any_collection_shape():
    for members in (["x"], ("x",), {"x"}, frozenset({"x"})):
        assert _eval(Comparator.IN, "x", members) is True


def test_membership_against_a_non_collection_is_unsatisfied():
    # An ill-formed predicate is unsatisfied — NOT_IN must not read as vacuously
    # true just because there is nothing to be a member of.
    assert _eval(Comparator.IN, "x", "not-a-collection") is False
    assert _eval(Comparator.NOT_IN, "x", "not-a-collection") is False
    assert _eval(Comparator.NOT_IN, "x", None) is False


# -- emptiness: also silently False before the extraction ----------------------


def test_emptiness():
    assert _eval(Comparator.IS_EMPTY, "") is True
    assert _eval(Comparator.IS_EMPTY, []) is True
    assert _eval(Comparator.IS_EMPTY, {}) is True
    assert _eval(Comparator.IS_EMPTY, None) is True
    assert _eval(Comparator.IS_EMPTY, "value") is False
    assert _eval(Comparator.NON_EMPTY, "value") is True
    assert _eval(Comparator.NON_EMPTY, ["a"]) is True
    assert _eval(Comparator.NON_EMPTY, "") is False


def test_a_number_is_never_empty():
    # 0 is a value, not an absence.
    assert _eval(Comparator.IS_EMPTY, 0) is False
    assert _eval(Comparator.NON_EMPTY, 0) is True


# -- the missing fact ----------------------------------------------------------


@pytest.mark.parametrize(
    "comparator",
    [c for c in Comparator if c not in (Comparator.IS_EMPTY, Comparator.NON_EMPTY)],
)
def test_a_missing_fact_leaves_a_predicate_unsatisfied(comparator):
    assert _eval(comparator, value=10) is False


def test_absence_is_emptiness():
    # The documented exception: emptiness has an answer for an absent fact, and
    # this direction is the safe one — a policy that blocks on empty evidence
    # blocks when the evidence never arrived.
    assert _eval(Comparator.IS_EMPTY) is True
    assert _eval(Comparator.NON_EMPTY) is False


# -- every comparator is implemented -------------------------------------------


def test_every_comparator_has_an_evaluation_rule():
    # The defect this module was extracted to remove: four comparators fell
    # through to False. A future enum member must fail loudly, not quietly.
    for comparator in Comparator:
        evaluate_predicate(_p(comparator, ["x"]), {"fact": "x"})


def test_an_unknown_comparator_raises_rather_than_reading_as_unsatisfied():
    class _Rogue:
        pass

    predicate = _p(Comparator.EQ)
    object.__setattr__(predicate, "__dict__", dict(predicate.__dict__))
    predicate.__dict__["comparator"] = _Rogue()
    with pytest.raises(UnsupportedComparator):
        evaluate_predicate(predicate, {"fact": 1})


# -- combinators ---------------------------------------------------------------


def test_all_and_any():
    facts = {"a": 5, "b": "x"}
    low = Predicate(fact_key="a", comparator=Comparator.LTE, value=10)
    wrong = Predicate(fact_key="b", comparator=Comparator.EQ, value="y")
    assert evaluate_all((low,), facts) is True
    assert evaluate_all((low, wrong), facts) is False
    assert evaluate_any((low, wrong), facts) is True
    assert evaluate_any((wrong,), facts) is False
    # An empty conjunction holds; an empty disjunction does not.
    assert evaluate_all((), facts) is True
    assert evaluate_any((), facts) is False


def test_evaluation_is_deterministic():
    facts = {"fact": 5}
    predicate = _p(Comparator.LTE, 10)
    assert evaluate_predicate(predicate, facts) == evaluate_predicate(predicate, facts)


# -- the harness delegates -----------------------------------------------------


def test_the_procurement_harness_uses_this_evaluator():
    from ugence_policy_workflow_compiler.reference import procurement_equivalence

    facts = {"fact": "x"}
    predicate = _p(Comparator.IN, ["x", "y"])
    # Before the extraction this returned False for IN.
    assert procurement_equivalence._eval_predicate(predicate, facts) is True
    assert procurement_equivalence._eval_predicate(
        predicate, facts
    ) == evaluate_predicate(predicate, facts)
