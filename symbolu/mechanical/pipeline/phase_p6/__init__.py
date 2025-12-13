"""
P6 — Regime Selection & Operational Mode Gate

P6 is the first post-governance, pre-language phase.
It determines what operational regime is safe for this turn based on
already-computed signals from PO1-PO5.

P6's responsibility is to:
- Select an operational regime based on intent, eligibility, coherence, and stability
- Produce a read-only RegimeEnvelope that constrains downstream language generation

P6 does NOT:
- Perform semantic interpretation
- Choose words or discourse acts
- Execute actions
- Modify intent or grounding
- Call LLMs
- Introduce probabilistic behavior

Components:
- RegimeEnvelope: Output dataclass capturing regime selection verdict
- OperationalRegime: Enum for STABILIZE/REFLECT/INFORM/CLARIFY/DE_ESCALATE/HOLD
- P6RegimeGate: Deterministic regime selection gate

CRITICAL: HOLD is always safe. Regime may only restrict, never expand capability.

Usage:
    from symbolu.mechanical.pipeline.phase_p6 import (
        P6RegimeGate,
        RegimeEnvelope,
        OperationalRegime,
    )

    gate = P6RegimeGate()
    envelope = gate.select(intent_envelope, execution, coherence_regime, overall_policy)
    # envelope.regime indicates STABILIZE / REFLECT / INFORM / CLARIFY / DE_ESCALATE / HOLD

Authority Model:
- P6 receives signals from PO2 IntentEnvelope, PO5 ExecutionEligibilityEnvelope,
  and Phase-41 coherence regime
- P6 evaluates regime based on deterministic rules (read-only gating)
- P6 cannot override PO1–PO5 decisions
- Regime constrains downstream language generation
"""

from .p6_schema import (
    OperationalRegime,
    RegimeEnvelope,
)
from .p6_regime_gate import P6RegimeGate


__all__ = [
    # Enums
    "OperationalRegime",
    # Dataclasses
    "RegimeEnvelope",
    # Gate
    "P6RegimeGate",
]
