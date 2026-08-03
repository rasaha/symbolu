"""Structured validation diagnostics.

A :class:`ValidationDiagnostic` is a typed, addressable finding with a stable
``code``, a ``severity``, the offending ``object_id``, a human message, related
object ids, provenance, and a suggested remediation. A :class:`ValidationReport`
aggregates diagnostics and reports whether compilation may proceed.

Severity is explicit and never silently reclassified: a ``WARNING`` never becomes
an ``ERROR`` and vice versa.
"""

from __future__ import annotations

from enum import Enum
from typing import Tuple

from pydantic import Field

from ..models.common import CompilerModel


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ERROR = "ERROR"
    FATAL = "FATAL"


#: Severities that block compilation.
_BLOCKING = frozenset({Severity.REVIEW_REQUIRED, Severity.ERROR, Severity.FATAL})


class ValidationDiagnostic(CompilerModel):
    """A single structured validation finding."""

    code: str = Field(..., min_length=1)
    severity: Severity
    object_id: str = ""
    message: str = Field(..., min_length=1)
    related_object_ids: Tuple[str, ...] = ()
    provenance: Tuple[str, ...] = ()
    suggested_remediation: str = ""

    @property
    def is_blocking(self) -> bool:
        return self.severity in _BLOCKING


class ValidationReport(CompilerModel):
    """The result of validating a policy pack."""

    policy_pack_id: str
    diagnostics: Tuple[ValidationDiagnostic, ...] = ()

    @property
    def blocking(self) -> Tuple[ValidationDiagnostic, ...]:
        return tuple(d for d in self.diagnostics if d.is_blocking)

    @property
    def ok(self) -> bool:
        """True when nothing blocks compilation."""
        return not self.blocking

    def by_severity(self, severity: Severity) -> Tuple[ValidationDiagnostic, ...]:
        return tuple(d for d in self.diagnostics if d.severity is severity)

    def counts(self) -> dict:
        out = {s.value: 0 for s in Severity}
        for d in self.diagnostics:
            out[d.severity.value] += 1
        return out
