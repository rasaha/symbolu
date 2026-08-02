"""ActionGate shadow-integration adapter.

Maps a :class:`PreparedMergeAction` into the existing neutral
``ActionGovernanceRequest`` and invokes the live ActionGate provider through its
public ``authorize`` API. ActionGate is **not** modified.

The result is recorded as **SHADOW_ONLY**: the product never acts on it. No
ActionGate outcome — AUTHORIZED or otherwise — can trigger GitHub execution in
this phase. There is no execution method to invoke.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Tuple

# Neutral contract + ActionGate provider — public surfaces only.
from actiongate_provider.api import build_actiongate_provider  # type: ignore
from governance_providers.api import (  # type: ignore
    ActionGovernanceOutcome,
    ActionGovernanceRequest,
    ProviderError,
)

from ..fingerprints import domain_hash
from ..models.enums import ActionEvaluationMode
from .prepared_action import PreparedMergeAction


@dataclass(frozen=True)
class ShadowActionEvaluation:
    """Immutable record of an ActionGate shadow evaluation. Never execution."""

    mode: ActionEvaluationMode
    prepared_action_fingerprint: str
    request_fingerprint: str
    result_fingerprint: str
    outcome: str
    reason_codes: Tuple[str, ...]
    obligations: Tuple[str, ...]
    constraints: Tuple[str, ...]
    provider_trace_id: str
    authority_basis: str
    expiry: Optional[datetime]
    policy_refs: Tuple[str, ...]
    errored: bool = False

    @property
    def would_authorize(self) -> bool:
        """Descriptive only. NEVER an execution signal in this phase."""
        return self.outcome in (
            ActionGovernanceOutcome.AUTHORIZED.value,
            ActionGovernanceOutcome.AUTHORIZED_WITH_CONSTRAINTS.value,
        )


class ActionGateShadowAdapter:
    """Adapter that evaluates a prepared action through ActionGate in shadow mode."""

    def __init__(self, provider=None) -> None:
        if provider is None:
            provider = build_actiongate_provider()
            provider.initialize()
        self._provider = provider

    def _build_request(self, action: PreparedMergeAction) -> ActionGovernanceRequest:
        return ActionGovernanceRequest(
            action_type="merge_pull_request",
            requested_parameters=dict(action.requested_parameters),
            actor="code-governance-shadow",
            authority_context="shadow",
            target_resource=f"github://{action.repository}",
            policy_refs=tuple(action.policy_refs),
            decision_refs=(action.decision_record_id,),
            risk_context={"tenant_id": action.tenant_id, "mode": "SHADOW"},
            correlation_id=action.cer_id,
            idempotency_key=action.fingerprint,
        )

    @staticmethod
    def _request_fingerprint(
        request: ActionGovernanceRequest, prepared_action_fingerprint: str
    ) -> str:
        # Content-derived (replay-stable): only the exact parameters + action
        # identity. Provenance ids (decision_refs, correlation_id=cer_id) are
        # carried on the request but excluded from the identity fingerprint.
        return domain_hash(
            "action_governance_request.v1",
            {
                "action_type": request.action_type,
                "requested_parameters": dict(request.requested_parameters),
                "policy_refs": sorted(request.policy_refs),
                "prepared_action_fingerprint": prepared_action_fingerprint,
            },
        )

    def evaluate_shadow(self, action: PreparedMergeAction) -> ShadowActionEvaluation:
        """Invoke ActionGate for ``action`` in shadow mode (read-only)."""
        request = self._build_request(action)
        req_fp = self._request_fingerprint(request, action.fingerprint)
        try:
            result = self._provider.authorize(request)
        except ProviderError as exc:
            # No decision produced; record as an indeterminate shadow evaluation.
            return ShadowActionEvaluation(
                mode=ActionEvaluationMode.SHADOW_ONLY,
                prepared_action_fingerprint=action.fingerprint,
                request_fingerprint=req_fp,
                result_fingerprint="",
                outcome=ActionGovernanceOutcome.INDETERMINATE.value,
                reason_codes=(type(exc).__name__,),
                obligations=(),
                constraints=(),
                provider_trace_id="",
                authority_basis="",
                expiry=None,
                policy_refs=tuple(action.policy_refs),
                errored=True,
            )
        return ShadowActionEvaluation(
            mode=ActionEvaluationMode.SHADOW_ONLY,
            prepared_action_fingerprint=action.fingerprint,
            request_fingerprint=req_fp,
            result_fingerprint=result.fingerprint,
            outcome=result.outcome.value,
            reason_codes=tuple(result.reason_codes),
            obligations=tuple(result.obligations),
            constraints=tuple(result.constraints),
            provider_trace_id=result.provider_trace_id,
            authority_basis=result.authority_basis,
            expiry=result.expiry,
            policy_refs=tuple(action.policy_refs),
        )


__all__ = ["ShadowActionEvaluation", "ActionGateShadowAdapter"]
