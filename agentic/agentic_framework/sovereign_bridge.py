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
        entropy_from_sovereign_state,
        vritti_from_sovereign_state,
    )

    # In inference loop, after model forward pass:
    outputs = model(input_ids)
    state = outputs['state']        # [B, 32] full Sovereign State
    delta_S = outputs['delta_S']    # [B, 32] full state delta

    # Convert to agentic signals
    signals = signals_from_sovereign_state(state, delta_S)
    coherence = coherence_from_sovereign_state(state, delta_S)
    entropy_result = entropy_from_sovereign_state(state)

    # Feed into existing agentic pipeline
    decision = confidence_gate.evaluate(signals)
    contract = safety_evaluator.evaluate(coherence)
    # entropy_result is attached to AuthorizationRequest/MCPToolCall by
    # whichever caller builds the governance request.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

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

if TYPE_CHECKING:
    from agentic.entropy.types import EntropyResult, KoshaProfile
    from agentic.chitta_vritti.types import ChittaVrittiResult


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


# =============================================================================
# Public API: entropy_from_sovereign_state
# =============================================================================
#
# Translate 32D Sovereign State into a canonical EntropyResult from
# agentic/entropy/EntropyEngine. Parallel to signals_from_sovereign_state()
# and coherence_from_sovereign_state() — same input, different governance-side
# representation.
#
# Mapping rationale (direct, no fabrication):
#   Guna slice [22:28]:
#     guna[GUNA_LUCIDITY]  = lucidity        → GunaProfile.sattva
#     guna[GUNA_ACTIVITY]  = activity        → GunaProfile.rajas
#     guna[GUNA_STABILITY] = stability_tamas → GunaProfile.tamas
#     (velocity/accel/stable describe dynamics, not the 3-guna distribution,
#      so they are deliberately NOT included in GunaProfile)
#
#   Kosha slice [12:17] → source KoshaProfile:
#     kosha[KOSHA_MATERIAL]     → annamaya   (physical sheath)
#     kosha[KOSHA_VITAL]        → pranamaya  (energy/vital sheath)
#     kosha[KOSHA_MENTAL]       → manomaya   (mental sheath)
#     kosha[KOSHA_INTELLECTUAL] → vijnanamaya (wisdom sheath)
#     kosha[KOSHA_BLISSFUL]     → anandamaya  (bliss sheath)
#
# Target kosha is OPTIONAL:
#   - If caller supplies target_kosha, full kosha entropy (source/target
#     distance) is evaluated by the engine.
#   - If target_kosha is None, kosha entropy is not computed — the engine
#     naturally defaults to 0.0 for kosha when a target is absent. This is
#     honest behavior: at single-state inference time we have only the
#     current state's kosha and no natural target without extra context.
#
# Cross-domain entropy is never computed here — it requires source and
# target DomainProfile structures that the 32D state does not carry.
#
# This helper is deterministic, side-effect-free, and uses the same
# _extract_slices() indexing as the other bridge functions.
#

# Module-level cache of EntropyEngine instances by tier name.
# EntropyEngine is a thin stateless wrapper around TierConfig; caching
# avoids reconstructing it per call and keeps the function hot-path cheap.
_ENTROPY_ENGINE_CACHE: Dict[str, Any] = {}


def _get_entropy_engine(tier_name: str) -> Any:
    """Get or create a cached EntropyEngine for the given tier name."""
    engine = _ENTROPY_ENGINE_CACHE.get(tier_name)
    if engine is None:
        from agentic.entropy.entropy_engine import create_engine_for_tier
        engine = create_engine_for_tier(tier_name)
        _ENTROPY_ENGINE_CACHE[tier_name] = engine
    return engine


