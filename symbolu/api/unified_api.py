"""
Unified Symbol-U API Output Schema (USU-API v1.0)
================================================

This module provides a single JSON output format combining all pipeline components:
- Fusion Renderer symbolic/practical/mirror layers
- DHA insights
- MapperProfile details
- TTOR routing plan
- MLCR activation
- PipelineContext
- CoherenceReport

Design Principles:
- Zero-LLM: All operations are deterministic and rule-based
- Non-invasive: Does not modify pipeline behavior
- Additive: Optional layer that can be enabled without breaking existing code
- JSON-safe: All outputs are JSON-serializable

Usage:
    from symbolu.api.unified_api import get_unified_json, get_public_response

    # After pipeline execution:
    unified = get_unified_json(ctx)
    public = get_public_response(ctx)
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional
from datetime import datetime


@dataclass
class UnifiedOutput:
    """
    Unified output structure combining all pipeline layers.

    This is the complete API contract for Symbol-U AGI responses.

    Fields:
        text: Final rendered text output
        symbolic: Symbolic layer from Fusion renderer
        practical: Practical layer from Fusion renderer
        mirror: Mirror-truth layer from Fusion renderer
        dha: DHA insights and delivery profile
        routing: TTOR routing plan fields
        mappers: Mapper profile details (HRM/LCM/LAM activation)
        entropy: Entropy measures (H_D, H_G, H_K, normalized)
        coherence: Coherence report from CoherenceObserver
        metadata: Turn number, timestamp, domain, etc.
        session_memory: Session memory v2.0 (episodic events)
        session_recap: Session recap v1.0 (multi-turn summary)
        intent_arc: Intent Arc Engine v1.0 (trajectory classification)
        identity_signature: Identity Signature Engine v1.0 (identity trajectory classification)
        motivation_profile: Motivation Flow Engine v1.0 (motivational driver classification)
        formulas: Phase 2 temporal formulas (SMI, ΔSMI, Bhava Gap, Tension Corridor) - observation only
        trading_guardrails: Phase 7 trading formula guardrails (trading safety risk flags)
    """

    text: str
    symbolic: Dict[str, Any]
    practical: Dict[str, Any]
    mirror: Dict[str, Any]
    dha: Dict[str, Any]
    routing: Dict[str, Any]
    mappers: Dict[str, Any]
    entropy: Dict[str, float]
    coherence: Dict[str, Any]
    metadata: Dict[str, Any]
    session_memory: Dict[str, Any] = field(default_factory=dict)
    session_recap: Dict[str, Any] = field(default_factory=dict)
    intent_arc: Dict[str, Any] = field(default_factory=dict)
    identity_signature: Dict[str, Any] = field(default_factory=dict)
    motivation_profile: Dict[str, Any] = field(default_factory=dict)
    formulas: Optional[Dict[str, Optional[float]]] = None
    trading_guardrails: Optional[Dict[str, bool]] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to JSON-serializable dictionary.

        Removes None values and ensures all keys are snake_case.

        Returns:
            Clean dictionary with all unified output fields
        """
        result = asdict(self)

        # Remove None values recursively
        return _remove_none_values(result)

    def to_json_string(self) -> str:
        """
        Convert to JSON string.

        Returns:
            JSON string representation
        """
        import json
        return json.dumps(self.to_dict(), indent=2)


