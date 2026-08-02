"""Operator-level operational metrics.

These measure operator *behavior* (lifecycle, adapter calls, retries, timeouts,
integrity/preflight failures, queue size, kill-switch/stop activations, durations)
and are kept SEPARATE from clearance-quality metrics — nothing is combined into a
single score.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict

from ..fingerprints import domain_hash

DOMAIN_OPERATOR_METRICS = "cg.pilot_operator.metrics.v1"


@dataclass
class OperatorMetrics:
    """Mutable accumulator of operator-level counters (snapshot to persist)."""

    pilot_id: str
    tenant_id: str
    lifecycle_status: str = "DRAFT"
    evaluations_attempted: int = 0
    evaluations_completed: int = 0
    evaluations_skipped: int = 0
    evaluations_stale: int = 0
    adapter_calls: int = 0
    adapter_successes: int = 0
    adapter_failures: int = 0
    adapter_retries: int = 0
    rate_limit_events: int = 0
    timeouts: int = 0
    integrity_failures: int = 0
    preflight_failures: int = 0
    review_queue_size: int = 0
    feedback_completion_rate: float = 0.0
    total_collection_duration_s: float = 0.0
    total_evaluation_duration_s: float = 0.0
    last_successful_collection_at: str = ""
    last_successful_evaluation_at: str = ""
    stop_condition_activations: int = 0
    kill_switch_activations: int = 0

    @property
    def average_collection_duration_s(self) -> float:
        return round(self.total_collection_duration_s / self.evaluations_attempted, 6) \
            if self.evaluations_attempted else 0.0

    @property
    def average_evaluation_duration_s(self) -> float:
        return round(self.total_evaluation_duration_s / self.evaluations_completed, 6) \
            if self.evaluations_completed else 0.0

    def snapshot(self) -> Dict[str, Any]:
        d = asdict(self)
        d["average_collection_duration_s"] = self.average_collection_duration_s
        d["average_evaluation_duration_s"] = self.average_evaluation_duration_s
        d["execution_status"] = "DISABLED"
        d["metrics_fingerprint"] = self.metrics_fingerprint
        return d

    @property
    def metrics_fingerprint(self) -> str:
        return domain_hash(DOMAIN_OPERATOR_METRICS, {
            "pilot_id": self.pilot_id, "tenant_id": self.tenant_id,
            "lifecycle_status": self.lifecycle_status,
            "evaluations_attempted": self.evaluations_attempted,
            "evaluations_completed": self.evaluations_completed,
            "evaluations_skipped": self.evaluations_skipped,
            "evaluations_stale": self.evaluations_stale,
            "adapter_calls": self.adapter_calls, "adapter_successes": self.adapter_successes,
            "adapter_failures": self.adapter_failures, "adapter_retries": self.adapter_retries,
            "rate_limit_events": self.rate_limit_events, "timeouts": self.timeouts,
            "integrity_failures": self.integrity_failures,
            "preflight_failures": self.preflight_failures,
            "review_queue_size": self.review_queue_size,
            "stop_condition_activations": self.stop_condition_activations,
            "kill_switch_activations": self.kill_switch_activations})


__all__ = ["OperatorMetrics", "DOMAIN_OPERATOR_METRICS"]
