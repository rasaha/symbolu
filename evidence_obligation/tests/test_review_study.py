"""Phase 20 tests: the review study is flagged simulated, deterministic, and reports the honest
low-agreement / stricter-override signals."""
from evidence_obligation import review_study as rs


def test_review_study_flagged_simulated():
    m = rs.compute()
    assert m["simulated"] is True
    assert "SIMULATED" in m["caveat"]


def test_low_agreement_and_stricter_overrides():
    m = rs.compute()
    assert m["reviewer_agreement"] < 0.7                       # H0-14 risk signal
    # overrides skew toward stricter (component leans permissive)
    assert m["override_direction"]["toward_stricter"] >= m["override_direction"]["toward_looser"]


def test_review_study_deterministic():
    a = rs.compute(); b = rs.compute()
    assert a["reviewer_agreement"] == b["reviewer_agreement"]
    assert a["override_rate"] == b["override_rate"]