def entropy_from_sovereign_state(
    state: Any,
    delta_S: Any = None,
    batch_idx: int = 0,
    tier_name: str = "enterprise_chat",
    target_kosha: Optional["KoshaProfile"] = None,
) -> "EntropyResult":
    """
    Build EntropyResult from a 32D Sovereign State tensor.

    Parallel to signals_from_sovereign_state() and
    coherence_from_sovereign_state(). Uses the same state layout and the
    same slice extraction — translates raw Kosha/Guna activations into
    the canonical entropy engine input types and invokes
    EntropyEngine.evaluate().

    Mapping:
        Guna  [22:28] first 3 dims → GunaProfile(sattva, rajas, tamas)
        Kosha [12:17]              → source KoshaProfile

    Args:
        state: [B, 32] or [32] Sovereign State tensor, or list of 32 floats.
        delta_S: Unused here (kept for signature parity with sibling
            bridge functions; reserved for future velocity-aware entropy).
        batch_idx: Which batch element to use when state is batched.
        tier_name: Tier configuration selector ("enterprise_search",
            "enterprise_chat", or "consumer"). Controls gate behavior
            (DIAGNOSTIC_ONLY / MODULATION_ONLY / FULL_GATING) but does
            not fabricate thresholds.
        target_kosha: Optional target KoshaProfile. When supplied, the
            engine evaluates source→target kosha distance. When absent,
            kosha entropy is not computed (honest for single-state
            inference where no natural target exists yet).

    Returns:
        EntropyResult carrying guna_entropy, kosha_entropy (zero when
        target_kosha is None), combined_entropy, gate, mode, and trace.

    Example:
        >>> outputs = model(input_ids)
        >>> entropy_result = entropy_from_sovereign_state(outputs['state'])
        >>> request = AuthorizationRequest(
        ...     actor_id="agent-1",
        ...     action_type="file_read",
        ...     entropy_result=entropy_result,
        ... )
    """
    # Lazy import to keep module load cheap and avoid paying the entropy
    # import cost on code paths that only need ConfidenceSignals.
    from agentic.entropy.types import GunaProfile, KoshaProfile

    kosha, _, guna = _extract_slices(state, batch_idx)

    # Guna: first three dims of the 6D slice are the canonical 3-guna
    # distribution (sattva/rajas/tamas). The remaining three dims
    # (velocity/accel/stable) are dynamics descriptors and are deliberately
    # not part of GunaProfile.
    guna_profile = GunaProfile(
        sattva=max(0.0, min(1.0, float(guna[GUNA_LUCIDITY]))),
        rajas=max(0.0, min(1.0, float(guna[GUNA_ACTIVITY]))),
        tamas=max(0.0, min(1.0, float(guna[GUNA_STABILITY]))),
    )

    # Kosha: 5D slice maps directly to the 5 sheaths in canonical order.
    source_kosha = KoshaProfile(
        annamaya=max(0.0, min(1.0, float(kosha[KOSHA_MATERIAL]))),
        pranamaya=max(0.0, min(1.0, float(kosha[KOSHA_VITAL]))),
        manomaya=max(0.0, min(1.0, float(kosha[KOSHA_MENTAL]))),
        vijnanamaya=max(0.0, min(1.0, float(kosha[KOSHA_INTELLECTUAL]))),
        anandamaya=max(0.0, min(1.0, float(kosha[KOSHA_BLISSFUL]))),
    )

    engine = _get_entropy_engine(tier_name)

    # Only pass kosha_target when the caller supplied one. When None,
    # the engine's evaluate() treats kosha entropy as not computed
    # (natural default, no fabrication).
    if target_kosha is not None:
        return engine.evaluate(
            guna_profile=guna_profile,
            kosha_source=source_kosha,
            kosha_target=target_kosha,
        )
    return engine.evaluate(guna_profile=guna_profile)


