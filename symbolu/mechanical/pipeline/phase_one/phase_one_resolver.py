"""
PO3 — Intent → Allowed Action Contract Resolver
(Implemented as phase_one for backward compatibility)

Deterministic resolution from IntentEnvelope to AllowedActionSet.
No planning, no sequencing, no optimization, no LLM calls.

PO phases are pre-acoustic governance layers and precede symbolic processing (P1+).

This is an authority layer that strictly binds intent to eligible actions.
The Planner may ONLY propose actions from the resulting AllowedActionSet.

Authority Model:
- Consumes PO2 IntentEnvelope (read-only)
- Cannot override PO2 decisions
- Produces AllowedActionSet for Planner consumption
- PlannerGate remains final authority on actual execution
"""

from __future__ import annotations

import uuid
from typing import Dict, FrozenSet, Set

from symbolu.mechanical.pipeline.phase_zero.phase_zero_schema import (
    IntentType,
    IntentEnvelope,
)
from symbolu.mechanical.pipeline.governance.planner_gate import ActionClass
from symbolu.mechanical.pipeline.phase_one.phase_one_schema import AllowedActionSet


# ============================================================================
# CANONICAL MAPPING - Intent → Allowed Actions
# ============================================================================
#
# This mapping is STRICT and DETERMINISTIC.
# Rules:
#   - Empty set is valid (ABSTAIN)
#   - No fallback logic
#   - No dynamic expansion
#   - Planner may only propose actions from this set
#   - PlannerGate remains final authority
#
# Note: When PO2 is extended with additional IntentTypes (e.g., ANALYZE,
# DEESCALATE), this mapping should be updated accordingly.
# ============================================================================

INTENT_TO_ACTIONS: Dict[IntentType, FrozenSet[ActionClass]] = {
    IntentType.CLARIFY: frozenset({
        ActionClass.ASK_CLARIFY_REFERENCE,
        ActionClass.ASK,
    }),

    IntentType.SUPPORT: frozenset({
        ActionClass.CARE,
        ActionClass.VALIDATE,
        ActionClass.REFLECT,
        ActionClass.GROUND,
    }),

    IntentType.REFLECT: frozenset({
        ActionClass.REFLECT,
        ActionClass.REFLECT_BACK,
        ActionClass.ASK,
        ActionClass.ALIGN,
    }),

    IntentType.INFORM: frozenset({
        ActionClass.EXPLAIN,
        ActionClass.SUMMARIZE,
        ActionClass.COMPARE,
    }),

    IntentType.ABSTAIN: frozenset(),
}


class PhaseOneResolver:
    """
    Deterministic resolver from IntentEnvelope to AllowedActionSet.

    This resolver implements strict intent-to-action binding with no
    probabilistic logic, no LLM calls, and no side effects.

    Usage:
        resolver = PhaseOneResolver()
        allowed = resolver.resolve(intent_envelope)
        # allowed.allowed_actions contains the eligible ActionClass values
    """

    def __init__(self) -> None:
        """Initialize the PO3 resolver."""
        # Validate that all IntentTypes are mapped
        self._validate_mapping_coverage()

    def _validate_mapping_coverage(self) -> None:
        """Ensure all IntentTypes have a mapping."""
        for intent_type in IntentType:
            if intent_type not in INTENT_TO_ACTIONS:
                raise RuntimeError(
                    f"INTENT_TO_ACTIONS missing mapping for {intent_type.value}"
                )

    def resolve(self, intent_envelope: IntentEnvelope) -> AllowedActionSet:
        """
        Resolve IntentEnvelope to AllowedActionSet.

        This is a pure, deterministic lookup with no side effects.
        The result strictly bounds what actions the Planner may propose.

        Args:
            intent_envelope: The PO2 IntentEnvelope.

        Returns:
            AllowedActionSet with the eligible ActionClass values.

        Raises:
            ValueError: If intent_envelope is None or has invalid intent_type.
        """
        # Validate input
        if intent_envelope is None:
            raise ValueError("intent_envelope cannot be None")

        intent_type = intent_envelope.intent_type

        if intent_type is None:
            raise ValueError("intent_envelope.intent_type cannot be None")

        # Strict lookup - no fallback
        if intent_type not in INTENT_TO_ACTIONS:
            raise ValueError(
                f"Unknown IntentType: {intent_type.value}. "
                f"INTENT_TO_ACTIONS mapping is incomplete."
            )

        # Get allowed actions for this intent
        allowed_actions = INTENT_TO_ACTIONS[intent_type]

        # Build resolution reason
        resolution_reason = self._build_resolution_reason(intent_type, allowed_actions)

        # Build debug info
        debug = self._build_debug_info(intent_envelope, allowed_actions)

        return AllowedActionSet(
            intent_type=intent_type,
            allowed_actions=allowed_actions,
            run_id=f"p1-{uuid.uuid4().hex[:8]}",
            resolution_reason=resolution_reason,
            debug=debug,
        )

    def _build_resolution_reason(
        self,
        intent_type: IntentType,
        allowed_actions: FrozenSet[ActionClass],
    ) -> str:
        """Build a human-readable resolution reason."""
        if not allowed_actions:
            return f"Intent {intent_type.value} → empty action set (ABSTAIN)"

        action_names = sorted([a.value for a in allowed_actions])
        return (
            f"Intent {intent_type.value} → {len(allowed_actions)} allowed actions: "
            f"{', '.join(action_names)}"
        )

    def _build_debug_info(
        self,
        intent_envelope: IntentEnvelope,
        allowed_actions: FrozenSet[ActionClass],
    ) -> Dict:
        """Build debug information for tracing."""
        return {
            "source_intent": intent_envelope.intent_type.value,
            "source_posture": intent_envelope.response_posture.value,
            "source_planning_allowed": intent_envelope.planning_allowed,
            "action_count": len(allowed_actions),
            "actions": sorted([a.value for a in allowed_actions]),
        }

    def get_actions_for_intent(self, intent_type: IntentType) -> FrozenSet[ActionClass]:
        """
        Get allowed actions for a given intent type.

        Useful for introspection and testing.

        Args:
            intent_type: The IntentType to query.

        Returns:
            FrozenSet of allowed ActionClass values.
        """
        if intent_type not in INTENT_TO_ACTIONS:
            return frozenset()
        return INTENT_TO_ACTIONS[intent_type]

    def is_action_allowed_for_intent(
        self,
        action: ActionClass,
        intent_type: IntentType,
    ) -> bool:
        """
        Check if an action is allowed for a given intent.

        Args:
            action: The ActionClass to check.
            intent_type: The IntentType context.

        Returns:
            True if action is in the allowed set for this intent.
        """
        allowed = self.get_actions_for_intent(intent_type)
        return action in allowed


# Public exports
__all__ = [
    "PhaseOneResolver",
    "INTENT_TO_ACTIONS",
]
