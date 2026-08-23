"""Validation outcomes, findings and reports. Fail-closed by construction.

Three outcomes, and the distinction between the two non-VALID ones is load-bearing:

* ``VALID`` — the artifact is well-formed and internally consistent under every
  rule this build implements. It says nothing about whether the content is *good*,
  and nothing about whether anybody had standing to write it.
* ``INVALID`` — a rule this build implements is definitely broken. The artifact is
  wrong, and re-asking a better-informed build will not change that.
* ``INDETERMINATE`` — this build cannot decide. An unrecognized schema version, an
  ambiguous mandatory field, a mandatory requirement that resolves to nothing. The
  artifact may be fine; this build cannot say so.

**Fail-closed** means only ``VALID`` is usable. ``INDETERMINATE`` is not a
softer ``VALID``: it is a refusal to answer, and a caller that treats it as
permission has defeated the point. :attr:`ValidationReport.is_usable` is the only
sanctioned way to ask, and it is true for ``VALID`` alone.

Aggregation precedence is ``INVALID`` > ``INDETERMINATE`` > ``VALID``. A definite
break is reported as a break even when something else was also undecidable,
because the definite finding is the more actionable one and both refuse use.
"""

from __future__ import annotations

from enum import Enum
from typing import Iterable, Tuple

from ..models.common import FrozenArtifact


class ValidationOutcome(str, Enum):
    """The decision a validation pass reached."""

    VALID = "VALID"
    INVALID = "INVALID"
    INDETERMINATE = "INDETERMINATE"


#: Lower is more severe. Used only by :func:`combine_outcomes`.
_PRECEDENCE = {
    ValidationOutcome.INVALID: 0,
    ValidationOutcome.INDETERMINATE: 1,
    ValidationOutcome.VALID: 2,
}


def combine_outcomes(outcomes: Iterable[ValidationOutcome]) -> ValidationOutcome:
    """Reduce outcomes under ``INVALID`` > ``INDETERMINATE`` > ``VALID``.

    An empty iterable reduces to ``VALID``: no rule was broken because no rule was
    checked. Callers that could be handed nothing to check should say so with an
    explicit finding rather than relying on this.
    """
    worst = ValidationOutcome.VALID
    for outcome in outcomes:
        if _PRECEDENCE[outcome] < _PRECEDENCE[worst]:
            worst = outcome
    return worst


class ValidationFinding(FrozenArtifact):
    """One rule result, addressed to a field path.

    This is a *validation* finding — a statement about the well-formedness of an
    artifact. It is not a conformance finding: nothing here says whether an
    implementation behaves as a constitution requires. AC-0 emits no conformance
    findings at all.
    """

    code: str
    outcome: ValidationOutcome
    path: str
    message: str

    @property
    def sort_key(self) -> Tuple[int, str, str]:
        """Deterministic ordering: severity, then code, then path."""
        return (_PRECEDENCE[self.outcome], self.code, self.path)


class ValidationReport(FrozenArtifact):
    """The result of validating one artifact. Deterministic and fully ordered."""

    artifact_kind: str
    outcome: ValidationOutcome
    findings: Tuple[ValidationFinding, ...] = ()

    @property
    def is_usable(self) -> bool:
        """True for ``VALID`` only. The fail-closed gate; do not open-code it."""
        return self.outcome is ValidationOutcome.VALID

    @property
    def codes(self) -> Tuple[str, ...]:
        """Every finding code, in report order."""
        return tuple(f.code for f in self.findings)

    def has_code(self, code: str) -> bool:
        """True when a finding with ``code`` was reported."""
        return code in self.codes

    @classmethod
    def build(
        cls, artifact_kind: str, findings: Iterable[ValidationFinding]
    ) -> "ValidationReport":
        """Assemble a report: findings sorted deterministically, outcome derived.

        The outcome is always derived from the findings, never passed in, so a
        report cannot claim ``VALID`` while carrying an ``INVALID`` finding.
        """
        ordered = tuple(sorted(findings, key=lambda f: f.sort_key))
        return cls(
            artifact_kind=artifact_kind,
            outcome=combine_outcomes(f.outcome for f in ordered),
            findings=ordered,
        )


def invalid(code: str, path: str, message: str) -> ValidationFinding:
    """A definite rule break."""
    return ValidationFinding(
        code=code, outcome=ValidationOutcome.INVALID, path=path, message=message
    )


def indeterminate(code: str, path: str, message: str) -> ValidationFinding:
    """A refusal to decide. Not a pass."""
    return ValidationFinding(
        code=code, outcome=ValidationOutcome.INDETERMINATE, path=path, message=message
    )


__all__ = [
    "ValidationOutcome",
    "ValidationFinding",
    "ValidationReport",
    "combine_outcomes",
    "invalid",
    "indeterminate",
]
