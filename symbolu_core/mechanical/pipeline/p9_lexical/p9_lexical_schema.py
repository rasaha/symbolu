"""
P9 - Lexical Selection Schema Definitions

P9 is a post-semantic, pre-acoustic phase.
It selects the appropriate lexical item (word or short phrase) for each
populated semantic slot, subject to regime, discourse act, and safety constraints.

P9's responsibility is to:
- Select words for each populated semantic slot from deterministic pools
- Produce a read-only LexicalFrame that maps slots to selected words
- Respect regime and discourse act constraints on word selection

P9 does NOT:
- Generate syntax or order words
- Infer missing meaning
- Add or remove semantic slots
- Perform acoustic scoring (that is P10)
- Call LLMs
- Introduce probabilistic behavior
- Hallucinate words

Design Principles:
- Deterministic: No LLM calls, no probabilistic sampling
- Conservative: Choose lowest-impact words under careful regimes
- Authority-Respecting: Cannot override PO1-P8 constraints
- Strict Allow-List: Only words from curated pools may be selected

Authority Model:
- Authority flows: PO1 -> PO2 -> PO3 -> PO4 -> PO5 -> P6 -> P7 -> P8 -> P9 -> (Acoustic layers)
- P9 receives signals from P8 (SemanticFrame), P7 (discourse), P6 (regime)
- P9 cannot override or expand upstream decisions
- P9 produces LexicalFrame for downstream acoustic/prosody generation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Optional

from symbolu_core.mechanical.pipeline.p8_semantics.p8_semantic_schema import SemanticSlot


# ============================================================================
# DATACLASSES - Core envelope objects
# ============================================================================


@dataclass(frozen=True)
class LexicalFrame:
    """
    P9 output envelope: Lexical selection verdict.

    This envelope is read-only and captures the selected lexical items for each
    populated semantic slot. It does NOT perform any syntax construction,
    word ordering, or acoustic modulation.

    Invariants:
    - selections dictionary contains ONLY slots that are present in source SemanticFrame
    - No None values in selections (only populated slots appear)
    - No empty strings allowed
    - Every selection must come from a curated lexical pool

    Attributes:
        selections: Dictionary mapping SemanticSlot to selected lexical string
        allowed: Whether the lexical frame is permitted (False means constrained)
        reason: Human-readable explanation of the selection
        source_discourse_act: The discourse act from P7 (for tracing)
        source_regime: The operational regime from P6 (for tracing)
        architectural_phase: Identifier for this phase ("P9")
        debug: Additional debug/trace information
    """
    selections: Dict[SemanticSlot, str]
    allowed: bool
    reason: str
    source_discourse_act: str  # String value for serialization
    source_regime: str  # String value for serialization
    architectural_phase: str = "P9"

    # Debug/trace information
    debug: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate LexicalFrame invariants."""
        # Reason must be a non-empty string
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError(
                "LexicalFrame.reason must be a non-empty string"
            )

        # Selections must be a dictionary
        if self.selections is None:
            raise ValueError("LexicalFrame.selections cannot be None")

        # Validate all slot keys are valid SemanticSlot enum values
        for slot_key in self.selections:
            if not isinstance(slot_key, SemanticSlot):
                raise ValueError(
                    f"LexicalFrame.selections keys must be SemanticSlot, "
                    f"got {type(slot_key).__name__}"
                )

        # Validate no None values in selections
        for slot_key, value in self.selections.items():
            if value is None:
                raise ValueError(
                    f"LexicalFrame.selections cannot contain None values. "
                    f"Slot {slot_key.value} has None value. "
                    f"Only populated slots should appear in selections."
                )

        # Validate no empty strings
        for slot_key, value in self.selections.items():
            if not isinstance(value, str):
                raise ValueError(
                    f"LexicalFrame.selections values must be strings. "
                    f"Slot {slot_key.value} has type {type(value).__name__}"
                )
            if not value.strip():
                raise ValueError(
                    f"LexicalFrame.selections cannot contain empty strings. "
                    f"Slot {slot_key.value} has empty value."
                )

    def is_empty(self) -> bool:
        """Check if this is an empty lexical frame (no selections)."""
        return len(self.selections) == 0

    def has_slot(self, slot: SemanticSlot) -> bool:
        """Check if a slot has a lexical selection."""
        return slot in self.selections

    def get_selection(self, slot: SemanticSlot) -> Optional[str]:
        """Get the selected lexical item for a slot, or None if not present."""
        return self.selections.get(slot)

    def get_all_selections(self) -> Dict[SemanticSlot, str]:
        """Get all lexical selections as a dictionary."""
        return dict(self.selections)

    def get_selected_slots(self) -> FrozenSet[SemanticSlot]:
        """Get all slots that have lexical selections."""
        return frozenset(self.selections.keys())

    def count(self) -> int:
        """Get the number of lexical selections."""
        return len(self.selections)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            "selections": {k.value: v for k, v in self.selections.items()},
            "allowed": self.allowed,
            "reason": self.reason,
            "source_discourse_act": self.source_discourse_act,
            "source_regime": self.source_regime,
            "architectural_phase": self.architectural_phase,
            "debug": self.debug,
            "selection_count": len(self.selections),
            "is_empty": self.is_empty(),
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def validate_selections_against_semantic_frame(
    selections: Dict[SemanticSlot, str],
    semantic_slots: Dict[SemanticSlot, Optional[str]],
) -> None:
    """
    Validate that selections only contain slots from the source SemanticFrame.

    Args:
        selections: The proposed lexical selections.
        semantic_slots: The slots from the source SemanticFrame.

    Raises:
        ValueError: If selections contains a slot not in semantic_slots.
    """
    for slot in selections:
        if slot not in semantic_slots:
            raise ValueError(
                f"LexicalFrame contains slot {slot.value} which is not present "
                f"in the source SemanticFrame. Only slots from SemanticFrame "
                f"may have lexical selections."
            )


# Public exports
__all__ = [
    # Dataclasses
    "LexicalFrame",
    # Helpers
    "validate_selections_against_semantic_frame",
]
