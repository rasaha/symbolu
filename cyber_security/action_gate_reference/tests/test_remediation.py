"""R1 remediation projection — compatibility, correctness, security, robustness.

Proves ActionGate becomes MORE INFORMATIVE without becoming MORE PERMISSIVE: the projection
never changes an outcome, precedence, hash, or binding, and never turns a DENY into
something retryable.
"""

from __future__ import annotations

import copy
import io
import json
import contextlib

import pytest

from action_gate_ref import cli, gate, policy as policy_mod, projection, remediation as RM
from tests import helpers as H

SP = H.signed_policy()
NOW = H.NOW


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _decide(env, ev, ap):
    return gate.evaluate(env, SP, evidence=ev, approvals=ap, now=NOW)


def _project(env, ev, ap, mode="FULL", trusted=True, sp=SP):
    d = gate.evaluate(env, sp, evidence=ev, approvals=ap, now=NOW)
    return d, RM.project_remediation(d, env, sp, evidence=ev, approvals=ap, now=NOW,
                                     disclosure_mode=mode, trusted_context=trusted)


def _custom_policy(rules):
    return policy_mod.sign_policy(policy_mod.build_bundle(rules=rules))


def _disp_change(rem):
    return rem["required_changes"][0] if rem["required_changes"] else None


# --------------------------------------------------------------------------- #
# The 15 required fixtures (grounded in the reference rules R1..R10)
# --------------------------------------------------------------------------- #
def fixtures():
    F = {}

    # 1 missing soft evidence (DEPLOY, no signed_artifact) -> REQUEST_MORE_EVIDENCE
    e = H.env_for("DEPLOY")
    F["01_missing_soft_evidence"] = (e, [], [], SP,
        "REQUEST_MORE_EVIDENCE", RM.EVIDENCE_RETRYABLE, "R_EVIDENCE_REQUIRED", True)

    # 2 missing attestation (IAM_GRANT_ADMIN, dual approval present, no attestation)
    e = H.env_for("IAM_GRANT_ADMIN")
    ap = [H.approval_for(e, SP, approver_policy="dual_control", approvers=H._DUAL)]
    F["02_missing_attestation"] = (e, [], ap, SP,
        "REQUEST_MORE_EVIDENCE", RM.EVIDENCE_RETRYABLE, "R_ATTESTATION_REQUIRED", True)

    # 3 missing simulation (DB_MUTATION, no simulation) -> SIMULATE_AND_RETRY
    e = H.env_for("DB_MUTATION", args={"unbounded": False, "affected_count": "100"})
    F["03_missing_simulation"] = (e, [], [], SP,
        "SIMULATE_AND_RETRY", RM.SIMULATION_RETRYABLE, "R_SIMULATION_REQUIRED", True)

    # 4 missing human approval (SECRET_READ, no approval) -> ESCALATE_TO_HUMAN
    e = H.env_for("SECRET_READ")
    F["04_missing_approval"] = (e, [], [], SP,
        "ESCALATE_TO_HUMAN", RM.HUMAN_ONLY_CLASS, "R_APPROVAL_REQUIRED", True)

    # 5 excessive scope (DB_MUTATION, affected_count 25000 > 10000, sim provided)
    e = H.env_for("DB_MUTATION", args={"unbounded": False, "affected_count": "25000"})
    F["05_excessive_scope"] = (e, [H.ev_sim(e, fidelity="MEDIUM")], [], SP,
        "ESCALATE_TO_HUMAN", RM.HUMAN_ONLY_CLASS, "R_SCOPE_EXCEEDED", True)

    # 6 excessive cost (CLOUD_SPEND_INCREASE, projected_cost > 100000)
    e = H.env_for("CLOUD_SPEND_INCREASE",
                  args={"self_approved": False, "projected_cost": "200000", "large_delta": False})
    F["06_excessive_cost"] = (e, [], [], SP,
        "ESCALATE_TO_HUMAN", RM.HUMAN_ONLY_CLASS, "R_COST_EXCEEDED", True)

    # 7 excessive blast radius (custom policy adds MAX_BLAST_RADIUS to DB_MUTATION)
    rules = copy.deepcopy(policy_mod.DEFAULT_RULES)
    for r in rules:
        if r["id"] == "R7":
            r["effects"] = [{"op": "FORBID", "fact": "unbounded"},
                            {"op": "MAX_BLAST_RADIUS", "value": "500", "fact": "affected_count"},
                            {"op": "ALLOW_WITH_CONSTRAINTS", "constraints": {"in_transaction": True}}]
    spb = _custom_policy(rules)
    e = H.env_for("DB_MUTATION", args={"unbounded": False, "affected_count": "1000"})
    F["07_excessive_blast_radius"] = (e, [], [], spb,
        "ESCALATE_TO_HUMAN", RM.HUMAN_ONLY_CLASS, "R_BLAST_RADIUS_EXCEEDED", True)

    # 8 excessive irreversibility (DB_DELETE IRREVERSIBLE, backup + dual approval present)
    e = H.env_for("DB_DELETE", reversibility="IRREVERSIBLE")
    ap = [H.approval_for(e, SP, approver_policy="dual_control", approvers=H._DUAL)]
    F["08_excessive_irreversibility"] = (e, [H.ev_backup(e)], ap, SP,
        "ESCALATE_TO_HUMAN", RM.HUMAN_ONLY_CLASS, "R_IRREVERSIBILITY_EXCEEDED", True)

    # 9 hard missing precondition (DB_DELETE, no backup) -> DENY terminal
    e = H.env_for("DB_DELETE", reversibility="REVERSIBLE_WITH_COST")
    F["09_hard_missing_precondition"] = (e, [], [], SP,
        "DENY", RM.TERMINAL, "R_HARD_PRECONDITION", False)

    # 10 explicit FORBID (SECRET_READ bulk) -> DENY terminal
    e = H.env_for("SECRET_READ", args={"export": False, "bulk": True, "sink_approved": True})
    F["10_explicit_forbid"] = (e, [], [], SP,
        "DENY", RM.TERMINAL, "R_FORBIDDEN", False)

    # 11 multiple unmet at different severities (DEPLOY: no artifact sev2 + no sim sev3)
    e = H.env_for("DEPLOY")
    F["11_multiple_severities"] = (e, [], [], SP,
        "REQUEST_MORE_EVIDENCE", RM.EVIDENCE_RETRYABLE, "R_EVIDENCE_REQUIRED", True)

    # 12 same action under each disclosure mode (reuse excessive scope)
    e = H.env_for("DB_MUTATION", args={"unbounded": False, "affected_count": "25000"})
    F["12_disclosure_matrix"] = (e, [H.ev_sim(e, fidelity="MEDIUM")], [], SP,
        "ESCALATE_TO_HUMAN", RM.HUMAN_ONLY_CLASS, "R_SCOPE_EXCEEDED", True)

    # 13 hard vs soft MUST_HAVE contrast covered by 01 (soft) and 09 (hard)
    # 14 permitted action, no remediation (happy DEPLOY) -> ALLOW
    e, ev, ap, _ = H.happy("DEPLOY")
    F["14_permitted_no_remediation"] = (e, ev, ap, SP, "ALLOW", None, None, False)

    # 15 denied action, remediation terminal (SECRET_READ bulk) -> DENY
    e = H.env_for("SECRET_READ", args={"export": False, "bulk": True, "sink_approved": True})
    F["15_denied_terminal"] = (e, [], [], SP, "DENY", RM.TERMINAL, "R_FORBIDDEN", False)

    return F


