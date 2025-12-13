"""
P7 — Discourse Act Resolver

P7 is a post-regime, pre-semantics phase.
It determines WHAT KIND OF UTTERANCE is allowed, not what it says.
It resolves the Discourse Act for the current turn.

P7's responsibility is to:
- Resolve the discourse act type based on intent, regime, and allowed actions
- Produce a read-only DiscourseEnvelope that constrains downstream language generation

P7 does NOT:
- Select words, syntax, or meaning slots
- Perform semantic interpretation
- Execute actions
- Call LLMs
- Introduce probabilistic behavior

Components:
- DiscourseEnvelope: Output dataclass capturing discourse act verdict
- DiscourseAct: Enum for QUESTION/REFLECTION/ACKNOWLEDGMENT/EXPLANATION/INSTRUCTION/DEFERRAL
- P7DiscourseResolver: Deterministic discourse act resolver

CRITICAL: DEFERRAL is always safe. Discourse act may only restrict, never expand capability.

Usage:
    from symbolu.mechanical.pipeline.p7_discourse import (
        P7DiscourseResolver,
        DiscourseEnvelope,
        DiscourseAct,
    )

    resolver = P7DiscourseResolver()
    envelope = resolver.resolve(
        grounding_envelope=po1_envelope,
        intent_envelope=po2_envelope,
        action_contract=po3_actions,
        regime_envelope=p6_envelope,
        grammar_evidence=optional_evidence,
    )
    # envelope.act indicates QUESTION / REFLECTION / ACKNOWLEDGMENT / EXPLANATION / INSTRUCTION / DEFERRAL

Authority Model:
- P7 receives signals from PO1 (grounding), PO2 (intent), PO3 (actions), P6 (regime)
- P7 evaluates discourse act based on deterministic rules (read-only gating)
- P7 cannot override PO1–P6 decisions
- Discourse act constrains downstream semantic/language generation
"""

from .p7_discourse_schema import (
    DiscourseAct,
    DiscourseEnvelope,
)
from .p7_discourse_resolver import P7DiscourseResolver


__all__ = [
    # Enums
    "DiscourseAct",
    # Dataclasses
    "DiscourseEnvelope",
    # Resolver
    "P7DiscourseResolver",
]
