"""
Audit Trail
============

Compliance audit logging for Phase Quad enterprise deployments.

Provides an immutable-style event log that enterprises need for:
    - Regulatory compliance (finance, healthcare, legal)
    - Incident review and root-cause analysis
    - Model behavior audit during investigations
    - SOC2 / ISO 27001 evidence collection

Each audit entry records:
    - What happened (action type + telemetry snapshot)
    - When it happened (timestamp)
    - Why it happened (policy decision + routing rationale)
    - What the model relied on (provenance + stability signals)

Usage:
    trail = AuditTrail(max_entries=10000)
    trail.record("response_generated", telemetry.to_dict())
    trail.record("tool_blocked", {"reason": "low_coherence", ...})

    # Export for compliance
    entries = trail.export(since_ms=start_time)
    trail.export_jsonl("/path/to/audit.jsonl")
"""

from __future__ import annotations

import json
import time
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional


class AuditEntry:
    """
    A single immutable audit record.

    Fields:
        action: What happened ("response_generated", "tool_blocked", etc.)
        data: Full payload (usually ExplanationTelemetry.to_dict())
        timestamp_ms: When it happened (epoch milliseconds)
        sequence_id: Monotonic sequence number for ordering
    """
    __slots__ = ("action", "data", "timestamp_ms", "sequence_id")

    def __init__(
        self,
        action: str,
        data: Dict[str, Any],
        timestamp_ms: int,
        sequence_id: int,
    ):
        self.action = action
        self.data = data
        self.timestamp_ms = timestamp_ms
        self.sequence_id = sequence_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "data": self.data,
            "timestamp_ms": self.timestamp_ms,
            "sequence_id": self.sequence_id,
        }


class AuditTrail:
    """
    Compliance-grade audit trail for Phase Quad.

    Maintains an in-memory log of all significant model decisions,
    with optional persistent file output (JSON-lines format).

    Design:
        - Append-only semantics (no edits, no deletes)
        - Monotonic sequence IDs for ordering
        - Bounded memory via ring buffer (oldest entries evicted)
        - File output is append-only (never truncates)
    """

    # Standard action types for enterprise integration
    ACTION_RESPONSE = "response_generated"
    ACTION_TOOL_ALLOWED = "tool_execution_allowed"
    ACTION_TOOL_BLOCKED = "tool_execution_blocked"
    ACTION_ESCALATION = "escalation_triggered"
    ACTION_VERIFICATION = "verification_requested"
    ACTION_ADVERSARIAL = "adversarial_detected"
    ACTION_POLICY_OVERRIDE = "policy_override"
    ACTION_CONFIDENCE_DROP = "confidence_drop"
    ACTION_STABILITY_RED = "stability_red"

    def __init__(
        self,
        max_entries: int = 10000,
        audit_file: Optional[str] = None,
    ):
        """
        Args:
            max_entries: Ring buffer size for in-memory trail.
            audit_file: Optional path for persistent JSON-lines output.
        """
        self._entries: Deque[AuditEntry] = deque(maxlen=max_entries)
        self._audit_file = Path(audit_file) if audit_file else None
        self._sequence: int = 0

    def record(self, action: str, data: Dict[str, Any]) -> AuditEntry:
        """
        Record an audit entry.

        Args:
            action: Action type (use ACTION_* constants for standard types).
            data: Payload dict (typically ExplanationTelemetry.to_dict() or
                  a subset with relevant fields).

        Returns:
            The created AuditEntry.
        """
        self._sequence += 1
        entry = AuditEntry(
            action=action,
            data=data,
            timestamp_ms=int(time.time() * 1000),
            sequence_id=self._sequence,
        )

        self._entries.append(entry)

        # Persistent file
        if self._audit_file is not None:
            self._persist(entry)

        return entry

    def record_telemetry(self, telemetry_dict: Dict[str, Any]) -> AuditEntry:
        """
        Convenience: record a full telemetry snapshot as a response event.

        Automatically extracts policy outcome to choose the right action type.
        """
        policy = telemetry_dict.get("policy", {})
        outcome = policy.get("policy_outcome", "allowed")

        if outcome == "blocked":
            action = self.ACTION_TOOL_BLOCKED
        elif policy.get("verification_needed", False):
            action = self.ACTION_VERIFICATION
        elif policy.get("adversarial_drift_detected", False):
            action = self.ACTION_ADVERSARIAL
        else:
            action = self.ACTION_RESPONSE

        return self.record(action, telemetry_dict)

    # ------------------------------------------------------------------
    # Query API
    # ------------------------------------------------------------------

    def export(
        self,
        since_ms: Optional[int] = None,
        action_filter: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Export audit entries as dicts.

        Args:
            since_ms: Only entries after this timestamp.
            action_filter: Only entries with this action type.
            limit: Maximum entries to return.

        Returns:
            List of entry dicts, ordered by sequence_id.
        """
        results = []
        for entry in self._entries:
            if since_ms is not None and entry.timestamp_ms < since_ms:
                continue
            if action_filter is not None and entry.action != action_filter:
                continue
            results.append(entry.to_dict())
            if len(results) >= limit:
                break
        return results

    def export_jsonl(self, path: str) -> int:
        """
        Export all entries to a JSON-lines file.

        Returns the number of entries written.
        """
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with open(p, "w") as f:
            for entry in self._entries:
                f.write(json.dumps(entry.to_dict(), default=str) + "\n")
                count += 1
        return count

    def count(self, action_filter: Optional[str] = None) -> int:
        """Count entries, optionally filtered by action type."""
        if action_filter is None:
            return len(self._entries)
        return sum(1 for e in self._entries if e.action == action_filter)

    @property
    def entries(self) -> List[AuditEntry]:
        """Access the full entry list (read-only view)."""
        return list(self._entries)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _persist(self, entry: AuditEntry) -> None:
        """Append entry to persistent file."""
        try:
            self._audit_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._audit_file, "a") as f:
                f.write(json.dumps(entry.to_dict(), default=str) + "\n")
        except Exception:
            pass  # Never let I/O errors break inference
