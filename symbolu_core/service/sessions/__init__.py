"""
Symbol-U Session Management Layer

This package provides deterministic, non-invasive session management
for multi-turn conversations in the Symbol-U pipeline.

Public API:
    - SessionStore: In-memory session storage
    - SessionState: Session state container
    - SessionSummary: Aggregated session statistics
    - compute_session_summary: Helper function for statistics
"""

from .session_models import SessionState, SessionSummary
from .session_store import SessionStore, compute_session_summary

__all__ = [
    "SessionStore",
    "SessionState",
    "SessionSummary",
    "compute_session_summary",
]
