"""Phase 10 tests: metrics return NOT_ENOUGH_HUMAN_EVIDENCE with no human records; mock records excluded;
real records compute."""
from reviewer_calibration_pilot import metrics


def test_empty_is_not_enough_human_evidence():
    assert metrics.compute([])["status"] == "NOT_ENOUGH_HUMAN_EVIDENCE"


def test_mock_records_excluded():
    assert metrics.compute([{"is_mock": True, "agreement": True}])["status"] == "NOT_ENOUGH_HUMAN_EVIDENCE"


def test_real_records_compute():
    recs = [{"is_mock": False, "agreement": True, "exact_agree": True, "override": False,
             "confidence": 0.8, "review_time": 30, "explanation_usefulness": 4}]
    m = metrics.compute(recs)
    assert m["status"] == "COMPUTED"
    assert m["human_records"] == 1
    assert m["post_reveal_agreement"] == 1.0
