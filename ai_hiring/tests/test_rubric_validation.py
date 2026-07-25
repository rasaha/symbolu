"""Rubric contract validation tests."""

from __future__ import annotations

from ai_hiring.ontology import EvidenceType, ReasonCode
from ai_hiring.rubrics import EvidenceRule, Rubric, RubricCapability
from ai_hiring.services.rubric_validation_service import IssueCode

from .conftest import make_rubric, publish_capability


def _rc(cap_id, weight, cap_version=1, scale="scale.1_5", reason_codes=()):
    rule = EvidenceRule(capability_id=cap_id, allowed_types=(EvidenceType.CODING_TEST,),
                        required_types=(EvidenceType.CODING_TEST,), minimum_count=1)
    return RubricCapability(capability_id=cap_id, capability_version=cap_version,
                            weight=weight, scoring_scale_id=scale, evidence_rule=rule,
                            allowed_reason_codes=reason_codes)


def test_valid_rubric_passes(platform):
    publish_capability(platform, "cap.python")
    result = platform.rubric_validation_service.validate(make_rubric("cap.python"))
    assert result.valid, result.issue_codes


def test_duplicate_capability(platform):
    publish_capability(platform, "cap.python")
    rub = Rubric(rubric_id="r", role="Backend", version=1,
                 capabilities=(_rc("cap.python", 0.5), _rc("cap.python", 0.5)),
                 default_scoring_scale_id="scale.1_5")
    result = platform.rubric_validation_service.validate(rub)
    assert IssueCode.DUPLICATE_CAPABILITY.value in result.issue_codes


def test_weight_total_invalid(platform):
    publish_capability(platform, "cap.python")
    publish_capability(platform, "cap.testing", name="Testing")
    rub = Rubric(rubric_id="r", role="Backend", version=1,
                 capabilities=(_rc("cap.python", 0.3), _rc("cap.testing", 0.3)),
                 default_scoring_scale_id="scale.1_5")
    result = platform.rubric_validation_service.validate(rub)
    assert IssueCode.WEIGHT_TOTAL_INVALID.value in result.issue_codes


def test_unknown_capability(platform):
    rub = make_rubric("cap.ghost")
    result = platform.rubric_validation_service.validate(rub)
    assert IssueCode.UNKNOWN_CAPABILITY.value in result.issue_codes


def test_unpublished_capability(platform):
    # capability exists but only as DRAFT (never published)
    from ai_hiring.ontology import CapabilityStatus
    from .conftest import make_capability
    platform.ontology_repo.add(make_capability("cap.draft"))  # DRAFT, not via service
    result = platform.rubric_validation_service.validate(make_rubric("cap.draft"))
    assert IssueCode.UNPUBLISHED_CAPABILITY.value in result.issue_codes


def test_capability_version_mismatch(platform):
    publish_capability(platform, "cap.python")  # version 1 only
    result = platform.rubric_validation_service.validate(
        make_rubric("cap.python", cap_version=5))
    assert IssueCode.CAPABILITY_VERSION_MISMATCH.value in result.issue_codes


def test_unknown_scoring_scale(platform):
    publish_capability(platform, "cap.python")
    result = platform.rubric_validation_service.validate(
        make_rubric("cap.python", scale="scale.nonexistent"))
    assert IssueCode.UNKNOWN_SCORING_SCALE.value in result.issue_codes


def test_reason_code_not_allowed(platform):
    publish_capability(platform, "cap.python")
    rub = Rubric(rubric_id="r", role="Backend", version=1,
                 capabilities=(_rc("cap.python", 1.0,
                                   reason_codes=(ReasonCode.LOW_CONFIDENCE,)),),
                 default_scoring_scale_id="scale.1_5",
                 allowed_reason_codes=(ReasonCode.INSUFFICIENT_SAMPLE,))
    result = platform.rubric_validation_service.validate(rub)
    assert IssueCode.REASON_CODE_NOT_ALLOWED.value in result.issue_codes


def test_no_capabilities(platform):
    from ai_hiring.errors import DomainValidationError
    import pytest
    # a rubric with no capabilities is structurally allowed but fails validation
    rub = Rubric(rubric_id="r", role="Backend", version=1, capabilities=(),
                 default_scoring_scale_id="scale.1_5")
    result = platform.rubric_validation_service.validate(rub)
    assert IssueCode.NO_CAPABILITIES.value in result.issue_codes


def test_custom_scale_recognized(platform):
    publish_capability(platform, "cap.python")
    from ai_hiring.rubrics import ScoringScale, ScaleType
    custom = ScoringScale(scale_id="scale.custom", scale_type=ScaleType.CUSTOM,
                          minimum=0, maximum=3, labels=("none", "some", "lots", "expert"))
    rub = make_rubric("cap.python", scale="scale.custom", custom_scales=(custom,))
    result = platform.rubric_validation_service.validate(rub)
    assert result.valid, result.issue_codes
