"""Phases 12-13 tests: human validation is NOT_EVALUATED (never called human validation); the proxy is
deterministic and shows the policy safe-direction dominant."""
from minimal_evidence_policy import review_study as rs


def test_human_validation_not_evaluated():
    m = rs.compute()
    assert m["human_validation"] == "NOT_EVALUATED"
    assert "NOT human validation" in m["method"]


def test_policy_mostly_at_or_above_gold():
    m = rs.compute()
    assert m["policy_at_or_above_gold_rate"] >= 0.9      # errs stronger, safe direction
    assert m["policy_below_gold_count"] <= 3


def test_deterministic():
    assert rs.compute()["rubric_agreement"] == rs.compute()["rubric_agreement"]
