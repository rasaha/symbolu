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


def _cmd_study_validate(args) -> int:
    from ..pilot_study.manifest import PilotStudyManifest, validate_study_manifest
    from ..pilot_study.errors import StudyManifestError
    data = json.loads(Path(args.manifest).read_text())
    try:
        m = PilotStudyManifest(
            manifest_id=data["manifest_id"], manifest_version=data["manifest_version"],
            pilot_id=data["pilot_id"], tenant_id=data["tenant_id"],
            allowed_repositories=tuple(data.get("allowed_repositories", ())),
            allowed_branches=tuple(data.get("allowed_branches", ())),
            pilot_start_date=data.get("pilot_start_date", ""),
            pilot_end_date=data.get("pilot_end_date", ""),
            maximum_evaluations=int(data.get("maximum_evaluations", 0)),
            target_sample_count=int(data.get("target_sample_count", 0)),
            selection_method=data.get("selection_method", ""),
            evaluation_profile_ref=data.get("evaluation_profile_ref", ""),
            policy_version=data.get("policy_version", ""),
            adapter_registry_version=data.get("adapter_registry_version", ""),
            intervention_routing_version=data.get("intervention_routing_version", ""),
            reviewer_role_allowlist=tuple(data.get("reviewer_role_allowlist", ())),
            reviewer_refs=tuple(data.get("reviewer_refs", ())),
            evidence_classes_permitted=tuple(data.get("evidence_classes_permitted", ())),
            minimum_reviewer_feedback_target=int(data.get("minimum_reviewer_feedback_target", 0)),
            reviewer_protocol_ref=data.get("reviewer_protocol_ref", ""))
        validate_study_manifest(m)
    except (StudyManifestError, KeyError, ValueError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}))
        return 1
    print(json.dumps({"valid": True, "manifest_fingerprint": m.manifest_fingerprint,
                      "pilot_id": m.pilot_id, "execution_status": "DISABLED"}))
    return 0


def _cmd_evidence_pack_verify(args) -> int:
    from ..pilot_study.evidence_pack import verify_pilot_evidence_pack
    pack = json.loads(Path(args.pack).read_text())
    v = verify_pilot_evidence_pack(pack)
    print(json.dumps({"ok": v.ok, "issues": list(v.issues)}))
    return 0 if v.ok else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cg-pilot", description="Code Governance pilot operator")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="print version + execution status")
    p_val = sub.add_parser("validate", help="validate a pilot deployment config (JSON)")
    p_val.add_argument("--config", required=True, help="path to a JSON deployment config")
    sub.add_parser("security-scan", help="static read-only security scan of the adapter+operator boundary")
    sub.add_parser("health", help="operator health banner")
    # MVP 1F — study subcommands
    p_sv = sub.add_parser("study-validate", help="validate a pilot study manifest (JSON)")
    p_sv.add_argument("--manifest", required=True, help="path to a JSON study manifest")
    p_ev = sub.add_parser("evidence-pack-verify", help="verify a pilot evidence pack offline (JSON)")
    p_ev.add_argument("--pack", required=True, help="path to a JSON evidence pack")
    return parser


_DISPATCH = {
    "version": _cmd_version,
    "validate": _cmd_validate,
    "security-scan": _cmd_security_scan,
    "health": _cmd_health,
    "study-validate": _cmd_study_validate,
    "evidence-pack-verify": _cmd_evidence_pack_verify,
}


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return _DISPATCH[args.command](args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
