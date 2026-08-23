"""Negative controls: every invariant test fails when its invariant is inverted.

A passing invariant test proves nothing on its own. If the checker returned
``VALID`` for everything, or if the "broken" artifact a test builds were not
actually broken, the assertion would still pass and the suite would look healthy.

Each control below is a pair: the intact artifact, which must be usable, and the
same artifact with exactly one invariant inverted, which must not be. Running both
halves is what makes the invariant tests load-bearing rather than decorative. The
final two tests close the loop on the controls themselves — that the table covers
every invariant claimed, and that a deliberately broken checker would be caught.
"""

from __future__ import annotations

import fixtures
import pytest

from ugence_agent_constitution import (
    AGENT_CONSTITUTION_V1,
    ArtifactKind,
    RequirementObligation,
    ValidationOutcome,
    validate_artifact,
    validate_constitution,
)
from ugence_agent_constitution.validation import codes


def _const(**overrides):
    return fixtures.constitution(**overrides)


#: (name, kind, intact artifact, inverted artifact, expected code on the inversion)
CONTROLS = [
    (
        "mandatory field present",
        ArtifactKind.AGENT_CONSTITUTION,
        lambda: _const(),
        lambda: _const(role_name=""),
        codes.MANDATORY_FIELD_MISSING,
    ),
    (
        "mandatory field unambiguous",
        ArtifactKind.AGENT_CONSTITUTION,
        lambda: _const(),
        lambda: _const(role_name=" Refund agent"),
        codes.MANDATORY_FIELD_AMBIGUOUS,
    ),
    (
        "declared digest matches content",
        ArtifactKind.AGENT_CONSTITUTION,
        lambda: _const(),
        lambda: _const().model_copy(update={"role_name": "Quietly renamed"}),
        codes.DIGEST_MISMATCH,
    ),
    (
        "declared digest well-formed",
        ArtifactKind.AGENT_CONSTITUTION,
        lambda: _const(),
        lambda: _const().model_copy(update={"content_digest": "not-a-digest"}),
        codes.DIGEST_MALFORMED,
    ),
    (
        "digest present",
        ArtifactKind.AGENT_CONSTITUTION,
        lambda: _const(),
        lambda: _const(_stamp=False),
        codes.DIGEST_ABSENT,
    ),
    (
        "issuer is not the draft's author",
        ArtifactKind.AGENT_CONSTITUTION,
        lambda: _const(),
        lambda: _const(source_manifest_author_id=fixtures.ISSUER_ID),
        codes.SELF_RATIFICATION,
    ),
    (
        "artifact version is a release version",
        ArtifactKind.AGENT_CONSTITUTION,
        lambda: _const(),
        lambda: _const(artifact_version="1.0.0-rc1"),
        codes.ARTIFACT_VERSION_MALFORMED,
    ),
    (
        "successor bumps its version",
        ArtifactKind.AGENT_CONSTITUTION,
        lambda: fixtures.successor(_const()),
        lambda: fixtures.successor(_const(), artifact_version="1.0.0"),
        codes.SUCCESSION_VERSION_NOT_BUMPED,
    ),
    (
        "successor stays in its lineage",
        ArtifactKind.AGENT_CONSTITUTION,
        lambda: fixtures.successor(_const()),
        lambda: fixtures.successor(_const(), constitution_id="constitution.other"),
        codes.SUCCESSION_LINEAGE_MISMATCH,
    ),
    (
        "requirement ids are unique",
        ArtifactKind.AGENT_CONSTITUTION,
        lambda: _const(
            capability_requirements=(
                fixtures.requirement(requirement_id="req.a"),
                fixtures.requirement(
                    requirement_id="req.b", entry_ref=fixtures.entry_ref("escalate")
                ),
            )
        ),
        lambda: _const(
            capability_requirements=(
                fixtures.requirement(requirement_id="req.a", summary="One reading"),
                fixtures.requirement(requirement_id="req.a", summary="Another reading"),
            )
        ),
        codes.REQUIREMENT_ID_AMBIGUOUS,
    ),
    (
        "a capability is not both mandatory and prohibited",
        ArtifactKind.AGENT_CONSTITUTION,
        lambda: _const(),
        lambda: _const(
            capability_requirements=(
                fixtures.requirement(requirement_id="req.a"),
                fixtures.requirement(
                    requirement_id="req.b",
                    obligation=RequirementObligation.PROHIBITED,
                ),
            ),
            prohibited_actions=(),
        ),
        codes.REQUIREMENT_CONTRADICTORY,
    ),
    (
        "a conditional obligation states its condition",
        ArtifactKind.AGENT_CONSTITUTION,
        lambda: _const(
            capability_requirements=(
                fixtures.requirement(
                    obligation=RequirementObligation.CONDITIONAL,
                    condition="Only within business hours",
                ),
            ),
            prohibited_actions=(),
        ),
        lambda: _const(
            capability_requirements=(
                fixtures.requirement(obligation=RequirementObligation.CONDITIONAL),
            ),
            prohibited_actions=(),
        ),
        codes.REQUIREMENT_CONDITION_MISSING,
    ),
    (
        "a mandatory requirement pins a resolvable entry",
        ArtifactKind.AGENT_CONSTITUTION,
        lambda: _const(),
        lambda: _const(
            capability_requirements=(fixtures.requirement(entry_ref=None),)
        ),
        codes.REQUIREMENT_UNRESOLVABLE,
    ),
    (
        "a prohibited action is not also mandatory",
        ArtifactKind.AGENT_CONSTITUTION,
        lambda: _const(),
        lambda: _const(
            prohibited_actions=("Issue a refund only up to the ratified ceiling",)
        ),
        codes.OBLIGATION_CONTRADICTION,
    ),
    (
        "a draft is not readable as a constitution",
        ArtifactKind.AGENT_CONSTITUTION,
        lambda: _const(),
        lambda: fixtures.manifest(),
        codes.DRAFT_IS_NOT_A_CONSTITUTION,
    ),
    (
        "a contract does not require and forbid the same behaviour",
        ArtifactKind.DEVELOPER_IMPLEMENTATION_CONTRACT,
        lambda: fixtures.contract(),
        lambda: fixtures.contract(
            required_behaviours=("Retry the refund",),
            forbidden_behaviours=("Retry the refund",),
        ),
        codes.CONTRACT_CONTRADICTORY_BEHAVIOUR,
    ),
    (
        "a contract states some obligation",
        ArtifactKind.DEVELOPER_IMPLEMENTATION_CONTRACT,
        lambda: fixtures.contract(),
        lambda: fixtures.contract(required_behaviours=(), forbidden_behaviours=()),
        codes.CONTRACT_NO_OBLIGATIONS,
    ),
    (
        "a subject declares each entry at one version",
        ArtifactKind.CONFORMANCE_SUBJECT,
        lambda: fixtures.subject(),
        lambda: fixtures.subject(
            declared_capability_entries=(
                fixtures.entry_ref(version="1.0.0"),
                fixtures.entry_ref(version="2.0.0"),
            )
        ),
        codes.SUBJECT_ENTRY_AMBIGUOUS,
    ),
    (
        "a manifest is well-formed",
        ArtifactKind.AGENT_ROLE_MANIFEST,
        lambda: fixtures.manifest(),
        lambda: fixtures.manifest(author_id=""),
        codes.MANDATORY_FIELD_MISSING,
    ),
]

