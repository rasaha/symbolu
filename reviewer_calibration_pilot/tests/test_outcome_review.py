"""Phase 16 test: outcome-bearing review returns NOT_ENOUGH_HUMAN_EVIDENCE with no real reviewers and
runs zero reviews."""
from reviewer_calibration_pilot import outcome_review as orv


def test_not_enough_human_evidence():
    m = orv.run()
    assert m["status"] == "NOT_ENOUGH_HUMAN_EVIDENCE"
    assert m["reviews_run"] == 0
    assert m["human_records"] == 0
    assert m["reviewer_count"] < orv.MIN_REAL_REVIEWERS
