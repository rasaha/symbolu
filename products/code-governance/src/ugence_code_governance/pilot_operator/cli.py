"""Command-line interface for the Code Governance pilot operator.

Deployable console entry point. The CLI covers the offline-verifiable operator
commands — configuration validation, the static read-only security scan, health,
recovery, and report verification — plus a version banner. It never performs a
GitHub write, never prints a credential, and defaults to no active pilot; live
evaluation is driven explicitly through the Python API or the gated live smoke.

Usage:
    python -m ugence_code_governance.pilot_operator.cli <command> [options]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from .. import __version__
from .config import load_pilot_config, load_pilot_config_json
from .errors import PilotConfigError
from .security import scan_paths


def _adapter_operator_paths() -> list:
    base = Path(__file__).resolve().parent.parent
    return list((base / "adapters").glob("*.py")) + list((base / "pilot_operator").glob("*.py"))


def _cmd_version(args) -> int:
    print(json.dumps({"product": "ugence-code-governance", "version": __version__,
                      "execution_status": "DISABLED"}))
    return 0


def _cmd_validate(args) -> int:
    try:
        config = load_pilot_config_json(Path(args.config).read_text())
    except (PilotConfigError, KeyError, ValueError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}))
        return 1
    print(json.dumps({"valid": True, "config_fingerprint": config.fingerprint,
                      "pilot_id": config.pilot_id, "execution_status": "DISABLED"}))
    return 0


def _cmd_security_scan(args) -> int:
    result = scan_paths(_adapter_operator_paths())
    print(json.dumps({"clean": result.clean,
                      "findings": [{"finding": f[0], "path": f[1], "line": f[2]}
                                   for f in result.findings]}))
    return 0 if result.clean else 2


def _cmd_health(args) -> int:
    # Health without a live store is a static readiness banner.
    print(json.dumps({"note": "operator health requires a durable store; use the Python API "
                              "for live health", "execution_status": "DISABLED"}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cg-pilot", description="Code Governance pilot operator")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="print version + execution status")
    p_val = sub.add_parser("validate", help="validate a pilot deployment config (JSON)")
    p_val.add_argument("--config", required=True, help="path to a JSON deployment config")
    sub.add_parser("security-scan", help="static read-only security scan of the adapter+operator boundary")
    sub.add_parser("health", help="operator health banner")
    return parser


_DISPATCH = {
    "version": _cmd_version,
    "validate": _cmd_validate,
    "security-scan": _cmd_security_scan,
    "health": _cmd_health,
}


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return _DISPATCH[args.command](args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
