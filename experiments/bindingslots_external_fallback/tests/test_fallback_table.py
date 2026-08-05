#!/usr/bin/env python3
"""Torch-free tests for the ephemeral table adapter, lifecycle/isolation scenarios, and the frozen
trigger. Standalone or pytest."""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))
from ephemeral_table import EphemeralTable, TableUnavailable, UnauthorizedLookup  # noqa: E402
from fallback import Trigger  # noqa: E402


class Clock:
    def __init__(self, t=1000.0):
        self.t = t
    def __call__(self):
        return self.t


def _w(tbl, clk, session="s1", tenant="t1", key="ENT1", val="V1", ttl=100, scope="eval"):
    return tbl.write_fact(session_id=session, tenant_id=tenant, memory_key=key, fact_or_entity_id=key,
                          typed_value=val, value_type="value_token_id", source_event_id="e1",
                          evidence_reference="ref1", authorization_scope=scope, ttl_s=ttl)


def test_write_read_round_trip_and_provenance():
    clk = Clock(); t = EphemeralTable(clock=clk)
    _w(t, clk)
    r = t.lookup(session_id="s1", tenant_id="t1", memory_key="ENT1", authorization_scope="eval")
    assert r.found and r.typed_value == "V1"
    assert r.provenance["source_event_id"] == "e1" and r.provenance["evidence_reference"] == "ref1"
    assert r.provenance["fallback_used"] is True


def test_deterministic_lookup():
    clk = Clock(); t = EphemeralTable(clock=clk); _w(t, clk)
    a = t.lookup(session_id="s1", tenant_id="t1", memory_key="ENT1", authorization_scope="eval")
    b = t.lookup(session_id="s1", tenant_id="t1", memory_key="ENT1", authorization_scope="eval")
    assert a.typed_value == b.typed_value == "V1" and a.version == b.version


def test_session_isolation():
    clk = Clock(); t = EphemeralTable(clock=clk); _w(t, clk, session="s1", val="V1")
    r = t.lookup(session_id="s2", tenant_id="t1", memory_key="ENT1", authorization_scope="eval")
    assert not r.found, "cross-session disclosure"


def test_tenant_isolation():
    clk = Clock(); t = EphemeralTable(clock=clk); _w(t, clk, tenant="t1", val="V1")
    r = t.lookup(session_id="s1", tenant_id="t2", memory_key="ENT1", authorization_scope="eval")
    assert not r.found, "cross-tenant disclosure"


def test_ttl_expiry():
    clk = Clock(1000.0); t = EphemeralTable(clock=clk); _w(t, clk, ttl=50)
    clk.t = 1049.0
    assert t.lookup(session_id="s1", tenant_id="t1", memory_key="ENT1", authorization_scope="eval").found
    clk.t = 1051.0
    assert not t.lookup(session_id="s1", tenant_id="t1", memory_key="ENT1", authorization_scope="eval").found


def test_deletion():
    clk = Clock(); t = EphemeralTable(clock=clk); _w(t, clk)
    t.delete(session_id="s1", tenant_id="t1", memory_key="ENT1")
    assert not t.lookup(session_id="s1", tenant_id="t1", memory_key="ENT1", authorization_scope="eval").found


def test_version_handling_and_stale():
    clk = Clock(); t = EphemeralTable(clock=clk)
    v1 = _w(t, clk, val="V1"); v2 = _w(t, clk, val="V2")
    assert v1 == 1 and v2 == 2
    latest = t.lookup(session_id="s1", tenant_id="t1", memory_key="ENT1", authorization_scope="eval")
    assert latest.typed_value == "V2" and latest.version == 2, "latest version must win"
    stale = t.lookup(session_id="s1", tenant_id="t1", memory_key="ENT1", authorization_scope="eval", requested_version=1)
    assert stale.typed_value == "V1"


def test_duplicate_key_increments_version():
    clk = Clock(); t = EphemeralTable(clock=clk)
    assert _w(t, clk) == 1 and _w(t, clk) == 2 and _w(t, clk) == 3


def test_missing_key():
    t = EphemeralTable()
    assert not t.lookup(session_id="s1", tenant_id="t1", memory_key="NOPE", authorization_scope="eval").found


def test_unauthorized_scope():
    clk = Clock(); t = EphemeralTable(clock=clk); _w(t, clk, scope="eval")
    try:
        t.lookup(session_id="s1", tenant_id="t1", memory_key="ENT1", authorization_scope="other")
        assert False, "should raise on scope mismatch"
    except UnauthorizedLookup:
        pass


def test_table_unavailable():
    t = EphemeralTable(available=False)
    try:
        t.lookup(session_id="s1", tenant_id="t1", memory_key="ENT1", authorization_scope="eval")
        assert False
    except TableUnavailable:
        pass


def test_refuses_forbidden_content():
    t = EphemeralTable()
    for bad in ("hidden_state", "slot_tensor", "gradient", "ground_truth", "answer_label"):
        try:
            t.write_fact(session_id="s", tenant_id="t", memory_key="k", fact_or_entity_id="k",
                         typed_value="x", value_type=bad, source_event_id="e", evidence_reference="r",
                         authorization_scope="eval", ttl_s=10)
            assert False, f"should refuse {bad}"
        except ValueError:
            pass


def test_cleanup_after_session():
    clk = Clock(); t = EphemeralTable(clock=clk); _w(t, clk, session="s1"); _w(t, clk, session="s2", key="ENT2")
    t.cleanup_session("s1")
    assert not t.lookup(session_id="s1", tenant_id="t1", memory_key="ENT1", authorization_scope="eval").found
    assert t.lookup(session_id="s2", tenant_id="t1", memory_key="ENT2", authorization_scope="eval").found


def test_concurrent_sessions_no_leakage():
    clk = Clock(); t = EphemeralTable(clock=clk)
    for s in ("sa", "sb", "sc"):
        _w(t, clk, session=s, val=f"V_{s}")
    for s in ("sa", "sb", "sc"):
        r = t.lookup(session_id=s, tenant_id="t1", memory_key="ENT1", authorization_scope="eval")
        assert r.typed_value == f"V_{s}", "session cross-talk"


def test_trigger_determinism_and_formula():
    tr = Trigger(prob_min=0.5, margin_min=0.2, entropy_max=2.0)
    lowp = {"top1_prob": 0.4, "margin": 0.9, "entropy": 0.1}
    lowm = {"top1_prob": 0.9, "margin": 0.1, "entropy": 0.1}
    highe = {"top1_prob": 0.9, "margin": 0.9, "entropy": 3.0}
    conf = {"top1_prob": 0.9, "margin": 0.9, "entropy": 0.1}
    assert tr.fires(lowp) and tr.fires(lowm) and tr.fires(highe) and not tr.fires(conf)
    assert tr.fires(lowp) == tr.fires(lowp)   # deterministic


def _run_standalone():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"fallback-table tests: {len(fns)} passed, 0 failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
