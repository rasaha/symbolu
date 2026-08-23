"""Missing and ambiguous mandatory fields, and the INVALID/INDETERMINATE split.

The two are not graded severities of one problem. A missing field is definitely
wrong. An ambiguous field is something this build refuses to interpret, because
choosing an interpretation would be this package silently making a decision that
belongs to a person. Both are fail-closed; only one is a defect report.
"""

from __future__ import annotations

import fixtures
import pytest

from ugence_agent_constitution import (
    ArtifactKind,
    RequirementObligation,
    ValidationOutcome,
    validate_artifact,
    validate_constitution,
)
from ugence_agent_constitution.validation import codes


# -- missing ------------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    [
        "constitution_id",
        "role_name",
        "role_summary",
        "ratified_at",
        "source_manifest_id",
        "source_manifest_author_id",
    ],
)
@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
def test_a_blank_mandatory_field_is_invalid(field, blank):
    report = validate_constitution(fixtures.constitution(**{field: blank}))
    assert report.outcome is ValidationOutcome.INVALID
    assert report.has_code(codes.MANDATORY_FIELD_MISSING)
    assert not report.is_usable


def test_an_absent_schema_version_is_invalid_and_is_not_guessed():
    payload = fixtures.constitution().model_dump()
    del payload["schema_version"]
    report = validate_constitution(payload)
    assert report.outcome is ValidationOutcome.INVALID
    assert report.has_code(codes.SCHEMA_VERSION_MISSING)


def test_an_absent_required_model_field_is_reported_as_a_structure_error():
    payload = fixtures.constitution().model_dump()
    del payload["issuer"]
    report = validate_constitution(payload)
    assert report.outcome is ValidationOutcome.INVALID
    assert report.has_code(codes.SCHEMA_STRUCTURE_INVALID)


def test_an_unknown_extra_field_is_refused_rather_than_dropped():
    """Dropping it would make the digest attest to less than the author wrote."""
    payload = fixtures.constitution().model_dump()
    payload["some_future_field"] = "meaning this build cannot digest"
    report = validate_constitution(payload)
    assert report.outcome is ValidationOutcome.INVALID
    assert report.has_code(codes.SCHEMA_STRUCTURE_INVALID)


def test_a_non_mapping_payload_is_invalid():
    report = validate_constitution(["not", "a", "mapping"])
    assert report.outcome is ValidationOutcome.INVALID
    assert report.has_code(codes.PAYLOAD_NOT_A_MAPPING)


# -- ambiguous -----------------------------------------------------------


@pytest.mark.parametrize("value", [" Refund agent", "Refund agent ", "\tRefund agent\n"])
def test_surrounding_whitespace_on_a_mandatory_field_is_indeterminate(value):
    """It reads as one value and digests as another; the package will not choose."""
    report = validate_constitution(fixtures.constitution(role_name=value))
    assert report.outcome is ValidationOutcome.INDETERMINATE
    assert report.has_code(codes.MANDATORY_FIELD_AMBIGUOUS)
    assert not report.is_usable


def test_a_duplicated_requirement_id_is_indeterminate_not_invalid():
    """Which of the two binds is not determinable from the artifact."""
    report = validate_constitution(
        fixtures.constitution(
            capability_requirements=(
                fixtures.requirement(summary="Refund up to the ceiling"),
                fixtures.requirement(summary="Refund up to twice the ceiling"),
            )
        )
    )
    assert report.outcome is ValidationOutcome.INDETERMINATE
    assert report.has_code(codes.REQUIREMENT_ID_AMBIGUOUS)


def test_a_mandatory_requirement_that_pins_no_registry_entry_is_indeterminate():
    """It names nothing anyone downstream could resolve, so nothing downstream
    could ever decide whether it was met."""
    report = validate_constitution(
        fixtures.constitution(
            capability_requirements=(fixtures.requirement(entry_ref=None),)
        )
    )
    assert report.outcome is ValidationOutcome.INDETERMINATE
    assert report.has_code(codes.REQUIREMENT_UNRESOLVABLE)


def test_a_narrative_prohibition_without_a_registry_entry_stays_well_formed():
    """The unresolvable rule is scoped to MANDATORY: a prohibition written before
    the capability exists anywhere is a legitimate thing to write down."""
    report = validate_constitution(
        fixtures.constitution(
            capability_requirements=(
                fixtures.requirement(
                    obligation=RequirementObligation.PROHIBITED, entry_ref=None
                ),
            ),
            prohibited_actions=(),
        )
    )
    assert report.is_usable


