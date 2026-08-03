"""Exception rules.

A named exception to a decision rule and the behavior it requires. Compiles to an
exception branch. Every exception must name the decision rule it modifies.
"""

from __future__ import annotations

from typing import Tuple

from pydantic import Field

from .common import CapabilityId, ObjectType, PolicyObject
from .rules import Predicate


class ExceptionRule(PolicyObject):
    """A named exception that modifies a decision rule under stated conditions."""

    object_type: ObjectType = ObjectType.EXCEPTION_RULE
    #: The DecisionRule object id this exception modifies. Required — an exception
    #: that references no decision rule fails validation.
    decision_rule_id: str = Field(..., min_length=1)
    #: Conditions under which the exception applies.
    conditions: Tuple[Predicate, ...] = ()
    #: The outcome the exception forces when it applies (declarative label).
    exception_outcome: str = "ESCALATE"
    owning_capability: CapabilityId = CapabilityId.DECISION_AUTHORITY