def build_unified_output(text: str, ctx: Any) -> UnifiedOutput:
    """
    Build unified output from pipeline context.

    This is the main assembler function that extracts data from all
    pipeline components and creates a unified output structure.

    Args:
        text: Final rendered text
        ctx: PipelineContext with all pipeline results

    Returns:
        UnifiedOutput with complete pipeline data

    Note:
        This function is deterministic and does not modify ctx.
    """
    # Extract symbolic/practical/mirror layers from Fusion renderer
    symbolic_layer = {}
    practical_layer = {}
    mirror_layer = {}

    # Try to extract from fusion result if available
    if hasattr(ctx, 'fusion') and ctx.fusion is not None:
        fusion_result = ctx.fusion.fused_candidates if ctx.fusion else None

        if fusion_result and hasattr(fusion_result, 'to_dict'):
            fusion_dict = fusion_result.to_dict()

            # Extract layers from fusion metadata or explain
            explain = fusion_dict.get('explain', {})
            symbolic_layer = {
                'fusion_score': fusion_dict.get('fusion_score', 0.0),
                'candidate_count': len(fusion_dict.get('ranked_candidates', [])),
                'selected_source': fusion_dict.get('selected_candidate', {}).get('source', 'unknown'),
                'reasoning': explain.get('reasoning', 'No reasoning available'),
            }

            practical_layer = {
                'text': fusion_dict.get('selected_candidate', {}).get('text', text),
                'confidence': fusion_dict.get('selected_candidate', {}).get('confidence', 0.0),
                'relevance_score': fusion_dict.get('selected_candidate', {}).get('relevance_score', 0.0),
            }

            mirror_layer = {
                'routing': fusion_dict.get('routing', {}),
                'metadata': fusion_dict.get('metadata', {}),
            }

    # Extract DHA insights
    dha_insights = {}
    if hasattr(ctx, 'dha') and ctx.dha is not None:
        dha_insights = {
            'delivery_profile': ctx.dha.tone_profile,
            'readiness_level': ctx.dha.readiness_level,
            'resistance_flags': ctx.dha.resistance_flags,
            'safety_flags': ctx.dha.safety_flags,
            'adaptation_notes': ctx.dha.adaptation_notes,
            'adapted_message': ctx.dha.guarded_text,
        }

    # Extract routing plan from MLCR/TTOR
    routing_plan = {}
    if hasattr(ctx, 'mlcr') and ctx.mlcr is not None:
        # Try to extract routing plan from MLCR entries
        mlcr_entries = ctx.mlcr.entries if ctx.mlcr else {}

        if isinstance(mlcr_entries, dict):
            # Check if there's a routing_plan in the activation_plan
            activation_plan = mlcr_entries.get('activation_plan', {})

            routing_plan = {
                'tier': mlcr_entries.get('explain_log', {}).get('meta', {}).get('tier', 'unknown'),
                'intent': mlcr_entries.get('explain_log', {}).get('meta', {}).get('intent', 'unknown'),
                'domain': mlcr_entries.get('explain_log', {}).get('meta', {}).get('domain', 'unknown'),
                'use_hrm': activation_plan.get('use_hrm', False),
                'use_lcm': activation_plan.get('use_lcm', False),
                'use_lam': activation_plan.get('use_lam', False),
                'flow_mode': 'standard',  # Default
            }

    # Extract mapper profile
    mapper_profile = {}
    if hasattr(ctx, 'mapper_profile') and ctx.mapper_profile is not None:
        mapper_profile = ctx.mapper_profile.to_dict()
    else:
        # Default mapper profile
        mapper_profile = {
            'resolution_level': 'medium',
            'arc_mode': 'none',
            'detail_bias': 0.5,
            'practical_bias': 0.5,
            'reflective_bias': 0.5,
        }

    # Extract entropy values
    entropy_values = {}
    if hasattr(ctx, 'mlcr') and ctx.mlcr is not None:
        mlcr_entries = ctx.mlcr.entries if ctx.mlcr else {}
        if isinstance(mlcr_entries, dict):
            entropy_dict = mlcr_entries.get('explain_log', {}).get('entropy', {})
            entropy_values = {
                'H_D': entropy_dict.get('H_D', 0.0),
                'H_G': entropy_dict.get('H_G', 0.0),
                'H_K': entropy_dict.get('H_K', 0.0),
                'normalized_entropy': entropy_dict.get('normalized_entropy', 0.0),
            }

    # Extract coherence report
    coherence_report = {}
    if hasattr(ctx, 'coherence_report') and ctx.coherence_report is not None:
        coherence_report = ctx.coherence_report
    else:
        # Default coherence report
        coherence_report = {
            'coherence_score': 1.0,
            'persona_drift_score': 0.0,
            'semantic_stability_score': 1.0,
            'temporal_arc_score': 1.0,
            'mapper_volatility_score': 0.0,
            'turn_number': 0,
            'tier': 'unknown',
            'domain': 'unknown',
            'active_mappers': [],
        }

    # Phase 11 & 12: Ensure coherence_score_v2, coherence_score_v3, and coherence_v3_quality are included if available
    if hasattr(ctx, 'coherence_state') and ctx.coherence_state is not None:
        coherence_state = ctx.coherence_state
        coherence_score_v2 = getattr(coherence_state, 'coherence_score_v2', None)
        coherence_score_v3 = getattr(coherence_state, 'coherence_score_v3', None)
        coherence_v3_quality = getattr(coherence_state, 'coherence_v3_quality', None)

        if coherence_score_v2 is not None:
            coherence_report['coherence_score_v2'] = coherence_score_v2
        if coherence_score_v3 is not None:
            coherence_report['coherence_score_v3'] = coherence_score_v3
        if coherence_v3_quality is not None:
            coherence_report['coherence_v3_quality'] = coherence_v3_quality

    # Build metadata
    metadata = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'turn_index': coherence_report.get('turn_number', 0),
        'domain': routing_plan.get('domain', 'unknown'),
        'api_version': 'USU-API-v1.0',
        'pipeline_version': '3.0',
    }

    # Add user_id if available
    if hasattr(ctx, 'request') and ctx.request is not None:
        metadata['user_id'] = ctx.request.user_id

    # Extract session memory (Memory v2.0)
    session_memory_data = {}
    if hasattr(ctx, 'session_memory') and ctx.session_memory is not None:
        session_memory_data = ctx.session_memory.serialize()

    # Extract session recap (Session Summarizer v1.0)
    session_recap_data = {}
    if hasattr(ctx, 'session_recap') and ctx.session_recap is not None:
        session_recap_data = ctx.session_recap.serialize()

    # Extract intent arc (Intent Arc Engine v1.0)
    intent_arc_data = {}
    if hasattr(ctx, 'intent_arc') and ctx.intent_arc is not None:
        intent_arc_data = ctx.intent_arc.serialize()

    # Extract identity signature (Identity Signature Engine v1.0)
    identity_signature_data = {}
    if hasattr(ctx, 'identity_signature') and ctx.identity_signature is not None:
        identity_signature_data = ctx.identity_signature.serialize()

    # Extract motivation profile (Motivation Flow Engine v1.0)
    motivation_profile_data = {}
    if hasattr(ctx, 'motivation_profile') and ctx.motivation_profile is not None:
        motivation_profile_data = ctx.motivation_profile.serialize()

    # Phase 7: Extract trading guardrails (Trading Formula Guardrails v1.0)
    trading_guardrails_data = None
    if hasattr(ctx, 'trading_guardrails') and ctx.trading_guardrails is not None:
        trading_guardrails_data = ctx.trading_guardrails.to_dict()

    # Phase 2 & 3: Extract formulas from coherence state or pipeline context
    formulas_data = None
    if hasattr(ctx, 'coherence_state') and ctx.coherence_state is not None:
        coherence_state = ctx.coherence_state
        formulas_data = {}

        # Get most recent values from histories
        delta_smi_hist = getattr(coherence_state, 'delta_smi_history', [])
        if delta_smi_hist and delta_smi_hist[-1] is not None:
            formulas_data["delta_smi"] = delta_smi_hist[-1]

        bhava_gap_hist = getattr(coherence_state, 'bhava_gap_history', [])
        if bhava_gap_hist and bhava_gap_hist[-1] is not None:
            formulas_data["bhava_gap"] = bhava_gap_hist[-1]

        tension_corridor_hist = getattr(coherence_state, 'tension_corridor_history', [])
        if tension_corridor_hist and tension_corridor_hist[-1] is not None:
            formulas_data["tension_corridor"] = tension_corridor_hist[-1]

        # Get aggregates
        avg_smi = getattr(coherence_state, 'avg_smi', None)
        if avg_smi is not None:
            formulas_data["avg_smi"] = avg_smi

        max_smi = getattr(coherence_state, 'max_smi', None)
        if max_smi is not None:
            formulas_data["max_smi"] = max_smi

        min_smi = getattr(coherence_state, 'min_smi', None)
        if min_smi is not None:
            formulas_data["min_smi"] = min_smi

        avg_tension_corridor = getattr(coherence_state, 'avg_tension_corridor', None)
        if avg_tension_corridor is not None:
            formulas_data["avg_tension_corridor"] = avg_tension_corridor

        max_tension_corridor = getattr(coherence_state, 'max_tension_corridor', None)
        if max_tension_corridor is not None:
            formulas_data["max_tension_corridor"] = max_tension_corridor

        # Get current SMI from smi_history
        smi_hist = getattr(coherence_state, 'smi_history', [])
        if smi_hist and smi_hist[-1] is not None:
            formulas_data["smi"] = smi_hist[-1]

        # Phase 3: Extract derived metrics
        resonance_index = getattr(coherence_state, 'resonance_index', None)
        tension_index = getattr(coherence_state, 'tension_index', None)
        arc_alignment_index = getattr(coherence_state, 'arc_alignment_index', None)

        # Add derived metrics to formulas dict if any exist
        if resonance_index is not None or tension_index is not None or arc_alignment_index is not None:
            derived = {}
            if resonance_index is not None:
                derived["resonance_index"] = resonance_index
            if tension_index is not None:
                derived["tension_index"] = tension_index
            if arc_alignment_index is not None:
                derived["arc_alignment_index"] = arc_alignment_index
            formulas_data["derived"] = derived

        # Phase 8: Extract Guna/Kosha resonance metrics
        guna_resonance_index = getattr(coherence_state, 'guna_resonance_index', None)
        kosha_resonance_index = getattr(coherence_state, 'kosha_resonance_index', None)
        kosha_activation_vector = getattr(coherence_state, 'kosha_activation_vector', None)

        # Add Guna/Kosha metrics to formulas dict if any exist
        if guna_resonance_index is not None or kosha_resonance_index is not None:
            if guna_resonance_index is not None:
                formulas_data["guna_resonance_index"] = guna_resonance_index
            if kosha_resonance_index is not None:
                formulas_data["kosha_resonance_index"] = kosha_resonance_index
            if kosha_activation_vector is not None:
                formulas_data["kosha_activation_vector"] = kosha_activation_vector

        # Phase 14: Extract Vritti Momentum & Arc-Tension Harmonizer
        # Get most recent values from histories
        vmf_hist = getattr(coherence_state, 'vritti_momentum_history', [])
        if vmf_hist and vmf_hist[-1] is not None:
            formulas_data["vritti_momentum"] = vmf_hist[-1]

        ath_hist = getattr(coherence_state, 'arc_tension_harmonizer_history', [])
        if ath_hist and ath_hist[-1] is not None:
            formulas_data["arc_tension_harmonizer"] = ath_hist[-1]

        # Get Phase 14 aggregates
        avg_vritti_momentum = getattr(coherence_state, 'avg_vritti_momentum', None)
        if avg_vritti_momentum is not None:
            formulas_data["avg_vritti_momentum"] = avg_vritti_momentum

        max_vritti_momentum = getattr(coherence_state, 'max_vritti_momentum', None)
        if max_vritti_momentum is not None:
            formulas_data["max_vritti_momentum"] = max_vritti_momentum

        min_vritti_momentum = getattr(coherence_state, 'min_vritti_momentum', None)
        if min_vritti_momentum is not None:
            formulas_data["min_vritti_momentum"] = min_vritti_momentum

        avg_arc_tension_harmonizer = getattr(coherence_state, 'avg_arc_tension_harmonizer', None)
        if avg_arc_tension_harmonizer is not None:
            formulas_data["avg_arc_tension_harmonizer"] = avg_arc_tension_harmonizer

        max_arc_tension_harmonizer = getattr(coherence_state, 'max_arc_tension_harmonizer', None)
        if max_arc_tension_harmonizer is not None:
            formulas_data["max_arc_tension_harmonizer"] = max_arc_tension_harmonizer

        min_arc_tension_harmonizer = getattr(coherence_state, 'min_arc_tension_harmonizer', None)
        if min_arc_tension_harmonizer is not None:
            formulas_data["min_arc_tension_harmonizer"] = min_arc_tension_harmonizer

    return UnifiedOutput(
        text=text,
        symbolic=symbolic_layer,
        practical=practical_layer,
        mirror=mirror_layer,
        dha=dha_insights,
        routing=routing_plan,
        mappers=mapper_profile,
        entropy=entropy_values,
        coherence=coherence_report,
        metadata=metadata,
        session_memory=session_memory_data,
        session_recap=session_recap_data,
        intent_arc=intent_arc_data,
        identity_signature=identity_signature_data,
        motivation_profile=motivation_profile_data,
        formulas=formulas_data,
        trading_guardrails=trading_guardrails_data,
    )


