"""Phase 4 tests: source-role classification and the authority distinctions the spec requires."""
from evidence_obligation import source_role as sr
from evidence_obligation import authority as au


def test_code_is_primary_implementation_tests_are_test_artifact():
    assert sr.classify_source_role("pkg/mod.py", "docstring", "docs")[0] == sr.PRIMARY_IMPLEMENTATION
    assert sr.classify_source_role("pkg/tests/test_mod.py", "docstring", "x")[0] == sr.TEST_ARTIFACT


def test_approved_vs_draft_policy():
    assert sr.classify_source_role("docs/p.md", "doc", "This approved policy is effective.")[0] == \
        sr.APPROVED_POLICY
    assert sr.classify_source_role("docs/p.md", "doc", "Draft proposal, WIP.")[0] == sr.DRAFT_POLICY


def test_unknown_source_fails_closed():
    assert sr.classify_source_role("weird.bin", "blob", "x")[0] == sr.UNKNOWN_SOURCE


def test_code_authoritative_for_behavior_not_performance():
    assert au.authority_for(sr.PRIMARY_IMPLEMENTATION, "code_behavior")[0] == au.AUTHORITATIVE
    assert au.authority_for(sr.PRIMARY_IMPLEMENTATION, "measured_performance")[0] == au.NOT_AUTHORITATIVE


def test_model_output_never_self_verifies_factual():
    assert au.authority_for(sr.MODEL_GENERATED_TEXT, "medical")[0] == au.SELF_REFERENTIAL
    assert au.authority_for(sr.GENERATED_DOCUMENTATION, "current_fact")[0] == au.SELF_REFERENTIAL


def test_user_authoritative_for_own_preference():
    assert au.authority_for(sr.USER_STATEMENT, "user_preference")[0] == au.AUTHORITATIVE


def test_audit_log_historical_only():
    assert au.authority_for(sr.AUDIT_LOG, "historical_fact")[0] == au.HISTORICAL_ONLY


def test_authority_levels():
    assert au.artifact_authority_level(sr.APPROVED_POLICY) == "high"
    assert au.artifact_authority_level(sr.PRIMARY_IMPLEMENTATION) == "medium"
    assert au.artifact_authority_level(sr.UNKNOWN_SOURCE) == "none"