# =============================================================================
# Public API: vritti_from_sovereign_state
# =============================================================================
#
# Translate 32D Sovereign State into a canonical ChittaVrittiResult from
# agentic/chitta_vritti/ChittaVrittiEngine. Parallel to the sibling helpers
# above — same input, different governance-side representation.
#
# Mapping rationale (direct, no fabrication):
#
#   Representation layers (cross-layer coherence is what the engine checks):
#     Bhava  [0:12]  → semantic_rep     (intent / meaning vector)
#     Kosha  [12:17] → structural_rep   (processing-depth structure)
#     ΔS Bhava slice → temporal_rep     (only when delta_S is supplied)
#     phonemic_rep   → None             (sovereign state has no acoustic
#                                        or surface-token signal; honest
#                                        absence, not fabricated)
#
#   Scalar signals:
#     entropy             ← normalized Shannon entropy of Vritti[17:22]
#                           treated as a probability distribution (uniform
#                           slice → entropy≈1, one-hot slice → entropy≈0)
#     motion              ← min(1.0, ‖ΔS‖₂); 0.0 if delta_S absent
#     confidence          ← quality_score from _vritti_to_confidence(vritti)
#                           (reuses the existing sovereign-bridge mapping,
#                           not a new heuristic)
#     temporal_continuity ← 1.0 - motion
#
# Layer presence:
#   - delta_S absent → 2 layers present (semantic + structural).
#     count_missing_layers() == 2, so the engine runs full_computation
#     on two layers (not nidra fast-path, which needs >=3 missing).
#   - delta_S present → 3 layers present (+ temporal). Still full
#     computation (phonemic alone missing, count_missing == 1).
#   - Fast-path pramana requires all_layers_present(), so the bridge
#     never triggers it — cross-layer coherence is always computed
#     honestly from what sovereign state actually provides.
#
# Engine lifecycle:
#   ChittaVrittiEngine holds per-session smriti state. Bridge calls
#   describe independent inference snapshots, so we construct a fresh
#   engine per call to avoid smriti bleed across unrelated requests.
#   Callers who need turn-to-turn smriti should hold their own
#   long-lived ChittaVrittiEngine and call .compute() directly rather
#   than going through this bridge.
#

def _vritti_slice_entropy(vritti: List[float]) -> float:
    """Normalized Shannon entropy of the 5D Vritti slice, in [0, 1].

    Treats the slice as a probability distribution (re-normalizing
    defensively, since sovereign state may ship it softmax-normalized
    or raw). Uniform → 1.0, one-hot → 0.0, all-zero → 1.0 (max
    uncertainty, honest for an empty/void signal).
    """
    import math

    total = sum(max(0.0, v) for v in vritti)
    if total <= 0.0:
        return 1.0

    probs = [max(0.0, v) / total for v in vritti]
    log_n = math.log(len(probs)) if len(probs) > 1 else 1.0

    h = 0.0
    for p in probs:
        if p > 0.0:
            h -= p * math.log(p)

    return max(0.0, min(1.0, h / log_n))


