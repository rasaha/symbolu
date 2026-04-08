"""
Symbol-U API Security Layer

This module provides optional, deterministic security features:
    - API Key Authentication (optional based on environment variable)
    - Rate Limiting (sliding window, in-memory)

Design Principles:
    1. Fully optional - if not configured, requests proceed normally
    2. Backward compatible - no changes to existing behavior when disabled
    3. Zero-LLM - deterministic logic only
    4. Non-invasive - wraps API layer, doesn't modify pipeline
"""

__all__ = [
    "verify_api_key",
    "enforce_rate_limit",
    "RateLimiter",
]
