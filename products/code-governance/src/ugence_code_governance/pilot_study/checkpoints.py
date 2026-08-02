"""Pilot checkpoint records + early-stop classification.

A checkpoint summarizes pilot state and recommends continue / pause / stop. A
checkpoint decision never enables enforcement. Critical safety failures recommend
STOP; collection must not continue merely to reach a target sample after a critical
failure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

from ..fingerprints import domain_hash
from .vocab import CheckpointKind, CheckpointRecommendation

DOMAIN_CHECKPOINT = "cg.pilot_study.checkpoint.v1"

#: Conditions that force an abort/stop (critical safety failures).
_CRITICAL = ("credential_leak", "github_mutation_detected", "execution_enabled",
             "store_integrity_failure", "manifest_fingerprint_mismatch",
             "unapproved_host", "unapproved_endpoint", "cross_tenant_exposure")


@dataclass(frozen=True)
class PilotCheckpointRecord:
    """An immutable pilot checkpoint. Never enables enforcement."""

    pilot_id: str
    tenant_id: str
    kind: CheckpointKind
    lifecycle_state: str
    evaluations_completed: int
    feedback_coverage: float
    source_failure_rate: float
    disagreement_categories: Tuple[str, ...]
    unresolved_adverse_cases: int
    security_status: str
    integrity_status: str
    recommendation: CheckpointRecommendation
    created_at: str
    execution_status: str = "DISABLED"

    @property
    def checkpoint_fingerprint(self) -> str:
        return domain_hash(DOMAIN_CHECKPOINT, {
            "pilot_id": self.pilot_id, "tenant_id": self.tenant_id, "kind": self.kind.value,
            "lifecycle_state": self.lifecycle_state,
            "evaluations_completed": self.evaluations_completed,
            "feedback_coverage": self.feedback_coverage,
            "source_failure_rate": self.source_failure_rate,
            "disagreement_categories": sorted(self.disagreement_categories),
            "unresolved_adverse_cases": self.unresolved_adverse_cases,
            "security_status": self.security_status, "integrity_status": self.integrity_status,
            "recommendation": self.recommendation.value, "execution_status": self.execution_status})

    @property
    def record_id(self) -> str:
        return f"pilot-checkpoint:{self.pilot_id}:{self.kind.value}:{self.checkpoint_fingerprint[:12]}"


def create_pilot_checkpoint(
    *, pilot_id: str, tenant_id: str, kind: CheckpointKind, lifecycle_state: str,
    evaluations_completed: int, feedback_coverage: float, source_failure_rate: float,
    disagreement_categories: Tuple[str, ...], unresolved_adverse_cases: int,
    security_status: str, integrity_status: str, created_at: str,
    critical_conditions: Tuple[str, ...] = (), max_source_failure_rate: float = 0.5,
) -> PilotCheckpointRecord:
    """Create a checkpoint and classify its continue/pause/stop recommendation."""
    if any(c in _CRITICAL for c in critical_conditions) or security_status != "OK" \
            or integrity_status != "OK":
        rec = CheckpointRecommendation.STOP
    elif source_failure_rate > max_source_failure_rate or unresolved_adverse_cases > 0:
        rec = CheckpointRecommendation.PAUSE
    else:
        rec = CheckpointRecommendation.CONTINUE
    return PilotCheckpointRecord(
        pilot_id=pilot_id, tenant_id=tenant_id, kind=kind, lifecycle_state=lifecycle_state,
        evaluations_completed=evaluations_completed, feedback_coverage=feedback_coverage,
        source_failure_rate=source_failure_rate, disagreement_categories=disagreement_categories,
        unresolved_adverse_cases=unresolved_adverse_cases, security_status=security_status,
        integrity_status=integrity_status, recommendation=rec, created_at=created_at)


__all__ = ["PilotCheckpointRecord", "create_pilot_checkpoint"]
