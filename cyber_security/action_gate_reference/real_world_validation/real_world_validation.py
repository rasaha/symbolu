"""Real-world validation harness — drives realistic agent workflows through the REAL
ActionGate gate/token/gateway and records MEASURED outcomes for injected failures.

Evidence, not positioning. Every result below is produced by executing the frozen modules
(action_gate_ref + action_gateway); nothing is asserted that the code does not do. The harness
changes no security logic — it only constructs inputs and records what the real code returns or
raises (error code + detection point + preserved security property).

Detection points:
  DECISION  = gate.evaluate (VALIDATE phase; approvals verified here)
  COMMIT    = token.verify_token / gateway.execute (commit-time revalidation)

Workflows are narratives mapped onto the frozen operation vocabulary (the engine is
domain-free; only operation/policy/facts are data). The mapping is stated per workflow.
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "action_gateway"))   # import action_gateway
sys.path.insert(0, str(HERE.parent))                          # import action_gate_ref

from action_gateway import Gateway                              # noqa: E402
from action_gateway.mapping import ToolRequest                  # noqa: E402
from action_gateway.clock import FixedClock                     # noqa: E402
from action_gate_ref import (evidence as EV, approval as AP, projection, token as TOK,  # noqa: E402
                             policy as POL, gate as GATE)
from action_gate_ref.conformance import ref_envelope            # noqa: E402
from action_gate_ref.errors import GateError                    # noqa: E402

NOW = "2026-07-12T14:00:00.000Z"
LATER = "2026-07-12T14:59:00.000Z"
FUTURE = "2026-07-12T14:50:00.000Z"
APPROVERS = {
    "security-lead": {"id": "security-lead", "key_id": "approver:security-lead"},
    "sre-lead": {"id": "sre-lead", "key_id": "approver:sre-lead"},
    "budget-owner": {"id": "budget-owner", "key_id": "approver:budget-owner"},
}
RESULTS = []


def _code(exc):
    return getattr(exc, "code", type(exc).__name__)


def record(workflow, operation, scenario, kind, phase, detection_point, observed,
           security_property, detected):
    RESULTS.append({"workflow": workflow, "operation": operation, "scenario": scenario,
                    "kind": kind, "phase": phase, "detection_point": detection_point,
                    "observed": observed, "security_property": security_property,
                    "detected": detected})


# --------------------------------------------------------------------------- #
# builders
# --------------------------------------------------------------------------- #
def _gw(clock):
    return Gateway(sandbox_root=tempfile.mkdtemp(prefix="rwv-"), clock=clock)


def ev(ah, kind, *, fidelity="HIGH", is_sim=False, valid_until=FUTURE):
    return EV.build_evidence(bound_to=ah, producer="ci", generated_at=NOW,
                             valid_until=valid_until, evidence_version="1", kind=kind,
                             fidelity_or_confidence=fidelity, is_simulation=is_sim,
                             content={"k": kind, "predicted_changes": [], "affected_resources": []}
                             if is_sim else {"k": kind})


def appr(ah, ph, approver_policy, approvers, *, nonce="ap-1", target=None, operation=None):
    return AP.build_approval(
        action_hash=ah, policy_hash=ph, approver_policy=approver_policy,
        approvers=[APPROVERS[a] for a in approvers],
        approval_scope={"operation": operation, "target": target},
        constraints={}, issued_at="2026-07-12T13:00:00.000Z", expiration="2026-07-12T15:30:00.000Z",
        nonce=nonce)


# --------------------------------------------------------------------------- #
# Workflow 1 — GitHub coding agent (build + deploy from a PR)  ->  DEPLOY
# --------------------------------------------------------------------------- #
def workflow_github():
    W, OP = "github_coding_agent", "DEPLOY"
    gw = _gw(FixedClock(NOW))
    req = ToolRequest(tool="terraform", verb="apply", target=["svc://checkout"],
                      args={"workspace": "prod"}, principal="agent://pr-bot/1",
                      agent_id="agent://pr-bot/1", objective="deploy merged PR #1421")
    s = gw.submit_action(req); rid, ah = s["request_id"], s["action_hash"]
    dec = gw.evaluate_action(rid, evidence=[ev(ah, "signed_artifact"),
                                            ev(ah, "simulation", is_sim=True, fidelity="HIGH")])
    committed = gw.execute_action(rid)
    record(W, OP, "happy_path", "happy", "COMMIT", "COMMIT",
           f"{dec['outcome']} -> {committed['state']}", "authorized commit executed once",
           committed["state"] == "COMPLETED")

    # ATTACK: replay / duplicated execution — re-run the committed token
    gw2 = _gw(FixedClock(NOW)); s2 = gw2.submit_action(req); rid2, ah2 = s2["request_id"], s2["action_hash"]
    gw2.evaluate_action(rid2, evidence=[ev(ah2, "signed_artifact"),
                                        ev(ah2, "simulation", is_sim=True, fidelity="HIGH")])
    gw2.execute_action(rid2)                                   # first commit ok
    try:
        gw2.execute_action(rid2)                              # replay / duplicate
        record(W, OP, "replay_duplicate_execution", "attack", "COMMIT", "none", "ALLOWED", "replay protection", False)
    except GateError as e:
        record(W, OP, "replay_duplicate_execution", "attack", "COMMIT", "COMMIT", _code(e),
               "single-use nonce -> exactly-once", True)

    # ATTACK: target substitution — execute against a different target than approved
    gw3 = _gw(FixedClock(NOW)); s3 = gw3.submit_action(req); rid3, ah3 = s3["request_id"], s3["action_hash"]
    gw3.evaluate_action(rid3, evidence=[ev(ah3, "signed_artifact"),
                                        ev(ah3, "simulation", is_sim=True, fidelity="HIGH")])
    tampered = dict(gw3.records[rid3].envelope); tampered["target_resource"] = ["svc://payments"]
    try:
        gw3.execute_action(rid3, call_envelope=tampered)
        record(W, OP, "target_substitution", "attack", "COMMIT", "none", "ALLOWED", "exact-action binding", False)
    except GateError as e:
        record(W, OP, "target_substitution", "attack", "COMMIT", "COMMIT", _code(e),
               "action_hash rebind rejects retargeting", True)


# --------------------------------------------------------------------------- #
# Workflow 2 — Kubernetes destructive rollout (delete prod StatefulSet)  ->  DB_DELETE
# --------------------------------------------------------------------------- #
def workflow_kubernetes():
    W, OP = "kubernetes_deployment", "DB_DELETE"
    gw = _gw(FixedClock(NOW))
    req = ToolRequest(tool="kubernetes", verb="delete", target=["db://prod/orders"],
                      args={"last_replica": False, "namespace": "prod"},
                      reversibility="REVERSIBLE_WITH_COST", principal="agent://k8s-bot/1",
                      agent_id="agent://k8s-bot/1", objective="roll out: delete old StatefulSet")
    s = gw.submit_action(req); rid, ah = s["request_id"], s["action_hash"]
    ph = gw.signed_policy["policy_hash"]
    ap = appr(ah, ph, "dual_control", ["security-lead", "sre-lead"], nonce="k8s-ap-1",
              target=["db://prod/orders"], operation="DB_DELETE")
    dec = gw.evaluate_action(rid, evidence=[ev(ah, "verified_restorable_backup")], approvals=[ap])
    committed = gw.execute_action(rid)
    record(W, OP, "happy_path", "happy", "COMMIT", "COMMIT",
           f"{dec['outcome']} -> {committed['state']}",
           "destructive delete: backup + dual approval required", committed["state"] == "COMPLETED")

    # ATTACK: approval reuse across a DIFFERENT action (approval bound to another action_hash)
    other = _gw(FixedClock(NOW))
    o = other.submit_action(ToolRequest(tool="kubernetes", verb="delete",
                                        target=["db://prod/OTHER"],
                                        args={"last_replica": False}, reversibility="REVERSIBLE_WITH_COST"))
    stolen_ap = appr(o["action_hash"], ph, "dual_control", ["security-lead", "sre-lead"],
                     nonce="k8s-ap-9", target=["db://prod/OTHER"], operation="DB_DELETE")
    gw_r = _gw(FixedClock(NOW))
    s2 = gw_r.submit_action(req); rid2, ah2 = s2["request_id"], s2["action_hash"]
    dec2 = gw_r.evaluate_action(rid2, evidence=[ev(ah2, "verified_restorable_backup")],
                                approvals=[stolen_ap])         # approval for a different action
    record(W, OP, "approval_reuse_cross_action", "attack", "DECISION", "DECISION",
           dec2["outcome"], "approval binds one action_hash only", dec2["outcome"] == "DENY")

    # ATTACK: stale state at DECISION time (freshness) — old state snapshot
    gw_s = _gw(FixedClock(NOW))
    stale_req = ToolRequest(tool="kubernetes", verb="delete", target=["db://prod/orders"],
                            args={"last_replica": False}, reversibility="REVERSIBLE_WITH_COST",
                            state_as_of="2026-07-12T10:00:00.000Z")   # > freshness bound old
    s3 = gw_s.submit_action(stale_req); rid3, ah3 = s3["request_id"], s3["action_hash"]
    ap3 = appr(ah3, gw_s.signed_policy["policy_hash"], "dual_control", ["security-lead", "sre-lead"],
               nonce="k8s-ap-3", target=["db://prod/orders"], operation="DB_DELETE")
    dec3 = gw_s.evaluate_action(rid3, evidence=[ev(ah3, "verified_restorable_backup")], approvals=[ap3])
    record(W, OP, "stale_state_at_decision", "attack", "DECISION", "DECISION", dec3["outcome"],
           "stale state -> refuse (REQUEST_MORE_EVIDENCE)", dec3["outcome"] == "REQUEST_MORE_EVIDENCE")

    # ATTACK: TOCTOU — state changed between approval and commit
    gw_t = _gw(FixedClock(NOW))
    s4 = gw_t.submit_action(req); rid4, ah4 = s4["request_id"], s4["action_hash"]
    ap4 = appr(ah4, gw_t.signed_policy["policy_hash"], "dual_control", ["security-lead", "sre-lead"],
               nonce="k8s-ap-4", target=["db://prod/orders"], operation="DB_DELETE")
    gw_t.evaluate_action(rid4, evidence=[ev(ah4, "verified_restorable_backup")], approvals=[ap4])
    try:
        gw_t.execute_action(rid4, observed_state_hash="sha256:" + "de" * 32)   # world moved on
        record(W, OP, "toctou_state_drift", "attack", "COMMIT", "none", "ALLOWED", "TOCTOU protection", False)
    except GateError as e:
        record(W, OP, "toctou_state_drift", "attack", "COMMIT", "COMMIT", _code(e),
               "commit-time state binding rejects drift", True)


# --------------------------------------------------------------------------- #
# Workflow 3 — ERP purchase approval (over-threshold spend)  ->  CLOUD_SPEND_INCREASE
# (manual lifecycle over the real modules; this operation has no gateway tool mapping)
# --------------------------------------------------------------------------- #
def _erp_env(*, projected_cost="50000", large_delta=True, principal="agent://erp-bot/1",
             permissions=None, target=("budget://q3-marketing",)):
    e = ref_envelope()
    e["operation"] = "CLOUD_SPEND_INCREASE"
    e["arguments"] = {"self_approved": False, "projected_cost": projected_cost,
                      "large_delta": large_delta}
    e["target_resource"] = list(target)
    e["reversibility"] = "REVERSIBLE"
    e["delegation_chain"] = [{"from": "user://cfo", "to": principal, "grant": "*",
                              "exp": "2026-07-12T18:00:00.000Z"}]
    e["credential_scope"] = {"principal": principal, "permissions": permissions or ["erp:spend"],
                             "ttl": "PT10M"}
    e["state_freshness"] = {"as_of": NOW, "source": "erp"}
    return e


def workflow_erp():
    W, OP = "erp_purchase_approval", "CLOUD_SPEND_INCREASE"
    sp = POL.sign_policy(POL.build_bundle())
    ph = sp["policy_hash"]
    env = _erp_env()
    ah = projection.action_hash(env)
    ap = appr(ah, ph, "budget_owner", ["budget-owner"], nonce="erp-ap-1",
              target=list(env["target_resource"]), operation="CLOUD_SPEND_INCREASE")
    dec = GATE.evaluate(env, sp, evidence=[], approvals=[ap], now=NOW)
    # happy path: mint token, verify at commit
    tok = TOK.build_token(action_hash=ah, permitted_operation="CLOUD_SPEND_INCREASE",
                          permitted_target=env["target_resource"],
                          credential_scope=env["credential_scope"],
                          constraints=dec.get("applied_constraints") or {}, expiration=FUTURE,
                          nonce="erp-tok-1", policy_hash=ph, decision_record_hash="dr-1")
    ok = TOK.verify_token(tok, env, active_policy_hash=ph, now=NOW, require_reeval=True)
    record(W, OP, "happy_path", "happy", "COMMIT", "COMMIT",
           f"{dec['outcome']} -> token_verified={ok}", "over-threshold spend: budget-owner approval",
           dec["outcome"] == "ALLOW" and ok)

    # ATTACK: policy update after approval — token bound to policy P, active policy is P'
    sp2 = POL.sign_policy(POL.build_bundle(version="9.9.9"))    # a different signed policy
    try:
        TOK.verify_token(tok, env, active_policy_hash=sp2["policy_hash"], now=NOW, require_reeval=True)
        record(W, OP, "policy_update_after_approval", "attack", "COMMIT", "none", "ALLOWED",
               "policy-binding", False)
    except GateError as e:
        record(W, OP, "policy_update_after_approval", "attack", "COMMIT", "COMMIT", _code(e),
               "token bound to policy_hash; stale-policy commit rejected", True)

    # ATTACK: privilege downgrade / credential tamper at commit
    tampered = dict(env)
    tampered["credential_scope"] = {**env["credential_scope"], "permissions": ["erp:spend", "iam:admin"]}
    try:
        TOK.verify_token(tok, tampered, active_policy_hash=ph, now=NOW, require_reeval=True)
        record(W, OP, "privilege_tamper_at_commit", "attack", "COMMIT", "none", "ALLOWED",
               "credential binding", False)
    except GateError as e:
        record(W, OP, "privilege_tamper_at_commit", "attack", "COMMIT", "COMMIT", _code(e),
               "credential_scope in action_hash; tamper rejected", True)

    # ATTACK: approval nonce replay (same approval reused after its nonce is spent)
    dec_r = GATE.evaluate(env, sp, evidence=[], approvals=[ap], now=NOW, used_nonces={"erp-ap-1"})
    record(W, OP, "approval_nonce_replay", "attack", "DECISION", "DECISION", dec_r["outcome"],
           "approval nonce single-use", dec_r["outcome"] == "DENY")


# --------------------------------------------------------------------------- #
# Workflow 4 — Database schema migration  ->  DB_MUTATION
# --------------------------------------------------------------------------- #
def workflow_migration():
    W, OP = "database_schema_migration", "DB_MUTATION"
    gw = _gw(FixedClock(NOW))
    req = ToolRequest(tool="filesystem", verb="write", target=["db://prod/orders"],
                      args={"unbounded": False, "affected_count": "5000", "content": "ALTER ..."},
                      principal="agent://migrator/1", agent_id="agent://migrator/1",
                      objective="add index, backfill 5000 rows")
    s = gw.submit_action(req); rid, ah = s["request_id"], s["action_hash"]
    dec = gw.evaluate_action(rid, evidence=[ev(ah, "simulation", is_sim=True, fidelity="MEDIUM")])
    committed = gw.execute_action(rid)
    record(W, OP, "happy_path", "happy", "COMMIT", "COMMIT",
           f"{dec['outcome']} -> {committed['state']}", "bounded migration: simulation required",
           committed["state"] == "COMPLETED")

    # DECISION guard: over-scope migration is ESCALATED, not auto-run
    gw2 = _gw(FixedClock(NOW))
    big = ToolRequest(tool="filesystem", verb="write", target=["db://prod/orders"],
                      args={"unbounded": False, "affected_count": "25000", "content": "ALTER ..."})
    s2 = gw2.submit_action(big); rid2, ah2 = s2["request_id"], s2["action_hash"]
    dec2 = gw2.evaluate_action(rid2, evidence=[ev(ah2, "simulation", is_sim=True, fidelity="MEDIUM")])
    record(W, OP, "over_scope_blast_radius", "attack", "DECISION", "DECISION", dec2["outcome"],
           "MAX_SCOPE blast-radius guard escalates", dec2["outcome"] == "ESCALATE_TO_HUMAN")

    # ATTACK: argument expansion at commit (widen affected_count after approval)
    gw3 = _gw(FixedClock(NOW))
    s3 = gw3.submit_action(req); rid3, ah3 = s3["request_id"], s3["action_hash"]
    gw3.evaluate_action(rid3, evidence=[ev(ah3, "simulation", is_sim=True, fidelity="MEDIUM")])
    tampered = dict(gw3.records[rid3].envelope)
    tampered["arguments"] = {**tampered["arguments"], "affected_count": "999999"}
    try:
        gw3.execute_action(rid3, call_envelope=tampered)
        record(W, OP, "argument_expansion_at_commit", "attack", "COMMIT", "none", "ALLOWED",
               "no post-approval argument tamper", False)
    except GateError as e:
        record(W, OP, "argument_expansion_at_commit", "attack", "COMMIT", "COMMIT", _code(e),
               "arguments in action_hash; expansion rejected", True)


# --------------------------------------------------------------------------- #
# Workflow 5 — Multi-agent software pipeline (build agent -> migrate agent)
# --------------------------------------------------------------------------- #
def workflow_multiagent():
    W = "multi_agent_pipeline"
    gw = _gw(FixedClock(NOW))
    # Agent A: build+deploy (DEPLOY)
    a = ToolRequest(tool="terraform", verb="apply", target=["svc://api"], args={"workspace": "prod"},
                    principal="agent://build/1", agent_id="agent://build/1",
                    correlation_id="pipe-42", sequence_id="pipe-42:0001", objective="stage build")
    sa = gw.submit_action(a); rida, aha = sa["request_id"], sa["action_hash"]
    gw.evaluate_action(rida, evidence=[ev(aha, "signed_artifact"),
                                       ev(aha, "simulation", is_sim=True, fidelity="HIGH")])
    ca = gw.execute_action(rida)
    # Agent B: schema migration (DB_MUTATION), same correlation_id, next in sequence
    b = ToolRequest(tool="filesystem", verb="write", target=["db://prod/api"],
                    args={"unbounded": False, "affected_count": "800", "content": "ALTER ..."},
                    principal="agent://migrate/1", agent_id="agent://migrate/1",
                    correlation_id="pipe-42", sequence_id="pipe-42:0002", objective="apply migration")
    sb = gw.submit_action(b); ridb, ahb = sb["request_id"], sb["action_hash"]
    gw.evaluate_action(ridb, evidence=[ev(ahb, "simulation", is_sim=True, fidelity="MEDIUM")])
    cb = gw.execute_action(ridb)
    record(W, "DEPLOY+DB_MUTATION", "happy_pipeline", "happy", "COMMIT", "COMMIT",
           f"A={ca['state']} B={cb['state']} (corr=pipe-42)",
           "each step independently authorized + audited under one correlation_id",
           ca["state"] == "COMPLETED" and cb["state"] == "COMPLETED")

    # ATTACK: replay agent A's committed action (downstream tries to re-fire the build)
    try:
        gw.execute_action(rida)
        record(W, "DEPLOY", "cross_step_replay", "attack", "COMMIT", "none", "ALLOWED",
               "per-step exactly-once", False)
    except GateError as e:
        record(W, "DEPLOY", "cross_step_replay", "attack", "COMMIT", "COMMIT", _code(e),
               "agent A's action commits exactly once", True)

    # ATTACK: token/action confusion — a FRESH, uncommitted migrate slot is driven with agent
    # A's (build) action envelope; B's token binds B's action_hash, so A's action is rejected
    sc = gw.submit_action(b); ridc, ahc = sc["request_id"], sc["action_hash"]
    gw.evaluate_action(ridc, evidence=[ev(ahc, "simulation", is_sim=True, fidelity="MEDIUM")])
    try:
        gw.execute_action(ridc, call_envelope=gw.records[rida].envelope)   # A's action, B's token
        record(W, "DB_MUTATION", "cross_agent_action_confusion", "attack", "COMMIT", "none",
               "ALLOWED", "per-action binding across agents", False)
    except GateError as e:
        record(W, "DB_MUTATION", "cross_agent_action_confusion", "attack", "COMMIT", "COMMIT",
               _code(e), "B's token binds B's action only (no cross-agent action swap)", True)


def run():
    for fn in (workflow_github, workflow_kubernetes, workflow_erp, workflow_migration,
               workflow_multiagent):
        fn()
    attacks = [r for r in RESULTS if r["kind"] == "attack"]
    happy = [r for r in RESULTS if r["kind"] == "happy"]
    summary = {
        "n_workflows": 5, "n_records": len(RESULTS),
        "n_happy_paths_ok": sum(1 for r in happy if r["detected"]),
        "n_happy_paths": len(happy),
        "n_attacks": len(attacks),
        "n_attacks_detected": sum(1 for r in attacks if r["detected"]),
        "all_attacks_detected": all(r["detected"] for r in attacks),
        "all_happy_paths_ok": all(r["detected"] for r in happy),
    }
    out = {"summary": summary, "records": RESULTS}
    (HERE / "real_world_results.json").write_text(json.dumps(out, indent=2) + "\n")
    return out


if __name__ == "__main__":
    result = run()
    print(json.dumps(result["summary"], indent=2))
    print("\nattack detections:")
    for r in result["records"]:
        if r["kind"] == "attack":
            mark = "OK " if r["detected"] else "!! "
            print(f"  {mark}{r['workflow']:26s} {r['scenario']:34s} @{r['detection_point']:8s} "
                  f"-> {r['observed']}")
