"""Bounded, deterministic evaluation selection + stop-condition classification.

The scheduler never scans an organization-wide repository list and never silently
governs an arbitrary pull request: it selects only from an explicitly supplied
candidate list of known Code Governance workflow revisions, respecting allowlists,
the pilot window, evaluation/batch bounds, prior evaluation, and stale-head
detection. There is no hidden background daemon and no automatic external call on
durable-store reopen.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Mapping, Optional, Tuple

from .config import PilotDeploymentConfig, PilotStopThresholds


@dataclass(frozen=True)
class EvaluationCandidate:
    """A known Code Governance workflow revision offered for pilot evaluation."""

    repository: str
    target_branch: str
    pull_request_number: int
    workflow_id: str
    workflow_revision_id: str
    head_sha: str


def select_candidates(
    candidates: List[EvaluationCandidate],
    config: PilotDeploymentConfig,
    *,
    already_evaluated: Tuple[str, ...] = (),
    remaining_evaluations: Optional[int] = None,
    batch_size: Optional[int] = None,
) -> Tuple[List[EvaluationCandidate], List[Tuple[str, str]]]:
    """Return (selected, skipped) where skipped is (revision_id, reason)."""
    selected: List[EvaluationCandidate] = []
    skipped: List[Tuple[str, str]] = []
    evaluated = set(already_evaluated)
    cap = config.maximum_evaluations if remaining_evaluations is None else remaining_evaluations
    batch = batch_size if batch_size is not None else len(candidates)
    for c in candidates:
        if len(selected) >= batch or cap <= 0:
            skipped.append((c.workflow_revision_id, "batch_or_count_bound"))
            continue
        if c.repository not in config.allowed_repositories:
            skipped.append((c.workflow_revision_id, "repository_not_allowed"))
            continue
        if c.target_branch not in config.allowed_branches:
            skipped.append((c.workflow_revision_id, "branch_not_allowed"))
            continue
        if config.allowed_pull_request_numbers and \
                c.pull_request_number not in config.allowed_pull_request_numbers:
            skipped.append((c.workflow_revision_id, "pull_request_not_allowed"))
            continue
        if c.workflow_revision_id in evaluated:
            skipped.append((c.workflow_revision_id, "already_evaluated"))
            continue
        selected.append(c)
        cap -= 1
    return selected, skipped


def repository_allowed(config: PilotDeploymentConfig, repository: str) -> bool:
    return repository in config.allowed_repositories


# --- stop conditions --------------------------------------------------------
class StopConditionKind(str, Enum):
    PAUSE_CONDITION = "PAUSE_CONDITION"
    STOP_CONDITION = "STOP_CONDITION"
    ABORT_CONDITION = "ABORT_CONDITION"


@dataclass(frozen=True)
class StopConditionHit:
    condition: str
    kind: StopConditionKind
    detail: str = ""


def evaluate_stop_conditions(
    thresholds: PilotStopThresholds,
    *,
    integrity_failures: int = 0,
    credential_leak: bool = False,
    write_boundary_violation: bool = False,
    unexpected_github_host: bool = False,
    artifact_mismatch_rate: float = 0.0,
    source_failure_rate: float = 0.0,
    unexplained_escalation_rate: float = 0.0,
    store_health_failure: bool = False,
    reviewer_safety_concern: bool = False,
    max_evaluations_reached: bool = False,
    pilot_end_reached: bool = False,
    operator_stop_request: bool = False,
) -> Tuple[StopConditionHit, ...]:
    """Classify active stop conditions. A breach never enables execution or policy change."""
    hits: List[StopConditionHit] = []
    A, S, P = (StopConditionKind.ABORT_CONDITION, StopConditionKind.STOP_CONDITION,
               StopConditionKind.PAUSE_CONDITION)
    if integrity_failures > thresholds.max_integrity_failures:
        hits.append(StopConditionHit("integrity_failure", A))
    if credential_leak and thresholds.abort_on_credential_leak:
        hits.append(StopConditionHit("credential_leak", A))
    if write_boundary_violation and thresholds.abort_on_write_boundary_violation:
        hits.append(StopConditionHit("write_boundary_violation", A))
    if unexpected_github_host:
        hits.append(StopConditionHit("unexpected_github_host", A))
    if store_health_failure:
        hits.append(StopConditionHit("durable_store_health_failure", A))
    if artifact_mismatch_rate > thresholds.max_artifact_mismatch_rate:
        hits.append(StopConditionHit("artifact_mismatch_rate", S))
    if source_failure_rate > thresholds.max_source_failure_rate:
        hits.append(StopConditionHit("source_failure_rate", S))
    if unexplained_escalation_rate > thresholds.max_unexplained_escalation_rate:
        hits.append(StopConditionHit("unexplained_escalation_rate", S))
    if max_evaluations_reached:
        hits.append(StopConditionHit("maximum_evaluations_reached", S))
    if pilot_end_reached:
        hits.append(StopConditionHit("pilot_end_time_reached", S))
    if operator_stop_request:
        hits.append(StopConditionHit("operator_stop_request", S))
    if reviewer_safety_concern:
        hits.append(StopConditionHit("reviewer_safety_concern", P))
    return tuple(hits)


__all__ = [
    "EvaluationCandidate", "select_candidates", "repository_allowed",
    "StopConditionKind", "StopConditionHit", "evaluate_stop_conditions",
]