def vritti_from_sovereign_state(
    state: Any,
    delta_S: Any = None,
    batch_idx: int = 0,
    tier: str = "consumer",
) -> "ChittaVrittiResult":
    """
    Build a ChittaVrittiResult from a 32D Sovereign State tensor.

    Parallel to signals_from_sovereign_state(), coherence_from_sovereign_state(),
    and entropy_from_sovereign_state(). Uses the same state layout and the
    same slice extraction — translates raw Bhava/Kosha/Vritti/ΔS activations
    into ChittaVrittiInputs and invokes ChittaVrittiEngine.compute().

    Mapping:
        Bhava  [0:12]  → semantic_rep
        Kosha  [12:17] → structural_rep
        ΔS Bhava[0:12] → temporal_rep (only if delta_S is provided)
        Vritti [17:22] → entropy signal (Shannon entropy of the slice)
        Vritti [17:22] → confidence signal (via _vritti_to_confidence)
        ΔS norm        → motion signal
        1 - motion     → temporal_continuity signal
        phonemic_rep   → None (not derivable from sovereign state)

    Args:
        state: [B, 32] or [32] Sovereign State tensor, or list of 32 floats.
        delta_S: Optional [B, 32] or [32] state delta. When present, its
            Bhava slice becomes temporal_rep and its L2 norm drives motion.
        batch_idx: Which batch element to use when state is batched.
        tier: "consumer" or "enterprise" — selects ChittaVrittiEngine config
            (threshold tightness, penalty weights, decay rate).

    Returns:
        ChittaVrittiResult carrying coherence, the 5-mode vritti distribution
        (pramana/viparyaya/vikalpa/smrti/nidra), score, dominant_vritti,
        fractures, primary_fracture, explanation, and fast_path_used.

    Example:
        >>> outputs = model(input_ids)
        >>> cv_result = vritti_from_sovereign_state(
        ...     outputs['state'], outputs['delta_S'],
        ... )
        >>> # Feed into the vritti signal adapter:
        >>> from agentic.agentic_framework.signal_adapters.vritti_adapter \\
        ...     import resolve_vritti_signal
        >>> resolution = resolve_vritti_signal(vritti_result=cv_result)
        >>> assert resolution.source.value == "real"
    """
    import numpy as np

    # Lazy imports: keep module load cheap and avoid paying numpy /
    # chitta_vritti import cost on code paths that only need
    # ConfidenceSignals or entropy helpers.
    from agentic.chitta_vritti.types import ChittaVrittiInputs
    from agentic.chitta_vritti.engine import create_engine

    # --- Extract 32D state → raw lists ---
    # Reuse _extract_slices for kosha/vritti/guna, and pull Bhava inline
    # (the existing helper doesn't surface Bhava since other bridges
    # don't need it).
    if hasattr(state, 'dim'):
        if state.dim() == 2:
            state_vec = state[batch_idx]
        else:
            state_vec = state
        vals = state_vec.detach().cpu().tolist()
    elif isinstance(state, (list, tuple)):
        vals = [float(x) for x in state]
    else:
        raise TypeError(f"Expected tensor or list, got {type(state)}")

    if len(vals) < GUNA_END:
        raise ValueError(
            f"State must have >= {GUNA_END} dims, got {len(vals)}"
        )

    bhava = vals[BHAVA_START:BHAVA_END]
    kosha = vals[KOSHA_START:KOSHA_END]
    vritti_slice = vals[VRITTI_START:VRITTI_END]

    # --- Representation layers ---
    semantic_rep = np.asarray(bhava, dtype=float)
    structural_rep = np.asarray(kosha, dtype=float)

    # --- Delta processing: temporal_rep + motion ---
    temporal_rep = None
    delta_norm = 0.0
    if delta_S is not None:
        # Extract delta values
        if hasattr(delta_S, 'dim'):
            if delta_S.dim() == 2:
                delta_vec = delta_S[batch_idx]
            else:
                delta_vec = delta_S
            delta_vals = delta_vec.detach().cpu().tolist()
            if hasattr(delta_vec, 'norm'):
                delta_norm = float(delta_vec.norm().item())
            else:
                delta_norm = sum(x ** 2 for x in delta_vals) ** 0.5
        elif isinstance(delta_S, (list, tuple)):
            delta_vals = [float(x) for x in delta_S]
            delta_norm = sum(x ** 2 for x in delta_vals) ** 0.5
        else:
            raise TypeError(
                f"delta_S must be tensor or list, got {type(delta_S)}"
            )

        if len(delta_vals) >= BHAVA_END:
            temporal_rep = np.asarray(
                delta_vals[BHAVA_START:BHAVA_END], dtype=float,
            )

    # --- Scalar signals (all clamped to [0, 1]) ---
    entropy_signal = _vritti_slice_entropy(vritti_slice)
    motion_signal = max(0.0, min(1.0, delta_norm))
    vritti_conf = _vritti_to_confidence(vritti_slice)
    confidence_signal = vritti_conf['quality_score']
    temporal_continuity_signal = max(0.0, min(1.0, 1.0 - motion_signal))

    inputs = ChittaVrittiInputs(
        phonemic_rep=None,
        semantic_rep=semantic_rep,
        structural_rep=structural_rep,
        temporal_rep=temporal_rep,
        entropy=entropy_signal,
        motion=motion_signal,
        confidence=confidence_signal,
        temporal_continuity=temporal_continuity_signal,
    )

    # Fresh engine per call — see module-level note on engine lifecycle.
    engine = create_engine(tier=tier)
    return engine.compute(inputs)


