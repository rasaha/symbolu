"""Reason-code taxonomy tests."""

from __future__ import annotations

from ai_hiring.ontology import (
    REASON_CODE_CATALOG,
    ReasonCode,
    get_reason_code_spec,
    is_known_reason_code,
)


def test_all_codes_documented():
    for code in ReasonCode:
        assert code in REASON_CODE_CATALOG
        spec = get_reason_code_spec(code)
        assert spec.summary and spec.description and spec.category


def test_codes_are_unique():
    values = [c.value for c in ReasonCode]
    assert len(values) == len(set(values))


def test_known_lookup():
    assert is_known_reason_code("MISSING_REQUIRED_EVIDENCE")
    assert not is_known_reason_code("INVENTED_CODE")


def test_expected_codes_present():
    expected = {
        "MISSING_REQUIRED_EVIDENCE", "STALE_EVIDENCE", "INSUFFICIENT_SAMPLE",
        "CONFLICTING_EVIDENCE", "PROHIBITED_EVIDENCE", "QUARANTINED_CONTENT",
        "LOW_CONFIDENCE", "NOT_APPLICABLE"}
    assert expected <= {c.value for c in ReasonCode}


def test_spec_code_matches_key():
    for code, spec in REASON_CODE_CATALOG.items():
        assert spec.code is code


def test_evidence_types_known():
    from ai_hiring.ontology import EvidenceType, is_known_evidence_type
    assert is_known_evidence_type("CODING_TEST")
    assert not is_known_evidence_type("TAROT_READING")
    assert "PHOTO" in {e.value for e in EvidenceType}
