"""
Unified Dashboard Renderers (Phase 20 v1.0)

This module provides pure-Python text renderers for UnifiedSessionAnalytics.
All renderers are deterministic, zero-LLM, and suitable for CLI/logging.

Design Principles:
    1. Zero-LLM (no model calls)
    2. Deterministic (same input → same output)
    3. Human-readable (CLI-friendly formatting)
    4. ASCII-safe (no fancy unicode)
    5. Compact (suitable for logs)
"""

from typing import List
from agentic.tools.unified_dashboard.models import UnifiedSessionAnalytics, MetricSparkline


def render_session_overview(analytics: UnifiedSessionAnalytics) -> str:
    """
    Render a multi-line human-readable session overview.

    Includes:
    - Session metadata (ID, domain, turn count)
    - Core coherence metrics
    - Semantic & drift metrics
    - Temporal & entropy metrics
    - Intent/Identity/Motivation
    - Aggregated bands
    - Session note

    Args:
        analytics: UnifiedSessionAnalytics to render

    Returns:
        Multi-line formatted string suitable for CLI/logs
    """
    lines = []

    # Header
    lines.append("=" * 70)
    lines.append("  UNIFIED SESSION ANALYTICS OVERVIEW")
    lines.append("=" * 70)
    lines.append("")

    # Session Metadata
    lines.append(f"Session ID:     {analytics.session_id}")
    lines.append(f"Domain:         {analytics.domain or 'unknown'}")
    lines.append(f"Turn Count:     {analytics.turn_count}")
    lines.append("")

    # Core Coherence
    lines.append("--- COHERENCE METRICS ---")
    lines.append(f"  Coherence v1 (Legacy):      {_format_metric(analytics.coherence_v1)}")
    lines.append(f"  Coherence v2 (Enhanced):    {_format_metric(analytics.coherence_v2)}")
    lines.append(f"  Coherence v3 (Multi-Track): {_format_metric(analytics.coherence_v3)}")
    lines.append(f"  Coherence Fused:            {_format_metric(analytics.coherence_fused)}")
    lines.append(f"  Coherence v3 Quality:       {_format_metric(analytics.coherence_v3_quality)}")
    lines.append("")

    # Semantic & Drift
    lines.append("--- SEMANTIC & DRIFT ---")
    lines.append(f"  Semantic Integrity:         {_format_metric(analytics.semantic_integrity_score)}")
    lines.append(f"  Cognitive Drift v3:         {_format_metric(analytics.cognitive_drift_v3)}")
    lines.append(f"  Drift Band:                 {analytics.drift_band or 'unknown'}")
    lines.append(f"  Semantic Band:              {analytics.semantic_band or 'unknown'}")
    lines.append("")

    # Temporal & Entropy
    lines.append("--- TEMPORAL & ENTROPY ---")
    lines.append(f"  Temporal Arc Score:         {_format_metric(analytics.temporal_arc_score)}")
    lines.append(f"  Normalized Entropy Diff:    {_format_metric(analytics.normalized_entropy_diff)}")
    lines.append(f"  Entropy Volatility:         {_format_metric(analytics.entropy_volatility)}")
    lines.append(f"  Instantaneous Entropy:      {_format_metric(analytics.instantaneous_entropy)}")
    lines.append("")

    # Intent/Identity/Motivation
    lines.append("--- INTENT / IDENTITY / MOTIVATION ---")
    lines.append(f"  Intent Arc Type:            {analytics.intent_arc_type or 'unknown'}")
    lines.append(f"  Identity Signature:         {analytics.identity_signature or 'unknown'}")
    lines.append(f"  Motivation Type:            {analytics.motivation_type or 'unknown'}")
    lines.append(f"  Motivation Band:            {analytics.motivation_band or 'unknown'}")
    lines.append("")

    # Formula / Resonance
    lines.append("--- FORMULA / RESONANCE ---")
    lines.append(f"  Avg Enhanced SMI:           {_format_metric(analytics.avg_enhanced_smi)}")
    lines.append(f"  Resonance Index:            {_format_metric(analytics.resonance_index)}")
    lines.append(f"  Tension Index:              {_format_metric(analytics.tension_index)}")
    lines.append(f"  Arc Alignment Index:        {_format_metric(analytics.arc_alignment_index)}")
    lines.append(f"  Guna Resonance:             {_format_metric(analytics.guna_resonance_index)}")
    lines.append(f"  Kosha Resonance:            {_format_metric(analytics.kosha_resonance_index)}")
    lines.append("")

    # Aggregated Bands
    lines.append("--- AGGREGATED BANDS ---")
    lines.append(f"  Stability Band:             {analytics.stability_band or 'unknown'}")
    lines.append(f"  Drift Band:                 {analytics.drift_band or 'unknown'}")
    lines.append(f"  Semantic Band:              {analytics.semantic_band or 'unknown'}")
    lines.append(f"  Motivation Band:            {analytics.motivation_band or 'unknown'}")
    lines.append("")

    # Pattern Tags
    if analytics.session_pattern_tags:
        lines.append("--- SESSION PATTERN TAGS ---")
        lines.append(f"  {', '.join(analytics.session_pattern_tags)}")
        lines.append("")

    # Session Note
    if analytics.note:
        lines.append("--- SESSION NOTE ---")
        lines.append(f"  {analytics.note}")
        lines.append("")

    lines.append("=" * 70)

    return "\n".join(lines)


