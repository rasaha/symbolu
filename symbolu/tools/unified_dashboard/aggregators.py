"""
Unified Dashboard Aggregators (Phase 20 v1.0)

This module builds UnifiedSessionAnalytics from existing session data.
All operations are deterministic, zero-LLM, and read-only.

Design Principles:
    1. Zero-LLM (no model calls)
    2. Deterministic (same input → same output)
    3. Read-only (does not modify session state)
    4. Graceful degradation (handles missing data)
    5. Complete metric extraction
"""

from typing import Optional, List, Dict, Any
from symbolu.tools.unified_dashboard.models import (
    MetricSparkline,
    UnifiedSessionAnalytics,
)
from symbolu.service.sessions.session_store import SessionStore, compute_session_summary


def build_unified_session_analytics(
    session_id: str,
    session_store: Optional[SessionStore] = None,
) -> Optional[UnifiedSessionAnalytics]:
    """
    Build UnifiedSessionAnalytics from session state and summary.

    This is the main analytics builder that extracts all metrics from:
    - SessionState (complete turn history)
    - SessionSummary (aggregated statistics)
    - CoherenceState (coherence/drift/entropy metrics)
    - Intent/Identity/Motivation engines

    All derivations are deterministic and rule-based.

    Args:
        session_id: Session identifier
        session_store: Optional SessionStore instance (uses singleton if None)

    Returns:
        UnifiedSessionAnalytics if session found, None otherwise

    Design:
        1. Look up SessionState from SessionStore
        2. Compute SessionSummary
        3. Extract metrics from coherence_history
        4. Derive bands using deterministic rules
        5. Build sparklines from turn history
        6. Assemble pattern tags
        7. Generate deterministic note
    """
    # Import SessionStore if not provided
    if session_store is None:
        # Create a new instance (caller should pass singleton if needed)
        from symbolu.service.sessions import SessionStore as _SessionStore
        session_store = _SessionStore()

    # Retrieve session state
    session_state = session_store.get(session_id)
    if session_state is None:
        return None

    # Compute session summary
    summary = compute_session_summary(session_state)

    # ========================================================================
    # Extract Core Metrics
    # ========================================================================

    # Session metadata
    domain = session_state.domain
    turn_count = summary.total_turns

    # Coherence metrics (v1/v2/v3/fused/quality)
    coherence_v1 = summary.coherence_trend  # v1 = coherence_score from coherence_history
    coherence_v2 = None
    coherence_v3 = None
    coherence_fused = None
    coherence_v3_quality = None

    # Semantic & Drift metrics
    semantic_integrity_score = summary.semantic_stability_score
    cognitive_drift_v3 = summary.persona_drift_avg
    drift_fusion_index = None
    drift_risk_band = None

    # Temporal & Entropy
    temporal_arc_score = summary.temporal_arc_avg
    instantaneous_entropy = None
    short_window_entropy = None
    long_window_entropy = None
    normalized_entropy_diff = summary.avg_temporal_entropy_diff
    entropy_volatility = summary.avg_temporal_entropy_volatility

    # Motivation & Identity & Intent
    intent_arc_type = None
    identity_signature = None
    motivation_type = None

    # Formula / Resonance
    enhanced_smi = summary.avg_smi
    avg_enhanced_smi = summary.avg_smi
    resonance_index = summary.avg_resonance_index
    tension_index = summary.avg_tension_index
    arc_alignment_index = summary.avg_arc_alignment_index
    guna_resonance_index = summary.avg_guna_resonance
    kosha_resonance_index = summary.avg_kosha_resonance

    # Phase 23: Cause-Effect Inversion Analytics
    inversion_band = summary.dominant_inversion_band
    inversion_pattern_tags = summary.inversion_pattern_tags

    # Phase 24: Resonance Weighting Function
    avg_resonance_entropy = summary.avg_resonance_entropy
    dominant_resonance_metrics = summary.dominant_resonance_metrics
    resonance_weighting_notes = summary.resonance_weighting_notes

    # Derive resonance entropy band from avg_resonance_entropy
    resonance_entropy_band = None
    if avg_resonance_entropy is not None:
        if avg_resonance_entropy < 0.35:
            resonance_entropy_band = "focused"
        elif avg_resonance_entropy < 0.70:
            resonance_entropy_band = "balanced"
        else:
            resonance_entropy_band = "diffuse"

    # Phase 27: Symbolic Harmonization Formula
    avg_symbolic_harmonization = summary.avg_symbolic_harmonization
    dominant_symbolic_harmonization_pattern = summary.dominant_symbolic_harmonization_pattern
    symbolic_harmonization_notes = summary.symbolic_harmonization_notes

    # Use dominant pattern as band classification
    symbolic_harmonization_band = dominant_symbolic_harmonization_pattern

    # ========================================================================
    # Extract from Last Coherence State (Phase 11/12/16/17/18)
    # ========================================================================

    if session_state.coherence_history:
        last_coh = session_state.coherence_history[-1]

        if isinstance(last_coh, dict):
            # Coherence v2/v3/fused/quality
            coherence_v2 = last_coh.get('coherence_score_v2')
            coherence_v3 = last_coh.get('coherence_score_v3')
            coherence_fused = last_coh.get('coherence_fused')
            coherence_v3_quality = last_coh.get('coherence_v3_quality')

            # Semantic & Drift (Phase 17)
            if 'semantic' in last_coh:
                sem = last_coh['semantic']
                semantic_integrity_score = sem.get('integrity_score', semantic_integrity_score)
                cognitive_drift_v3 = sem.get('cognitive_drift_v3', cognitive_drift_v3)

            # Temporal Entropy (Phase 18)
            if 'temporal_entropy' in last_coh:
                temp_ent = last_coh['temporal_entropy']
                if 'details' in temp_ent:
                    details = temp_ent['details']
                    instantaneous_entropy = details.get('instantaneous_entropy')
                    short_window_entropy = details.get('short_window_entropy')
                    long_window_entropy = details.get('long_window_entropy')
                    normalized_entropy_diff = details.get('normalized_entropy_diff', normalized_entropy_diff)
                    entropy_volatility = details.get('entropy_volatility', entropy_volatility)

    # ========================================================================
    # Extract from Last Turn (Intent/Identity/Motivation)
    # ========================================================================

    if session_state.turns:
        last_turn = session_state.turns[-1]

        if isinstance(last_turn, dict):
            # Intent Arc Engine
            if 'intent_arc' in last_turn:
                intent_data = last_turn['intent_arc']
                intent_arc_type = intent_data.get('arc_type')

            # Identity Signature Engine
            if 'identity_signature' in last_turn:
                identity_data = last_turn['identity_signature']
                identity_signature = identity_data.get('signature_type')

            # Motivation Flow Engine
            if 'motivation_profile' in last_turn:
                motivation_data = last_turn['motivation_profile']
                motivation_type = motivation_data.get('motivation_type')

    # ========================================================================
    # Derive Stability Band
    # ========================================================================
    # Uses coherence_fused and entropy_volatility
    # - "stable"     if coherence_fused >= 0.65 and entropy_volatility <= 0.35
    # - "transition" if 0.45 <= coherence_fused < 0.65 or 0.35 < volatility <= 0.65
    # - "unstable"   if coherence_fused < 0.45 or entropy_volatility > 0.65

    stability_band = None
    if coherence_fused is not None and entropy_volatility is not None:
        if coherence_fused >= 0.65 and entropy_volatility <= 0.35:
            stability_band = "stable"
        elif coherence_fused < 0.45 or entropy_volatility > 0.65:
            stability_band = "unstable"
        else:
            stability_band = "transition"
    elif coherence_fused is not None:
        # Fallback: use only coherence_fused
        if coherence_fused >= 0.65:
            stability_band = "stable"
        elif coherence_fused < 0.45:
            stability_band = "unstable"
        else:
            stability_band = "transition"

    # ========================================================================
    # Derive Semantic Band
    # ========================================================================
    # Combines semantic_integrity_score and cognitive_drift_v3
    # - "coherent" if integrity >= 0.70 and drift_v3 <= 0.35
    # - "mixed"    if 0.45 <= integrity < 0.70
    # - "fragile"  if integrity < 0.45 or drift_v3 > 0.65

    semantic_band = None
    if semantic_integrity_score is not None and cognitive_drift_v3 is not None:
        if semantic_integrity_score >= 0.70 and cognitive_drift_v3 <= 0.35:
            semantic_band = "coherent"
        elif semantic_integrity_score < 0.45 or cognitive_drift_v3 > 0.65:
            semantic_band = "fragile"
        else:
            semantic_band = "mixed"
    elif semantic_integrity_score is not None:
        # Fallback: use only semantic_integrity_score
        if semantic_integrity_score >= 0.70:
            semantic_band = "coherent"
        elif semantic_integrity_score < 0.45:
            semantic_band = "fragile"
        else:
            semantic_band = "mixed"

    # ========================================================================
    # Derive Motivation Band
    # ========================================================================
    # Deterministic mapping from motivation_type:
    # - fear/avoidance/overcorrection → "defensive"
    # - hope/expansion/stabilization  → "expansive"
    # - assertion                      → "assertive"
    # - ambiguous                      → "ambiguous"

    motivation_band = None
    if motivation_type:
        motivation_lower = motivation_type.lower()
        if any(kw in motivation_lower for kw in ['fear', 'avoidance', 'overcorrection']):
            motivation_band = "defensive"
        elif any(kw in motivation_lower for kw in ['hope', 'expansion', 'stabilization']):
            motivation_band = "expansive"
        elif 'assertion' in motivation_lower:
            motivation_band = "assertive"
        elif 'ambiguous' in motivation_lower:
            motivation_band = "ambiguous"

    # ========================================================================
    # Derive Drift Band (mirror of drift_risk_band)
    # ========================================================================
    # For now, derive from cognitive_drift_v3 if not available
    drift_band = drift_risk_band
    if drift_band is None and cognitive_drift_v3 is not None:
        if cognitive_drift_v3 <= 0.35:
            drift_band = "low"
        elif cognitive_drift_v3 <= 0.65:
            drift_band = "moderate"
        else:
            drift_band = "high"

    # ========================================================================
    # Build Sparklines
    # ========================================================================
    # Extract last N turns (max 20) for coherence/drift/entropy

    max_sparkline_points = 20

    # Coherence sparkline (coherence_fused or coherence_v1)
    coherence_values = []
    coherence_labels = []

    for i, coh in enumerate(session_state.coherence_history[-max_sparkline_points:]):
        if isinstance(coh, dict):
            val = coh.get('coherence_fused') or coh.get('coherence_score') or coh.get('stability')
            if val is not None:
                coherence_values.append(val)
                coherence_labels.append(f"Turn {i+1}")

    coherence_sparkline = MetricSparkline(
        name="coherence",
        values=coherence_values,
        labels=coherence_labels,
    )

    # Drift sparkline (cognitive_drift_v3 or persona_drift)
    drift_values = []
    drift_labels = []

    for i, coh in enumerate(session_state.coherence_history[-max_sparkline_points:]):
        if isinstance(coh, dict):
            val = None
            if 'semantic' in coh and 'cognitive_drift_v3' in coh['semantic']:
                val = coh['semantic']['cognitive_drift_v3']
            elif 'persona_drift' in coh:
                val = coh['persona_drift']

            if val is not None:
                drift_values.append(val)
                drift_labels.append(f"Turn {i+1}")

    drift_sparkline = MetricSparkline(
        name="drift",
        values=drift_values,
        labels=drift_labels,
    )

    # Entropy sparkline (normalized_entropy_diff or entropy_volatility)
    entropy_values = []
    entropy_labels = []

    for i, coh in enumerate(session_state.coherence_history[-max_sparkline_points:]):
        if isinstance(coh, dict):
            val = None
            if 'temporal_entropy' in coh and 'details' in coh['temporal_entropy']:
                details = coh['temporal_entropy']['details']
                val = details.get('normalized_entropy_diff') or details.get('instantaneous_entropy')

            if val is not None:
                # Clamp to [0, 1] for sparkline
                val = max(0.0, min(1.0, val))
                entropy_values.append(val)
                entropy_labels.append(f"Turn {i+1}")

    entropy_sparkline = MetricSparkline(
        name="entropy",
        values=entropy_values,
        labels=entropy_labels,
    )

    # Inversion sparkline (Phase 23: inversion_score)
    inversion_values = []
    inversion_labels = []

    for i, coh in enumerate(session_state.coherence_history[-max_sparkline_points:]):
        if isinstance(coh, dict):
            val = None
            # Try to extract from cause_effect_inversion_history
            if 'cause_effect_inversion_history' in coh:
                inv_history = coh['cause_effect_inversion_history']
                if isinstance(inv_history, list) and len(inv_history) > 0:
                    latest_snapshot = inv_history[-1]
                    if latest_snapshot is not None and hasattr(latest_snapshot, 'inversion_score'):
                        val = latest_snapshot.inversion_score

            # Fallback to avg_inversion_score if available
            if val is None and 'avg_inversion_score' in coh:
                val = coh['avg_inversion_score']

            if val is not None:
                # Clamp to [0, 1] for sparkline
                val = max(0.0, min(1.0, val))
                inversion_values.append(val)
                inversion_labels.append(f"Turn {i+1}")

    inversion_sparkline = MetricSparkline(
        name="inversion",
        values=inversion_values,
        labels=inversion_labels,
    ) if inversion_values else None

    # Symbolic Harmonization sparkline (Phase 27: symbolic_harmonization_index)
    shi_values = []
    shi_labels = []

    for i, coh in enumerate(session_state.coherence_history[-max_sparkline_points:]):
        if isinstance(coh, dict):
            val = None
            # Try to extract from current_symbolic_harmonization_index
            if 'current_symbolic_harmonization_index' in coh:
                val = coh['current_symbolic_harmonization_index']

            # Fallback to symbolic_harmonization_history if available
            if val is None and 'symbolic_harmonization_history' in coh:
                shf_history = coh['symbolic_harmonization_history']
                if isinstance(shf_history, list) and len(shf_history) > 0:
                    latest_snapshot = shf_history[-1]
                    if latest_snapshot is not None:
                        if hasattr(latest_snapshot, 'symbolic_harmonization_index'):
                            val = latest_snapshot.symbolic_harmonization_index
                        elif isinstance(latest_snapshot, dict) and 'symbolic_harmonization_index' in latest_snapshot:
                            val = latest_snapshot['symbolic_harmonization_index']

            if val is not None:
                # Clamp to [0, 1] for sparkline
                val = max(0.0, min(1.0, val))
                shi_values.append(val)
                shi_labels.append(f"Turn {i+1}")

    symbolic_harmonization_sparkline = MetricSparkline(
        name="symbolic_harmonization",
        values=shi_values,
        labels=shi_labels,
    ) if shi_values else None

    # ========================================================================
    # Assemble Session Pattern Tags
    # ========================================================================
    # Combine: drift_pattern, intent_arc_type, identity_signature, motivation_type
    # Example tags:
    #   "stabilization_arc", "insight_arc", "identity_expansion",
    #   "self_fragmentation", "hope_driven", "fear_driven", etc.

    session_pattern_tags = []

    # From intent_arc_type
    if intent_arc_type:
        if 'stabilization' in intent_arc_type.lower():
            session_pattern_tags.append("stabilization_arc")
        elif 'insight' in intent_arc_type.lower():
            session_pattern_tags.append("insight_arc")
        elif 'expansion' in intent_arc_type.lower():
            session_pattern_tags.append("expansion_arc")
        elif 'regression' in intent_arc_type.lower():
            session_pattern_tags.append("regression_arc")

    # From identity_signature
    if identity_signature:
        if 'expansion' in identity_signature.lower():
            session_pattern_tags.append("identity_expansion")
        elif 'fragmentation' in identity_signature.lower():
            session_pattern_tags.append("self_fragmentation")
        elif 'consolidation' in identity_signature.lower():
            session_pattern_tags.append("identity_consolidation")

    # From motivation_type
    if motivation_type:
        if 'hope' in motivation_type.lower():
            session_pattern_tags.append("hope_driven")
        elif 'fear' in motivation_type.lower():
            session_pattern_tags.append("fear_driven")
        elif 'assertion' in motivation_type.lower():
            session_pattern_tags.append("assertion_driven")

    # From drift_band
    if drift_band:
        if drift_band == "high":
            session_pattern_tags.append("high_drift")
        elif drift_band == "low":
            session_pattern_tags.append("low_drift")

    # From stability_band
    if stability_band:
        if stability_band == "stable":
            session_pattern_tags.append("stable_session")
        elif stability_band == "unstable":
            session_pattern_tags.append("unstable_session")

    # ========================================================================
    # Generate Deterministic Note
    # ========================================================================
    # Short, deterministic string summarizing session state

    note = _generate_session_note(
        stability_band=stability_band,
        semantic_band=semantic_band,
        drift_band=drift_band,
        motivation_band=motivation_band,
        coherence_fused=coherence_fused,
        cognitive_drift_v3=cognitive_drift_v3,
    )

    # ========================================================================
    # Assemble UnifiedSessionAnalytics
    # ========================================================================

    return UnifiedSessionAnalytics(
        session_id=session_id,
        domain=domain,
        turn_count=turn_count,
        # Coherence
        coherence_v1=coherence_v1,
        coherence_v2=coherence_v2,
        coherence_v3=coherence_v3,
        coherence_fused=coherence_fused,
        coherence_v3_quality=coherence_v3_quality,
        # Semantic & Drift
        semantic_integrity_score=semantic_integrity_score,
        cognitive_drift_v3=cognitive_drift_v3,
        drift_fusion_index=drift_fusion_index,
        drift_risk_band=drift_risk_band,
        drift_pattern_tags=[],  # Could add from summary if available
        # Temporal & Entropy
        temporal_arc_score=temporal_arc_score,
        instantaneous_entropy=instantaneous_entropy,
        short_window_entropy=short_window_entropy,
        long_window_entropy=long_window_entropy,
        normalized_entropy_diff=normalized_entropy_diff,
        entropy_volatility=entropy_volatility,
        # Motivation & Identity & Intent
        intent_arc_type=intent_arc_type,
        identity_signature=identity_signature,
        motivation_type=motivation_type,
        # Formula / Resonance
        enhanced_smi=enhanced_smi,
        avg_enhanced_smi=avg_enhanced_smi,
        resonance_index=resonance_index,
        tension_index=tension_index,
        arc_alignment_index=arc_alignment_index,
        guna_resonance_index=guna_resonance_index,
        kosha_resonance_index=kosha_resonance_index,
        # Aggregated Bands
        stability_band=stability_band,
        drift_band=drift_band,
        motivation_band=motivation_band,
        semantic_band=semantic_band,
        # Sparklines
        coherence_sparkline=coherence_sparkline,
        drift_sparkline=drift_sparkline,
        entropy_sparkline=entropy_sparkline,
        # Pattern Tags & Note
        session_pattern_tags=session_pattern_tags,
        note=note,
        # Phase 23: Cause-Effect Inversion Analytics
        inversion_band=inversion_band,
        inversion_sparkline=inversion_sparkline,
        inversion_notes=inversion_pattern_tags,
        # Phase 24: Resonance Weighting Function
        resonance_entropy_band=resonance_entropy_band,
        dominant_resonance_metrics=dominant_resonance_metrics,
        resonance_notes=resonance_weighting_notes,
        # Phase 27: Symbolic Harmonization Formula
        symbolic_harmonization_band=symbolic_harmonization_band,
        symbolic_harmonization_sparkline=symbolic_harmonization_sparkline,
        symbolic_harmonization_notes=symbolic_harmonization_notes,
    )


