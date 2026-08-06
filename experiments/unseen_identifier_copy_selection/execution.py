"""Fail-closed execution authorization gate for the unseen-identifier diagnostic.

Reserved diagnostic seeds (smoke 9070 / development 9071-9073 / final 90760-90764) cannot be used
to generate a cohort or train unless a caller supplies a valid execution-authorization token. No
such token exists: the registry is intentionally EMPTY, because execution is not authorized. Every
reserved seed therefore fails closed. Non-reserved seeds (including the fixture namespace) are
ungated so unit tests can build fixtures.
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Final

from .config import RESERVED_SEEDS, SMOKE_SEEDS, DEVELOPMENT_SEEDS, FINAL_SEEDS


class ExecutionNotAuthorized(PermissionError):
    """Raised before any dataset generation, model initialization, or training side effect."""


def _role(seed: int) -> str | None:
    s = int(seed)
    if s in SMOKE_SEEDS:
        return "smoke"
    if s in DEVELOPMENT_SEEDS:
        return "development"
    if s in FINAL_SEEDS:
        return "final"
    return None


# Intentionally EMPTY: execution is not authorized, so no reserved seed has a valid token.
_AUTHORIZATION_TOKENS: Final = MappingProxyType({})  # type: ignore[var-annotated]


def require_execution_authorization(seed: int, token: str | None = None) -> None:
    """Fail closed for reserved seeds. Non-reserved seeds are permitted (fixtures/tests)."""
    if int(seed) not in RESERVED_SEEDS:
        return
    role = _role(seed)
    expected = _AUTHORIZATION_TOKENS.get(role)
    if expected is None or token is None or token != expected:
        raise ExecutionNotAuthorized(
            f"seed {seed} is a reserved {role} diagnostic seed; execution is not authorized "
            f"(no valid execution-authorization token exists)"
        )