def get_unified_json(ctx: Any) -> Dict[str, Any]:
    """
    Get complete unified JSON output from pipeline context.

    This is the main public API function for getting the full unified output.

    Args:
        ctx: PipelineContext after pipeline execution

    Returns:
        Dictionary with complete unified output structure

    Usage:
        unified = get_unified_json(ctx)
        print(json.dumps(unified, indent=2))
    """
    # Extract final text
    final_text = ""
    if hasattr(ctx, 'rendered') and ctx.rendered is not None:
        final_text = ctx.rendered.raw_text
    elif hasattr(ctx, 'dha') and ctx.dha is not None:
        final_text = ctx.dha.guarded_text

    unified = build_unified_output(final_text, ctx)
    return unified.to_dict()


def get_public_response(ctx: Any) -> Dict[str, Any]:
    """
    Get trimmed public response for UI/API consumers.

    This function returns a simplified version of the unified output
    suitable for public-facing APIs and UI dashboards.

    Args:
        ctx: PipelineContext after pipeline execution

    Returns:
        Dictionary with public-facing response fields

    Usage:
        public = get_public_response(ctx)
        return jsonify(public)  # Flask example
    """
    unified = get_unified_json(ctx)

    # Extract coherence summary
    coherence = unified.get('coherence', {})
    coherence_summary = {
        'coherence_score': coherence.get('coherence_score', 0.0),
        'state': _get_coherence_state_label(coherence.get('coherence_score', 0.0)),
    }

    # Extract session memory (Memory v2.0) - trim to last 1-2 significant events
    session_memory = unified.get('session_memory', {})
    trimmed_memory = _trim_session_memory_for_public(session_memory)

    # Extract session recap (Session Summarizer v1.0) - trim to public fields
    session_recap = unified.get('session_recap', {})
    trimmed_recap = _trim_session_recap_for_public(session_recap)

    # Extract identity signature (Identity Signature Engine v1.0) - trim to public fields
    identity_signature = unified.get('identity_signature', {})
    trimmed_identity_signature = _trim_identity_signature_for_public(identity_signature)

    # Build public response
    return {
        'text': unified.get('text', ''),
        'symbolic': unified.get('symbolic', {}),
        'practical': unified.get('practical', {}),
        'mirror': unified.get('mirror', {}),
        'dha': {
            'delivery_profile': unified.get('dha', {}).get('delivery_profile', 'unknown'),
            'readiness_level': unified.get('dha', {}).get('readiness_level', 'unknown'),
        },
        'coherence': coherence_summary,
        'mappers': unified.get('mappers', {}),
        'domain': unified.get('metadata', {}).get('domain', 'unknown'),
        'timestamp': unified.get('metadata', {}).get('timestamp', ''),
        'session_memory': trimmed_memory,
        'session_recap': trimmed_recap,
        'identity_signature': trimmed_identity_signature,
    }


