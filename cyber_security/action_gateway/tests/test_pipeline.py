"""End-to-end pipeline: submit -> evaluate -> execute, and runtime states."""

from __future__ import annotations

import pathlib

from action_gateway import ToolRequest
from action_gateway import state as S
from tests.helpers import approved_terraform, make_gateway, sim


def test_full_allow_path_completes():
    gw = make_gateway()
    s = gw.submit_action(ToolRequest(
        tool="filesystem", verb="write", target=["file://d/f.txt"],
        args={"unbounded": False, "affected_count": "1", "content": "hello"}))
    assert gw.status(s["request_id"])["state"] == S.PENDING
    d = gw.evaluate_action(s["request_id"], evidence=[sim(s["action_hash"], gw, "MEDIUM")])
    assert d["outcome"] == "ALLOW_WITH_CONSTRAINTS"
    assert gw.status(s["request_id"])["state"] == S.APPROVED
    r = gw.execute_action(s["request_id"])
    assert r["state"] == S.COMPLETED
    # side effect actually happened in the sandbox
    assert pathlib.Path(r["result"]["path"]).read_text() == "hello"


def test_pipeline_stages_are_audited():
    gw = make_gateway()
    s = approved_terraform(gw)
    before = len(gw.chain.records)
    gw.execute_action(s["request_id"])
    after = len(gw.chain.records)
    # execution adds an EXECUTED record and an EXECUTION_RESULT record
    decisions = [r["payload"]["decision"] for r in gw.chain.records]
    assert "EXECUTED" in decisions
    assert after > before
    assert gw.verify_audit()["intact"]


def test_action_hash_is_stable_for_same_request():
    gw = make_gateway()
    req = ToolRequest(tool="terraform", verb="apply", target=["svc://x"], args={})
    h1 = gw.submit_action(req)["action_hash"]
    h2 = gw.submit_action(req)["action_hash"]
    assert h1 == h2  # action_id/timestamp excluded from the hash


def test_status_reports_operation_and_token():
    gw = make_gateway()
    s = approved_terraform(gw)
    st = gw.status(s["request_id"])
    assert st["operation"] == "DEPLOY" and st["has_token"] is True
