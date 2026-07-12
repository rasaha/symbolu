"""Audit completeness + tamper evidence."""

from __future__ import annotations

from action_gateway import state as S
from tests.helpers import approved_terraform, make_gateway


def test_chain_intact_after_each_stage():
    gw = make_gateway()
    s = approved_terraform(gw)
    assert gw.verify_audit()["intact"]
    gw.execute_action(s["request_id"])
    assert gw.verify_audit()["intact"]


def test_execution_produces_decision_execution_and_result_records():
    gw = make_gateway()
    s = approved_terraform(gw)
    gw.execute_action(s["request_id"])
    decisions = [r["payload"]["decision"] for r in gw.chain.records]
    # two evaluate decisions (SIMULATE_AND_RETRY, ALLOW) + EXECUTED
    assert "ALLOW" in decisions
    assert "EXECUTED" in decisions
    executed = [r for r in gw.chain.records if r["payload"]["decision"] == "EXECUTED"]
    assert executed and executed[0]["payload"]["execution_token_hash"]
    assert executed[0]["payload"]["execution_result_hash"]


def test_tamper_is_detected_and_localized():
    gw = make_gateway()
    s = approved_terraform(gw)
    gw.execute_action(s["request_id"])
    # tamper with the first record's decision
    gw.chain.records[0]["payload"]["decision"] = "ALLOW"
    v = gw.verify_audit()
    assert v["intact"] is False
    assert v["tamper_index"] == 0


def test_rejected_execution_is_audited():
    gw = make_gateway()
    s = approved_terraform(gw)
    gw.oracle.bump("terraform", ["svc://billing"])
    try:
        gw.execute_action(s["request_id"])
    except Exception:
        pass
    decisions = [r["payload"]["decision"] for r in gw.chain.records]
    assert any(d.startswith("EXECUTION_DENIED") for d in decisions)
    assert gw.verify_audit()["intact"]
