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

All 12 layers connect to agentic governance:

  Lower 6 — Execution layers (governance ACTS ON these):
    O1  POTENTIAL    →  policy/      What capabilities may activate?
    O2  IDENTITY     →  safety/      Is identity classification safe?
    O3  EXECUTION    →  safety/      Is action authorized? (P55)
    O4  STRUCTURE    →  safety/      Does form comply with contracts? (P16)
    O5  COGNITION    →  agentic_fw/  Are perceptions trustworthy? (confidence gate)
    O6  AGENCY       →  policy/      Is direction policy-aligned? (P53)

  Upper 6 — Governance layers (these PERFORM governance):
    O7  REASONING    →  safety/      Admissibility checks (P15/P16)
    O8  PURPOSE      →  policy/      Constraint alignment (P53 binding)
    O9  WITNESSES    →  posture/     Meta-observation (P51 readiness)
    O10 UNIFYING     →  agentic_fw/  Coherence integration (confidence gate)
    O11 INTEGRATION  →  ledger/      Audit consolidation (P54 records)
    O12 ABSOLVING    →  safety/      Termination boundary (P55, output gate)

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

# Mapping: ALL 12 layers → agentic governance module
#
# Lower 6 (Execution) — governance ACTS ON these layers:
#   Each execution layer has a governance concern that constrains it.
#
# Upper 6 (Governance) — these layers PERFORM governance:
#   Each governance layer maps to an agentic module that implements it.
#
LAYER_TO_GOVERNANCE_MODULE: Dict[str, str] = {
    # Lower 6 — Execution layers governed BY agentic modules
    "O1_POTENTIAL":    "policy",            # Capability gating: what may activate?
    "O2_IDENTITY":     "safety",            # Identity guards: safe to act on?
    "O3_EXECUTION":    "safety",            # Execution boundary (P55): authorized?
    "O4_STRUCTURE":    "safety",            # Regression guard (P16): contract-compliant?
    "O5_COGNITION":    "agentic_framework", # Confidence gate: perceptions trustworthy?
    "O6_AGENCY":       "policy",            # Governance binding (P53): direction aligned?
    # Upper 6 — Governance layers implemented IN agentic modules
    "O7_REASONING":    "safety",            # Admissibility guards (P15/P16)
    "O8_PURPOSE":      "policy",            # Constraint alignment (P53)
    "O9_WITNESSES":    "posture",           # Observation / readiness (P51)
    "O10_UNIFYING":    "agentic_framework", # Confidence gate / coherence
    "O11_INTEGRATION": "ledger",            # Audit consolidation (P54)
    "O12_ABSOLVING":   "safety",            # Execution boundary (P55) / output gate
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
    """Governance signals extracted from all 12 ontological layers.

    All 12 layers participate in governance:
    - Lower 6 (O1-O6): Execution layers that governance CONSTRAINS.
      Each has a governance concern (capability gating, identity safety,
      execution authorization, structural compliance, perceptual trust,
      directional alignment).
    - Upper 6 (O7-O12): Governance layers that PERFORM constraint,
      observation, coherence, audit, and boundary enforcement.

    Attributes:
        governance_strength: Upper 6 layer activation [0, 1].
        execution_strength: Lower 6 layer activation [0, 1].
        layer_balance: Execution vs governance ratio [0, 1].
            0.0 = pure governance, 0.5 = balanced, 1.0 = pure execution.

        Lower 6 — Execution layers (governance acts on these):
        potential_weight: O1 — latent capability pressure.
        identity_weight: O2 — classification / role assignment pressure.
        execution_weight: O3 — somatic initiation / action pressure.
        structure_weight: O4 — structural shaping pressure.
        cognition_weight: O5 — perceptual / attentional pressure.
        agency_weight: O6 — directional control pressure.

        Upper 6 — Governance layers (these perform governance):
        reasoning_weight: O7 — admissibility checking capacity.
        purpose_weight: O8 — constraint alignment capacity.
        witness_weight: O9 — self-observation / damping capacity.
        unifying_weight: O10 — coherence integration capacity.
        integration_weight: O11 — audit consolidation capacity.
        absolving_weight: O12 — boundary enforcement capacity.

        tension_zones: Structural tensions detected by OLM.
        governance_gaps: Governance weaknesses (layer below threshold).
        execution_risks: Execution layers active without governance cover.
    """
    governance_strength: float
    execution_strength: float
    layer_balance: float

    # Lower 6 — Execution layer weights (governance acts on these)
    potential_weight: float     # O1 — capability pressure
    identity_weight: float     # O2 — classification pressure
    execution_weight: float    # O3 — action pressure
    structure_weight: float    # O4 — structural pressure
    cognition_weight: float    # O5 — perceptual pressure
    agency_weight: float       # O6 — directional pressure

    # Upper 6 — Governance layer weights (these perform governance)
    reasoning_weight: float     # O7 — admissibility
    purpose_weight: float       # O8 — alignment
    witness_weight: float       # O9 — observation
    unifying_weight: float      # O10 — coherence
    integration_weight: float   # O11 — audit
    absolving_weight: float     # O12 — boundary

    tension_zones: Tuple[str, ...] = ()
    governance_gaps: Tuple[str, ...] = ()
    execution_risks: Tuple[str, ...] = ()


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

    # All 12 layer values
    o1 = weights["O1_POTENTIAL"]
    o2 = weights["O2_IDENTITY"]
    o3 = weights["O3_EXECUTION"]
    o4 = weights["O4_STRUCTURE"]
    o5 = weights["O5_COGNITION"]
    o6 = weights["O6_AGENCY"]
    o7 = weights["O7_REASONING"]
    o8 = weights["O8_PURPOSE"]
    o9 = weights["O9_WITNESSES"]
    o10 = weights["O10_UNIFYING"]
    o11 = weights["O11_INTEGRATION"]
    o12 = weights["O12_ABSOLVING"]

    # Aggregates
    exec_sum = sum(weights[l] for l in EXECUTION_LAYERS)
    gov_sum = sum(weights[l] for l in GOVERNANCE_LAYERS)
    total = exec_sum + gov_sum
    balance = exec_sum / total if total > 0 else 0.5

    # Map all 12 layers into 7 confidence dimensions:
    #
    # quality_score: O7 (admissibility) + O4 (structural integrity)
    #   → higher when reasoning checks AND structure are sound
    #
    # coherence_score: O10 (unifying) + O11 (integration) + O2 (identity consistency)
    #   → higher when field coherence, consolidation, and identity are aligned
    #
    # internal_consistency: O9 (witnesses) + O5 (cognition)
    #   → higher when self-observation AND perceptual clarity are active
    #
    # goal_alignment: O8 (purpose) + O6 (agency)
    #   → higher when teleological orientation AND directional control align
    #
    # trajectory_confidence: governance vs execution balance
    #   → higher governance strength = more confident trajectory
    #
    # action_complexity: O3 (execution) + O1 (potential) + O6 (agency)
    #   → higher when action pressure, latent activation, and control are active
    #
    # action_reversibility: O12 (absolving) + O11 (integration)
    #   → higher when termination boundary AND consolidation are available
    #
    return ConfidenceSignals(
        quality_score=_clamp(0.4 * o7 + 0.3 * o10 + 0.3 * o4),
        coherence_score=_clamp(0.4 * o10 + 0.3 * o11 + 0.3 * o2),
        internal_consistency=_clamp(0.6 * o9 + 0.4 * o5),
        goal_alignment=_clamp(0.6 * o8 + 0.4 * o6),
        trajectory_confidence=_clamp(1.0 - balance),
        action_complexity=_clamp(0.4 * o3 + 0.3 * o1 + 0.3 * o6),
        action_reversibility=_clamp(0.6 * o12 + 0.4 * o11),
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

    # Identify governance gaps (upper 6 below threshold)
    gaps = []
    for layer in GOVERNANCE_LAYERS:
        if weights[layer] < LAYER_GAP_THRESHOLD:
            gaps.append(f"{layer}_suppressed")

    # Identify execution risks: execution layers active without
    # their corresponding governance cover
    exec_risks = []
    # O1 POTENTIAL active without O8 PURPOSE (capability without alignment)
    if weights["O1_POTENTIAL"] > GOVERNANCE_ACTIVE_THRESHOLD and weights["O8_PURPOSE"] < LAYER_GAP_THRESHOLD:
        exec_risks.append("O1_ungoverned_potential")
    # O2 IDENTITY active without O7 REASONING (classification without admissibility)
    if weights["O2_IDENTITY"] > GOVERNANCE_ACTIVE_THRESHOLD and weights["O7_REASONING"] < LAYER_GAP_THRESHOLD:
        exec_risks.append("O2_unverified_identity")
    # O3 EXECUTION active without O12 ABSOLVING (action without termination boundary)
    if weights["O3_EXECUTION"] > GOVERNANCE_ACTIVE_THRESHOLD and weights["O12_ABSOLVING"] < LAYER_GAP_THRESHOLD:
        exec_risks.append("O3_unbounded_execution")
    # O4 STRUCTURE active without O7 REASONING (form without compliance check)
    if weights["O4_STRUCTURE"] > GOVERNANCE_ACTIVE_THRESHOLD and weights["O7_REASONING"] < LAYER_GAP_THRESHOLD:
        exec_risks.append("O4_unchecked_structure")
    # O5 COGNITION active without O9 WITNESSES (perception without observation)
    if weights["O5_COGNITION"] > GOVERNANCE_ACTIVE_THRESHOLD and weights["O9_WITNESSES"] < LAYER_GAP_THRESHOLD:
        exec_risks.append("O5_unwitnessed_cognition")
    # O6 AGENCY active without O8 PURPOSE (direction without alignment)
    if weights["O6_AGENCY"] > GOVERNANCE_ACTIVE_THRESHOLD and weights["O8_PURPOSE"] < LAYER_GAP_THRESHOLD:
        exec_risks.append("O6_misaligned_agency")

    return OLMGovernanceSignals(
        governance_strength=gov_sum,
        execution_strength=exec_sum,
        layer_balance=balance,
        # Lower 6
        potential_weight=weights["O1_POTENTIAL"],
        identity_weight=weights["O2_IDENTITY"],
        execution_weight=weights["O3_EXECUTION"],
        structure_weight=weights["O4_STRUCTURE"],
        cognition_weight=weights["O5_COGNITION"],
        agency_weight=weights["O6_AGENCY"],
        # Upper 6
        reasoning_weight=weights["O7_REASONING"],
        purpose_weight=weights["O8_PURPOSE"],
        witness_weight=weights["O9_WITNESSES"],
        unifying_weight=weights["O10_UNIFYING"],
        integration_weight=weights["O11_INTEGRATION"],
        absolving_weight=weights["O12_ABSOLVING"],
        tension_zones=tensions,
        governance_gaps=tuple(gaps),
        execution_risks=tuple(exec_risks),
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

    # Check specific critical gaps in upper 6 (governance performers)
    if signals.witness_weight < LAYER_GAP_THRESHOLD:
        risk_factors.append("O9_WITNESSES suppressed — no self-observation")
    if signals.absolving_weight < LAYER_GAP_THRESHOLD:
        risk_factors.append("O12_ABSOLVING suppressed — no termination boundary")
    if signals.reasoning_weight < LAYER_GAP_THRESHOLD:
        risk_factors.append("O7_REASONING suppressed — no admissibility checking")
    if signals.unifying_weight < LAYER_GAP_THRESHOLD:
        risk_factors.append("O10_UNIFYING suppressed — no coherence integration")
    if signals.integration_weight < LAYER_GAP_THRESHOLD:
        risk_factors.append("O11_INTEGRATION suppressed — no audit consolidation")
    if signals.purpose_weight < LAYER_GAP_THRESHOLD:
        risk_factors.append("O8_PURPOSE suppressed — no constraint alignment")

    # Check execution risks: lower 6 active without governance cover
    for exec_risk in signals.execution_risks:
        risk_factors.append(f"Execution risk: {exec_risk}")

    # Check tension zones
    for tension in signals.tension_zones:
        if tension in (
            "execution_governance_gap",
            "boundary_dissolution_risk",
            "high_entropy_destabilization",
        ):
            risk_factors.append(f"Tension: {tension}")

    # Determine risk level
    gov_gap_count = len(weak_layers)
    exec_risk_count = len(signals.execution_risks)
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
        or gov_gap_count >= 3
        or exec_risk_count >= 3
        or has_exec_gap
    ):
        risk_level = "HIGH"
        recommended = "DEFER — require human confirmation before execution"
        confidence_adj = -0.20
    elif (
        gov_gap_count >= 1
        or exec_risk_count >= 1
        or signals.layer_balance > EXECUTION_DOMINANT_THRESHOLD
    ):
        risk_level = "MODERATE"
        recommended = "CAUTIOUS — proceed with elevated monitoring"
        confidence_adj = -0.10
    else:
        risk_level = "LOW"
        recommended = "ALLOW — all 12 layers adequately governed"
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
        # Lower 6
        "O1_POTENTIAL": "potential_weight",
        "O2_IDENTITY": "identity_weight",
        "O3_EXECUTION": "execution_weight",
        "O4_STRUCTURE": "structure_weight",
        "O5_COGNITION": "cognition_weight",
        "O6_AGENCY": "agency_weight",
        # Upper 6
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
