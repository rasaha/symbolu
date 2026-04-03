"""
Phase 31: Adaptive Persona Echo Layer (APEL) v1.0
===================================================

Deterministic, zero-LLM, persona-side echo layer that optionally adds
a short, resonance-aware "echo segment" to Persona responses based on
multi-turn session context and resonance maps.

APEL is:
    • UI / tone layer only
    • Observation-driven (uses session + resonance signals)
    • Fully deterministic, zero-LLM
    • Config & mode-aware (domain + interaction mode + preferences)

Design Principles:
    1. Zero-LLM (computes only control parameters, not language)
    2. Observation-only (does not influence routing, mapping, or semantics)
    3. Deterministic (same inputs → same echo profile)
    4. Backwards Compatible (existing tests remain green)
    5. Semantic Safety (core semantic content is not altered)

Echo Profile Structure:
    • echo_enabled: bool — whether echo is active
    • echo_mode: str — "none" | "light" | "reflective" | "pattern"
    • echo_strength: float — [0.0, 1.0] strength parameter
    • echo_length_hint: int — approximate sentence count (1–3)
    • echo_focus_tags: List[str] — e.g. ["identity", "stability", "drift"]
    • echo_risk_tags: List[str] — e.g. ["drift_caution", "entropy_high"]

Usage:
    from symbolu_core.mechanical.persona.persona_echo_layer import (
        compute_adaptive_persona_echo_profile,
        AdaptivePersonaEchoProfile
    )

    # Compute echo profile from session + resonance context
    echo_profile = compute_adaptive_persona_echo_profile(
        session_summary=session_summary,
        resonance_map=resonance_map,
        identity_signature=identity_signature,
        intent_arc=intent_arc,
        motivation_profile=motivation_profile,
        interaction_mode=interaction_mode,
        domain=domain,
    )

    # Check if echo is enabled
    if echo_profile.echo_enabled:
        print(f"Echo Mode: {echo_profile.echo_mode}")
        print(f"Echo Strength: {echo_profile.echo_strength}")
        print(f"Focus Tags: {echo_profile.echo_focus_tags}")
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any


# ============================================================================
# AdaptivePersonaEchoProfile Dataclass
# ============================================================================


@dataclass
class AdaptivePersonaEchoProfile:
    """
    Adaptive Persona Echo Layer profile (control parameters only).

    This profile contains all control knobs and diagnostic metadata
    for the echo layer, but does NOT contain generated text.

    Attributes:
        echo_enabled: Whether echo is active (hard gate by mode/domain)
        echo_mode: Echo mode type ("none" | "light" | "reflective" | "pattern")
        echo_strength: Echo strength parameter [0.0, 1.0]
        echo_length_hint: Approximate sentence count for echo (1–3)
        echo_focus_tags: Focus tags (e.g., ["identity", "stability"])
        echo_risk_tags: Risk tags (e.g., ["drift_caution", "entropy_high"])
        source_metrics: Which metrics drove this profile (for diagnostics)
        notes: Deterministic notes for dashboards/logging
    """
    echo_enabled: bool
    echo_mode: str  # "none" | "light" | "reflective" | "pattern"
    echo_strength: float  # [0.0, 1.0]
    echo_length_hint: int  # 1–3 (approximate sentence count)
    echo_focus_tags: List[str] = field(default_factory=list)
    echo_risk_tags: List[str] = field(default_factory=list)
    source_metrics: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self):
        """Convert to JSON-serializable dictionary."""
        return {
            "echo_enabled": self.echo_enabled,
            "echo_mode": self.echo_mode,
            "echo_strength": self.echo_strength,
            "echo_length_hint": self.echo_length_hint,
            "echo_focus_tags": self.echo_focus_tags,
            "echo_risk_tags": self.echo_risk_tags,
            "source_metrics": self.source_metrics,
            "notes": self.notes,
        }


# ============================================================================
# Helper Functions
# ============================================================================


def _clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp value to [min_val, max_val] range."""
    return max(min_val, min(max_val, value))


