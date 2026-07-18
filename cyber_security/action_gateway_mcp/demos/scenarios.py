"""Fifteen end-to-end MCP enforcement demonstrations.

Each scenario drives the MCP gateway through the protocol boundary and asserts
the enforcement outcome. Shared by ``run_demos.py`` and the integration tests.
All side effects are mocked (the filesystem adapter alone writes, to a sandbox).
"""

from __future__ import annotations

import copy
import pathlib
import sys
import tempfile
import threading

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from action_gateway_mcp import ClientSession, McpGateway  # noqa: E402
from action_gateway_mcp._core import FixedClock, ref_evidence  # noqa: E402

START = "2026-07-12T14:00:00.000Z"


def _mcp():
    clk = FixedClock(START)
    mcp = McpGateway(sandbox_root=tempfile.mkdtemp(prefix="mcp-demo-"), clock=clk)
    return mcp, ClientSession(clock=clk)


def _backup(mcp, action_hash):
    return ref_evidence.build_evidence(
        bound_to=action_hash, producer="restore-checker", generated_at=mcp.clock.now(),
        valid_until=mcp.clock.plus(3600), evidence_version="1",
        kind="verified_restorable_backup", fidelity_or_confidence="HIGH",
        content={"backup_id": "b1", "restore_tested": True})


def _res(name, expected, actual, passed, detail, mcp):
    return {"scenario": name, "expected": expected, "actual": actual,
            "passed": bool(passed), "detail": detail,
            "audit_intact": mcp.verify_audit()["intact"]}


# ---------------------------------------------------------------- scenarios

def d01_readonly_kubernetes_get():
    mcp, cs = _mcp()
    r = mcp.read(cs.context(), "kubernetes.get",
                 {"namespace": "prod", "kind": "pod", "name": "web"})
    ok = r["outcome"] == "ALLOW" and r.get("read_only") and r["execution_token"] is None
    return _res("Read-only Kubernetes query", "ALLOW (read-only, no token)",
                f"{r['outcome']} read_only={r.get('read_only')}", ok,
                "discovery phase carries no execution authority", mcp)


def d02_safe_filesystem_write():
    mcp, cs = _mcp()
    p = mcp.prepare(cs.context(), "filesystem.write", {"path": "reports/ok.txt", "content": "safe"})
    e = mcp.evaluate(cs.context(), p["request_id"])
    s = mcp.simulate(cs.context(), p["request_id"])
    x = mcp.execute(cs.context(), p["request_id"])
    ok = (e["outcome"] == "SIMULATE_AND_RETRY" and s["outcome"] == "ALLOW_WITH_CONSTRAINTS"
          and x["outcome"] == "ALLOW_WITH_CONSTRAINTS" and x["state"] == "COMPLETED")
    return _res("Safe filesystem write (constrained)",
                "SIMULATE_AND_RETRY -> ALLOW_WITH_CONSTRAINTS -> COMPLETED",
                f"{e['outcome']} -> {s['outcome']} -> {x['state']}", ok,
                f"constraints {x.get('applied_constraints')}", mcp)


def d03_denied_filesystem_delete():
    mcp, cs = _mcp()
    p = mcp.prepare(cs.context(), "filesystem.delete", {"path": "reports/ok.txt"})
    e = mcp.evaluate(cs.context(), p["request_id"])
    x = mcp.execute(cs.context(), p["request_id"])
    ok = e["outcome"] == "DENY" and x["reason_codes"] == ["E_NO_EXECUTION_TOKEN"]
    return _res("Denied filesystem delete", "DENY, no token",
                f"{e['outcome']}, {x['reason_codes'][0]}", ok,
                "irreversible delete without verified backup -> hard DENY", mcp)


def d04_terraform_apply_requires_simulation():
    mcp, cs = _mcp()
    p = mcp.prepare(cs.context(), "terraform.apply", {"workspace": "billing"})
    e = mcp.evaluate(cs.context(), p["request_id"])
    s = mcp.simulate(cs.context(), p["request_id"])
    x = mcp.execute(cs.context(), p["request_id"])
    ok = (e["outcome"] == "SIMULATE_AND_RETRY" and s["outcome"] == "ALLOW"
          and x["state"] == "COMPLETED")
    return _res("Terraform apply requires simulation",
                "SIMULATE_AND_RETRY -> (bound sim) -> ALLOW -> COMPLETED",
                f"{e['outcome']} -> {s['outcome']} -> {x['state']}", ok,
                "signed artifact auto-supplied; plan bound to action hash", mcp)


