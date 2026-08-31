"""The deny-by-default implementations of the three trust boundaries.

These are the **production defaults**. When no resolver or verifier is
configured, orchestration does not fall back to caller metadata, structural
labels, or "best effort" — it uses these, and every input they touch is refused
with a stable typed reason.

Note what is **not** here, and will not be added: no allow-all resolver, no
allow-all verifier, no "testing" verifier, no ``verify_everything=True`` flag,
and no environment switch that turns denial off. Those absences are the
boundary, not gaps to be filled in later. A test that needs a permissive
verifier writes one inside its own test module, where it can never ship in the
wheel or reach a consumer through the public API.
"""

from __future__ import annotations

from datetime import datetime

from ugence_policy_authority.api import (
    PolicyResolution,
    PolicyResolutionReason,
    uvi_coordinate,
)
from ugence_uvi_policy_contracts.api import PolicyReference

from .codes import ReadinessInputVerificationStatus
from .contracts import (
    ConditionSetVerification,
    ConditionVerificationRequest,
    GateResultVerification,
    GateVerificationRequest,
)
from .errors import ReadinessAssessmentError

__all__ = [
    "DENY_ALL_POLICY_RESOLVER_ID",
    "DENY_ALL_GATE_VERIFIER_ID",
    "DENY_ALL_CONDITION_VERIFIER_ID",
    "DenyAllReadinessPolicyResolver",
    "DenyAllGateResultVerifier",
    "DenyAllConditionSetVerifier",
]

DENY_ALL_POLICY_RESOLVER_ID = "ugence.agent-value-readiness.deny-all-policy-resolver"
DENY_ALL_GATE_VERIFIER_ID = "ugence.agent-value-readiness.deny-all-gate-result-verifier"
DENY_ALL_CONDITION_VERIFIER_ID = "ugence.agent-value-readiness.deny-all-condition-verifier"


class DenyAllReadinessPolicyResolver:
    """Resolves nothing. The default when no trusted resolver is configured."""

    def resolve_readiness_policy(
        self,
        *,
        reference: PolicyReference,
        expected_tenant_id: str,
        as_of: datetime,
    ) -> PolicyResolution:
        if not isinstance(reference, PolicyReference):
            raise ReadinessAssessmentError(
                "DenyAllReadinessPolicyResolver.reference must be a PolicyReference"
            )
        # The coordinate is derived through the shared authority's own public
        # mapping so the refusal is stated in the authority's vocabulary rather
        # than a parallel one invented here.
        return PolicyResolution.unresolved(
            PolicyResolutionReason.NOT_FOUND,
            requested_coordinate=uvi_coordinate(reference),
            as_of=as_of,
            detail=(
                "no trusted readiness-policy resolver is configured; readiness orchestration "
                "denies by default and never resolves a policy itself"
            ),
        )


class DenyAllGateResultVerifier:
    """Verifies nothing. The default when no gate-result verifier is configured.

    It echoes the requested binding back so the refusal is still a complete,
    auditable record of *what* was refused — while carrying no verified status
    and no supporting-verification claim (the contract makes that unstatable).
    """

    def verify_gate_result(self, request: GateVerificationRequest) -> GateResultVerification:
        if not isinstance(request, GateVerificationRequest):
            raise ReadinessAssessmentError(
                "DenyAllGateResultVerifier.request must be a GateVerificationRequest"
            )
        return GateResultVerification(
            status=ReadinessInputVerificationStatus.NO_VERIFIER_CONFIGURED,
            verifier_id=DENY_ALL_GATE_VERIFIER_ID,
            gate_id=request.gate_id,
            gate_digest=request.gate_digest,
            readiness_policy_ref=request.readiness_policy_ref,
            tenant_id=request.tenant_id,
            subject_id=request.subject_id,
            context_digest=request.context_digest,
            requested_target=request.requested_target,
            verified_at=request.evaluation_time,
            detail="no gate-result verifier is configured; the claimed status is not trusted",
        )


class DenyAllConditionSetVerifier:
    """Verifies nothing. The default when no condition verifier is configured."""

    def verify_condition(
        self, request: ConditionVerificationRequest
    ) -> ConditionSetVerification:
        if not isinstance(request, ConditionVerificationRequest):
            raise ReadinessAssessmentError(
                "DenyAllConditionSetVerifier.request must be a ConditionVerificationRequest"
            )
        return ConditionSetVerification(
            status=ReadinessInputVerificationStatus.NO_VERIFIER_CONFIGURED,
            verifier_id=DENY_ALL_CONDITION_VERIFIER_ID,
            condition_id=request.condition_id,
            condition_digest=request.condition_digest,
            source_gate_or_finding_ref=request.source_gate_or_finding_ref,
            covered_gate_id=request.covered_gate_id,
            gate_digest=request.gate_digest,
            readiness_policy_ref=request.readiness_policy_ref,
            tenant_id=request.tenant_id,
            subject_id=request.subject_id,
            context_digest=request.context_digest,
            requested_target=request.requested_target,
            verified_at=request.evaluation_time,
            detail=(
                "no condition verifier is configured; this compensating control provides no "
                "coverage"
            ),
        )
