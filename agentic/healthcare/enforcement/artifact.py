"""
Authorization artifact, execution request, and PHI-safe execution receipt.

The AuthorizationArtifact is an integrity-bound (HMAC-signed) object that states
*exactly* what may be executed. The enforcement adapter trusts the artifact, not
the calling agent: any material difference between the execution attempt and the
artifact is rejected.

Nothing here carries raw PHI — only classifications, opaque references, scopes,
and provenance.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Dict, Optional, Tuple

# NOTE: test/HMAC key. A real deployment uses asymmetric signing + key custody.
DEFAULT_SIGNING_KEY = b"actiongate-healthcare-enforcement-test-key"


def _canonical(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      default=str).encode("utf-8")


def sign_payload(payload: Dict[str, Any], key: bytes = DEFAULT_SIGNING_KEY) -> str:
    """Deterministic HMAC-SHA256 over the canonical payload."""
    return hmac.new(key, _canonical(payload), hashlib.sha256).hexdigest()


class ExecutionStatus(str, Enum):
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"


class MismatchCode(str, Enum):
    """Deterministic rejection reasons (fail-closed)."""

    OK = "OK"
    SIGNATURE_INVALID = "E_SIGNATURE_INVALID"
    EXPIRED = "E_EXPIRED"
    REPLAY = "E_REPLAY_NONCE_USED"
    APPROVAL_INCOMPLETE = "E_APPROVAL_INCOMPLETE"
    TENANT_MISMATCH = "E_TENANT_MISMATCH"
    ACTOR_MISMATCH = "E_ACTOR_MISMATCH"
    AGENT_MISMATCH = "E_AGENT_MISMATCH"
    PATIENT_MISMATCH = "E_PATIENT_MISMATCH"
    ENCOUNTER_MISMATCH = "E_ENCOUNTER_MISMATCH"
    OPERATION_MISMATCH = "E_OPERATION_MISMATCH"
    PURPOSE_MISMATCH = "E_PURPOSE_MISMATCH"
    DESTINATION_MISMATCH = "E_DESTINATION_MISMATCH"
    SCOPE_WIDENING = "E_SCOPE_WIDENING"
    CONSENT_CHANGED = "E_CONSENT_CHANGED"
    POLICY_STALE = "E_POLICY_STALE"
    RECORD_LIMIT = "E_RECORD_LIMIT"
    CUMULATIVE_LIMIT = "E_CUMULATIVE_SESSION_LIMIT"
    NO_AUTHORIZATION = "E_NO_AUTHORIZATION"


# Fields covered by the signature (everything except `signature` itself).
_SIGNED_FIELDS = (
    "authorization_id", "tenant_id", "actor_id", "actor_role", "agent_id",
    "agent_version", "patient_ref", "encounter_ref", "purpose", "operation",
    "permitted_categories", "excluded_categories", "required_redactions",
    "max_record_count", "approved_destination", "destination_class",
    "allow_external", "no_onward_disclosure", "approval_required",
    "approval_completed", "policy_version", "policy_hash", "governance_version",
    "model_version", "issued_at", "expires_at", "nonce", "one_time",
    "require_policy_freshness", "final_authority_used", "consent_state",
)


@dataclass(frozen=True)
class AuthorizationArtifact:
    """Integrity-bound statement of exactly what may be executed."""

    authorization_id: str
    tenant_id: str
    actor_id: str
    actor_role: str
    agent_id: Optional[str]
    agent_version: Optional[str]
    patient_ref: Optional[str]
    encounter_ref: Optional[str]
    purpose: str
    operation: str
    permitted_categories: Tuple[str, ...]
    excluded_categories: Tuple[str, ...]
    required_redactions: Tuple[str, ...]
    max_record_count: int
    approved_destination: Optional[str]
    destination_class: str
    allow_external: bool
    no_onward_disclosure: bool
    approval_required: bool
    approval_completed: bool
    policy_version: str
    policy_hash: str
    governance_version: str
    model_version: Optional[str]
    issued_at: float
    expires_at: float
    nonce: str
    one_time: bool
    require_policy_freshness: bool
    final_authority_used: str
    consent_state: str
    signature: str = ""

    def signing_payload(self) -> Dict[str, Any]:
        d = {}
        for f in _SIGNED_FIELDS:
            v = getattr(self, f)
            d[f] = list(v) if isinstance(v, tuple) else v
        return d

    def signed(self, key: bytes = DEFAULT_SIGNING_KEY) -> "AuthorizationArtifact":
        return replace(self, signature=sign_payload(self.signing_payload(), key))

    def verify(self, key: bytes = DEFAULT_SIGNING_KEY) -> bool:
        expected = sign_payload(self.signing_payload(), key)
        return hmac.compare_digest(expected, self.signature)

    def safe_dict(self) -> Dict[str, Any]:
        """PHI-free view for audit (all fields are classifications/refs)."""
        return self.signing_payload() | {"signature_present": bool(self.signature)}


@dataclass(frozen=True)
class ExecutionRequest:
    """What the caller actually attempts at execution time (may be adversarial)."""

    authorization_id: str
    tenant_id: str
    actor_id: str
    agent_id: Optional[str]
    patient_ref: Optional[str]
    encounter_ref: Optional[str]
    operation: str
    purpose: str
    requested_categories: Tuple[str, ...]
    destination_class: str
    destination_ref: Optional[str]
    consent_state: str
    policy_version: str
    approval_completed: bool
    record_count: int = 1
    session_id: str = "default-session"

    @staticmethod
    def faithful_from(artifact: AuthorizationArtifact, *,
                      session_id: str = "default-session",
                      **overrides: Any) -> "ExecutionRequest":
        """An honest execution matching the artifact; tests mutate via overrides."""
        base = dict(
            authorization_id=artifact.authorization_id,
            tenant_id=artifact.tenant_id,
            actor_id=artifact.actor_id,
            agent_id=artifact.agent_id,
            patient_ref=artifact.patient_ref,
            encounter_ref=artifact.encounter_ref,
            operation=artifact.operation,
            purpose=artifact.purpose,
            requested_categories=artifact.permitted_categories,
            destination_class=artifact.destination_class,
            destination_ref=artifact.approved_destination,
            consent_state=artifact.consent_state,
            policy_version=artifact.policy_version,
            approval_completed=artifact.approval_completed,
            record_count=1,
            session_id=session_id,
        )
        base.update(overrides)
        return ExecutionRequest(**base)


@dataclass(frozen=True)
class ExecutionReceipt:
    """PHI-safe execution receipt — classifications/refs/provenance only."""

    authorization_id: str
    execution_status: str
    tenant_ref: str
    actor_ref: str
    agent_ref: Optional[str]
    patient_ref: Optional[str]
    encounter_ref: Optional[str]
    operation: str
    categories_released: Tuple[str, ...]
    categories_excluded: Tuple[str, ...]
    redactions_applied: Tuple[str, ...]
    record_count: int
    destination_class: str
    policy_version: str
    timestamp: float
    denial_code: Optional[str]
    audit_correlation_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "authorization_id": self.authorization_id,
            "execution_status": self.execution_status,
            "tenant_ref": self.tenant_ref,
            "actor_ref": self.actor_ref,
            "agent_ref": self.agent_ref,
            "patient_ref": self.patient_ref,
            "encounter_ref": self.encounter_ref,
            "operation": self.operation,
            "categories_released": list(self.categories_released),
            "categories_excluded": list(self.categories_excluded),
            "redactions_applied": list(self.redactions_applied),
            "record_count": self.record_count,
            "destination_class": self.destination_class,
            "policy_version": self.policy_version,
            "timestamp": self.timestamp,
            "denial_code": self.denial_code,
            "audit_correlation_id": self.audit_correlation_id,
        }


@dataclass(frozen=True)
class ExecutionResult:
    """The receipt (for audit) plus the released synthetic payload (for caller).

    The payload is delivered to the caller but MUST NOT be logged to governance
    audit — it is the only place field values appear.
    """

    receipt: ExecutionReceipt
    payload: Dict[str, Any] = field(default_factory=dict)

    @property
    def executed(self) -> bool:
        return self.receipt.execution_status == ExecutionStatus.EXECUTED.value

    @property
    def denial_code(self) -> Optional[str]:
        return self.receipt.denial_code
