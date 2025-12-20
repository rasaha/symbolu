"""
Session Processing for Pipeline Orchestrator

Extracted from orchestrator.py to reduce complexity.
Handles all session-related processing:
- Session policy flags
- Session memory
- Session recap
- Intent arc classification
- Identity signature
- Motivation flow
- Trading guardrails
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .models import PipelineContext


def process_session_context(ctx: "PipelineContext") -> None:
    """
    Process all session-related context enrichment.

    This is a non-invasive observability layer that enriches the context
    with session-derived insights. All processing is fail-safe - if any
    component fails, the pipeline continues without it.

    Components processed:
    - Session policy flags (trajectory-aware policy hints)
    - Session memory (episodic memory events)
    - Session recap (multi-turn recap)
    - Intent arc (trajectory classification)
    - Identity signature (identity trajectory)
    - Motivation flow (motivational driver)
    - Trading guardrails (formula-aware safety checks)

    Args:
        ctx: Pipeline context with request containing session_id in metadata.
    """
    # Initialize session-related context fields
    ctx.session_policy_flags = None
    ctx.session_memory = None
    ctx.session_recap = None
    ctx.intent_arc = None
    ctx.identity_signature = None
    ctx.motivation_profile = None
    ctx.trading_guardrails = None

    # Only process if session_id is provided
    session_id = ctx.request.metadata.get("session_id")
    if not session_id:
        return

    try:
        # Import session components (lazy to avoid circular dependency)
        from symbolu.service.sessions import SessionStore, compute_session_summary

        # Get session state
        session_store = SessionStore()
        session_state = session_store.get(session_id)

        if not session_state:
            return

        # Compute session summary
        session_summary = compute_session_summary(session_state)

        # Process each component (fail-safe)
        _process_session_policy(ctx, session_summary)
        _process_session_memory(ctx, session_id, session_store, session_state)
        _process_session_recap(ctx, session_state, session_summary)
        _process_intent_arc(ctx, session_state, session_summary)
        _process_identity_signature(ctx, session_state, session_summary)
        _process_motivation_flow(ctx, session_state, session_summary)
        _process_trading_guardrails(ctx, session_summary)

    except Exception:
        # If session processing fails entirely, continue without it
        pass


def _process_session_policy(
    ctx: "PipelineContext",
    session_summary: Any,
) -> None:
    """Process session policy flags."""
    try:
        from symbolu.policy.session_policy import compute_session_policy_flags
        ctx.session_policy_flags = compute_session_policy_flags(session_summary)
    except Exception:
        pass


def _process_session_memory(
    ctx: "PipelineContext",
    session_id: str,
    session_store: Any,
    session_state: Any,
) -> None:
    """Process session memory updates."""
    try:
        session_store.update_session(session_id, ctx)
        ctx.session_memory = session_state.session_memory
    except Exception:
        ctx.session_memory = None


def _process_session_recap(
    ctx: "PipelineContext",
    session_state: Any,
    session_summary: Any,
) -> None:
    """Process session recap."""
    try:
        from symbolu.service.sessions import compute_session_summary
        from symbolu.service.sessions.session_summarizer import compute_session_recap

        # Recompute summary if needed
        session_summary = compute_session_summary(session_state)
        recap_domain = ctx.request.metadata.get("domain", session_summary.last_domain)

        ctx.session_recap = compute_session_recap(
            session_summary=session_summary,
            session_memory=session_state.session_memory,
            session_policy=ctx.session_policy_flags,
            domain=recap_domain,
        )
    except Exception:
        ctx.session_recap = None


def _process_intent_arc(
    ctx: "PipelineContext",
    session_state: Any,
    session_summary: Any,
) -> None:
    """Process intent arc classification."""
    try:
        from symbolu.intent.intent_arc_engine import compute_intent_arc

        if session_summary:
            ctx.intent_arc = compute_intent_arc(
                session_summary=session_summary,
                session_memory=session_state.session_memory,
                session_policy=ctx.session_policy_flags,
                session_recap=ctx.session_recap,
            )
    except Exception:
        ctx.intent_arc = None


def _process_identity_signature(
    ctx: "PipelineContext",
    session_state: Any,
    session_summary: Any,
) -> None:
    """Process identity signature classification."""
    try:
        from symbolu.identity.identity_signature_engine import compute_identity_signature

        if session_summary:
            identity_domain = ctx.request.metadata.get("domain", session_summary.last_domain)
            ctx.identity_signature = compute_identity_signature(
                session_summary=session_summary,
                session_memory=session_state.session_memory,
                session_policy=ctx.session_policy_flags,
                intent_arc=ctx.intent_arc,
                domain=identity_domain,
            )
    except Exception:
        ctx.identity_signature = None


def _process_motivation_flow(
    ctx: "PipelineContext",
    session_state: Any,
    session_summary: Any,
) -> None:
    """Process motivation flow classification."""
    try:
        from symbolu.motivation.motivation_engine import compute_motivation_flow

        if session_summary:
            ctx.motivation_profile = compute_motivation_flow(
                session_summary=session_summary,
                session_memory=session_state.session_memory,
                session_policy=ctx.session_policy_flags,
                intent_arc=ctx.intent_arc,
                identity_signature=ctx.identity_signature,
            )
    except Exception:
        ctx.motivation_profile = None


def _process_trading_guardrails(
    ctx: "PipelineContext",
    session_summary: Any,
) -> None:
    """Process trading guardrails for trading domain."""
    try:
        from symbolu.policy.trading_guardrail_engine import compute_trading_guardrails
        from symbolu.policy.domain_profiles import get_domain_profile

        guardrail_domain = ctx.request.metadata.get("domain", session_summary.last_domain)

        if guardrail_domain != "trading":
            ctx.trading_guardrails = None
            return

        domain_profile = get_domain_profile(guardrail_domain)

        if not domain_profile.get("formula_guardrails_enabled", False):
            ctx.trading_guardrails = None
            return

        ctx.trading_guardrails = compute_trading_guardrails(
            summary=session_summary,
            policy=ctx.policy_flags,
            motivation=ctx.motivation_profile,
            intent_arc=ctx.intent_arc,
            identity_signature=ctx.identity_signature,
        )
    except Exception:
        ctx.trading_guardrails = None
