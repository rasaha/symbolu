"""
PO5 — Planner Execution Gate

Deterministic gate that evaluates execution eligibility.
No execution, no reasoning, no side effects.

PO phases are pre-acoustic governance layers and precede symbolic processing (P1+).

This is a governance layer that determines if execution would be conceptually
permitted in the current context. It produces a read-only verdict and does NOT
execute, schedule, or trigger any actions.

Authority Model:
- Consumes PO2 IntentEnvelope, PO4 PlannerProposalEnvelope, and PO1 OverallPolicy
- Cannot override PO1–PO4 decisions
- Produces ExecutionEligibilityEnvelope (read-only, non-actuating)
- No execution occurs at this phase or any downstream phase from PO5

Deterministic Rules (Authoritative, evaluated in order):
1. If proposal.status == BLOCKED → PROHIBITED
2. If intent_envelope.posture in {HOLD, ACKNOWLEDGE} → PROHIBITED
3. If intent_envelope.intent in {CLARIFY, INFORM} → PROHIBITED
4. If overall_policy == MULTI_CONTEXT → DEFERRED
5. If intent in {SUPPORT, REFLECT} and proposal is VALID → DEFERRED
6. ELIGIBLE is allowed only as an informational state

CRITICAL: ELIGIBLE does not enable execution. No executor exists.
"""

from __future__ import annotations

from symbolu.mechanical.pipeline.phase_zero.phase_zero_schema import (
    IntentEnvelope,
    IntentType,
    ResponsePosture,
)
from symbolu.mechanical.pipeline.phase_po4.po4_schema import (
    PlannerProposalEnvelope,
    ProposalStatus,
)
from symbolu.mechanical.pipeline.grounding.phase_minus_one_schema import OverallPolicy
from symbolu.mechanical.pipeline.phase_po5.po5_schema import (
    ExecutionEligibility,
    ExecutionEligibilityEnvelope,
)


