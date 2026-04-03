"""
Governance Audit Store — Durable, append-only, tamper-evident audit persistence.

Provides a SQLite-backed repository for governance decisions and tool mediation
events with SHA-256 hash chaining and deterministic serialization.

DESIGN:
    - SQLite for structured querying; JSONL export for portability
    - Each record stores a canonical_payload (stable JSON) and entry_hash
    - Hash chain: entry_hash = SHA-256(prev_hash + canonical_payload)[:16]
    - In-memory callers are adapted, not broken: existing .audit_log lists
      become views over this persistent store

HASH CHAIN PATTERN (follows LedgerReplayVerifier):
    - Canonical JSON: sorted keys, compact separators, ensure_ascii
    - SHA-256, first 16 hex chars
    - Chain links via prev_hash field (None/"" for genesis entry)

FAIL-CLOSED:
    - Persistence failure raises GovernanceAuditError (does NOT silently drop)
    - Callers decide whether to halt or log-and-continue

OLM mapping: O11_INTEGRATION (audit consolidation), O9_WITNESSES (observation)
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


# =============================================================================
# Constants
# =============================================================================

SCHEMA_VERSION = "1.0.0"

_GENESIS_HASH = "0" * 16  # Sentinel for the first entry's prev_hash


# =============================================================================
# Exceptions
# =============================================================================


class GovernanceAuditError(Exception):
    """Raised when audit persistence fails.

    Governance-critical: callers should NOT silently swallow this.
    """


# =============================================================================
# Canonical Event Model
# =============================================================================


@dataclass(frozen=True)
class GovernanceAuditEvent:
    """Canonical audit event for governance decisions and tool mediation.

    This is the *hashed* payload.  All fields participate in the integrity
    chain.  Derived/index-only fields (entry_hash, prev_hash, seq) are
    stored alongside but are NOT part of the canonical payload.

    Attributes:
        event_id: Unique event identifier (UUID hex).
        timestamp: ISO 8601 UTC timestamp of the event.
        event_type: Discriminator — "governance_decision" | "mcp_tool_call"
                    | "safety_contract" | "forbidden_block" | "fail_closed"
                    | "escalation" | "confidence_gate".
        source_module: Originating module (e.g. "governance_service",
                       "mcp_gateway").
        actor_id: Human or agent identity that triggered the event.
        session_id: Session/request correlation ID (may be empty).
        action_type: High-level action (e.g. "authorize", "call_tool").
        tool_name: Tool being evaluated (empty if N/A).
        decision_outcome: ALLOW / DENY / DEFER / BLOCKED / ESCALATE / ERROR.
        eligible: Whether safety preconditions passed.
        risk_level: Tool risk classification.
        confidence: Overall confidence score [0, 1].
        execution_mode: FULL / CAUTIOUS / CONFIRM_REQUIRED / BLOCKED.
        escalation_level: NONE / NOTIFY / CONFIRM / HALT.
        blocked_reasons: Machine-readable reason codes.
        rationale: Human-readable decision rationale.
        request_snapshot: Serialisable snapshot of the triggering request.
        execution_result: Outcome metadata (timing, success, error).
        schema_version: Version of this schema for forward compatibility.
    """
    event_id: str
    timestamp: str
    event_type: str
    source_module: str
    actor_id: str
    session_id: str
    action_type: str
    tool_name: str
    decision_outcome: str
    eligible: bool
    risk_level: str
    confidence: float
    execution_mode: str
    escalation_level: str
    blocked_reasons: Tuple[str, ...]
    rationale: str
    request_snapshot: Dict[str, Any]
    execution_result: Dict[str, Any]
    schema_version: str = SCHEMA_VERSION


# =============================================================================
# Canonical Serialization (deterministic, stable)
# =============================================================================


def canonical_serialize(event: GovernanceAuditEvent) -> str:
    """Produce a deterministic JSON string for hashing.

    Rules (matching LedgerReplayVerifier pattern):
        - sorted keys at every level
        - compact separators (",", ":")
        - ensure_ascii=True
        - tuples serialized as sorted lists
        - enums serialized as .value strings
        - floats rounded to 6 decimal places for stability
    """
    payload = _to_canonical_dict(event)
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _to_canonical_dict(event: GovernanceAuditEvent) -> Dict[str, Any]:
    """Convert event to a canonical dict suitable for hashing."""
    return {
        "event_id": event.event_id,
        "timestamp": event.timestamp,
        "event_type": event.event_type,
        "source_module": event.source_module,
        "actor_id": event.actor_id,
        "session_id": event.session_id,
        "action_type": event.action_type,
        "tool_name": event.tool_name,
        "decision_outcome": event.decision_outcome,
        "eligible": event.eligible,
        "risk_level": event.risk_level,
        "confidence": round(event.confidence, 6),
        "execution_mode": event.execution_mode,
        "escalation_level": event.escalation_level,
        "blocked_reasons": sorted(event.blocked_reasons),
        "rationale": event.rationale,
        "request_snapshot": _deep_sort(event.request_snapshot),
        "execution_result": _deep_sort(event.execution_result),
        "schema_version": event.schema_version,
    }


def _deep_sort(obj: Any) -> Any:
    """Recursively sort dicts by key and lists of strings."""
    if isinstance(obj, dict):
        return {k: _deep_sort(v) for k, v in sorted(obj.items())}
    if isinstance(obj, (list, tuple)):
        return [_deep_sort(item) for item in obj]
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, float):
        return round(obj, 6)
    return obj


# =============================================================================
# Hash Computation
# =============================================================================


def compute_entry_hash(prev_hash: str, canonical_payload: str) -> str:
    """Compute the tamper-evident hash for a single entry.

    hash = SHA-256(prev_hash + canonical_payload)[:16]

    Matches the 16-hex-char pattern from LedgerReplayVerifier.
    """
    data = (prev_hash + canonical_payload).encode("utf-8")
    return hashlib.sha256(data).hexdigest()[:16]


# =============================================================================
# SQLite Schema
# =============================================================================

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS audit_events (
    seq             INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        TEXT    NOT NULL UNIQUE,
    timestamp       TEXT    NOT NULL,
    event_type      TEXT    NOT NULL,
    source_module   TEXT    NOT NULL,
    actor_id        TEXT    NOT NULL DEFAULT '',
    session_id      TEXT    NOT NULL DEFAULT '',
    action_type     TEXT    NOT NULL DEFAULT '',
    tool_name       TEXT    NOT NULL DEFAULT '',
    decision_outcome TEXT   NOT NULL,
    eligible        INTEGER NOT NULL,
    risk_level      TEXT    NOT NULL DEFAULT '',
    confidence      REAL    NOT NULL DEFAULT 0.0,
    execution_mode  TEXT    NOT NULL DEFAULT '',
    escalation_level TEXT   NOT NULL DEFAULT '',
    blocked_reasons TEXT    NOT NULL DEFAULT '[]',
    rationale       TEXT    NOT NULL DEFAULT '',
    request_snapshot TEXT   NOT NULL DEFAULT '{}',
    execution_result TEXT   NOT NULL DEFAULT '{}',
    schema_version  TEXT    NOT NULL,
    canonical_payload TEXT  NOT NULL,
    prev_hash       TEXT    NOT NULL,
    entry_hash      TEXT    NOT NULL
);
"""

_CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_event_type ON audit_events(event_type);
CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_decision_outcome ON audit_events(decision_outcome);
CREATE INDEX IF NOT EXISTS idx_session_id ON audit_events(session_id);
CREATE INDEX IF NOT EXISTS idx_actor_id ON audit_events(actor_id);
"""


# =============================================================================
# Governance Audit Store
# =============================================================================


class GovernanceAuditStore:
    """Durable, append-only, tamper-evident governance audit store.

    Backed by SQLite.  Thread-safe via a reentrant lock.

    Usage::

        store = GovernanceAuditStore("/var/data/governance_audit.db")
        event = GovernanceAuditEvent(...)
        store.append(event)

        # Verify integrity
        result = store.verify_chain()
        assert result.valid

        # Query
        recent = store.list_recent(limit=50)
        denials = store.list_by_event_type("governance_decision", limit=20)

        # Export
        store.export_jsonl("/tmp/audit_export.jsonl")
    """

    def __init__(self, db_path: str = "governance_audit.db") -> None:
        """Open or create the audit database.

        Args:
            db_path: Path to the SQLite database file.
                     Use ":memory:" for testing.

        Raises:
            GovernanceAuditError: If the database cannot be opened.
        """
        self._db_path = db_path
        self._lock = threading.Lock()
        try:
            self._conn = sqlite3.connect(
                db_path,
                check_same_thread=False,
                isolation_level="DEFERRED",
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(_CREATE_TABLE + _CREATE_INDEXES)
            self._conn.commit()
        except sqlite3.Error as e:
            raise GovernanceAuditError(
                f"Failed to open audit database at {db_path}: {e}"
            ) from e

        # Cache the last hash for chaining
        self._last_hash: str = self._load_last_hash()

    # -- Core Operations ---------------------------------------------------

    def append(self, event: GovernanceAuditEvent) -> str:
        """Persist an audit event with hash chaining.

        Args:
            event: The canonical governance audit event.

        Returns:
            The entry_hash of the persisted record.

        Raises:
            GovernanceAuditError: If persistence fails (fail-closed).
        """
        canonical = canonical_serialize(event)
        with self._lock:
            prev_hash = self._last_hash
            entry_hash = compute_entry_hash(prev_hash, canonical)

            try:
                self._conn.execute(
                    """INSERT INTO audit_events (
                        event_id, timestamp, event_type, source_module,
                        actor_id, session_id, action_type, tool_name,
                        decision_outcome, eligible, risk_level, confidence,
                        execution_mode, escalation_level, blocked_reasons,
                        rationale, request_snapshot, execution_result,
                        schema_version, canonical_payload, prev_hash, entry_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        event.event_id,
                        event.timestamp,
                        event.event_type,
                        event.source_module,
                        event.actor_id,
                        event.session_id,
                        event.action_type,
                        event.tool_name,
                        event.decision_outcome,
                        1 if event.eligible else 0,
                        event.risk_level,
                        event.confidence,
                        event.execution_mode,
                        event.escalation_level,
                        json.dumps(sorted(event.blocked_reasons)),
                        event.rationale,
                        json.dumps(_deep_sort(event.request_snapshot)),
                        json.dumps(_deep_sort(event.execution_result)),
                        event.schema_version,
                        canonical,
                        prev_hash,
                        entry_hash,
                    ),
                )
                self._conn.commit()
            except sqlite3.Error as e:
                raise GovernanceAuditError(
                    f"Failed to persist audit event {event.event_id}: {e}"
                ) from e

            self._last_hash = entry_hash
            return entry_hash

    def get_last_hash(self) -> str:
        """Return the hash of the most recent entry (or genesis hash)."""
        with self._lock:
            return self._last_hash

    # -- Query Operations --------------------------------------------------

    def list_recent(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return the most recent *limit* audit records, newest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM audit_events ORDER BY seq DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def list_by_event_type(
        self,
        event_type: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Return records matching *event_type*, newest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM audit_events WHERE event_type = ? ORDER BY seq DESC LIMIT ?",
                (event_type, limit),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def list_by_decision(
        self,
        decision_outcome: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Return records matching *decision_outcome*, newest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM audit_events WHERE decision_outcome = ? ORDER BY seq DESC LIMIT ?",
                (decision_outcome, limit),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def list_by_session(
        self,
        session_id: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Return records for a specific session, newest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM audit_events WHERE session_id = ? ORDER BY seq DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def count(self) -> int:
        """Return total number of audit records."""
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM audit_events"
            ).fetchone()
            return row[0] if row else 0

    # -- Integrity Verification --------------------------------------------

    def verify_chain(self) -> "ChainVerificationResult":
        """Walk all records in order and verify hash chain integrity.

        Returns:
            ChainVerificationResult with valid=True if chain is intact,
            or valid=False with details of the first break.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT seq, event_id, canonical_payload, prev_hash, entry_hash "
                "FROM audit_events ORDER BY seq ASC"
            ).fetchall()

        if not rows:
            return ChainVerificationResult(
                valid=True, total_records=0, error_at_seq=None, error_detail=""
            )

        expected_prev = _GENESIS_HASH
        for seq, event_id, canonical, stored_prev, stored_hash in rows:
            # Check prev_hash linkage
            if stored_prev != expected_prev:
                return ChainVerificationResult(
                    valid=False,
                    total_records=len(rows),
                    error_at_seq=seq,
                    error_detail=(
                        f"seq={seq} event_id={event_id}: "
                        f"prev_hash mismatch — expected {expected_prev!r}, "
                        f"stored {stored_prev!r}"
                    ),
                )
            # Recompute hash
            recomputed = compute_entry_hash(stored_prev, canonical)
            if recomputed != stored_hash:
                return ChainVerificationResult(
                    valid=False,
                    total_records=len(rows),
                    error_at_seq=seq,
                    error_detail=(
                        f"seq={seq} event_id={event_id}: "
                        f"entry_hash mismatch — recomputed {recomputed!r}, "
                        f"stored {stored_hash!r}"
                    ),
                )
            expected_prev = stored_hash

        return ChainVerificationResult(
            valid=True, total_records=len(rows), error_at_seq=None, error_detail=""
        )

    def replay_verify(self) -> "ChainVerificationResult":
        """Alias for verify_chain() — full replay verification."""
        return self.verify_chain()

    # -- Export ------------------------------------------------------------

    def export_jsonl(self, path: str) -> int:
        """Export all records to JSONL format.

        Each line is a JSON object with canonical_payload, prev_hash,
        entry_hash, seq, and all indexed fields.

        Returns:
            Number of records exported.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM audit_events ORDER BY seq ASC"
            ).fetchall()

        count = 0
        with open(path, "w", encoding="utf-8") as f:
            for row in rows:
                record = self._row_to_dict(row)
                f.write(json.dumps(record, sort_keys=True, ensure_ascii=True))
                f.write("\n")
                count += 1
        return count

    # -- Lifecycle ---------------------------------------------------------

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            self._conn.close()

    # -- Internals ---------------------------------------------------------

    def _load_last_hash(self) -> str:
        """Load the hash of the most recent entry, or genesis."""
        row = self._conn.execute(
            "SELECT entry_hash FROM audit_events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else _GENESIS_HASH

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | tuple) -> Dict[str, Any]:
        """Convert a raw SQLite row to a dict."""
        columns = [
            "seq", "event_id", "timestamp", "event_type", "source_module",
            "actor_id", "session_id", "action_type", "tool_name",
            "decision_outcome", "eligible", "risk_level", "confidence",
            "execution_mode", "escalation_level", "blocked_reasons",
            "rationale", "request_snapshot", "execution_result",
            "schema_version", "canonical_payload", "prev_hash", "entry_hash",
        ]
        d = dict(zip(columns, row))
        d["eligible"] = bool(d["eligible"])
        # Parse JSON fields back
        for json_field in ("blocked_reasons", "request_snapshot", "execution_result"):
            if isinstance(d[json_field], str):
                try:
                    d[json_field] = json.loads(d[json_field])
                except json.JSONDecodeError:
                    pass
        return d


# =============================================================================
# Verification Result
# =============================================================================


@dataclass(frozen=True)
class ChainVerificationResult:
    """Result of hash chain verification.

    Attributes:
        valid: True if the entire chain is intact.
        total_records: Number of records checked.
        error_at_seq: Sequence number where first error was found (None if valid).
        error_detail: Human-readable description of the integrity failure.
    """
    valid: bool
    total_records: int
    error_at_seq: Optional[int]
    error_detail: str


# =============================================================================
# Event Factory Helpers
# =============================================================================


def create_event_id() -> str:
    """Generate a unique event ID."""
    return uuid.uuid4().hex[:16]


def create_timestamp() -> str:
    """Generate an ISO 8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def event_from_governance_decision(
    *,
    decision_id: str,
    timestamp: str,
    actor_id: str,
    action_type: str,
    tool_name: str = "",
    decision: str,
    risk_level: str,
    eligible: bool,
    confidence: float,
    execution_mode: str,
    escalation_level: str,
    blocked_reasons: Sequence[str] = (),
    rationale: str = "",
    request_snapshot: Optional[Dict[str, Any]] = None,
    session_id: str = "",
) -> GovernanceAuditEvent:
    """Create a GovernanceAuditEvent from GovernanceService decision data.

    Maps the existing AuditEvent fields to the canonical event model.
    """
    return GovernanceAuditEvent(
        event_id=decision_id,
        timestamp=timestamp,
        event_type="governance_decision",
        source_module="governance_service",
        actor_id=actor_id,
        session_id=session_id,
        action_type=action_type,
        tool_name=tool_name or "",
        decision_outcome=decision,
        eligible=eligible,
        risk_level=risk_level,
        confidence=confidence,
        execution_mode=execution_mode,
        escalation_level=escalation_level,
        blocked_reasons=tuple(blocked_reasons),
        rationale=rationale,
        request_snapshot=request_snapshot or {},
        execution_result={},
        schema_version=SCHEMA_VERSION,
    )


def event_from_mcp_audit(
    *,
    timestamp: str,
    request_id: str,
    tool_name: str,
    parameters: Dict[str, Any],
    decision: str,
    confidence: float,
    risk_level: str,
    session_id: str = "",
    execution_time_ms: float = 0.0,
    success: bool = True,
    error: Optional[str] = None,
    human_confirmed: bool = False,
    jepa_regime: Optional[str] = None,
    jepa_recommended_action: Optional[str] = None,
    jepa_reason_codes: Optional[List[str]] = None,
    jepa_confidence_adjustment: Optional[float] = None,
    jepa_execution_mode_override: Optional[str] = None,
    jepa_escalation_override: Optional[str] = None,
    jepa_overrode: bool = False,
    domain_policy: Optional[Dict[str, Any]] = None,
    domain_overrode: bool = False,
) -> GovernanceAuditEvent:
    """Create a GovernanceAuditEvent from MCP gateway audit data.

    Maps the existing AuditEntry fields to the canonical event model.
    JEPA governance fields are persisted into request_snapshot so they
    survive into the durable audit store.
    """
    blocked = []
    if decision in ("BLOCKED", "ERROR"):
        if error:
            blocked.append(error)

    snapshot: Dict[str, Any] = _deep_sort(parameters) if parameters else {}
    # Embed JEPA governance data in the snapshot for durable persistence
    if jepa_regime is not None:
        snapshot["jepa_regime"] = jepa_regime
        snapshot["jepa_recommended_action"] = jepa_recommended_action
        snapshot["jepa_reason_codes"] = jepa_reason_codes or []
        snapshot["jepa_confidence_adjustment"] = jepa_confidence_adjustment
        snapshot["jepa_execution_mode_override"] = jepa_execution_mode_override
        snapshot["jepa_escalation_override"] = jepa_escalation_override
        snapshot["jepa_overrode"] = jepa_overrode

    # Embed domain policy data in the snapshot for durable persistence
    if domain_policy is not None:
        snapshot["domain_policy"] = domain_policy
        snapshot["domain_overrode"] = domain_overrode

    return GovernanceAuditEvent(
        event_id=request_id or create_event_id(),
        timestamp=timestamp,
        event_type="mcp_tool_call",
        source_module="mcp_gateway",
        actor_id="",
        session_id=session_id or "",
        action_type="call_tool",
        tool_name=tool_name,
        decision_outcome=decision,
        eligible=decision == "ALLOWED",
        risk_level=risk_level,
        confidence=confidence,
        execution_mode="",
        escalation_level="",
        blocked_reasons=tuple(blocked),
        rationale="",
        request_snapshot=snapshot,
        execution_result={
            "execution_time_ms": round(execution_time_ms, 3),
            "success": success,
            "error": error or "",
            "human_confirmed": human_confirmed,
        },
        schema_version=SCHEMA_VERSION,
    )


# =============================================================================
# Module-level convenience
# =============================================================================

_default_store: Optional[GovernanceAuditStore] = None
_default_lock = threading.Lock()


def get_default_store(
    db_path: str = "governance_audit.db",
) -> GovernanceAuditStore:
    """Get or create the module-level default audit store.

    Thread-safe singleton.  First call determines the path.
    """
    global _default_store
    with _default_lock:
        if _default_store is None:
            _default_store = GovernanceAuditStore(db_path)
        return _default_store


def set_default_store(store: GovernanceAuditStore) -> None:
    """Replace the module-level default audit store (for testing)."""
    global _default_store
    with _default_lock:
        _default_store = store


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Core
    "GovernanceAuditStore",
    "GovernanceAuditEvent",
    "GovernanceAuditError",
    "ChainVerificationResult",
    # Serialization / hashing
    "canonical_serialize",
    "compute_entry_hash",
    # Event factories
    "create_event_id",
    "create_timestamp",
    "event_from_governance_decision",
    "event_from_mcp_audit",
    # Module-level store
    "get_default_store",
    "set_default_store",
    # Constants
    "SCHEMA_VERSION",
]
