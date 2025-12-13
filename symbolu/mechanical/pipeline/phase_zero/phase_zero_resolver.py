"""
PO2 — Intent Envelope & Response Posture Resolver
(Implemented as phase_zero for backward compatibility)

The PhaseZeroResolver consumes a PhaseMinusOneEnvelope and produces an IntentEnvelope.
All resolution logic is deterministic, rule-based, with no LLM calls.

PO phases are pre-acoustic governance layers and precede symbolic processing (P1+).

Resolution Rules (in order of precedence):
1. BLOCKED → CLARIFY (no planning)
2. Any clause with selected=None → CLARIFY
3. MULTI_CONTEXT + any RELATIONAL mode → REFLECT
4. Pure REFLEXIVE (all clauses) → SUPPORT
5. Pure DETACHED (all clauses) → INFORM
6. Fallback → ABSTAIN

Authority Model:
- PO2 cannot override PO1 constraints
- PO2 must respect BLOCKED status unconditionally
- Conservative defaults protect against ungrounded analysis
"""

from __future__ import annotations

from typing import List, Optional, Set

from symbolu.mechanical.pipeline.grounding.phase_minus_one_schema import (
    PhaseMinusOneEnvelope,
    ClauseGroundingResult,
    ObservationMode,
    OverallPolicy,
)

from .phase_zero_schema import (
    IntentType,
    ResponsePosture,
    IntentEnvelope,
    INTENT_TO_POSTURE,
)


class PhaseZeroResolver:
    """
    Deterministic resolver for PO2 intent classification.

    Takes PO1 grounding envelope and produces PO2 intent envelope.
    All resolution is rule-based with no probabilistic logic.

    Usage:
        resolver = PhaseZeroResolver()
        intent_envelope = resolver.resolve(phase_minus_one_envelope)
    """

    def resolve(self, envelope: PhaseMinusOneEnvelope) -> IntentEnvelope:
        """
        Resolve PO1 envelope to PO2 intent envelope.

        Args:
            envelope: PhaseMinusOneEnvelope from PO1 analysis.

        Returns:
            IntentEnvelope with determined intent type and response posture.
        """
        # Extract mode signals from all clauses for diagnostics
        mode_signals = self._extract_mode_signals(envelope.clauses)

        # Rule 1: BLOCKED → CLARIFY (no planning)
        if envelope.is_blocked():
            return self._make_envelope(
                intent_type=IntentType.CLARIFY,
                planning_allowed=False,
                phase_minus_one_policy=envelope.overall_policy,
                mode_signals=mode_signals,
                reason="PO1 BLOCKED: clarification required before proceeding",
            )

        # Rule 2: Any clause with selected=None → CLARIFY
        if self._has_unresolved_clause(envelope.clauses):
            return self._make_envelope(
                intent_type=IntentType.CLARIFY,
                planning_allowed=False,
                phase_minus_one_policy=envelope.overall_policy,
                mode_signals=mode_signals,
                reason="Unresolved clause grounding: clarification required",
            )

        # Rule 3: MULTI_CONTEXT + any RELATIONAL → REFLECT
        if envelope.has_multi_context() and self._has_relational_mode(envelope.clauses):
            return self._make_envelope(
                intent_type=IntentType.REFLECT,
                planning_allowed=True,
                phase_minus_one_policy=envelope.overall_policy,
                mode_signals=mode_signals,
                reason="Multi-context with relational signals: reflective engagement",
            )

        # Rule 4: Pure REFLEXIVE → SUPPORT
        if self._is_pure_mode(envelope.clauses, ObservationMode.REFLEXIVE):
            return self._make_envelope(
                intent_type=IntentType.SUPPORT,
                planning_allowed=True,
                phase_minus_one_policy=envelope.overall_policy,
                mode_signals=mode_signals,
                reason="Pure reflexive mode: supportive acknowledgment",
            )

        # Rule 5: Pure DETACHED → INFORM
        if self._is_pure_mode(envelope.clauses, ObservationMode.DETACHED):
            return self._make_envelope(
                intent_type=IntentType.INFORM,
                planning_allowed=True,
                phase_minus_one_policy=envelope.overall_policy,
                mode_signals=mode_signals,
                reason="Pure detached mode: informative engagement",
            )

        # Rule 6: Fallback → ABSTAIN
        return self._make_envelope(
            intent_type=IntentType.ABSTAIN,
            planning_allowed=False,
            phase_minus_one_policy=envelope.overall_policy,
            mode_signals=mode_signals,
            reason="No clear intent pattern matched: conservative abstention",
        )

    def _extract_mode_signals(
        self, clauses: List[ClauseGroundingResult]
    ) -> List[ObservationMode]:
        """
        Extract observation modes from all clauses.

        Args:
            clauses: List of clause grounding results.

        Returns:
            List of ObservationMode values from selected groundings.
        """
        modes: List[ObservationMode] = []
        for clause in clauses:
            if clause.selected is not None:
                modes.append(clause.selected.mode)
        return modes

    def _has_unresolved_clause(self, clauses: List[ClauseGroundingResult]) -> bool:
        """
        Check if any clause has unresolved grounding (selected=None).

        Args:
            clauses: List of clause grounding results.

        Returns:
            True if any clause has selected=None.
        """
        for clause in clauses:
            if clause.selected is None:
                return True
        return False

    def _has_relational_mode(self, clauses: List[ClauseGroundingResult]) -> bool:
        """
        Check if any clause has RELATIONAL observation mode.

        Args:
            clauses: List of clause grounding results.

        Returns:
            True if any clause has mode=RELATIONAL.
        """
        for clause in clauses:
            if clause.selected is not None:
                if clause.selected.mode == ObservationMode.RELATIONAL:
                    return True
        return False

    def _is_pure_mode(
        self, clauses: List[ClauseGroundingResult], target_mode: ObservationMode
    ) -> bool:
        """
        Check if all clauses have the same observation mode.

        Args:
            clauses: List of clause grounding results.
            target_mode: The mode to check for.

        Returns:
            True if all clauses with selected grounding have target_mode.
        """
        if not clauses:
            return False

        modes: Set[ObservationMode] = set()
        for clause in clauses:
            if clause.selected is not None:
                modes.add(clause.selected.mode)

        # Must have at least one mode and all must match target
        return len(modes) == 1 and target_mode in modes

    def _make_envelope(
        self,
        intent_type: IntentType,
        planning_allowed: bool,
        phase_minus_one_policy: OverallPolicy,
        mode_signals: List[ObservationMode],
        reason: str,
    ) -> IntentEnvelope:
        """
        Construct an IntentEnvelope with deterministic posture mapping.

        Args:
            intent_type: The resolved intent type.
            planning_allowed: Whether planning may proceed.
            phase_minus_one_policy: The upstream PO1 policy.
            mode_signals: Observation modes from input clauses.
            reason: Human-readable resolution explanation.

        Returns:
            Fully constructed IntentEnvelope.
        """
        response_posture = INTENT_TO_POSTURE[intent_type]

        return IntentEnvelope(
            intent_type=intent_type,
            response_posture=response_posture,
            planning_allowed=planning_allowed,
            phase_minus_one_policy=phase_minus_one_policy,
            mode_signals=mode_signals,
            resolution_reason=reason,
            debug={
                "rule_applied": intent_type.value,
                "mode_count": len(mode_signals),
                "unique_modes": list({m.value for m in mode_signals}),
            },
        )


# Public exports
__all__ = ["PhaseZeroResolver"]
