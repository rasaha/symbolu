"""Fail-closed execution authorization gate.

Reserved benchmark seeds cannot run unless the caller supplies the exact token for the
seed's role. Execution of these seeds was explicitly authorized by the repository owner
(see EXECUTION_AUTHORIZATION.md); before that authorization the token registry was empty
and every reserved seed failed closed. Non-benchmark seeds are never gated.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from .config import (
    RESERVED_SEED_ROLES,
    SMOKE_AUTHORIZATION_TOKEN,
    DEVELOPMENT_AUTHORIZATION_TOKEN,
    FINAL_AUTHORIZATION_TOKEN,
)


class ExecutionNotAuthorized(PermissionError):
    """Raised before generation, model initialization, or filesystem effects."""


@dataclass(frozen=True)
class GrantedAuthorization:
    role: str
    authorized: bool = True


_AUTHORIZATION_TOKENS: Final = MappingProxyType(
    {
        "smoke": SMOKE_AUTHORIZATION_TOKEN,
        "development": DEVELOPMENT_AUTHORIZATION_TOKEN,
        "final": FINAL_AUTHORIZATION_TOKEN,
    }
)


def guard_seed(seed: int, token: str | None = None) -> GrantedAuthorization:
    """Return a granted authorization, or raise ExecutionNotAuthorized (before any side effect).

    Non-reserved seeds are ungated. Reserved seeds require the exact role token."""
    role = RESERVED_SEED_ROLES.get(int(seed))
    if role is None:
        return GrantedAuthorization("non_benchmark", True)
    expected = _AUTHORIZATION_TOKENS.get(role)
    if expected is None or token is None or token != expected:
        raise ExecutionNotAuthorized(
            f"seed {seed} is reserved for {role}; a valid {role} execution token is required"
        )
    return GrantedAuthorization(role, True)


def authorization_token_for(seed: int) -> str | None:
    """Return the owner-authorized token needed to run a reserved seed, or None if ungated."""
    role = RESERVED_SEED_ROLES.get(int(seed))
    return None if role is None else _AUTHORIZATION_TOKENS[role]
