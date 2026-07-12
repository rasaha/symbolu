"""File-backed CLI for the MCP enforcement gateway.

    python3 -m action_gateway_mcp.cli <command> [args]

Session state (server + client counters) persists to ``--session`` between
invocations. Output is single-line JSON. Raw secrets and broker capabilities are
never printed (responses carry no token/capability material; ``execution_token``
is always null).

Commands: start, list-tools, submit, status, simulate, provide-evidence,
escalations, approve, execute, audit, verify, metrics, demos.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from .clientkit import ClientSession
from .server import McpGateway
from ._core import RealClock

DEFAULT_SESSION = ".action_gateway_mcp_session.json"


def _emit(obj) -> int:
    sys.stdout.write(json.dumps(obj, sort_keys=True, default=str) + "\n")
    return 0 if obj.get("ok", True) else 1


def _load(path):
    snap = json.loads(Path(path).read_text())
    clock = RealClock()
    mcp = McpGateway.restore(snap["mcp"], clock=clock)
    c = snap["client"]
    cs = ClientSession(clock=clock, authenticated_agent_id=c["agent"],
                       delegator=c["delegator"], correlation_id=c["correlation_id"],
                       start_seq=c["seq"], start_nonce=c["nonce"])
    return mcp, cs, path


def _save(mcp, cs, path):
    snap = {"mcp": mcp.snapshot(),
            "client": {"agent": cs.authenticated_agent_id, "delegator": cs.delegator,
                       "correlation_id": cs.correlation_id, **cs.counters()}}
    Path(path).write_text(json.dumps(snap, sort_keys=True, default=str))


def _read_json(path):
    return json.loads(Path(path).read_text()) if path else None


def cmd_start(a):
    root = a.sandbox_root or tempfile.mkdtemp(prefix="mcp-gateway-")
    clock = RealClock()
    mcp = McpGateway(sandbox_root=root, clock=clock)
    cs = ClientSession(clock=clock, authenticated_agent_id=a.agent,
                       delegator=a.delegator, correlation_id=a.correlation)
    _save(mcp, cs, a.session)
    return _emit({"ok": True, "session": a.session, "sandbox_root": root,
                  "exposed_tools": list(mcp.list_tools()["tools"].keys())})


def cmd_list_tools(a):
    mcp, cs, path = _load(a.session)
    return _emit({"ok": True, "tools": mcp.list_tools()["tools"]})


def cmd_submit(a):
    mcp, cs, path = _load(a.session)
    args = json.loads(a.args) if a.args else {}
    from .registry import REGISTRY
    spec = REGISTRY.get(a.tool)
    if spec is not None and spec.read_only:
        out = mcp.read(cs.context(), a.tool, args)
    else:
        prep = mcp.prepare(cs.context(), a.tool, args)
        if prep.get("phase") != "prepared":
            out = prep
        else:
            ev = _read_json(a.evidence)
            out = mcp.evaluate(cs.context(), prep["request_id"], evidence=ev)
            out["request_id"] = prep["request_id"]
            out["action_hash"] = prep["action_hash"]
    _save(mcp, cs, path)
    return _emit({"ok": out.get("outcome") != "DENY" or "request_id" in out, **out})


def cmd_status(a):
    mcp, cs, path = _load(a.session)
    return _emit({"ok": True, **mcp.status(a.request_id)})


def cmd_simulate(a):
    mcp, cs, path = _load(a.session)
    out = mcp.simulate(cs.context(), a.request_id, fidelity=a.fidelity)
    _save(mcp, cs, path)
    return _emit({"ok": True, **out})


def cmd_provide_evidence(a):
    mcp, cs, path = _load(a.session)
    out = mcp.provide_evidence(cs.context(), a.request_id, _read_json(a.evidence) or [])
    _save(mcp, cs, path)
    return _emit({"ok": True, **out})


def cmd_escalations(a):
    mcp, cs, path = _load(a.session)
    return _emit({"ok": True, **mcp.list_escalations()})


def cmd_approve(a):
    mcp, cs, path = _load(a.session)
    ap = mcp.create_test_approval(a.request_id, nonce=a.nonce)
    out = mcp.attach_approval(cs.context(), a.request_id, ap)
    _save(mcp, cs, path)
    return _emit({"ok": True, **out})


def cmd_execute(a):
    mcp, cs, path = _load(a.session)
    out = mcp.execute(cs.context(), a.request_id, observed_state_hash=a.observed_state_hash)
    _save(mcp, cs, path)
    return _emit({"ok": out.get("executable", False), **out})


def cmd_audit(a):
    mcp, cs, path = _load(a.session)
    return _emit({"ok": True, **mcp.audit_dump()})


def cmd_verify(a):
    mcp, cs, path = _load(a.session)
    v = mcp.verify_audit()
    return _emit({"ok": v["intact"], **v})


def cmd_metrics(a):
    mcp, cs, path = _load(a.session)
    return _emit({"ok": True, **mcp.metrics_snapshot()})


def cmd_demos(a):
    import importlib.util
    sc_path = Path(__file__).resolve().parents[1] / "demos" / "scenarios.py"
    spec = importlib.util.spec_from_file_location("mcp_demo_scenarios", sc_path)
    scenarios = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scenarios)
    results = scenarios.run_all()
    return _emit({"ok": all(r["passed"] for r in results),
                  "passed": sum(r["passed"] for r in results), "total": len(results),
                  "results": [{"scenario": r["scenario"], "passed": r["passed"],
                               "actual": r["actual"]} for r in results]})


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="action_gateway_mcp")
    p.add_argument("--session", default=DEFAULT_SESSION)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start"); s.add_argument("--sandbox-root", default=None)
    s.add_argument("--agent", default="agent://sre/1")
    s.add_argument("--delegator", default="user://alice")
    s.add_argument("--correlation", default="sess-mcp")
    s.set_defaults(fn=cmd_start)

    sub.add_parser("list-tools").set_defaults(fn=cmd_list_tools)

    s = sub.add_parser("submit"); s.add_argument("--tool", required=True)
    s.add_argument("--args", default=None); s.add_argument("--evidence", default=None)
    s.set_defaults(fn=cmd_submit)

    s = sub.add_parser("status"); s.add_argument("request_id"); s.set_defaults(fn=cmd_status)

    s = sub.add_parser("simulate"); s.add_argument("request_id")
    s.add_argument("--fidelity", default="HIGH"); s.set_defaults(fn=cmd_simulate)

    s = sub.add_parser("provide-evidence"); s.add_argument("request_id")
    s.add_argument("--evidence", required=True); s.set_defaults(fn=cmd_provide_evidence)

    sub.add_parser("escalations").set_defaults(fn=cmd_escalations)

    s = sub.add_parser("approve"); s.add_argument("request_id")
    s.add_argument("--nonce", default="ap-cli"); s.set_defaults(fn=cmd_approve)

    s = sub.add_parser("execute"); s.add_argument("request_id")
    s.add_argument("--observed-state-hash", default=None, dest="observed_state_hash")
    s.set_defaults(fn=cmd_execute)

    sub.add_parser("audit").set_defaults(fn=cmd_audit)
    sub.add_parser("verify").set_defaults(fn=cmd_verify)
    sub.add_parser("metrics").set_defaults(fn=cmd_metrics)
    sub.add_parser("demos").set_defaults(fn=cmd_demos)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