def d05_kubernetes_delete_escalates_then_executes():
    mcp, cs = _mcp()
    p = mcp.prepare(cs.context(), "kubernetes.delete",
                    {"namespace": "prod", "kind": "statefulset", "name": "db"})
    e = mcp.evaluate(cs.context(), p["request_id"], evidence=[_backup(mcp, p["action_hash"])])
    ap = mcp.create_test_approval(p["request_id"])
    a = mcp.attach_approval(cs.context(), p["request_id"], ap)
    x = mcp.execute(cs.context(), p["request_id"])
    ok = (e["outcome"] == "ESCALATE_TO_HUMAN" and e.get("escalation_id")
          and a["outcome"] == "ALLOW" and x["state"] == "COMPLETED")
    return _res("Kubernetes delete escalates then executes",
                "ESCALATE -> exact-action approval -> ALLOW -> COMPLETED",
                f"{e['outcome']} -> {a['outcome']} -> {x['state']}", ok,
                f"escalation {e.get('escalation_id')}, approval bound to action hash", mcp)


def d06_iam_self_grant_denied():
    mcp, cs = _mcp()
    p = mcp.prepare(cs.context(), "iam.grant",
                    {"role": "arn:aws:iam::acct:role/admin", "grantee": "agent://sre/1"})
    e = mcp.evaluate(cs.context(), p["request_id"])
    ok = e["outcome"] == "DENY" and "R1" in e["dispositive_rules"]
    return _res("IAM self-grant denied", "DENY (R1 self_grant)",
                f"{e['outcome']} {e['dispositive_rules']}", ok,
                "grantee == requesting principal -> self-grant forbidden", mcp)


def _approved_tf(mcp, cs, ws="pay"):
    p = mcp.prepare(cs.context(), "terraform.apply", {"workspace": ws})
    mcp.evaluate(cs.context(), p["request_id"])
    mcp.simulate(cs.context(), p["request_id"])
    return p


def d07_modified_action_after_approval():
    mcp, cs = _mcp()
    p = _approved_tf(mcp, cs)
    bad = copy.deepcopy(mcp.gateway.records[p["request_id"]].envelope)
    bad["arguments"] = {"changes": "9999"}
    r = mcp._commit(cs.context(), p["request_id"], call_envelope=bad)
    ok = r["reason_codes"] == ["E_ACTION_HASH_MISMATCH"]
    return _res("Modified action after approval", "E_ACTION_HASH_MISMATCH",
                r["reason_codes"][0], ok, "token binds the approved action hash", mcp)


def d08_modified_arguments_after_token():
    mcp, cs = _mcp()
    p = _approved_tf(mcp, cs, "pay-args")
    tampered = copy.deepcopy(mcp.gateway.records[p["request_id"]].envelope)
    tampered["arguments"] = dict(tampered["arguments"], injected="malice")
    r = mcp._commit(cs.context(), p["request_id"], call_envelope=tampered)
    ok = r["reason_codes"] == ["E_ACTION_HASH_MISMATCH"]
    return _res("Modified arguments after token issuance", "E_ACTION_HASH_MISMATCH",
                r["reason_codes"][0], ok, "any argument change breaks the binding", mcp)


def d09_credential_scope_expansion():
    mcp, cs = _mcp()
    p = _approved_tf(mcp, cs, "pay-scope")
    r = mcp._commit(cs.context(), p["request_id"], requested_permissions=["tf:apply", "iam:*"])
    ok = r["reason_codes"] == ["E_CREDENTIAL"]
    return _res("Credential scope expansion", "E_CREDENTIAL (broker refuses widening)",
                r["reason_codes"][0], ok, "capability cannot exceed the token's scope", mcp)


def d10_replayed_execution_token():
    mcp, cs = _mcp()
    p = _approved_tf(mcp, cs, "pay-replay")
    mcp.execute(cs.context(), p["request_id"])
    r = mcp.execute(cs.context(), p["request_id"])
    ok = r["reason_codes"] == ["E_NONCE_REPLAY"]
    return _res("Replayed execution token", "E_NONCE_REPLAY",
                r["reason_codes"][0], ok, "execution-token nonce is single-use", mcp)


