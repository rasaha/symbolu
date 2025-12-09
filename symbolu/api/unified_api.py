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


# Public API
__all__ = [
    'UnifiedOutput',
    'build_unified_output',
    'get_unified_json',
    'get_public_response',
    'get_internal_diagnostics',
]
