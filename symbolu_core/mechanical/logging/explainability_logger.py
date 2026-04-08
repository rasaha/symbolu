"""
Explainability Logger
======================

Production-grade logging for Phase Quad explainability telemetry.

Captures four explanation layers per response:
    A) Path Attribution  — Local / Phase / Quad contribution ratios
    B) Attention Provenance — Which context blocks drove the answer
    C) Stability & Drift   — Phase health, gate volatility, reversal risk
    D) Policy & Confidence  — ConfidenceGate / Sentinel decision ledger

Supports multiple output backends:
    - In-memory ring buffer (for real-time dashboards / tests)
    - Structured dict emission (for external logging pipelines)
    - JSON file append (for local audit logs)

Usage:
    logger = ExplainabilityLogger(max_entries=1000)
    logger.log_telemetry(telemetry)
    logger.log("custom_event", {"key": "value"})

    # Query recent telemetry
    recent = logger.recent(n=10)
    stats = logger.aggregate_stats()
"""

from __future__ import annotations

import json
import time
from collections import deque
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional

from symbolu_core.mechanical.logging.telemetry_schema import (
    ExplanationTelemetry,
    StabilityBadge,
    ConfidenceBand,
    PolicyOutcome,
)


class ExplainabilityLogger:
    """
    Production explainability logger for Phase Quad.

    Maintains an in-memory ring buffer of telemetry records and optionally
    forwards to external sinks (file, callback, structured logging).

    Thread safety: NOT thread-safe. For concurrent use, wrap with a lock
    or use one logger per thread.
    """

    def __init__(
        self,
        max_entries: int = 1000,
        log_file: Optional[str] = None,
        sink: Optional[Callable[[Dict[str, Any]], None]] = None,
        emit_summaries: bool = True,
    ):
        """
        Args:
            max_entries: Ring buffer size. Oldest entries evicted when full.
            log_file: Optional path to JSON-lines file for persistent logging.
            sink: Optional callback that receives each telemetry dict.
                  Use this to integrate with external logging (e.g. structlog,
                  OpenTelemetry, Datadog).
            emit_summaries: If True, store one-line summaries alongside records.
        """
        self._buffer: Deque[Dict[str, Any]] = deque(maxlen=max_entries)
        self._event_log: Deque[Dict[str, Any]] = deque(maxlen=max_entries)
        self._log_file = Path(log_file) if log_file else None
        self._sink = sink
        self._emit_summaries = emit_summaries
        self._total_logged: int = 0
        self._total_events: int = 0

        # Aggregation counters
        self._stability_counts = {b: 0 for b in StabilityBadge}
        self._confidence_counts = {b: 0 for b in ConfidenceBand}
        self._outcome_counts = {o: 0 for o in PolicyOutcome}
        self._escalation_count: int = 0
        self._adversarial_count: int = 0

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def log_telemetry(self, telemetry: ExplanationTelemetry) -> None:
        """
        Log a complete ExplanationTelemetry record.

        This is the primary entry point — called after each forward pass
        or response generation.
        """
        record = telemetry.to_dict()

        # Add summary if enabled
        if self._emit_summaries:
            record["_summary"] = telemetry.summary()

        # Buffer
        self._buffer.append(record)
        self._total_logged += 1

        # Update aggregation counters
        self._update_counters(telemetry)

        # External sink
        if self._sink is not None:
            try:
                self._sink(record)
            except Exception:
                pass  # Never let sink errors break inference

        # File output
        if self._log_file is not None:
            self._append_to_file(record)

    def log(self, step: str, data: Dict[str, Any]) -> None:
        """
        Log a custom event (non-telemetry).

        Use for intermediate steps, debugging, or custom annotations.

        Args:
            step: Event name / stage identifier.
            data: Arbitrary key-value payload.
        """
        event = {
            "step": step,
            "timestamp_ms": int(time.time() * 1000),
            "data": data,
        }
        self._event_log.append(event)
        self._total_events += 1

        if self._sink is not None:
            try:
                self._sink(event)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def recent(self, n: int = 10) -> List[Dict[str, Any]]:
        """Return the N most recent telemetry records."""
        entries = list(self._buffer)
        return entries[-n:]

    def recent_events(self, n: int = 10) -> List[Dict[str, Any]]:
        """Return the N most recent custom events."""
        entries = list(self._event_log)
        return entries[-n:]

    def aggregate_stats(self) -> Dict[str, Any]:
        """
        Aggregate statistics across all logged telemetry.

        Returns a dict suitable for dashboards / monitoring:
            - stability badge distribution
            - confidence band distribution
            - policy outcome distribution
            - escalation rate
            - adversarial detection rate
        """
        total = max(self._total_logged, 1)  # Avoid division by zero

        return {
            "total_logged": self._total_logged,
            "total_events": self._total_events,
            "stability_distribution": {
                b.value: round(self._stability_counts[b] / total, 4)
                for b in StabilityBadge
            },
            "confidence_distribution": {
                b.value: round(self._confidence_counts[b] / total, 4)
                for b in ConfidenceBand
            },
            "outcome_distribution": {
                o.value: round(self._outcome_counts[o] / total, 4)
                for o in PolicyOutcome
            },
            "escalation_rate": round(self._escalation_count / total, 4),
            "adversarial_rate": round(self._adversarial_count / total, 4),
        }

    def clear(self) -> None:
        """Clear all buffers and reset counters."""
        self._buffer.clear()
        self._event_log.clear()
        self._total_logged = 0
        self._total_events = 0
        self._stability_counts = {b: 0 for b in StabilityBadge}
        self._confidence_counts = {b: 0 for b in ConfidenceBand}
        self._outcome_counts = {o: 0 for o in PolicyOutcome}
        self._escalation_count = 0
        self._adversarial_count = 0

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _update_counters(self, t: ExplanationTelemetry) -> None:
        """Update running aggregation counters."""
        self._stability_counts[t.stability.stability_badge] += 1
        self._confidence_counts[t.policy.confidence_band] += 1
        self._outcome_counts[t.policy.policy_outcome] += 1

        if t.policy.verification_needed:
            self._escalation_count += 1
        if t.policy.adversarial_drift_detected:
            self._adversarial_count += 1

    def _append_to_file(self, record: Dict[str, Any]) -> None:
        """Append a JSON-lines record to the log file."""
        try:
            self._log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._log_file, "a") as f:
                f.write(json.dumps(record, default=str) + "\n")
        except Exception:
            pass  # Never let I/O errors break inference
