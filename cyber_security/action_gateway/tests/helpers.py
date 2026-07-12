"""Shared builders for gateway integration tests."""

from __future__ import annotations

import tempfile

from action_gateway import Gateway, FixedClock, ToolRequest
from action_gateway._ref import approval as AP
from action_gateway._ref import evidence as EV

START = "2026-07-12T14:00:00.000Z"
VALID_UNTIL = "2026-07-12T14:20:00.000Z"


def make_gateway(**kw):
    return Gateway(sandbox_root=tempfile.mkdtemp(prefix="gw-test-"),
                   clock=FixedClock(START), **kw)


def sim(ah, gw, fidelity="HIGH"):
    return EV.build_evidence(bound_to=ah, producer="sim", generated_at=gw.clock.now(),
                             valid_until=VALID_UNTIL, evidence_version="1",
                             kind="simulation", fidelity_or_confidence=fidelity,
                             is_simulation=True,
                             content={"coverage": "0.9", "predicted_changes": []})


def artifact(ah, gw):
    return EV.build_evidence(bound_to=ah, producer="registry", generated_at=gw.clock.now(),
                             valid_until=VALID_UNTIL, evidence_version="1",
                             kind="signed_artifact", fidelity_or_confidence="HIGH",
                             content={"artifact": "sha256:abc", "signed": "yes"})


def backup(ah, gw):
    return EV.build_evidence(bound_to=ah, producer="restore-checker", generated_at=gw.clock.now(),
                             valid_until=VALID_UNTIL, evidence_version="1",
                             kind="verified_restorable_backup", fidelity_or_confidence="HIGH",
                             content={"backup_id": "b1", "restore_tested": True})


def approved_write(gw):
    """Submit + approve a safe filesystem write; return the submit result."""
    s = gw.submit_action(ToolRequest(
        tool="filesystem", verb="write", target=["file://out/x.txt"],
        args={"unbounded": False, "affected_count": "1", "content": "payload"}))
    gw.evaluate_action(s["request_id"], evidence=[sim(s["action_hash"], gw, "MEDIUM")])
    return s


def approved_terraform(gw):
    s = gw.submit_action(ToolRequest(tool="terraform", verb="apply",
                                     target=["svc://billing"], args={}))
    gw.evaluate_action(s["request_id"], evidence=[artifact(s["action_hash"], gw)])
    gw.evaluate_action(s["request_id"], evidence=[sim(s["action_hash"], gw, "HIGH")])
    return s
