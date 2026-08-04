"""Offline, non-executing CLI: ``ugence-llm-steering``.

Subcommands::

    ugence-llm-steering inspect
    ugence-llm-steering validate-registry --input registry.json
    ugence-llm-steering recommend --fixture scenario.json
    ugence-llm-steering explain   --fixture scenario.json
    ugence-llm-steering simulate  --fixture suite.json
    ugence-llm-steering verify-package
    ugence-llm-steering version

Every routing subcommand prints the advisory banner::

    ROUTING RECOMMENDATION ONLY
    NO PROVIDER REQUEST WAS EXECUTED

The CLI never contacts a provider, loads a credential, opens a socket, or executes a
model request. There is deliberately no live-invocation command.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, List, Optional

from .api import build_controller
from .contracts import ContractError, RegistryError, SteeringRequest
from .policy import RoutingPolicy
from .registry import validate_registry
from .simulation import run_suite
from .version import POLICY_VERSION, SCHEMA_VERSION, __version__

BANNER = "ROUTING RECOMMENDATION ONLY\nNO PROVIDER REQUEST WAS EXECUTED"

_AUTHORITY = {
    "distribution": "ugence-llm-steering-controller",
    "import_namespace": "ugence_llm_steering_controller",
    "version": __version__,
    "authority_class": "ADVISORY",
    "execution_capability": "NONE",
    "provider_invocation_capability": "NONE",
    "credential_access": "NONE",
    "routing_decision_is_authority": False,
    "live_provider_calls_enabled_by_default": False,
    "recommendation_only": True,
    "policy_version": POLICY_VERSION,
    "schema_version": SCHEMA_VERSION,
}


def _eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def _read_json(path: str) -> Any:
    text = sys.stdin.read() if path == "-" else open(path, "r", encoding="utf-8").read()
    return json.loads(text)


def _policy_from_scenario(scn: dict, req: SteeringRequest) -> Optional[RoutingPolicy]:
    p = scn.get("policy")
    if not p:
        return None
    return RoutingPolicy(
        preference=p.get("preference", req.quality_preference),
        weight_overrides=p.get("weight_overrides", {}) or {},
        policy_version=p.get("policy_version", "") or "",
    )


def _run_scenario_result(scn: dict):
    controller = build_controller(scn["registry"])
    req = SteeringRequest.from_dict(scn["request"])
    return controller.recommend(req, _policy_from_scenario(scn, req))


def _cmd_inspect(args: argparse.Namespace) -> int:
    print(BANNER, file=sys.stderr)
    print(json.dumps(_AUTHORITY, sort_keys=True, indent=2))
    return 0


def _cmd_version(args: argparse.Namespace) -> int:
    print(json.dumps({"name": "ugence-llm-steering-controller", "version": __version__,
                      "policy_version": POLICY_VERSION, "schema_version": SCHEMA_VERSION},
                     sort_keys=True))
    return 0


def _cmd_validate_registry(args: argparse.Namespace) -> int:
    try:
        payload = _read_json(args.input)
    except FileNotFoundError:
        _eprint(f"error: input not found: {args.input}"); return 2
    except json.JSONDecodeError as exc:
        _eprint(f"error: invalid JSON: {exc}"); return 2
    ok, problems = validate_registry(payload)
    print(json.dumps({"valid": ok, "problems": problems,
                      "model_count": len(payload.get("models", []) if isinstance(payload, dict) else [])},
                     sort_keys=True, indent=2))
    return 0 if ok else 1


def _cmd_recommend(args: argparse.Namespace) -> int:
    print(BANNER, file=sys.stderr)
    try:
        scn = _read_json(args.fixture)
        result = _run_scenario_result(scn)
    except (FileNotFoundError,) as exc:
        _eprint(f"error: fixture not found: {args.fixture}"); return 2
    except json.JSONDecodeError as exc:
        _eprint(f"error: invalid JSON: {exc}"); return 2
    except (ContractError, RegistryError, KeyError) as exc:
        _eprint(f"error: invalid fixture: {exc}"); return 2
    out = result.to_dict()
    _emit(out, args.output)
    return 0


def _cmd_explain(args: argparse.Namespace) -> int:
    print(BANNER, file=sys.stderr)
    try:
        scn = _read_json(args.fixture)
        result = _run_scenario_result(scn)
    except FileNotFoundError:
        _eprint(f"error: fixture not found: {args.fixture}"); return 2
    except json.JSONDecodeError as exc:
        _eprint(f"error: invalid JSON: {exc}"); return 2
    except (ContractError, RegistryError, KeyError) as exc:
        _eprint(f"error: invalid fixture: {exc}"); return 2
    rec = result.recommendation
    payload = {
        "status": result.status,
        "decision_id": result.decision_id,
        "reason": result.reason,
        "explanation": None if rec is None else rec.explanation.to_dict(),
        "confidence": None if rec is None else rec.confidence,
        "confidence_basis": None if rec is None else rec.confidence_basis,
        "execution_status": result.execution_status,
        "recommendation_only": result.recommendation_only,
    }
    _emit(payload, args.output)
    return 0


def _cmd_simulate(args: argparse.Namespace) -> int:
    print(BANNER, file=sys.stderr)
    try:
        payload = _read_json(args.fixture)
    except FileNotFoundError:
        _eprint(f"error: fixture not found: {args.fixture}"); return 2
    except json.JSONDecodeError as exc:
        _eprint(f"error: invalid JSON: {exc}"); return 2
    scenarios = payload["scenarios"] if isinstance(payload, dict) and "scenarios" in payload else payload
    if not isinstance(scenarios, list):
        _eprint("error: fixture must be a list or {'scenarios': [...]}"); return 2
    try:
        report = run_suite(scenarios)
    except (ContractError, RegistryError, KeyError) as exc:
        _eprint(f"error: invalid scenario: {exc}"); return 2
    _emit(report, args.output)
    # Nonzero if any expectation failed.
    if report["checked"] and report["expectations_met"] != report["checked"]:
        return 1
    return 0


def _cmd_verify_package(args: argparse.Namespace) -> int:
    """Lightweight, offline self-check of the advisory invariants."""
    import importlib

    checks: List[dict] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "passed": bool(ok), "detail": detail})

    mod = importlib.import_module("ugence_llm_steering_controller")
    add("import_ok", True, f"version={mod.__version__}")
    add("advisory_authority", _AUTHORITY["authority_class"] == "ADVISORY")
    add("execution_capability_none", _AUTHORITY["execution_capability"] == "NONE")
    add("credential_access_none", _AUTHORITY["credential_access"] == "NONE")

    # A minimal recommendation must be recommendation-only and not executed.
    scn = {
        "registry": {
            "providers": [{"provider_id": "p1"}],
            "models": [{"model_id": "m1", "provider_id": "p1", "context_limit": 8000}],
        },
        "request": {"task_category": "general"},
    }
    result = _run_scenario_result(scn)
    add("recommendation_only", result.recommendation_only is True)
    add("execution_status_not_executed", result.execution_status == "NOT_EXECUTED")
    add("deterministic_decision_id",
        result.decision_id == _run_scenario_result(scn).decision_id,
        result.decision_id)

    ok = all(c["passed"] for c in checks)
    print(json.dumps({"verified": ok, "checks": checks}, sort_keys=True, indent=2))
    if ok:
        print("LLM STEERING CONTROLLER PACKAGE SELF-CHECK OK", file=sys.stderr)
    return 0 if ok else 1


def _emit(payload: Any, output: Optional[str]) -> None:
    text = json.dumps(payload, sort_keys=True, indent=2)
    if output:
        with open(output, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        _eprint(f"wrote output to {output}")
    else:
        print(text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ugence-llm-steering",
        description="Offline, advisory-only LLM routing recommendation engine "
                    "(recommendation only; no provider request is ever executed).")
    sub = parser.add_subparsers(dest="command", required=True)

    p_inspect = sub.add_parser("inspect", help="print package identity and authority manifest")
    p_inspect.set_defaults(func=_cmd_inspect)

    p_vr = sub.add_parser("validate-registry", help="validate a candidate registry JSON")
    p_vr.add_argument("--input", "-i", required=True, help="registry JSON path or '-'")
    p_vr.set_defaults(func=_cmd_validate_registry)

    p_rec = sub.add_parser("recommend", help="recommend a route from a fixture scenario")
    p_rec.add_argument("--fixture", "-f", required=True, help="scenario JSON path or '-'")
    p_rec.add_argument("--output", "-o", default=None)
    p_rec.set_defaults(func=_cmd_recommend)

    p_exp = sub.add_parser("explain", help="explain a route recommendation from a fixture")
    p_exp.add_argument("--fixture", "-f", required=True, help="scenario JSON path or '-'")
    p_exp.add_argument("--output", "-o", default=None)
    p_exp.set_defaults(func=_cmd_explain)

    p_sim = sub.add_parser("simulate", help="run a fixture suite deterministically")
    p_sim.add_argument("--fixture", "-f", required=True, help="suite JSON path or '-'")
    p_sim.add_argument("--output", "-o", default=None)
    p_sim.set_defaults(func=_cmd_simulate)

    p_verify = sub.add_parser("verify-package", help="offline advisory-invariant self-check")
    p_verify.set_defaults(func=_cmd_verify_package)

    p_ver = sub.add_parser("version", help="print the package version as JSON")
    p_ver.set_defaults(func=_cmd_version)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
