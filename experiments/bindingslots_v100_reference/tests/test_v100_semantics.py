#!/usr/bin/env python3
"""Torch-free tests for V100 semantics, lifecycle/integrity, and mechanical verdict reconstruction.
Standalone (prints a pass count) or pytest. No model inference here."""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))

import v100 as V100                                   # noqa: E402
from v100_table import V100Table, TableUnavailable    # noqa: E402
import integrity as INT                               # noqa: E402
import gates as G                                     # noqa: E402


def _w(t, session="s1", tenant="t1", key="E1", val="V1", ttl=100, scope="eval"):
    t.write_fact(session_id=session, tenant_id=tenant, memory_key=key, fact_or_entity_id=key,
                 typed_value=val, value_type="value_token_id", source_event_id="ev",
                 evidence_reference="ref", authorization_scope=scope, ttl_s=ttl)


def _verify(t, neural, target, session="s1", tenant="t1", key="E1", scope="eval"):
    try:
        rd = t.read_for_verification(session_id=session, tenant_id=tenant, memory_key=key,
                                     authorization_scope=scope)
    except TableUnavailable:
        return V100._abstain("abstained_table_unavailable", neural, reason="table_unavailable")
    return V100.classify(neural_pred=neural, target=target, read=rd)


def test_exactly_one_read_per_v100_query():
    t = V100Table()
    for i in range(25):
        _w(t, session=f"s{i}", key=f"E{i}", val=f"V{i}")
    before = t.ops["reads"]
    for i in range(25):
        _verify(t, neural=f"V{i}", target=f"V{i}", session=f"s{i}", key=f"E{i}")
    assert t.ops["reads"] - before == 25, "V100 must read the table exactly once per query"


def test_valid_agreement_classification():
    t = V100Table(); _w(t)
    d = _verify(t, neural="V1", target="V1")
    assert d["category"] == "verified_agreement_correct" and d["status"] == "verified_agreement"
    assert d["answer"] == "V1" and d["verified"] and not d["corrected"]


def test_valid_correction_classification():
    t = V100Table(); _w(t)
    d = _verify(t, neural="WRONG", target="V1")
    assert d["category"] == "verified_correction_correct" and d["status"] == "verified_correction"
    assert d["answer"] == "V1" and d["corrected"] and d["disagreement"]


def test_incorrect_correction_impossible_under_valid_record():
    # with a correct stored fact, the returned (table) value is always the correct target
    t = V100Table(); _w(t, val="V1")
    d = _verify(t, neural="anything", target="V1")
    assert d["answer"] == d["table_value"] == "V1"
    assert d["category"] != "verified_return_incorrect"


def test_missing_record_abstains():
    t = V100Table()
    d = _verify(t, neural="x", target="V1")
    assert d["category"] == "abstained_missing_record" and d["answer"] is None


def test_stale_expired_deleted_abstain():
    clk = [1000.0]; t = V100Table(clock=lambda: clk[0])
    _w(t, key="EXP", val="v", ttl=10); clk[0] = 1050.0
    assert _verify(t, "x", "v", key="EXP")["category"] == "abstained_invalid_record"
    clk[0] = 1000.0
    _w(t, key="DEL", val="v"); t.delete(session_id="s1", tenant_id="t1", memory_key="DEL")
    assert _verify(t, "x", "v", key="DEL")["category"] == "abstained_invalid_record"


def test_table_unavailable_and_read_failure_fail_closed():
    t = V100Table(); _w(t)
    t.set_available(False)
    assert _verify(t, "V1", "V1")["category"] == "abstained_table_unavailable"
    t.set_available(True)
    t.set_fail_read(True)
    assert _verify(t, "V1", "V1")["category"] == "abstained_table_unavailable"
    t.set_fail_read(False)


def test_write_failure_fails_closed():
    t = V100Table(); t.set_fail_write(True)
    try:
        _w(t, key="WF"); raised = False
    except TableUnavailable:
        raised = True
    t.set_fail_write(False)
    assert raised
    assert _verify(t, "x", "x", key="WF")["answer"] is None


def test_malformed_record_abstains():
    t = V100Table(); _w(t); t.set_malform_provenance(True)
    assert _verify(t, "V1", "V1")["category"] == "abstained_integrity_failure"


def test_version_selection():
    t = V100Table(); _w(t, val="one"); _w(t, val="two")
    d = _verify(t, "two", "two")
    assert d["version"] == 2 and d["table_value"] == "two"