IDS = [name for name, *_ in CONTROLS]


@pytest.mark.parametrize("name,kind,intact,inverted,code", CONTROLS, ids=IDS)
def test_the_intact_artifact_is_usable(name, kind, intact, inverted, code):
    """Half one: without this, an inverted-half assertion could pass because the
    checker refuses everything."""
    report = validate_artifact(intact(), kind)
    assert report.is_usable, (name, report.codes)


@pytest.mark.parametrize("name,kind,intact,inverted,code", CONTROLS, ids=IDS)
def test_inverting_the_invariant_makes_the_artifact_unusable(
    name, kind, intact, inverted, code
):
    """Half two: without this, an intact-half assertion could pass because the
    checker accepts everything."""
    report = validate_artifact(inverted(), kind)
    assert not report.is_usable, (name, report.codes)
    assert report.has_code(code), (name, report.codes)


@pytest.mark.parametrize("name,kind,intact,inverted,code", CONTROLS, ids=IDS)
def test_the_inversion_changes_the_outcome_not_merely_the_findings(
    name, kind, intact, inverted, code
):
    before = validate_artifact(intact(), kind)
    after = validate_artifact(inverted(), kind)
    assert before.outcome is ValidationOutcome.VALID
    assert after.outcome in (
        ValidationOutcome.INVALID,
        ValidationOutcome.INDETERMINATE,
    )


def test_a_checker_that_accepted_everything_would_fail_these_controls():
    """The controls detect an always-accept checker, demonstrated rather than asserted."""

    def always_valid(_artifact, _kind):
        class _Report:
            is_usable = True
            outcome = ValidationOutcome.VALID
            codes = ()

            def has_code(self, _code):
                return False

        return _Report()

    caught = 0
    for _name, kind, _intact, inverted, code in CONTROLS:
        report = always_valid(inverted(), kind)
        if report.is_usable or not report.has_code(code):
            caught += 1
    assert caught == len(CONTROLS)


def test_a_checker_that_rejected_everything_would_fail_these_controls():
    """And the mirror image: an always-refuse checker fails the intact half."""

    def always_invalid(_artifact, _kind):
        class _Report:
            is_usable = False
            outcome = ValidationOutcome.INVALID

        return _Report()

    caught = sum(
        1 for _n, kind, intact, _i, _c in CONTROLS if not always_invalid(intact(), kind).is_usable
    )
    assert caught == len(CONTROLS)


def test_every_control_names_a_declared_finding_code():
    for _name, _kind, _intact, _inverted, code in CONTROLS:
        assert code in codes.ALL_CODES


def test_the_controls_cover_every_invariant_the_suite_claims():
    """A control table that silently loses a row stops protecting that invariant."""
    covered = {code for *_rest, code in CONTROLS}
    must_cover = {
        codes.MANDATORY_FIELD_MISSING,
        codes.MANDATORY_FIELD_AMBIGUOUS,
        codes.DIGEST_ABSENT,
        codes.DIGEST_MALFORMED,
        codes.DIGEST_MISMATCH,
        codes.SELF_RATIFICATION,
        codes.ARTIFACT_VERSION_MALFORMED,
        codes.SUCCESSION_VERSION_NOT_BUMPED,
        codes.SUCCESSION_LINEAGE_MISMATCH,
        codes.REQUIREMENT_ID_AMBIGUOUS,
        codes.REQUIREMENT_CONTRADICTORY,
        codes.REQUIREMENT_CONDITION_MISSING,
        codes.REQUIREMENT_UNRESOLVABLE,
        codes.OBLIGATION_CONTRADICTION,
        codes.DRAFT_IS_NOT_A_CONSTITUTION,
        codes.CONTRACT_CONTRADICTORY_BEHAVIOUR,
        codes.CONTRACT_NO_OBLIGATIONS,
        codes.SUBJECT_ENTRY_AMBIGUOUS,
    }
    assert must_cover <= covered, sorted(must_cover - covered)
