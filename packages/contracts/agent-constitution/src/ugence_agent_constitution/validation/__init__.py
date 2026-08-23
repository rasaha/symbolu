"""Deterministic, fail-closed validation of agent-constitution artifacts.

One entry point, :func:`validate_artifact`, running the schema layer and then —
only if the payload actually constructed — the semantic layer. The result is a
:class:`~.outcomes.ValidationReport` whose outcome is derived from its findings,
never asserted independently of them.

Determinism is a property of the whole surface: no clock, no environment, no
filesystem, no randomness, no iteration over unordered sets without sorting. The
same payload yields the same report, finding for finding, in the same order, in
every process.
"""

from __future__ import annotations

from typing import Any, List

from ..models.common import ArtifactKind
from ..models.constitution import AgentConstitution
from . import codes
from .outcomes import (
    ValidationFinding,
    ValidationOutcome,
    ValidationReport,
    combine_outcomes,
    indeterminate,
    invalid,
)
from .schema_validation import MODEL_FOR_KIND, validate_schema
from .semantic_validation import SEMANTIC_RULES


def validate_artifact(payload: Any, kind: ArtifactKind) -> ValidationReport:
    """Validate a payload as ``kind`` and return a deterministic report.

    ``payload`` may be a mapping or an already-constructed artifact; an artifact is
    canonicalized and re-parsed so that both routes take exactly the same path and
    cannot diverge.

    This never raises for bad data. A malformed payload is a result, not an
    exception, so callers can collect and compare outcomes uniformly.
    """
    kind = ArtifactKind(kind)
    if isinstance(payload, MODEL_FOR_KIND[kind]):
        payload = payload.model_dump(mode="python")
    elif hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="python")

    artifact, findings = validate_schema(payload, kind)
    if artifact is not None:
        findings = list(findings) + list(SEMANTIC_RULES[kind](artifact))
    return ValidationReport.build(kind.value, findings)


def validate_constitution(payload: Any) -> ValidationReport:
    """Validate a payload as a ratified constitution.

    Handed a draft, this reports :data:`~.codes.DRAFT_IS_NOT_A_CONSTITUTION` and
    refuses. That is the point of having the two as separate types.
    """
    return validate_artifact(payload, ArtifactKind.AGENT_CONSTITUTION)


def is_ratified_constitution(candidate: Any) -> bool:
    """True only for an :class:`~..models.constitution.AgentConstitution` that validates.

    Deliberately narrow, and deliberately not duck-typed. A draft carrying every
    field a constitution carries is still not a constitution: ratification is an act
    recorded by producing a different artifact, not a shape a draft can grow into.
    This function is the sanctioned way to ask, so that no caller open-codes a
    ``hasattr``-style check that a manifest would pass.
    """
    if not isinstance(candidate, AgentConstitution):
        return False
    return validate_artifact(candidate, ArtifactKind.AGENT_CONSTITUTION).is_usable


__all__ = [
    "codes",
    "ValidationOutcome",
    "ValidationFinding",
    "ValidationReport",
    "combine_outcomes",
    "invalid",
    "indeterminate",
    "validate_schema",
    "validate_artifact",
    "validate_constitution",
    "is_ratified_constitution",
    "SEMANTIC_RULES",
    "MODEL_FOR_KIND",
]
