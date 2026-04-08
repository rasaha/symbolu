"""
Coherence API - External API exposure for coherence observability.

Zero-LLM, deterministic, rule-based API functions for coherence metrics.
Does not modify any core engine behavior.

Functions:
    - get_coherence_report: Detailed coherence state report
    - get_turn_summary: Single-turn summary from PipelineContext
    - get_multi_turn_overview: Multi-turn trend analysis and recommendations
"""

from typing import Dict, Any, List, Optional
import statistics


def get_coherence_report(coherence_state: Any) -> Dict[str, Any]:
    """
    Generate a comprehensive coherence report from CoherenceState.

    Args:
        coherence_state: CoherenceState instance

    Returns:
        JSON-safe dict with:
            - coherence_score: Overall score (0.0-1.0)
            - components: Individual metric scores
            - history_window: Number of turns in sliding window
            - is_stabilizing: Boolean stabilization indicator
            - is_recovering: Boolean recovery indicator
            - state_vector: Recent history snapshot
    """
    if coherence_state is None:
        return {
            "coherence_score": 0.0,
            "components": {
                "persona_drift": 0.0,
                "semantic_stability": 0.0,
                "temporal_arc": 0.0,
                "mapper_volatility": 0.0,
            },
            "history_window": 0,
            "is_stabilizing": False,
            "is_recovering": False,
            "state_vector": [],
        }

    # Extract core metrics
    coherence_score = getattr(coherence_state, 'coherence_score', 0.0)
    persona_drift = getattr(coherence_state, 'persona_drift_score', 0.0)
    semantic_stability = getattr(coherence_state, 'semantic_stability_score', 0.0)
    temporal_arc = getattr(coherence_state, 'temporal_arc_score', 0.0)
    mapper_volatility = getattr(coherence_state, 'mapper_volatility_score', 0.0)

    # Extract history length
    history_length = getattr(coherence_state, 'turn_index', 0)

    # Check stabilization patterns
    is_stabilizing = _check_stabilization(coherence_state)
    is_recovering = _check_recovery(coherence_state)

    # Build state vector (recent history snapshot)
    state_vector = _build_state_vector(coherence_state)

    return {
        "coherence_score": round(coherence_score, 4),
        "components": {
            "persona_drift": round(persona_drift, 4),
            "semantic_stability": round(semantic_stability, 4),
            "temporal_arc": round(temporal_arc, 4),
            "mapper_volatility": round(mapper_volatility, 4),
        },
        "history_window": history_length,
        "is_stabilizing": is_stabilizing,
        "is_recovering": is_recovering,
        "state_vector": state_vector,
    }


def get_turn_summary(context: Any) -> Dict[str, Any]:
    """
    Generate a single-turn summary from PipelineContext.

    Args:
        context: PipelineContext instance

    Returns:
        JSON-safe dict with turn-level metadata and coherence metrics
    """
    # Extract MLCR/TTOR metadata
    tier = "unknown"
    domain = "unknown"
    flow_mode = "unknown"
    normalized_entropy = 0.0
    long_arc_tension = 0.0

    mlcr = getattr(context, 'mlcr', None)
    if mlcr is not None:
        routing_plan = getattr(mlcr, 'routing_plan', None)
        if routing_plan is not None:
            tier = str(getattr(routing_plan, 'tier', 'unknown'))
            domain = getattr(routing_plan, 'domain', 'unknown')
            flow_mode = str(getattr(routing_plan, 'flow_mode', 'unknown'))
            normalized_entropy = getattr(routing_plan, 'normalized_entropy', 0.0)
            long_arc_tension = getattr(routing_plan, 'long_arc_tension', 0.0)

    # Detect active mappers
    active_mappers = []
    if getattr(context, 'hrm_map', None) is not None:
        active_mappers.append("HRM")
    if getattr(context, 'lcm_map', None) is not None:
        active_mappers.append("LCM")
    if getattr(context, 'lam_map', None) is not None:
        active_mappers.append("LAM")

    # Extract coherence state if available
    coherence_state = getattr(context, 'coherence_state', None)
    coherence_metrics = {}

    if coherence_state is not None:
        coherence_metrics = {
            "coherence_score": getattr(coherence_state, 'coherence_score', 0.0),
            "persona_drift": getattr(coherence_state, 'persona_drift_score', 0.0),
            "semantic_stability": getattr(coherence_state, 'semantic_stability_score', 0.0),
            "temporal_arc": getattr(coherence_state, 'temporal_arc_score', 0.0),
            "mapper_volatility": getattr(coherence_state, 'mapper_volatility_score', 0.0),
            "turn_index": getattr(coherence_state, 'turn_index', 0),
        }

    return {
        "tier": tier,
        "domain": domain,
        "flow_mode": flow_mode,
        "normalized_entropy": round(normalized_entropy, 4),
        "long_arc_tension": round(long_arc_tension, 4),
        "active_mappers": active_mappers,
        "coherence_metrics": coherence_metrics,
    }


