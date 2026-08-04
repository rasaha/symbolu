"""Deployment access gate — HTTP Basic over HTTPS (P3E §9, §10, §11).

A narrow single-instance access gate, not an identity platform. Constant-time
credential comparison, a bounded in-memory per-source failure counter with temporary
cooldown, a fixed delay on failure, generic 401s that never disclose whether the
username exists, and no logging of credentials or Authorization headers.

Only ``/healthz`` and ``/readyz`` are exempt.
"""
from __future__ import annotations

import base64
import binascii
import hmac
import time
from typing import Callable, Dict, Tuple

from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

from .config import (
    DeploymentConfig,
    FAILED_AUTH_DELAY_SECONDS,
    FAILURE_COOLDOWN_SECONDS,
    MAX_FAILURES_PER_SOURCE,
)
from .passwords import verify_password

PUBLIC_PATHS = frozenset({"/healthz", "/readyz"})
_MAX_TRACKED_SOURCES = 4096


class FailureTracker:
    """Bounded in-memory failure counter with temporary cooldown (no permanent lockout)."""

    def __init__(self, *, max_failures: int = MAX_FAILURES_PER_SOURCE, cooldown: float = FAILURE_COOLDOWN_SECONDS):
        self._max = max_failures
        self._cooldown = cooldown
        self._state: Dict[str, Tuple[int, float]] = {}

    def _now(self) -> float:
        return time.monotonic()

    def in_cooldown(self, source: str) -> bool:
        count, until = self._state.get(source, (0, 0.0))
        if count >= self._max and self._now() < until:
            return True
        return False

    def record_failure(self, source: str) -> None:
        now = self._now()
        count, until = self._state.get(source, (0, 0.0))
        if count >= self._max and now >= until:
            count = 0  # cooldown elapsed → reset window (never a permanent lockout)
        count += 1
        until = now + self._cooldown if count >= self._max else 0.0
        if source not in self._state and len(self._state) >= _MAX_TRACKED_SOURCES:
            self._state.pop(next(iter(self._state)))  # bound memory
        self._state[source] = (count, until)

    def clear(self, source: str) -> None:
        self._state.pop(source, None)


def _client_source(request: Request, trusted_proxy: bool) -> str:
    if trusted_proxy:
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            return fwd.split(",")[0].strip()
    client = request.client
    return client.host if client else "unknown"


def _parse_basic(header: str) -> Tuple[str, str] | None:
    if not header.lower().startswith("basic "):
        return None
    try:
        decoded = base64.b64decode(header[6:].strip(), validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None
    if ":" not in decoded:
        return None
    user, _, pw = decoded.partition(":")
    return user, pw


def _unauthorized() -> Response:
    resp = PlainTextResponse("Unauthorized", status_code=401)
    resp.headers["WWW-Authenticate"] = 'Basic realm="Governance Studio", charset="UTF-8"'
    return resp


class AccessGate:
    """ASGI-agnostic gate usable as Starlette BaseHTTPMiddleware dispatch."""

    def __init__(self, config: DeploymentConfig, tracker: FailureTracker | None = None, sleep: Callable[[float], None] | None = None):
        self.config = config
        self.tracker = tracker or FailureTracker()
        self._sleep = sleep or time.sleep

    def authenticate(self, request: Request) -> bool:
        creds = _parse_basic(request.headers.get("authorization", ""))
        if creds is None:
            return False
        user, pw = creds
        user_ok = hmac.compare_digest(user.encode("utf-8"), self.config.username.encode("utf-8"))
        pw_ok = verify_password(pw, self.config.password_hash)
        return user_ok and pw_ok

    async def dispatch(self, request: Request, call_next):
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        source = _client_source(request, self.config.trusted_proxy)
        if self.tracker.in_cooldown(source):
            self._sleep(FAILED_AUTH_DELAY_SECONDS)
            return _unauthorized()  # generic — no lockout disclosure

        if not self.authenticate(request):
            self._sleep(FAILED_AUTH_DELAY_SECONDS)
            self.tracker.record_failure(source)
            return _unauthorized()  # generic — never reveals whether the username exists

        self.tracker.clear(source)
        return await call_next(request)
