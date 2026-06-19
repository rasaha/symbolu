"""
outcome_reputation_validation.py — shadow-only validation corpus for the Phase 2
outcome-reputation observable.

Each scenario seeds a synthetic PRIOR history (approved / denied / blocked / auto-allowed
outcomes) into the gateway's audit log — the in-memory view of the durable hash-chained
chain — then makes a single CLEAN call to that tool with `enable_outcome_reputation=True`.
The observable reads that history and (only on a poor track record) escalates the otherwise
ALLOW decision to a recorded CONFIRM.

Demonstrates participation in shadow mode + parity + audit persistence + shadow_report
aggregation, with the reputation escalations classified `intended` (advisory), 0
unsafe_relaxation, 0 unintended. No production behaviour change (flag off by default; legacy
still ALLOWs/executes here).

Run:
    PYTHONPATH="$(pwd)" python3 -m experiments.trust_signal.outcome_reputation_validation
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional

from agentic.agentic_framework.mcp_gateway import (
    MCPToolCall,
    MCPToolDefinition,
    ToolRiskLevel,
    create_mock_mcp_gateway,
)
from agentic.agentic_framework.trust.parity import REVIEWED_POLICY, TrustMode
from experiments.trust_signal import shadow_report

_REQ = itertools.count()


def _entry(tool: str, decision: str, human_confirmed: bool = False) -> SimpleNamespace:
    return SimpleNamespace(tool_name=tool,
                           decision=SimpleNamespace(value=decision),
                           human_confirmed=human_confirmed)


def _history(tool: str, *, approved=0, denied=0, blocked=0, auto=0) -> List[SimpleNamespace]:
    es: List[SimpleNamespace] = []
    es += [_entry(tool, "allowed", True) for _ in range(approved)]
    es += [_entry(tool, "escalate") for _ in range(denied)]
    es += [_entry(tool, "blocked") for _ in range(blocked)]
    es += [_entry(tool, "allowed", False) for _ in range(auto)]
    return es


# (name, risk, prior-history) — clean tools; only the seeded history varies.
CORPUS = [
    ("reputation_reliable", ToolRiskLevel.READ_ONLY,
     dict(approved=6, auto=4)),                          # good → SAFE → match
    ("reputation_denied", ToolRiskLevel.WRITE,
     dict(approved=1, denied=5, auto=2)),                # poor (low approval) → CONFIRM
    ("reputation_violations", ToolRiskLevel.WRITE,
     dict(blocked=8, auto=2)),                           # egregious violations → CONFIRM
    ("reputation_new_tool", ToolRiskLevel.READ_ONLY,
     dict()),                                            # no history → inert → match
]


def _runner():
    def run(coro):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
            asyncio.set_event_loop(asyncio.new_event_loop())
    return run


def run_validation(*, db_path: str, jsonl_path: Optional[str] = None) -> dict:
    from agentic.ledger.governance_audit_store import GovernanceAuditStore

    store = GovernanceAuditStore(db_path)
    gw = create_mock_mcp_gateway()
    gw._trust_mode = TrustMode.SHADOW
    gw._trust_authority_policy = REVIEWED_POLICY
    gw._enable_outcome_reputation = True
    gw._audit_store = store

    run = _runner()
    for name, risk, hist in CORPUS:
        tool = f"perf_{name}"
        gw.audit_log.extend(_history(tool, **hist))     # seed prior chain history
        gw.mcp_client.register_tool(tool, lambda p: "ok", risk)
        gw.tool_definitions[tool] = MCPToolDefinition(
            name=tool, description=name, risk_level=risk, min_confidence=0.0)
        run(gw.call_tool(MCPToolCall(
            tool_name=tool, parameters={"x": 1}, request_id=f"rep-{next(_REQ)}",
            quality_score=0.9, coherence_score=0.9, raw_entropy=0.1)))

    if jsonl_path:
        store.export_jsonl(jsonl_path)
    rep = shadow_report.build_report(shadow_report.load_records(store_path=db_path))
    return {"store": store, "report": rep, "n": len(CORPUS)}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Shadow-only validation of the outcome-reputation observable.")
    parser.add_argument("--db")
    parser.add_argument("--jsonl")
    parser.add_argument("--fail-on-unintended", action="store_true")
    args = parser.parse_args(argv)

    tmp = None
    db_path = args.db
    if db_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        db_path = tmp.name

    res = run_validation(db_path=db_path, jsonl_path=args.jsonl)
    store, rep = res["store"], res["report"]
    print(f"# Outcome-reputation shadow validation  (scenarios={res['n']}, "
          f"chain_valid={store.verify_chain().valid})\n")
    print(shadow_report.render(rep, fail_on_unintended=args.fail_on_unintended))
    store.close()
    if tmp is not None:
        Path(tmp.name).unlink(missing_ok=True)
    return shadow_report.verdict(rep, fail_on_unintended=args.fail_on_unintended)["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
