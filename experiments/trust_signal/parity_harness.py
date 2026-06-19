"""
parity_harness.py — Phase 1.5 differential/parity harness (migration, no new observables).

Drives a SafeMCPGateway (mock client) over a focused scenario corpus in SHADOW mode and
tabulates where the trust decision core disagrees with the legacy gateway decision. Output
is a mismatch table with each row classified:

    match       legacy and trust agree
    intended    a reviewed, accepted difference (none by default)
    unintended  trust differs from legacy without a reviewed reason (must resolve)
    unresolved  could not be classified

This is the gate for flipping `trust_core` to authoritative: it flips only when there are
zero `unintended`/`unresolved` mismatches. Pure plumbing — no ML, no CG, read-only on the
gateway (shadow never changes behavior).

Run:
    python -m experiments.trust_signal.parity_harness
"""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
from typing import List, Optional

from agentic.agentic_framework.mcp_gateway import (
    MCPToolCall,
    MCPToolDefinition,
    ToolRiskLevel,
    create_mock_mcp_gateway,
)
from agentic.agentic_framework.trust.parity import TrustMode


def _run(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@dataclass(frozen=True)
class Scenario:
    name: str
    tool: str
    risk: ToolRiskLevel
    quality: float = 0.9
    coherence: float = 0.9
    raw_entropy: Optional[float] = None
    verbalized_safety: Optional[float] = None
    requires_confirmation: bool = False
    min_confidence: float = 0.3


# Focused corpus: spans allow / confirm / block across risk levels, the confidence-risk
# gap, approval, and a low-confidence floor. Deterministic, no model.
CORPUS: List[Scenario] = [
    Scenario("ro_clean", "p_read", ToolRiskLevel.READ_ONLY, raw_entropy=0.1, verbalized_safety=0.95),
    Scenario("write_clean", "p_write", ToolRiskLevel.WRITE, raw_entropy=0.1, verbalized_safety=0.95),
    Scenario("write_gap", "p_write", ToolRiskLevel.WRITE, raw_entropy=0.9, verbalized_safety=0.95),
    Scenario("exec_gap", "p_exec", ToolRiskLevel.EXECUTE, raw_entropy=0.9, verbalized_safety=0.9),
    Scenario("write_approval", "p_write_conf", ToolRiskLevel.WRITE, raw_entropy=0.1,
             requires_confirmation=True),
    Scenario("low_conf", "p_write", ToolRiskLevel.WRITE, quality=0.05, coherence=0.05,
             raw_entropy=0.1, min_confidence=0.9),
    Scenario("destructive_clean", "p_destroy", ToolRiskLevel.DESTRUCTIVE, raw_entropy=0.1,
             verbalized_safety=0.9),
    Scenario("destructive_gap", "p_destroy", ToolRiskLevel.DESTRUCTIVE, raw_entropy=0.9,
             verbalized_safety=0.95),
    Scenario("privileged_gap", "p_priv", ToolRiskLevel.PRIVILEGED, raw_entropy=0.85,
             verbalized_safety=0.92),
]


def _build_gateway() -> "object":
    gw = create_mock_mcp_gateway()
    gw._trust_mode = TrustMode.SHADOW
    # Register the corpus tools on the mock client + definitions.
    for risk, names in {
        ToolRiskLevel.READ_ONLY: ["p_read"],
        ToolRiskLevel.WRITE: ["p_write", "p_write_conf"],
        ToolRiskLevel.EXECUTE: ["p_exec"],
        ToolRiskLevel.DESTRUCTIVE: ["p_destroy"],
        ToolRiskLevel.PRIVILEGED: ["p_priv"],
    }.items():
        for n in names:
            gw.mcp_client.register_tool(n, lambda p: "ok", risk)
    return gw


def run_harness() -> dict:
    gw = _build_gateway()
    rows = []
    for sc in CORPUS:
        gw.tool_definitions[sc.tool] = MCPToolDefinition(
            name=sc.tool, description=sc.name, risk_level=sc.risk,
            requires_confirmation=sc.requires_confirmation, min_confidence=sc.min_confidence)
        call = MCPToolCall(
            tool_name=sc.tool, parameters={"x": 1},
            quality_score=sc.quality, coherence_score=sc.coherence,
            raw_entropy=sc.raw_entropy, verbalized_safety_confidence=sc.verbalized_safety)
        _run(gw.call_tool(call))
        e = gw.audit_log[-1]
        rows.append({
            "scenario": sc.name, "legacy": e.trust_legacy_decision,
            "trust": e.trust_decision, "class": e.trust_mismatch_class,
            "drivers": e.trust_drivers,
        })
    counts = Counter(r["class"] for r in rows)
    return {"rows": rows, "counts": dict(counts)}


def render(report: dict) -> str:
    lines = ["# Phase 1.5 differential parity report (shadow mode)", "",
             "| scenario | legacy | trust | class | drivers |", "|---|---|---|---|---|"]
    for r in report["rows"]:
        lines.append(f"| {r['scenario']} | {r['legacy']} | {r['trust']} | {r['class']} "
                     f"| {','.join(r['drivers'] or [])} |")
    lines.append("")
    c = report["counts"]
    total = sum(c.values())
    mismatches = total - c.get("match", 0)
    lines.append(f"**Total:** {total}  ·  **match:** {c.get('match', 0)}  ·  "
                 f"**mismatch:** {mismatches} "
                 f"(intended={c.get('intended',0)}, unintended={c.get('unintended',0)}, "
                 f"unresolved={c.get('unresolved',0)})")
    lines.append("")
    lines.append("**Flip gate:** trust_core may become authoritative only when "
                 "unintended == 0 and unresolved == 0.")
    return "\n".join(lines) + "\n"


def main() -> int:
    report = run_harness()
    print(render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
