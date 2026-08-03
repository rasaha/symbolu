"""Sequence-risk patterns and legitimate counterexamples.

A :class:`SequenceRiskPattern` is a linked-event pattern that raises collective
risk — compiled to a StoryGraph **advisory** check (never a binding decision). A
:class:`LegitimateCounterexample` is a benign case that resembles prohibited
behavior — compiled to a must-allow negative test (the false-positive guard).
"""

from __future__ import annotations

from typing import Tuple

from pydantic import Field

from .common import CapabilityId, ObjectType, PolicyObject
from .rules import Predicate


class SequenceRiskPattern(PolicyObject):
    """A linked-event pattern that raises collective risk (advisory only)."""

    object_type: ObjectType = ObjectType.SEQUENCE_RISK_PATTERN
    #: Ordered event-signature labels whose co-occurrence raises risk.
    event_signatures: Tuple[str, ...] = ()
    #: How events are linked (e.g. "BY_ACTOR", "BY_CASE"); declarative label.
    linkage: str = "BY_ACTOR"
    #: Advisory signal emitted when the pattern matches (OBSERVE/ESCALATE).
    advisory_signal: str = "ESCALATE"
    #: StoryGraph is advisory: it never owns a binding consequence.
    owning_capability: CapabilityId = CapabilityId.STORYGRAPH


class LegitimateCounterexample(PolicyObject):
    """A benign case that resembles prohibited behavior and must be allowed."""

    object_type: ObjectType = ObjectType.LEGITIMATE_COUNTEREXAMPLE
    #: The prohibited-condition or sequence-risk object id it resembles. Required.
    resembles_object_id: str = Field(..., min_length=1)
    #: Facts that make this case benign despite the resemblance.
    distinguishing_conditions: Tuple[Predicate, ...] = ()
    #: The outcome that must be allowed (declarative label).
    must_allow_outcome: str = "ADVANCE"
    owning_capability: CapabilityId = CapabilityId.COMPILER
