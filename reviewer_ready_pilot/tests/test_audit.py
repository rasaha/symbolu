"""M9 tests - review audit trail (Phase 14)."""
from reviewer_ready_pilot import audit


def _good_session(log, ts0=0, rid="REV-A", role="technical", aid="rrp-01"):
    log.assigned(ts0, rid, role, aid)
    log.stage_a(ts0 + 1, rid, role, aid, {"obligation": "E3"})
    log.revealed(ts0 + 2, rid, role, aid, {"final_obligation": "E3"})
    log.stage_b(ts0 + 3, rid, role, aid, {"obligation": "E3", "override": False})


def test_clean_session_verifies():
    log = audit.AuditLog()
    _good_session(log)
    r = audit.verify(log)
    assert r["chain_ok"] and r["workflow_ok"], r["findings"]
    assert r["n_entries"] == 4


def test_override_recorded_as_override_event():
    log = audit.AuditLog()
    log.assigned(0, "REV-A", "technical", "rrp-01")
    log.stage_a(1, "REV-A", "technical", "rrp-01", {"obligation": "E2"})
    log.revealed(2, "REV-A", "technical", "rrp-01", {"final_obligation": "E3"})
    log.stage_b(3, "REV-A", "technical", "rrp-01",
                {"obligation": "E2", "override": True, "override_reason": "insufficient"})
    assert log.entries[-1].event == audit.OVERRIDE


def test_reveal_before_stage_a_flagged():
    log = audit.AuditLog()
    log.assigned(0, "REV-A", "technical", "rrp-01")
    log.revealed(1, "REV-A", "technical", "rrp-01", {"final_obligation": "E3"})
    r = audit.verify(log)
    assert not r["workflow_ok"]
    assert any("blinding violated" in f for f in r["findings"])


def test_tampering_breaks_chain():
    log = audit.AuditLog()
    _good_session(log)
    # tamper: mutate a recorded entry's payload hash
    log.entries  # snapshot copy; mutate the internal list directly
    log._entries[1].payload_hash = "deadbeef"
    r = audit.verify(log)
    assert not r["chain_ok"]
    assert any("mismatch" in f or "link" in f for f in r["findings"])


def test_append_only_no_update_delete():
    log = audit.AuditLog()
    _good_session(log)
    assert not hasattr(log, "update")
    assert not hasattr(log, "delete")
    # entries property returns a copy; mutating it does not shrink the log
    e = log.entries
    e.clear()
    assert len(log.entries) == 4
