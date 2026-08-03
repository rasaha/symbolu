"""Offline service CLI (§26).

    ugence-governance-studio-api version
    ugence-governance-studio-api validate-scenarios
    ugence-governance-studio-api run-scenario procurement
    ugence-governance-studio-api verify-expected
    ugence-governance-studio-api export-scenario procurement
    ugence-governance-studio-api openapi
    ugence-governance-studio-api serve

Defaults: host 127.0.0.1, port 8000, authentication disabled, no external network
use. ``serve`` never binds to all interfaces unless explicitly configured.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from .scenarios.catalog import ScenarioCatalog
from .services.orchestration import AwcOrchestrationService
from .services.scenario_service import ScenarioService
from .version import version_info


def _service() -> ScenarioService:
    catalog = ScenarioCatalog()
    return ScenarioService(catalog, AwcOrchestrationService())


def _cmd_version(_args) -> int:
    print(json.dumps(version_info(), indent=2, sort_keys=True))
    return 0


def _cmd_validate_scenarios(_args) -> int:
    catalog = ScenarioCatalog()
    result = catalog.readiness()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ready"] else 1


def _cmd_run_scenario(args) -> int:
    svc = _service()
    if args.scenario_id not in ScenarioCatalog().scenario_ids:
        print(f"unknown scenario {args.scenario_id!r}", file=sys.stderr)
        return 2
    pipeline, _ = svc.run(args.scenario_id)
    verification = svc.verify(args.scenario_id, pipeline)
    out = {"scenario_id": args.scenario_id, "plan_state": pipeline.plan.plan_state.value,
           "fingerprints": pipeline.fingerprints(), "verification": verification}
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0 if verification["match"] else 1


def _cmd_verify_expected(_args) -> int:
    svc = _service()
    ok = True
    rows = []
    for sid in ScenarioCatalog().scenario_ids:
        pipeline, _ = svc.run(sid)
        v = svc.verify(sid, pipeline)
        ok = ok and v["match"]
        rows.append({"scenario_id": sid, "plan_state": pipeline.plan.plan_state.value,
                     "match": v["match"]})
    print(json.dumps({"all_match": ok, "scenarios": rows}, indent=2, sort_keys=True))
    return 0 if ok else 1


def _cmd_export_scenario(args) -> int:
    svc = _service()
    if args.scenario_id not in ScenarioCatalog().scenario_ids:
        print(f"unknown scenario {args.scenario_id!r}", file=sys.stderr)
        return 2
    bundle = svc.export_bundle(args.scenario_id)
    print(json.dumps(bundle, indent=2, sort_keys=True))
    return 0


def _cmd_openapi(_args) -> int:
    from .openapi import generate_openapi

    print(json.dumps(generate_openapi(), indent=2, sort_keys=True))
    return 0


def _cmd_serve(args) -> int:
    import uvicorn

    from .app import create_app
    from .settings import ApiSettings

    settings = ApiSettings.from_env(build_commit=None)
    app = create_app(settings)
    uvicorn.run(app, host=args.host, port=args.port, log_level=settings.log_level.lower())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ugence-governance-studio-api",
                                     description="Offline Governance Studio API service CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("version").set_defaults(func=_cmd_version)
    sub.add_parser("validate-scenarios").set_defaults(func=_cmd_validate_scenarios)

    p_run = sub.add_parser("run-scenario")
    p_run.add_argument("scenario_id")
    p_run.set_defaults(func=_cmd_run_scenario)

    sub.add_parser("verify-expected").set_defaults(func=_cmd_verify_expected)

    p_exp = sub.add_parser("export-scenario")
    p_exp.add_argument("scenario_id")
    p_exp.set_defaults(func=_cmd_export_scenario)

    sub.add_parser("openapi").set_defaults(func=_cmd_openapi)

    p_serve = sub.add_parser("serve")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.set_defaults(func=_cmd_serve)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