FIX = fixtures()


@pytest.mark.parametrize("name", sorted(FIX))
def test_fixture_outcome_and_classification(name):
    env, ev, ap, sp, exp_outcome, exp_class, exp_code, exp_retryable = FIX[name]
    d = gate.evaluate(env, sp, evidence=ev, approvals=ap, now=NOW)
    assert d["outcome"] == exp_outcome, (name, d["outcome"])
    rem = RM.project_remediation(d, env, sp, evidence=ev, approvals=ap, now=NOW,
                                 disclosure_mode="FULL", trusted_context=True)
    assert rem["retryability"]["retryable"] is exp_retryable, name
    if exp_outcome in ("ALLOW", "ALLOW_WITH_CONSTRAINTS"):
        assert rem["required_changes"] == []
        return
    ch = _disp_change(rem)
    assert ch is not None, name
    assert ch["retry_class"] == exp_class, (name, ch["retry_class"])
    assert ch["requirement_code"] == exp_code, (name, ch["requirement_code"])


# --------------------------------------------------------------------------- #
# compatibility: remediation OFF and no mutation
# --------------------------------------------------------------------------- #
def test_off_returns_decision_unchanged():
    env = H.env_for("DEPLOY")
    d = _decide(env, [], [])
    d_copy = copy.deepcopy(d)
    out = RM.decide_with_remediation(gate, env, SP, evidence=[], approvals=[], now=NOW,
                                     disclosure_mode="OFF")
    assert out == d_copy                         # byte-identical decision
    assert RM.project_remediation(d, env, SP, now=NOW, disclosure_mode="OFF") == {}


