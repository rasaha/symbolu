"""
P8 - Semantic Slot Resolution

P8 is a post-discourse, pre-lexical phase.
It determines WHAT MEANINGS must be expressed, not how they are worded.
It constructs a Semantic Slot Map based on the selected Discourse Act.

P8's responsibility is to:
- Resolve which semantic slots are required for the discourse act
- Produce a read-only SemanticFrame that constrains downstream lexical selection

P8 does NOT:
- Select words, syntax, or sentence structure
- Perform lexical selection
- Execute actions
- Call LLMs
- Introduce probabilistic behavior
- Hallucinate slot values

Components:
- SemanticSlot: Enum for AGENT/TARGET/STATE/CAUSE/TEMPORAL_CONTEXT/etc.
- SemanticFrame: Output dataclass capturing semantic slot verdict
- P8SemanticResolver: Deterministic semantic slot resolver

CRITICAL: Never hallucinate slot values. If information is missing, slot = None.

Usage:
    from symbolu.mechanical.pipeline.p8_semantics import (
        P8SemanticResolver,
        SemanticFrame,
        SemanticSlot,
    )

    resolver = P8SemanticResolver()
    frame = resolver.resolve(
        grounding_envelope=po1_envelope,
        intent_envelope=po2_envelope,
        regime_envelope=p6_envelope,
        discourse_envelope=p7_envelope,
        grammar_evidence=optional_evidence,
    )
    # frame.slots contains the semantic slot map

Authority Model:
- P8 receives signals from PO1 (grounding), PO2 (intent), P6 (regime), P7 (discourse)
- P8 evaluates semantic slots based on deterministic rules (read-only gating)
- P8 cannot override PO1-P7 decisions
- Semantic slots constrain downstream lexical/language generation
"""

from .p8_semantic_schema import (
    SemanticSlot,
    SemanticFrame,
    DISCOURSE_ACT_ALLOWED_SLOTS,
)
from .p8_semantic_resolver import P8SemanticResolver


__all__ = [
    # Enums
    "SemanticSlot",
    # Constants
    "DISCOURSE_ACT_ALLOWED_SLOTS",
    # Dataclasses
    "SemanticFrame",
    # Resolver
    "P8SemanticResolver",
]
