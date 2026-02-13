"""
P38 - Pattern Aspect Derivation
================================

Derives the 10 UNIVERSAL_ASPECTS from CDI input signals (smi, bhava_id,
bhava_direction, kosha_id, ontology_id) using deterministic formulas.

These aspect vectors serve as domain-agnostic pattern fingerprints that
can be fed into ``get_aspect_overlap()`` from ``domain_distance.py``
for cross-domain structural similarity computation.

INVARIANTS:
    - INV-P38-1: Deterministic (same inputs -> same outputs)
    - INV-P38-3: No LLM, no ML, no learning
    - All derivation rules are pure arithmetic, clamped to [0.0, 1.0]

Version: 1.0.0
"""

from __future__ import annotations

from typing import Dict


P38_ASPECT_VERSION = "1.0.0"

# 10 Universal Aspects (aligned with domain_distance.py:311-322)
ASPECT_NAMES = [
    "ENTROPY", "CAUSALITY", "AGENCY", "BALANCE", "FLOW",
    "CONSTRAINT", "EMERGENCE", "FEEDBACK", "HIERARCHY", "THRESHOLD",
]


def _clamp(value: float) -> float:
    """Clamp value to [0.0, 1.0]."""
    return max(0.0, min(1.0, value))


def derive_aspect_vector(
    smi: float,
    bhava_id: int,
    bhava_direction: str,
    kosha_id: int,
    ontology_id: int,
) -> Dict[str, float]:
    """
    Derive a 10-dimensional aspect vector from CDI input signals.

    Each aspect is a deterministic function of the inputs, clamped to [0.0, 1.0].

    Args:
        smi: Semantic Mismatch Index [0.0, 1.0].
        bhava_id: Bhava state identifier (0-11).
        bhava_direction: "upward" | "downward" | "neutral".
        kosha_id: Kosha layer identifier (0-7).
        ontology_id: Ontology state identifier (0-12).

    Returns:
        Dict mapping aspect names to float values in [0.0, 1.0].
    """
    direction_flow = {"upward": 0.8, "neutral": 0.5, "downward": 0.2}
    flow_val = direction_flow.get(bhava_direction, 0.5)
    is_upward = 1.0 if bhava_direction == "upward" else 0.3

    # Normalize identifiers to [0, 1] ranges
    bhava_norm = bhava_id / 11.0 if bhava_id <= 11 else 1.0
    kosha_norm = kosha_id / 7.0 if kosha_id <= 7 else 1.0
    ontology_norm = ontology_id / 12.0 if ontology_id <= 12 else 1.0

    # --- Derivation rules (locked) ---

    # ENTROPY: High SMI = high entropy (semantic mismatch = disorder)
    entropy = smi

    # CAUSALITY: Higher ontology_ids (>5) map to reasoning/purpose dimensions
    causality = max(0.0, (ontology_id - 5) / 7.0) if ontology_id > 5 else 0.0

    # AGENCY: Higher bhava_ids indicate more agentic states
    agency = bhava_norm

    # BALANCE: Low SMI + centered bhava = balance
    bhava_center_dist = abs(bhava_id - 5.5) / 5.5
    balance = (1.0 - smi) * (1.0 - bhava_center_dist)

    # FLOW: upward = flow, neutral = moderate, downward = blocked
    flow = flow_val

    # CONSTRAINT: Higher kosha = deeper constraint layers
    constraint = kosha_norm

    # EMERGENCE: Low SMI + high bhava + upward direction = emergent
    emergence = (1.0 - smi) * bhava_norm * is_upward

    # FEEDBACK: Tension corridor signal (high SMI sustained = feedback loop)
    feedback = smi if smi > 0.6 else smi * 0.5

    # HIERARCHY: Kosha layers are hierarchical by definition
    hierarchy = kosha_norm

    # THRESHOLD: Proximity to known SMI pattern boundaries
    boundary_distances = [
        abs(smi - 0.35),
        abs(smi - 0.50),
        abs(smi - 0.65),
        abs(smi - 0.75),
    ]
    min_boundary_dist = min(boundary_distances)
    threshold = 1.0 - min(min_boundary_dist / 0.20, 1.0)

    return {
        "ENTROPY": _clamp(entropy),
        "CAUSALITY": _clamp(causality),
        "AGENCY": _clamp(agency),
        "BALANCE": _clamp(balance),
        "FLOW": _clamp(flow),
        "CONSTRAINT": _clamp(constraint),
        "EMERGENCE": _clamp(emergence),
        "FEEDBACK": _clamp(feedback),
        "HIERARCHY": _clamp(hierarchy),
        "THRESHOLD": _clamp(threshold),
    }


__all__ = [
    "P38_ASPECT_VERSION",
    "ASPECT_NAMES",
    "derive_aspect_vector",
]
