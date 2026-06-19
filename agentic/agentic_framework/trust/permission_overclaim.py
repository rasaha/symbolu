"""
permission_overclaim.py — Phase 2 deterministic observable (PROVISIONAL, advisory-only).

Detects when a requested action claims permission / scope / authority / capability beyond
what is explicitly granted. Pure deterministic comparison of a `PermissionContext`'s
`requested_*` profile against its `granted_*` profile — no ML, no thresholds, no scores.

It produces a single `Observation`:
  * ObservableType.VALIDATOR, EvidenceStatus.PROVISIONAL  → confirm-only (never blocks) while
    PROVISIONAL, enforced by `decision._proposed`; promotion to PROVEN is what would let a
    *severe* overclaim BLOCK.
  * verdict SAFE (within grant) / UNSURE (mild overclaim) / UNSAFE (severe overclaim).

Inert by default: `build_overclaim_observation` returns None when no context (or an empty
context) is supplied, so it never changes a production decision.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple

from agentic.agentic_framework.trust.observables import (
    EvidenceStatus,
    Observation,
    ObservableType,
    Verdict,
)

# Fixed, total ordering of authority levels (deterministic; no learning).
_AUTHORITY_RANK: Dict[str, int] = {
    "none": 0, "read": 1, "write": 2, "execute": 3, "admin": 4, "root": 5,
}

# Violation kinds considered SEVERE — these map to BLOCK only AFTER promotion to PROVEN.
_SEVERE_KINDS = frozenset({"policy_bypass", "cross_tenant", "authority_escalation_admin"})


@dataclass(frozen=True)
class PermissionContext:
    """A requested permission profile paired with what was explicitly granted.

    All fields default to "nothing requested / nothing granted"; an all-default context is
    `empty()` and produces no observation (fully inert).
    """
    requested_capabilities: FrozenSet[str] = frozenset()
    granted_capabilities: FrozenSet[str] = frozenset()
    requested_authority: Optional[str] = None
    granted_authority: Optional[str] = None
    requested_scopes: Tuple[str, ...] = ()
    granted_scopes: Tuple[str, ...] = ()
    requested_tenant: Optional[str] = None
    granted_tenants: FrozenSet[str] = frozenset()
    policy_bypass_requested: bool = False

    def is_empty(self) -> bool:
        return (not self.requested_capabilities
                and self.requested_authority is None
                and not self.requested_scopes
                and self.requested_tenant is None
                and not self.policy_bypass_requested)


@dataclass(frozen=True)
class OverclaimViolation:
    kind: str
    detail: str


def _rank(level: Optional[str]) -> int:
    return _AUTHORITY_RANK.get((level or "none").lower(), 0)


def detect_overclaim(ctx: PermissionContext) -> List[OverclaimViolation]:
    """Return the deterministic list of overclaim violations (possibly empty)."""
    out: List[OverclaimViolation] = []

    extra_caps = sorted(set(ctx.requested_capabilities) - set(ctx.granted_capabilities))
    if extra_caps:
        out.append(OverclaimViolation(
            "capability_escalation", f"capabilities not granted: {', '.join(extra_caps)}"))

    if ctx.requested_authority is not None and _rank(ctx.requested_authority) > _rank(
            ctx.granted_authority):
        req = ctx.requested_authority.lower()
        kind = ("authority_escalation_admin" if req in ("admin", "root")
                else "authority_escalation")
        out.append(OverclaimViolation(
            kind, f"authority '{ctx.requested_authority}' exceeds granted "
                  f"'{ctx.granted_authority or 'none'}'"))

    uncovered = [s for s in ctx.requested_scopes
                 if not any(fnmatch.fnmatch(s, g) for g in ctx.granted_scopes)]
    if uncovered:
        out.append(OverclaimViolation(
            "scope_escalation", f"scopes outside grant: {', '.join(sorted(uncovered))}"))

    if ctx.requested_tenant is not None and ctx.requested_tenant not in ctx.granted_tenants:
        out.append(OverclaimViolation(
            "cross_tenant", f"tenant '{ctx.requested_tenant}' not in granted "
                            f"{sorted(ctx.granted_tenants) or '[]'}"))

    if ctx.policy_bypass_requested:
        out.append(OverclaimViolation("policy_bypass", "explicit policy-bypass requested"))

    return out


def _verdict_for(violations: List[OverclaimViolation]) -> Verdict:
    if not violations:
        return Verdict.SAFE
    # Normalize the "_admin" suffix back to authority_escalation for severity matching.
    kinds = {v.kind for v in violations}
    if kinds & _SEVERE_KINDS:
        return Verdict.UNSAFE          # PROVISIONAL → still CONFIRM; PROVEN → BLOCK
    return Verdict.UNSURE


def build_overclaim_observation(
    ctx: Optional[PermissionContext],
    *,
    evidence: EvidenceStatus = EvidenceStatus.PROVISIONAL,
) -> Optional[Observation]:
    """Build the permission-overclaim Observation, or None when inert.

    Returns None when no context is supplied or the context is empty (nothing requested) —
    so production calls (which carry no context) never get this observation and never change
    decision. Default evidence is PROVISIONAL (confirm-only); a promotion would pass PROVEN.
    """
    if ctx is None or ctx.is_empty():
        return None

    violations = detect_overclaim(ctx)
    verdict = _verdict_for(violations)
    # Severity orders audit drivers only; proportional to the number of violations.
    severity = min(1.0, 0.4 + 0.2 * len(violations)) if violations else 0.0
    if violations:
        reason = "permission overclaim: " + "; ".join(
            f"{v.kind} ({v.detail})" for v in violations)
    else:
        reason = "requested permissions within grant"

    return Observation(
        name="permission_overclaim",
        otype=ObservableType.VALIDATOR,
        evidence=evidence,
        verdict=verdict,
        severity=severity,
        reason=reason,
        detail={"violations": [{"kind": v.kind, "detail": v.detail} for v in violations]},
    )
