"""Fail-closed execution authorization gate.

The implementation PR intentionally contains no valid execution credentials. A later,
separately reviewed authorization must update the empty token registry before any
reserved benchmark seed can pass this gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from .config import RESERVED_SEED_ROLES


class ExecutionNotAuthorized(PermissionError):
    """Raised before generation, model initialization, or filesystem effects."""


# Deliberately empty in this implementation-only PR.
_AUTHORIZATION_TOKENS: Final = MappingProxyType({})


@dataclass(frozen=True)
class ExecutionAuthorization:
    role: str
    token: str


def guard_seed(seed: int, authorization: ExecutionAuthorization | None = None) -> None:
    role = RESERVED_SEED_ROLES.get(seed)
    if role is None:
        return
    expected = _AUTHORIZATION_TOKENS.get(role)
    if expected is None:
        raise ExecutionNotAuthorized(
            f"seed {seed} is reserved for {role}; this implementation authorizes no benchmark execution"
        )
    if authorization is None or authorization.role != role or authorization.token != expected:
        raise ExecutionNotAuthorized(f"missing or invalid {role} execution authorization")


def assert_no_execution_tokens() -> None:
    if _AUTHORIZATION_TOKENS:
        raise AssertionError("implementation-only branch must not contain execution tokens")
