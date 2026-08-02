"""Immutable shadow-pilot configuration + acceptance thresholds.

A pilot is **allowlist-based**: a repository, branch, adapter, or workflow mode not
explicitly allowed is never evaluated by the pilot runner. Acceptance thresholds
are configuration, not universal truth — meeting them does **not** enable
execution.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple


class PilotStatus(str, Enum):
    """Whether a pilot meets its *configured* thresholds. Not an enforcement gate."""

    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    MEETS_CONFIGURED_THRESHOLDS = "MEETS_CONFIGURED_THRESHOLDS"
    DOES_NOT_MEET_CONFIGURED_THRESHOLDS = "DOES_NOT_MEET_CONFIGURED_THRESHOLDS"
    INTEGRITY_FAILURE = "INTEGRITY_FAILURE"


class RetentionCategory(str, Enum):
    """Documented retention category for pilot data (no destructive engine in 1D)."""

    SHORT_PILOT = "SHORT_PILOT"
    STANDARD_AUDIT = "STANDARD_AUDIT"
    REFERENCE_ONLY = "REFERENCE_ONLY"


@dataclass(frozen=True)
class PilotThresholds:
    """Configured acceptance thresholds (advisory)."""

    minimum_evaluations: int = 1
    minimum_feedback_coverage: float = 0.0
    maximum_source_failure_rate: float = 1.0
    maximum_stale_signal_rate: float = 1.0
    maximum_unexplained_escalation_rate: float = 1.0
    maximum_unresolved_integrity_failures: int = 0
    minimum_reconstruction_complete_rate: float = 0.0


@dataclass(frozen=True)
class ShadowPilotConfig:
    """An immutable, allowlist-based shadow-pilot configuration."""

    pilot_id: str
    pilot_version: str
    tenant_id: str
    allowed_repositories: Tuple[str, ...]
    allowed_branches: Tuple[str, ...] = ()
    allowed_workflow_modes: Tuple[str, ...] = ("SHADOW",)
    allowed_adapter_ids: Tuple[str, ...] = ()
    required_signal_types: Tuple[str, ...] = ()
    evaluation_profile_ref: str = ""
    intervention_routing_ref: str = ""
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    maximum_evaluations: int = 1000
    retention_category: RetentionCategory = RetentionCategory.SHORT_PILOT
    reviewer_feedback_enabled: bool = True
    reviewer_role_required: bool = False
    reporting_interval_s: int = 86400
    thresholds: PilotThresholds = field(default_factory=PilotThresholds)
    policy_refs: Tuple[str, ...] = ()

    def repository_allowed(self, repository: str) -> bool:
        return repository in self.allowed_repositories

    def branch_allowed(self, branch: str) -> bool:
        return not self.allowed_branches or branch in self.allowed_branches

    def adapter_allowed(self, adapter_id: str) -> bool:
        return not self.allowed_adapter_ids or adapter_id in self.allowed_adapter_ids


__all__ = ["PilotStatus", "RetentionCategory", "PilotThresholds", "ShadowPilotConfig"]
