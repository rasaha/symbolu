"""Versioned, immutable ActionMapping — binds a decision outcome to an action type.

A mapping is a *pre-approved governance rule*, not a decision and not code. It says
"a decision of this type with this outcome may become this action type on this kind
of target system, with these parameter bounds." Only PUBLISHED mappings may be
used; unsupported outcomes fail closed; mappings never contain executable
credentials.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, model_validator

from ..common import canonical_hash, utc_now
from ..decision_cases.status import DecisionOutcome
from ..domain.base import DomainModel
from ..errors import DomainValidationError
from .status import ActionMappingStatus

#: Substrings that must never appear as declared parameter fields (credentials etc.).
_FORBIDDEN_FIELD_MARKERS = (
    "password", "secret", "token", "credential", "api_key", "apikey",
    "private_key", "access_key",
)


class ParameterSchema(DomainModel):
    """A minimal, declarative schema for an action's requested parameters.

    Deterministic and string-typed: it names required and optional fields. It
    contains no executable logic and no credentials.
    """

    required_fields: tuple[str, ...] = ()
    optional_fields: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _validate(self) -> "ParameterSchema":
        allowed = set(self.required_fields) | set(self.optional_fields)
        for name in allowed:
            low = name.lower()
            if any(marker in low for marker in _FORBIDDEN_FIELD_MARKERS):
                raise DomainValidationError(
                    f"parameter field '{name}' looks like a credential and is prohibited")
        if set(self.required_fields) & set(self.optional_fields):
            raise DomainValidationError("a field cannot be both required and optional")
        return self

    def unknown_fields(self, provided: tuple[str, ...]) -> tuple[str, ...]:
        allowed = set(self.required_fields) | set(self.optional_fields)
        return tuple(f for f in provided if f not in allowed)

    def missing_required(self, provided: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(f for f in self.required_fields if f not in set(provided))


class ActionMapping(DomainModel):
    """An immutable, versioned mapping from a decision outcome to an action type."""

    mapping_id: str
    version: int
    domain_id: str
    decision_type: str
    decision_outcome: DecisionOutcome
    permitted_action_type: str
    target_system_type: str
    parameter_schema: ParameterSchema = ParameterSchema()
    required_context_fields: tuple[str, ...] = ()
    prohibited_fields: tuple[str, ...] = ()
    status: ActionMappingStatus = ActionMappingStatus.DRAFT
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None
    content_hash: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "ActionMapping":
        for req in ("mapping_id", "domain_id", "decision_type",
                    "permitted_action_type", "target_system_type"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"{req} is required")
        if self.version < 1:
            raise DomainValidationError("version must be >= 1")
        if (self.effective_from is not None and self.effective_until is not None
                and self.effective_until < self.effective_from):
            raise DomainValidationError("effective_until must be >= effective_from")
        overlap = set(self.prohibited_fields) & (
            set(self.parameter_schema.required_fields)
            | set(self.parameter_schema.optional_fields))
        if overlap:
            raise DomainValidationError(
                f"fields both permitted and prohibited: {sorted(overlap)}")
        return self

    def compute_hash(self) -> str:
        """Deterministic content hash over the mapping's semantic fields."""
        return canonical_hash({
            "mapping_id": self.mapping_id, "version": self.version,
            "domain_id": self.domain_id, "decision_type": self.decision_type,
            "decision_outcome": self.decision_outcome.value,
            "permitted_action_type": self.permitted_action_type,
            "target_system_type": self.target_system_type,
            "required_fields": sorted(self.parameter_schema.required_fields),
            "optional_fields": sorted(self.parameter_schema.optional_fields),
            "required_context_fields": sorted(self.required_context_fields),
            "prohibited_fields": sorted(self.prohibited_fields),
        })

    def is_effective(self, at: datetime) -> bool:
        if self.effective_from is not None and at < self.effective_from:
            return False
        if self.effective_until is not None and at > self.effective_until:
            return False
        return True
