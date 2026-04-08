"""
Approval Workflow Layer — Persistent approval objects for governance decisions.

When governance determines an action requires human approval (DEFER +
requires_human_approval), this layer creates a durable ApprovalRequest
with auditable state transitions.

ARCHITECTURAL POSITION:
    GovernanceService.authorize()
        ↓ decision == DEFER + requires_human_approval
    ApprovalStore.create_request()
        ↓ returns approval_id
    AuthorizationResponse carries approval_id
        ↓ approver calls approve() / deny()
    ApprovalStore records transition + audit event

STATE MACHINE:
    PENDING → APPROVED
    PENDING → DENIED
    PENDING → EXPIRED
    PENDING → CANCELED
    PENDING → SUPERSEDED
    (all other transitions are invalid)

FAIL-CLOSED:
    - If ApprovalStore.create_request() fails, the action MUST be denied
    - Invalid transitions raise ApprovalTransitionError
    - Expired approvals cannot be approved

NON-MUTATION:
    - Approval creation does NOT execute the action
    - Only after explicit approve() can the action proceed (future resume layer)

PERSISTENCE:
    SQLite-backed, thread-safe, following GovernanceAuditStore pattern.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

_logger = logging.getLogger(__name__)


# =========================================================================
# Constants
# =========================================================================

SCHEMA_VERSION = "1.0.0"
DEFAULT_EXPIRY_HOURS = 24


# =========================================================================
# Exceptions
# =========================================================================


class ApprovalStoreError(Exception):
    """Raised when approval persistence fails. Fail-closed."""


class ApprovalTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""


class ApprovalNotFoundError(Exception):
    """Raised when an approval request is not found."""


# =========================================================================
# Approval Status
# =========================================================================


class ApprovalStatus(Enum):
    """Lifecycle status of an approval request."""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    CANCELED = "canceled"
    SUPERSEDED = "superseded"


# Terminal states — no further transitions allowed
_TERMINAL_STATES = frozenset({
    ApprovalStatus.APPROVED,
    ApprovalStatus.DENIED,
    ApprovalStatus.EXPIRED,
    ApprovalStatus.CANCELED,
    ApprovalStatus.SUPERSEDED,
})

# Valid transitions from PENDING only
_VALID_TRANSITIONS = {
    ApprovalStatus.PENDING: frozenset({
        ApprovalStatus.APPROVED,
        ApprovalStatus.DENIED,
        ApprovalStatus.EXPIRED,
        ApprovalStatus.CANCELED,
        ApprovalStatus.SUPERSEDED,
    }),
}


class ApprovalLevel(Enum):
    """Required approval level (maps to escalation severity)."""
    CONFIRM = "confirm"
    HALT = "halt"
    ESCALATE = "escalate"


# =========================================================================
# Approval Models
# =========================================================================


@dataclass(frozen=True)
class ApprovalContext:
    """Context from the governance decision that triggered approval.

    Carries enough information to understand what is being approved
    without requiring the caller to re-read the original governance event.
    """
    governance_decision_id: str
    action_type: str
    tool_name: str
    actor_id: str
    risk_level: str
    confidence_score: float
    escalation_level: str
    execution_mode: str
    reason_codes: Tuple[str, ...] = ()
    policy_id: Optional[str] = None
    policy_version: Optional[str] = None
    domain_id: Optional[str] = None
    tenant_id: Optional[str] = None
    session_id: Optional[str] = None

    # Phase 3: Session enrichment context for approval reviewers
    session_identity_type: Optional[str] = None
    session_identity_unstable: Optional[bool] = None
    session_motivation_type: Optional[str] = None
    session_motivation_risk: Optional[bool] = None
    session_temporal_state: Optional[str] = None
    session_temporal_tense: Optional[bool] = None
    session_confidence_adjustment: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "governance_decision_id": self.governance_decision_id,
            "action_type": self.action_type,
            "tool_name": self.tool_name,
            "actor_id": self.actor_id,
            "risk_level": self.risk_level,
            "confidence_score": self.confidence_score,
            "escalation_level": self.escalation_level,
            "execution_mode": self.execution_mode,
            "reason_codes": list(self.reason_codes),
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "domain_id": self.domain_id,
            "tenant_id": self.tenant_id,
            "session_id": self.session_id,
            "session_identity_type": self.session_identity_type,
            "session_identity_unstable": self.session_identity_unstable,
            "session_motivation_type": self.session_motivation_type,
            "session_motivation_risk": self.session_motivation_risk,
            "session_temporal_state": self.session_temporal_state,
            "session_temporal_tense": self.session_temporal_tense,
            "session_confidence_adjustment": self.session_confidence_adjustment,
        }


@dataclass(frozen=True)
class ApprovalDecision:
    """Record of who decided and why."""
    decided_by: str
    decided_at: str
    decision: ApprovalStatus
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decided_by": self.decided_by,
            "decided_at": self.decided_at,
            "decision": self.decision.value,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class ApprovalRequest:
    """A persistent approval request created by governance.

    Immutable snapshot — state changes produce new ApprovalRequest instances
    via the store (read-after-write).
    """
    approval_id: str
    created_at: str
    expires_at: str
    status: ApprovalStatus
    approval_level: ApprovalLevel
    context: ApprovalContext
    decision: Optional[ApprovalDecision] = None
    schema_version: str = SCHEMA_VERSION

    @property
    def is_terminal(self) -> bool:
        return self.status in _TERMINAL_STATES

    @property
    def is_expired(self) -> bool:
        if self.status == ApprovalStatus.EXPIRED:
            return True
        if self.status != ApprovalStatus.PENDING:
            return False
        try:
            expiry = datetime.fromisoformat(self.expires_at)
            now = datetime.now(timezone.utc)
            return now >= expiry
        except (ValueError, TypeError):
            return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "status": self.status.value,
            "approval_level": self.approval_level.value,
            "context": self.context.to_dict(),
            "decision": self.decision.to_dict() if self.decision else None,
            "schema_version": self.schema_version,
        }

    def to_summary_dict(self) -> Dict[str, Any]:
        """Compact summary for embedding in governance responses."""
        return {
            "approval_id": self.approval_id,
            "status": self.status.value,
            "approval_level": self.approval_level.value,
            "expires_at": self.expires_at,
            "action_type": self.context.action_type,
            "tool_name": self.context.tool_name,
            "risk_level": self.context.risk_level,
        }


# =========================================================================
# Approval ID generation
# =========================================================================


def _generate_approval_id() -> str:
    """Generate a unique approval ID."""
    return f"apr-{uuid.uuid4().hex[:16]}"


# =========================================================================
# SQLite Schema
# =========================================================================


_CREATE_APPROVAL_TABLE = """
CREATE TABLE IF NOT EXISTS approval_requests (
    approval_id      TEXT    PRIMARY KEY,
    created_at       TEXT    NOT NULL,
    expires_at       TEXT    NOT NULL,
    status           TEXT    NOT NULL DEFAULT 'pending',
    approval_level   TEXT    NOT NULL DEFAULT 'confirm',
    context_json     TEXT    NOT NULL DEFAULT '{}',
    decision_json    TEXT    DEFAULT NULL,
    schema_version   TEXT    NOT NULL DEFAULT '1.0.0',
    updated_at       TEXT    NOT NULL
);
"""

_CREATE_APPROVAL_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_approval_status
    ON approval_requests(status);
CREATE INDEX IF NOT EXISTS idx_approval_expires
    ON approval_requests(expires_at);
CREATE INDEX IF NOT EXISTS idx_approval_created
    ON approval_requests(created_at);
"""

