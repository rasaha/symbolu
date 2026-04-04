"""
Sovereign State Bridge — Wires tensor-level 32D Sovereign State into the
agentic framework's ConfidenceGate and SafetyContract.

V11.0.0: Bridges the two disconnected stacks:

  Stack 1 (Tensor-level):
    Hidden[768D] → SovereignStateProjector → State[32D]
      ├─ Bhava[0:12]  → phase rotation (handled by IntentPhaseProjector)
      ├─ Kosha[12:17] → processing depth
      ├─ Vritti[17:22] → epistemic reliability
      └─ Guna[22:28]  → energy dynamics

  Stack 2 (Agentic framework):
    ConfidenceSignals → ConfidenceGate → EscalationController / BudgetController
    CoherenceState → SafetyContractEvaluator → SafetyContract

This module bridges Stack 1 → Stack 2 by converting control plane
tensor signals (Kosha/Vritti/Guna) into the dataclass signals that
ConfidenceGate and SafetyContractEvaluator already consume.

Usage:
    from agentic.agentic_framework.sovereign_bridge import (
        signals_from_sovereign_state,
        coherence_from_sovereign_state,
    )

    # In inference loop, after model forward pass:
    outputs = model(input_ids)
    state = outputs['state']        # [B, 32] full Sovereign State
    delta_S = outputs['delta_S']    # [B, 32] full state delta

    # Convert to agentic signals
    signals = signals_from_sovereign_state(state, delta_S)
    coherence = coherence_from_sovereign_state(state, delta_S)

    # Feed into existing agentic pipeline
    decision = confidence_gate.evaluate(signals)
    contract = safety_evaluator.evaluate(coherence)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from agentic.agentic_framework.confidence_gate import ConfidenceSignals

# Shared sovereign constants (Phase S1 — single source of truth)
from agentic.sovereign_constants import (
    BHAVA_START, BHAVA_END,
    KOSHA_START, KOSHA_END,
    VRITTI_START, VRITTI_END,
    GUNA_START, GUNA_END,
    RESERVED_START, RESERVED_END,
    VRITTI_FACT, VRITTI_ERROR, VRITTI_IMAGINATION, VRITTI_VOID, VRITTI_MEMORY,
    GUNA_LUCIDITY, GUNA_ACTIVITY, GUNA_STABILITY,
    GUNA_VELOCITY, GUNA_ACCEL, GUNA_STABLE,
    KOSHA_MATERIAL, KOSHA_VITAL, KOSHA_MENTAL,
    KOSHA_INTELLECTUAL, KOSHA_BLISSFUL,
)


# =============================================================================
# Tensor → Float Extraction (torch-free)
# =============================================================================

def _to_floats(tensor_or_list: Any) -> List[float]:
    """
    Convert a tensor slice or list to plain Python floats.

    Handles:
    - torch.Tensor (calls .detach().cpu().tolist())
    - list/tuple (passthrough)
    - Already-extracted floats from diagnostics dicts
    """
    if isinstance(tensor_or_list, (list, tuple)):
        return [float(x) for x in tensor_or_list]
    # torch.Tensor path
    if hasattr(tensor_or_list, 'detach'):
        return [float(x) for x in tensor_or_list.detach().cpu().tolist()]
    return [float(tensor_or_list)]


def _extract_slices(
    state: Any,
    batch_idx: int = 0,
) -> Tuple[List[float], List[float], List[float]]:
    """
    Extract Kosha, Vritti, Guna slices from a 32D state tensor or list.

    Args:
        state: [B, 32] tensor, [32] tensor, or list of 32 floats
        batch_idx: Which batch element to use (default 0)

    Returns:
        (kosha_5, vritti_5, guna_6) as lists of floats
    """
    # Handle batched tensor [B, 32]
    if hasattr(state, 'dim'):
        if state.dim() == 2:
            state = state[batch_idx]
        vals = state.detach().cpu().tolist()
    elif isinstance(state, (list, tuple)):
        vals = [float(x) for x in state]
    else:
        raise TypeError(f"Expected tensor or list, got {type(state)}")

    if len(vals) < GUNA_END:
        raise ValueError(f"State must have >= {GUNA_END} dims, got {len(vals)}")

    kosha = vals[KOSHA_START:KOSHA_END]
    vritti = vals[VRITTI_START:VRITTI_END]
    guna = vals[GUNA_START:GUNA_END]
    return kosha, vritti, guna


# =============================================================================
# Vritti → Confidence Mapping
# =============================================================================
#
# Vritti tracks epistemic reliability — exactly what ConfidenceSignals needs.
#
# Mapping rationale:
#   FACT (Pramana)       → high quality_score, high correctness
#   ERROR (Viparyaya)    → high prediction_reversal_risk, low correctness
#   IMAGINATION (Vikalpa)→ moderate quality, low correctness
#   VOID (Nidra)         → low everything (absence of content)
#   MEMORY (Smriti)      → moderate quality (recall, not fresh reasoning)
#

def _vritti_to_confidence(vritti: List[float]) -> Dict[str, float]:
    """
    Convert 5D Vritti activations to confidence signal components.

    Vrittis are softmax-normalized (probabilities), so they sum to ~1.0.

    Returns dict with:
        quality_score: High when FACT dominates, low when ERROR/VOID
        correctness_score: FACT activation directly
        prediction_reversal_risk: ERROR + high delta between FACT and others
        coherence_score: 1 - (ERROR + VOID) — coherent when not wrong or empty
    """
    fact = vritti[VRITTI_FACT]
    error = vritti[VRITTI_ERROR]
    imagination = vritti[VRITTI_IMAGINATION]
    void = vritti[VRITTI_VOID]
    memory = vritti[VRITTI_MEMORY]

    # quality_score: FACT contributes positively, ERROR and VOID negatively
    # MEMORY is moderate (recalling is okay but not as good as fresh reasoning)
    quality_score = fact * 1.0 + memory * 0.6 + imagination * 0.4 - error * 0.5 - void * 0.3
    quality_score = max(0.0, min(1.0, quality_score))

    # correctness_score: direct FACT probability
    correctness_score = max(0.0, min(1.0, fact))

    # prediction_reversal_risk: ERROR is the primary driver
    # Also high when IMAGINATION dominates (speculative, not grounded)
    reversal_risk = error * 1.0 + imagination * 0.3
    reversal_risk = max(0.0, min(1.0, reversal_risk))

    # coherence_score: coherent when not in ERROR or VOID states
    coherence_score = 1.0 - (error + void)
    coherence_score = max(0.0, min(1.0, coherence_score))

    return {
        'quality_score': quality_score,
        'correctness_score': correctness_score,
        'prediction_reversal_risk': reversal_risk,
        'coherence_score': coherence_score,
    }


# =============================================================================
# Kosha → Budget/Complexity Mapping
# =============================================================================
#
# Kosha tracks processing depth — maps to how much compute the task requires.
#
# Mapping rationale:
#   MATERIAL-dominant   → low complexity (surface syntax)
#   MENTAL-dominant     → moderate complexity (semantic)
#   INTELLECTUAL-dominant → high complexity (deep reasoning)
#   BLISSFUL-dominant   → integration task (high completeness)
#

def _kosha_to_budget(kosha: List[float]) -> Dict[str, float]:
    """
    Convert 5D Kosha activations to budget/complexity signals.

    Koshas may be sigmoid (independent, v2.2.5) or softmax (legacy).

    Returns dict with:
        action_complexity: Higher when deeper sheaths are active
        completeness_score: Higher when BLISSFUL (integration) is active
    """
    material = kosha[KOSHA_MATERIAL]
    vital = kosha[KOSHA_VITAL]
    mental = kosha[KOSHA_MENTAL]
    intellectual = kosha[KOSHA_INTELLECTUAL]
    blissful = kosha[KOSHA_BLISSFUL]

    # action_complexity: weighted sum favoring deeper sheaths
    # Material = surface (low complexity), Intellectual = deep (high complexity)
    complexity = (
        material * 0.1 +
        vital * 0.2 +
        mental * 0.4 +
        intellectual * 0.7 +
        blissful * 0.5  # Integration is moderately complex
    )
    # Normalize: if all sheaths are at 1.0 (sigmoid mode), max = 1.9
    # Scale to [0, 1] range
    action_complexity = max(0.0, min(1.0, complexity / 1.0))

    # completeness_score: integration sheath signals holistic processing
    completeness_score = max(0.0, min(1.0, blissful * 0.6 + intellectual * 0.3 + mental * 0.1))

    return {
        'action_complexity': action_complexity,
        'completeness_score': completeness_score,
    }


# =============================================================================
# Guna → Stability/Trajectory Mapping
# =============================================================================
#
# Guna tracks energy dynamics — maps to trajectory stability signals.
#
# Mapping rationale:
#   LUCIDITY (Sattva)   → high stability, high consistency
#   ACTIVITY (Rajas)    → high volatility, moderate stability
#   STABILITY (Tamas)   → low volatility but also low adaptability
#   VELOCITY            → state change rate → volatility
#   ACCEL               → acceleration of change → instability risk
#   STABLE              → direct stability measure
#

def _guna_to_stability(
    guna: List[float],
    delta_norm: float = 0.0,
) -> Dict[str, float]:
    """
    Convert 6D Guna activations + delta norm to stability signals.

    Gunas are sigmoid-normalized (independent [0, 1]).

    Args:
        guna: 6D Guna activations
        delta_norm: L2 norm of ΔS (full 32D delta), measures state change magnitude

    Returns dict with:
        volatility_index: High when ACTIVITY, VELOCITY, ACCEL are high
        session_stability: High when LUCIDITY and STABLE are high
        trajectory_confidence: Inverse of volatility, boosted by LUCIDITY
        internal_consistency: LUCIDITY - ACTIVITY balance
        identity_stability: STABLE measure + low VELOCITY
    """
    lucidity = guna[GUNA_LUCIDITY]
    activity = guna[GUNA_ACTIVITY]
    stability_tamas = guna[GUNA_STABILITY]
    velocity = guna[GUNA_VELOCITY]
    accel = guna[GUNA_ACCEL]
    stable = guna[GUNA_STABLE]

    # volatility_index: driven by ACTIVITY, VELOCITY, ACCEL
    # delta_norm contributes — large state changes mean volatile
    volatility = (
        activity * 0.3 +
        velocity * 0.3 +
        accel * 0.2 +
        min(1.0, delta_norm * 0.5) * 0.2  # Normalize delta_norm contribution
    )
    volatility_index = max(0.0, min(1.0, volatility))

    # session_stability: LUCIDITY and STABLE are positive, ACTIVITY is negative
    session_stability = (
        lucidity * 0.4 +
        stable * 0.4 +
        stability_tamas * 0.1 -
        activity * 0.1
    )
    session_stability = max(0.0, min(1.0, session_stability))

    # trajectory_confidence: inverse of volatility, boosted by lucidity
    trajectory_confidence = (1.0 - volatility_index) * 0.6 + lucidity * 0.4
    trajectory_confidence = max(0.0, min(1.0, trajectory_confidence))

    # internal_consistency: LUCIDITY vs ACTIVITY balance
    # High lucidity + low activity = internally consistent
    internal_consistency = lucidity * 0.6 + (1.0 - activity) * 0.2 + stable * 0.2
    internal_consistency = max(0.0, min(1.0, internal_consistency))

    # identity_stability: STABLE measure + low velocity/accel
    identity_stability = (
        stable * 0.5 +
        (1.0 - velocity) * 0.3 +
        (1.0 - accel) * 0.2
    )
    identity_stability = max(0.0, min(1.0, identity_stability))

    return {
        'volatility_index': volatility_index,
        'session_stability': session_stability,
        'trajectory_confidence': trajectory_confidence,
        'internal_consistency': internal_consistency,
        'identity_stability': identity_stability,
    }


# =============================================================================
# Public API: signals_from_sovereign_state
# =============================================================================

def signals_from_sovereign_state(
    state: Any,
    delta_S: Any = None,
    batch_idx: int = 0,
) -> ConfidenceSignals:
    """
    Build ConfidenceSignals from 32D Sovereign State tensor.

    This is the main bridge function. It follows the same pattern as
    signals_from_critique() and signals_from_coherence_metrics() in
    confidence_gate.py, but sources from the tensor-level control plane.

    Mapping:
        Vritti [17:22] → quality_score, correctness_score,
                         prediction_reversal_risk, coherence_score
        Kosha  [12:17] → action_complexity, completeness_score
        Guna   [22:28] → volatility_index, session_stability,
                         trajectory_confidence, internal_consistency

    Args:
        state: [B, 32] or [32] Sovereign State tensor, or list of 32 floats
        delta_S: Optional [B, 32] or [32] state delta tensor (for volatility)
        batch_idx: Which batch element to use (default 0)

    Returns:
        ConfidenceSignals populated from Sovereign State control plane

    Example:
        >>> outputs = model(input_ids)
        >>> signals = signals_from_sovereign_state(outputs['state'], outputs['delta_S'])
        >>> merged = merge_signals(signals, signals_from_critique(critique))
        >>> decision = confidence_gate.evaluate(merged)
    """
    kosha, vritti, guna = _extract_slices(state, batch_idx)

    # Compute delta norm if provided
    delta_norm = 0.0
    if delta_S is not None:
        if hasattr(delta_S, 'norm'):
            # torch.Tensor
            if delta_S.dim() == 2:
                delta_norm = delta_S[batch_idx].norm().item()
            else:
                delta_norm = delta_S.norm().item()
        elif isinstance(delta_S, (list, tuple)):
            delta_norm = sum(x ** 2 for x in delta_S) ** 0.5

    # Convert each control plane group
    vritti_signals = _vritti_to_confidence(vritti)
    kosha_signals = _kosha_to_budget(kosha)
    guna_signals = _guna_to_stability(guna, delta_norm)

    return ConfidenceSignals(
        # From Vritti (epistemic reliability)
        quality_score=vritti_signals['quality_score'],
        correctness_score=vritti_signals['correctness_score'],
        prediction_reversal_risk=vritti_signals['prediction_reversal_risk'],
        coherence_score=vritti_signals['coherence_score'],
        # From Kosha (processing depth)
        action_complexity=kosha_signals['action_complexity'],
        completeness_score=kosha_signals['completeness_score'],
        # From Guna (energy dynamics)
        volatility_index=guna_signals['volatility_index'],
        session_stability=guna_signals['session_stability'],
        trajectory_confidence=guna_signals['trajectory_confidence'],
        internal_consistency=guna_signals['internal_consistency'],
        # Relevance not derivable from state — leave at default
        relevance_score=0.5,
        # Goal alignment not derivable from state — leave at default
        goal_alignment=0.5,
        # Reversibility is action-specific, not state-derived
        action_reversibility=1.0,
    )


# =============================================================================
# Public API: coherence_from_sovereign_state
# =============================================================================

@dataclass
class SovereignCoherenceState:
    """
    CoherenceState-compatible wrapper around Sovereign State signals.

    SafetyContractEvaluator.evaluate() reads:
        coherence_state.current_metrics.internal_consistency
        coherence_state.current_metrics.goal_alignment
        coherence_state.current_metrics.prediction_reversal_risk
        coherence_state.current_metrics.identity_stability

    This class provides that interface sourced from the 32D tensor.
    """
    internal_consistency: float = 0.5
    goal_alignment: float = 0.5
    prediction_reversal_risk: float = 0.5
    identity_stability: float = 0.5

    @property
    def current_metrics(self) -> "SovereignCoherenceState":
        """SafetyContractEvaluator reads coherence_state.current_metrics."""
        return self


def coherence_from_sovereign_state(
    state: Any,
    delta_S: Any = None,
    batch_idx: int = 0,
) -> SovereignCoherenceState:
    """
    Build SafetyContract-compatible coherence state from 32D Sovereign State.

    SafetyContractEvaluator.evaluate() expects a coherence_state with:
        .current_metrics.internal_consistency
        .current_metrics.goal_alignment
        .current_metrics.prediction_reversal_risk
        .current_metrics.identity_stability

    This function derives those from the Guna and Vritti control plane.

    Mapping:
        internal_consistency  ← Guna LUCIDITY vs ACTIVITY balance
        goal_alignment        ← left at default (requires goal context)
        prediction_reversal_risk ← Vritti ERROR activation
        identity_stability    ← Guna STABLE + low VELOCITY

    Args:
        state: [B, 32] or [32] Sovereign State tensor
        delta_S: Optional state delta for volatility contribution
        batch_idx: Which batch element to use

    Returns:
        SovereignCoherenceState compatible with SafetyContractEvaluator.evaluate()

    Example:
        >>> coherence = coherence_from_sovereign_state(outputs['state'], outputs['delta_S'])
        >>> contract = safety_evaluator.evaluate(coherence)
        >>> if not contract.eligible:
        ...     print(contract.get_rejection_summary())
    """
    _, vritti, guna = _extract_slices(state, batch_idx)

    delta_norm = 0.0
    if delta_S is not None:
        if hasattr(delta_S, 'norm'):
            if delta_S.dim() == 2:
                delta_norm = delta_S[batch_idx].norm().item()
            else:
                delta_norm = delta_S.norm().item()
        elif isinstance(delta_S, (list, tuple)):
            delta_norm = sum(x ** 2 for x in delta_S) ** 0.5

    vritti_signals = _vritti_to_confidence(vritti)
    guna_signals = _guna_to_stability(guna, delta_norm)

    return SovereignCoherenceState(
        internal_consistency=guna_signals['internal_consistency'],
        goal_alignment=0.5,  # Requires goal context, not derivable from state
        prediction_reversal_risk=vritti_signals['prediction_reversal_risk'],
        identity_stability=guna_signals['identity_stability'],
    )
