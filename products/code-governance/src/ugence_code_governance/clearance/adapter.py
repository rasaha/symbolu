"""ActionGate result + PreparedMergeAction → canonical Action Clearance inputs.

``ActionClearanceShadowAdapter`` builds the canonical Action Clearance request
family from an **eligible** ActionGate shadow result and the exact prepared merge
action, using only the Action Clearance public API. It imports no Action Clearance
internals and never imports Code Governance models into Action Clearance.

Only ``AUTHORIZED`` / ``AUTHORIZED_WITH_CONSTRAINTS`` outcomes are eligible; any
other outcome is refused for CLEAR evaluation (see :func:`is_eligible`).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from ugence_action_clearance import (  # type: ignore
    AuthorizationContext,
    AuthorizedActionIdentity,
    ClearancePolicyContext,
    ClearanceRequest,
    SignalBundle,
)

from ..governance.actiongate_adapter import ShadowActionEvaluation
from ..governance.prepared_action import PreparedMergeAction
from .profile import CodeGovernanceClearanceProfile

#: Canonical ActionGate outcomes eligible for Action Clearance evaluation.
ELIGIBLE_ACTIONGATE_OUTCOMES = frozenset({"AUTHORIZED", "AUTHORIZED_WITH_CONSTRAINTS"})


def is_eligible(shadow_eval: ShadowActionEvaluation) -> bool:
    """True only when the ActionGate outcome may be evaluated for clearance."""
    return (not shadow_eval.errored
            and shadow_eval.outcome in ELIGIBLE_ACTIONGATE_OUTCOMES)


class ActionClearanceShadowAdapter:
    """Builds canonical Action Clearance inputs from Code Governance artifacts."""

    def authorization_context(
        self,
        shadow_eval: ShadowActionEvaluation,
        action: PreparedMergeAction,
        *,
        actor_ref: str,
        authorization_issued_at: datetime,
    ) -> AuthorizationContext:
        return AuthorizationContext(
            authorization_ref=shadow_eval.result_fingerprint,
            authorization_result_fingerprint=shadow_eval.result_fingerprint,
            authorization_outcome=shadow_eval.outcome,
            authorization_issued_at=authorization_issued_at,
            authorization_expires_at=action.expiry,
            tenant_id=action.tenant_id,
            authorization_constraints=tuple(shadow_eval.constraints),
            authorization_obligations=tuple(shadow_eval.obligations),
            decision_record_ref=action.decision_record_id,
            context_envelope_ref=action.cer_id,
            context_envelope_hash=action.cer_content_hash,
            authorized_actor_basis=actor_ref,
            policy_refs=tuple(action.policy_refs),
        )

    def action_identity(
        self, action: PreparedMergeAction, *, actor_ref: str
    ) -> AuthorizedActionIdentity:
        return AuthorizedActionIdentity(
            authorized_action_fingerprint=action.fingerprint,
            action_type="merge_pull_request",
            target_ref=action.repository,
            operation=action.merge_method.value,
            actor_ref=actor_ref,
            artifact_ref=action.head_sha,
            artifact_fingerprint=action.change_fingerprint,
            parameters=dict(action.requested_parameters),
        )

    def policy_context(self, profile: CodeGovernanceClearanceProfile) -> ClearancePolicyContext:
        return ClearancePolicyContext(
            profile_id=profile.profile_id,
            policy_refs=tuple(profile.policy_refs) or (profile.policy_ref,),
            required_control_refs=(),
            max_clearance_lifetime_s=profile.maximum_shadow_clearance_lifetime_s,
            clock_skew_tolerance_s=profile.clock_skew_tolerance_s or None,
        )

    def build_request(
        self,
        *,
        request_id: str,
        tenant_id: str,
        evaluation_time: datetime,
        authorization: AuthorizationContext,
        action: AuthorizedActionIdentity,
        signals: SignalBundle,
        policy: ClearancePolicyContext,
        workflow_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> ClearanceRequest:
        return ClearanceRequest(
            request_id=request_id, tenant_id=tenant_id, evaluation_time=evaluation_time,
            authorization=authorization, action=action, signals=signals, policy=policy,
            workflow_id=workflow_id, correlation_id=correlation_id)


__all__ = [
    "ActionClearanceShadowAdapter",
    "is_eligible",
    "ELIGIBLE_ACTIONGATE_OUTCOMES",
]