def render_risk_panel(analytics: UnifiedSessionAnalytics) -> str:
    """
    Render a focused risk panel summarizing key risk indicators.

    Includes:
    - Stability band
    - Drift band
    - Semantic band
    - Key pattern tags
    - Risk recommendations

    Args:
        analytics: UnifiedSessionAnalytics to render

    Returns:
        Multi-line formatted risk panel
    """
    lines = []

    lines.append("=" * 70)
    lines.append("  RISK PANEL")
    lines.append("=" * 70)
    lines.append("")

    # Risk Bands
    lines.append("--- RISK BANDS ---")
    lines.append(f"  Stability:       {_format_band(analytics.stability_band)}")
    lines.append(f"  Drift:           {_format_band(analytics.drift_band)}")
    lines.append(f"  Semantic:        {_format_band(analytics.semantic_band)}")
    lines.append("")

    # Key Metrics
    lines.append("--- KEY METRICS ---")
    lines.append(f"  Coherence Fused:    {_format_metric(analytics.coherence_fused)}")
    lines.append(f"  Cognitive Drift:    {_format_metric(analytics.cognitive_drift_v3)}")
    lines.append(f"  Entropy Volatility: {_format_metric(analytics.entropy_volatility)}")
    lines.append("")

    # Pattern Tags
    if analytics.session_pattern_tags:
        lines.append("--- ACTIVE PATTERNS ---")
        for tag in analytics.session_pattern_tags:
            lines.append(f"  - {tag}")
        lines.append("")

    # Recommendations
    lines.append("--- RECOMMENDATIONS ---")
    recommendations = _generate_recommendations(analytics)
    for rec in recommendations:
        lines.append(f"  - {rec}")
    lines.append("")

    lines.append("=" * 70)

    return "\n".join(lines)