def get_internal_diagnostics(ctx: Any) -> Dict[str, Any]:
    """
    Get complete internal diagnostics for debugging and observability.

    This function returns the full unified output with additional
    debug information for internal use.

    Args:
        ctx: PipelineContext after pipeline execution

    Returns:
        Dictionary with complete diagnostics including all raw data

    Usage:
        diagnostics = get_internal_diagnostics(ctx)
        logger.debug(f"Pipeline diagnostics: {diagnostics}")
    """
    unified = get_unified_json(ctx)

    # Add additional diagnostics
    diagnostics = unified.copy()

    # Add raw context summary
    diagnostics['_internal'] = {
        'has_fusion': hasattr(ctx, 'fusion') and ctx.fusion is not None,
        'has_dha': hasattr(ctx, 'dha') and ctx.dha is not None,
        'has_mlcr': hasattr(ctx, 'mlcr') and ctx.mlcr is not None,
        'has_coherence': hasattr(ctx, 'coherence_report') and ctx.coherence_report is not None,
        'has_rendered': hasattr(ctx, 'rendered') and ctx.rendered is not None,
        'router_mode': ctx.router_mode if hasattr(ctx, 'router_mode') else 'unknown',
    }

    return diagnostics


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _remove_none_values(d: Any) -> Any:
    """
    Recursively remove None values from dictionary.

    Args:
        d: Dictionary or value to process

    Returns:
        Cleaned dictionary or value
    """
    if isinstance(d, dict):
        return {k: _remove_none_values(v) for k, v in d.items() if v is not None}
    elif isinstance(d, list):
        return [_remove_none_values(item) for item in d]
    else:
        return d