def test_projection_does_not_mutate_inputs():
    for name in FIX:
        env, ev, ap, sp, *_ = FIX[name]
        e0, ev0, ap0 = copy.deepcopy(env), copy.deepcopy(ev), copy.deepcopy(ap)
        d = gate.evaluate(env, sp, evidence=ev, approvals=ap, now=NOW)
        d0 = copy.deepcopy(d)
        RM.project_remediation(d, env, sp, evidence=ev, approvals=ap, now=NOW,
                               disclosure_mode="FULL", trusted_context=True)
        assert env == e0 and ev == ev0 and ap == ap0 and d == d0, name


def test_hash_and_binding_invariance():
    env = H.env_for("DB_DELETE", reversibility="REVERSIBLE_WITH_COST")
    ah0 = projection.action_hash(env)
    ph0 = SP["policy_hash"]
    d = gate.evaluate(env, SP, evidence=[], approvals=[], now=NOW)
    RM.project_remediation(d, env, SP, now=NOW, disclosure_mode="FULL", trusted_context=True)
    assert projection.action_hash(env) == ah0        # action hash unchanged
    assert SP["policy_hash"] == ph0                    # policy hash unchanged
    assert d["action_hash"] == ah0                     # decision hash unchanged


# --------------------------------------------------------------------------- #
# determinism
# --------------------------------------------------------------------------- #
def test_deterministic_and_stable_ordering():
    env = H.env_for("DB_DELETE", reversibility="REVERSIBLE_WITH_COST")
    ap = [H.approval_for(env, SP, approver_policy="dual_control", approvers=H._DUAL,
                         nonce="x")]  # valid approver present
    # two unmet: hard MUST_HAVE (sev0) — approver satisfied -> only the hard remains
    d, rem1 = _project(env, [], ap)
    _, rem2 = _project(env, [], ap)
    assert json.dumps(rem1, sort_keys=True) == json.dumps(rem2, sort_keys=True)
    # ordering: severity then rule order — stable across runs
    order = [c["change_id"] for c in rem1["required_changes"]]
    assert order == sorted(set(order), key=order.index)  # no duplicates, stable


def test_no_duplicate_change_ids():
    for name in FIX:
        env, ev, ap, sp, *_ = FIX[name]
        _, rem = _project(env, ev, ap, sp=sp)
        ids = [c["change_id"] for c in rem["required_changes"]]
        assert len(ids) == len(set(ids)), name


def test_no_wallclock_dependence():
    # identical inputs + explicit now -> identical output regardless of when called
    env = H.env_for("DEPLOY")
    d = _decide(env, [], [])
    a = RM.project_remediation(d, env, SP, now=NOW, disclosure_mode="STANDARD")
    b = RM.project_remediation(d, env, SP, now=NOW, disclosure_mode="STANDARD")
    assert a == b


# --------------------------------------------------------------------------- #
# security invariants
# --------------------------------------------------------------------------- #
def test_forbid_and_hard_never_retryable_all_ops():
    # every DENY-producing terminal condition must be TERMINAL / not retryable
    for name in ("09_hard_missing_precondition", "10_explicit_forbid", "15_denied_terminal"):
        env, ev, ap, sp, *_ = FIX[name]
        _, rem = _project(env, ev, ap, sp=sp)
        assert rem["retryability"]["retryable"] is False
        for ch in rem["required_changes"]:
            assert ch["retry_class"] == RM.TERMINAL


def test_policy_metadata_cannot_upgrade_terminal():
    # a FORBID that (maliciously) carries an action-modification opt-in stays TERMINAL
    rules = copy.deepcopy(policy_mod.DEFAULT_RULES)
    for r in rules:
        if r["id"] == "R5":
            for eff in r["effects"]:
                if eff.get("op") == "FORBID" and eff.get("fact") == "bulk":
                    eff["remediation"] = {"retry_class": RM.ACTION_MODIFICATION_RETRYABLE}
    sp = _custom_policy(rules)
    env = H.env_for("SECRET_READ", args={"export": False, "bulk": True, "sink_approved": True})
    _, rem = _project(env, [], [], sp=sp)
    assert rem["retryability"]["retryable"] is False
    assert _disp_change(rem)["retry_class"] == RM.TERMINAL


