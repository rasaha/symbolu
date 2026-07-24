"""Phase 1 test: the prior-artifact guard pins all 59 prior outcome-bearing artifacts and passes."""
from reviewer_calibration_pilot import verify_prior_artifacts as guard


def test_prior_artifacts_intact():
    assert guard.verify() is True
    assert len(guard.FROZEN) == 59