def _generate_session_note(
    stability_band: Optional[str],
    semantic_band: Optional[str],
    drift_band: Optional[str],
    motivation_band: Optional[str],
    coherence_fused: Optional[float],
    cognitive_drift_v3: Optional[float],
) -> str:
    """
    Generate a deterministic session note based on band classifications.

    Args:
        stability_band: "stable" | "transition" | "unstable"
        semantic_band: "coherent" | "mixed" | "fragile"
        drift_band: "low" | "moderate" | "high"
        motivation_band: "defensive" | "expansive" | "assertive" | "ambiguous"
        coherence_fused: Fused coherence score
        cognitive_drift_v3: Cognitive drift v3 score

    Returns:
        Short descriptive note (1-2 sentences)
    """
    # Build note components
    stability_desc = ""
    semantic_desc = ""
    motivation_desc = ""

    if stability_band == "stable":
        stability_desc = "stable coherence"
    elif stability_band == "unstable":
        stability_desc = "unstable coherence"
    elif stability_band == "transition":
        stability_desc = "transitional coherence"
    else:
        stability_desc = "coherence state unknown"

    if drift_band == "low":
        semantic_desc = "low drift"
    elif drift_band == "high":
        semantic_desc = "high drift"
    elif drift_band == "moderate":
        semantic_desc = "moderate drift"
    else:
        semantic_desc = "drift level unknown"

    if motivation_band == "expansive":
        motivation_desc = "expansive motivation"
    elif motivation_band == "defensive":
        motivation_desc = "defensive motivation"
    elif motivation_band == "assertive":
        motivation_desc = "assertive motivation"
    else:
        motivation_desc = ""

    # Assemble note
    parts = [f"Session shows {stability_desc} with {semantic_desc}"]
    if motivation_desc:
        parts.append(f"and {motivation_desc}")

    note = " ".join(parts) + "."

    # Add recommendation if unstable or high drift
    if stability_band == "unstable" or drift_band == "high":
        if semantic_band == "fragile":
            note += " Recommend grounding and stabilization interventions."
        else:
            note += " Monitor for continued instability."

    return note


# Public API
__all__ = [
    "build_unified_session_analytics",
]
