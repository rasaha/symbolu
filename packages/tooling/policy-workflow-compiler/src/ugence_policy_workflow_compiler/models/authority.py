"""Authority requirements, approval paths, and approval steps.

Who holds authority for an action type, the ordered approvals required, and the
segregation-of-duties constraints between them. Compiles to Decision Authority
authority checks, decision-gate sequences, and segregation-of-duties gates.
"""

from __future__ import annotations

from typing import Tuple

from pydantic import Field

from .common import AuthorityType, CapabilityId, ObjectType, PolicyObject


class AuthorityRequirement(PolicyObject):
    """Who holds authority for a decision/action type."""

    object_type: ObjectType = ObjectType.AUTHORITY_REQUIREMENT
    #: The decision/action scope this authority governs (declarative label).
    decision_scope: str = Field(..., min_length=1)
    authority_type: AuthorityType = AuthorityType.HUMAN_APPROVER
    #: A role/level label the acting authority must satisfy.
    required_role: str = ""
    #: Whether a machine/non-human actor is allowed to satisfy this requirement.
    #: For binding business decisions this must remain False.
    allow_non_human: bool = False
    owning_capability: CapabilityId = CapabilityId.DECISION_AUTHORITY


class ApprovalStep(PolicyObject):
    """A single ordered approval within an approval path."""

    object_type: ObjectType = ObjectType.APPROVAL_STEP
    #: 1-based order of this step within its path.
    order: int = Field(..., ge=1)
    #: The AuthorityRequirement object id the approver must satisfy.
    authority_requirement_id: str = Field(..., min_length=1)
    #: A stable label for the role acting at this step (for SoD comparison).
    role_label: str = ""
    optional: bool = False


class ApprovalPath(PolicyObject):
    """Ordered approvals plus segregation-of-duties constraints."""

    object_type: ObjectType = ObjectType.APPROVAL_PATH
    #: Ordered ApprovalStep object ids. Ordering is derived from each step's
    #: ``order`` field at validation time.
    step_ids: Tuple[str, ...] = ()
    #: Pairs of step ids (or role labels) that must be satisfied by distinct
    #: identities (segregation of duties). Each pair is a 2-tuple of labels.
    segregation_pairs: Tuple[Tuple[str, str], ...] = ()
    owning_capability: CapabilityId = CapabilityId.DECISION_AUTHORITY
