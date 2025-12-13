"""
P9 - Lexical Selection Resolver

Deterministic resolver that selects lexical items for each populated semantic slot.
No execution, no syntax generation, no word ordering, no side effects.

This is a selection layer that determines what words to use for each meaning.
It produces a read-only LexicalFrame and does NOT execute, plan, or generate syntax.

Authority Model:
- Consumes P8 SemanticFrame, P7 DiscourseEnvelope, P6 RegimeEnvelope
- Cannot override P1-P8 decisions
- Produces LexicalFrame (read-only, non-actuating)
- Constrains downstream acoustic/prosody generation only

Resolution Algorithm (Authoritative, exact order):
1. If regime == HOLD:
   - Return empty LexicalFrame
2. Get populated slots from SemanticFrame
3. For each populated slot:
   a. Get lexical candidates from pool
   b. Filter by regime constraints
   c. Filter by discourse act constraints
   d. Select first (lowest-impact) allowed candidate
   e. If no candidate allowed, omit slot
4. Validate safety constraints
5. Return LexicalFrame

CRITICAL:
- Never invent words outside pools
- Never collapse UNCERTAINTY into certainty
- Never use emotionally amplifying words
- Deterministic: same input -> same output
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from symbolu.mechanical.pipeline.p8_semantics.p8_semantic_schema import (
    SemanticFrame,
    SemanticSlot,
)
from symbolu.mechanical.pipeline.p7_discourse.p7_discourse_schema import (
    DiscourseEnvelope,
    DiscourseAct,
)
from symbolu.mechanical.pipeline.phase_p6.p6_schema import (
    RegimeEnvelope,
    OperationalRegime,
)
from symbolu.mechanical.pipeline.p9_lexical.p9_lexical_schema import (
    LexicalFrame,
    validate_selections_against_semantic_frame,
)
from symbolu.mechanical.pipeline.p9_lexical.p9_lexical_pools import (
    CONSERVATIVE_REGIMES,
    HOLD_BLOCKED_SLOTS,
    NO_INTENSIFICATION_SLOTS,
    select_lexical_item,
    is_word_allowed,
)


class P9LexicalResolver:
    """
    Deterministic lexical selection resolver (non-actuating).

    This resolver implements strict, deterministic rules to select lexical items
    for each populated semantic slot. It does NOT execute any actions, generate
    syntax, or enable any execution pathway.

    CRITICAL: This class is purely evaluative. The lexical frame constrains
    downstream acoustic/prosody generation but does not directly produce output.

    Usage:
        resolver = P9LexicalResolver()
        frame = resolver.resolve(
            semantic_frame=p8_frame,
            discourse_act=p7_act,
            regime=p6_regime,
        )
        # frame.selections contains the lexical selections
    """

    def __init__(self) -> None:
        """Initialize the P9 lexical resolver."""
        pass  # No state needed - purely deterministic

    def resolve(
        self,
        *,
        semantic_frame: SemanticFrame,
        discourse_envelope: DiscourseEnvelope,
        regime_envelope: RegimeEnvelope,
    ) -> LexicalFrame:
        """
        Resolve lexical selections based on deterministic rules.

        This is a pure, deterministic evaluation with no side effects.
        The result is a read-only lexical frame verdict.

        CRITICAL:
        - Never invent words outside pools
        - Never collapse UNCERTAINTY into certainty
        - HOLD regime returns empty LexicalFrame

        Resolution Algorithm (exact order):
        1. If regime == HOLD: Return empty LexicalFrame
        2. Get populated slots from SemanticFrame
        3. For each slot: select lexical item from pool
        4. Validate safety constraints
        5. Return LexicalFrame

        Args:
            semantic_frame: The P8 SemanticFrame (provides semantic slots).
            discourse_envelope: The P7 DiscourseEnvelope (provides discourse act).
            regime_envelope: The P6 RegimeEnvelope (provides operational regime).

        Returns:
            LexicalFrame with lexical selection verdict.

        Raises:
            ValueError: If required inputs are None or invalid.
        """
        # Validate inputs
        if semantic_frame is None:
            raise ValueError("semantic_frame cannot be None")
        if discourse_envelope is None:
            raise ValueError("discourse_envelope cannot be None")
        if regime_envelope is None:
            raise ValueError("regime_envelope cannot be None")

        # Extract values for rule evaluation
        discourse_act = discourse_envelope.act
        regime = regime_envelope.regime

        # Step 1: Handle HOLD regime specially
        if regime == OperationalRegime.HOLD:
            return self._build_hold_frame(
                discourse_act=discourse_act,
                regime=regime,
            )

        # Step 2: Get populated slots from SemanticFrame
        populated_slots = semantic_frame.get_populated_slots()

        # Step 3-4: Select lexical items for each populated slot
        selections, reason = self._select_lexical_items(
            populated_slots=populated_slots,
            discourse_act=discourse_act,
            regime=regime,
            semantic_slots=semantic_frame.slots,
        )

        # Build debug info
        debug = self._build_debug_info(
            semantic_frame=semantic_frame,
            discourse_envelope=discourse_envelope,
            regime_envelope=regime_envelope,
            selections=selections,
        )

        return LexicalFrame(
            selections=selections,
            allowed=True,
            reason=reason,
            source_discourse_act=discourse_act.value,
            source_regime=regime.value,
            debug=debug,
        )

    def _build_hold_frame(
        self,
        discourse_act: DiscourseAct,
        regime: OperationalRegime,
    ) -> LexicalFrame:
        """
        Build an empty LexicalFrame for HOLD regime.

        Under HOLD regime, no lexical selection is permitted.
        This is the most conservative response.

        Args:
            discourse_act: The discourse act from P7.
            regime: The operational regime (should be HOLD).

        Returns:
            Empty LexicalFrame.
        """
        return LexicalFrame(
            selections={},
            allowed=True,
            reason="Lexical HOLD: No lexical selection under HOLD regime",
            source_discourse_act=discourse_act.value,
            source_regime=regime.value,
            debug={
                "hold_reason": "HOLD regime blocks all lexical selection",
            },
        )

    def _select_lexical_items(
        self,
        populated_slots: Dict[SemanticSlot, str],
        discourse_act: DiscourseAct,
        regime: OperationalRegime,
        semantic_slots: Dict[SemanticSlot, Optional[str]],
    ) -> tuple[Dict[SemanticSlot, str], str]:
        """
        Select lexical items for each populated slot.

        Selection Rules:
        - Use deterministic pools only
        - Apply regime constraints
        - Apply discourse act constraints
        - Choose lowest-impact option
        - Omit slot if no candidate allowed

        Args:
            populated_slots: Dictionary of populated semantic slots.
            discourse_act: The discourse act.
            regime: The operational regime.
            semantic_slots: All slots from SemanticFrame (for validation).

        Returns:
            Tuple of (selections dict, reason string).
        """
        selections: Dict[SemanticSlot, str] = {}
        omitted_slots: list[str] = []

        for slot, slot_value in populated_slots.items():
            # Check if slot is blocked under this regime
            if self._is_slot_blocked(slot, regime):
                omitted_slots.append(f"{slot.value}(regime_blocked)")
                continue

            # Select lexical item from pool
            selected = select_lexical_item(
                slot=slot,
                slot_value=slot_value,
                regime=regime,
                discourse_act=discourse_act,
            )

            if selected is None:
                omitted_slots.append(f"{slot.value}(no_allowed_candidate)")
                continue

            # Final safety validation
            if not self._validate_safety(selected, slot):
                omitted_slots.append(f"{slot.value}(safety_blocked)")
                continue

            selections[slot] = selected

        # Validate against semantic frame
        validate_selections_against_semantic_frame(selections, semantic_slots)

        # Build reason
        if omitted_slots:
            reason = (
                f"Lexical {discourse_act.value}: Selected {len(selections)}/{len(populated_slots)} items. "
                f"Omitted: {', '.join(omitted_slots)}"
            )
        else:
            reason = f"Lexical {discourse_act.value}: Selected {len(selections)}/{len(populated_slots)} items"

        return selections, reason

    def _is_slot_blocked(
        self,
        slot: SemanticSlot,
        regime: OperationalRegime,
    ) -> bool:
        """
        Check if a slot is blocked under the given regime.

        Args:
            slot: The SemanticSlot.
            regime: The operational regime.

        Returns:
            True if the slot is blocked, False otherwise.
        """
        # HOLD blocks most slots
        if regime == OperationalRegime.HOLD:
            if slot in HOLD_BLOCKED_SLOTS:
                return True

        # STABILIZE and DE_ESCALATE block CAUSE
        if regime in {OperationalRegime.STABILIZE, OperationalRegime.DE_ESCALATE}:
            if slot == SemanticSlot.CAUSE:
                return True

        return False

    def _validate_safety(
        self,
        word: str,
        slot: SemanticSlot,
    ) -> bool:
        """
        Validate that a word passes safety constraints.

        Safety Rules:
        - UNCERTAINTY slots must never collapse into certainty
        - No emotionally amplifying words
        - LIMITATION slots must soften, not explain

        Args:
            word: The word to validate.
            slot: The SemanticSlot.

        Returns:
            True if the word is safe, False otherwise.
        """
        # UNCERTAINTY must never collapse into certainty
        if slot == SemanticSlot.UNCERTAINTY:
            certainty_words = {
                "definitely", "certainly", "absolutely",
                "clearly", "obviously", "surely",
                "undoubtedly", "unquestionably",
            }
            if word.lower() in certainty_words:
                return False

        # No emotionally amplifying words
        amplifying_words = {
            "extremely", "incredibly", "amazingly",
            "terribly", "horribly", "devastatingly",
            "overwhelmingly", "intensely",
        }
        if word.lower() in amplifying_words:
            return False

        return True

    def _build_debug_info(
        self,
        semantic_frame: SemanticFrame,
        discourse_envelope: DiscourseEnvelope,
        regime_envelope: RegimeEnvelope,
        selections: Dict[SemanticSlot, str],
    ) -> Dict[str, Any]:
        """Build debug information for tracing."""
        return {
            "source_discourse_act": discourse_envelope.act.value,
            "source_regime": regime_envelope.regime.value,
            "semantic_frame_slots": [s.value for s in semantic_frame.slots.keys()],
            "populated_slots": [
                s.value for s, v in semantic_frame.slots.items() if v is not None
            ],
            "selected_slots": [s.value for s in selections.keys()],
            "selection_count": len(selections),
            "is_conservative_regime": regime_envelope.regime in CONSERVATIVE_REGIMES,
        }


# Public exports
__all__ = [
    "P9LexicalResolver",
]
