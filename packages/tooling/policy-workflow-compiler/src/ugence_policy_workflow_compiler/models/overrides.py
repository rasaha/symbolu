"""Override rules.

Who may override a decision rule, with what justification and expiry. Compiles to
an override gate. An override without documented justification, or past its expiry
window, is rejected. Every override must name the decision rule it modifies.
"""

from __future__ import annotations

from typing import Tuple

from pydantic import Field

from .common import AuthorityType, CapabilityId, ObjectType, PolicyObject


class OverrideRule(PolicyObject):
    """Who may override a decision rule, with justification and expiry."""

    object_type: ObjectType = ObjectType.OVERRIDE_RULE
    #: The DecisionRule object id this override modifies. Required.
    decision_rule_id: str = Field(..., min_length=1)
    #: The AuthorityRequirement object id an overrider must satisfy.
    authority_requirement_id: str = ""
    #: Whether a documented justification is mandatory for a valid override.
    requires_justification: bool = True
    #: Whether the override expires (a valid override must be within its window).
    has_expiry: bool = True
    #: Maximum validity window in seconds (0 means "no window"/instantaneous).
    max_validity_seconds: int = Field(default=3600, ge=0)
    overrider_authority_type: AuthorityType = AuthorityType.HUMAN_APPROVER
    owning_capability: CapabilityId = CapabilityId.DECISION_AUTHORITY