def test_a_subject_declaring_one_entry_at_two_versions_is_indeterminate():
    report = validate_artifact(
        fixtures.subject(
            declared_capability_entries=(
                fixtures.entry_ref(version="1.0.0"),
                fixtures.entry_ref(version="2.0.0"),
            )
        ),
        ArtifactKind.CONFORMANCE_SUBJECT,
    )
    assert report.outcome is ValidationOutcome.INDETERMINATE
    assert report.has_code(codes.SUBJECT_ENTRY_AMBIGUOUS)


# -- contradictions are INVALID, not ambiguous ---------------------------


def test_a_capability_both_mandatory_and_prohibited_is_invalid():
    report = validate_constitution(
        fixtures.constitution(
            capability_requirements=(
                fixtures.requirement(requirement_id="req.a"),
                fixtures.requirement(
                    requirement_id="req.b", obligation=RequirementObligation.PROHIBITED
                ),
            ),
            prohibited_actions=(),
        )
    )
    assert report.outcome is ValidationOutcome.INVALID
    assert report.has_code(codes.REQUIREMENT_CONTRADICTORY)


def test_a_conditional_obligation_with_no_condition_is_invalid():
    report = validate_constitution(
        fixtures.constitution(
            capability_requirements=(
                fixtures.requirement(obligation=RequirementObligation.CONDITIONAL),
            )
        )
    )
    assert report.outcome is ValidationOutcome.INVALID
    assert report.has_code(codes.REQUIREMENT_CONDITION_MISSING)


def test_an_unconditional_obligation_carrying_a_condition_is_invalid():
    report = validate_constitution(
        fixtures.constitution(
            capability_requirements=(
                fixtures.requirement(condition="only on Tuesdays"),
            )
        )
    )
    assert report.outcome is ValidationOutcome.INVALID
    assert report.has_code(codes.REQUIREMENT_CONDITION_UNEXPECTED)


def test_a_prohibited_action_that_is_also_a_mandatory_requirement_is_invalid():
    report = validate_constitution(
        fixtures.constitution(
            prohibited_actions=("Issue a refund only up to the ratified ceiling",)
        )
    )
    assert report.outcome is ValidationOutcome.INVALID
    assert report.has_code(codes.OBLIGATION_CONTRADICTION)


def test_a_contract_requiring_and_forbidding_the_same_behaviour_is_invalid():
    report = validate_artifact(
        fixtures.contract(
            required_behaviours=("Retry the refund",),
            forbidden_behaviours=("Retry the refund",),
        ),
        ArtifactKind.DEVELOPER_IMPLEMENTATION_CONTRACT,
    )
    assert report.outcome is ValidationOutcome.INVALID
    assert report.has_code(codes.CONTRACT_CONTRADICTORY_BEHAVIOUR)


# -- fail-closed aggregation --------------------------------------------


def test_invalid_outranks_indeterminate_when_both_are_present():
    report = validate_constitution(
        fixtures.constitution(
            role_name=" Refund agent",  # ambiguous
            artifact_version="1.0",  # invalid
        )
    )
    assert report.outcome is ValidationOutcome.INVALID
    assert report.has_code(codes.MANDATORY_FIELD_AMBIGUOUS)
    assert report.has_code(codes.ARTIFACT_VERSION_MALFORMED)


def test_only_valid_is_usable():
    assert validate_constitution(fixtures.constitution()).is_usable
    for outcome_case in (
        fixtures.constitution(role_name=""),
        fixtures.constitution(role_name=" Refund agent"),
    ):
        assert not validate_constitution(outcome_case).is_usable


def test_every_rule_runs_so_a_fixed_artifact_does_not_surface_a_new_problem():
    """No short-circuiting: three independent breaks are all reported at once."""
    report = validate_constitution(
        fixtures.constitution(role_name="", role_summary="", ratified_at="")
    )
    paths = {f.path for f in report.findings}
    assert {"role_name", "role_summary", "ratified_at"} <= paths


def test_a_report_is_deterministic_finding_for_finding():
    payload = fixtures.constitution(role_name="", artifact_version="1.0").model_dump()
    reports = [validate_constitution(payload) for _ in range(10)]
    assert len({r.canonical_json() for r in reports}) == 1
