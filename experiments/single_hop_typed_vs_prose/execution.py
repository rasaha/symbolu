"""Fail-closed seed authorization gate."""
from __future__ import annotations

from dataclasses import dataclass

from .config import (
    DEVELOPMENT_AUTHORIZATION_TOKEN,
    DEVELOPMENT_SEEDS,
    FINAL_AUTHORIZATION_TOKEN,
    FINAL_SEEDS,
    SMOKE_AUTHORIZATION_TOKEN,
    SMOKE_SEED,
)


class ExecutionNotAuthorized(PermissionError):
    pass


@dataclass(frozen=True)
class SeedAuthorization:
    seed: int
    role: str
    authorized: bool


def guard_seed(seed: int, authorization_token: str | None = None) -> SeedAuthorization:
    seed = int(seed)
    if seed == SMOKE_SEED:
        if authorization_token != SMOKE_AUTHORIZATION_TOKEN:
            raise ExecutionNotAuthorized("smoke seed 76 requires explicit smoke authorization")
        return SeedAuthorization(seed, "smoke", True)
    if seed in DEVELOPMENT_SEEDS:
        if authorization_token != DEVELOPMENT_AUTHORIZATION_TOKEN:
            raise ExecutionNotAuthorized(
                f"development seed {seed} requires explicit development authorization"
            )
        return SeedAuthorization(seed, "development", True)
    if seed in FINAL_SEEDS:
        if authorization_token != FINAL_AUTHORIZATION_TOKEN:
            raise ExecutionNotAuthorized(
                f"final seed {seed} requires explicit final-execution authorization"
            )
        return SeedAuthorization(seed, "final", True)
    return SeedAuthorization(seed, "non_benchmark", True)
