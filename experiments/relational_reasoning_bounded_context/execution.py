"""Fail-closed execution-authorization gate. Torch-free.

Reserved BTRR scientific seeds (smoke 8100, dev 8101-8103, final 81600-81604) cannot enter any
generation/training/evaluation path unless the caller supplies the exact role token. The token registry
is EMPTY (execution unauthorized), so every reserved seed fails closed. Unit-fixture seeds
(883000-883004) and any non-reserved seed are ungated (implementation testing only).
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from .config import RESERVED_SEED_ROLES, UNIT_FIXTURE_SEEDS


class ExecutionNotAuthorized(PermissionError):
    """Raised before any side effect when a reserved seed is used without authorization."""


@dataclass(frozen=True)
class GrantedAuthorization:
    role: str
    authorized: bool = True


# EMPTY registry: execution is not authorized. EXECUTION_AUTHORIZATION.md remains unsigned.
_AUTHORIZATION_TOKENS: Final = MappingProxyType({})  # type: ignore[var-annotated]


def guard_seed(seed: int, token: str | None = None) -> GrantedAuthorization:
    """Return a granted authorization, or raise ExecutionNotAuthorized before any side effect."""
    role = RESERVED_SEED_ROLES.get(int(seed))
    if role is None:
        return GrantedAuthorization("non_reserved", True)
    expected = _AUTHORIZATION_TOKENS.get(role)
    if expected is None or token is None or token != expected:
        raise ExecutionNotAuthorized(
            f"seed {seed} is reserved for {role}; execution is not authorized "
            f"(EXECUTION_AUTHORIZATION.md unsigned)"
        )
    return GrantedAuthorization(role, True)


def is_unit_fixture(seed: int) -> bool:
    return int(seed) in UNIT_FIXTURE_SEEDS


def require_unit_fixture(seed: int) -> int:
    """Executable implementation tests may use ONLY inadmissible unit-fixture seeds."""
    if not is_unit_fixture(seed):
        raise ExecutionNotAuthorized(
            f"seed {seed} is not an inadmissible unit-fixture seed (883000-883004); "
            f"reserved scientific seeds must not enter any generator/training/eval path"
        )
    return int(seed)
