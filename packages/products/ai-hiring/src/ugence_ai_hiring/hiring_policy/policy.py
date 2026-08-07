"""The declarative Hiring Policy — the human-authored compiler *source*.

HR declares role requirements plainly; they do **not** hand-configure dimension
weights or JSON contracts. The Hiring Policy Compiler (PWC) derives dimensions,
weights, gates, required evidence, and confidence thresholds from this source and
emits a signed ``HiringWorkflowIR`` (see :mod:`.compiler`, :mod:`.workflow_ir`).

Matches ``docs/schemas/hiring_policy_source.schema.json``.
"""

from __future__ import annotations

from typing import Optional

from pydantic import Field, model_validator

from ..domain.base import DomainModel
from ..errors import DomainValidationError
from .enums import DimensionEmphasis, HiringEvidenceClass, MandatoryGateType


class RoleRef(DomainModel):
    """Identifies the role a policy governs."""

    job_definition_id: str
    title: str
    seniority_level: str

    @model_validator(mode="after")
    def _validate(self) -> "RoleRef":
        for field in ("job_definition_id", "title", "seniority_level"):
            if not getattr(self, field).strip():
                raise DomainValidationError(f"role.{field} is required")
        return self


class ActionConstraints(DomainModel):
    """Approved bounds an offer/action must satisfy.

    Compiled verbatim into the IR/contract and enforced by the Hiring ActionGate
    (a deviation is ``DENY_REAUTH``).
    """

    salary_ceiling: float = Field(ge=0)
    salary_currency: str = "USD"
    approved_level: str
    approved_roles: tuple[str, ...] = ()
    allowed_locations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate(self) -> "ActionConstraints":
        if not self.approved_level.strip():
            raise DomainValidationError("action_constraints.approved_level is required")
        if not self.salary_currency.strip():
            raise DomainValidationError("action_constraints.salary_currency is required")
        return self


class Requirements(DomainModel):
    """What the role requires, declared plainly."""

    required_skills: tuple[str, ...] = ()
    required_domain: tuple[str, ...] = ()
    mandatory: tuple[MandatoryGateType, ...] = ()
    operating_environment: Optional[str] = None
    # Emphasis hints per dimension; the compiler normalizes these into weights.
    # A tuple of (dimension, emphasis) pairs keeps the source immutable and
    # order-stable for reproducible compilation.
    emphasis: tuple[tuple[str, DimensionEmphasis], ...] = ()

    @model_validator(mode="after")
    def _validate(self) -> "Requirements":
        seen: set[str] = set()
        for dim, _emph in self.emphasis:
            if not dim.strip():
                raise DomainValidationError("emphasis dimension name is required")
            key = dim.strip().upper()
            if key in seen:
                raise DomainValidationError(f"duplicate emphasis dimension {dim!r}")
            seen.add(key)
        return self

    def emphasis_map(self) -> dict[str, DimensionEmphasis]:
        return {dim.strip().upper(): emph for dim, emph in self.emphasis}


class HiringPolicy(DomainModel):
    """A declarative, human-authored hiring policy (compiler input)."""

    policy_id: str
    role: RoleRef
    requirements: Requirements
    action_constraints: ActionConstraints
    approval_chain: tuple[str, ...]
    review_schedule_months: tuple[int, ...] = (1, 3, 6, 12)
    authored_by: str

    @model_validator(mode="after")
    def _validate(self) -> "HiringPolicy":
        if not self.policy_id.strip():
            raise DomainValidationError("policy_id is required")
        if not self.authored_by.strip():
            raise DomainValidationError("authored_by is required")
        if not self.approval_chain:
            raise DomainValidationError("approval_chain must have at least one approver")
        for approver in self.approval_chain:
            if not approver.strip():
                raise DomainValidationError("approval_chain entries must be non-empty")
        for months in self.review_schedule_months:
            if months < 1:
                raise DomainValidationError("review_schedule_months entries must be >= 1")
        return self
