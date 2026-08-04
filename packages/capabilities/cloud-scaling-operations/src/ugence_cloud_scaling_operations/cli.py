"""Offline CLI: ``ugence-cloud-scaling-operations``.

Default behavior is NON-MUTATING. Live execution requires the explicit
``execute --mode live`` command with an authorization, target/audit configuration, and
a confirmation flag. ``version``/``inspect-capabilities``/``validate-*``/``plan``/
``dry-run``/``simulate``/``verify-install`` never mutate infrastructure.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from .version import __version__
from .config import OperationsConfig, TargetPolicy
from .contracts import (
    ExecutionAuthorization,
    ExecutionMode,
    ExecutionRequest,
)
from .executors import ControlledScalingExecutor, FakeScalingBackend


def _eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def _read_json(path: str):
    text = sys.stdin.read() if path == "-" else open(path, "r", encoding="utf-8").read()
    return json.loads(text)


def _request_from(d: dict) -> ExecutionRequest:
    return ExecutionRequest(
        action=d.get("action", "scale"),
        target_cluster=d["target_cluster"],
        target_namespace=d["target_namespace"],
        target_resource=d["target_resource"],
        current_replicas=int(d["current_replicas"]),
        target_replicas=int(d["target_replicas"]),
        recommendation_id=d.get("recommendation_id", ""),
        idempotency_key=d.get("idempotency_key", "cli"),
        correlation_id=d.get("correlation_id"),
        observed_at=d.get("observed_at"),
    )


def _cmd_version(_a) -> int:
    print(json.dumps({"name": "ugence-cloud-scaling-operations", "version": __version__},
                     sort_keys=True))
    return 0


def _cmd_inspect(_a) -> int:
    print(json.dumps({
        "authority_class": "CONTROLLED_EXECUTION",
        "execution_capability": "INFRASTRUCTURE_MUTATION",
        "advisory_only": False,
        "contains_concrete_executor": True,
        "requires_external_authorization": True,
        "live_execution_enabled_by_default": False,
        "default_mode": "dry_run",
        "modes": [m.value for m in ExecutionMode],
        "mutation_entrypoints": ["ControlledScalingExecutor.execute (LIVE)",
                                 "GateExecutor.sync (LIVE)"],
    }, indent=2, sort_keys=True))
    return 0


def _cmd_validate_config(a) -> int:
    try:
        _read_json(a.input)
    except Exception as exc:
        _eprint(f"error: invalid config JSON: {exc}")
        return 2
    print(json.dumps({"valid": True}))
    return 0


def _cmd_validate_authorization(a) -> int:
    try:
        d = _read_json(a.input)
        authz = ExecutionAuthorization(**d)
    except Exception as exc:
        _eprint(f"error: invalid authorization: {exc}")
        return 2
    import time
    now = time.time()
    problems = []
    if authz.is_expired(now):
        problems.append("expired")
    if authz.is_not_yet_valid(now):
        problems.append("not_yet_valid")
    if not authz.authorization_id or not authz.nonce:
        problems.append("malformed")
    print(json.dumps({"structurally_valid": not problems, "problems": problems},
                     sort_keys=True))
    return 0 if not problems else 1


def _plan_or_dryrun(a) -> int:
    try:
        req = _request_from(_read_json(a.input))
    except Exception as exc:
        _eprint(f"error: invalid request: {exc}")
        return 2
    ex = ControlledScalingExecutor(OperationsConfig(mode=ExecutionMode.DRY_RUN))
    receipt = ex.execute(req, tenant_id="cli")
    print(receipt.to_json(indent=2))
    return 0


def _cmd_simulate(a) -> int:
    try:
        req = _request_from(_read_json(a.input))
    except Exception as exc:
        _eprint(f"error: invalid request: {exc}")
        return 2
    authz = None
    if a.authorization:
        try:
            authz = ExecutionAuthorization(**_read_json(a.authorization))
        except Exception as exc:
            _eprint(f"error: invalid authorization: {exc}")
            return 2
    tp = TargetPolicy(allowed_clusters=(req.target_cluster,),
                      allowed_namespaces=(req.target_namespace,),
                      allowed_resources=(req.target_resource,),
                      max_replica_delta=max(1, abs(req.delta)),
                      min_replicas=0, max_replicas=max(req.target_replicas, req.current_replicas) + 1)
    ex = ControlledScalingExecutor(
        OperationsConfig(mode=ExecutionMode.SIMULATION, target_policy=tp),
        backend=FakeScalingBackend({f"{req.target_cluster}/{req.target_namespace}/{req.target_resource}":
                                    req.current_replicas}))
    receipt = ex.execute(req, authz, tenant_id=(authz.tenant_id if authz else "cli"))
    print(receipt.to_json(indent=2))
    return 0 if receipt.outcome != "denied" else 1


def _cmd_verify_install(_a) -> int:
    # Import-only smoke: proves the package imports and the facade constructs offline.
    ControlledScalingExecutor(OperationsConfig())
    print(json.dumps({"import": "ok", "default_mode": "dry_run", "version": __version__},
                     sort_keys=True))
    return 0


def _cmd_execute(a) -> int:
    # Live execution is deliberately hard: it requires an unmistakable command plus
    # explicit flags. This CLI never ships a real backend/credentials, so a live
    # invocation fails closed here rather than mutating anything.
    if a.mode != "live":
        _eprint("error: 'execute' requires --mode live (dry-run/simulate are separate commands)")
        return 2
    if not a.authorization or not a.confirm:
        _eprint("error: live execution requires --authorization <file> and --confirm")
        return 2
    _eprint("error: live execution requires an operator-configured scaling backend, "
            "audit sink, and credentials that this CLI does not provide. Use the "
            "ControlledScalingExecutor API in a governed deployment.")
    return 3


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ugence-cloud-scaling-operations",
        description="Controlled-execution operations for cloud scaling (non-mutating by default).")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("version").set_defaults(func=_cmd_version)
    sub.add_parser("inspect-capabilities").set_defaults(func=_cmd_inspect)
    sub.add_parser("verify-install").set_defaults(func=_cmd_verify_install)

    vc = sub.add_parser("validate-config"); vc.add_argument("--input", "-i", required=True)
    vc.set_defaults(func=_cmd_validate_config)
    va = sub.add_parser("validate-authorization"); va.add_argument("--input", "-i", required=True)
    va.set_defaults(func=_cmd_validate_authorization)

    for name in ("plan", "dry-run"):
        sp = sub.add_parser(name); sp.add_argument("--input", "-i", required=True)
        sp.set_defaults(func=_plan_or_dryrun)

    sim = sub.add_parser("simulate")
    sim.add_argument("--input", "-i", required=True)
    sim.add_argument("--authorization", "-a", default=None)
    sim.set_defaults(func=_cmd_simulate)

    ex = sub.add_parser("execute", help="live execution (requires explicit flags)")
    ex.add_argument("--mode", default="dry_run")
    ex.add_argument("--authorization", "-a", default=None)
    ex.add_argument("--input", "-i", default=None)
    ex.add_argument("--confirm", action="store_true")
    ex.set_defaults(func=_cmd_execute)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