def _get_coherence_state_label(score: float) -> str:
    """
    Get human-readable coherence state label.

    Args:
        score: Coherence score (0-1)

    Returns:
        State label (Excellent/Good/Fair/Poor)
    """
    if score >= 0.85:
        return "Excellent"
    elif score >= 0.7:
        return "Good"
    elif score >= 0.5:
        return "Fair"
    else:
        return "Poor"


def _trim_session_memory_for_public(session_memory: Dict[str, Any]) -> Dict[str, Any]:
    """
    Trim session memory to only significant events for public API.

    Shows only last 1-2 memory entries of types:
    - breakthrough
    - stabilization
    - mapper_flip

    Filters out raw metrics for public consumption.

    Args:
        session_memory: Full session memory dictionary

    Returns:
        Trimmed session memory dictionary
    """
    if not session_memory or 'events' not in session_memory:
        return {}

    events = session_memory.get('events', [])

    # Filter to significant event types
    significant_types = {'breakthrough', 'stabilization', 'mapper_flip'}
    significant_events = [
        e for e in events
        if e.get('event_type') in significant_types
    ]

    # Get last 2 significant events
    recent_significant = significant_events[-2:] if len(significant_events) >= 2 else significant_events

    # Remove raw metrics for public API (keep only description and type)
    trimmed_events = []
    for event in recent_significant:
        trimmed_events.append({
            'turn_index': event.get('turn_index'),
            'event_type': event.get('event_type'),
            'description': event.get('description'),
        })

    return {
        'events': trimmed_events,
        'event_count': len(events),
    }


