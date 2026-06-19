"""
parity_harness.py — Phase 1.5 differential/parity harness (migration, no new observables).

Drives SafeMCPGateway (mock client) over a focused scenario corpus in SHADOW mode and
tabulates where the trust decision core disagrees with the legacy gateway decision. The
gateway itself computes the parallel trust decision in `_audit` (post-decision, behavior
unchanged); this harness just drives real decisions across profiles and reads the recorded
`trust_*` audit fields.

Corpus spans: clean allow, confidence-risk gap, approval-required, min_confidence block,
destructive / privileged actions, **domain policy** (finance), and **shadow AI** (unknown
asset). Every row is classified match / intended / unintended / unresolved.

Flip gate: trust_core may become authoritative only when unintended == 0 and unresolved == 0.

Run:
    python -m experiments.trust_signal.parity_harness
"""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from agentic.agentic_framework.mcp_gateway import (
    MCPToolCall,
    MCPToolDefinition,
    MockMCPClient,
    SafeMCPGateway,
    ToolRiskLevel,
    create_mock_mcp_gateway,
)
from agentic.agentic_framework.trust.parity import TrustMode


def _run(coro):
    # Fully isolated: own fresh loop per call, restore a usable loop after (so neither
    # global event-loop state nor sibling tests are polluted).
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(asyncio.new_event_loop())


@dataclass(frozen=True)
class Scenario:
    name: str
    tool: str
    risk: ToolRiskLevel
    profile: str = "default"            # default | domain_finance | shadow_basic
    quality: float = 0.9
    coherence: float = 0.9
    raw_entropy: Optional[float] = None
    verbalized_safety: Optional[float] = None
    requires_confirmation: bool = False
    min_confidence: float = 0.3
    capabilities: List[str] = field(default_factory=list)


CORPUS: List[Scenario] = [
    # --- base uncertainty / approval / floor ---
    Scenario("ro_clean", "p_read", ToolRiskLevel.READ_ONLY, raw_entropy=0.1, verbalized_safety=0.95),
    Scenario("write_clean", "p_write", ToolRiskLevel.WRITE, raw_entropy=0.1, verbalized_safety=0.95),
    Scenario("write_gap", "p_write", ToolRiskLevel.WRITE, raw_entropy=0.9, verbalized_safety=0.95),
    Scenario("exec_gap", "p_exec", ToolRiskLevel.EXECUTE, raw_entropy=0.9, verbalized_safety=0.9),
    Scenario("write_approval", "p_write_conf", ToolRiskLevel.WRITE, raw_entropy=0.1,
             requires_confirmation=True),
    Scenario("low_conf_block", "p_write", ToolRiskLevel.WRITE, quality=0.05, coherence=0.05,
             raw_entropy=0.1, min_confidence=0.9),
    # --- destructive / privileged ---
    Scenario("destructive_clean", "p_destroy", ToolRiskLevel.DESTRUCTIVE, raw_entropy=0.1,
             verbalized_safety=0.9),
    Scenario("destructive_gap", "p_destroy", ToolRiskLevel.DESTRUCTIVE, raw_entropy=0.9,
             verbalized_safety=0.95),
    Scenario("privileged_clean", "p_priv", ToolRiskLevel.PRIVILEGED, raw_entropy=0.1,
             verbalized_safety=0.95),
    Scenario("privileged_gap", "p_priv", ToolRiskLevel.PRIVILEGED, raw_entropy=0.85,
             verbalized_safety=0.92),
    # --- domain policy (finance) ---
    Scenario("domain_finance_write", "ledger_write", ToolRiskLevel.WRITE,
             profile="domain_finance", raw_entropy=0.1, capabilities=["ledger_write"]),
    Scenario("domain_finance_read", "ledger_read", ToolRiskLevel.READ_ONLY,
             profile="domain_finance", raw_entropy=0.1, capabilities=["ledger_read"]),
    # --- shadow AI (unknown / unsanctioned asset) ---
    Scenario("shadow_unknown_write", "unknown_shadow_write", ToolRiskLevel.WRITE,
             profile="shadow_basic", raw_entropy=0.1),
    Scenario("shadow_unknown_exec", "unknown_shadow_exec", ToolRiskLevel.EXECUTE,
             profile="shadow_basic", raw_entropy=0.1),
]


