"""ClearanceRequest + ClearancePolicyContext (design §13).

The request binds the authorization context, the exact action identity, the
trusted-signal bundle, and the clearance-policy context. It carries no credentials
and no executable provider commands. The evaluator reads **no** system clock —
``evaluation_time`` is always caller-supplied.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Tuple

from ..errors import ValidationError
from ..fingerprinting import clearance_request_fingerprint
from ..normalization import normalize_timestamp
from .authorization import AuthorizationContext, AuthorizedActionIdentity
from .signals import SignalBundle


@dataclass(frozen=True)
class ClearancePolicyContext:
    """The already-resolved policy projection referenced by the request."""

    profile_id: str
    policy_refs: Tuple[str, ...] = ()
    required_control_refs: Tuple[str, ...] = ()
    max_clearance_lifetime_s: Optional[int] = None
    clock_skew_tolerance_s: Optional[int] = None


@dataclass(frozen=True)
class ClearanceRequest:
    """The immutable input to the deterministic evaluator."""

    request_id: str
    tenant_id: str
    evaluation_time: datetime
    authorization: AuthorizationContext
    action: AuthorizedActionIdentity
    signals: SignalBundle
    policy: ClearancePolicyContext
    correlation_id: Optional[str] = None
    workflow_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValidationError("ClearanceRequest.request_id must be non-empty")
        if self.evaluation_time.tzinfo is None:
            raise ValidationError("evaluation_time must be timezone-aware")

    @property
    def fingerprint(self) -> str:
        auth = self.authorization
        act = self.action
        pol = self.policy
        return clearance_request_fingerprint({
            "request_id": self.request_id,
            "tenant_id": self.tenant_id,
            "correlation_id": self.correlation_id,
            "workflow_id": self.workflow_id,
            "evaluation_time": normalize_timestamp(self.evaluation_time),
            "authorization": {
                "authorization_ref": auth.authorization_ref,
                "authorization_result_fingerprint": auth.authorization_result_fingerprint,
                "authorization_outcome": auth.authorization_outcome,
                "authorization_issued_at": normalize_timestamp(auth.authorization_issued_at),
                "authorization_expires_at": normalize_timestamp(auth.authorization_expires_at),
                "authorization_constraints": sorted(auth.authorization_constraints),
                "authorization_obligations": sorted(auth.authorization_obligations),
                "decision_record_ref": auth.decision_record_ref,
                "context_envelope_ref": auth.context_envelope_ref,
                "context_envelope_hash": auth.context_envelope_hash,
                "authorized_actor_basis": auth.authorized_actor_basis,
                "override_ref": auth.override_ref,
                "supersedes_ref": auth.supersedes_ref,
            },
            "action": {
                "authorized_action_fingerprint": act.authorized_action_fingerprint,
                "action_type": act.action_type,
                "target_ref": act.target_ref,
                "operation": act.operation,
                "action_governance_request_ref": act.action_governance_request_ref,
            },
            "signal_bundle_fingerprint": self.signals.fingerprint,
            "policy": {
                "profile_id": pol.profile_id,
                "policy_refs": sorted(pol.policy_refs),
                "required_control_refs": sorted(pol.required_control_refs),
                "max_clearance_lifetime_s": pol.max_clearance_lifetime_s,
                "clock_skew_tolerance_s": pol.clock_skew_tolerance_s,
            },
        })


__all__ = ["ClearancePolicyContext", "ClearanceRequest"]
