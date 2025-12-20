"""
Output Processing for Pipeline Orchestrator

Extracted from orchestrator.py to reduce complexity.
Handles post-pipeline output processing:
- Unified API generation
- Policy flag computation
- DILchat adapter payload
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import PipelineContext


def process_output_layers(ctx: "PipelineContext") -> None:
    """
    Process all output layer enrichments.

    This is a non-invasive layer that enriches the context with
    output-facing components. All processing is fail-safe.

    Components processed:
    - Unified API (complete API contract for consumers)
    - Policy flags (domain-specific advisory flags)
    - DILchat payload (presentation layer for DILchat)

    Args:
        ctx: Pipeline context after rendering.
    """
    _process_unified_api(ctx)
    _process_policy_flags(ctx)
    _process_dilchat_payload(ctx)


def _process_unified_api(ctx: "PipelineContext") -> None:
    """Generate unified API output."""
    try:
        from symbolu.api.unified_api import get_unified_json
        ctx.unified_output = get_unified_json(ctx)
    except Exception:
        ctx.unified_output = None


def _process_policy_flags(ctx: "PipelineContext") -> None:
    """Compute policy flags from unified output."""
    if ctx.unified_output is None:
        ctx.policy_flags = None
        return

    try:
        from symbolu.policy import compute_policy_flags

        # Extract domain
        domain = ctx.request.metadata.get("domain", "generic")
        if not domain or domain == "unknown":
            domain = ctx.unified_output.get("metadata", {}).get("domain", "generic")

        # Extract user/org for preference lookup
        user_id = ctx.request.metadata.get("user_id")
        org_id = ctx.request.metadata.get("org_id")

        ctx.policy_flags = compute_policy_flags(
            ctx.unified_output,
            domain,
            user_id=user_id,
            org_id=org_id
        )
    except Exception:
        ctx.policy_flags = None


def _process_dilchat_payload(ctx: "PipelineContext") -> None:
    """Generate DILchat presentation payload."""
    if ctx.unified_output is None or ctx.policy_flags is None:
        ctx.dilchat_payload = None
        return

    try:
        from symbolu.adapter import build_dilchat_payload

        # Extract domain
        domain = ctx.request.metadata.get("domain", "generic")
        if not domain or domain == "unknown":
            domain = ctx.unified_output.get("metadata", {}).get("domain", "generic")

        # Get session policy dict if available
        session_policy_dict = None
        if ctx.session_policy_flags:
            session_policy_dict = ctx.session_policy_flags.to_dict()

        ctx.dilchat_payload = build_dilchat_payload(
            ctx.unified_output,
            ctx.policy_flags,
            domain,
            session_policy_dict
        )
    except Exception:
        ctx.dilchat_payload = None
