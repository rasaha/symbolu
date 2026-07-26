"""Deterministic assessment-readiness rules (H1).

Decides whether an application has collected the evidence its job definition
requires before it may advance to ASSESSMENT. Purely structural coverage — it does
**not** read, score, or interpret evidence content. Incomplete evidence yields an
explainable, non-ready result listing exactly which required evidence types are
missing.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..domain.base import DomainModel
from ..requisitions.job_definition import JobDefinition


class ReadinessResult(DomainModel):
    ready: bool
    missing_evidence_types: tuple[str, ...] = ()
    satisfied_evidence_types: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()


def evaluate_readiness(
    *,
    job_definition: JobDefinition,
    collected_evidence_types: Iterable[str],
) -> ReadinessResult:
    """Ready iff every required evidence type has at least one collected item."""
    required = tuple(job_definition.required_evidence_types)
    collected = set(collected_evidence_types)
    satisfied = tuple(t for t in required if t in collected)
    missing = tuple(t for t in required if t not in collected)

    reasons: list[str] = []
    if not job_definition.is_published:
        reasons.append(f"job_definition_not_published:{job_definition.status.value}")
    if missing:
        reasons.append("incomplete_evidence")

    ready = not reasons
    return ReadinessResult(
        ready=ready,
        missing_evidence_types=missing,
        satisfied_evidence_types=satisfied,
        reasons=tuple(reasons),
    )
