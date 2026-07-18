"""File-backed CLI for the runtime gateway.

    python3 -m action_gateway.cli <command> [args]

The gateway is an in-process object; to make a multi-command CLI usable, the
session state is persisted to a JSON file between invocations (``--session``,
default ``.action_gateway_session.json``). This is a convenience shell over the
same ``Gateway`` API a transport (HTTP/gRPC/MCP) would call — it adds no policy
logic. Output is single-line JSON; secrets are never printed (there are none —
signatures/tokens carry no secret material).

Commands: start, submit, evaluate, execute, status, audit, verify.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from .clock import RealClock
from .errors import GatewayError
from ._ref import REF_VERSION
from ._ref import errors as ref_errors
from .gateway import Gateway
from .mapping import ToolRequest

DEFAULT_SESSION = ".action_gateway_session.json"


def _emit(obj) -> int:
    sys.stdout.write(json.dumps(obj, sort_keys=True) + "\n")
    return 0 if obj.get("ok", True) else 1


def _err(exc: Exception):
    return {"ok": False, "error_code": getattr(exc, "code", type(exc).__name__),
            "message": str(exc)}


def _load(path: str) -> Gateway:
    snap = json.loads(Path(path).read_text())
    return Gateway.restore(snap, clock=RealClock())


def _save(gw: Gateway, path: str) -> None:
    Path(path).write_text(json.dumps(gw.snapshot(), sort_keys=True))


def _read_json(path):
    return json.loads(Path(path).read_text()) if path else None


def cmd_start(a):
    root = a.sandbox_root or tempfile.mkdtemp(prefix="action-gateway-")
    gw = Gateway(sandbox_root=root, clock=RealClock())
    _save(gw, a.session)
    return _emit({"ok": True, "session": a.session, "sandbox_root": root,
                  "policy_version": gw.policy_version, "ref_version": REF_VERSION})


def cmd_submit(a):
    try:
        gw = _load(a.session)
        req = ToolRequest(
            tool=a.tool, verb=a.verb, target=a.target,
            args=json.loads(a.args) if a.args else {},
            reversibility=a.reversibility, grant=a.grant or "*",
            permissions=a.permissions)
        out = gw.submit_action(req)
        _save(gw, a.session)
        return _emit({"ok": True, **out})
    except Exception as exc:  # noqa: BLE001
        return _emit(_err(exc))


def cmd_evaluate(a):
    try:
        gw = _load(a.session)
        out = gw.evaluate_action(a.request_id, evidence=_read_json(a.evidence),
                                 approvals=_read_json(a.approvals))
        _save(gw, a.session)
        return _emit({"ok": True, **out})
    except Exception as exc:  # noqa: BLE001
        return _emit(_err(exc))


def cmd_execute(a):
    try:
        gw = _load(a.session)
        out = gw.execute_action(
            a.request_id, observed_state_hash=a.observed_state_hash,
            requested_permissions=a.requested_permissions,
            active_policy_hash=a.active_policy_hash)
        _save(gw, a.session)
        return _emit({"ok": True, **out})
    except (GatewayError, ref_errors.GateError) as exc:
        # persist the (audited) rejection, then report it
        try:
            _save(gw, a.session)
        except Exception:  # noqa: BLE001
            pass
        return _emit(_err(exc))
    except Exception as exc:  # noqa: BLE001
        return _emit(_err(exc))


def cmd_status(a):
    try:
        gw = _load(a.session)
        return _emit({"ok": True, **gw.status(a.request_id)})
    except Exception as exc:  # noqa: BLE001
        return _emit(_err(exc))


def cmd_audit(a):
    try:
        gw = _load(a.session)
        return _emit({"ok": True, **gw.audit_log()})
    except Exception as exc:  # noqa: BLE001
        return _emit(_err(exc))


def cmd_verify(a):
    try:
        gw = _load(a.session)
        v = gw.verify_audit()
        return _emit({"ok": v["intact"], **v})
    except Exception as exc:  # noqa: BLE001
        return _emit(_err(exc))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="action_gateway")
    p.add_argument("--session", default=DEFAULT_SESSION, help="session state file")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start", help="initialize a fresh session")
    s.add_argument("--sandbox-root", default=None)
    s.set_defaults(fn=cmd_start)

    s = sub.add_parser("submit", help="submit a tool action")
    s.add_argument("--tool", required=True)
    s.add_argument("--verb", required=True)
    s.add_argument("--target", nargs="+", required=True)
    s.add_argument("--args", default=None, help="JSON object of operation arguments")
    s.add_argument("--reversibility", default=None)
    s.add_argument("--grant", default=None)
    s.add_argument("--permissions", nargs="+", default=None)
    s.set_defaults(fn=cmd_submit)

    s = sub.add_parser("evaluate", help="evaluate a submitted action through the gate")
    s.add_argument("request_id")
    s.add_argument("--evidence", default=None, help="JSON array of evidence objects")
    s.add_argument("--approvals", default=None, help="JSON array of approval objects")
    s.set_defaults(fn=cmd_evaluate)

    s = sub.add_parser("execute", help="execute an approved action (requires token)")
    s.add_argument("request_id")
    s.add_argument("--observed-state-hash", default=None, dest="observed_state_hash")
    s.add_argument("--requested-permissions", nargs="+", default=None,
                   dest="requested_permissions")
    s.add_argument("--active-policy-hash", default=None, dest="active_policy_hash")
    s.set_defaults(fn=cmd_execute)

    s = sub.add_parser("status", help="show a request's runtime state")
    s.add_argument("request_id")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("audit", help="dump the audit chain")
    s.set_defaults(fn=cmd_audit)

    s = sub.add_parser("verify", help="verify the audit chain integrity")
    s.set_defaults(fn=cmd_verify)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