def _safe_get(obj: Any, attr: str, default: Any = None) -> Any:
    """Safely get attribute from object or dict."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


# ============================================================================
# Main Echo Profile Computation
# ============================================================================


def compute_adaptive_persona_echo_profile(
    *,
    session_summary: Optional[Any] = None,
    resonance_map: Optional[Any] = None,
    identity_signature: Optional[Any] = None,
    intent_arc: Optional[Any] = None,
    motivation_profile: Optional[Any] = None,
    interaction_mode: str,
    domain: str,
) -> AdaptivePersonaEchoProfile:
    """
    Deterministic, zero-LLM computation of echo parameters.

    Does NOT generate text, only control profile.

    Canonical v1.0 Logic:

        1. Mode & Domain Gate (hard):
           • If interaction_mode == "analytics_only" → echo disabled
           • If domain in {"trading", "generic"} → echo disabled
           • Only therapy & identity + modes SMART_INSIGHT / DEEP_ADAPTIVE can enable echo

        2. Echo Mode Selection:
           • light: low drift, good stability, hope/stabilization motivation
           • reflective: identity expansion/integration/discovery, balanced entropy
           • pattern: moderate drift or transitional entropy, identity/insight/dissonance arc

        3. Echo Strength & Length Hints:
           • Base strength from coherence_fused + semantic_integrity (avg)
           • Clamp to [0.0, 1.0]
           • If drift_risk_band == "high" or temporal_entropy_band == "volatile" → multiply by 0.5
           • Map to length hint: <0.35→1, 0.35-0.70→2, ≥0.70→3

        4. Focus & Risk Tags (deterministic, rule-based):
           • Focus: "identity", "stability", "drift", "pattern", "entropy"
           • Risk: "drift_caution", "entropy_high", "inversion_plausible"

        5. Diagnostics:
           • source_metrics and notes list which bands/metrics drove the profile

    Args:
        session_summary: SessionSummary object (with coherence, drift, stability metrics)
        resonance_map: CrossLayerResonanceMap object (with resonance signals)
        identity_signature: IdentitySignature object (with signature type)
        intent_arc: IntentArc object (with arc type)
        motivation_profile: MotivationProfile object (with motivation type)
        interaction_mode: Interaction mode (e.g., "SMART_INSIGHT", "DEEP_ADAPTIVE", "analytics_only")
        domain: Domain context (e.g., "trading", "therapy", "identity", "generic")

    Returns:
        AdaptivePersonaEchoProfile with all control parameters

    Invariants:
        • Zero-LLM: No text generation, only control parameters
        • Deterministic: Same inputs → same outputs
        • Observation-only: Does not modify any pipeline state
        • Backwards compatible: Graceful degradation when inputs missing
    """
    # ========================================================================
    # STEP 1: Mode & Domain Gate (Hard Gate)
    # ========================================================================

    # Hard gate: analytics_only mode disables echo
    if interaction_mode == "analytics_only":
        return AdaptivePersonaEchoProfile(
            echo_enabled=False,
            echo_mode="none",
            echo_strength=0.0,
            echo_length_hint=0,
            notes=["echo_disabled: interaction_mode=analytics_only"],
        )

    # Hard gate: trading and generic domains disable echo
    if domain in {"trading", "generic"}:
        return AdaptivePersonaEchoProfile(
            echo_enabled=False,
            echo_mode="none",
            echo_strength=0.0,
            echo_length_hint=0,
            notes=[f"echo_disabled: domain={domain}"],
        )

    # Only therapy & identity + modes SMART_INSIGHT / DEEP_ADAPTIVE can enable echo
    if domain not in {"therapy", "identity"}:
        return AdaptivePersonaEchoProfile(
            echo_enabled=False,
            echo_mode="none",
            echo_strength=0.0,
            echo_length_hint=0,
            notes=[f"echo_disabled: domain={domain} not in [therapy, identity]"],
        )

    if interaction_mode not in {"SMART_INSIGHT", "DEEP_ADAPTIVE"}:
        return AdaptivePersonaEchoProfile(
            echo_enabled=False,
            echo_mode="none",
            echo_strength=0.0,
            echo_length_hint=0,
            notes=[f"echo_disabled: interaction_mode={interaction_mode} not in [SMART_INSIGHT, DEEP_ADAPTIVE]"],
        )

    # ========================================================================
    # STEP 2: Extract Metrics from Inputs
    # ========================================================================

    # Extract from session_summary
    drift_risk_band = _safe_get(session_summary, "drift_risk_band", "unknown")
    stability_band = _safe_get(session_summary, "stability_band", "unknown")
    temporal_entropy_band = _safe_get(session_summary, "temporal_entropy_band", "unknown")
    coherence_fused = _safe_get(session_summary, "coherence_fused", 0.5)

    # Extract from resonance_map
    semantic_integrity = _safe_get(resonance_map, "semantic_integrity", 0.5)
    resonance_entropy_band = _safe_get(resonance_map, "resonance_entropy_band", "unknown")

    # Extract from identity_signature
    identity_type = _safe_get(identity_signature, "signature_type", "neutral_identity")

    # Extract from intent_arc
    intent_arc_type = _safe_get(intent_arc, "arc_type", "unknown")

    # Extract from motivation_profile
    motivation_type = _safe_get(motivation_profile, "motivation_type", "unknown")

    # ========================================================================
    # STEP 3: Echo Mode Selection (Deterministic Rule-Based)
    # ========================================================================

    echo_mode = "none"
    source_metrics = []

    # Mode: light
    # Conditions: low drift, good stability, hope/stabilization motivation
    if (
        drift_risk_band == "low"
        and stability_band == "stable"
        and motivation_type in {"hope_driven", "stabilization_driven"}
    ):
        echo_mode = "light"
        source_metrics.append(f"drift_band={drift_risk_band}")
        source_metrics.append(f"stability_band={stability_band}")
        source_metrics.append(f"motivation={motivation_type}")

    # Mode: reflective
    # Conditions: identity expansion/integration/discovery, balanced/focused entropy
    elif (
        identity_type in {"self_expansion", "self_integration", "self_discovery"}
        and resonance_entropy_band in {"balanced", "focused"}
    ):
        echo_mode = "reflective"
        source_metrics.append(f"identity={identity_type}")
        source_metrics.append(f"entropy_band={resonance_entropy_band}")

    # Mode: pattern
    # Conditions: moderate drift or transitional entropy, identity/insight/dissonance arc
    elif (
        drift_risk_band == "moderate" or temporal_entropy_band == "transitional"
    ) and intent_arc_type in {"identity_arc", "insight_arc", "dissonance_arc"}:
        echo_mode = "pattern"
        source_metrics.append(f"drift_band={drift_risk_band}")
        source_metrics.append(f"entropy_band={temporal_entropy_band}")
        source_metrics.append(f"intent_arc={intent_arc_type}")

    # If no mode matched, disable echo
    if echo_mode == "none":
        return AdaptivePersonaEchoProfile(
            echo_enabled=False,
            echo_mode="none",
            echo_strength=0.0,
            echo_length_hint=0,
            notes=["echo_disabled: no mode rules matched"],
        )

    # ========================================================================
    # STEP 4: Echo Strength & Length Hints
    # ========================================================================

    # Base strength from coherence_fused + semantic_integrity (avg)
    if coherence_fused is not None and semantic_integrity is not None:
        strength_raw = 0.5 * coherence_fused + 0.5 * semantic_integrity
    elif coherence_fused is not None:
        strength_raw = coherence_fused
    elif semantic_integrity is not None:
        strength_raw = semantic_integrity
    else:
        strength_raw = 0.5  # default fallback

    # Clamp to [0.0, 1.0]
    echo_strength = _clamp(strength_raw, 0.0, 1.0)

    # Dampening: if drift_risk_band == "high" or temporal_entropy_band == "volatile" → multiply by 0.5
    if drift_risk_band == "high" or temporal_entropy_band == "volatile":
        echo_strength *= 0.5
        source_metrics.append("dampened: high_drift or volatile_entropy")

    # Map to length hint
    if echo_strength < 0.35:
        echo_length_hint = 1
    elif echo_strength < 0.70:
        echo_length_hint = 2
    else:
        echo_length_hint = 3

    # ========================================================================
    # STEP 5: Focus & Risk Tags (Deterministic, Rule-Based)
    # ========================================================================

    focus_tags = []
    risk_tags = []

    # Focus tag: "identity"
    if identity_type in {"self_expansion", "self_integration", "self_discovery"}:
        focus_tags.append("identity")

    # Focus tag: "stability"
    if stability_band == "stable" or drift_risk_band == "low":
        focus_tags.append("stability")

    # Focus tag: "drift"
    if drift_risk_band in {"moderate", "high"}:
        focus_tags.append("drift")

    # Focus tag: "entropy"
    if temporal_entropy_band in {"transitional", "volatile"}:
        focus_tags.append("entropy")

    # Focus tag: "pattern"
    # (We'll check for mirror_time_cycle type if available from resonance_map)
    mirror_time_cycle = _safe_get(resonance_map, "mirror_time_cycle_type", None)
    if mirror_time_cycle in {"oscillating", "converging"}:
        focus_tags.append("pattern")

    # Risk tag: "drift_caution"
    if drift_risk_band == "high":
        risk_tags.append("drift_caution")

    # Risk tag: "entropy_high"
    if temporal_entropy_band == "volatile":
        risk_tags.append("entropy_high")

    # Risk tag: "inversion_plausible"
    cause_effect_inversion_band = _safe_get(resonance_map, "cause_effect_inversion_band", None)
    if cause_effect_inversion_band in {"inversion_plausible", "inversion_dominant"}:
        risk_tags.append("inversion_plausible")

    # Dedupe and sort tags
    focus_tags = sorted(list(set(focus_tags)))
    risk_tags = sorted(list(set(risk_tags)))

    # ========================================================================
    # STEP 6: Build Diagnostics (Notes)
    # ========================================================================

    notes = []
    notes.append(f"echo_enabled: mode={echo_mode}, domain={domain}, interaction_mode={interaction_mode}")
    notes.append(f"from: stability_band={stability_band}, drift_band={drift_risk_band}, identity={identity_type}")

    # ========================================================================
    # STEP 7: Return AdaptivePersonaEchoProfile
    # ========================================================================

    return AdaptivePersonaEchoProfile(
        echo_enabled=True,
        echo_mode=echo_mode,
        echo_strength=round(echo_strength, 4),
        echo_length_hint=echo_length_hint,
        echo_focus_tags=focus_tags,
        echo_risk_tags=risk_tags,
        source_metrics=source_metrics,
        notes=notes,
    )
