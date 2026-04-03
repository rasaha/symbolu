"""
Rate Limiter — Governance facade for API-level rate enforcement.

Re-exports the RateLimiter and enforce_rate_limit from
symbolu_core.service.security. Rate limiting is governance enforcement
at the API boundary: allow/deny decisions based on request frequency.

Usage:
    from agentic.safety.rate_limiter import enforce_rate_limit, RateLimiter

    # As FastAPI dependency
    @app.post("/authorize")
    async def authorize(request: Request):
        enforce_rate_limit(request)  # Raises 429 if exceeded
        ...
"""

from symbolu_core.service.security.rate_limiter import (
    RateLimiter,
    enforce_rate_limit,
    get_rate_limiter,
    reset_rate_limiter,
)

__all__ = [
    "RateLimiter",
    "enforce_rate_limit",
    "get_rate_limiter",
    "reset_rate_limiter",
]