def test_max_scope_stays_human_only_without_optin():
    env, ev, ap, sp, *_ = FIX["05_excessive_scope"]
    _, rem = _project(env, ev, ap, sp=sp)
    assert _disp_change(rem)["retry_class"] == RM.HUMAN_ONLY_CLASS


def test_max_scope_optin_action_modification():
    rules = copy.deepcopy(policy_mod.DEFAULT_RULES)
    for r in rules:
        if r["id"] == "R7":
            for eff in r["effects"]:
                if eff.get("op") == "MAX_SCOPE":
                    eff["remediation"] = {"retry_class": RM.ACTION_MODIFICATION_RETRYABLE}
    sp = _custom_policy(rules)
    env = H.env_for("DB_MUTATION", args={"unbounded": False, "affected_count": "25000"})
    _, rem = _project(env, [H.ev_sim(env, fidelity="MEDIUM")], [], sp=sp)
    assert _disp_change(rem)["retry_class"] == RM.ACTION_MODIFICATION_RETRYABLE
    assert rem["retryability"]["new_action_hash_required"] is True


def test_minimal_and_standard_hide_exact_thresholds():
    env, ev, ap, sp, *_ = FIX["12_disclosure_matrix"]
    d = gate.evaluate(env, sp, evidence=ev, approvals=ap, now=NOW)
    for mode in ("MINIMAL", "STANDARD"):
        rem = RM.project_remediation(d, env, sp, evidence=ev, approvals=ap, now=NOW,
                                     disclosure_mode=mode)
        blob = json.dumps(rem)
        assert "25000" not in blob and "10000" not in blob, mode
    # FULL (trusted) reveals the numbers
    remf = RM.project_remediation(d, env, sp, evidence=ev, approvals=ap, now=NOW,
                                  disclosure_mode="FULL", trusted_context=True)
    assert "25000" in json.dumps(remf) and "10000" in json.dumps(remf)


def test_untrusted_cannot_request_privileged_modes():
    env = H.env_for("DEPLOY")
    d = _decide(env, [], [])
    for mode in ("TRUSTED_PLANNER", "HUMAN_ONLY", "FULL"):
        with pytest.raises(RM.RemediationDisclosureError):
            RM.project_remediation(d, env, SP, now=NOW, disclosure_mode=mode,
                                   trusted_context=False)


def test_remediation_carries_no_authority_fields():
    # advisory only: never emits anything resembling evidence/approval/token/credential authority
    env, ev, ap, sp, *_ = FIX["04_missing_approval"]
    _, rem = _project(env, ev, ap, sp=sp)
    blob = json.dumps(rem).lower()
    for forbidden in ("signature", "\"sig\"", "approval_hash", "evidence_hash", "token_hash",
                      "private", "key_id"):
        assert forbidden not in blob


def test_minimal_hides_policy_structure():
    env, ev, ap, sp, *_ = FIX["05_excessive_scope"]
    d = gate.evaluate(env, sp, evidence=ev, approvals=ap, now=NOW)
    rem = RM.project_remediation(d, env, sp, evidence=ev, approvals=ap, now=NOW,
                                 disclosure_mode="MINIMAL")
    for ch in rem["required_changes"]:
        assert "field_path" not in ch and "source_rule_id" not in ch and "operator" not in ch
    for u in rem["all_unmet_conditions"]:
        assert "rule_id" not in u and "operator" not in u


def test_all_unmet_full_only():
    # DEPLOY missing artifact(sev2)+sim(sev3): FULL shows both, STANDARD shows dispositive only
    env = H.env_for("DEPLOY")
    d = _decide(env, [], [])
    full = RM.project_remediation(d, env, SP, now=NOW, disclosure_mode="FULL", trusted_context=True)
    std = RM.project_remediation(d, env, SP, now=NOW, disclosure_mode="STANDARD")
    assert len(full["all_unmet_conditions"]) == 2
    assert len(std["all_unmet_conditions"]) == 1
    tiers = {u["current_outcome"] for u in full["all_unmet_conditions"]}
    assert tiers == {"REQUEST_MORE_EVIDENCE", "SIMULATE_AND_RETRY"}


def test_dispositive_rules_and_outcome_unchanged_by_projection():
    for name in FIX:
        env, ev, ap, sp, *_ = FIX[name]
        d1 = gate.evaluate(env, sp, evidence=ev, approvals=ap, now=NOW)
        RM.project_remediation(d1, env, sp, evidence=ev, approvals=ap, now=NOW,
                               disclosure_mode="FULL", trusted_context=True)
        d2 = gate.evaluate(env, sp, evidence=ev, approvals=ap, now=NOW)
        assert d1["outcome"] == d2["outcome"]
        assert d1["dispositive_rules"] == d2["dispositive_rules"]


