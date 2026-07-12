"""File-backed CLI for the Kubernetes enforcement gateway.

    python3 -m action_gateway_k8s.cli <command> [args]

Session state persists to ``--session`` between invocations. JSON output. Never
prints bearer tokens, broker capabilities, or secret contents.

Commands: env-up, env-status, env-down, list-tools, list-protected, prepare,
evaluate, dry-run, escalations, approve, execute, convergence, audit, verify,
metrics, demos.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

from . import cluster
from ._core import RealClock
from .kubeclient import GVR
from .server import K8sGateway
from action_gateway_mcp import ClientSession

DEFAULT_SESSION = ".action_gateway_k8s_session.json"


def _emit(obj) -> int:
    sys.stdout.write(json.dumps(obj, sort_keys=True, default=str) + "\n")
    return 0 if obj.get("ok", True) else 1


def _err(exc):
    return {"ok": False, "error_code": getattr(exc, "code", type(exc).__name__),
            "message": str(exc)}


def _load(path):
    snap = json.loads(Path(path).read_text())
    clock = RealClock()
    gw = K8sGateway.restore(snap["k8s"], clock=clock)
    c = snap["client"]
    cs = ClientSession(clock=clock, correlation_id=c["correlation_id"],
                       start_seq=c["seq"], start_nonce=c["nonce"])
    return gw, cs, path


def _save(gw, cs, path):
    Path(path).write_text(json.dumps(
        {"k8s": gw.snapshot(),
         "client": {"correlation_id": cs.correlation_id, **cs.counters()}},
        sort_keys=True, default=str))


# ---- cluster lifecycle ----

def cmd_env_up(a):
    try:
        kcfg = cluster.up()
        return _emit({"ok": True, "kubeconfig": kcfg, **cluster.status()})
    except Exception as exc:  # noqa: BLE001
        return _emit(_err(exc))


def cmd_env_status(a):
    return _emit({"ok": True, **cluster.status()})


def cmd_env_down(a):
    cluster.down()
    return _emit({"ok": True, "down": True})


def cmd_start(a):
    if not cluster.is_available():
        return _emit({"ok": False, "error_code": "E_K8S_CLUSTER_UNAVAILABLE",
                      "message": "run env-up first"})
    gw = K8sGateway(allowed_namespaces=tuple(a.allowed_namespaces), clock=RealClock())
    cs = ClientSession(clock=gw.clock, correlation_id=a.correlation)
    _save(gw, cs, a.session)
    return _emit({"ok": True, "session": a.session,
                  "tools": list(gw.list_tools()["tools"].keys())})


def cmd_list_tools(a):
    gw, cs, path = _load(a.session)
    return _emit({"ok": True, "tools": gw.list_tools()["tools"]})


def cmd_list_protected(a):
    c = cluster.admin_client()
    out = {}
    for kind in ("ConfigMap", "Deployment", "Service"):
        out[kind] = c.list_names(kind, cluster.PROTECTED_NS)
    return _emit({"ok": True, "namespace": cluster.PROTECTED_NS, "resources": out})


def _args(a):
    return json.loads(a.args) if a.args else {}


def cmd_prepare(a):
    gw, cs, path = _load(a.session)
    out = gw.prepare(cs.context(), a.tool, _args(a))
    _save(gw, cs, path)
    return _emit({"ok": out.get("outcome") != "DENY", **out})


def cmd_evaluate(a):
    gw, cs, path = _load(a.session)
    out = gw.evaluate(cs.context(), a.request_id)
    _save(gw, cs, path)
    return _emit({"ok": True, **out})


def cmd_dry_run(a):
    gw, cs, path = _load(a.session)
    out = gw.dry_run(cs.context(), a.request_id)
    _save(gw, cs, path)
    return _emit({"ok": out.get("outcome") != "DENY", **out})


def cmd_escalations(a):
    gw, cs, path = _load(a.session)
    return _emit({"ok": True, **gw.list_escalations()})


def cmd_approve(a):
    gw, cs, path = _load(a.session)
    ap = gw.create_test_approval(a.request_id)
    out = gw.attach_approval(cs.context(), a.request_id, ap)
    _save(gw, cs, path)
    return _emit({"ok": True, **out})


def cmd_execute(a):
    gw, cs, path = _load(a.session)
    out = gw.execute(cs.context(), a.request_id)
    _save(gw, cs, path)
    return _emit({"ok": out.get("executable", False), **out})


def cmd_convergence(a):
    gw, cs, path = _load(a.session)
    return _emit({"ok": True, **gw.check_convergence(a.request_id)})


def cmd_audit(a):
    gw, cs, path = _load(a.session)
    return _emit({"ok": True, **gw.audit_dump()})


def cmd_verify(a):
    gw, cs, path = _load(a.session)
    v = gw.verify_audit()
    return _emit({"ok": v["intact"], **v})


def cmd_metrics(a):
    gw, cs, path = _load(a.session)
    return _emit({"ok": True, **gw.metrics_snapshot()})


def cmd_demos(a):
    sc_path = Path(__file__).resolve().parents[1] / "demos" / "scenarios.py"
    spec = importlib.util.spec_from_file_location("k8s_demo_scenarios", sc_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    results = mod.run_all()
    if all(r.get("skipped") for r in results):
        return _emit({"ok": True, "skipped": True, "reason": "no cluster; run env-up"})
    ran = [r for r in results if not r.get("skipped")]
    return _emit({"ok": all(r["passed"] for r in ran), "passed": sum(bool(r["passed"]) for r in ran),
                  "total": len(ran), "results": [{"scenario": r["scenario"],
                                                  "passed": r["passed"], "actual": r.get("actual")}
                                                 for r in ran]})


def build_parser():
    p = argparse.ArgumentParser(prog="action_gateway_k8s")
    p.add_argument("--session", default=DEFAULT_SESSION)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("env-up").set_defaults(fn=cmd_env_up)
    sub.add_parser("env-status").set_defaults(fn=cmd_env_status)
    sub.add_parser("env-down").set_defaults(fn=cmd_env_down)
    s = sub.add_parser("start"); s.add_argument("--allowed-namespaces", nargs="+",
                                                default=["protected"], dest="allowed_namespaces")
    s.add_argument("--correlation", default="sess-k8s"); s.set_defaults(fn=cmd_start)
    sub.add_parser("list-tools").set_defaults(fn=cmd_list_tools)
    sub.add_parser("list-protected").set_defaults(fn=cmd_list_protected)
    s = sub.add_parser("prepare"); s.add_argument("--tool", required=True)
    s.add_argument("--args", default=None); s.set_defaults(fn=cmd_prepare)
    s = sub.add_parser("evaluate"); s.add_argument("request_id"); s.set_defaults(fn=cmd_evaluate)
    s = sub.add_parser("dry-run"); s.add_argument("request_id"); s.set_defaults(fn=cmd_dry_run)
    sub.add_parser("escalations").set_defaults(fn=cmd_escalations)
    s = sub.add_parser("approve"); s.add_argument("request_id"); s.set_defaults(fn=cmd_approve)
    s = sub.add_parser("execute"); s.add_argument("request_id"); s.set_defaults(fn=cmd_execute)
    s = sub.add_parser("convergence"); s.add_argument("request_id"); s.set_defaults(fn=cmd_convergence)
    sub.add_parser("audit").set_defaults(fn=cmd_audit)
    sub.add_parser("verify").set_defaults(fn=cmd_verify)
    sub.add_parser("metrics").set_defaults(fn=cmd_metrics)
    sub.add_parser("demos").set_defaults(fn=cmd_demos)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except Exception as exc:  # noqa: BLE001
        return _emit(_err(exc))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