class PO5ExecutionGate:
    """
    Deterministic execution eligibility gate (non-actuating).

    This gate implements strict, deterministic rules to determine if execution
    would be conceptually permitted. It does NOT execute any actions or enable
    any execution pathway.

    CRITICAL: This class is purely evaluative. The ELIGIBLE status is
    informational only. No executor exists in the Symbol-U architecture
    at this phase.

    Usage:
        gate = PO5ExecutionGate()
        envelope = gate.evaluate(intent_envelope, proposal, overall_policy)
        # envelope.eligibility indicates PROHIBITED / DEFERRED / ELIGIBLE
        # ELIGIBLE is informational only; no execution occurs
    """

    def __init__(self) -> None:
        """Initialize the PO5 execution gate."""
        pass  # No state needed - purely deterministic

    def evaluate(
        self,
        intent_envelope: IntentEnvelope,
        proposal: PlannerProposalEnvelope,
        overall_policy: OverallPolicy,
    ) -> ExecutionEligibilityEnvelope:
        """
        Evaluate execution eligibility based on deterministic rules.

        This is a pure, deterministic evaluation with no side effects.
        The result is a read-only eligibility verdict.

        CRITICAL: ELIGIBLE does not enable execution. No executor exists.

        Deterministic Rules (evaluated in order):
        1. If proposal.status == BLOCKED → PROHIBITED
        2. If intent_envelope.posture in {HOLD, ACKNOWLEDGE} → PROHIBITED
        3. If intent_envelope.intent in {CLARIFY, INFORM} → PROHIBITED
        4. If overall_policy == MULTI_CONTEXT → DEFERRED
        5. If intent in {SUPPORT, REFLECT} and proposal is VALID → DEFERRED
        6. Otherwise → ELIGIBLE (informational only)

        Args:
            intent_envelope: The PO2 IntentEnvelope (provides intent/posture).
            proposal: The PO4 PlannerProposalEnvelope (provides proposal status).
            overall_policy: The PO1 OverallPolicy (provides grounding policy).

        Returns:
            ExecutionEligibilityEnvelope with eligibility verdict.

        Raises:
            ValueError: If inputs are None or invalid.
        """
        # Validate inputs
        if intent_envelope is None:
            raise ValueError("intent_envelope cannot be None")
        if proposal is None:
            raise ValueError("proposal cannot be None")
        if overall_policy is None:
            raise ValueError("overall_policy cannot be None")

        # Extract values for rule evaluation
        intent_type = intent_envelope.intent_type
        response_posture = intent_envelope.response_posture
        proposal_status = proposal.status

        # Apply deterministic rules in order
        eligibility, reason = self._apply_rules(
            intent_type=intent_type,
            response_posture=response_posture,
            proposal_status=proposal_status,
            overall_policy=overall_policy,
        )

        # Build debug info
        debug = self._build_debug_info(
            intent_envelope=intent_envelope,
            proposal=proposal,
            overall_policy=overall_policy,
            eligibility=eligibility,
        )

        return ExecutionEligibilityEnvelope(
            eligibility=eligibility,
            reason=reason,
            intent=intent_type,
            proposal_status=proposal_status,
            debug=debug,
        )

    def _apply_rules(
        self,
        intent_type: IntentType,
        response_posture: ResponsePosture,
        proposal_status: ProposalStatus,
        overall_policy: OverallPolicy,
    ) -> tuple[ExecutionEligibility, str]:
        """
        Apply deterministic rules to determine eligibility.

        Rules are evaluated in strict order. First matching rule wins.

        Args:
            intent_type: The classified intent from PO2.
            response_posture: The response posture from PO2.
            proposal_status: The proposal status from PO4.
            overall_policy: The overall policy from PO1.

        Returns:
            Tuple of (ExecutionEligibility, reason string).
        """
        # Rule 1: If proposal.status == BLOCKED → PROHIBITED
        if proposal_status == ProposalStatus.BLOCKED:
            return (
                ExecutionEligibility.PROHIBITED,
                f"Execution prohibited: PO4 proposal is BLOCKED"
            )

        # Rule 2: If posture in {HOLD, ACKNOWLEDGE} → PROHIBITED
        if response_posture in {ResponsePosture.HOLD, ResponsePosture.ACKNOWLEDGE}:
            return (
                ExecutionEligibility.PROHIBITED,
                f"Execution prohibited: Response posture is {response_posture.value} "
                f"(requires clarification or acknowledgment only)"
            )

        # Rule 3: If intent in {CLARIFY, INFORM} → PROHIBITED
        if intent_type in {IntentType.CLARIFY, IntentType.INFORM}:
            return (
                ExecutionEligibility.PROHIBITED,
                f"Execution prohibited: Intent type {intent_type.value} "
                f"does not permit execution"
            )

        # Rule 4: If overall_policy == MULTI_CONTEXT → DEFERRED
        if overall_policy == OverallPolicy.MULTI_CONTEXT:
            return (
                ExecutionEligibility.DEFERRED,
                f"Execution deferred: Multiple grounding contexts detected; "
                f"per-clause handling required"
            )

        # Rule 5: If intent in {SUPPORT, REFLECT} and proposal is VALID → DEFERRED
        if intent_type in {IntentType.SUPPORT, IntentType.REFLECT}:
            if proposal_status == ProposalStatus.VALID:
                return (
                    ExecutionEligibility.DEFERRED,
                    f"Execution deferred: Intent type {intent_type.value} with VALID "
                    f"proposal requires careful engagement before execution"
                )

        # Rule 6: ELIGIBLE (informational only)
        # This is the fallthrough case for proposals that pass all prohibitions
        # CRITICAL: ELIGIBLE does not enable execution; no executor exists
        return (
            ExecutionEligibility.ELIGIBLE,
            f"Execution conceptually eligible (informational only; "
            f"no executor exists in architecture)"
        )

    def _build_debug_info(
        self,
        intent_envelope: IntentEnvelope,
        proposal: PlannerProposalEnvelope,
        overall_policy: OverallPolicy,
        eligibility: ExecutionEligibility,
    ) -> dict:
        """Build debug information for tracing."""
        return {
            "source_intent": intent_envelope.intent_type.value,
            "source_posture": intent_envelope.response_posture.value,
            "proposal_status": proposal.status.value,
            "overall_policy": overall_policy.value,
            "eligibility": eligibility.value,
            "proposal_allowed_count": proposal.allowed_count(),
            "proposal_rejected_count": proposal.rejected_count(),
            "planning_allowed": intent_envelope.planning_allowed,
        }


# Public exports
__all__ = [
    "PO5ExecutionGate",
]