# =============================================================================
# Phase S3: Diagnostic context forwarding
# =============================================================================

@dataclass
class SovereignDiagnosticContext:
    """Forwarded reasoning-kernel diagnostics for governance consumption.

    This is the governance-side view of sovereign reasoning diagnostics.
    Populated from inference_bridge ProjectionMetadata or from direct
    kernel diagnostic dicts. All fields are plain Python types.

    Bounded governance effects:
    - mauna_active → adds caution reason code + confirmation pressure
    - opb_unstable → informational audit metadata
    - vritti_rejection → informational audit metadata
    - All other fields are audit/replay enrichment only
    """
    # Mauna / silence
    mauna_active: bool = False

    # Reasoning mode
    active_intervention: Optional[str] = None
    active_logic_template: Optional[str] = None

    # State summary
    dominant_bhava: Optional[str] = None
    active_kosha: Optional[str] = None
    vritti_state: Optional[str] = None
    vritti_rejection: bool = False

    # OPB stability
    opb_active_locks: int = 0
    opb_locked_dims: Tuple[str, ...] = ()
    opb_unstable: bool = False  # True if dimension churn detected

    # Entropy direction
    entropy_delta: float = 0.0

    # Provenance
    source: str = "unknown"
    available: bool = False

    def to_audit_dict(self) -> Dict[str, Any]:
        """Serialize for governance audit."""
        return {
            "mauna_active": self.mauna_active,
            "active_intervention": self.active_intervention,
            "active_logic_template": self.active_logic_template,
            "dominant_bhava": self.dominant_bhava,
            "active_kosha": self.active_kosha,
            "vritti_state": self.vritti_state,
            "vritti_rejection": self.vritti_rejection,
            "opb_active_locks": self.opb_active_locks,
            "opb_locked_dims": list(self.opb_locked_dims),
            "opb_unstable": self.opb_unstable,
            "entropy_delta": round(self.entropy_delta, 6),
            "source": self.source,
            "available": self.available,
        }



# =============================================================================
# Phase S4: Guna Anomaly Context
# =============================================================================

@dataclass
class GunaAnomalyContext:
    """Forwarded Guna anomaly signals for governance consumption.

    Populated from inference_bridge ProjectionMetadata.guna_anomalies
    or from direct GunaMonitor output.

    Bounded governance effects:
    - collapse → confidence penalty (max 0.03) + escalation bias
    - oscillation → confidence penalty (max 0.02)
    - stagnation → informational audit metadata only
    """
    collapse: bool = False
    oscillation: bool = False
    stagnation: bool = False
    dominant_guna: str = "unknown"
    anomaly_count: int = 0
    available: bool = False

    def to_audit_dict(self) -> Dict[str, Any]:
        """Serialize for governance audit."""
        return {
            "collapse": self.collapse,
            "oscillation": self.oscillation,
            "stagnation": self.stagnation,
            "dominant_guna": self.dominant_guna,
            "anomaly_count": self.anomaly_count,
            "available": self.available,
        }


def guna_anomalies_from_projection(
    projection_metadata: Optional[Dict[str, Any]] = None,
    monitor_output: Optional[Dict[str, Any]] = None,
) -> GunaAnomalyContext:
    """Build GunaAnomalyContext from bridge metadata or monitor output.

    Args:
        projection_metadata: Dict from SovereignProjectionResult.metadata.to_dict()
            which may contain embedded guna_anomalies.
        monitor_output: Dict directly from GunaMonitor (check_anomalies + dominant).

    Returns:
        GunaAnomalyContext. If no data → available=False.
    """
    data = None

    # Prefer direct monitor output
    if monitor_output is not None:
        data = monitor_output
    elif projection_metadata is not None:
        data = projection_metadata.get("guna_anomalies")

    if data is None:
        return GunaAnomalyContext()

    try:
        collapse = bool(data.get("collapse", False))
        oscillation = bool(data.get("oscillation", False))
        stagnation = bool(data.get("stagnation", False))
        dominant = str(data.get("dominant_guna", "unknown"))
        count = sum([collapse, oscillation, stagnation])

        return GunaAnomalyContext(
            collapse=collapse,
            oscillation=oscillation,
            stagnation=stagnation,
            dominant_guna=dominant,
            anomaly_count=count,
            available=True,
        )
    except Exception:
        return GunaAnomalyContext()