def get_multi_turn_overview(history: List[Any]) -> Dict[str, Any]:
    """
    Generate a multi-turn overview from a list of PipelineContext objects.

    Zero-LLM, rule-based analysis only.

    Args:
        history: List of PipelineContext instances

    Returns:
        JSON-safe dict with:
            - average_coherence: Mean coherence across turns
            - drift_trend_slope: Trend in persona drift
            - temporal_arc_trend: Trend in temporal coherence
            - mapper_volatility_trend: Trend in mapper switching
            - recommendations: List of stabilization suggestions
    """
    if not history:
        return {
            "average_coherence": 0.0,
            "drift_trend_slope": 0.0,
            "temporal_arc_trend": 0.0,
            "mapper_volatility_trend": 0.0,
            "turn_count": 0,
            "recommendations": [],
        }

    # Extract metrics from all contexts
    coherence_scores = []
    drift_scores = []
    temporal_scores = []
    volatility_scores = []
    mapper_usage = {"HRM": 0, "LCM": 0, "LAM": 0}
    tier_distribution = {"lower": 0, "upper": 0, "hybrid": 0}
    domain_set = set()

    for ctx in history:
        coherence_state = getattr(ctx, 'coherence_state', None)
        if coherence_state is not None:
            coherence_scores.append(getattr(coherence_state, 'coherence_score', 0.0))
            drift_scores.append(getattr(coherence_state, 'persona_drift_score', 0.0))
            temporal_scores.append(getattr(coherence_state, 'temporal_arc_score', 0.0))
            volatility_scores.append(getattr(coherence_state, 'mapper_volatility_score', 0.0))

        # Track mapper usage
        if getattr(ctx, 'hrm_map', None) is not None:
            mapper_usage["HRM"] += 1
        if getattr(ctx, 'lcm_map', None) is not None:
            mapper_usage["LCM"] += 1
        if getattr(ctx, 'lam_map', None) is not None:
            mapper_usage["LAM"] += 1

        # Track tier distribution
        mlcr = getattr(ctx, 'mlcr', None)
        if mlcr is not None:
            routing_plan = getattr(mlcr, 'routing_plan', None)
            if routing_plan is not None:
                tier = str(getattr(routing_plan, 'tier', 'unknown'))
                if tier in tier_distribution:
                    tier_distribution[tier] += 1

                domain = getattr(routing_plan, 'domain', None)
                if domain:
                    domain_set.add(domain)

    # Calculate averages
    avg_coherence = statistics.mean(coherence_scores) if coherence_scores else 0.0
    avg_drift = statistics.mean(drift_scores) if drift_scores else 0.0
    avg_temporal = statistics.mean(temporal_scores) if temporal_scores else 0.0
    avg_volatility = statistics.mean(volatility_scores) if volatility_scores else 0.0

    # Calculate trends (simple linear approximation)
    drift_trend = _calculate_trend(drift_scores)
    temporal_trend = _calculate_trend(temporal_scores)
    volatility_trend = _calculate_trend(volatility_scores)

    # Generate recommendations (rule-based)
    recommendations = _generate_recommendations(
        avg_coherence=avg_coherence,
        avg_drift=avg_drift,
        avg_volatility=avg_volatility,
        drift_trend=drift_trend,
        temporal_trend=temporal_trend,
        mapper_usage=mapper_usage,
        tier_distribution=tier_distribution,
        domain_set=domain_set,
    )

    return {
        "average_coherence": round(avg_coherence, 4),
        "average_drift": round(avg_drift, 4),
        "average_temporal_arc": round(avg_temporal, 4),
        "average_volatility": round(avg_volatility, 4),
        "drift_trend_slope": round(drift_trend, 4),
        "temporal_arc_trend": round(temporal_trend, 4),
        "mapper_volatility_trend": round(volatility_trend, 4),
        "turn_count": len(history),
        "mapper_usage": mapper_usage,
        "tier_distribution": tier_distribution,
        "domains": sorted(list(domain_set)),
        "recommendations": recommendations,
    }


