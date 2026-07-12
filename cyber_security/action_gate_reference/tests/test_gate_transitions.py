"""Ten operation-class transitions through the deterministic gate (spec §5/§6).

Each F* asserts that a fully-satisfied ("happy path") action for one operation
class reaches its expected non-DENY terminal state, and walks the state trace.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from action_gate_ref import gate
from tests import helpers as H

OPS = list(H._HAPPY.keys())
_FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "transitions.json"


@pytest.mark.parametrize("op", OPS)
def test_happy_path_terminal(op):
    sp = H.signed_policy()
    e, ev, aps, expected = H.happy(op)
    d = gate.evaluate(e, sp, evidence=ev, approvals=aps, now=H.NOW)
    assert d["outcome"] == expected, (op, d["dispositive_rules"], d["reason"])
    assert d["terminal"] == "COMMITTED"
    assert d["action_hash"] is not None


@pytest.mark.parametrize("op", OPS)
def test_state_trace_ordered(op):
    sp = H.signed_policy()
    e, ev, aps, _ = H.happy(op)
    d = gate.evaluate(e, sp, evidence=ev, approvals=aps, now=H.NOW)
    tr = d["state_trace"]
    # canonical progression from RECEIVED to a terminal state
    assert tr[0] == "RECEIVED"
    assert "VALIDATED" in tr and "INVARIANT_CHECK" in tr and "FINAL_DECISION" in tr
    assert tr.index("VALIDATED") < tr.index("INVARIANT_CHECK") < tr.index("FINAL_DECISION")
    assert tr[-1] == d["terminal"]


def test_constrained_allows_carry_constraints():
    sp = H.signed_policy()
    for op in ("SECRET_READ", "MONITORING_DISABLE", "DB_MUTATION", "EXTERNAL_COMMS"):
        e, ev, aps, _ = H.happy(op)
        d = gate.evaluate(e, sp, evidence=ev, approvals=aps, now=H.NOW)
        assert d["outcome"] == "ALLOW_WITH_CONSTRAINTS"
        assert d["applied_constraints"]  # non-empty


# operations whose happy path requires evidence/approval/attestation; stripping
# those inputs must block the action. (NET_EXPOSE/KEY_ROTATE/CLOUD_SPEND_INCREASE
# legitimately allow on safe arguments alone, so they are excluded here.)
_REQUIRES_INPUTS = ["IAM_GRANT_ADMIN", "DEPLOY", "DB_DELETE", "SECRET_READ",
                    "MONITORING_DISABLE", "DB_MUTATION", "EXTERNAL_COMMS"]


@pytest.mark.parametrize("op", _REQUIRES_INPUTS)
def test_missing_requirements_never_allow(op):
    # Strip evidence/approvals/attestation: these must not ALLOW.
    sp = H.signed_policy()
    e, _ev, _aps, _ = H.happy(op)
    d = gate.evaluate(e, sp, now=H.NOW)  # no evidence, no approvals
    assert d["outcome"] not in ("ALLOW", "ALLOW_WITH_CONSTRAINTS"), (op, d["outcome"])


def test_deterministic_repeat():
    sp = H.signed_policy()
    e, ev, aps, _ = H.happy("DB_DELETE")
    d1 = gate.evaluate(e, sp, evidence=ev, approvals=aps, now=H.NOW)
    d2 = gate.evaluate(e, sp, evidence=ev, approvals=aps, now=H.NOW)
    assert d1 == d2


def test_committed_transitions_fixture_matches():
    if not _FIXTURE.exists():
        pytest.skip("transitions fixture not generated yet")
    fx = json.loads(_FIXTURE.read_text())
    sp = H.signed_policy()
    assert fx["policy_hash"] == sp["policy_hash"]
    live = {}
    for op in OPS:
        e, ev, aps, _ = H.happy(op)
        d = gate.evaluate(e, sp, evidence=ev, approvals=aps, now=H.NOW)
        live[op] = (d["outcome"], d["action_hash"], d["applied_constraints"])
    for t in fx["transitions"]:
        lo, lh, lc = live[t["operation"]]
        assert (t["outcome"], t["action_hash"], t["applied_constraints"]) == (lo, lh, lc), \
            t["operation"]
