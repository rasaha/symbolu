"""Evidence admissibility rule tests."""

from __future__ import annotations

import pytest

from ugence_ai_hiring.ontology import EvidenceType
from ugence_ai_hiring.rubrics import (
    DEFAULT_ADMISSIBILITY_POLICY,
    EvidenceAdmissibility,
    EvidenceDescriptor,
    EvidenceRule,
    MissingEvidenceStatus,
)

POL = DEFAULT_ADMISSIBILITY_POLICY


def _rule(**kw):
    base = dict(capability_id="cap.python", allowed_types=(EvidenceType.CODING_TEST,
                EvidenceType.GITHUB), required_types=(EvidenceType.CODING_TEST,),
                prohibited_types=(EvidenceType.PHOTO, EvidenceType.REFERENCE_LETTER),
                minimum_count=1, freshness_days=365)
    base.update(kw)
    return EvidenceRule(**base)


def test_admissible():
    assert POL.classify_item(_rule(), EvidenceDescriptor(EvidenceType.CODING_TEST, 10)) \
        is EvidenceAdmissibility.ADMISSIBLE


def test_prohibited():
    assert POL.classify_item(_rule(), EvidenceDescriptor(EvidenceType.PHOTO)) \
        is EvidenceAdmissibility.PROHIBITED


def test_stale():
    assert POL.classify_item(_rule(), EvidenceDescriptor(EvidenceType.CODING_TEST, 400)) \
        is EvidenceAdmissibility.STALE


def test_unknown_type():
    # a type not in the allow-list and not prohibited
    assert POL.classify_item(_rule(), EvidenceDescriptor(EvidenceType.CERTIFICATION)) \
        is EvidenceAdmissibility.UNKNOWN


def test_insufficient_set():
    rule = _rule(minimum_count=2)
    result = POL.classify_set(rule, (EvidenceDescriptor(EvidenceType.CODING_TEST, 5),))
    assert result is EvidenceAdmissibility.INSUFFICIENT


def test_prohibited_dominates_set():
    result = POL.classify_set(_rule(), (
        EvidenceDescriptor(EvidenceType.CODING_TEST, 5),
        EvidenceDescriptor(EvidenceType.PHOTO)))
    assert result is EvidenceAdmissibility.PROHIBITED


def test_admissible_set():
    result = POL.classify_set(_rule(), (
        EvidenceDescriptor(EvidenceType.CODING_TEST, 5),
        EvidenceDescriptor(EvidenceType.GITHUB, 5)))
    assert result is EvidenceAdmissibility.ADMISSIBLE


def test_required_not_in_allowed_rejected():
    with pytest.raises(Exception):
        EvidenceRule(capability_id="c", allowed_types=(EvidenceType.GITHUB,),
                     required_types=(EvidenceType.CODING_TEST,))


def test_prohibited_and_allowed_overlap_rejected():
    with pytest.raises(Exception):
        EvidenceRule(capability_id="c", allowed_types=(EvidenceType.GITHUB,),
                     prohibited_types=(EvidenceType.GITHUB,))


def test_missing_evidence_status_enum_complete():
    assert {s.value for s in MissingEvidenceStatus} == {
        "NOT_SUBMITTED", "NOT_REQUIRED", "REDACTED", "QUARANTINED",
        "UNAVAILABLE", "INSUFFICIENT"}
