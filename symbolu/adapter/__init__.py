"""
Symbol-U DILchat Adapter Layer v1.0

This module provides presentation-layer transformation from Symbol-U's
unified output + policy flags into a DILchat-facing response format.

The adapter is:
- Zero-LLM: Pure deterministic rule-based transformations
- Non-invasive: Does not modify any pipeline behavior
- Additive: Optional presentation layer
- Deterministic: Same input always produces same output

Usage:
    from symbolu.adapter import build_dilchat_payload

    # After pipeline execution:
    dilchat_response = build_dilchat_payload(
        unified_output=ctx.unified_output,
        policy_flags=ctx.policy_flags,
        domain=ctx.domain
    )
"""

from .dilchat_adapter import (
    DILchatBadge,
    DILchatHint,
    DILchatResponse,
    build_dilchat_payload,
    build_dilchat_response,
)

__all__ = [
    'DILchatBadge',
    'DILchatHint',
    'DILchatResponse',
    'build_dilchat_payload',
    'build_dilchat_response',
]
