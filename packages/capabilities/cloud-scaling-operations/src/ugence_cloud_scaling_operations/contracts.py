"""Public execution contracts for the controlled-execution operations package.

These types define the authority boundary: no infrastructure mutation may occur
without an explicit, immutable :class:`ExecutionAuthorization`. An advisory
recommendation, an approval Boolean, or a confidence score is NOT execution authority.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, Optional

SCHEMA_VERSION = "1.0"


class ExecutionMode(str, Enum):
    """How an execution request is carried out."""

    DRY_RUN = "dry_run"        # no mutation, no creds, no network; proposed receipt only
    SIMULATION = "simulation"  # deterministic local fakes; exercises success/failure/rollback
    SHADOW = "shadow"          # authorized read-only observation only; never mutates
    LIVE = "live"              # real mutation; requires authorization + config + creds


class ExecutionOutcome(str, Enum):
    """Terminal status of an execution attempt."""

    PROPOSED = "proposed"        # DRY_RUN: what would be done
    SIMULATED = "simulated"      # SIMULATION: applied against a fake
    SHADOWED = "shadowed"        # SHADOW: read-only observation
    APPLIED = "applied"          # LIVE: mutation applied
    DUPLICATE = "duplicate"      # idempotent replay of a completed request
    DENIED = "denied"            # authority/policy denial (fail closed)
    FAILED = "failed"            # execution attempted but errored


class ExecutionAction(str, Enum):
    SCALE = "scale"
    ARGOCD_SYNC = "argocd_sync"
    ADMISSION_GATE = "admission_gate"
    ROLLBACK = "rollback"


class ExecutionDenied(Exception):
    """Raised/returned when an action is not authorized (fail closed)."""

    def __init__(self, reason: str, code: str = "denied"):
        super().__init__(reason)
        self.reason = reason
        self.code = code


class ExecutionIntegrityError(Exception):
    """Raised when idempotency/replay integrity is violated."""


@dataclass(frozen=True)
class ExecutionAuthorization:
    """Immutable external authorization for exactly one infrastructure change.

    Minted by an external governance authority — never by this package's own
    recommendation, approval, or confidence logic.
    """

    authorization_id: str
    decision_id: str
    recommendation_id: str
    tenant_id: str
    actor_id: str
    authority_source: str
    issued_at: float
    expires_at: float
    permitted_action: str            # an ExecutionAction value
    target_cluster: str
    target_namespace: str
    target_resource: str
    current_replicas: int
    minimum_replicas: int
    maximum_replicas: int
    maximum_delta: int
    reason: str
    policy_version: str
    idempotency_key: str
    nonce: str
    # Optional cryptographic fields (verified by a pluggable AuthorityVerifier).
    issuer: Optional[str] = None
    signature_algorithm: Optional[str] = None
    signature: Optional[str] = None
    key_id: Optional[str] = None

    def signing_payload(self) -> str:
        """Deterministic payload over the non-signature fields (for verification)."""
        d = {k: v for k, v in asdict(self).items()
             if k not in ("signature", "signature_algorithm", "key_id")}
        return json.dumps(d, sort_keys=True, separators=(",", ":"))

    def is_expired(self, now: Optional[float] = None) -> bool:
        now = time.time() if now is None else now
        return now >= self.expires_at

    def is_not_yet_valid(self, now: Optional[float] = None) -> bool:
        now = time.time() if now is None else now
        return now < self.issued_at


@dataclass(frozen=True)
class ExecutionRequest:
    """A concrete request to change (or propose changing) one target."""

    action: str                      # an ExecutionAction value
    target_cluster: str
    target_namespace: str
    target_resource: str
    current_replicas: int
    target_replicas: int
    recommendation_id: str
    idempotency_key: str
    correlation_id: Optional[str] = None
    observed_at: Optional[float] = None   # when current_replicas was observed (staleness)
    metadata: Optional[Dict[str, Any]] = None

    @property
    def delta(self) -> int:
        return self.target_replicas - self.current_replicas

    def digest(self) -> str:
        payload = json.dumps({
            "action": self.action,
            "target_cluster": self.target_cluster,
            "target_namespace": self.target_namespace,
            "target_resource": self.target_resource,
            "target_replicas": self.target_replicas,
            "recommendation_id": self.recommendation_id,
            "idempotency_key": self.idempotency_key,
        }, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class ExecutionReceipt:
    """JSON-serializable record of an execution attempt (including denials)."""

    schema_version: str
    outcome: str                     # an ExecutionOutcome value
    action: str
    execution_mode: str
    target_cluster: str
    target_namespace: str
    target_resource: str
    pre_state: Optional[int]
    post_state: Optional[int]
    requested_replicas: int
    applied: bool
    authorization_id: Optional[str]
    recommendation_id: str
    correlation_id: Optional[str]
    idempotency_key: str
    denial_reason: Optional[str] = None
    detail: str = ""
    audit_event_id: Optional[str] = None
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {k: asdict(self)[k] for k in sorted(asdict(self))}

    def to_json(self, *, indent: Optional[int] = None) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=indent)

    def receipt_hash(self) -> str:
        return hashlib.sha256(self.to_json().encode()).hexdigest()


# Alias kept for the documented public name (a receipt is the execution result object).
ExecutionResult = ExecutionReceipt


__all__ = [
    "SCHEMA_VERSION",
    "ExecutionMode",
    "ExecutionOutcome",
    "ExecutionAction",
    "ExecutionDenied",
    "ExecutionIntegrityError",
    "ExecutionAuthorization",
    "ExecutionRequest",
    "ExecutionReceipt",
    "ExecutionResult",
]