def test_tenant_and_session_isolation():
    t = V100Table(); _w(t, session="s1", tenant="t1", val="V1")
    assert _verify(t, "x", "V1", session="s2", tenant="t1")["answer"] is None
    assert _verify(t, "x", "V1", session="s1", tenant="t2")["answer"] is None


def test_concurrent_sessions():
    t = V100Table()
    for s in ("a", "b", "c"):
        _w(t, session=s, val=f"V_{s}")
    for s in ("a", "b", "c"):
        assert _verify(t, f"V_{s}", f"V_{s}", session=s)["table_value"] == f"V_{s}"


def test_provenance_completeness():
    t = V100Table(); _w(t)
    d = _verify(t, "V1", "V1")
    assert V100.provenance_complete(d["provenance"])


def test_cleanup_zero_residual():
    t = V100Table(); _w(t, session="s1"); _w(t, session="s2", key="E2")
    t.cleanup_session("s1")
    assert t.live_session_rows("s1") == 0
    assert _verify(t, "V1", "V1", session="s1")["answer"] is None


def test_all_integrity_scenarios_pass():
    s = INT.run_scenarios()
    assert s["all_pass"], {k: v for k, v in s.items() if v is False}


def _synthetic_seed(seed, n=120, failures=40):
    """A 100%-coverage seed: `failures` disagreements (all corrected), rest agreements; no incorrect."""
    agree = n - failures
    cats = {c: 0 for c in V100.CATEGORIES}
    cats["verified_agreement_correct"] = agree
    cats["verified_correction_correct"] = failures
    return {
        "seed": seed, "n": n,
        "M0": {"correct": agree, "accuracy": agree / n},
        "T0": {"correct": n, "accuracy": 1.0},
        "F0": {"correct": n, "fallback_invoked": failures, "rescued": failures, "unnecessary": 0,
               "incorrect_fallback": 0, "abstain": 0,
               "confusion": {"tp": failures, "fp": 0, "tn": agree, "fn": 0}},
        "V100": {"returned": n, "returned_correct": n, "verified_correct": n, "incorrect_verified": 0,
                 "disagreements": failures, "corrections": failures, "incorrect_corrections": 0,
                 "abstain": 0, "provenance_complete": n, "reads": n, "reads_equal_n": True,
                 "categories": cats, "accuracy": 1.0, "answer_availability": 1.0, "abstention_rate": 0.0},
    }


def test_mechanical_verdict_reconstruction_pass():
    per_seed = [_synthetic_seed(s) for s in (28, 29, 30, 31, 32)]
    scen = INT.run_scenarios()
    agg = G.aggregate(per_seed)
    g = G.gates(agg, scen, repro_all_match=True, model_unchanged=True, eval_optimizer_steps=0)
    assert g["all_pass"], {k: v for k, v in g.items() if v is False}
    v, extra = G.verdict(agg, g, torch_available=True, reproduced=True)
    assert v == "ALWAYS_VERIFY_RELIABILITY_VERIFIED_OPERATIONAL_COST_UNRESOLVED", v
    assert v != G.FORBIDDEN_VERDICT
    for token in ("KEY_CONSISTENCY_SIGNAL_NOT_AVAILABLE", "BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED",
                  "KDA_VALIDATION_BLOCKED"):
        assert token in extra


def test_mechanical_verdict_reconstruction_reliability_fail():
    per_seed = [_synthetic_seed(s) for s in (28, 29, 30, 31, 32)]
    per_seed[0]["V100"]["incorrect_verified"] = 3     # inject a reliability breach
    scen = INT.run_scenarios()
    agg = G.aggregate(per_seed)
    g = G.gates(agg, scen, repro_all_match=True, model_unchanged=True, eval_optimizer_steps=0)
    assert not g["all_pass"]
    v, _ = G.verdict(agg, g, torch_available=True, reproduced=True)
    assert v in ("ALWAYS_VERIFY_RELIABILITY_GATE_FAILED", "EXTERNAL_VERIFICATION_RESULTS_INCONCLUSIVE"), v
    assert v != "ALWAYS_VERIFY_RELIABILITY_VERIFIED_OPERATIONAL_COST_UNRESOLVED"


def _run_standalone():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"v100-semantics tests: {len(fns)} passed, 0 failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
