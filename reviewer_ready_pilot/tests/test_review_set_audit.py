"""M5 tests - final review set audit (Phase 9)."""
from reviewer_ready_pilot import review_set_audit as a
from reviewer_ready_pilot import dataset


def test_audit_passes_on_frozen_set():
    rep = a.audit()
    failed = [c.key for c in rep.checks if not c.passed]
    assert rep.status == "REVIEW_SET_OK", f"failed checks: {failed}"
    assert not failed


def test_all_risk_tiers_and_trap_families_covered():
    rep = a.audit()
    rd = rep.stats["risk_distribution"]
    for tier in ("low", "medium", "high", "critical", "unknown"):
        assert rd.get(tier, 0) > 0, tier
    td = rep.stats["trap_distribution"]
    assert set(td) == {t[0] for t in dataset._TRAPS}
    assert all(v >= dataset.TRAP_VARIANTS for v in td.values())


def test_audit_flags_a_leaked_gold_label(monkeypatch):
    """If a system result leaks into the final set, the audit must fail (never silently pass)."""
    good = dataset.load_final()
    poisoned = [dict(i) for i in good]
    poisoned[0]["gold_obligation"] = "E4_EXTERNAL_AUTHORITATIVE_EVIDENCE_AND_REVIEW"
    monkeypatch.setattr(dataset, "load_final", lambda: poisoned)
    rep = a.audit()
    assert rep.status == "REVIEW_SET_NEEDS_IMPROVEMENT"
    assert not next(c for c in rep.checks if c.key == "A2").passed


def test_audit_report_serializable():
    d = a.audit().as_dict()
    assert d["status"] in ("REVIEW_SET_OK", "REVIEW_SET_NEEDS_IMPROVEMENT")
    assert "checks" in d and "stats" in d
