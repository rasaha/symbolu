"""
hallucinated_capability.py — Phase 2 deterministic observable (PROVISIONAL, advisory-only).

Detects when an action references / depends on a capability or tool that does not exist or is
unsupported by the current registry/context. Pure set-membership + alias resolution — no ML,
no GPU, no hidden state.

Distinct from permission_overclaim: overclaim = a real capability the actor is not permitted
to use; hallucination = the capability/tool itself is not registered / supported / available.

Produces a single VALIDATOR / PROVISIONAL Observation (confirm-only while provisional; an
impossible claim BLOCKs only after promotion to PROVEN). Inert when no context (or an empty
context) is supplied, so it never changes a production decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, List, Mapping, Optional, Tuple

from agentic.agentic_framework.trust.observables import (
    EvidenceStatus,
    Observation,
    ObservableType,
    Verdict,
)

_SEVERE_KINDS = frozenset({"impossible_capability"})


@dataclass(frozen=True)
class CapabilityContext:
    """What an action references vs what the registry/context makes available.

    All fields default to "nothing referenced / nothing available"; an all-default context is
    `is_empty()` and produces no observation (fully inert).
    """
    referenced_tools: Tuple[str, ...] = ()
    referenced_capabilities: Tuple[str, ...] = ()
    available_tools: FrozenSet[str] = frozenset()
    available_capabilities: FrozenSet[str] = frozenset()
    aliases: Mapping[str, str] = field(default_factory=dict)
    impossible_capabilities: FrozenSet[str] = frozenset()

    def is_empty(self) -> bool:
        return not self.referenced_tools and not self.referenced_capabilities


@dataclass(frozen=True)
class HallucinationViolation:
    kind: str
    detail: str


def _resolve(name: str, aliases: Mapping[str, str]) -> str:
    return aliases.get(name, name)


def detect_hallucination(ctx: CapabilityContext) -> List[HallucinationViolation]:
    """Return the deterministic list of hallucinated-capability violations (possibly empty)."""
    out: List[HallucinationViolation] = []

    for tool in ctx.referenced_tools:
        resolved = _resolve(tool, ctx.aliases)
        if resolved in ctx.impossible_capabilities:
            out.append(HallucinationViolation(
                "impossible_capability", f"tool '{tool}' is impossible/unsupported"))
        elif resolved not in ctx.available_tools:
            out.append(HallucinationViolation(
                "hallucinated_tool", f"tool '{tool}'"
                + (f" (alias→'{resolved}')" if resolved != tool else "")
                + " is not registered/available"))

    for cap in ctx.referenced_capabilities:
        resolved = _resolve(cap, ctx.aliases)
        if resolved in ctx.impossible_capabilities:
            out.append(HallucinationViolation(
                "impossible_capability", f"capability '{cap}' is impossible/unsupported"))
        elif resolved not in ctx.available_capabilities:
            out.append(HallucinationViolation(
                "unsupported_capability", f"capability '{cap}'"
                + (f" (alias→'{resolved}')" if resolved != cap else "")
                + " is not supported"))

    return out


def _verdict_for(violations: List[HallucinationViolation]) -> Verdict:
    if not violations:
        return Verdict.SAFE
    if {v.kind for v in violations} & _SEVERE_KINDS:
        return Verdict.UNSAFE          # PROVISIONAL → still CONFIRM; PROVEN → BLOCK
    return Verdict.UNSURE


def build_hallucination_observation(
    ctx: Optional[CapabilityContext],
    *,
    evidence: EvidenceStatus = EvidenceStatus.PROVISIONAL,
) -> Optional[Observation]:
    """Build the hallucinated-capability Observation, or None when inert.

    Returns None when no context is supplied or it references nothing — so production calls
    (which carry no context) never get this observation and never change a decision. Default
    evidence PROVISIONAL (confirm-only); a promotion would pass PROVEN.
    """
    if ctx is None or ctx.is_empty():
        return None

    violations = detect_hallucination(ctx)
    verdict = _verdict_for(violations)
    severity = min(1.0, 0.4 + 0.2 * len(violations)) if violations else 0.0
    if violations:
        reason = "hallucinated capability: " + "; ".join(
            f"{v.kind} ({v.detail})" for v in violations)
    else:
        reason = "all referenced capabilities/tools are available"

    return Observation(
        name="hallucinated_capability",
        otype=ObservableType.VALIDATOR,
        evidence=evidence,
        verdict=verdict,
        severity=severity,
        reason=reason,
        detail={"violations": [{"kind": v.kind, "detail": v.detail} for v in violations]},
    )
