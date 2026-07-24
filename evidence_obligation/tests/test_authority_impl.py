"""Phases 11-12 tests: contextual-authority validation (no false/unsafe authority, circular detected)
and implementation-evidence rules (behavior yes, production no)."""
from evidence_obligation import contextual_authority as ca
from evidence_obligation import implementation_evidence as ie


def test_contextual_authority_no_false_or_unsafe():
    r = ca.validate()
    assert r["accuracy"] == 1.0
    assert r["false_authority"] == 0
    assert r["unsafe_self_support"] == 0
    assert r["circular_self_verification_detected"] >= 3


def test_implementation_supports_behavior_not_production():
    assert ie.assess("source_code", "code_behavior")[0] == ie.SUPPORTS
    assert ie.assess("source_code", "measured_performance")[0] == ie.NON_PRODUCTION
    assert ie.assess("unit_test", "current_fact")[0] == ie.NON_PRODUCTION


def test_weak_implementation_evidence_insufficient():
    for kind in ("comment_only", "dead_code", "mocked_behavior", "stale_documentation", "version_mismatch"):
        assert ie.assess(kind, "code_behavior")[0] == ie.INSUFFICIENT


def test_implementation_matrix_all_correct():
    assert ie.validate()["accuracy"] == 1.0
