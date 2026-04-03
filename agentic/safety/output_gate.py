"""
Output Gate — Governance facade for presentation-layer output control.

Re-exports the GovernedGate from symbolu_core.presentation, which implements
ALLOW/BLOCK/WARN decisions based on P12 audit violations. This module
provides the agentic layer with direct access to output-level governance
without cross-boundary imports.

GovernedGate enforces:
  - GOVERNED mode: CRITICAL → BLOCK, ≥2 MAJOR → BLOCK, 1 MAJOR → WARN
  - OPEN mode: All violations → WARN only
  - AUDIT_ONLY mode: Log only, never block
  - Fail-closed: Ambiguous cases → BLOCK

Usage:
    from agentic.safety.output_gate import GovernedGate, GateMode

    gate = GovernedGate(mode=GateMode.GOVERNED)
    decision = gate.evaluate(chain_result)
    if decision.should_block:
        return decision.fallback_response
"""

from symbolu_core.presentation.governed_gate import (
    GovernedGate,
    GateDecision,
    GateMode,
    GateAction,
    evaluate_governed,
    evaluate_open,
    should_block_output,
    FALLBACK_RESPONSES,
    DEFAULT_FALLBACK,
)

__all__ = [
    "GovernedGate",
    "GateDecision",
    "GateMode",
    "GateAction",
    "evaluate_governed",
    "evaluate_open",
    "should_block_output",
    "FALLBACK_RESPONSES",
    "DEFAULT_FALLBACK",
]
