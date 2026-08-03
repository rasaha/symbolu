"""Action constraints.

Bounds on the exact action (numeric range, digest, once-only). Compiles to
ActionGate exact-action authorization. Every action constraint referencing an
authority must resolve to an :class:`AuthorityRequirement`.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Tuple

from pydantic import Field

from .common import CapabilityId, ObjectType, PolicyObject


class ConstraintKind(str, Enum):
    NUMERIC_RANGE = "NUMERIC_RANGE"
    HARD_LIMIT = "HARD_LIMIT"
    EXACT_MATCH = "EXACT_MATCH"
    MEMBER_OF = "MEMBER_OF"
    NOT_MEMBER_OF = "NOT_MEMBER_OF"
    ONCE_ONLY = "ONCE_ONLY"
    DIGEST = "DIGEST"


class ActionConstraint(PolicyObject):
    """A bound on an exact action parameter, authorized by ActionGate."""

    object_type: ObjectType = ObjectType.ACTION_CONSTRAINT
    #: The action type this constrains (declarative label, e.g. "CREATE_PURCHASE_ORDER").
    action_type: str = Field(..., min_length=1)
    #: The action parameter/field the constraint bounds (e.g. "amount", "supplier_id").
    parameter: str = Field(..., min_length=1)
    kind: ConstraintKind
    #: Inclusive numeric bounds for NUMERIC_RANGE / HARD_LIMIT.
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    #: Allowed/forbidden members for MEMBER_OF / NOT_MEMBER_OF; the exact match
    #: value for EXACT_MATCH is the single-element tuple.
    members: Tuple[str, ...] = ()
    #: The AuthorityRequirement object id that must authorize the action. Required
    #: for referential completeness: a constraint without applicable authority
    #: fails validation.
    authority_requirement_id: str = ""
    #: Reason code emitted on violation (declarative label).
    violation_reason_code: str = "DENIED"
    #: Whether a commit-time operational clearance check (Action Clearance) is
    #: required after authorization. Only emits an ACTION_CLEARANCE node when True,
    #: so a pack that does not govern commit-time safety stays clearance-free.
    requires_clearance: bool = False
    owning_capability: CapabilityId = CapabilityId.ACTION_GATE