# =============================================================================
# Phase S4: Bhava Transition Audit Context
# =============================================================================

def bhava_transition_from_diagnostics(
    previous_bhava: Optional[str],
    current_bhava: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Evaluate Bhava transition using pure-Python priors.

    Returns audit dict if both bhavas are available, None otherwise.
    This is audit-only metadata — no governance behavior change.
    """
    if previous_bhava is None or current_bhava is None:
        return None

    try:
        from agentic.sovereign_bhava_priors import evaluate_bhava_transition
        audit = evaluate_bhava_transition(previous_bhava, current_bhava)
        if audit.available:
            return audit.to_audit_dict()
        return None
    except Exception:
        return None


# =============================================================================
# Phase S4: Governor Telemetry Context
# =============================================================================

def governor_telemetry_from_projection(
    projection_metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Extract governor telemetry from bridge metadata.

    Returns the governor telemetry dict if present, None otherwise.
    This is audit-only metadata — no governance behavior change.
    """
    if projection_metadata is None:
        return None
    try:
        telem = projection_metadata.get("governor_telemetry")
        if telem is not None and isinstance(telem, dict):
            return dict(telem)
        return None
    except Exception:
        return None


# =============================================================================
# Phase S3: Diagnostic context forwarding (unchanged)
# =============================================================================

def diagnostics_from_projection(
    projection_metadata: Optional[Dict[str, Any]] = None,
    kernel_diagnostics: Optional[Dict[str, Any]] = None,
    kernel_state: Optional[Dict[str, Any]] = None,
) -> SovereignDiagnosticContext:
    """Build SovereignDiagnosticContext from bridge projection or kernel output.

    This is the main entry point for the governance layer to obtain
    reasoning diagnostics. It accepts multiple source types for flexibility:

    1. projection_metadata: Dict from SovereignProjectionResult.metadata.to_dict()
       which may contain embedded reasoning_diagnostics.
    2. kernel_diagnostics: Dict from SovereignReasoningKernel.intervene()['diagnostics'].
    3. kernel_state: Dict from SovereignReasoningKernel.get_diagnostics().

    If multiple sources are provided, they are merged (kernel > projection).

    Returns:
        SovereignDiagnosticContext with all available fields.
        If no data → available=False, all defaults.
    """
    if projection_metadata is None and kernel_diagnostics is None and kernel_state is None:
        return SovereignDiagnosticContext()

    try:
        from agentic.sovereign_diagnostics import (
            diagnostics_from_kernel_output,
            diagnostics_from_bridge_metadata,
        )

        # Prefer kernel output if available
        if kernel_diagnostics is not None or kernel_state is not None:
            diag = diagnostics_from_kernel_output(kernel_diagnostics, kernel_state)
        elif projection_metadata is not None:
            diag = diagnostics_from_bridge_metadata(projection_metadata)
        else:
            return SovereignDiagnosticContext()

        return SovereignDiagnosticContext(
            mauna_active=diag.mauna_active,
            active_intervention=diag.active_intervention,
            active_logic_template=diag.active_logic_template,
            dominant_bhava=diag.dominant_bhava,
            active_kosha=diag.active_kosha,
            vritti_state=diag.vritti_state,
            vritti_rejection=diag.vritti_rejection,
            opb_active_locks=diag.opb_active_locks,
            opb_locked_dims=diag.opb_locked_dims,
            opb_unstable=diag.opb_is_unstable,
            entropy_delta=diag.entropy_delta,
            source=diag.source,
            available=True,
        )
    except Exception:
        return SovereignDiagnosticContext()