def _trim_session_recap_for_public(session_recap: Dict[str, Any]) -> Dict[str, Any]:
    """
    Trim session recap to public-safe fields.

    Exposes only:
    - overall_state
    - net_trajectory
    - last 1-2 turning points (breakthrough, stabilization, fragmentation)
    - recommended_style

    Never exposes raw metrics or full mapper journey.

    Args:
        session_recap: Full session recap dictionary

    Returns:
        Trimmed session recap dictionary for public API
    """
    if not session_recap:
        return {}

    # Extract public fields
    overall_state = session_recap.get('overall_state')
    net_trajectory = session_recap.get('net_trajectory')
    recommended_style = session_recap.get('recommended_style')
    turning_points = session_recap.get('turning_points', [])

    # Filter turning points to significant types only
    significant_types = {'breakthrough', 'stabilization', 'fragmentation'}
    significant_turning_points = [
        tp for tp in turning_points
        if tp.get('event_type') in significant_types
    ]

    # Get last 1-2 significant turning points
    recent_turning_points = significant_turning_points[-2:] if len(significant_turning_points) >= 2 else significant_turning_points

    # Remove metrics from turning points for public API
    trimmed_turning_points = []
    for tp in recent_turning_points:
        trimmed_turning_points.append({
            'turn_index': tp.get('turn_index'),
            'event_type': tp.get('event_type'),
            'description': tp.get('description'),
        })

    return {
        'overall_state': overall_state,
        'net_trajectory': net_trajectory,
        'recommended_style': recommended_style,
        'recent_turning_points': trimmed_turning_points,
    }


def _trim_identity_signature_for_public(identity_signature: Dict[str, Any]) -> Dict[str, Any]:
    """
    Trim identity signature to public-safe fields.

    Exposes only:
    - signature_type
    - confidence
    - last 2 markers (identity-related session markers)
    - driver summary (count of drivers, not full list)

    Never exposes full driver list or all markers.

    Args:
        identity_signature: Full identity signature dictionary

    Returns:
        Trimmed identity signature dictionary for public API
    """
    if not identity_signature:
        return {}

    # Extract public fields
    signature_type = identity_signature.get('signature_type')
    confidence = identity_signature.get('confidence')
    markers = identity_signature.get('markers', [])
    drivers = identity_signature.get('drivers', [])

    # Get last 2 markers
    recent_markers = markers[-2:] if len(markers) >= 2 else markers

    # Driver summary (count only, not full list)
    driver_summary = {
        'count': len(drivers),
        'primary': drivers[0] if drivers else None,
    }

    return {
        'signature_type': signature_type,
        'confidence': confidence,
        'recent_markers': recent_markers,
        'driver_summary': driver_summary,
    }


# Public API
__all__ = [
    'UnifiedOutput',
    'build_unified_output',
    'get_unified_json',
    'get_public_response',
    'get_internal_diagnostics',
]