_CREATE_APPROVAL_HISTORY = """
CREATE TABLE IF NOT EXISTS approval_history (
    seq              INTEGER PRIMARY KEY AUTOINCREMENT,
    approval_id      TEXT    NOT NULL,
    timestamp        TEXT    NOT NULL,
    from_status      TEXT    NOT NULL,
    to_status        TEXT    NOT NULL,
    actor            TEXT    NOT NULL DEFAULT '',
    rationale        TEXT    NOT NULL DEFAULT '',
    FOREIGN KEY (approval_id) REFERENCES approval_requests(approval_id)
);
"""

_CREATE_HISTORY_INDEX = """
CREATE INDEX IF NOT EXISTS idx_history_approval
    ON approval_history(approval_id);
"""


# =========================================================================
# Approval Store
# =========================================================================


class ApprovalStore:
    """Durable, thread-safe store for approval requests.

    SQLite-backed, following the GovernanceAuditStore pattern.

    Usage::

        store = ApprovalStore(":memory:")
        req = store.create_request(context, ApprovalLevel.CONFIRM)
        store.approve(req.approval_id, decided_by="admin@corp.com")
        approved = store.get(req.approval_id)
        assert approved.status == ApprovalStatus.APPROVED
    """

    def __init__(self, db_path: str = "approval_workflow.db") -> None:
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
            self._conn.executescript(
                _CREATE_APPROVAL_TABLE
                + _CREATE_APPROVAL_INDEXES
                + _CREATE_APPROVAL_HISTORY
                + _CREATE_HISTORY_INDEX
            )
            self._conn.commit()
        except sqlite3.Error as e:
            raise ApprovalStoreError(
                f"Failed to open approval database at {db_path}: {e}"
            ) from e

    # -- Create ------------------------------------------------------------

    def create_request(
        self,
        context: ApprovalContext,
        approval_level: ApprovalLevel = ApprovalLevel.CONFIRM,
        expiry_hours: float = DEFAULT_EXPIRY_HOURS,
    ) -> ApprovalRequest:
        """Create a new pending approval request.

        Args:
            context: Governance context that triggered the approval.
            approval_level: Required approval level.
            expiry_hours: Hours until the approval expires.

        Returns:
            The created ApprovalRequest.

        Raises:
            ApprovalStoreError: If persistence fails (fail-closed).
        """
        now = datetime.now(timezone.utc)
        approval_id = _generate_approval_id()
        created_at = now.isoformat()
        expires_at = (now + timedelta(hours=expiry_hours)).isoformat()

        request = ApprovalRequest(
            approval_id=approval_id,
            created_at=created_at,
            expires_at=expires_at,
            status=ApprovalStatus.PENDING,
            approval_level=approval_level,
            context=context,
        )

        with self._lock:
            try:
                self._conn.execute(
                    """INSERT INTO approval_requests (
                        approval_id, created_at, expires_at, status,
                        approval_level, context_json, decision_json,
                        schema_version, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        approval_id,
                        created_at,
                        expires_at,
                        ApprovalStatus.PENDING.value,
                        approval_level.value,
                        json.dumps(context.to_dict(), sort_keys=True),
                        None,
                        SCHEMA_VERSION,
                        created_at,
                    ),
                )
                self._record_history(
                    approval_id, "none", ApprovalStatus.PENDING.value,
                    actor="system", rationale="Approval request created",
                    timestamp=created_at,
                )
                self._conn.commit()
            except sqlite3.Error as e:
                raise ApprovalStoreError(
                    f"Failed to create approval request: {e}"
                ) from e

        return request

    # -- Read --------------------------------------------------------------

    def get(self, approval_id: str) -> ApprovalRequest:
        """Get an approval request by ID.

        Raises:
            ApprovalNotFoundError: If not found.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM approval_requests WHERE approval_id = ?",
                (approval_id,),
            ).fetchone()

        if row is None:
            raise ApprovalNotFoundError(
                f"Approval request '{approval_id}' not found"
            )
        return self._row_to_request(row)

    def list_pending(self, limit: int = 100) -> List[ApprovalRequest]:
        """List pending (non-expired) approval requests, newest first."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            rows = self._conn.execute(
                """SELECT * FROM approval_requests
                   WHERE status = ? AND expires_at > ?
                   ORDER BY created_at DESC LIMIT ?""",
                (ApprovalStatus.PENDING.value, now, limit),
            ).fetchall()
        return [self._row_to_request(r) for r in rows]

    def list_by_status(
        self,
        status: ApprovalStatus,
        limit: int = 100,
    ) -> List[ApprovalRequest]:
        """List approval requests by status, newest first."""
        with self._lock:
            rows = self._conn.execute(
                """SELECT * FROM approval_requests
                   WHERE status = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (status.value, limit),
            ).fetchall()
        return [self._row_to_request(r) for r in rows]

    def list_recent(self, limit: int = 100) -> List[ApprovalRequest]:
        """List all approval requests, newest first."""
        with self._lock:
            rows = self._conn.execute(
                """SELECT * FROM approval_requests
                   ORDER BY created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [self._row_to_request(r) for r in rows]

    def get_history(self, approval_id: str) -> List[Dict[str, Any]]:
        """Get the transition history for an approval request."""
        with self._lock:
            rows = self._conn.execute(
                """SELECT seq, approval_id, timestamp, from_status,
                          to_status, actor, rationale
                   FROM approval_history
                   WHERE approval_id = ?
                   ORDER BY seq ASC""",
                (approval_id,),
            ).fetchall()
        return [
            {
                "seq": r[0],
                "approval_id": r[1],
                "timestamp": r[2],
                "from_status": r[3],
                "to_status": r[4],
                "actor": r[5],
                "rationale": r[6],
            }
            for r in rows
        ]

    def count(self, status: Optional[ApprovalStatus] = None) -> int:
        """Count approval requests, optionally filtered by status."""
        with self._lock:
            if status is not None:
                row = self._conn.execute(
                    "SELECT COUNT(*) FROM approval_requests WHERE status = ?",
                    (status.value,),
                ).fetchone()
            else:
                row = self._conn.execute(
                    "SELECT COUNT(*) FROM approval_requests"
                ).fetchone()
        return row[0] if row else 0

    # -- State Transitions -------------------------------------------------

    def approve(
        self,
        approval_id: str,
        decided_by: str,
        rationale: str = "",
    ) -> ApprovalRequest:
        """Approve a pending request.

        Raises:
            ApprovalNotFoundError: If not found.
            ApprovalTransitionError: If not in PENDING state or expired.
        """
        return self._transition(
            approval_id,
            ApprovalStatus.APPROVED,
            decided_by,
            rationale,
        )

    def deny(
        self,
        approval_id: str,
        decided_by: str,
        rationale: str = "",
    ) -> ApprovalRequest:
        """Deny a pending request.

        Raises:
            ApprovalNotFoundError: If not found.
            ApprovalTransitionError: If not in PENDING state.
        """
        return self._transition(
            approval_id,
            ApprovalStatus.DENIED,
            decided_by,
            rationale,
        )

    def expire(self, approval_id: str) -> ApprovalRequest:
        """Mark a pending request as expired.

        Raises:
            ApprovalNotFoundError: If not found.
            ApprovalTransitionError: If not in PENDING state.
        """
        return self._transition(
            approval_id,
            ApprovalStatus.EXPIRED,
            decided_by="system",
            rationale="Approval expired",
        )

    def cancel(
        self,
        approval_id: str,
        canceled_by: str,
        rationale: str = "",
    ) -> ApprovalRequest:
        """Cancel a pending request.

        Raises:
            ApprovalNotFoundError: If not found.
            ApprovalTransitionError: If not in PENDING state.
        """
        return self._transition(
            approval_id,
            ApprovalStatus.CANCELED,
            canceled_by,
            rationale or "Approval canceled",
        )

    def supersede(
        self,
        approval_id: str,
        superseded_by: str = "system",
        rationale: str = "",
    ) -> ApprovalRequest:
        """Mark a pending request as superseded (replaced by a new request).

        Raises:
            ApprovalNotFoundError: If not found.
            ApprovalTransitionError: If not in PENDING state.
        """
        return self._transition(
            approval_id,
            ApprovalStatus.SUPERSEDED,
            superseded_by,
            rationale or "Superseded by newer request",
        )

    def expire_stale(self) -> int:
        """Expire all pending requests past their expiry time.

        Returns:
            Number of requests expired.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            rows = self._conn.execute(
                """SELECT approval_id FROM approval_requests
                   WHERE status = ? AND expires_at <= ?""",
                (ApprovalStatus.PENDING.value, now),
            ).fetchall()

        count = 0
        for (aid,) in rows:
            try:
                self.expire(aid)
                count += 1
            except (ApprovalTransitionError, ApprovalNotFoundError):
                pass
        return count

    # -- Internals ---------------------------------------------------------

    def _transition(
        self,
        approval_id: str,
        to_status: ApprovalStatus,
        decided_by: str,
        rationale: str,
    ) -> ApprovalRequest:
        """Execute a validated state transition."""
        now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM approval_requests WHERE approval_id = ?",
                (approval_id,),
            ).fetchone()

            if row is None:
                raise ApprovalNotFoundError(
                    f"Approval request '{approval_id}' not found"
                )

            current = self._row_to_request(row)

            # Validate transition
            if current.status not in _VALID_TRANSITIONS:
                raise ApprovalTransitionError(
                    f"Cannot transition from terminal state '{current.status.value}'"
                )
            if to_status not in _VALID_TRANSITIONS[current.status]:
                raise ApprovalTransitionError(
                    f"Invalid transition: {current.status.value} → {to_status.value}"
                )

            # Check expiry for approve (cannot approve an expired request)
            if to_status == ApprovalStatus.APPROVED and current.is_expired:
                raise ApprovalTransitionError(
                    "Cannot approve an expired request"
                )

            decision = ApprovalDecision(
                decided_by=decided_by,
                decided_at=now,
                decision=to_status,
                rationale=rationale,
            )

            try:
                self._conn.execute(
                    """UPDATE approval_requests
                       SET status = ?, decision_json = ?, updated_at = ?
                       WHERE approval_id = ?""",
                    (
                        to_status.value,
                        json.dumps(decision.to_dict(), sort_keys=True),
                        now,
                        approval_id,
                    ),
                )
                self._record_history(
                    approval_id,
                    current.status.value,
                    to_status.value,
                    actor=decided_by,
                    rationale=rationale,
                    timestamp=now,
                )
                self._conn.commit()
            except sqlite3.Error as e:
                raise ApprovalStoreError(
                    f"Failed to transition approval {approval_id}: {e}"
                ) from e

        return self.get(approval_id)

    def _record_history(
        self,
        approval_id: str,
        from_status: str,
        to_status: str,
        actor: str,
        rationale: str,
        timestamp: str,
    ) -> None:
        """Record a transition in the history table. Caller holds lock."""
        self._conn.execute(
            """INSERT INTO approval_history (
                approval_id, timestamp, from_status, to_status,
                actor, rationale
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (approval_id, timestamp, from_status, to_status, actor, rationale),
        )

    @staticmethod
    def _row_to_request(row: tuple) -> ApprovalRequest:
        """Convert a SQLite row to an ApprovalRequest."""
        columns = [
            "approval_id", "created_at", "expires_at", "status",
            "approval_level", "context_json", "decision_json",
            "schema_version", "updated_at",
        ]
        d = dict(zip(columns, row))

        context_data = json.loads(d["context_json"]) if d["context_json"] else {}
        context = ApprovalContext(
            governance_decision_id=context_data.get("governance_decision_id", ""),
            action_type=context_data.get("action_type", ""),
            tool_name=context_data.get("tool_name", ""),
            actor_id=context_data.get("actor_id", ""),
            risk_level=context_data.get("risk_level", ""),
            confidence_score=context_data.get("confidence_score", 0.0),
            escalation_level=context_data.get("escalation_level", ""),
            execution_mode=context_data.get("execution_mode", ""),
            reason_codes=tuple(context_data.get("reason_codes", ())),
            policy_id=context_data.get("policy_id"),
            policy_version=context_data.get("policy_version"),
            domain_id=context_data.get("domain_id"),
            tenant_id=context_data.get("tenant_id"),
            session_id=context_data.get("session_id"),
        )

        decision = None
        if d["decision_json"]:
            dec_data = json.loads(d["decision_json"])
            decision = ApprovalDecision(
                decided_by=dec_data.get("decided_by", ""),
                decided_at=dec_data.get("decided_at", ""),
                decision=ApprovalStatus(dec_data.get("decision", "denied")),
                rationale=dec_data.get("rationale", ""),
            )

        return ApprovalRequest(
            approval_id=d["approval_id"],
            created_at=d["created_at"],
            expires_at=d["expires_at"],
            status=ApprovalStatus(d["status"]),
            approval_level=ApprovalLevel(d["approval_level"]),
            context=context,
            decision=decision,
            schema_version=d.get("schema_version", SCHEMA_VERSION),
        )

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            self._conn.close()
