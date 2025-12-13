"""
P9 - Lexical Selection Pools

Deterministic synonym pools per SemanticSlot.
All pools are:
- Finite
- Explicit
- Hand-curated
- No dynamic generation

These pools are used by P9LexicalResolver to select appropriate lexical items
for each populated semantic slot, subject to regime and discourse constraints.

CRITICAL: No LLM calls, no NLP libraries, no probabilistic selection.
All selections are deterministic and from these curated pools only.

Architectural Notes:
- P9 is the first word-touching phase
- P9 decides which word, not how it sounds
- P10 will handle acoustic modulation separately
- Authority flows downward; P9 is subordinate to P1-P8
"""

from __future__ import annotations

from typing import Dict, FrozenSet, List, Tuple

from symbolu.mechanical.pipeline.p8_semantics.p8_semantic_schema import SemanticSlot
from symbolu.mechanical.pipeline.p7_discourse.p7_discourse_schema import DiscourseAct
from symbolu.mechanical.pipeline.phase_p6.p6_schema import OperationalRegime


# ============================================================================
# LEXICAL POOLS PER SEMANTIC SLOT
# Each pool is ordered by "impact level" (lowest impact first)
# Under CAREFUL/STABILIZE/DE_ESCALATE regimes, lower-impact options are preferred
# ============================================================================


# AGENT lexical options
# Maps semantic agent values to lexical realizations
AGENT_POOL: Dict[str, Tuple[str, ...]] = {
    "user_self": ("you", "yourself"),
    "other_entity": ("they", "them", "that person"),
    "phenomenon": ("it", "this", "that"),
    # Default for unknown agent values
    "_default": ("it",),
}

# TARGET lexical options
TARGET_POOL: Dict[str, Tuple[str, ...]] = {
    "relational_target": ("them", "that", "it"),
    # Default for unknown target values
    "_default": ("that",),
}

# STATE lexical options
# Ordered by intensity: lowest impact first
STATE_POOL: Dict[str, Tuple[str, ...]] = {
    "reflexive_state": ("present", "here", "aware"),
    "relational_state": ("connected", "in relation", "involved"),
    "detached_state": ("observed", "noted", "apparent"),
    # Default for unknown state values
    "_default": ("present",),
}

# UNCERTAINTY lexical options
# These must NEVER collapse into certainty
UNCERTAINTY_POOL: Dict[str, Tuple[str, ...]] = {
    "low_confidence": ("seems", "appears", "might be", "may be"),
    "moderate_confidence": ("seems", "appears", "likely"),
    "hedged": ("perhaps", "possibly", "maybe"),
    # Default preserves uncertainty
    "_default": ("seems", "appears"),
}

# LIMITATION lexical options
# Must soften, not explain
LIMITATION_POOL: Dict[str, Tuple[str, ...]] = {
    "hold_regime": ("pausing", "holding", "waiting"),
    "abstain_intent": ("unable to", "cannot", "not able to"),
    "blocked_grounding": ("unclear", "uncertain", "not sure"),
    "high_projection_risk": ("uncertain", "unclear", "not able to determine"),
    # Default softens
    "_default": ("limited", "constrained"),
}

# CAUSE lexical options (restricted under conservative regimes)
CAUSE_POOL: Dict[str, Tuple[str, ...]] = {
    "causal_relation": ("because", "since", "as"),
    "grounding_causal": ("due to", "given", "considering"),
    "because_clause": ("because", "since"),
    # Default
    "_default": ("because",),
}

# TEMPORAL_CONTEXT lexical options
TEMPORAL_CONTEXT_POOL: Dict[str, Tuple[str, ...]] = {
    "past": ("before", "previously", "earlier"),
    "present": ("now", "currently", "at this time"),
    "future": ("soon", "later", "afterward"),
    "ongoing": ("continuing", "still", "ongoing"),
    # Default
    "_default": ("now",),
}

# REQUEST_FOCUS lexical options (for questions)
REQUEST_FOCUS_POOL: Dict[str, Tuple[str, ...]] = {
    "clarification_needed": ("what", "which", "how"),
    "information": ("what", "which"),
    "confirmation": ("whether", "if"),
    "explanation": ("why", "how"),
    # Default
    "_default": ("what",),
}

