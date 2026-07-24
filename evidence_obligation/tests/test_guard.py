"""Phase 1 test: the prior-artifact guard pins all 32 prior outcome-bearing artifacts and passes."""
from evidence_obligation import verify_prior_artifacts as guard


def test_prior_artifacts_intact():
    assert guard.verify() is True
    assert len(guard.FROZEN) == 32
