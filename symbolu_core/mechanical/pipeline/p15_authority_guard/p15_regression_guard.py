"""
P15 Regression Guard — Core Guard Logic

Implements the P15RegressionGuard class with:
- capture(): Captures immutable authority snapshot from PipelineContext
- validate(): Validates current context against snapshot, returns violations

HARD INVARIANTS (for any phase ≥ 16):
- intent MUST NOT change
- regime MUST NOT change
- discourse_act MUST NOT change
- response_posture MUST NOT change
- interaction_mode MUST NOT change
- allowed_actions MUST NOT expand (may only shrink or stay same)
- blocked=True MUST remain blocked (cannot transition to unblocked)
- No explanation, certainty, or authority flags may appear
- Grammar, prediction, or temporal signals are NOT valid justification

Violations are COLLECTED, not silently corrected.
This guard exists to STOP the system, not to FIX it.

Design Principles:
- Deterministic: Same input → same violations
- No hidden state
- No LLM usage
- No heuristics
- No learning
- No auto-correction
"""

from __future__ import annotations

from typing import Any, List, Optional

from symbolu_core.mechanical.pipeline.p15_authority_guard.p15_regression_schema import (
    P15AuthoritySnapshot,
    P15RegressionViolation,
    ViolationType,
)


class P15RegressionGuard:
    """
    Guard that enforces P15 authority preservation.

    This class provides two core operations:
    1. capture() - Capture an immutable snapshot of authority decisions
    2. validate() - Validate current context against the snapshot

    The guard is STATELESS. It does not store the snapshot internally.
    The snapshot is stored on the PipelineContext by the integration layer.

    Usage:
        guard = P15RegressionGuard()
        snapshot = guard.capture(ctx)  # After P15 completes
        violations = guard.validate(snapshot, ctx, phase=16)  # At start of P16+
        if violations:
            raise P15RegressionViolationError(violations, phase=16)
    """

    # Minimum phase number for guard activation
    GUARD_ACTIVE_FROM_PHASE = 16

    def capture(self, ctx: Any) -> P15AuthoritySnapshot:
        """
        Capture an immutable P15 authority snapshot from the pipeline context.

        This method extracts all authority-bearing decisions from PO1–P15
        and freezes them into an immutable snapshot.

        Args:
            ctx: The PipelineContext after P15 has completed

        Returns:
            P15AuthoritySnapshot: Immutable snapshot of all authority decisions

        Raises:
            ValueError: If required context fields are missing
        """
        # Extract intent from PO2 (phase_zero)
        intent = self._extract_intent(ctx)

        # Extract regime from P6
        regime = self._extract_regime(ctx)

        # Extract discourse_act from P7
        discourse_act = self._extract_discourse_act(ctx)

        # Extract response_posture from PO2 (phase_zero)
        response_posture = self._extract_response_posture(ctx)

        # Extract interaction_mode from P15
        interaction_mode = self._extract_interaction_mode(ctx)

        # Extract allowed_actions from PO3 (phase_one / allowed_actions)
        allowed_actions = self._extract_allowed_actions(ctx)

        # Extract blocked state
        blocked = self._extract_blocked_state(ctx)

        # Extract grounding mode from PO1
        grounding_mode = self._extract_grounding_mode(ctx)

        return P15AuthoritySnapshot(
            intent=intent,
            regime=regime,
            discourse_act=discourse_act,
            response_posture=response_posture,
            interaction_mode=interaction_mode,
            allowed_actions=allowed_actions,
            blocked=blocked,
            grounding_mode=grounding_mode,
        )

    def validate(
        self,
        snapshot: P15AuthoritySnapshot,
        current_ctx: Any,
        current_phase: int,
    ) -> List[P15RegressionViolation]:
        """
        Validate the current context against the P15 snapshot.

        This method checks ALL authority-bearing fields and collects
        ALL violations. It does NOT stop at the first violation.

        CRITICAL: This method should only be called for phases >= 16.
        For phases < 16, it returns an empty list (guard inactive).

        Args:
            snapshot: The P15AuthoritySnapshot captured after P15
            current_ctx: The current PipelineContext
            current_phase: The phase number being validated (must be >= 16)

        Returns:
            List[P15RegressionViolation]: All detected violations (may be empty)
        """
        # Guard is inactive for phases < 16
        if current_phase < self.GUARD_ACTIVE_FROM_PHASE:
            return []

        violations: List[P15RegressionViolation] = []

        # Check intent (MUST NOT change)
        self._check_intent(snapshot, current_ctx, current_phase, violations)

        # Check regime (MUST NOT change)
        self._check_regime(snapshot, current_ctx, current_phase, violations)

        # Check discourse_act (MUST NOT change)
        self._check_discourse_act(snapshot, current_ctx, current_phase, violations)

        # Check response_posture (MUST NOT change)
        self._check_response_posture(snapshot, current_ctx, current_phase, violations)

        # Check interaction_mode (MUST NOT change)
        self._check_interaction_mode(snapshot, current_ctx, current_phase, violations)

        # Check allowed_actions (MUST NOT expand)
        self._check_allowed_actions(snapshot, current_ctx, current_phase, violations)

        # Check blocked state (MUST NOT unblock)
        self._check_blocked_state(snapshot, current_ctx, current_phase, violations)

        # Check for authority reintroduction signals
        self._check_authority_reintroduction(
            snapshot, current_ctx, current_phase, violations
        )

        return violations

    # =========================================================================
    # EXTRACTION METHODS
    # =========================================================================

    def _extract_intent(self, ctx: Any) -> str:
        """Extract intent type from PO2 (phase_zero)."""
        phase_zero = getattr(ctx, "phase_zero", None)
        if phase_zero is None:
            raise ValueError(
                "P15RegressionGuard.capture: ctx.phase_zero is None. "
                "PO2 must complete before P15 snapshot can be captured."
            )

        intent_type = getattr(phase_zero, "intent_type", None)
        if intent_type is None:
            raise ValueError(
                "P15RegressionGuard.capture: phase_zero.intent_type is None"
            )

        # Handle both enum and string
        if hasattr(intent_type, "value"):
            return intent_type.value
        return str(intent_type)

    def _extract_regime(self, ctx: Any) -> str:
        """Extract operational regime from P6."""
        p6_regime = getattr(ctx, "p6_regime", None)
        if p6_regime is None:
            raise ValueError(
                "P15RegressionGuard.capture: ctx.p6_regime is None. "
                "P6 must complete before P15 snapshot can be captured."
            )

        regime = getattr(p6_regime, "regime", None)
        if regime is None:
            raise ValueError(
                "P15RegressionGuard.capture: p6_regime.regime is None"
            )

        # Handle both enum and string
        if hasattr(regime, "value"):
            return regime.value
        return str(regime)

    def _extract_discourse_act(self, ctx: Any) -> str:
        """Extract discourse act from P7."""
        p7_discourse = getattr(ctx, "p7_discourse_envelope", None)
        if p7_discourse is None:
            raise ValueError(
                "P15RegressionGuard.capture: ctx.p7_discourse_envelope is None. "
                "P7 must complete before P15 snapshot can be captured."
            )

        act = getattr(p7_discourse, "act", None)
        if act is None:
            raise ValueError(
                "P15RegressionGuard.capture: p7_discourse_envelope.act is None"
            )

        # Handle both enum and string
        if hasattr(act, "value"):
            return act.value
        return str(act)

    def _extract_response_posture(self, ctx: Any) -> str:
        """Extract response posture from PO2 (phase_zero)."""
        phase_zero = getattr(ctx, "phase_zero", None)
        if phase_zero is None:
            raise ValueError(
                "P15RegressionGuard.capture: ctx.phase_zero is None"
            )

        posture = getattr(phase_zero, "response_posture", None)
        if posture is None:
            raise ValueError(
                "P15RegressionGuard.capture: phase_zero.response_posture is None"
            )

        # Handle both enum and string
        if hasattr(posture, "value"):
            return posture.value
        return str(posture)

    def _extract_interaction_mode(self, ctx: Any) -> str:
        """Extract interaction mode from P15."""
        interaction_directive = getattr(ctx, "interaction_directive", None)
        if interaction_directive is None:
            raise ValueError(
                "P15RegressionGuard.capture: ctx.interaction_directive is None. "
                "P15 must complete before snapshot can be captured."
            )

        mode = getattr(interaction_directive, "mode", None)
        if mode is None:
            raise ValueError(
                "P15RegressionGuard.capture: interaction_directive.mode is None"
            )

        # Handle both enum and string
        if hasattr(mode, "value"):
            return mode.value
        return str(mode)

    def _extract_allowed_actions(self, ctx: Any) -> frozenset:
        """Extract allowed actions from PO3."""
        allowed_actions = getattr(ctx, "allowed_actions", None)
        if allowed_actions is None:
            # Allowed actions may be empty/None for blocked states
            return frozenset()

        actions_set = getattr(allowed_actions, "allowed_actions", None)
        if actions_set is None:
            return frozenset()

        # Convert to frozenset of strings
        result = set()
        for action in actions_set:
            if hasattr(action, "value"):
                result.add(action.value)
            else:
                result.add(str(action))

        return frozenset(result)

    def _extract_blocked_state(self, ctx: Any) -> bool:
        """Extract blocked state from context."""
        # Check interaction_directive.blocked first (most authoritative for P15)
        interaction_directive = getattr(ctx, "interaction_directive", None)
        if interaction_directive is not None:
            blocked = getattr(interaction_directive, "blocked", None)
            if blocked is not None:
                return bool(blocked)

        # Check phase_minus_one (PO1) for overall policy BLOCKED
        phase_minus_one = getattr(ctx, "phase_minus_one", None)
        if phase_minus_one is not None:
            overall_policy = getattr(phase_minus_one, "overall_policy", None)
            if overall_policy is not None:
                if hasattr(overall_policy, "value"):
                    return overall_policy.value == "BLOCKED"
                return str(overall_policy) == "BLOCKED"

        # Check for is_blocked method on context
        if hasattr(ctx, "is_blocked") and callable(ctx.is_blocked):
            return bool(ctx.is_blocked())

        return False

    def _extract_grounding_mode(self, ctx: Any) -> str:
        """Extract grounding mode from PO1."""
        phase_minus_one = getattr(ctx, "phase_minus_one", None)
        if phase_minus_one is None:
            return ""

        # Try to get dominant mode
        dominant_mode = getattr(phase_minus_one, "dominant_mode", None)
        if dominant_mode is not None:
            if hasattr(dominant_mode, "value"):
                return dominant_mode.value
            return str(dominant_mode)

        return ""

    # =========================================================================
    # VALIDATION METHODS
    # =========================================================================

    def _check_intent(
        self,
        snapshot: P15AuthoritySnapshot,
        ctx: Any,
        phase: int,
        violations: List[P15RegressionViolation],
    ) -> None:
        """Check that intent has not changed."""
        try:
            current_intent = self._extract_intent(ctx)
        except ValueError:
            # If we can't extract, assume violation (missing data)
            violations.append(
                P15RegressionViolation(
                    phase=phase,
                    field="intent",
                    expected=snapshot.intent,
                    observed="<extraction_failed>",
                    violation_type=ViolationType.INTENT_OVERRIDE,
                    reason="Failed to extract intent from context",
                )
            )
            return

        if current_intent != snapshot.intent:
            violations.append(
                P15RegressionViolation(
                    phase=phase,
                    field="intent",
                    expected=snapshot.intent,
                    observed=current_intent,
                    violation_type=ViolationType.INTENT_OVERRIDE,
                    reason="Intent was modified after P15",
                )
            )

    def _check_regime(
        self,
        snapshot: P15AuthoritySnapshot,
        ctx: Any,
        phase: int,
        violations: List[P15RegressionViolation],
    ) -> None:
        """Check that regime has not changed."""
        try:
            current_regime = self._extract_regime(ctx)
        except ValueError:
            violations.append(
                P15RegressionViolation(
                    phase=phase,
                    field="regime",
                    expected=snapshot.regime,
                    observed="<extraction_failed>",
                    violation_type=ViolationType.REGIME_ESCALATION,
                    reason="Failed to extract regime from context",
                )
            )
            return

        if current_regime != snapshot.regime:
            violations.append(
                P15RegressionViolation(
                    phase=phase,
                    field="regime",
                    expected=snapshot.regime,
                    observed=current_regime,
                    violation_type=ViolationType.REGIME_ESCALATION,
                    reason="Regime was modified after P15",
                )
            )

    def _check_discourse_act(
        self,
        snapshot: P15AuthoritySnapshot,
        ctx: Any,
        phase: int,
        violations: List[P15RegressionViolation],
    ) -> None:
        """Check that discourse_act has not changed."""
        try:
            current_act = self._extract_discourse_act(ctx)
        except ValueError:
            violations.append(
                P15RegressionViolation(
                    phase=phase,
                    field="discourse_act",
                    expected=snapshot.discourse_act,
                    observed="<extraction_failed>",
                    violation_type=ViolationType.DISCOURSE_MUTATION,
                    reason="Failed to extract discourse_act from context",
                )
            )
            return

        if current_act != snapshot.discourse_act:
            violations.append(
                P15RegressionViolation(
                    phase=phase,
                    field="discourse_act",
                    expected=snapshot.discourse_act,
                    observed=current_act,
                    violation_type=ViolationType.DISCOURSE_MUTATION,
                    reason="Discourse act was modified after P15",
                )
            )

    def _check_response_posture(
        self,
        snapshot: P15AuthoritySnapshot,
        ctx: Any,
        phase: int,
        violations: List[P15RegressionViolation],
    ) -> None:
        """Check that response_posture has not changed."""
        try:
            current_posture = self._extract_response_posture(ctx)
        except ValueError:
            violations.append(
                P15RegressionViolation(
                    phase=phase,
                    field="response_posture",
                    expected=snapshot.response_posture,
                    observed="<extraction_failed>",
                    violation_type=ViolationType.POSTURE_MUTATION,
                    reason="Failed to extract response_posture from context",
                )
            )
            return

        if current_posture != snapshot.response_posture:
            violations.append(
                P15RegressionViolation(
                    phase=phase,
                    field="response_posture",
                    expected=snapshot.response_posture,
                    observed=current_posture,
                    violation_type=ViolationType.POSTURE_MUTATION,
                    reason="Response posture was modified after P15",
                )
            )

    def _check_interaction_mode(
        self,
        snapshot: P15AuthoritySnapshot,
        ctx: Any,
        phase: int,
        violations: List[P15RegressionViolation],
    ) -> None:
        """Check that interaction_mode has not changed."""
        try:
            current_mode = self._extract_interaction_mode(ctx)
        except ValueError:
            violations.append(
                P15RegressionViolation(
                    phase=phase,
                    field="interaction_mode",
                    expected=snapshot.interaction_mode,
                    observed="<extraction_failed>",
                    violation_type=ViolationType.AUTHORITY_REINTRODUCTION,
                    reason="Failed to extract interaction_mode from context",
                )
            )
            return

        if current_mode != snapshot.interaction_mode:
            violations.append(
                P15RegressionViolation(
                    phase=phase,
                    field="interaction_mode",
                    expected=snapshot.interaction_mode,
                    observed=current_mode,
                    violation_type=ViolationType.AUTHORITY_REINTRODUCTION,
                    reason="Interaction mode was modified after P15",
                )
            )

    def _check_allowed_actions(
        self,
        snapshot: P15AuthoritySnapshot,
        ctx: Any,
        phase: int,
        violations: List[P15RegressionViolation],
    ) -> None:
        """
        Check that allowed_actions has not EXPANDED.

        Note: Actions may be REDUCED (more restrictive) without violation.
        Only EXPANSION (adding new actions) is a violation.
        """
        current_actions = self._extract_allowed_actions(ctx)

        # Check for expansion: any action in current that was not in snapshot
        expanded_actions = current_actions - snapshot.allowed_actions

        if expanded_actions:
            violations.append(
                P15RegressionViolation(
                    phase=phase,
                    field="allowed_actions",
                    expected=snapshot.allowed_actions,
                    observed=current_actions,
                    violation_type=ViolationType.ACTION_EXPANSION,
                    reason=f"Allowed actions were expanded: {sorted(expanded_actions)}",
                )
            )

    def _check_blocked_state(
        self,
        snapshot: P15AuthoritySnapshot,
        ctx: Any,
        phase: int,
        violations: List[P15RegressionViolation],
    ) -> None:
        """
        Check that blocked state has not been unblocked.

        CRITICAL: blocked=True MUST remain blocked.
        A blocked state cannot transition to unblocked.
        """
        if not snapshot.blocked:
            # If snapshot was not blocked, no violation possible
            return

        current_blocked = self._extract_blocked_state(ctx)

        if not current_blocked:
            violations.append(
                P15RegressionViolation(
                    phase=phase,
                    field="blocked",
                    expected=True,
                    observed=False,
                    violation_type=ViolationType.BLOCKED_UNBLOCK,
                    reason="Blocked state was illegally unblocked",
                )
            )

    def _check_authority_reintroduction(
        self,
        snapshot: P15AuthoritySnapshot,
        ctx: Any,
        phase: int,
        violations: List[P15RegressionViolation],
    ) -> None:
        """
        Check for unauthorized authority signal reintroduction.

        This checks for fields that should NOT exist or should NOT
        have certain values in phases >= 16. These include:
        - certainty flags
        - explanation injection
        - prediction-based overrides
        - persona-based authority
        """
        # Check for certainty/confidence injection
        certainty = getattr(ctx, "authority_certainty", None)
        if certainty is not None:
            violations.append(
                P15RegressionViolation(
                    phase=phase,
                    field="authority_certainty",
                    expected=None,
                    observed=certainty,
                    violation_type=ViolationType.AUTHORITY_REINTRODUCTION,
                    reason="Authority certainty signal introduced after P15",
                )
            )

        # Check for explanation injection (phases >= 16 should not add explanations)
        authority_explanation = getattr(ctx, "authority_explanation", None)
        if authority_explanation is not None:
            violations.append(
                P15RegressionViolation(
                    phase=phase,
                    field="authority_explanation",
                    expected=None,
                    observed=authority_explanation,
                    violation_type=ViolationType.AUTHORITY_REINTRODUCTION,
                    reason="Authority explanation signal introduced after P15",
                )
            )

        # Check for prediction-based override flags
        prediction_override = getattr(ctx, "prediction_override", None)
        if prediction_override is not None:
            violations.append(
                P15RegressionViolation(
                    phase=phase,
                    field="prediction_override",
                    expected=None,
                    observed=prediction_override,
                    violation_type=ViolationType.AUTHORITY_REINTRODUCTION,
                    reason="Prediction-based override attempted after P15",
                )
            )

        # Check for persona-based authority injection
        persona_authority = getattr(ctx, "persona_authority_override", None)
        if persona_authority is not None:
            violations.append(
                P15RegressionViolation(
                    phase=phase,
                    field="persona_authority_override",
                    expected=None,
                    observed=persona_authority,
                    violation_type=ViolationType.AUTHORITY_REINTRODUCTION,
                    reason="Persona-based authority override attempted after P15",
                )
            )

        # Check for temporal/grammar-based authority injection
        grammar_authority = getattr(ctx, "grammar_authority_override", None)
        if grammar_authority is not None:
            violations.append(
                P15RegressionViolation(
                    phase=phase,
                    field="grammar_authority_override",
                    expected=None,
                    observed=grammar_authority,
                    violation_type=ViolationType.AUTHORITY_REINTRODUCTION,
                    reason="Grammar-based authority override attempted after P15",
                )
            )


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================


__all__ = ["P15RegressionGuard"]