# CONSTRAINT lexical options
CONSTRAINT_POOL: Dict[str, Tuple[str, ...]] = {
    "analysis_restricted": ("limited", "restricted", "constrained"),
    "boundary": ("within", "bounded by", "limited to"),
    # Default
    "_default": ("within",),
}


# ============================================================================
# COMBINED POOL REGISTRY
# ============================================================================


LEXICAL_POOLS: Dict[SemanticSlot, Dict[str, Tuple[str, ...]]] = {
    SemanticSlot.AGENT: AGENT_POOL,
    SemanticSlot.TARGET: TARGET_POOL,
    SemanticSlot.STATE: STATE_POOL,
    SemanticSlot.UNCERTAINTY: UNCERTAINTY_POOL,
    SemanticSlot.LIMITATION: LIMITATION_POOL,
    SemanticSlot.CAUSE: CAUSE_POOL,
    SemanticSlot.TEMPORAL_CONTEXT: TEMPORAL_CONTEXT_POOL,
    SemanticSlot.REQUEST_FOCUS: REQUEST_FOCUS_POOL,
    SemanticSlot.CONSTRAINT: CONSTRAINT_POOL,
}


# ============================================================================
# REGIME CONSTRAINTS
# Under these regimes, only the lowest-impact (first) option is allowed
# ============================================================================


CONSERVATIVE_REGIMES: FrozenSet[OperationalRegime] = frozenset({
    OperationalRegime.HOLD,
    OperationalRegime.STABILIZE,
    OperationalRegime.DE_ESCALATE,
})


# Slots that are completely blocked under HOLD regime
HOLD_BLOCKED_SLOTS: FrozenSet[SemanticSlot] = frozenset({
    SemanticSlot.CAUSE,
    SemanticSlot.STATE,
    SemanticSlot.AGENT,
    SemanticSlot.TARGET,
})


# Slots where intensification is never allowed
NO_INTENSIFICATION_SLOTS: FrozenSet[SemanticSlot] = frozenset({
    SemanticSlot.UNCERTAINTY,
    SemanticSlot.LIMITATION,
})


# ============================================================================
# DISCOURSE ACT CONSTRAINTS
# Specific lexical restrictions per discourse act
# ============================================================================


# For REFLECTION: must mirror, no intensification
REFLECTION_CONSTRAINTS: Dict[SemanticSlot, FrozenSet[str]] = {
    # UNCERTAINTY must use mirroring language
    SemanticSlot.UNCERTAINTY: frozenset({"seems", "appears"}),
    # STATE must use reflective language
    SemanticSlot.STATE: frozenset({"present", "here", "aware"}),
}


# For QUESTION: no certainty-asserting words
QUESTION_BLOCKED_WORDS: FrozenSet[str] = frozenset({
    "definitely",
    "certainly",
    "absolutely",
    "clearly",
    "obviously",
    "surely",
})


# For EXPLANATION: neutral, descriptive vocabulary only
EXPLANATION_PREFERRED_WORDS: Dict[SemanticSlot, FrozenSet[str]] = {
    SemanticSlot.CAUSE: frozenset({"because", "since", "as", "due to", "given"}),
    SemanticSlot.STATE: frozenset({"observed", "noted", "apparent"}),
}


# ============================================================================
# SAFETY CONSTRAINTS
# Critical safety rules for lexical selection
# ============================================================================


# Words that are emotionally amplifying (never allowed unless explicitly permitted)
EMOTIONALLY_AMPLIFYING_WORDS: FrozenSet[str] = frozenset({
    "extremely",
    "incredibly",
    "amazingly",
    "terribly",
    "horribly",
    "devastatingly",
    "overwhelmingly",
    "intensely",
})


# Certainty words that must never appear in UNCERTAINTY slots
CERTAINTY_WORDS: FrozenSet[str] = frozenset({
    "definitely",
    "certainly",
    "absolutely",
    "clearly",
    "obviously",
    "surely",
    "undoubtedly",
    "unquestionably",
})


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_pool_for_slot(slot: SemanticSlot) -> Dict[str, Tuple[str, ...]]:
    """
    Get the lexical pool for a given semantic slot.

    Args:
        slot: The SemanticSlot to get the pool for.

    Returns:
        The lexical pool dictionary mapping slot values to word options.
    """
    return LEXICAL_POOLS.get(slot, {"_default": ("",)})


