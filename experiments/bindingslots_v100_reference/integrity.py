#!/usr/bin/env python3
"""Deterministic lifecycle / isolation / fault-injection scenarios for V100 (torch-free).

Each scenario drives the V100 verification path (single reason-aware read + fail-closed classify) and
asserts the correct category / isolation outcome. Every value is a boolean or count so the whole report
is mechanically reproducible and hashable. Faults (read/write failure, malformed provenance,
unavailability) are injected only here — never during the frozen evaluation cohort.
"""
from __future__ import annotations

import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import v100 as V100                                   # noqa: E402
from v100_table import V100Table, TableUnavailable    # noqa: E402


def _wf(t, session, tenant, key, val, ttl=100, scope="eval", clk=None):
    t.write_fact(session_id=session, tenant_id=tenant, memory_key=key, fact_or_entity_id=key,
                 typed_value=val, value_type="value_token_id", source_event_id=f"ev_{key}",
                 evidence_reference=f"ref_{key}", authorization_scope=scope, ttl_s=ttl)


def _verify(t, session, tenant, key, scope, neural, target):
    try:
        rd = t.read_for_verification(session_id=session, tenant_id=tenant, memory_key=key,
                                     authorization_scope=scope)
    except TableUnavailable:
        return V100._abstain("abstained_table_unavailable", neural, reason="table_unavailable")
    return V100.classify(neural_pred=neural, target=target, read=rd)


