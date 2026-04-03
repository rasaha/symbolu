"""
PO4 — Planner Proposal Envelope Resolver

Deterministic resolution that wraps planner proposals into a validated
envelope structure. No execution, no reasoning, no side effects.

PO phases are pre-acoustic governance layers and precede symbolic processing (P1+).

This is a governance layer that captures planner proposals and validates them
against PO3 allow-lists. The planner output is wrapped, never executed.

Authority Model:
- Consumes PO2 IntentEnvelope and PO3 AllowedActionSet (read-only)
- Cannot override PO1–PO3 decisions
- Produces PlannerProposalEnvelope for governance/audit review
- No execution occurs at this phase
"""

from __future__ import annotations

from typing import Dict, FrozenSet, List

from symbolu_core.mechanical.pipeline.phase_zero.phase_zero_schema import IntentEnvelope
from symbolu_core.mechanical.pipeline.phase_one.phase_one_schema import AllowedActionSet
from symbolu_core.mechanical.pipeline.governance.planner_gate import (
    ActionClass,
    GatedPlanResult,
)
from symbolu_core.mechanical.pipeline.phase_po4.po4_schema import (
    ProposalStatus,
    PlannerProposalEnvelope,
)


class PO4Resolver:
    """
    Deterministic resolver that wraps planner proposals into a validated envelope.

    This resolver implements strict proposal validation with no probabilistic
    logic, no LLM calls, and no side effects. It captures what the planner
    is attempting to do without executing any actions.

    Usage:
        resolver = PO4Resolver()
        envelope = resolver.resolve(intent_envelope, allowed_action_set, proposed_actions)
        # envelope.status indicates VALID / PARTIALLY_ALLOWED / BLOCKED
    """

    def __init__(self) -> None:
        """Initialize the PO4 resolver."""
        pass  # No state needed - purely deterministic

    def resolve(
        self,
        intent_envelope: IntentEnvelope,
        allowed_action_set: AllowedActionSet,
        proposed_actions: List[ActionClass],
    ) -> PlannerProposalEnvelope:
        """
        Resolve planner proposals into a validated envelope.

        This is a pure, deterministic validation with no side effects.
        The result captures what was proposed and what was allowed/rejected.

        Deterministic Rules:
        1. If PO3 allowed_actions is empty ⇒ ProposalStatus.BLOCKED
        2. If any proposed action not in allowed_actions ⇒ PARTIALLY_ALLOWED
        3. If all proposed actions in allowed_actions ⇒ VALID
        4. If no actions proposed and PO3 not empty ⇒ VALID (empty proposal)

        Args:
            intent_envelope: The PO2 IntentEnvelope (provides context).
            allowed_action_set: The PO3 AllowedActionSet (provides allow-list).
            proposed_actions: List of actions the planner proposes.

        Returns:
            PlannerProposalEnvelope with validation result.

        Raises:
            ValueError: If inputs are None or invalid.
        """
        # Validate inputs
        if intent_envelope is None:
            raise ValueError("intent_envelope cannot be None")
        if allowed_action_set is None:
            raise ValueError("allowed_action_set cannot be None")
        if proposed_actions is None:
            raise ValueError("proposed_actions cannot be None")

        intent_type = intent_envelope.intent_type
        po3_allowed = allowed_action_set.allowed_actions
        proposed_set = frozenset(proposed_actions)

        # Validate all proposed actions are ActionClass
        for action in proposed_actions:
            if not isinstance(action, ActionClass):
                raise ValueError(
                    f"All proposed_actions must be ActionClass, got {type(action).__name__}"
                )

        # Build allowed and rejected sets
        allowed_actions, rejected_actions = self._partition_proposals(
            proposed_set, po3_allowed
        )

        # Determine status
        status, blocked_reason = self._determine_status(
            po3_allowed=po3_allowed,
            allowed_actions=allowed_actions,
            rejected_actions=rejected_actions,
            intent_envelope=intent_envelope,
        )

        # Build debug info
        debug = self._build_debug_info(
            intent_envelope=intent_envelope,
            allowed_action_set=allowed_action_set,
            proposed_actions=proposed_set,
            allowed_actions=allowed_actions,
            rejected_actions=rejected_actions,
        )

        return PlannerProposalEnvelope(
            intent=intent_type,
            allowed_actions=frozenset(allowed_actions),
            proposed_actions=proposed_set,
            rejected_actions=rejected_actions,
            status=status,
            blocked_reason=blocked_reason,
            debug=debug,
        )

    def resolve_from_gated_plan(
        self,
        intent_envelope: IntentEnvelope,
        allowed_action_set: AllowedActionSet,
        gated_plan: GatedPlanResult,
    ) -> PlannerProposalEnvelope:
        """
        Resolve from a GatedPlanResult (alternative entry point).

        This method extracts proposed actions from a GatedPlanResult structure
        and wraps them into a PlannerProposalEnvelope.

        Args:
            intent_envelope: The PO2 IntentEnvelope.
            allowed_action_set: The PO3 AllowedActionSet.
            gated_plan: The GatedPlanResult from PlannerGate.

        Returns:
            PlannerProposalEnvelope with validation result.
        """
        if gated_plan is None:
            raise ValueError("gated_plan cannot be None")

        # Extract all proposed actions (selected + rejected keys)
        proposed_actions: List[ActionClass] = list(gated_plan.selected_action_classes)
        proposed_actions.extend(gated_plan.rejected_action_classes.keys())

        return self.resolve(intent_envelope, allowed_action_set, proposed_actions)

    def _partition_proposals(
        self,
        proposed: FrozenSet[ActionClass],
        po3_allowed: FrozenSet[ActionClass],
    ) -> tuple[FrozenSet[ActionClass], Dict[ActionClass, str]]:
        """
        Partition proposed actions into allowed and rejected sets.

        An action is allowed if and only if it is in the PO3 allow-list.
        All other actions are rejected with reason.

        Args:
            proposed: Set of proposed actions.
            po3_allowed: Set of PO3 allowed actions.

        Returns:
            Tuple of (allowed_actions frozenset, rejected_actions dict with reasons).
        """
        allowed: set[ActionClass] = set()
        rejected: Dict[ActionClass, str] = {}

        for action in proposed:
            if action in po3_allowed:
                allowed.add(action)
            else:
                rejected[action] = f"Action {action.value} not in PO3 allow-list"

        return frozenset(allowed), rejected

    def _determine_status(
        self,
        po3_allowed: FrozenSet[ActionClass],
        allowed_actions: FrozenSet[ActionClass],
        rejected_actions: Dict[ActionClass, str],
        intent_envelope: IntentEnvelope,
    ) -> tuple[ProposalStatus, str | None]:
        """
        Determine the proposal status based on validation results.

        Deterministic Rules:
        1. If PO3 is empty (ABSTAIN or blocked upstream) ⇒ BLOCKED
        2. If no actions were proposed ⇒ VALID (empty proposal is valid)
        3. If all proposed actions were allowed ⇒ VALID
        4. If some proposed actions were rejected ⇒ PARTIALLY_ALLOWED
        5. If all proposed actions were rejected ⇒ BLOCKED

        Args:
            po3_allowed: The PO3 allowed action set.
            allowed_actions: Actions that passed validation.
            rejected_actions: Actions that were rejected.
            intent_envelope: The intent envelope for context.

        Returns:
            Tuple of (ProposalStatus, blocked_reason or None).
        """
        # Rule 1: If PO3 allow-list is empty ⇒ BLOCKED
        if len(po3_allowed) == 0:
            return (
                ProposalStatus.BLOCKED,
                f"PO3 allow-list is empty for intent {intent_envelope.intent_type.value}"
            )

        # Rule 2: No actions proposed - empty proposal is valid
        if len(allowed_actions) == 0 and len(rejected_actions) == 0:
            return (ProposalStatus.VALID, None)

        # Rule 3: All proposed actions were allowed ⇒ VALID
        if len(rejected_actions) == 0:
            return (ProposalStatus.VALID, None)

        # Rule 4: Some allowed, some rejected ⇒ PARTIALLY_ALLOWED
        if len(allowed_actions) > 0 and len(rejected_actions) > 0:
            return (ProposalStatus.PARTIALLY_ALLOWED, None)

        # Rule 5: All proposed actions rejected ⇒ BLOCKED
        if len(allowed_actions) == 0 and len(rejected_actions) > 0:
            rejected_names = ", ".join(a.value for a in rejected_actions.keys())
            return (
                ProposalStatus.BLOCKED,
                f"All proposed actions rejected: {rejected_names}"
            )

        # Should not reach here, but defensive
        return (ProposalStatus.BLOCKED, "Unknown validation state")

    def _build_debug_info(
        self,
        intent_envelope: IntentEnvelope,
        allowed_action_set: AllowedActionSet,
        proposed_actions: FrozenSet[ActionClass],
        allowed_actions: FrozenSet[ActionClass],
        rejected_actions: Dict[ActionClass, str],
    ) -> Dict:
        """Build debug information for tracing."""
        return {
            "source_intent": intent_envelope.intent_type.value,
            "source_posture": intent_envelope.response_posture.value,
            "po3_allowed_count": len(allowed_action_set.allowed_actions),
            "po3_allowed": sorted([a.value for a in allowed_action_set.allowed_actions]),
            "proposed_count": len(proposed_actions),
            "allowed_count": len(allowed_actions),
            "rejected_count": len(rejected_actions),
        }


# Public exports
__all__ = [
    "PO4Resolver",
]
