"""Nine end-to-end enforcement demonstrations.

Each scenario spins up a fresh gateway (deterministic ``FixedClock``), drives a
full submit -> evaluate -> execute flow, and reports what the gateway did versus
what enforcement requires. Shared by ``run_demos.py`` (human-readable output) and
the integration tests (assertions), so the demos are themselves tested.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from action_gateway import Gateway, ToolRequest, FixedClock  # noqa: E402
from action_gateway._ref import approval as AP  # noqa: E402
from action_gateway._ref import errors as E  # noqa: E402
from action_gateway._ref import evidence as EV  # noqa: E402

START = "2026-07-12T14:00:00.000Z"
VALID_UNTIL = "2026-07-12T14:20:00.000Z"


def _gw():
    return Gateway(sandbox_root=tempfile.mkdtemp(prefix="gw-demo-"),
                   clock=FixedClock(START))


def _sim(ah, clk, fidelity="HIGH"):
    return EV.build_evidence(bound_to=ah, producer="sim", generated_at=clk.now(),
                             valid_until=VALID_UNTIL, evidence_version="1",
                             kind="simulation", fidelity_or_confidence=fidelity,
                             is_simulation=True,
                             content={"coverage": "0.9", "predicted_changes": []})


def _artifact(ah, clk):
    return EV.build_evidence(bound_to=ah, producer="registry", generated_at=clk.now(),
                             valid_until=VALID_UNTIL, evidence_version="1",
                             kind="signed_artifact", fidelity_or_confidence="HIGH",
                             content={"artifact": "sha256:abc", "signed": "yes"})


def _backup(ah, clk):
    return EV.build_evidence(bound_to=ah, producer="restore-checker", generated_at=clk.now(),
                             valid_until=VALID_UNTIL, evidence_version="1",
                             kind="verified_restorable_backup", fidelity_or_confidence="HIGH",
                             content={"backup_id": "b1", "restore_tested": True})


def _dual_approval(gw, ah, operation, target, *, expiration):
    return AP.build_approval(
        action_hash=ah, policy_hash=gw.signed_policy["policy_hash"],
        approver_policy="dual_control",
        approvers=[{"id": "security-lead", "key_id": "approver:security-lead"},
                   {"id": "sre-lead", "key_id": "approver:sre-lead"}],
        approval_scope={"operation": operation, "target": target},
        constraints={}, issued_at="2026-07-12T13:00:00.000Z",
        expiration=expiration, nonce="ap-demo")


def _result(name, expected, actual, passed, detail, gw):
    return {"scenario": name, "expected": expected, "actual": actual,
            "passed": bool(passed), "detail": detail,
            "audit_intact": gw.verify_audit()["intact"],
            "audit_len": len(gw.chain.records)}


# --------------------------------------------------------------------- scenarios

def s01_safe_filesystem_write():
    gw = _gw(); clk = gw.clock
    s = gw.submit_action(ToolRequest(
        tool="filesystem", verb="write", target=["file://reports/ok.txt"],
        args={"unbounded": False, "affected_count": "1", "content": "safe payload"}))
    d = gw.evaluate_action(s["request_id"], evidence=[_sim(s["action_hash"], clk, "MEDIUM")])
    r = gw.execute_action(s["request_id"])
    passed = d["outcome"] == "ALLOW_WITH_CONSTRAINTS" and r["state"] == "COMPLETED"
    return _result("Safe filesystem write", "ALLOW_WITH_CONSTRAINTS -> COMPLETED",
                   f"{d['outcome']} -> {r['state']}", passed,
                   f"wrote {r['result']['bytes_written']} bytes", gw)


def s02_denied_filesystem_delete():
    gw = _gw()
    s = gw.submit_action(ToolRequest(
        tool="filesystem", verb="delete", target=["file://reports/ok.txt"],
        args={"last_replica": False}))
    d = gw.evaluate_action(s["request_id"])
    blocked = ""
    try:
        gw.execute_action(s["request_id"])
    except E.GateError as x:
        blocked = x.code
    except Exception as x:  # gateway error
        blocked = getattr(x, "code", type(x).__name__)
    passed = d["outcome"] == "DENY" and blocked == "E_NO_EXECUTION_TOKEN"
    return _result("Denied filesystem delete", "DENY, no token to execute",
                   f"{d['outcome']}, {blocked}", passed,
                   "DB_DELETE missing verified backup -> hard DENY", gw)


def s03_terraform_apply_requires_simulation():
    gw = _gw(); clk = gw.clock
    s = gw.submit_action(ToolRequest(tool="terraform", verb="apply",
                                     target=["svc://billing"], args={}))
    d1 = gw.evaluate_action(s["request_id"], evidence=[_artifact(s["action_hash"], clk)])
    d2 = gw.evaluate_action(s["request_id"], evidence=[_sim(s["action_hash"], clk, "HIGH")])
    r = gw.execute_action(s["request_id"])
    passed = (d1["outcome"] == "SIMULATE_AND_RETRY" and d2["outcome"] == "ALLOW"
              and r["state"] == "COMPLETED")
    return _result("Terraform apply requiring simulation",
                   "SIMULATE_AND_RETRY -> (add sim) -> ALLOW -> COMPLETED",
                   f"{d1['outcome']} -> {d2['outcome']} -> {r['state']}", passed,
                   "high-fidelity simulation supplied on retry", gw)


def s04_kubernetes_delete_escalates():
    gw = _gw(); clk = gw.clock
    s = gw.submit_action(ToolRequest(
        tool="kubernetes", verb="delete", target=["k8s://prod/statefulset/db"],
        args={"last_replica": False}, reversibility="REVERSIBLE_WITH_COST"))
    d = gw.evaluate_action(s["request_id"], evidence=[_backup(s["action_hash"], clk)])
    blocked = ""
    try:
        gw.execute_action(s["request_id"])
    except Exception as x:
        blocked = getattr(x, "code", type(x).__name__)
    passed = d["outcome"] == "ESCALATE_TO_HUMAN" and blocked == "E_NO_EXECUTION_TOKEN"
    return _result("Kubernetes delete requiring escalation",
                   "ESCALATE_TO_HUMAN, no token", f"{d['outcome']}, {blocked}", passed,
                   "destructive delete without dual-control approval -> escalate", gw)


def s05_expired_approval_denied():
    gw = _gw(); clk = gw.clock
    s = gw.submit_action(ToolRequest(
        tool="kubernetes", verb="delete", target=["k8s://prod/statefulset/db"],
        args={"last_replica": False}, reversibility="REVERSIBLE_WITH_COST"))
    ah = s["action_hash"]
    expired = _dual_approval(gw, ah, "DB_DELETE", ["k8s://prod/statefulset/db"],
                             expiration="2026-07-12T13:30:00.000Z")  # already past at 14:00
    d = gw.evaluate_action(s["request_id"], evidence=[_backup(ah, clk)], approvals=[expired])
    passed = d["outcome"] == "DENY" and d["state"] == "DENIED"
    return _result("Expired approval", "DENY (present-but-invalid approval)",
                   f"{d['outcome']} / {d['state']}", passed,
                   "expired approval treated as invalid, fail-closed", gw)


def _approved_terraform(gw):
    clk = gw.clock
    s = gw.submit_action(ToolRequest(tool="terraform", verb="apply",
                                     target=["svc://billing"], args={}))
    gw.evaluate_action(s["request_id"], evidence=[_artifact(s["action_hash"], clk)])
    gw.evaluate_action(s["request_id"], evidence=[_sim(s["action_hash"], clk, "HIGH")])
    return s


def s06_replay_rejected():
    gw = _gw()
    s = _approved_terraform(gw)
    gw.execute_action(s["request_id"])  # first, succeeds
    blocked = ""
    try:
        gw.execute_action(s["request_id"])  # replay same token
    except E.GateError as x:
        blocked = x.code
    passed = blocked == "E_NONCE_REPLAY"
    return _result("Replay attempt", "E_NONCE_REPLAY on second execution",
                   blocked or "not rejected", passed,
                   "execution-token nonce is single-use", gw)


def s07_modified_action_rejected():
    import copy
    gw = _gw()
    s = _approved_terraform(gw)
    tampered = copy.deepcopy(gw.records[s["request_id"]].envelope)
    tampered["arguments"] = {"changes": "9999", "malicious": "true"}
    blocked = ""
    try:
        gw.execute_action(s["request_id"], call_envelope=tampered)
    except E.GateError as x:
        blocked = x.code
    passed = blocked == "E_ACTION_HASH_MISMATCH"
    return _result("Modified action after approval",
                   "E_ACTION_HASH_MISMATCH", blocked or "not rejected", passed,
                   "token binds the approved action hash", gw)


def s08_credential_scope_expansion_rejected():
    gw = _gw()
    s = _approved_terraform(gw)
    blocked = ""
    try:
        gw.execute_action(s["request_id"], requested_permissions=["tf:apply", "iam:*"])
    except Exception as x:
        blocked = getattr(x, "code", type(x).__name__)
    passed = blocked == "E_CREDENTIAL"
    return _result("Credential scope expansion",
                   "E_CREDENTIAL (broker refuses widening)", blocked or "not rejected",
                   passed, "adapter cannot obtain broader scope than the token", gw)


def s09_toctou_state_mismatch_rejected():
    gw = _gw()
    s = _approved_terraform(gw)
    gw.oracle.bump("terraform", ["svc://billing"])  # world changed after approval
    blocked = ""
    try:
        gw.execute_action(s["request_id"])
    except E.GateError as x:
        blocked = x.code
    passed = blocked == "E_STALE_STATE"
    return _result("TOCTOU state mismatch", "E_STALE_STATE", blocked or "not rejected",
                   passed, "commit-time state differs from approval-time state", gw)


ALL_SCENARIOS = [
    s01_safe_filesystem_write,
    s02_denied_filesystem_delete,
    s03_terraform_apply_requires_simulation,
    s04_kubernetes_delete_escalates,
    s05_expired_approval_denied,
    s06_replay_rejected,
    s07_modified_action_rejected,
    s08_credential_scope_expansion_rejected,
    s09_toctou_state_mismatch_rejected,
]


def run_all() -> list:
    return [fn() for fn in ALL_SCENARIOS]
