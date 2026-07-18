"""R2 corpus + retry-governance simulator — validation & security tests.

Verifies the corpus is grounded (its ground-truth class matches the real gate), the simulator
is deterministic and preserves every security invariant, and the measured verdict is
evidence-based. No ActionGate semantics are exercised beyond gate.evaluate.
"""

from __future__ import annotations

import pathlib
import sys

_REF = pathlib.Path(__file__).resolve().parents[1]
for _p in (str(_REF / "vnext_remediation" / "r2"), str(_REF)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import corpus as C          # noqa: E402
import simulator as SIM     # noqa: E402
import metrics as M         # noqa: E402
from action_gate_ref import gate, remediation as R   # noqa: E402

SCEN = C.build_corpus()
RESULTS = [SIM.simulate(s) for s in SCEN]
METRICS = M.compute(SCEN, RESULTS)


# ---- corpus ----
def test_corpus_size_and_classes():
    assert len(SCEN) >= 150
    present = {s.expected_class for s in SCEN}
    assert present == set(C.CLASSES)                 # all five classes represented


def test_corpus_has_required_case_types():
    tags = {t for s in SCEN for t in s.tags}
    for needed in ("adversarial", "repeated_retry", "oscillation", "conflicting", "opt_in"):
        assert needed in tags, needed


def test_ground_truth_class_matches_real_gate():
    for s in SCEN:
        d = gate.evaluate(s.envelope, s.signed_policy, evidence=s.initial_evidence,
                          approvals=s.initial_approvals, now=C.NOW)
        rem = R.project_remediation(d, s.envelope, s.signed_policy, evidence=s.initial_evidence,
                                    approvals=s.initial_approvals, now=C.NOW,
                                    disclosure_mode="FULL", trusted_context=True)
        if d["outcome"].startswith("ALLOW"):
            got = "ALLOW"
        else:
            rc = rem["required_changes"][0]["retry_class"] if rem["required_changes"] else None
            got = C.retry_to_class(rc)
        assert got == s.expected_class, (s.scenario_id, got)


# ---- simulator determinism + security ----
def test_simulator_is_deterministic():
    for s in SCEN[:40]:
        a, b = SIM.simulate(s), SIM.simulate(s)
        assert a.status == b.status
        assert [x["action_hash"] for x in a.trajectory] == [x["action_hash"] for x in b.trajectory]


def test_no_retry_bypasses_deny():
    # every scenario that ever sees DENY ends TERMINAL and never reaches ALLOW
    for s, r in zip(SCEN, RESULTS):
        if r.saw_deny:
            assert r.status == SIM.TERMINAL
            assert not any(x["outcome"].startswith("ALLOW") for x in r.trajectory)


def test_terminal_scenarios_never_succeed():
    for s, r in zip(SCEN, RESULTS):
        if s.expected_class == C.TERMINAL:
            assert r.status == SIM.TERMINAL


def test_every_modification_has_fresh_action_hash():
    assert all(r.fresh_hash_on_modification for r in RESULTS)
    assert METRICS["security"]["fresh_hash_on_every_modification"] is True


def test_no_token_ever_minted():
    assert not any(r.minted_token for r in RESULTS)
    assert METRICS["security"]["no_token_minted"] is True


def test_no_success_reached_through_deny():
    assert METRICS["security"]["no_success_reached_through_deny"] is True


def test_stale_approval_does_not_authorize_modified_action():
    # invalid_approval_replay scenarios: an approval bound to a different action stays terminal
    replay = [s for s in SCEN if "invalid_approval_replay" in s.tags]
    assert replay
    for s in replay:
        d = gate.evaluate(s.envelope, s.signed_policy, evidence=s.initial_evidence,
                          approvals=s.initial_approvals, now=C.NOW)
        assert d["outcome"] == "DENY"


# ---- specific remediation-class behaviours ----
def test_optin_scope_succeeds_default_escalates():
    optin = [(s, r) for s, r in zip(SCEN, RESULTS)
             if "opt_in" in s.tags and s.operation == "DB_MUTATION"
             and s.expected_class == C.ACTION_MODIFICATION_REMEDIABLE
             and "conflicting" not in s.tags]
    assert optin and all(r.status == SIM.ALLOW_SUCCESS for _, r in optin)
    default = [(s, r) for s, r in zip(SCEN, RESULTS)
               if "action_modification_denied_by_default" in s.tags]
    assert default and all(r.status == SIM.ESCALATED_HUMAN for _, r in default)


def test_oscillation_detected_for_expiring_evidence():
    osc = [(s, r) for s, r in zip(SCEN, RESULTS) if "oscillation" in s.tags]
    assert osc and all(r.status == SIM.OSCILLATION for _, r in osc)


def test_conflicting_stalls():
    conf = [(s, r) for s, r in zip(SCEN, RESULTS) if "conflicting" in s.tags]
    assert conf and all(r.status in (SIM.STUCK, SIM.EXHAUSTED) for _, r in conf)


def test_simulation_class_always_remediable():
    sim = [(s, r) for s, r in zip(SCEN, RESULTS) if s.expected_class == C.SIMULATION_REMEDIABLE]
    assert sim and all(r.status == SIM.ALLOW_SUCCESS for _, r in sim)


# ---- metrics + verdict ----
def test_metrics_security_and_privacy():
    assert METRICS["policy_leakage_count"] == 0
    assert METRICS["decision_stability_rate"] == 1.0
    sec = METRICS["security"]
    assert sec["no_deny_bypass"] and sec["no_token_minted"] and \
        sec["fresh_hash_on_every_modification"] and sec["no_success_reached_through_deny"]


def test_verdict_is_evidence_based_stop_for_llm_planner():
    v = METRICS["verdict"]
    assert v["planner_automation"] == "STOP"
    assert v["deterministic_remediation"] == "LIMITED_GO"
    assert v["measured_planning_gap_rate"] == 0.0


def test_action_modification_share_and_success_measured():
    am = METRICS["action_modification"]
    assert am["count"] >= 15
    # where remediable at all, deterministic transforms already solve a majority
    assert am["autonomous_success_rate"] > 0.5