def d11_replayed_broker_capability():
    mcp, cs = _mcp()
    p = _approved_tf(mcp, cs, "pay-cap")
    res = mcp.execute(cs.context(), p["request_id"])
    cred = mcp.broker._issued[res["credential_id"]]
    blocked = ""
    try:
        mcp.broker.validate(cred, needed_permission="tf:apply", now=mcp.clock.now())
    except Exception as exc:  # noqa: BLE001
        blocked = getattr(exc, "code", type(exc).__name__)
    ok = blocked == "E_CREDENTIAL"
    return _res("Replayed broker capability", "E_CREDENTIAL (single-use capability)",
                blocked or "not rejected", ok, "a capability cannot be reused", mcp)


def d12_toctou_state_mismatch():
    mcp, cs = _mcp()
    p = _approved_tf(mcp, cs, "pay-toctou")
    mcp.gateway.oracle.bump("terraform", ["tf://pay-toctou"])
    r = mcp.execute(cs.context(), p["request_id"])
    ok = r["reason_codes"] == ["E_STALE_STATE"]
    return _res("TOCTOU state mismatch", "E_STALE_STATE", r["reason_codes"][0], ok,
                "commit-time state differs from approval-time state", mcp)


def d13_direct_adapter_bypass():
    from action_gateway import ToolRequest
    from action_gateway.broker import MockCredentialBroker, ScopedCredential
    mcp, cs = _mcp()
    tool = mcp.gateway.adapters["terraform"]
    forged = ScopedCredential(credential_id="forged", principal="p",
                              permissions=frozenset({"tf:apply"}), token_hash="h",
                              expires_at="2999-01-01T00:00:00.000Z")
    blocked = ""
    try:
        tool.execute(ToolRequest(tool="terraform", verb="apply", target=["t"], args={}),
                     forged, broker=MockCredentialBroker(), now=mcp.clock.now())
    except Exception as exc:  # noqa: BLE001
        blocked = getattr(exc, "code", type(exc).__name__)
    ok = blocked == "E_CREDENTIAL"
    return _res("Direct adapter bypass", "E_CREDENTIAL (forged capability rejected)",
                blocked or "not rejected", ok,
                "adapter validates the capability through the broker", mcp)


def d14_unknown_mcp_tool():
    mcp, cs = _mcp()
    r = mcp.prepare(cs.context(), "shell.exec", {"cmd": "rm -rf /"})
    ok = r["outcome"] == "DENY" and r["reason_codes"] == ["E_MCP_UNKNOWN_TOOL"]
    return _res("Unknown MCP tool", "DENY (fail closed)",
                f"{r['outcome']} {r['reason_codes'][0]}", ok,
                "unregistered tool is never coerced to a safe operation", mcp)


def d15_parallel_duplicate_execution():
    mcp, cs = _mcp()
    p = _approved_tf(mcp, cs, "pay-parallel")
    results = []

    def worker(ctx):
        results.append(mcp.execute(ctx, p["request_id"]))

    ctxs = [cs.context() for _ in range(2)]
    threads = [threading.Thread(target=worker, args=(c,)) for c in ctxs]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    commits = [r for r in results if r.get("state") == "COMPLETED"]
    replays = [r for r in results if r.get("reason_codes") == ["E_NONCE_REPLAY"]]
    ok = len(commits) == 1 and len(replays) == 1
    return _res("Parallel duplicate execution", "exactly one commit, one replay-reject",
                f"{len(commits)} commit / {len(replays)} rejected", ok,
                "token nonce reserved atomically under lock", mcp)


ALL_SCENARIOS = [
    d01_readonly_kubernetes_get, d02_safe_filesystem_write, d03_denied_filesystem_delete,
    d04_terraform_apply_requires_simulation, d05_kubernetes_delete_escalates_then_executes,
    d06_iam_self_grant_denied, d07_modified_action_after_approval,
    d08_modified_arguments_after_token, d09_credential_scope_expansion,
    d10_replayed_execution_token, d11_replayed_broker_capability, d12_toctou_state_mismatch,
    d13_direct_adapter_bypass, d14_unknown_mcp_tool, d15_parallel_duplicate_execution,
]


def run_all() -> list:
    return [fn() for fn in ALL_SCENARIOS]
