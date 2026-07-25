"""Typed validation results for external execution.

Every validator returns a typed result (blockers + warnings + retry classification),
never a bare boolean. Validation is structural and deterministic and never infers a
missing external outcome — a missing observation stays indeterminate, and expiry or
mismatch blocks execution (fail closed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .status import RetryClassification


@dataclass(frozen=True)
class ExecutionValidationIssue:
    code: str
    message: str
    blocking: bool = True
    field: str = ""


@dataclass(frozen=True)
class ExecutionValidationResult:
    valid: bool
    blockers: tuple[ExecutionValidationIssue, ...] = field(default_factory=tuple)
    warnings: tuple[ExecutionValidationIssue, ...] = field(default_factory=tuple)
    retry_classification: Optional[RetryClassification] = None
    validated_at: Optional[datetime] = None

    @property
    def blocker_codes(self) -> tuple[str, ...]:
        return tuple(i.code for i in self.blockers)
