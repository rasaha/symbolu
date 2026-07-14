"""Local CLI. JSON output for automation; never prints raw secrets.

    python -m action_gate_ref.cli <command> [args]

Commands: validate-envelope, canonicalize, hash-action, verify-approval,
verify-token, verify-audit-chain, decide, run-conformance.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import audit, gate, jcs, policy as policy_mod, projection, remediation, schema
from . import approval as approval_mod
from . import token as token_mod
from .errors import GateError
from .schema import ENVELOPE_NFC_PATHS, ENVELOPE_SET_PATHS

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _load(path: str):
    with open(path, "rb") as fh:
        return jcs.load_strict(fh.read())


def _emit(obj) -> int:
    sys.stdout.write(json.dumps(obj, sort_keys=True) + "\n")
    return 0 if obj.get("ok", True) else 1


def _err(exc: Exception):
    code = getattr(exc, "code", "E_GATE")
    return {"ok": False, "error_code": code, "message": str(exc)}


def cmd_validate_envelope(a):
    try:
        env = _load(a.envelope)
        schema.validate_envelope(env)
        return _emit({"ok": True, "valid": True})
    except (GateError, Exception) as exc:  # noqa: BLE001
        return _emit(_err(exc))


def cmd_canonicalize(a):
    try:
        val = _load(a.json)
        canon = jcs.canonicalize_str(val, ENVELOPE_SET_PATHS, ENVELOPE_NFC_PATHS)
        return _emit({"ok": True, "canonical": canon, "byte_len": len(canon.encode("utf-8"))})
    except Exception as exc:  # noqa: BLE001
        return _emit(_err(exc))


def cmd_hash_action(a):
    try:
        env = _load(a.envelope)
        schema.validate_envelope(env)
        return _emit({
            "ok": True,
            "action_hash_sha256": projection.action_hash(env, algorithm_id="sha-256"),
            "action_hash_sha512_256": projection.action_hash(env, algorithm_id="sha-512-256"),
            "projection_manifest": projection.PROJECTION_MANIFEST,
        })
    except Exception as exc:  # noqa: BLE001
        return _emit(_err(exc))


def cmd_verify_approval(a):
    try:
        ap = _load(a.approval)
        env = _load(a.envelope)
        ok = approval_mod.verify_approval(
            ap, env, active_policy_hash=a.policy_hash, now=a.now)
        return _emit({"ok": True, "valid": ok})
    except Exception as exc:  # noqa: BLE001
        return _emit(_err(exc))


def cmd_verify_token(a):
    try:
        tok = _load(a.token)
        env = _load(a.envelope)
        ok = token_mod.verify_token(
            tok, env, active_policy_hash=a.policy_hash, now=a.now,
            require_reeval=a.require_reeval)
        return _emit({"ok": True, "valid": ok})
    except Exception as exc:  # noqa: BLE001
        return _emit(_err(exc))


def cmd_verify_audit_chain(a):
    try:
        data = _load(a.chain)
        ch = audit.AuditChain(data["chain_id"], algorithm_id=data.get("hash_algorithm_id", "sha-256"))
        for rec in data["records"]:
            ch.append(rec)
        return _emit({"ok": True, "intact": ch.verify(), "head": ch.head(),
                      "records": len(ch.records)})
    except Exception as exc:  # noqa: BLE001
        return _emit(_err(exc))


def cmd_decide(a):
    try:
        env = _load(a.envelope)
        evidence = _load(a.evidence) if a.evidence else []
        approvals = _load(a.approvals) if a.approvals else []
        signed = policy_mod.sign_policy(policy_mod.build_bundle())  # reference default policy
        decision = gate.evaluate(env, signed, evidence=evidence, approvals=approvals, now=a.now)
        mode = (getattr(a, "remediation_mode", "off") or "off").upper().replace("-", "_")
        if mode == remediation.OFF:
            # remediation OFF -> byte-identical to the pre-remediation decision output
            return _emit({"ok": True, **decision})
        # FULL/HUMAN_ONLY/TRUSTED_PLANNER require an explicit, non-production admin flag —
        # a caller-provided mode string alone must never unlock privileged disclosure.
        trusted = bool(getattr(a, "trusted_admin", False))
        rem = remediation.project_remediation(
            decision, env, signed, evidence=evidence, approvals=approvals, now=a.now,
            disclosure_mode=mode, trusted_context=trusted)
        return _emit({"ok": True, **remediation.attach(decision, rem)})
    except Exception as exc:  # noqa: BLE001
        return _emit(_err(exc))


def cmd_run_conformance(a):
    from .conformance import run_conformance
    result = run_conformance()
    return _emit({"ok": result["all_pass"], **result})


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="action_gate_ref")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("validate-envelope"); s.add_argument("envelope"); s.set_defaults(fn=cmd_validate_envelope)
    s = sub.add_parser("canonicalize"); s.add_argument("json"); s.set_defaults(fn=cmd_canonicalize)
    s = sub.add_parser("hash-action"); s.add_argument("envelope"); s.set_defaults(fn=cmd_hash_action)
    s = sub.add_parser("verify-approval")
    s.add_argument("approval"); s.add_argument("envelope"); s.add_argument("--policy-hash", required=True, dest="policy_hash")
    s.add_argument("--now", required=True); s.set_defaults(fn=cmd_verify_approval)
    s = sub.add_parser("verify-token")
    s.add_argument("token"); s.add_argument("envelope"); s.add_argument("--policy-hash", required=True, dest="policy_hash")
    s.add_argument("--now", required=True); s.add_argument("--require-reeval", action="store_true", dest="require_reeval")
    s.set_defaults(fn=cmd_verify_token)
    s = sub.add_parser("verify-audit-chain"); s.add_argument("chain"); s.set_defaults(fn=cmd_verify_audit_chain)
    s = sub.add_parser("decide")
    s.add_argument("envelope"); s.add_argument("--now", required=True)
    s.add_argument("--evidence", default=None); s.add_argument("--approvals", default=None)
    s.add_argument("--remediation-mode", dest="remediation_mode", default="off",
                   choices=["off", "minimal", "standard", "trusted-planner", "human-only", "full"],
                   help="opt-in advisory remediation metadata (default: off = unchanged output)")
    s.add_argument("--trusted-admin", dest="trusted_admin", action="store_true",
                   help="NON-PRODUCTION: unlock privileged disclosure (trusted-planner/human-only/full)")
    s.set_defaults(fn=cmd_decide)
    s = sub.add_parser("run-conformance"); s.set_defaults(fn=cmd_run_conformance)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
