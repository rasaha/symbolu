"""Phase 4C slice 2: the run role, manifest v2, and the calibration contracts.

Fixtures are the existing deterministic pilot fixtures, adapted per test. The v1
compatibility anchor is a digest literal captured from the pre-change code, so a
regression that silently alters the historical payload cannot pass by recomputing it.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from ugence_governance_contracts.api import BenchmarkReference
from ugence_reasoning_method_governance.api import (
    ComparisonPolicy,
    ContractError,
    ResourceDimension,
    SufficiencyKind,
    SufficiencyRule,
    TaskClassIdentity,
)
from ugence_uvi_policy_contracts.api import ComparisonOperator, GovernedThreshold
from ugence_workflow_fit_pilot.api import (
    CALIBRATION_RESULT_SCHEMA_VERSION,
    PILOT_MANIFEST_SCHEMA_VERSION_V1,
    PILOT_MANIFEST_SCHEMA_VERSION_V2,
    CalibrationProvenance,
    CalibrationResult,
    PilotErrorCode,
    PilotRole,
    PilotRunRole,
    PilotStudyManifest,
)
from ugence_workflow_fit_pilot.errors import PilotError

import pilot_fixtures as pf

# Captured from the pre-slice-2 code. If the v1 canonical payload ever changes, this
# literal fails rather than following the implementation.
V1_MANIFEST_DIGEST_BEFORE_SLICE_2 = "de6f18598c1fe23d5b7940fb5fb012b07f8ffca462956a9ddf673fddde5b39c9"

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
DIGEST_C = "c" * 64
INSTANT = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- helpers


def _benchmark_threshold(manifest: PilotStudyManifest) -> GovernedThreshold:
    """A governed bar that names the benchmark instead of a number, so the engine's tau
    is None by construction."""
    return GovernedThreshold(
        "threshold.calibration",
        "score.unit",
        ComparisonOperator.GTE,
        benchmark_ref=BenchmarkReference(
            benchmark_id=manifest.benchmark.benchmark.benchmark_id,
            version=manifest.benchmark.benchmark.version,
            content_digest=manifest.benchmark.benchmark.content_digest,
        ),
    )


def _task_class_with(manifest: PilotStudyManifest, bar: GovernedThreshold) -> TaskClassIdentity:
    tc = manifest.plan.task_class
    policy = tc.comparison_policy
    rule = policy.sufficiency
    return dataclasses.replace(
        tc,
        task_class_digest="",
        comparison_policy=ComparisonPolicy(
            policy.policy_id,
            policy.policy_version,
            SufficiencyRule(rule.rule_id, rule.rule_version, SufficiencyKind.THRESHOLD_BASED, bar, rule.supporting_evidence_admission),
            policy.required_dimensions if policy.required_dimensions else (ResourceDimension.LLM_CALLS,),
            policy.quality_aggregation,
        ),
    )


def _provenance(**overrides) -> CalibrationProvenance:
    fields = dict(
        calibration_result_digest=DIGEST_A,
        calibration_manifest_digest=DIGEST_B,
        calibration_commitment_identifier="workflow_fit_prepared_index.calibration.v1",
        calibration_index_digest=DIGEST_C,
        formula_id="calfloor.linear_chain",
        formula_version="1",
        instantiated_literal="0.62",
    )
    fields.update(overrides)
    return CalibrationProvenance(**fields)


def _calibration_manifest(**overrides) -> PilotStudyManifest:
    """A v2 CALIBRATION manifest: one baseline method, benchmark-referenced bar, no
    provenance."""
    base = pf.manifest()
    baseline_assignment = [m for m in base.methods if PilotRole.GOVERNED_BASELINE in m.roles][0]
    tc = _task_class_with(base, _benchmark_threshold(base))
    plan = dataclasses.replace(base.plan, task_class=tc, recommended=(), plan_digest="")
    fields = dict(
        schema_version=PILOT_MANIFEST_SCHEMA_VERSION_V2,
        plan=plan,
        methods=(dataclasses.replace(baseline_assignment, roles=(PilotRole.GOVERNED_BASELINE,)),),
        advisory_digest=None,
        rule_set=None,
        run_role=PilotRunRole.CALIBRATION,
        calibration_provenance=None,
        manifest_digest="",
    )
    fields.update(overrides)
    return dataclasses.replace(base, **fields)


def _confirmatory_manifest(**overrides) -> PilotStudyManifest:
    base = pf.manifest()
    fields = dict(
        schema_version=PILOT_MANIFEST_SCHEMA_VERSION_V2,
        run_role=PilotRunRole.CONFIRMATORY,
        calibration_provenance=_provenance(),
        manifest_digest="",
    )
    fields.update(overrides)
    return dataclasses.replace(base, **fields)


def _calibration_result(**overrides) -> CalibrationResult:
    fields = dict(
        schema_version=CALIBRATION_RESULT_SCHEMA_VERSION,
        calibration_id="calibration.bbh-ld7.rep0",
        manifest_digest=DIGEST_A,
        evaluation_digest=DIGEST_B,
        attestation_digest=DIGEST_C,
        statistic_value="0.62",
        governed_unit="score.unit",
        score_count=50,
        sample_index_digest=DIGEST_A,
        commitment_identifier="workflow_fit_prepared_index.calibration.v1",
        index_digest=DIGEST_B,
        verdict_custody_ref="custody://verdicts/calibration",
        formula_id="calfloor.linear_chain",
        formula_version="1",
        issued_by="workflow-fit-pilot.runner",
        issued_at=INSTANT,
    )
    fields.update(overrides)
    return CalibrationResult(**fields)


# --------------------------------------------------------------------------- v1 compatibility


def test_v1_fixture_still_parses_and_keeps_its_historical_digest():
    manifest = pf.manifest()
    assert manifest.schema_version == PILOT_MANIFEST_SCHEMA_VERSION_V1
    assert manifest.manifest_digest == V1_MANIFEST_DIGEST_BEFORE_SLICE_2
    assert manifest.run_role is None and manifest.calibration_provenance is None


def test_v1_is_refused_as_phase_4c_eligible():
    with pytest.raises(PilotError) as excinfo:
        pf.manifest().require_phase_4c_eligible()
    assert excinfo.value.code is PilotErrorCode.RUN_ROLE_INVALID


def test_v1_cannot_carry_a_role_or_provenance():
    for extra in ({"run_role": PilotRunRole.CONFIRMATORY}, {"calibration_provenance": _provenance()}):
        with pytest.raises(PilotError) as excinfo:
            dataclasses.replace(pf.manifest(), manifest_digest="", **extra)
        assert excinfo.value.code is PilotErrorCode.RUN_ROLE_INVALID


def test_no_v1_to_v2_inference_occurs():
    with pytest.raises(PilotError) as excinfo:
        dataclasses.replace(pf.manifest(), schema_version=PILOT_MANIFEST_SCHEMA_VERSION_V2, manifest_digest="")
    assert excinfo.value.code is PilotErrorCode.RUN_ROLE_INVALID


@pytest.mark.parametrize("bad", ["workflow_fit_pilot.manifest.v3", "", "manifest.v2"])
def test_unknown_schema_versions_are_refused(bad):
    with pytest.raises(PilotError) as excinfo:
        dataclasses.replace(pf.manifest(), schema_version=bad, manifest_digest="")
    assert excinfo.value.code is PilotErrorCode.SCHEMA_VERSION_UNSUPPORTED


# --------------------------------------------------------------------------- v2 roles


def test_v2_accepts_a_valid_calibration_manifest():
    manifest = _calibration_manifest()
    assert manifest.run_role is PilotRunRole.CALIBRATION
    assert manifest.is_v2 and manifest.manifest_digest
    assert manifest.require_phase_4c_eligible() is manifest


def test_v2_accepts_a_valid_confirmatory_manifest():
    manifest = _confirmatory_manifest()
    assert manifest.run_role is PilotRunRole.CONFIRMATORY
    assert manifest.calibration_provenance is not None
    assert manifest.require_phase_4c_eligible() is manifest


@pytest.mark.parametrize("role", [None, "CALIBRATION", 1])
def test_v2_refuses_missing_and_unknown_roles(role):
    with pytest.raises(PilotError) as excinfo:
        _confirmatory_manifest(run_role=role)
    assert excinfo.value.code is PilotErrorCode.RUN_ROLE_INVALID


def test_calibration_refuses_a_literal_threshold():
    base = pf.manifest()  # the fixture task class carries a literal bar
    with pytest.raises(PilotError) as excinfo:
        _calibration_manifest(plan=dataclasses.replace(base.plan, recommended=(), plan_digest=""))
    assert excinfo.value.code is PilotErrorCode.ROLE_ARTIFACT_INCONSISTENT


def test_calibration_requires_a_benchmark_referenced_threshold():
    manifest = _calibration_manifest()
    bar = manifest.plan.task_class.comparison_policy.sufficiency.threshold
    assert bar.benchmark_ref is not None and not bar.literal_value


def test_calibration_refuses_provenance():
    with pytest.raises(PilotError) as excinfo:
        _calibration_manifest(calibration_provenance=_provenance())
    assert excinfo.value.code is PilotErrorCode.CALIBRATION_PROVENANCE_INVALID


def test_calibration_refuses_more_than_one_method():
    full = pf.manifest()
    with pytest.raises(PilotError) as excinfo:
        _calibration_manifest(
            methods=full.methods,
            advisory_digest=full.advisory_digest,
            rule_set=full.rule_set,
        )
    assert excinfo.value.code is PilotErrorCode.ROLE_ARTIFACT_INCONSISTENT


def test_calibration_refuses_a_challenger_role_on_its_single_assignment():
    manifest = _calibration_manifest()
    assignment = manifest.methods[0]
    with pytest.raises(PilotError) as excinfo:
        _calibration_manifest(methods=(dataclasses.replace(assignment, roles=(PilotRole.GOVERNED_BASELINE, PilotRole.CHALLENGER)),))
    assert excinfo.value.code is PilotErrorCode.ROLE_ARTIFACT_INCONSISTENT


def test_calibration_refuses_nonempty_recommendations():
    manifest = _calibration_manifest()
    plan = dataclasses.replace(manifest.plan, recommended=(manifest.plan.baseline,), plan_digest="")
    with pytest.raises(PilotError) as excinfo:
        _calibration_manifest(plan=plan)
    assert excinfo.value.code is PilotErrorCode.ROLE_ARTIFACT_INCONSISTENT


def test_confirmatory_requires_provenance():
    with pytest.raises(PilotError) as excinfo:
        _confirmatory_manifest(calibration_provenance=None)
    assert excinfo.value.code is PilotErrorCode.CALIBRATION_PROVENANCE_INVALID


def test_confirmatory_refuses_a_benchmark_referenced_threshold():
    base = pf.manifest()
    tc = _task_class_with(base, _benchmark_threshold(base))
    with pytest.raises(PilotError) as excinfo:
        _confirmatory_manifest(plan=dataclasses.replace(base.plan, task_class=tc, plan_digest=""))
    assert excinfo.value.code is PilotErrorCode.ROLE_ARTIFACT_INCONSISTENT


def test_role_and_provenance_participate_in_the_manifest_digest():
    confirmatory = _confirmatory_manifest()
    other_literal = _confirmatory_manifest(calibration_provenance=_provenance(instantiated_literal="0.64"))
    assert confirmatory.manifest_digest != other_literal.manifest_digest
    # the role is inside the digest too: a v2 confirmatory manifest and the v1 fixture it
    # was derived from cannot share a digest
    assert confirmatory.manifest_digest != pf.manifest().manifest_digest


# --------------------------------------------------------------------------- CalibrationResult


def test_calibration_result_round_trips_deterministically():
    first, second = _calibration_result(), _calibration_result()
    assert first == second
    assert first.calibration_result_digest == second.calibration_result_digest
    assert first.calibration_result_digest


@pytest.mark.parametrize(
    "override",
    [
        {"calibration_id": "calibration.other"},
        {"manifest_digest": DIGEST_C},
        {"evaluation_digest": DIGEST_A},
        {"attestation_digest": DIGEST_A},
        {"statistic_value": "0.64"},
        {"score_count": 49},
        {"sample_index_digest": DIGEST_C},
        {"commitment_identifier": "other.v1"},
        {"index_digest": DIGEST_C},
        {"verdict_custody_ref": "custody://other"},
        {"formula_id": "other"},
        {"formula_version": "2"},
        {"issued_by": "someone-else"},
        {"issued_at": datetime(2026, 9, 4, tzinfo=timezone.utc)},
    ],
)
def test_changing_any_governed_field_changes_the_result_digest(override):
    assert _calibration_result(**override).calibration_result_digest != _calibration_result().calibration_result_digest


@pytest.mark.parametrize(
    "override, code",
    [
        ({"schema_version": "workflow_fit_pilot.calibration_result.v2"}, PilotErrorCode.SCHEMA_VERSION_UNSUPPORTED),
        ({"governed_unit": "percent"}, PilotErrorCode.CALIBRATION_STATISTIC_UNAVAILABLE),
        ({"score_count": 0}, PilotErrorCode.COUNT_INVALID),
        ({"score_count": -1}, PilotErrorCode.COUNT_INVALID),
        ({"score_count": True}, PilotErrorCode.COUNT_INVALID),
    ],
)
def test_malformed_calibration_result_fields_fail_closed_with_pilot_errors(override, code):
    with pytest.raises(PilotError) as excinfo:
        _calibration_result(**override)
    assert excinfo.value.code is code


@pytest.mark.parametrize(
    "override",
    [
        {"calibration_id": "  "},
        {"manifest_digest": "not-a-digest"},
        {"evaluation_digest": DIGEST_A.upper()},
        {"attestation_digest": ""},
        {"statistic_value": "NaN"},
        {"statistic_value": "Infinity"},
        {"statistic_value": "zero"},
        {"statistic_value": ""},
        {"statistic_value": 0.62},
        {"sample_index_digest": "abc"},
        {"commitment_identifier": ""},
        {"verdict_custody_ref": " "},
        {"formula_id": ""},
        {"formula_version": ""},
        {"issued_by": ""},
        {"issued_at": datetime(2026, 9, 3, 12, 0)},
    ],
)
def test_malformed_calibration_result_fields_fail_closed_with_contract_errors(override):
    with pytest.raises((ContractError, PilotError)):
        _calibration_result(**override)


def test_calibration_result_refuses_unknown_keys():
    with pytest.raises(TypeError):
        _calibration_result(unexpected_key="x")


def test_calibration_result_does_not_duplicate_transitively_bound_fields():
    names = {f.name for f in dataclasses.fields(CalibrationResult)}
    for redundant in ("method", "benchmark_manifest_digest", "evaluator_identity", "scoring_instruction_digest", "run_id", "case_set_digest"):
        assert redundant not in names


# --------------------------------------------------------------------------- CalibrationProvenance


def test_provenance_round_trips_and_compares_by_value():
    assert _provenance() == _provenance()


@pytest.mark.parametrize(
    "override",
    [
        {"calibration_result_digest": "short"},
        {"calibration_manifest_digest": ""},
        {"calibration_index_digest": DIGEST_A.upper()},
        {"calibration_commitment_identifier": " "},
        {"formula_id": ""},
        {"formula_version": ""},
        {"instantiated_literal": "NaN"},
        {"instantiated_literal": "Infinity"},
        {"instantiated_literal": "-Infinity"},
        {"instantiated_literal": ""},
        {"instantiated_literal": 0.62},
    ],
)
def test_provenance_fails_closed_on_malformed_fields(override):
    with pytest.raises(ContractError):
        _provenance(**override)


def test_provenance_refuses_unknown_keys():
    with pytest.raises(TypeError):
        _provenance(unexpected_key="x")


def test_provenance_literal_is_a_canonical_decimal_string():
    assert Decimal(_provenance().instantiated_literal) == Decimal("0.62")


# --------------------------------------------------------------------------- vocabulary


def test_refusal_vocabulary_is_exactly_forty_four_members_with_the_eleven_additions():
    names = [c.name for c in PilotErrorCode]
    assert len(names) == 44
    assert len(set(names)) == 44
    for added in (
        "PROVIDER_IDENTITY_UNVERIFIED",
        "RETENTION_WRITE_FAILED",
        "RETENTION_VERIFY_FAILED",
        "EVALUATION_FAILED",
        "COMMITMENT_ALREADY_SPENT",
        "COMMITMENT_REGISTRY_UNAVAILABLE",
        "WORKFLOW_BUDGET_EXHAUSTED",
        "RUN_ROLE_INVALID",
        "ROLE_ARTIFACT_INCONSISTENT",
        "CALIBRATION_PROVENANCE_INVALID",
        "CALIBRATION_STATISTIC_UNAVAILABLE",
    ):
        assert added in names
    # ROLE_INCONSISTENT keeps its original meaning and is not reused for run-role failures
    assert "ROLE_INCONSISTENT" in names


def test_run_role_has_exactly_two_members():
    assert [r.value for r in PilotRunRole] == ["CALIBRATION", "CONFIRMATORY"]