# Helper functions

def _check_stabilization(coherence_state: Any) -> bool:
    """Check if coherence is stabilizing based on drift score."""
    drift = getattr(coherence_state, 'persona_drift_score', 0.0)
    return drift < 0.3


def _check_recovery(coherence_state: Any) -> bool:
    """Check if coherence is recovering based on temporal arc and bhava."""
    temporal_arc = getattr(coherence_state, 'temporal_arc_score', 0.0)

    bhava_dir_history = getattr(coherence_state, 'bhava_direction_history', [])
    if bhava_dir_history:
        recent_direction = bhava_dir_history[-1]
        if recent_direction == "upward" and temporal_arc > 0.6:
            return True

    return False


def _build_state_vector(coherence_state: Any) -> List[float]:
    """Build a compact state vector from recent history."""
    tier_history = getattr(coherence_state, 'tier_history', [])
    domain_history = getattr(coherence_state, 'domain_history', [])
    smi_history = getattr(coherence_state, 'smi_history', [])

    # Return most recent values
    return {
        "recent_tiers": tier_history[-5:] if len(tier_history) > 0 else [],
        "recent_domains": domain_history[-5:] if len(domain_history) > 0 else [],
        "recent_smi": [round(x, 3) for x in smi_history[-5:]] if len(smi_history) > 0 else [],
    }


def _calculate_trend(values: List[float]) -> float:
    """
    Calculate simple linear trend (slope) from a list of values.

    Positive = increasing, Negative = decreasing, ~0 = stable
    """
    if len(values) < 2:
        return 0.0

    n = len(values)
    x_mean = (n - 1) / 2.0
    y_mean = statistics.mean(values)

    numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return 0.0

    return numerator / denominator


def _generate_recommendations(
    avg_coherence: float,
    avg_drift: float,
    avg_volatility: float,
    drift_trend: float,
    temporal_trend: float,
    mapper_usage: Dict[str, int],
    tier_distribution: Dict[str, int],
    domain_set: set,
) -> List[str]:
    """
    Generate rule-based stabilization recommendations.

    Zero-LLM, deterministic only.
    """
    recommendations = []

    # High drift
    if avg_drift > 0.5:
        recommendations.append("High persona drift detected. Consider using LCM for grounding.")

    # Increasing drift trend
    if drift_trend > 0.1:
        recommendations.append("Drift is increasing. Monitor for identity shifts.")

    # High volatility
    if avg_volatility > 0.5:
        recommendations.append("High mapper volatility. Stabilize mapper selection logic.")

    # Low coherence
    if avg_coherence < 0.4:
        recommendations.append("Low overall coherence. Review semantic skeleton stability.")

    # LAM activation patterns
    if "identity" in domain_set or "therapy" in domain_set or "spiritual" in domain_set:
        if mapper_usage.get("LAM", 0) > 0:
            recommendations.append("LAM active due to identity/arc domains. This is expected.")
        else:
            recommendations.append("Identity domain detected but LAM not used. Consider activating LAM.")

    # Temporal arc trends
    if temporal_trend < -0.1:
        recommendations.append("Temporal arc declining. Check for narrative discontinuities.")

    # Tier imbalance
    total_turns = sum(tier_distribution.values())
    if total_turns > 0:
        lower_ratio = tier_distribution.get("lower", 0) / total_turns
        if lower_ratio > 0.8:
            recommendations.append("Predominantly LOWER tier. Consider balancing with reflective queries.")
        elif lower_ratio < 0.2:
            recommendations.append("Predominantly UPPER tier. Consider grounding with concrete tasks.")

    # Default recommendation
    if not recommendations:
        recommendations.append("Coherence is stable. No immediate action needed.")

    return recommendations
