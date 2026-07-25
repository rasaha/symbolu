"""Explicit representation of *who may bind a decision* and within what bounds.

Authority is a first-class, validated concept — not an attribute of the actor.
Human oversight does not always mean synchronous human approval: a deterministic,
published policy may hold **explicitly delegated and bounded** authority. It is
never unrestricted AI discretion — no ``AuthorityType`` is an AI model, and the
service boundary additionally rejects any AI-authenticated principal.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import model_validator

from ..domain.base import DomainModel
from ..errors import DomainValidationError
from .status import AuthorityType
from .subject import VersionedRef


class AuthorityContext(DomainModel):
    """The authority under which a decision may be made.

    For ``DELEGATED_POLICY`` a granting policy reference and explicit bounds are
    required — a delegated policy can only act inside a stated scope.
    """

    authority_id: str
    authority_type: AuthorityType
    decision_scope: str = ""
    granting_policy_ref: Optional[VersionedRef] = None
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None
    limits: tuple[str, ...] = ()
    segregation_of_duties: bool = False
    required_approvals: int = 0
    delegation_ref: Optional[str] = None

    @model_validator(mode="after")
    def _validate(self) -> "AuthorityContext":
        if not self.authority_id.strip():
            raise DomainValidationError("authority_id is required")
        if self.required_approvals < 0:
            raise DomainValidationError("required_approvals must be >= 0")
        if (self.effective_from is not None and self.effective_until is not None
                and self.effective_until < self.effective_from):
            raise DomainValidationError("effective_until must be >= effective_from")
        if self.authority_type is AuthorityType.DELEGATED_POLICY:
            # A delegated policy must be *bounded*: it needs a granting policy and
            # an explicit scope or limits. Unbounded delegation is prohibited.
            if self.granting_policy_ref is None:
                raise DomainValidationError(
                    "DELEGATED_POLICY authority requires a granting_policy_ref")
            if not self.decision_scope.strip() and not self.limits:
                raise DomainValidationError(
                    "DELEGATED_POLICY authority requires an explicit scope or limits")
        return self