# --------------------------------------------------------------------------- #
# robustness
# --------------------------------------------------------------------------- #
def test_invalid_mode_rejected():
    env = H.env_for("DEPLOY")
    d = _decide(env, [], [])
    with pytest.raises(RM.RemediationModeError):
        RM.project_remediation(d, env, SP, now=NOW, disclosure_mode="BOGUS")


def test_unknown_operator_classifies_terminal():
    synthetic = {"terminal_key": None, "operator": "TOTALLY_UNKNOWN", "severity": 0,
                 "eff_meta": {}}
    assert RM._retry_class(synthetic) == RM.TERMINAL


def test_unknown_policy_op_does_not_crash_and_is_ignored_like_gate():
    # gate ignores unknown effect ops; projection must too (no divergence, no crash)
    rules = copy.deepcopy(policy_mod.DEFAULT_RULES)
    for r in rules:
        if r["id"] == "R2":
            r["effects"].insert(0, {"op": "BOGUS_OP", "fact": "whatever"})
    sp = _custom_policy(rules)
    env = H.env_for("DEPLOY")
    d = gate.evaluate(env, sp, evidence=[], approvals=[], now=NOW)   # must not raise
    rem = RM.project_remediation(d, env, sp, now=NOW, disclosure_mode="FULL", trusted_context=True)
    assert "BOGUS" not in json.dumps(rem)


def test_serialization_round_trip_and_schema():
    env, ev, ap, sp, *_ = FIX["05_excessive_scope"]
    _, rem = _project(env, ev, ap, sp=sp)
    rt = json.loads(json.dumps(rem, sort_keys=True))
    assert rt == rem
    for key in ("response_schema_version", "all_unmet_conditions", "required_changes",
                "retryability", "disclosure", "retry_budget"):
        assert key in rt
    assert rt["response_schema_version"] == "1.1"
    assert set(rt["retryability"]) == {"retryable", "retry_class", "new_action_hash_required",
                                       "fresh_evaluation_required"}
    assert set(rt["retry_budget"]) == {"max_attempts", "deadline", "compute_budget"}


def test_pre_rule_denies_are_terminal():
    # invalid policy -> DENY; remediation must be terminal, not retryable
    bad = copy.deepcopy(SP)
    bad["signature"] = "sig:root_of_trust:deadbeef"      # break the policy signature
    env = H.env_for("DEPLOY")
    d = gate.evaluate(env, bad, evidence=[], approvals=[], now=NOW)
    assert d["outcome"] == "DENY"
    rem = RM.project_remediation(d, env, bad, now=NOW, disclosure_mode="FULL", trusted_context=True)
    assert rem["retryability"]["retryable"] is False


# --------------------------------------------------------------------------- #
# CLI opt-in
# --------------------------------------------------------------------------- #
def _cli(args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cli.main(args)
    return rc, json.loads(buf.getvalue())


def test_cli_off_matches_plain_decide(tmp_path):
    env = H.env_for("DEPLOY")
    p = tmp_path / "e.json"
    p.write_text(json.dumps(env))
    _, off = _cli(["decide", str(p), "--now", NOW])
    _, off2 = _cli(["decide", str(p), "--now", NOW, "--remediation-mode", "off"])
    assert off == off2
    assert "required_changes" not in off


def test_cli_standard_adds_fields_without_changing_outcome(tmp_path):
    env = H.env_for("DEPLOY")
    p = tmp_path / "e.json"
    p.write_text(json.dumps(env))
    _, off = _cli(["decide", str(p), "--now", NOW])
    _, std = _cli(["decide", str(p), "--now", NOW, "--remediation-mode", "standard"])
    assert std["outcome"] == off["outcome"]
    assert std["dispositive_rules"] == off["dispositive_rules"]
    assert "required_changes" in std and std["response_schema_version"] == "1.1"


def test_cli_full_requires_trusted_admin(tmp_path):
    env = H.env_for("DEPLOY")
    p = tmp_path / "e.json"
    p.write_text(json.dumps(env))
    rc, out = _cli(["decide", str(p), "--now", NOW, "--remediation-mode", "full"])
    assert rc == 1 and out["error_code"] == "E_REMEDIATION_DISCLOSURE"
    rc2, out2 = _cli(["decide", str(p), "--now", NOW, "--remediation-mode", "full",
                      "--trusted-admin"])
    assert rc2 == 0 and "required_changes" in out2
