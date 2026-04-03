"""
OLM Bridge — Wires the 12-layer Ontological Layer Model into the
agentic framework's ConfidenceGate and GovernanceService.

Bridges the patent-exact 12-layer ontological model:

  Lower 6 — Execution / Manifestation:
    O1  POTENTIAL   (dormant capacity, latent possibility)
    O2  IDENTITY    (classificatory marking, role assignment)
    O3  EXECUTION   (somatic initiation, karma)
    O4  STRUCTURE   (shaping force, embodiment)
    O5  COGNITION   (perception, attention, emotional processing)
    O6  AGENCY      (vector orientation, control, intent)

  Upper 6 — Governance / Coherence:
    O7  REASONING   (sequential logic, discriminative analysis)
    O8  PURPOSE     (teleological orientation, meaning)
    O9  WITNESSES   (meta-observation, pattern tracking)
    O10 UNIFYING    (field coherence, synthesis)
    O11 INTEGRATION (resolution, consolidation)
    O12 ABSOLVING   (dissolution, termination, release)

The upper 6 layers map directly to agentic governance modules:

    O7  REASONING    →  safety/      (admissibility, guards P15/P16)
    O8  PURPOSE      →  policy/      (constraint alignment, P53 binding)
    O9  WITNESSES    →  posture/     (observation, readiness P51)
    O10 UNIFYING     →  agentic_fw/  (confidence gate, coherence integration)
    O11 INTEGRATION  →  ledger/      (audit consolidation, P54 records)
    O12 ABSOLVING    →  safety/      (execution boundary P55, output gate)

Usage:
    from agentic.agentic_framework.olm_bridge import (
        signals_from_olm,
        governance_risk_from_olm,
        olm_to_readiness_input,
    )

    olm_map = olm_engine.build_map(olm_input)
    signals = signals_from_olm(olm_map)
    risk = governance_risk_from_olm(olm_map)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from agentic.agentic_framework.confidence_gate import ConfidenceSignals


# =============================================================================
# 12-Layer Constants (Patent-Exact)
# =============================================================================

# Lower 6 — Execution / Manifestation
EXECUTION_LAYERS: Tuple[str, ...] = (
    "O1_POTENTIAL",   # Dormant capacity
    "O2_IDENTITY",    # Classification
    "O3_EXECUTION",   # Somatic initiation
    "O4_STRUCTURE",   # Shaping / form
    "O5_COGNITION",   # Perception / attention
    "O6_AGENCY",      # Direction / control
)

# Upper 6 — Governance / Coherence
GOVERNANCE_LAYERS: Tuple[str, ...] = (
    "O7_REASONING",    # Sequential logic, admissibility
    "O8_PURPOSE",      # Teleological orientation
    "O9_WITNESSES",    # Meta-observation
    "O10_UNIFYING",    # Field coherence
    "O11_INTEGRATION", # Resolution / consolidation
    "O12_ABSOLVING",   # Dissolution / termination
)

ALL_12_LAYERS: Tuple[str, ...] = EXECUTION_LAYERS + GOVERNANCE_LAYERS

# Mapping: 12-layer → agentic governance module
LAYER_TO_GOVERNANCE_MODULE: Dict[str, str] = {
    "O7_REASONING":    "safety",           # Admissibility guards (P15/P16)
    "O8_PURPOSE":      "policy",           # Constraint alignment (P53)
    "O9_WITNESSES":    "posture",          # Observation / readiness (P51)
    "O10_UNIFYING":    "agentic_framework",  # Confidence gate / coherence
    "O11_INTEGRATION": "ledger",           # Audit consolidation (P54)
    "O12_ABSOLVING":   "safety",           # Execution boundary (P55) / output gate
}

# Mapping: OLM v1.0 (10-layer) → 12-layer (for backwards compatibility)
OLM_V1_TO_V2: Dict[str, str] = {
    "O1_action":         "O3_EXECUTION",
    "O2_tagging":        "O2_IDENTITY",
    "O3_forming":        "O4_STRUCTURE",
    "O4_thinking":       "O5_COGNITION",
    "O5_directing":      "O6_AGENCY",
    "O6_reasoning":      "O7_REASONING",
    "O7_purposing":      "O8_PURPOSE",
    "O8_meta_observing": "O9_WITNESSES",
    "O9_unifying":       "O10_UNIFYING",
    "O10_absolving":     "O12_ABSOLVING",
}


# =============================================================================
# OLM Governance Signals
# =============================================================================

@dataclass(frozen=True)
class OLMGovernanceSignals:
    """Governance signals extracted from a 12-layer ontological map.

    Attributes:
        governance_strength: Overall governance layer activation [0, 1].
            Sum of O7-O12 weights. Higher = more governance capacity.
        execution_strength: Overall execution layer activation [0, 1].
            Sum of O1-O6 weights. Higher = more execution pressure.
        layer_balance: Execution vs governance ratio [0, 1].
            0.0 = pure governance, 0.5 = balanced, 1.0 = pure execution.
        reasoning_weight: O7 — admissibility checking capacity.
        purpose_weight: O8 — constraint alignment capacity.
        witness_weight: O9 — self-observation / damping capacity.
        unifying_weight: O10 — coherence integration capacity.
        integration_weight: O11 — audit consolidation capacity.
        absolving_weight: O12 — boundary enforcement capacity.
        tension_zones: Structural tensions detected by OLM.
        governance_gaps: Specific governance weaknesses identified.
    """
    governance_strength: float
    execution_strength: float
    layer_balance: float

    # Individual governance layer weights
    reasoning_weight: float     # O7
    purpose_weight: float       # O8
    witness_weight: float       # O9
    unifying_weight: float      # O10
    integration_weight: float   # O11
    absolving_weight: float     # O12

    tension_zones: Tuple[str, ...] = ()
    governance_gaps: Tuple[str, ...] = ()


@dataclass(frozen=True)
class OLMGovernanceRisk:
    """Risk assessment derived from ontological layer imbalances.

    Attributes:
        risk_level: Overall governance risk (LOW / MODERATE / HIGH / CRITICAL).
        risk_factors: List of specific risk factor descriptions.
        recommended_action: Suggested governance response.
        weak_layers: Governance layers below minimum threshold.
        confidence_adjustment: Suggested adjustment to confidence score [-0.3, 0].
            Negative values lower confidence when governance layers are weak.
    """
    risk_level: str
    risk_factors: Tuple[str, ...]
    recommended_action: str
    weak_layers: Tuple[str, ...]
    confidence_adjustment: float


# =============================================================================
# Thresholds
# =============================================================================

# Minimum governance layer weight to be considered "active"
GOVERNANCE_ACTIVE_THRESHOLD: float = 0.08

# Governance strength below this triggers risk escalation
GOVERNANCE_WEAK_THRESHOLD: float = 0.30

# Layer balance above this means execution-dominant (governance risk)
EXECUTION_DOMINANT_THRESHOLD: float = 0.70

# Individual governance layer below this is a "gap"
LAYER_GAP_THRESHOLD: float = 0.05


# =============================================================================
# Bridge Functions
# =============================================================================

def _normalize_layer_weights(
    layer_weights: Dict[str, float],
) -> Dict[str, float]:
    """Normalize layer weights to 12-layer format.

    Accepts both v1 (10-layer) and v2 (12-layer) formats.
    Missing layers default to 0.0. Weights are NOT re-normalized;
    the caller's normalization is preserved.
    """
    normalized: Dict[str, float] = {layer: 0.0 for layer in ALL_12_LAYERS}

    for key, value in layer_weights.items():
        if key in ALL_12_LAYERS:
            # Already in 12-layer format
            normalized[key] = value
        elif key in OLM_V1_TO_V2:
            # Convert from 10-layer to 12-layer
            normalized[OLM_V1_TO_V2[key]] = value

    return normalized


def signals_from_olm(
    olm_output: Any,
    *,
    layer_weights: Optional[Dict[str, float]] = None,
) -> ConfidenceSignals:
    """Convert OLM output to ConfidenceSignals for the ConfidenceGate.

    Maps ontological governance layers to confidence dimensions:
        quality_score     ← O7 (reasoning) + O10 (unifying)
        coherence_score   ← O10 (unifying) + O11 (integration)
        internal_consistency ← O9 (witnesses) — self-observation capacity
        goal_alignment    ← O8 (purpose) — teleological alignment
        trajectory_confidence ← 1.0 - layer_balance (higher governance = more confidence)
        action_complexity ← execution_strength (higher execution = more action pressure)
        action_reversibility ← O12 (absolving) — boundary enforcement available

    Args:
        olm_output: OntologicalLayerMap from OLMEngine.build_map().
            If None, layer_weights must be provided.
        layer_weights: Raw layer weight dict (alternative to olm_output).

    Returns:
        ConfidenceSignals suitable for ConfidenceGate.evaluate().
    """
    if layer_weights is not None:
        weights = _normalize_layer_weights(layer_weights)
    elif olm_output is not None:
        # Extract from OntologicalLayerMap
        raw = {}
        if hasattr(olm_output, "governance_profile"):
            raw.update(olm_output.governance_profile)
        if hasattr(olm_output, "execution_profile"):
            raw.update(olm_output.execution_profile)
        weights = _normalize_layer_weights(raw)
    else:
        raise ValueError("Either olm_output or layer_weights must be provided")

    # Governance layer values
    o7 = weights["O7_REASONING"]
    o8 = weights["O8_PURPOSE"]
    o9 = weights["O9_WITNESSES"]
    o10 = weights["O10_UNIFYING"]
    o11 = weights["O11_INTEGRATION"]
    o12 = weights["O12_ABSOLVING"]

    # Execution aggregate
    exec_sum = sum(weights[l] for l in EXECUTION_LAYERS)
    gov_sum = sum(weights[l] for l in GOVERNANCE_LAYERS)
    total = exec_sum + gov_sum
    balance = exec_sum / total if total > 0 else 0.5

    return ConfidenceSignals(
        quality_score=_clamp(0.5 * o7 + 0.5 * o10),
        coherence_score=_clamp(0.5 * o10 + 0.5 * o11),
        internal_consistency=_clamp(o9),
        goal_alignment=_clamp(o8),
        trajectory_confidence=_clamp(1.0 - balance),
        action_complexity=_clamp(exec_sum),
        action_reversibility=_clamp(o12),
    )


def governance_signals_from_olm(
    olm_output: Any,
    *,
    layer_weights: Optional[Dict[str, float]] = None,
) -> OLMGovernanceSignals:
    """Extract structured governance signals from OLM output.

    Provides the full 6-layer governance profile and detects gaps
    where governance layers are suppressed while execution layers
    are active.

    Args:
        olm_output: OntologicalLayerMap from OLMEngine.build_map().
        layer_weights: Raw layer weight dict (alternative to olm_output).

    Returns:
        OLMGovernanceSignals with per-layer weights and gap analysis.
    """
    if layer_weights is not None:
        weights = _normalize_layer_weights(layer_weights)
        tensions: Tuple[str, ...] = ()
    elif olm_output is not None:
        raw = {}
        if hasattr(olm_output, "governance_profile"):
            raw.update(olm_output.governance_profile)
        if hasattr(olm_output, "execution_profile"):
            raw.update(olm_output.execution_profile)
        weights = _normalize_layer_weights(raw)
        tensions = tuple(
            olm_output.tension_zones
        ) if hasattr(olm_output, "tension_zones") else ()
    else:
        raise ValueError("Either olm_output or layer_weights must be provided")

    exec_sum = sum(weights[l] for l in EXECUTION_LAYERS)
    gov_sum = sum(weights[l] for l in GOVERNANCE_LAYERS)
    total = exec_sum + gov_sum
    balance = exec_sum / total if total > 0 else 0.5

    # Identify governance gaps
    gaps = []
    for layer in GOVERNANCE_LAYERS:
        if weights[layer] < LAYER_GAP_THRESHOLD:
            gaps.append(f"{layer}_suppressed")

    return OLMGovernanceSignals(
        governance_strength=gov_sum,
        execution_strength=exec_sum,
        layer_balance=balance,
        reasoning_weight=weights["O7_REASONING"],
        purpose_weight=weights["O8_PURPOSE"],
        witness_weight=weights["O9_WITNESSES"],
        unifying_weight=weights["O10_UNIFYING"],
        integration_weight=weights["O11_INTEGRATION"],
        absolving_weight=weights["O12_ABSOLVING"],
        tension_zones=tensions,
        governance_gaps=tuple(gaps),
    )


def governance_risk_from_olm(
    olm_output: Any,
    *,
    layer_weights: Optional[Dict[str, float]] = None,
) -> OLMGovernanceRisk:
    """Assess governance risk from ontological layer imbalances.

    Risk escalation rules:
        CRITICAL: governance_strength < 0.15 AND execution > 0.5
                  (system executing without governance)
        HIGH:     governance_strength < 0.30 OR 3+ governance gaps
                  OR execution_governance_gap tension detected
        MODERATE: 1-2 governance gaps OR layer_balance > 0.70
        LOW:      governance layers are adequately active

    Args:
        olm_output: OntologicalLayerMap from OLMEngine.build_map().
        layer_weights: Raw layer weight dict (alternative to olm_output).

    Returns:
        OLMGovernanceRisk with risk level, factors, and confidence adjustment.
    """
    signals = governance_signals_from_olm(
        olm_output, layer_weights=layer_weights
    )

    risk_factors = []
    weak_layers = []

    # Check each governance layer
    for layer in GOVERNANCE_LAYERS:
        weight = getattr(signals, _layer_to_attr(layer))
        if weight < GOVERNANCE_ACTIVE_THRESHOLD:
            weak_layers.append(layer)

    # Check governance strength
    if signals.governance_strength < GOVERNANCE_WEAK_THRESHOLD:
        risk_factors.append(
            f"Low governance strength ({signals.governance_strength:.2f})"
        )

    # Check balance
    if signals.layer_balance > EXECUTION_DOMINANT_THRESHOLD:
        risk_factors.append(
            f"Execution-dominant balance ({signals.layer_balance:.2f})"
        )

    # Check specific critical gaps
    if signals.witness_weight < LAYER_GAP_THRESHOLD:
        risk_factors.append("O9_WITNESSES suppressed — no self-observation")
    if signals.absolving_weight < LAYER_GAP_THRESHOLD:
        risk_factors.append("O12_ABSOLVING suppressed — no termination boundary")
    if signals.reasoning_weight < LAYER_GAP_THRESHOLD:
        risk_factors.append("O7_REASONING suppressed — no admissibility checking")

    # Check tension zones
    for tension in signals.tension_zones:
        if tension in (
            "execution_governance_gap",
            "boundary_dissolution_risk",
            "high_entropy_destabilization",
        ):
            risk_factors.append(f"Tension: {tension}")

    # Determine risk level
    gap_count = len(weak_layers)
    has_exec_gap = "execution_governance_gap" in signals.tension_zones

    if (
        signals.governance_strength < 0.15
        and signals.execution_strength > 0.50
    ):
        risk_level = "CRITICAL"
        recommended = "DENY — system executing without governance capacity"
        confidence_adj = -0.30
    elif (
        signals.governance_strength < GOVERNANCE_WEAK_THRESHOLD
        or gap_count >= 3
        or has_exec_gap
    ):
        risk_level = "HIGH"
        recommended = "DEFER — require human confirmation before execution"
        confidence_adj = -0.20
    elif gap_count >= 1 or signals.layer_balance > EXECUTION_DOMINANT_THRESHOLD:
        risk_level = "MODERATE"
        recommended = "CAUTIOUS — proceed with elevated monitoring"
        confidence_adj = -0.10
    else:
        risk_level = "LOW"
        recommended = "ALLOW — governance layers adequately active"
        confidence_adj = 0.0

    return OLMGovernanceRisk(
        risk_level=risk_level,
        risk_factors=tuple(risk_factors),
        recommended_action=recommended,
        weak_layers=tuple(weak_layers),
        confidence_adjustment=confidence_adj,
    )


def olm_to_readiness_input(
    olm_output: Any,
) -> Dict[str, Any]:
    """Extract P51-relevant readiness signals from OLM output.

    Returns a dict that can supplement P51 governance readiness
    assessment with ontological layer health information.

    Args:
        olm_output: OntologicalLayerMap from OLMEngine.build_map().

    Returns:
        Dict with readiness-relevant fields:
            olm_governance_active: bool (are governance layers active?)
            olm_balance: float (execution vs governance)
            olm_tension_count: int (structural tensions)
            olm_governance_gaps: list (suppressed governance layers)
    """
    signals = governance_signals_from_olm(olm_output)

    return {
        "olm_governance_active": signals.governance_strength >= GOVERNANCE_WEAK_THRESHOLD,
        "olm_balance": signals.layer_balance,
        "olm_tension_count": len(signals.tension_zones),
        "olm_governance_gaps": list(signals.governance_gaps),
    }


# =============================================================================
# Helpers
# =============================================================================

def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Clamp value to [low, high] range."""
    return max(low, min(high, value))


def _layer_to_attr(layer: str) -> str:
    """Convert layer name to OLMGovernanceSignals attribute name."""
    mapping = {
        "O7_REASONING": "reasoning_weight",
        "O8_PURPOSE": "purpose_weight",
        "O9_WITNESSES": "witness_weight",
        "O10_UNIFYING": "unifying_weight",
        "O11_INTEGRATION": "integration_weight",
        "O12_ABSOLVING": "absolving_weight",
    }
    return mapping[layer]


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Constants
    "EXECUTION_LAYERS",
    "GOVERNANCE_LAYERS",
    "ALL_12_LAYERS",
    "LAYER_TO_GOVERNANCE_MODULE",
    "OLM_V1_TO_V2",
    # Dataclasses
    "OLMGovernanceSignals",
    "OLMGovernanceRisk",
    # Bridge functions
    "signals_from_olm",
    "governance_signals_from_olm",
    "governance_risk_from_olm",
    "olm_to_readiness_input",
]
