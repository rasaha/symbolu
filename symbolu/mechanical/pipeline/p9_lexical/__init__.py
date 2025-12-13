"""
P9 - Lexical Selection Engine

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

Architectural Notes:
- P9 is the first word-touching phase
- P9 decides which word, not how it sounds
- P10 will handle acoustic modulation separately
- Authority flows downward; P9 is subordinate to P1-P8

Components:
- LexicalFrame: Output dataclass capturing lexical selection verdict
- P9LexicalResolver: Deterministic lexical selection resolver
- LEXICAL_POOLS: Curated synonym pools per semantic slot

CRITICAL: Never hallucinate words. Only select from curated pools.

Usage:
    from symbolu.mechanical.pipeline.p9_lexical import (
        P9LexicalResolver,
        LexicalFrame,
        LEXICAL_POOLS,
    )

    resolver = P9LexicalResolver()
    frame = resolver.resolve(
        semantic_frame=p8_frame,
        discourse_envelope=p7_envelope,
        regime_envelope=p6_envelope,
    )
    # frame.selections contains the lexical selections

Authority Model:
- P9 receives signals from P8 (SemanticFrame), P7 (discourse), P6 (regime)
- P9 evaluates lexical selections based on deterministic rules (read-only gating)
- P9 cannot override P1-P8 decisions
- Lexical selections constrain downstream acoustic/prosody generation
"""

from .p9_lexical_schema import (
    LexicalFrame,
    validate_selections_against_semantic_frame,
)
from .p9_lexical_pools import (
    LEXICAL_POOLS,
    AGENT_POOL,
    TARGET_POOL,
    STATE_POOL,
    UNCERTAINTY_POOL,
    LIMITATION_POOL,
    CAUSE_POOL,
    TEMPORAL_CONTEXT_POOL,
    REQUEST_FOCUS_POOL,
    CONSTRAINT_POOL,
    CONSERVATIVE_REGIMES,
    HOLD_BLOCKED_SLOTS,
    NO_INTENSIFICATION_SLOTS,
    REFLECTION_CONSTRAINTS,
    QUESTION_BLOCKED_WORDS,
    EXPLANATION_PREFERRED_WORDS,
    EMOTIONALLY_AMPLIFYING_WORDS,
    CERTAINTY_WORDS,
    get_pool_for_slot,
    get_candidates_for_value,
    is_word_allowed,
    get_allowed_candidates,
    select_lexical_item,
)
from .p9_lexical_resolver import P9LexicalResolver


__all__ = [
    # Dataclasses
    "LexicalFrame",
    # Resolver
    "P9LexicalResolver",
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
    # Helper functions
    "validate_selections_against_semantic_frame",
    "get_pool_for_slot",
    "get_candidates_for_value",
    "is_word_allowed",
    "get_allowed_candidates",
    "select_lexical_item",
]