def _make_shadow_registry():
    """Minimal shadow registry: any tool not listed is unsanctioned (fail-closed)."""
    from agentic.agentic_framework.shadow_ai import (
        ProvenanceStatus, ShadowAssetType, ShadowRegistry, ShadowRegistryEntry,
        ShadowTrustLevel,
    )
    return ShadowRegistry(entries=[
        ShadowRegistryEntry(
            asset_id="sanctioned-tool", asset_type=ShadowAssetType.TOOL,
            provenance=ProvenanceStatus.APPROVED, trust_level=ShadowTrustLevel.TRUSTED),
    ])


def _gateway_for_profile(profile: str) -> SafeMCPGateway:
    if profile == "domain_finance":
        from agentic.agentic_framework.domain_policy import create_default_registry
        gw = SafeMCPGateway(mcp_client=MockMCPClient(),
                            domain_registry=create_default_registry(), domain_id="finance")
    elif profile == "shadow_basic":
        gw = SafeMCPGateway(mcp_client=MockMCPClient(),
                            shadow_registry=_make_shadow_registry())
    else:
        gw = create_mock_mcp_gateway()
    gw._trust_mode = TrustMode.SHADOW
    return gw


def run_harness() -> dict:
    gateways: Dict[str, SafeMCPGateway] = {}
    rows = []
    for sc in CORPUS:
        gw = gateways.setdefault(sc.profile, _gateway_for_profile(sc.profile))
        gw.mcp_client.register_tool(sc.tool, lambda p: "ok", sc.risk)
        gw.tool_definitions[sc.tool] = MCPToolDefinition(
            name=sc.tool, description=sc.name, risk_level=sc.risk,
            requires_confirmation=sc.requires_confirmation,
            min_confidence=sc.min_confidence, capabilities=sc.capabilities)
        call = MCPToolCall(
            tool_name=sc.tool, parameters={"x": 1},
            quality_score=sc.quality, coherence_score=sc.coherence,
            raw_entropy=sc.raw_entropy, verbalized_safety_confidence=sc.verbalized_safety)
        _run(gw.call_tool(call))
        e = gw.audit_log[-1]
        rows.append({
            "scenario": sc.name, "profile": sc.profile,
            "legacy": e.trust_legacy_decision, "trust": e.trust_decision,
            "class": e.trust_mismatch_class, "drivers": e.trust_drivers or [],
        })
    counts = Counter(r["class"] for r in rows)
    return {"rows": rows, "counts": dict(counts)}


def render(report: dict) -> str:
    lines = ["# Phase 1.5 differential parity report (shadow mode)", "",
             "| scenario | profile | legacy | trust | class | drivers |",
             "|---|---|---|---|---|---|"]
    for r in report["rows"]:
        lines.append(f"| {r['scenario']} | {r['profile']} | {r['legacy']} | {r['trust']} "
                     f"| {r['class']} | {','.join(r['drivers'])} |")
    lines.append("")
    c = report["counts"]
    total = sum(c.values())
    lines.append(f"**Total:** {total}  ·  **match:** {c.get('match', 0)}  ·  "
                 f"**mismatch:** {total - c.get('match', 0)} "
                 f"(intended={c.get('intended', 0)}, unintended={c.get('unintended', 0)}, "
                 f"unresolved={c.get('unresolved', 0)})")
    lines.append("")
    lines.append("**Flip gate:** trust_core may become authoritative only when "
                 "unintended == 0 and unresolved == 0.")
    return "\n".join(lines) + "\n"


def main() -> int:
    report = run_harness()
    print(render(report))
    c = report["counts"]
    return 0 if (c.get("unintended", 0) == 0 and c.get("unresolved", 0) == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
