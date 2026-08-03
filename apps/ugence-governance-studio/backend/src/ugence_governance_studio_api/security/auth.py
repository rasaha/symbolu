"""Authentication / authorization seam (§21).

Authentication belongs to a later phase (P3E) and is DISABLED by default in local
P3B mode. This module provides only a typed seam: a dependency that is a no-op
when ``enable_authentication`` is false, and raises a typed 401 when the flag is
turned on without a real provider wired (so the seam is observable and honest,
never a hard-coded demo password).
"""
from __future__ import annotations

from starlette.requests import Request

from ..errors import ApiException


async def authentication_seam(request: Request) -> None:
    settings = request.app.state.settings
    if not settings.enable_authentication:
        return  # local P3B mode: no authentication
    # The flag is on but P3B ships no real provider. Fail closed & honest.
    raise ApiException(
        status_code=401,
        code="authentication_required",
        message="authentication is enabled but no provider is configured in P3B",
    )
