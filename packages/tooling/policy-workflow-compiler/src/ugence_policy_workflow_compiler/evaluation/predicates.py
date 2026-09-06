"""The single deterministic evaluator for policy predicates.

A :class:`~ugence_policy_workflow_compiler.models.rules.Predicate` is a declarative
triple — ``fact_key``, ``comparator``, ``value`` — and this module is the one place
that says what such a triple *means* against a set of facts. There is no expression
language and no code in a policy; there must equally be only one interpreter of the
policy there is.

**Why this module exists.** The interpretation lived privately inside
`reference/procurement_equivalence.py`, where it handled eight of the twelve
comparators and returned ``False`` for the other four. A policy using ``IN``,
``NOT_IN``, ``NON_EMPTY`` or ``IS_EMPTY`` therefore evaluated as *unsatisfied*
rather than raising — a silent wrong answer in a harness whose entire job is to
prove two interpretations agree. Extracting it fixes that and stops a second
interpreter from appearing when the P3C simulator needs one.

## Evaluation rules

Every rule below is total and deterministic. Nothing here reads a clock, an
environment, or anything outside the facts it is given.

* **A predicate that cannot be evaluated is not satisfied.** A missing fact, or a
  value of the wrong shape for its comparator, yields ``False`` rather than an
  exception — with the two emptiness comparators as the documented exception below.
* **Absence is emptiness.** ``IS_EMPTY`` treats a missing fact as empty and
  ``NON_EMPTY`` treats it as not non-empty. Emptiness is defined for absence in a
  way membership and ordering are not: "is this evidence missing?" has an answer
  when the fact is absent, while "is this amount below the limit?" does not.
  This direction is also the safe one — a policy that blocks on empty evidence
  blocks when the evidence never arrived.
* **Ordering requires comparable operands.** Two real numbers, or two strings.
  ``bool`` is deliberately excluded despite being an ``int`` in Python: comparing a
  flag to a threshold is a policy-authoring mistake, and answering it would hide one.
* **An unknown comparator raises.** It is not silently unsatisfied. That is the
  defect this module was extracted to remove, and it must not come back through a
  future enum member that nobody wires up here.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..models.rules import Comparator, Predicate


class UnsupportedComparator(ValueError):
    """A comparator this evaluator does not implement.

    Raised rather than returning ``False``: an unevaluable predicate that silently
    reads as unsatisfied is indistinguishable from a policy that genuinely does not
    apply, and that is exactly the confusion this evaluator was extracted to end.
    """


#: Types that may take part in an ordering comparison. ``bool`` is excluded on
#: purpose — see the module docstring.
_NUMERIC = (int, float)
_MISSING = object()


def _is_number(value: Any) -> bool:
    return isinstance(value, _NUMERIC) and not isinstance(value, bool)


def _orderable(left: Any, right: Any) -> bool:
    if _is_number(left) and _is_number(right):
        return True
    return isinstance(left, str) and isinstance(right, str)


def _is_empty(value: Any) -> bool:
    """Absence, ``None``, and any empty string or collection are all empty."""
    if value is _MISSING or value is None:
        return True
    if isinstance(value, (str, bytes, list, tuple, set, frozenset, dict)):
        return len(value) == 0
    return False


def _members(value: Any) -> Sequence[Any]:
    """The membership set of a predicate value, or ``()`` when it is not one."""
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(value)
    return ()


def evaluate_predicate(predicate: Predicate, facts: Mapping[str, Any]) -> bool:
    """Evaluate one declarative predicate against a flat fact mapping.

    Total and deterministic: identical inputs always yield the identical answer,
    and no input shape raises except an unknown comparator.
    """
    comparator = predicate.comparator
    fact = facts.get(predicate.fact_key, _MISSING)
    expected = predicate.value

    # -- emptiness: the two comparators for which absence is an answer --
    if comparator is Comparator.IS_EMPTY:
        return _is_empty(fact)
    if comparator is Comparator.NON_EMPTY:
        return not _is_empty(fact)

    # -- everything else is unsatisfied when the fact is absent --
    if fact is _MISSING:
        return False

    if comparator is Comparator.IS_TRUE:
        return fact is True
    if comparator is Comparator.IS_FALSE:
        return fact is False
    if comparator is Comparator.EQ:
        return fact == expected
    if comparator is Comparator.NE:
        return fact != expected
    if comparator in (Comparator.LT, Comparator.LTE, Comparator.GT, Comparator.GTE):
        if not _orderable(fact, expected):
            return False
        if comparator is Comparator.LT:
            return fact < expected
        if comparator is Comparator.LTE:
            return fact <= expected
        if comparator is Comparator.GT:
            return fact > expected
        return fact >= expected
    if comparator is Comparator.IN:
        return fact in _members(expected)
    if comparator is Comparator.NOT_IN:
        # Membership is undefined without a set to test against, so an ill-formed
        # predicate is unsatisfied rather than vacuously true.
        members = _members(expected)
        return bool(members) and fact not in members

    raise UnsupportedComparator(
        f"comparator {comparator!r} has no evaluation rule; a predicate that cannot "
        f"be evaluated must never read as unsatisfied"
    )


def evaluate_all(predicates, facts: Mapping[str, Any]) -> bool:
    """True when every predicate holds. An empty set of predicates holds."""
    return all(evaluate_predicate(p, facts) for p in predicates)


def evaluate_any(predicates, facts: Mapping[str, Any]) -> bool:
    """True when any predicate holds. An empty set of predicates does not hold."""
    return any(evaluate_predicate(p, facts) for p in predicates)


__all__ = [
    "evaluate_predicate",
    "evaluate_all",
    "evaluate_any",
    "UnsupportedComparator",
]
