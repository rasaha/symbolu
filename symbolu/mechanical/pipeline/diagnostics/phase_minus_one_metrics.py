"""
Phase −1 Metrics and Violation Logging

Tracks metrics and violations from Phase −1 grounding analysis for
diagnostics and observability.

Metrics Tracked:
- Mode distribution (REFLEXIVE/RELATIONAL/DETACHED counts)
- Projection risk distribution (LOW/MEDIUM/HIGH counts)
- Analysis blocked count
- Ambiguity rate
- Safe default rate
- Violation attempts by module

Design:
- In-memory counters keyed by run_id and stage
- JSON-compatible output for structured logging
- Thread-safe counters using simple dict operations
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from collections import defaultdict

from symbolu.mechanical.pipeline.grounding.phase_minus_one_schema import (
    PhaseMinusOneEnvelope,
    ObservationMode,
    ProjectionRisk,
    GroundingStatus,
    ResolutionPolicy,
    OverallPolicy,
)


@dataclass
class PhaseMinusOneMetricsSnapshot:
    """
    Snapshot of Phase −1 metrics at a point in time.

    Attributes:
        run_id: Unique run identifier.
        timestamp: Unix timestamp of snapshot.
        mode_counts: Count by observation mode.
        risk_counts: Count by projection risk level.
        status_counts: Count by grounding status.
        policy_counts: Count by resolution policy.
        overall_policy_counts: Count by overall policy.
        analysis_blocked_count: Number of times analysis was blocked.
        ambiguity_rate: Rate of ambiguous groundings.
        safe_default_rate: Rate of safe default selections.
        clause_split_rate: Rate of clause splits.
        blocked_rate: Rate of BLOCKED overall policies.
        violation_count: Total violation count.
        violation_by_module: Violations grouped by module.
    """
    run_id: str
    timestamp: float
    mode_counts: Dict[str, int]
    risk_counts: Dict[str, int]
    status_counts: Dict[str, int]
    policy_counts: Dict[str, int]
    overall_policy_counts: Dict[str, int]
    analysis_blocked_count: int
    ambiguity_rate: float
    safe_default_rate: float
    clause_split_rate: float
    blocked_rate: float
    violation_count: int
    violation_by_module: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "mode_counts": self.mode_counts,
            "risk_counts": self.risk_counts,
            "status_counts": self.status_counts,
            "policy_counts": self.policy_counts,
            "overall_policy_counts": self.overall_policy_counts,
            "analysis_blocked_count": self.analysis_blocked_count,
            "ambiguity_rate": self.ambiguity_rate,
            "safe_default_rate": self.safe_default_rate,
            "clause_split_rate": self.clause_split_rate,
            "blocked_rate": self.blocked_rate,
            "violation_count": self.violation_count,
            "violation_by_module": self.violation_by_module,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


class PhaseMinusOneMetrics:
    """
    Metrics collector for Phase −1 grounding analysis.

    Usage:
        metrics = PhaseMinusOneMetrics()
        metrics.record_envelope(envelope)
        metrics.record_violation("planner_gate", "ANALYZE", "forbidden_for_reflexive")
        snapshot = metrics.get_snapshot()
    """

    def __init__(self) -> None:
        """Initialize metrics collector."""
        self._mode_counts: Dict[str, int] = defaultdict(int)
        self._risk_counts: Dict[str, int] = defaultdict(int)
        self._status_counts: Dict[str, int] = defaultdict(int)
        self._policy_counts: Dict[str, int] = defaultdict(int)
        self._overall_policy_counts: Dict[str, int] = defaultdict(int)
        self._analysis_blocked_count: int = 0
        self._total_clauses: int = 0
        self._ambiguous_clauses: int = 0
        self._safe_default_clauses: int = 0
        self._split_envelopes: int = 0
        self._total_envelopes: int = 0
        self._blocked_envelopes: int = 0
        self._violations: List[Dict] = []
        self._violation_by_module: Dict[str, int] = defaultdict(int)
        self._run_id: str = ""

    def record_envelope(self, envelope: PhaseMinusOneEnvelope) -> None:
        """
        Record metrics from a Phase −1 envelope.

        Args:
            envelope: The envelope to record metrics from.
        """
        self._run_id = envelope.run_id
        self._total_envelopes += 1

        # Record overall policy
        self._overall_policy_counts[envelope.overall_policy.value] += 1

        if envelope.is_blocked():
            self._blocked_envelopes += 1

        if envelope.was_split:
            self._split_envelopes += 1

        # Record per-clause metrics
        for clause in envelope.clauses:
            self._total_clauses += 1

            # Status
            self._status_counts[clause.grounding_status.value] += 1

            # Policy
            self._policy_counts[clause.resolution_policy.value] += 1

            if clause.grounding_status == GroundingStatus.AMBIGUOUS:
                self._ambiguous_clauses += 1

            if clause.resolution_policy == ResolutionPolicy.SAFE_DEFAULT:
                self._safe_default_clauses += 1

            # Selected candidate metrics
            if clause.selected:
                self._mode_counts[clause.selected.mode.value] += 1
                self._risk_counts[clause.selected.projection_risk.value] += 1

                if not clause.selected.analysis_allowed:
                    self._analysis_blocked_count += 1

    def record_violation(
        self,
        module: str,
        action: str,
        reason: str,
        context: Optional[Dict] = None,
    ) -> None:
        """
        Record a constraint violation.

        Args:
            module: Module that detected/reported the violation.
            action: Action that violated the constraint.
            reason: Reason for violation.
            context: Additional context.
        """
        violation = {
            "module": module,
            "action": action,
            "reason": reason,
            "timestamp": time.time(),
            "context": context or {},
        }
        self._violations.append(violation)
        self._violation_by_module[module] += 1

    def get_snapshot(self) -> PhaseMinusOneMetricsSnapshot:
        """
        Get a snapshot of current metrics.

        Returns:
            PhaseMinusOneMetricsSnapshot with current values.
        """
        return PhaseMinusOneMetricsSnapshot(
            run_id=self._run_id,
            timestamp=time.time(),
            mode_counts=dict(self._mode_counts),
            risk_counts=dict(self._risk_counts),
            status_counts=dict(self._status_counts),
            policy_counts=dict(self._policy_counts),
            overall_policy_counts=dict(self._overall_policy_counts),
            analysis_blocked_count=self._analysis_blocked_count,
            ambiguity_rate=self._ambiguous_clauses / self._total_clauses if self._total_clauses > 0 else 0.0,
            safe_default_rate=self._safe_default_clauses / self._total_clauses if self._total_clauses > 0 else 0.0,
            clause_split_rate=self._split_envelopes / self._total_envelopes if self._total_envelopes > 0 else 0.0,
            blocked_rate=self._blocked_envelopes / self._total_envelopes if self._total_envelopes > 0 else 0.0,
            violation_count=len(self._violations),
            violation_by_module=dict(self._violation_by_module),
        )

    def get_violations(self) -> List[Dict]:
        """Get all recorded violations."""
        return self._violations.copy()

    def reset(self) -> None:
        """Reset all metrics."""
        self._mode_counts.clear()
        self._risk_counts.clear()
        self._status_counts.clear()
        self._policy_counts.clear()
        self._overall_policy_counts.clear()
        self._analysis_blocked_count = 0
        self._total_clauses = 0
        self._ambiguous_clauses = 0
        self._safe_default_clauses = 0
        self._split_envelopes = 0
        self._total_envelopes = 0
        self._blocked_envelopes = 0
        self._violations.clear()
        self._violation_by_module.clear()
        self._run_id = ""

    def emit_log(self) -> str:
        """
        Emit metrics as structured JSON log.

        Returns:
            JSON string suitable for structured logging.
        """
        snapshot = self.get_snapshot()
        log_entry = {
            "event": "phase_minus_one_metrics",
            **snapshot.to_dict(),
        }
        return json.dumps(log_entry)


# Singleton metrics instance for global access
_global_metrics: Optional[PhaseMinusOneMetrics] = None


def get_metrics() -> PhaseMinusOneMetrics:
    """Get the global metrics instance."""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = PhaseMinusOneMetrics()
    return _global_metrics


def record_envelope(envelope: PhaseMinusOneEnvelope) -> None:
    """Convenience function to record envelope metrics globally."""
    get_metrics().record_envelope(envelope)


def record_violation(
    module: str,
    action: str,
    reason: str,
    context: Optional[Dict] = None,
) -> None:
    """Convenience function to record violation globally."""
    get_metrics().record_violation(module, action, reason, context)


def get_metrics_snapshot() -> PhaseMinusOneMetricsSnapshot:
    """Convenience function to get metrics snapshot."""
    return get_metrics().get_snapshot()


def emit_metrics_log() -> str:
    """Convenience function to emit metrics log."""
    return get_metrics().emit_log()


__all__ = [
    "PhaseMinusOneMetrics",
    "PhaseMinusOneMetricsSnapshot",
    "get_metrics",
    "record_envelope",
    "record_violation",
    "get_metrics_snapshot",
    "emit_metrics_log",
]