def render_timeline_panel(analytics: UnifiedSessionAnalytics) -> str:
    """
    Render ASCII-style sparklines for key metrics over time.

    Shows coarse sparklines for:
    - Coherence trend
    - Drift trend
    - Entropy trend

    Args:
        analytics: UnifiedSessionAnalytics to render

    Returns:
        Multi-line formatted timeline panel with sparklines
    """
    lines = []

    lines.append("=" * 70)
    lines.append("  TIMELINE PANEL")
    lines.append("=" * 70)
    lines.append("")

    # Coherence Sparkline
    lines.append("--- COHERENCE TREND ---")
    coherence_spark = _render_sparkline(analytics.coherence_sparkline)
    lines.append(f"  {coherence_spark}")
    lines.append("")

    # Drift Sparkline
    lines.append("--- DRIFT TREND ---")
    drift_spark = _render_sparkline(analytics.drift_sparkline)
    lines.append(f"  {drift_spark}")
    lines.append("")

    # Entropy Sparkline
    lines.append("--- ENTROPY TREND ---")
    entropy_spark = _render_sparkline(analytics.entropy_sparkline)
    lines.append(f"  {entropy_spark}")
    lines.append("")

    lines.append("=" * 70)

    return "\n".join(lines)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _format_metric(value: float | None) -> str:
    """
    Format a metric value for display.

    Args:
        value: Metric value (0.0-1.0 or None)

    Returns:
        Formatted string (e.g., "0.75" or "N/A")
    """
    if value is None:
        return "N/A"
    return f"{value:.2f}"


def _format_band(band: str | None) -> str:
    """
    Format a band classification for display.

    Args:
        band: Band classification string

    Returns:
        Formatted string with visual indicator
    """
    if band is None:
        return "unknown"

    # Add visual indicators
    if band in ["stable", "low", "coherent"]:
        return f"{band} [OK]"
    elif band in ["moderate", "mixed", "transition"]:
        return f"{band} [WATCH]"
    elif band in ["high", "unstable", "fragile"]:
        return f"{band} [ALERT]"
    else:
        return band


def _generate_recommendations(analytics: UnifiedSessionAnalytics) -> List[str]:
    """
    Generate deterministic recommendations based on analytics.

    Args:
        analytics: UnifiedSessionAnalytics

    Returns:
        List of recommendation strings
    """
    recommendations = []

    # Stability recommendations
    if analytics.stability_band == "unstable":
        recommendations.append("Session is unstable. Consider grounding interventions.")
    elif analytics.stability_band == "transition":
        recommendations.append("Session is in transition. Monitor closely for stabilization.")

    # Drift recommendations
    if analytics.drift_band == "high":
        recommendations.append("High cognitive drift detected. Recommend semantic anchoring.")
    elif analytics.drift_band == "moderate":
        recommendations.append("Moderate drift. Monitor for escalation.")

    # Semantic recommendations
    if analytics.semantic_band == "fragile":
        recommendations.append("Fragile semantic integrity. Increase coherence scaffolding.")

    # Entropy recommendations
    if analytics.entropy_volatility and analytics.entropy_volatility > 0.65:
        recommendations.append("High entropy volatility. Consider stabilization strategies.")

    # Default recommendation
    if not recommendations:
        recommendations.append("Session metrics are within normal ranges. Continue monitoring.")

    return recommendations


def _render_sparkline(sparkline: MetricSparkline, width: int = 50) -> str:
    """
    Render ASCII-style sparkline for metric values.

    Args:
        sparkline: MetricSparkline with values to render
        width: Character width for sparkline (default: 50)

    Returns:
        ASCII sparkline string
    """
    if not sparkline.values:
        return "[No data available]"

    # Use simple bar chart representation
    values = sparkline.values[-width:]  # Take last N values
    if not values:
        return "[No data available]"

    # Normalize to 0-1 range
    min_val = min(values)
    max_val = max(values)

    if max_val == min_val:
        # All values are the same
        normalized = [0.5] * len(values)
    else:
        normalized = [(v - min_val) / (max_val - min_val) for v in values]

    # Create bar chart using ASCII characters
    # Use height of 5 levels: ' ', '.', ':', '|', '#'
    chars = [' ', '.', ':', '|', '#']
    sparkline_str = ""

    for val in normalized:
        idx = min(int(val * len(chars)), len(chars) - 1)
        sparkline_str += chars[idx]

    # Add summary
    summary = f"[{len(values)} pts | min={min_val:.2f} | max={max_val:.2f} | last={values[-1]:.2f}]"

    return f"{sparkline_str} {summary}"


# Public API
__all__ = [
    "render_session_overview",
    "render_risk_panel",
    "render_timeline_panel",
]
