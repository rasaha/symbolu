"""Lightweight experimental-protocol guards for the unseen-identifier diagnostic.

This is **not** a security-authorization system. For an internal research experiment a cryptographic
authorization layer (signed documents, Git-provenance authority roots, capability registries, mint
keys, per-run tokens) is disproportionate, so none of that exists here. What remains is
experimental-protocol control only:

* every invocation names an explicit **phase** — ``fixture`` / ``smoke`` / ``development`` / ``final``;
* the seed must belong to that phase's **exact** role (no cross-role);
* exactly one seed runs per invocation (enforced at the CLI);
* reserved-phase seeds (smoke/development/final) are refused unless their phase is named explicitly,
  so a reserved seed is never generated implicitly, by accident, or under the wrong phase;
* fixture seeds (993000-993004) are the only phase exercised by CI and the tests;
* final seeds run only when the operator explicitly directs them.

The real control on a reserved run is the reviewed, independently-audited, merged change plus the
operator's explicit phase-named invocation — not runtime self-verification. `token` on the primitive
guard simply carries the declared phase; it is a protocol boundary, not a secret.
"""
from __future__ import annotations

from typing import Final

from .config import (
    DEVELOPMENT_SEEDS,
    FINAL_SEEDS,
    FIXTURE_SEEDS,
    RESERVED_SEEDS,
    SMOKE_SEEDS,
)


class ExecutionNotAuthorized(PermissionError):
    """Raised (fail-closed) when a phase/seed protocol boundary is violated, before any side effect."""


PHASES: Final[tuple[str, ...]] = ("fixture", "smoke", "development", "final")
RESERVED_PHASES: Final[frozenset[str]] = frozenset({"smoke", "development", "final"})

# Exact phase -> permitted seed set. A phase may run ONLY its own seeds; every cross-role pairing fails.
PHASE_SEEDS: Final[dict[str, frozenset[int]]] = {
    "fixture": frozenset(FIXTURE_SEEDS),
    "smoke": frozenset(SMOKE_SEEDS),
    "development": frozenset(DEVELOPMENT_SEEDS),
    "final": frozenset(FINAL_SEEDS),
}


def _role(seed: int) -> str | None:
    s = int(seed)
    if s in SMOKE_SEEDS:
        return "smoke"
    if s in DEVELOPMENT_SEEDS:
        return "development"
    if s in FINAL_SEEDS:
        return "final"
    return None


def phase_for_seed(seed: int) -> str | None:
    """The phase a seed belongs to: 'fixture' for the fixture namespace, its role for a reserved seed,
    or None for a seed outside every declared set."""
    if int(seed) in PHASE_SEEDS["fixture"]:
        return "fixture"
    return _role(seed)


def validate_phase_seed(phase: str, seed: int) -> None:
    """Exact phase/seed-role validation (the protocol boundary). Raises on any mismatch.

    - `phase` must be one of PHASES;
    - `seed` must belong to that phase's exact seed set (no cross-role);
    - exactly one seed is validated per call (the CLI enforces a single --seed)."""
    if phase not in PHASE_SEEDS:
        raise ExecutionNotAuthorized(f"unknown phase {phase!r}; expected one of {PHASES}")
    allowed = PHASE_SEEDS[phase]
    if int(seed) not in allowed:
        raise ExecutionNotAuthorized(
            f"seed {seed} is not a {phase} seed (exact {phase} seeds: {sorted(allowed)})"
        )


def require_execution_authorization(seed: int, token: str | None = None) -> None:
    """Primitive-level protocol guard threaded through the data generators.

    `token` carries the explicitly-declared phase for this invocation (or None). Fixture (and other
    non-reserved) seeds are ungated. A reserved seed is refused unless the declared phase equals the
    seed's exact role, so reserved seeds are never generated implicitly or under the wrong phase. This
    is a protocol boundary, not a secret — the operator's explicit phase declaration is the control."""
    if int(seed) not in RESERVED_SEEDS:
        return
    role = _role(seed)
    if token != role:
        raise ExecutionNotAuthorized(
            f"seed {seed} is a reserved {role} seed; it runs only when the {role} phase is explicitly "
            f"declared for this invocation (declared phase: {token!r})"
        )
