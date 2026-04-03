"""
Unified Consciousness Dashboard & Analytics v1.0

This module provides a deterministic, zero-LLM, read-only analytics layer that:
  - Aggregates all major Symbol-U v3.0 metrics (coherence, formulas, drift, intent, identity, motivation, entropy, etc.)
  - Produces unified dashboard views and summaries for sessions
  - Exposes these via Python dashboard helpers and optional HTTP endpoints
  - Does NOT modify routing, mappers, policy, or pipeline behavior

Design Principles:
    1. Zero-LLM (no model calls, pure read-only analytics)
    2. Non-invasive (no behavior change to TTOR, MLCR, mappers, Fusion, DHA, Renderer)
    3. Observation-only (dashboards & summaries only)
    4. Deterministic (same state → same analytics)
    5. CI-safe, fully tested

Usage:
    from agentic.tools.unified_dashboard import build_unified_session_analytics

    # Build analytics for a session
    analytics = build_unified_session_analytics(session_id)

    if analytics:
        print(render_session_overview(analytics))
"""

from agentic.tools.unified_dashboard.models import (
    MetricSparkline,
    MetricBandStatus,
    UnifiedSessionAnalytics,
)

from agentic.tools.unified_dashboard.aggregators import (
    build_unified_session_analytics,
)

from agentic.tools.unified_dashboard.renderers import (
    render_session_overview,
    render_risk_panel,
    render_timeline_panel,
)

from agentic.tools.unified_dashboard.cli import (
    print_session_dashboard,
)

__all__ = [
    # Models
    "MetricSparkline",
    "MetricBandStatus",
    "UnifiedSessionAnalytics",
    # Aggregators
    "build_unified_session_analytics",
    # Renderers
    "render_session_overview",
    "render_risk_panel",
    "render_timeline_panel",
    # CLI
    "print_session_dashboard",
]
