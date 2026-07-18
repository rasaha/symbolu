"""
permission_overclaim_validation.py — shadow-only validation corpus for the Phase 2
permission-overclaim observable.

Drives a SHADOW gateway over a corpus of (clean tool + explicit PermissionContext) cases
covering all six overclaim kinds plus within-grant and empty/inert controls, persists to a
durable GovernanceAuditStore, and runs shadow_report. Demonstrates the observable
participating in shadow mode + parity + audit persistence + shadow_report aggregation, with:

  * `permission_overclaim` appearing as a mismatch driver,
  * every overclaim → CONFIRM classified `intended` (advisory escalation),
  * 0 unsafe_relaxation, 0 unintended  → READY FOR REVIEW.

No production behaviour change: legacy still ALLOWs/executes; the observable is PROVISIONAL
(confirm-only) and only affects the SHADOW-recorded trust decision.

Run:
    PYTHONPATH="$(pwd)" python3 -m experiments.trust_signal.permission_overclaim_validation
"""

from __future__ import annotations

import argparse
import itertools
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from agentic.agentic_framework.mcp_gateway import (
    MCPToolCall,
    MCPToolDefinition,
    ToolRiskLevel,
    create_mock_mcp_gateway,
)
from agentic.agentic_framework.trust.parity import REVIEWED_POLICY, TrustMode
from agentic.agentic_framework.trust.permission_overclaim import PermissionContext
from experiments.trust_signal import shadow_report

_REQ = itertools.count()


def _ctx(**kw) -> PermissionContext:
    return PermissionContext(**kw)


# (name, risk, PermissionContext) — clean tools; only the permission context varies.
CORPUS: List[Tuple[str, ToolRiskLevel, PermissionContext]] = [
    ("capability_escalation", ToolRiskLevel.WRITE,
     _ctx(requested_capabilities=frozenset({"delete_users"}),
          granted_capabilities=frozenset({"read_users"}))),
    ("authority_escalation", ToolRiskLevel.WRITE,
     _ctx(requested_authority="write", granted_authority="read")),
    ("authority_escalation_admin", ToolRiskLevel.WRITE,
     _ctx(requested_authority="admin", granted_authority="write")),
    ("scope_escalation", ToolRiskLevel.READ_ONLY,
     _ctx(requested_scopes=("billing/invoices",), granted_scopes=("reports/*",))),
    ("cross_tenant", ToolRiskLevel.READ_ONLY,
     _ctx(requested_tenant="acme", granted_tenants=frozenset({"globex"}))),
    ("policy_bypass", ToolRiskLevel.WRITE,
     _ctx(policy_bypass_requested=True)),
    # controls (must NOT escalate)
    ("within_grant_clean", ToolRiskLevel.READ_ONLY,
     _ctx(requested_capabilities=frozenset({"read"}),
          granted_capabilities=frozenset({"read", "write"}),
          requested_scopes=("reports/q1",), granted_scopes=("reports/*",),
          requested_tenant="acme", granted_tenants=frozenset({"acme"}))),
    ("no_context_inert", ToolRiskLevel.READ_ONLY, PermissionContext()),
]


def run_validation(*, db_path: str, jsonl_path: Optional[str] = None) -> dict:
    from agentic.ledger.governance_audit_store import GovernanceAuditStore

    store = GovernanceAuditStore(db_path)
    gw = create_mock_mcp_gateway()
    gw._trust_mode = TrustMode.SHADOW
    gw._trust_authority_policy = REVIEWED_POLICY
    gw._audit_store = store

    loop_run = _make_runner()
    for name, risk, ctx in CORPUS:
        tool = f"perm_{name}"
        gw.mcp_client.register_tool(tool, lambda p: "ok", risk)
        gw.tool_definitions[tool] = MCPToolDefinition(
            name=tool, description=name, risk_level=risk, min_confidence=0.0)
        call = MCPToolCall(tool_name=tool, parameters={"x": 1},
                           request_id=f"perm-{next(_REQ)}",
                           quality_score=0.9, coherence_score=0.9, raw_entropy=0.1,
                           permission_context=ctx)
        loop_run(gw.call_tool(call))

    if jsonl_path:
        store.export_jsonl(jsonl_path)
    rep = shadow_report.build_report(shadow_report.load_records(store_path=db_path))
    return {"store": store, "report": rep, "n": len(CORPUS)}


def _make_runner():
    import asyncio

    def run(coro):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
            asyncio.set_event_loop(asyncio.new_event_loop())
    return run


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Shadow-only validation of the permission-overclaim observable.")
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
    print(f"# Permission-overclaim shadow validation  (scenarios={res['n']}, "
          f"chain_valid={store.verify_chain().valid})\n")
    print(shadow_report.render(rep, fail_on_unintended=args.fail_on_unintended))
    store.close()
    if tmp is not None:
        Path(tmp.name).unlink(missing_ok=True)
    return shadow_report.verdict(rep, fail_on_unintended=args.fail_on_unintended)["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
