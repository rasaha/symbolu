"""Phase 1 test: the prior-artifact guard pins all 45 prior outcome-bearing artifacts and passes."""
from reviewer_ready_pilot import verify_prior_artifacts as guard


def test_prior_artifacts_intact():
    assert guard.verify() is True
    assert len(guard.FROZEN) == 45
