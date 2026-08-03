"""Decision rules and prohibited conditions.

A :class:`DecisionRule` says *when a recommendation may become a binding decision*
and which authority owns that gate. A :class:`ProhibitedCondition` is a hard block
(fail-closed). Both are typed, declarative predicates — never executable Python.
A predicate is expressed as a small structured comparison, evaluated by the
generic verifier, so the pack carries no arbitrary code.
"""

from __future__ import annotations

from enum import Enum
from typing import Tuple

from pydantic import Field

from .common import (
    BlockBehavior,
    CapabilityId,
    CompilerModel,
    ObjectType,
    PolicyObject,
)


class Comparator(str, Enum):
    """Deterministic comparison operators for declarative predicates."""

    EQ = "EQ"
    NE = "NE"
    LT = "LT"
    LTE = "LTE"
    GT = "GT"
    GTE = "GTE"
    IN = "IN"
    NOT_IN = "NOT_IN"
    IS_TRUE = "IS_TRUE"
    IS_FALSE = "IS_FALSE"
    NON_EMPTY = "NON_EMPTY"
    IS_EMPTY = "IS_EMPTY"


class Predicate(CompilerModel):
    """A single declarative condition over a named fact.

    ``fact_key`` names a field in the scenario fact set; ``comparator`` and
    ``value`` describe the deterministic check. ``value`` is a JSON scalar or a
    list of scalars (for ``IN``/``NOT_IN``). There is no expression language and
    no code.
    """

    fact_key: str = Field(..., min_length=1)
    comparator: Comparator
    value: object = None

    def describe(self) -> str:
        return f"{self.fact_key} {self.comparator.value} {self.value!r}"


class DecisionRule(PolicyObject):
    """When a recommendation may become a binding decision.

    Compiles primarily to a Decision Authority gate. The rule is advisory input
    plus an authority reference; the *authority* still owns the binding decision.
    """

    object_type: ObjectType = ObjectType.DECISION_RULE
    #: Conditions that must all hold for the rule to admit an ADVANCE outcome.
    conditions: Tuple[Predicate, ...] = ()
    #: The AuthorityRequirement object id that owns this gate.
    authority_requirement_id: str = ""
    #: Outcome asserted when conditions hold (e.g. "ADVANCE"); declarative label.
    on_satisfied_outcome: str = "ADVANCE"
    #: Outcome asserted when conditions do not hold.
    on_unsatisfied_outcome: str = "HOLD"
    owning_capability: CapabilityId = CapabilityId.DECISION_AUTHORITY


class ProhibitedCondition(PolicyObject):
    """A condition that must hard-block (or escalate) — never proceed by default."""

    object_type: ObjectType = ObjectType.PROHIBITED_CONDITION
    #: If any predicate holds, the condition trips.
    conditions: Tuple[Predicate, ...] = ()
    behavior: BlockBehavior = BlockBehavior.BLOCK
    #: Reason code emitted when tripped (declarative label).
    reason_code: str = "PROHIBITED_CONDITION"
    owning_capability: CapabilityId = CapabilityId.DECISION_AUTHORITY