def get_candidates_for_value(
    slot: SemanticSlot,
    slot_value: str,
) -> Tuple[str, ...]:
    """
    Get the lexical candidates for a specific slot value.

    Args:
        slot: The SemanticSlot.
        slot_value: The semantic value to get candidates for.

    Returns:
        Tuple of lexical candidates, ordered by impact (lowest first).
    """
    pool = get_pool_for_slot(slot)
    candidates = pool.get(slot_value)
    if candidates is None:
        candidates = pool.get("_default", ())
    return candidates


def is_word_allowed(
    word: str,
    slot: SemanticSlot,
    regime: OperationalRegime,
    discourse_act: DiscourseAct,
) -> bool:
    """
    Check if a word is allowed given regime and discourse constraints.

    Args:
        word: The word to check.
        slot: The SemanticSlot the word is for.
        regime: The operational regime.
        discourse_act: The discourse act.

    Returns:
        True if the word is allowed, False otherwise.
    """
    # Safety: emotionally amplifying words are never allowed
    if word.lower() in EMOTIONALLY_AMPLIFYING_WORDS:
        return False

    # Safety: UNCERTAINTY slots must never have certainty words
    if slot == SemanticSlot.UNCERTAINTY:
        if word.lower() in CERTAINTY_WORDS:
            return False

    # Discourse constraint: QUESTION cannot have certainty-asserting words
    if discourse_act == DiscourseAct.QUESTION:
        if word.lower() in QUESTION_BLOCKED_WORDS:
            return False

    # Discourse constraint: REFLECTION has specific allowed words
    if discourse_act == DiscourseAct.REFLECTION:
        if slot in REFLECTION_CONSTRAINTS:
            allowed_words = REFLECTION_CONSTRAINTS[slot]
            if word.lower() not in allowed_words:
                return False

    return True


def get_allowed_candidates(
    slot: SemanticSlot,
    slot_value: str,
    regime: OperationalRegime,
    discourse_act: DiscourseAct,
) -> List[str]:
    """
    Get the allowed lexical candidates for a slot value given constraints.

    Args:
        slot: The SemanticSlot.
        slot_value: The semantic value.
        regime: The operational regime.
        discourse_act: The discourse act.

    Returns:
        List of allowed lexical candidates, ordered by impact (lowest first).
    """
    candidates = get_candidates_for_value(slot, slot_value)
    allowed = []

    for candidate in candidates:
        if is_word_allowed(candidate, slot, regime, discourse_act):
            allowed.append(candidate)

    return allowed


def select_lexical_item(
    slot: SemanticSlot,
    slot_value: str,
    regime: OperationalRegime,
    discourse_act: DiscourseAct,
) -> str | None:
    """
    Select the appropriate lexical item for a slot.

    Selection Rules:
    - Under CONSERVATIVE_REGIMES: Choose first (lowest-impact) allowed option
    - Under OPEN regime: Choose first allowed option (neutral default)
    - If no allowed candidates: Return None (omit slot)

    Args:
        slot: The SemanticSlot.
        slot_value: The semantic value.
        regime: The operational regime.
        discourse_act: The discourse act.

    Returns:
        The selected lexical item, or None if no candidate is allowed.
    """
    allowed = get_allowed_candidates(slot, slot_value, regime, discourse_act)

    if not allowed:
        return None

    # Always return first (lowest-impact) option
    # Under CONSERVATIVE_REGIMES or OPEN, we use conservative selection
    return allowed[0]


# Public exports
__all__ = [
    # Pools
    "LEXICAL_POOLS",
    "AGENT_POOL",
    "TARGET_POOL",
    "STATE_POOL",
    "UNCERTAINTY_POOL",
    "LIMITATION_POOL",
    "CAUSE_POOL",
    "TEMPORAL_CONTEXT_POOL",
    "REQUEST_FOCUS_POOL",
    "CONSTRAINT_POOL",
    # Constraints
    "CONSERVATIVE_REGIMES",
    "HOLD_BLOCKED_SLOTS",
    "NO_INTENSIFICATION_SLOTS",
    "REFLECTION_CONSTRAINTS",
    "QUESTION_BLOCKED_WORDS",
    "EXPLANATION_PREFERRED_WORDS",
    "EMOTIONALLY_AMPLIFYING_WORDS",
    "CERTAINTY_WORDS",
    # Functions
    "get_pool_for_slot",
    "get_candidates_for_value",
    "is_word_allowed",
    "get_allowed_candidates",
    "select_lexical_item",
]
