"""
Unified Dashboard CLI (Phase 20 v1.0)

This module provides simple CLI entrypoints for developers to view
session dashboards and analytics.

Design Principles:
    1. Zero-LLM (no model calls)
    2. Deterministic (same input → same output)
    3. Developer-friendly (for debugging and testing)
    4. Non-invasive (does not modify session state)

Usage:
    from agentic.pipeline_tools.unified_dashboard.cli import print_session_dashboard

    # Print full dashboard for a session
    print_session_dashboard("abc123...")
"""

from typing import Optional
from agentic.pipeline_tools.unified_dashboard.aggregators import build_unified_session_analytics
from agentic.pipeline_tools.unified_dashboard.renderers import (
    render_session_overview,
    render_risk_panel,
    render_timeline_panel,
)


def print_session_dashboard(session_id: str) -> None:
    """
    Print complete dashboard for a session to stdout.

    This is a convenience function for developers to quickly view
    all analytics for a session.

    Prints:
    - Session overview (all metrics)
    - Risk panel (key risk indicators)
    - Timeline panel (sparklines)

    Args:
        session_id: Session identifier

    Output:
        Prints formatted dashboard to stdout, or "not found" message
    """
    # Build analytics
    analytics = build_unified_session_analytics(session_id)

    if analytics is None:
        print(f"Session {session_id} not found.")
        return

    # Print all panels
    print(render_session_overview(analytics))
    print()
    print(render_risk_panel(analytics))
    print()
    print(render_timeline_panel(analytics))


def print_session_overview_only(session_id: str) -> None:
    """
    Print only the overview panel for a session.

    Args:
        session_id: Session identifier

    Output:
        Prints overview to stdout, or "not found" message
    """
    analytics = build_unified_session_analytics(session_id)

    if analytics is None:
        print(f"Session {session_id} not found.")
        return

    print(render_session_overview(analytics))


def print_risk_panel_only(session_id: str) -> None:
    """
    Print only the risk panel for a session.

    Args:
        session_id: Session identifier

    Output:
        Prints risk panel to stdout, or "not found" message
    """
    analytics = build_unified_session_analytics(session_id)

    if analytics is None:
        print(f"Session {session_id} not found.")
        return

    print(render_risk_panel(analytics))


def print_timeline_panel_only(session_id: str) -> None:
    """
    Print only the timeline panel for a session.

    Args:
        session_id: Session identifier

    Output:
        Prints timeline panel to stdout, or "not found" message
    """
    analytics = build_unified_session_analytics(session_id)

    if analytics is None:
        print(f"Session {session_id} not found.")
        return

    print(render_timeline_panel(analytics))


def get_session_analytics_json(session_id: str) -> Optional[str]:
    """
    Get session analytics as JSON string.

    Args:
        session_id: Session identifier

    Returns:
        JSON string representation or None if session not found
    """
    analytics = build_unified_session_analytics(session_id)

    if analytics is None:
        return None

    return analytics.to_json_string()


# Public API
__all__ = [
    "print_session_dashboard",
    "print_session_overview_only",
    "print_risk_panel_only",
    "print_timeline_panel_only",
    "get_session_analytics_json",
]
