"""Typed validation results for governed action requests.

Every validator returns a typed result, never a bare boolean. Validation is
structural and deterministic; it never infers missing values — missing required
context blocks readiness (fail closed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class ActionRequestValidationIssue:
    code: str
    message: str
    blocking: bool = True
    field: str = ""


@dataclass(frozen=True)
class ActionRequestValidationResult:
    valid: bool
    blockers: tuple[ActionRequestValidationIssue, ...] = field(default_factory=tuple)
    warnings: tuple[ActionRequestValidationIssue, ...] = field(default_factory=tuple)
    validated_at: Optional[datetime] = None

    @property
    def blocker_codes(self) -> tuple[str, ...]:
        return tuple(i.code for i in self.blockers)
