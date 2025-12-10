"""
Symbol-U Insight Window Gating System v1.0 (Phase 32)

Policy-layer deterministic gating system that uses Unified Consciousness Formula (UCF)
metrics to softly refine UI-level policy flags for therapeutic and identity-focused personas.

Key Features:
- Zero-LLM: Pure deterministic rule-based logic
- Observation-only: No changes to routing, mappers, coherence, or safety-critical logic
- UI-layer only: Influences presentation flags only, never pipeline behavior
- Domain/mode gated: Only active in therapy/identity domains + SMART_INSIGHT/DEEP_ADAPTIVE modes
- UCF-aware: Uses COI, CSI, CIP, entropy, and diagnostic tags from megafusion

Design Principles:
- Deterministic: Same inputs → same outputs always
- Graceful degradation: Returns closed window if data unavailable
- Non-invasive: Does not modify routing, TTOR, MLCR, mappers, Fusion, DHA
- Backward compatible: All existing tests remain green
- Observation-only: Purely informational, never behavior-changing

Usage:
    from symbolu.policy.insight_window_gating import compute_insight_window

    result = compute_insight_window(
        ucf_snapshot=ucf_snapshot,
        coherence_observation=obs,
        interaction_mode="smart_insight",
        domain="therapy"
    )

    if result.insight_window_open and result.insight_mode == "deep":
        # UI can enable deeper reflection features
        pass
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class InsightWindowResult:
    """
    Immutable result of insight window gating computation.

    Fields:
        insight_window_open: Whether the insight window is open for deeper reflection
        insight_depth: Numeric depth score [0.0, 1.0] indicating readiness level
        insight_mode: Classification of insight mode ("none" | "light" | "deep")
        insight_tags: Diagnostic tags describing the state (e.g., ["structural_alignment", "stable"])
        notes: Human-readable diagnostic notes explaining the gating decision
    """
    insight_window_open: bool
    insight_depth: float  # [0.0, 1.0]
    insight_mode: str  # "none" | "light" | "deep"
    insight_tags: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


def _clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """
    Clamp value to [min_val, max_val] range.

    Args:
        value: Value to clamp
        min_val: Minimum value (default 0.0)
        max_val: Maximum value (default 1.0)

    Returns:
        float: Clamped value
    """
    return max(min_val, min(max_val, value))


def compute_insight_window(
    *,
    ucf_snapshot: Optional[any] = None,
    coherence_observation: Optional[any] = None,
    interaction_mode: str,
    domain: str,
) -> InsightWindowResult:
    """
    Compute insight window gating result from UCF and coherence signals.

    This is the main deterministic gating function. It evaluates UCF megafusion
    indicators (COI, CSI, CIP, entropy, diagnostic tags) to determine if the
    system should expose deeper insight/reflection UI features.

    Canonical Deterministic Rules (v1.0):

    1. Domain + Mode Gate (HARD):
       - Only active in therapy/identity domains
       - Only active in SMART_INSIGHT/DEEP_ADAPTIVE modes
       - Otherwise → window closed, mode="none"

    2. Insight Window Openness (boolean):
       Window opens when:
       - COI ≥ 0.55 (structural coherence)
       - CSI ≥ 0.50 (temporal stability)
       - AND none of the following blocked:
         * drift_risk_band == "high"
         * entropy_band == "volatile"

    3. Insight Depth (0–1):
       Base formula:
       raw_depth = 0.40 * COI + 0.40 * CSI + 0.20 * CIP

       Modifications:
       - If entropy_band == "transitional" → reduce depth by 15%
       - If drift_risk_band == "moderate" → reduce depth by 10%
       - If COI < 0.45 → cap at 0.45

    4. Insight Mode Classification:
       - if insight_depth >= 0.70 → "deep"
       - elif insight_depth >= 0.40 → "light"
       - else → "none"

    5. Insight Tags (diagnostic-only):
       Based on UCF + semantic + entropy metrics:
       - "structural_alignment" if COI ≥ 0.65
       - "temporal_resilience" if CSI ≥ 0.65
       - "integration_ready" if CIP ≥ 0.60
       - "entropy_transitional" if entropy_band == "transitional"
       - "entropy_high" if entropy_band == "volatile"
       - "drift_caution" if drift_risk_band ≥ "moderate"

    Args:
        ucf_snapshot: UnifiedConsciousnessSnapshot from Phase 26 UCF computation
        coherence_observation: CoherenceObservation with UCF + coherence metrics
        interaction_mode: Active interaction mode ("analytics_only" | "smart_insight" | "deep_adaptive")
        domain: Domain identifier ("therapy" | "identity" | "trading" | etc.)

    Returns:
        InsightWindowResult with gating decision and diagnostic metadata

    Graceful Degradation:
        Returns closed window (insight_window_open=False, insight_mode="none")
        if UCF data is unavailable or domain/mode gates fail.

    Examples:
        >>> # High COI/CSI, therapy domain, smart_insight mode → window open, light mode
        >>> result = compute_insight_window(
        ...     ucf_snapshot=snapshot,  # COI=0.70, CSI=0.65, CIP=0.55
        ...     coherence_observation=obs,
        ...     interaction_mode="smart_insight",
        ...     domain="therapy"
        ... )
        >>> result.insight_window_open
        True
        >>> result.insight_mode
        'light'

        >>> # Low COI, trading domain → window closed
        >>> result = compute_insight_window(
        ...     ucf_snapshot=snapshot,  # COI=0.40, CSI=0.70
        ...     coherence_observation=obs,
        ...     interaction_mode="analytics_only",
        ...     domain="trading"
        ... )
        >>> result.insight_window_open
        False
    """
    notes = []
    tags = []

    # ========================================================================
    # STEP 1: DOMAIN + MODE GATE (HARD)
    # ========================================================================

    # Only active in therapy/identity domains
    therapy_or_identity = domain.lower() in ["therapy", "identity"]

    # Only active in SMART_INSIGHT or DEEP_ADAPTIVE modes
    smart_or_deep = interaction_mode.lower() in ["smart_insight", "deep_adaptive"]

    if not therapy_or_identity:
        notes.append("Domain gate failed: only therapy/identity domains supported")
        return InsightWindowResult(
            insight_window_open=False,
            insight_depth=0.0,
            insight_mode="none",
            insight_tags=[],
            notes=notes,
        )

    if not smart_or_deep:
        notes.append("Mode gate failed: only SMART_INSIGHT/DEEP_ADAPTIVE modes supported")
        return InsightWindowResult(
            insight_window_open=False,
            insight_depth=0.0,
            insight_mode="none",
            insight_tags=[],
            notes=notes,
        )

    notes.append(f"Domain gate passed: {domain}")
    notes.append(f"Mode gate passed: {interaction_mode}")

    # ========================================================================
    # STEP 2: EXTRACT UCF METRICS
    # ========================================================================

    # Extract from UCF snapshot (primary source)
    coi = None
    csi = None
    cip = None
    ucf_entropy = None
    ucf_notes = []

    if ucf_snapshot is not None:
        coi = getattr(ucf_snapshot, 'consciousness_order_index', None)
        csi = getattr(ucf_snapshot, 'consciousness_stability_index', None)
        cip = getattr(ucf_snapshot, 'consciousness_integration_potential', None)
        ucf_entropy = getattr(ucf_snapshot, 'entropy_of_weights', None)
        ucf_notes_attr = getattr(ucf_snapshot, 'diagnostic_notes', [])
        if ucf_notes_attr:
            ucf_notes = list(ucf_notes_attr)

    # Fallback to coherence_observation if snapshot not available
    if coherence_observation is not None:
        if coi is None:
            coi = getattr(coherence_observation, 'consciousness_order_index', None)
        if csi is None:
            csi = getattr(coherence_observation, 'consciousness_stability_index', None)
        if cip is None:
            cip = getattr(coherence_observation, 'consciousness_integration_potential', None)
        if ucf_entropy is None:
            ucf_entropy = getattr(coherence_observation, 'ucf_entropy', None)
        if not ucf_notes:
            ucf_notes_attr = getattr(coherence_observation, 'ucf_notes', [])
            if ucf_notes_attr:
                ucf_notes = list(ucf_notes_attr)

    # Check if we have minimum required data
    if coi is None or csi is None:
        notes.append("Insufficient UCF data: COI or CSI unavailable")
        return InsightWindowResult(
            insight_window_open=False,
            insight_depth=0.0,
            insight_mode="none",
            insight_tags=[],
            notes=notes,
        )

    # Use default CIP if unavailable
    if cip is None:
        cip = 0.5
        notes.append("CIP unavailable, using default 0.5")

    notes.append(f"UCF metrics: COI={coi:.3f}, CSI={csi:.3f}, CIP={cip:.3f}")

    # ========================================================================
    # STEP 3: EXTRACT SEMANTIC & ENTROPY RISK BANDS
    # ========================================================================

    # Extract cognitive drift v3 (risk metric)
    cognitive_drift_v3 = None
    if coherence_observation is not None:
        cognitive_drift_v3 = getattr(coherence_observation, 'cognitive_drift_v3', None)

    # Classify drift risk band
    drift_risk_band = "low"
    if cognitive_drift_v3 is not None:
        if cognitive_drift_v3 >= 0.65:
            drift_risk_band = "high"
        elif cognitive_drift_v3 >= 0.45:
            drift_risk_band = "moderate"

    # Extract temporal entropy volatility (risk metric)
    temporal_entropy_volatility = None
    if coherence_observation is not None:
        temporal_entropy_volatility = getattr(coherence_observation, 'temporal_entropy_volatility', None)

    # Classify entropy band
    entropy_band = "stable"
    if temporal_entropy_volatility is not None:
        if temporal_entropy_volatility >= 0.65:
            entropy_band = "volatile"
        elif temporal_entropy_volatility >= 0.35:
            entropy_band = "transitional"

    notes.append(f"Risk bands: drift={drift_risk_band}, entropy={entropy_band}")

    # ========================================================================
    # STEP 4: INSIGHT WINDOW OPENNESS (BOOLEAN)
    # ========================================================================

    # Window opens when UCF megafusion signals indicate readiness:
    # COI ≥ 0.55 AND CSI ≥ 0.50
    # AND none of the following blocked:
    # - drift_risk_band == "high"
    # - entropy_band == "volatile"

    window_blocked = False

    if coi < 0.55:
        notes.append("Window blocked: COI < 0.55")
        window_blocked = True

    if csi < 0.50:
        notes.append("Window blocked: CSI < 0.50")
        window_blocked = True

    if drift_risk_band == "high":
        notes.append("Window blocked: high drift risk")
        window_blocked = True

    if entropy_band == "volatile":
        notes.append("Window blocked: volatile entropy")
        window_blocked = True

    insight_window_open = not window_blocked

    if insight_window_open:
        notes.append("Insight window: OPEN")
    else:
        notes.append("Insight window: CLOSED")

    # ========================================================================
    # STEP 5: INSIGHT DEPTH (0–1)
    # ========================================================================

    # Base formula: weighted sum of UCF indices
    raw_depth = 0.40 * coi + 0.40 * csi + 0.20 * cip

    # Apply modifiers
    depth_modifiers = []

    if entropy_band == "transitional":
        raw_depth *= 0.85  # Reduce by 15%
        depth_modifiers.append("entropy_transitional:-15%")

    if drift_risk_band == "moderate":
        raw_depth *= 0.90  # Reduce by 10%
        depth_modifiers.append("drift_moderate:-10%")

    # Cap depth if COI is low
    if coi < 0.45:
        raw_depth = min(raw_depth, 0.45)
        depth_modifiers.append("coi_low:cap@0.45")

    insight_depth = _clamp(raw_depth, 0.0, 1.0)

    if depth_modifiers:
        notes.append(f"Depth modifiers: {', '.join(depth_modifiers)}")

    notes.append(f"Insight depth: {insight_depth:.3f}")

    # ========================================================================
    # STEP 6: INSIGHT MODE CLASSIFICATION
    # ========================================================================

    if insight_depth >= 0.70:
        insight_mode = "deep"
    elif insight_depth >= 0.40:
        insight_mode = "light"
    else:
        insight_mode = "none"

    notes.append(f"Insight mode: {insight_mode}")

    # ========================================================================
    # STEP 7: INSIGHT TAGS (DIAGNOSTIC-ONLY)
    # ========================================================================

    # Structural alignment
    if coi >= 0.65:
        tags.append("structural_alignment")

    # Temporal resilience
    if csi >= 0.65:
        tags.append("temporal_resilience")

    # Integration readiness
    if cip >= 0.60:
        tags.append("integration_ready")

    # Entropy state
    if entropy_band == "transitional":
        tags.append("entropy_transitional")
    elif entropy_band == "volatile":
        tags.append("entropy_high")

    # Drift caution
    if drift_risk_band in ["moderate", "high"]:
        tags.append("drift_caution")

    # Add UCF diagnostic notes as tags
    for note in ucf_notes:
        if note not in tags:
            tags.append(note)

    # Sort and deduplicate tags
    tags = sorted(set(tags))

    # ========================================================================
    # STEP 8: RETURN RESULT
    # ========================================================================

    return InsightWindowResult(
        insight_window_open=insight_window_open,
        insight_depth=insight_depth,
        insight_mode=insight_mode,
        insight_tags=tags,
        notes=notes,
    )


# Public API
__all__ = [
    'InsightWindowResult',
    'compute_insight_window',
]
