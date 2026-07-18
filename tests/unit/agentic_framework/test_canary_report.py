"""
test_canary_report.py — JEPA canary approve/deny report over synthetic persisted audit data.
"""

from __future__ import annotations

from experiments.trust_signal import canary_report, shadow_report


def _persist(store, *, request_id, decision, human_confirmed, drivers, trust_decision="confirm",
             trust_legacy="confirm", cls="match", latency=100.0, risk="write"):
    from agentic.ledger.governance_audit_store import event_from_mcp_audit
    store.append(event_from_mcp_audit(
        timestamp="2026-06-19T00:00:00Z", request_id=request_id, tool_name="t",
        parameters={}, decision=decision, confidence=0.9, risk_level=risk,
        execution_time_ms=latency, success=(decision == "ALLOWED"),
        human_confirmed=human_confirmed,
        trust_decision=trust_decision, trust_legacy_decision=trust_legacy,
        trust_mismatch=(trust_decision != trust_legacy), trust_mismatch_class=cls,
        trust_drivers=drivers, trust_reason="r"))


def _store(tmp_path, name="c.db"):
    from agentic.ledger.governance_audit_store import GovernanceAuditStore
    return GovernanceAuditStore(str(tmp_path / name))


def test_approve_deny_rates_from_persisted_data(tmp_path):
    store = _store(tmp_path)
    n = 0
    for _ in range(3):                       # approved JEPA-sole confirmations
        n += 1
        _persist(store, request_id=f"a{n}", decision="ALLOWED", human_confirmed=True,
                 drivers=["jepa", "execution_permission"], latency=120.0)
    for _ in range(2):                       # denied
        n += 1
        _persist(store, request_id=f"d{n}", decision="ESCALATE", human_confirmed=False,
                 drivers=["jepa"], latency=80.0)
    # a non-JEPA allowed control (must be ignored by the canary summary)
    _persist(store, request_id="ctl", decision="ALLOWED", human_confirmed=False,
             drivers=["execution_permission"], trust_decision="allow", trust_legacy="allow",
             cls="match")
    store.close()

    records = shadow_report.load_records(store_path=str(tmp_path / "c.db"))
    s = canary_report.summarize_canary(records)
    assert s.total == 5 and s.approved == 3 and s.denied == 2
    assert abs(s.approval_rate - 0.6) < 1e-9
    assert abs(s.denial_rate - 0.4) < 1e-9
    assert abs(s.avg_latency_ms - (3 * 120 + 2 * 80) / 5) < 1e-6
    rep = shadow_report.build_report(records)
    assert canary_report.exit_code(s, rep) == 0
    assert "JEPA canary approve/deny report" in canary_report.render(s, rep)


def test_no_canary_data_is_zero_and_clean(tmp_path):
    store = _store(tmp_path, "empty.db")
    _persist(store, request_id="x", decision="ALLOWED", human_confirmed=False,
             drivers=["execution_permission"], trust_decision="allow", trust_legacy="allow")
    store.close()
    records = shadow_report.load_records(store_path=str(tmp_path / "empty.db"))
    s = canary_report.summarize_canary(records)
    assert s.total == 0 and s.approval_rate is None
    assert canary_report.exit_code(s, shadow_report.build_report(records)) == 0


def test_unsafe_relaxation_makes_exit_nonzero(tmp_path):
    store = _store(tmp_path, "bad.db")
    # a JEPA-driven confirm that is fine, plus an unsafe relaxation elsewhere
    _persist(store, request_id="a", decision="ALLOWED", human_confirmed=True,
             drivers=["jepa"], latency=100.0)
    _persist(store, request_id="bad", decision="ALLOWED", human_confirmed=False,
             drivers=["shadow_jepa_derived"], trust_decision="allow", trust_legacy="block",
             cls="unsafe_relaxation")
    store.close()
    records = shadow_report.load_records(store_path=str(tmp_path / "bad.db"))
    s = canary_report.summarize_canary(records)
    rep = shadow_report.build_report(records)
    assert rep.unsafe_relaxation == 1
    assert canary_report.exit_code(s, rep) == 1
    assert "STOP" in canary_report.render(s, rep)


def test_main_smoke(tmp_path):
    store = _store(tmp_path, "m.db")
    _persist(store, request_id="a", decision="ALLOWED", human_confirmed=True, drivers=["jepa"])
    store.close()
    assert canary_report.main(["--store", str(tmp_path / "m.db")]) == 0
