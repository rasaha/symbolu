"""Shadow mode (Phase 11). The control plane computes a recommendation ALONGSIDE the
existing authoritative route but never acts (SHADOW: no external calls, no actions,
authoritative = existing production path). Records where the control-plane recommendation
agrees or differs, so integration value can be assessed without taking control.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from control_plane.orchestrator import Orchestrator, Scenario


@dataclass
class ShadowComparison:
    trace_id: str
    authoritative_route: Optional[str]      # what production would/did do
    recommended_route: Optional[str]        # what the control plane recommends
    agree: bool
    recommended_terminal: str
    would_have_blocked: bool                # control plane would have blocked what production allowed


def shadow_run(sc: Scenario, authoritative_route: Optional[str],
               authoritative_allowed: bool = True) -> ShadowComparison:
    # SHADOW never acts: force non-enforcing mode and disable action execution.
    sc.envelope.mode = "SHADOW"
    o = Orchestrator(validate_contracts=True, enforce_invariants=True)
    res = o.run(sc)
    recommended = res.selected
    agree = (recommended == authoritative_route)
    terminal_ok = res.terminal_state in ("COMPLETED", "ASSERTION_DELIVERED")
    would_block = authoritative_allowed and not terminal_ok
    return ShadowComparison(
        trace_id=sc.envelope.trace_id, authoritative_route=authoritative_route,
        recommended_route=recommended, agree=agree,
        recommended_terminal=res.terminal_state, would_have_blocked=would_block)