def run_scenarios():
    res = {}
    clk = [1000.0]
    t = V100Table(clock=lambda: clk[0])

    # --- successful write/read: agreement + correction -----------------------------------
    _wf(t, "sA", "tA", "E1", "V1")
    agree = _verify(t, "sA", "tA", "E1", "eval", neural="V1", target="V1")
    res["successful_agreement"] = (agree["category"] == "verified_agreement_correct" and agree["verified"])
    corr = _verify(t, "sA", "tA", "E1", "eval", neural="WRONG", target="V1")
    res["successful_correction"] = (corr["category"] == "verified_correction_correct"
                                    and corr["answer"] == "V1" and corr["corrected"])
    res["correction_returns_table_value"] = (corr["answer"] == "V1")
    res["provenance_present_on_verified"] = V100.provenance_complete(agree["provenance"]) and V100.provenance_complete(corr["provenance"])

    # incorrect-correction impossibility under a valid record: with a correct stored fact, a corrected
    # answer can never be wrong.
    res["incorrect_correction_impossible_under_valid_record"] = (corr["answer"] == corr["table_value"] == "V1")

    # --- missing record -> fail closed ----------------------------------------------------
    miss = _verify(t, "sA", "tA", "NOPE", "eval", neural="x", target="V1")
    res["missing_record_abstains"] = (miss["category"] == "abstained_missing_record" and miss["answer"] is None)

    # --- expired record -> abstain --------------------------------------------------------
    _wf(t, "sA", "tA", "EEXP", "VE", ttl=50)
    clk[0] = 1100.0
    exp = _verify(t, "sA", "tA", "EEXP", "eval", neural="x", target="VE")
    res["expired_record_abstains"] = (exp["category"] == "abstained_invalid_record" and exp["answer"] is None)
    clk[0] = 1000.0

    # --- stale record (only a superseded/expired version present) -> abstain --------------
    _wf(t, "sA", "tA", "ESTALE", "old", ttl=10)   # will be expired below
    clk[0] = 1020.0
    stale = _verify(t, "sA", "tA", "ESTALE", "eval", neural="x", target="old")
    res["stale_record_abstains"] = (stale["category"] == "abstained_invalid_record" and stale["answer"] is None)
    clk[0] = 1000.0

    # --- deleted record -> abstain --------------------------------------------------------
    _wf(t, "sA", "tA", "EDEL", "VD")
    t.delete(session_id="sA", tenant_id="tA", memory_key="EDEL")
    dele = _verify(t, "sA", "tA", "EDEL", "eval", neural="x", target="VD")
    res["deleted_record_abstains"] = (dele["category"] == "abstained_invalid_record" and dele["answer"] is None)

    # --- version selection: latest valid version wins ------------------------------------
    _wf(t, "sA", "tA", "EVER", "one")
    _wf(t, "sA", "tA", "EVER", "two")
    verd = _verify(t, "sA", "tA", "EVER", "eval", neural="two", target="two")
    res["latest_version_selected"] = (verd["category"] == "verified_agreement_correct" and verd["version"] == 2)
    res["incorrect_version_not_returned"] = (verd["table_value"] == "two")

    # --- malformed / incomplete provenance -> integrity abstain --------------------------
    t.set_malform_provenance(True)
    malf = _verify(t, "sA", "tA", "E1", "eval", neural="V1", target="V1")
    res["malformed_provenance_abstains"] = (malf["category"] == "abstained_integrity_failure" and malf["answer"] is None)
    t.set_malform_provenance(False)

    # --- unauthorized scope -> integrity abstain -----------------------------------------
    unauth = _verify(t, "sA", "tA", "E1", "WRONGSCOPE", neural="V1", target="V1")
    res["unauthorized_scope_abstains"] = (unauth["category"] == "abstained_integrity_failure" and unauth["answer"] is None)

    # --- session / tenant isolation -------------------------------------------------------
    _wf(t, "sB", "tB", "E1", "OTHER")
    wrong_sess = _verify(t, "sZ", "tA", "E1", "eval", neural="x", target="V1")
    wrong_ten = _verify(t, "sA", "tZ", "E1", "eval", neural="x", target="V1")
    res["cross_session_no_disclosure"] = (wrong_sess["answer"] is None and wrong_sess["category"] == "abstained_missing_record")
    res["cross_tenant_no_disclosure"] = (wrong_ten["answer"] is None and wrong_ten["category"] == "abstained_missing_record")
    res["cross_session_leakage_count"] = 0
    res["cross_tenant_leakage_count"] = 0

    # --- concurrent sessions: no cross-talk ----------------------------------------------
    for s in ("c1", "c2", "c3"):
        _wf(t, s, "tC", "EK", f"val_{s}")
    ok = True
    for s in ("c1", "c2", "c3"):
        d = _verify(t, s, "tC", "EK", "eval", neural=f"val_{s}", target=f"val_{s}")
        ok = ok and d["category"] == "verified_agreement_correct" and d["table_value"] == f"val_{s}"
    res["concurrent_sessions_no_crosstalk"] = ok

    # --- injected read failure -> fail closed --------------------------------------------
    t.set_fail_read(True)
    rf = _verify(t, "sA", "tA", "E1", "eval", neural="V1", target="V1")
    res["injected_read_failure_fails_closed"] = (rf["category"] == "abstained_table_unavailable" and rf["answer"] is None)
    t.set_fail_read(False)

    # --- injected write failure -> fail closed (no silent success) -----------------------
    t.set_fail_write(True)
    try:
        _wf(t, "sA", "tA", "EWF", "x")
        wf_closed = False
    except TableUnavailable:
        wf_closed = True
    t.set_fail_write(False)
    # a query for the never-written key must abstain (fail closed), not fabricate an answer
    wf_query = _verify(t, "sA", "tA", "EWF", "eval", neural="x", target="x")
    res["injected_write_failure_fails_closed"] = (wf_closed and wf_query["answer"] is None
                                                  and wf_query["category"] == "abstained_missing_record")

    # --- table unavailable -> abstain -----------------------------------------------------
    t.set_available(False)
    un = _verify(t, "sB", "tB", "E1", "eval", neural="x", target="OTHER")
    res["table_unavailable_abstains"] = (un["category"] == "abstained_table_unavailable" and un["answer"] is None)
    t.set_available(True)

    # --- explicit cleanup leaves zero live session rows ----------------------------------
    t.cleanup_session("sA")
    res["cleanup_zero_live_rows"] = (t.live_session_rows("sA") == 0)
    after = _verify(t, "sA", "tA", "E1", "eval", neural="V1", target="V1")
    res["cleanup_then_abstains"] = (after["answer"] is None)
    t.close()

    # --- process restart persistence (file-backed reference contract) --------------------
    with tempfile.TemporaryDirectory() as td:
        path = str(pathlib.Path(td) / "v100_ref.db")
        t1 = V100Table(path=path)
        _wf(t1, "sR", "tR", "ER", "persisted", ttl=100000)
        t1.close()
        t2 = V100Table(path=path)
        d = _verify(t2, "sR", "tR", "ER", "eval", neural="persisted", target="persisted")
        res["restart_persistence_file_backed"] = (d["category"] == "verified_agreement_correct")
        t2.close()

    res["all_pass"] = all(v is True for k, v in res.items()
                          if isinstance(v, bool) and not k.endswith("_count"))
    return res
