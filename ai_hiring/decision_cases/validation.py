"""Typed validation results for the DecisionCase aggregate.

Every validator returns a *typed result* (issues with codes), never a bare
boolean. Validation is structural and deterministic — it checks references,
versions, authority, required reviews, and lifecycle shape. It never reinterprets
assessment content or judges candidate quality.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class CaseValidationIssue:
    code: str
    message: str
    blocking: bool = True
    field: str = ""
    ref_id: str = ""


@dataclass(frozen=True)
class CaseValidationResult:
    """Structural validity of a proposed case operation."""

    valid: bool
    errors: tuple[CaseValidationIssue, ...] = field(default_factory=tuple)
    warnings: tuple[CaseValidationIssue, ...] = field(default_factory=tuple)
    blocking_conditions: tuple[str, ...] = field(default_factory=tuple)
    referenced_versions: tuple[str, ...] = field(default_factory=tuple)

    @property
    def error_codes(self) -> tuple[str, ...]:
        return tuple(i.code for i in self.errors)


@dataclass(frozen=True)
class DecisionReadinessResult:
    """Whether a case is structurally ready for a decision to be recorded.

    ``ready`` is *structural readiness only* — it never means the candidate is
    good or that a particular outcome is correct.
    """

    ready: bool
    blockers: tuple[CaseValidationIssue, ...] = field(default_factory=tuple)
    warnings: tuple[CaseValidationIssue, ...] = field(default_factory=tuple)
    required_reviews_outstanding: tuple[str, ...] = field(default_factory=tuple)

    @property
    def blocker_codes(self) -> tuple[str, ...]:
        return tuple(i.code for i in self.blockers)
