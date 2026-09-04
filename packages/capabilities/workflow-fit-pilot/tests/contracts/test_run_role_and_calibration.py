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
from ugence_workflow_fit_pilot._canon import digest_of
import ugence_workflow_fit_pilot
from ugence_reasoning_method_governance.api import (
    ComparisonPolicy,
    ContractError,
    ContractErrorCode,
    ResourceDimension,
    SamplingKind,
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
    validate_manifest,
)
from ugence_workflow_fit_pilot.contracts.calibration import require_canonical_decimal
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


def test_a_wrong_governed_unit_retains_the_ratified_code_with_its_limitation_recorded():
    """F5, revision 16. The statistic is present and only its unit is wrong, so this code
    is a semantic stretch — but the precise name, UNIT_MISMATCH, belongs to RefusalCode,
    the engine's evaluation-time vocabulary that ContractError cannot carry. Adding a code
    was forbidden, so the ratified code stands and the limitation is documented."""
    assert "UNIT_MISMATCH" not in {c.name for c in ContractErrorCode}
    with pytest.raises(PilotError) as excinfo:
        _calibration_result(governed_unit="percent")
    assert excinfo.value.code is PilotErrorCode.CALIBRATION_STATISTIC_UNAVAILABLE


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


# --------------------------------------------------------------------------- F1: role-aware validation


def test_a_calibration_manifest_passes_both_its_contract_and_validate_manifest():
    """F1, ratified in revision 16: a manifest its contract accepts must also pass the
    package's own §3.1 validator. Before the correction this combination was refused with
    COMPOSITION_INCOMPLETE, so the calibration shape was constructible but unusable."""
    manifest = _calibration_manifest()
    assert manifest.plan.challengers.kind is SamplingKind.PREREGISTERED
    validated = validate_manifest(manifest, catalog=pf.catalog(), rule_set=pf.rule_set())
    assert validated.manifest_digest == manifest.manifest_digest


@pytest.mark.parametrize("kind", [SamplingKind.RISK_BASED, SamplingKind.RANDOMIZED])
def test_calibration_refuses_a_sampled_composition(kind):
    """The baseline-only set was fixed before execution, so PREREGISTERED is the truthful
    value; risk-based or randomized would misdescribe a composition never sampled."""
    base = _calibration_manifest()
    plan = dataclasses.replace(
        base.plan, challengers=dataclasses.replace(base.plan.challengers, kind=kind), plan_digest=""
    )
    with pytest.raises(PilotError) as excinfo:
        _calibration_manifest(plan=plan)
    assert excinfo.value.code is PilotErrorCode.ROLE_ARTIFACT_INCONSISTENT


def test_confirmatory_preregistered_completeness_is_unchanged():
    """The exhaustive rule still applies to a v2 CONFIRMATORY manifest: dropping an
    admissible method must still be refused."""
    full = _confirmatory_manifest()
    validate_manifest(full, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=pf.advisory())
    baseline_only = _confirmatory_manifest(
        methods=tuple(m for m in full.methods if PilotRole.GOVERNED_BASELINE in m.roles),
        advisory_digest=None,
        rule_set=None,
        plan=dataclasses.replace(full.plan, recommended=(), plan_digest=""),
    )
    with pytest.raises(PilotError) as excinfo:
        validate_manifest(baseline_only, catalog=pf.catalog(), rule_set=pf.rule_set())
    assert excinfo.value.code is PilotErrorCode.COMPOSITION_INCOMPLETE


def test_v1_validation_is_untouched_by_the_role_branch():
    v1 = pf.manifest()
    validated = validate_manifest(v1, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=pf.advisory())
    assert validated.manifest_digest == V1_MANIFEST_DIGEST_BEFORE_SLICE_2


# --------------------------------------------------------------------------- F2: canonical decimals

CANONICAL = ["0", "1", "0.62", "-0.25", "12", "1.5", "-3", "100", "0.5"]
NONCANONICAL = ["0.620", "+0.62", "6.2E-1", "00.62", "0.0", "-0", "6.2e-1", " 0.62", "0.62 ", ".62", "62.", "", "  ", "NaN", "Infinity", "-Infinity", "zero", "1_0", "-00.5", "0.10"]


@pytest.mark.parametrize("value", CANONICAL)
def test_canonical_decimals_are_accepted(value):
    assert require_canonical_decimal(value, "field") == Decimal(value)
    assert _provenance(instantiated_literal=value).instantiated_literal == value


@pytest.mark.parametrize("value", NONCANONICAL)
def test_noncanonical_decimals_are_refused_never_normalized(value):
    for call in (
        lambda: require_canonical_decimal(value, "field"),
        lambda: _provenance(instantiated_literal=value),
        lambda: _calibration_result(statistic_value=value),
    ):
        with pytest.raises(ContractError) as excinfo:
            call()
        assert excinfo.value.code is ContractErrorCode.DECIMAL_UNPARSEABLE


@pytest.mark.parametrize("value", [0.62, 62, Decimal("0.62"), None, True])
def test_non_string_decimals_are_refused(value):
    with pytest.raises(ContractError) as excinfo:
        require_canonical_decimal(value, "field")
    assert excinfo.value.code is ContractErrorCode.DECIMAL_UNPARSEABLE


@pytest.mark.parametrize("bad", ["0.900", "+0.9", "9E-1"])
def test_a_confirmatory_threshold_literal_must_be_canonical(bad):
    base = pf.manifest()
    tc = _task_class_with(base, GovernedThreshold("study.hard.tau", "score.unit", ComparisonOperator.GTE, bad))
    with pytest.raises(ContractError) as excinfo:
        _confirmatory_manifest(plan=dataclasses.replace(base.plan, task_class=tc, plan_digest=""))
    assert excinfo.value.code is ContractErrorCode.DECIMAL_UNPARSEABLE


def test_equivalent_canonical_spellings_are_distinct_digests_so_code_point_equality_is_safe():
    """Slice 3 compares these strings by exact code-point equality. That is only sound
    because one value has exactly one admissible spelling — proven here by the fact that
    the alternative spellings cannot be constructed at all."""
    literal = _provenance().instantiated_literal
    assert require_canonical_decimal(literal, "literal") == Decimal(literal)
    with pytest.raises(ContractError):
        _provenance(instantiated_literal=literal + "0")


def test_canonical_strings_participate_in_result_provenance_and_manifest_digests():
    a, b = _calibration_result(), _calibration_result(statistic_value="0.63")
    assert a.calibration_result_digest != b.calibration_result_digest
    p, q = _provenance(), _provenance(instantiated_literal="0.63")
    assert p != q
    assert _confirmatory_manifest(calibration_provenance=p).manifest_digest != _confirmatory_manifest(
        calibration_provenance=q
    ).manifest_digest


def test_v1_decimal_behaviour_is_unchanged():
    """The canonical rule is Phase 4C's own. A v1 manifest carries the same threshold
    literal it always did, is validated exactly as before, and keeps its digest."""
    v1 = pf.manifest()
    assert v1.plan.task_class.comparison_policy.sufficiency.threshold.literal_value == "0.9"
    assert v1.manifest_digest == V1_MANIFEST_DIGEST_BEFORE_SLICE_2
    # a v1 manifest whose literal is non-canonical is still accepted: the rule is not retroactive
    tc = pf.task_class(threshold="0.900")
    plan = dataclasses.replace(v1.plan, task_class=tc, plan_digest="")
    legacy = dataclasses.replace(v1, plan=plan, manifest_digest="")
    assert legacy.schema_version == PILOT_MANIFEST_SCHEMA_VERSION_V1
    assert legacy.plan.task_class.comparison_policy.sufficiency.threshold.literal_value == "0.900"


# --------------------------------------------------------------------------- F3 / F4 enforcement (slice 3B-1)


def test_f3_eligibility_is_now_enforced_at_the_phase_4c_entry_point():
    """The inverse of the slice-2 test that pinned F3 as unenforced. Slice 3B-1 wires
    require_phase_4c_eligible into run_phase_4c_pilot, so the caller list must be non-empty
    and must name the runner."""
    import ast
    import pathlib

    src = pathlib.Path(ugence_workflow_fit_pilot.__file__).parent
    callers = []
    for path in sorted(src.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            called = isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            if called and node.func.attr == "require_phase_4c_eligible":
                callers.append(path.name)
    assert "runner.py" in callers, f"F3 is not enforced at the run entry point; callers={callers}"
    with pytest.raises(PilotError):
        pf.manifest().require_phase_4c_eligible()


def test_run_pilot_itself_stays_ungated_for_historical_mechanism_validation():
    """Revision 20: run_pilot remains available for historical tests. The gate lives in the
    separately named Phase 4C entry point, so this must not become an alias."""
    import inspect

    from ugence_workflow_fit_pilot.runner import run_phase_4c_pilot, run_pilot

    assert run_phase_4c_pilot is not run_pilot
    assert "require_phase_4c_eligible" not in inspect.getsource(run_pilot)
    assert "require_phase_4c_eligible" in inspect.getsource(run_phase_4c_pilot)


def test_the_phase_4c_entry_point_refuses_a_v1_manifest_before_starting_a_boundary():
    """A v1 manifest is refused, never upgraded. Refusal happens before any boundary process
    exists, so the absence of executor/scorer arguments cannot be what raises."""
    from ugence_workflow_fit_pilot.runner import run_phase_4c_pilot

    with pytest.raises(PilotError) as e:
        run_phase_4c_pilot(pf.manifest())
    assert e.value.code is PilotErrorCode.RUN_ROLE_INVALID


def test_f4_role_revalidation_refuses_a_v1_manifest_carrying_a_smuggled_role():
    """F4: the v1 digest payload excludes run_role, so a tampered v1 object keeps a digest
    that still verifies. Re-running the role validation through the constructor catches it;
    recomputing the digest alone would not."""
    v1 = pf.manifest()
    object.__setattr__(v1, "run_role", PilotRunRole.CALIBRATION)
    # The tampered object still passes a naive digest recomputation, which is the whole point.
    assert v1.manifest_digest == digest_of(v1, exclude=("manifest_digest", "run_role", "calibration_provenance"))
    with pytest.raises(PilotError):
        v1.revalidate_role()


def test_f4_role_revalidation_accepts_untampered_manifests():
    for manifest in (pf.manifest(), _calibration_manifest(), _confirmatory_manifest()):
        assert manifest.revalidate_role() is manifest


def test_f4_role_revalidation_refuses_a_tampered_digest_bearing_field():
    v2 = _calibration_manifest()
    object.__setattr__(v2, "manifest_id", "manifest.pilot.tampered")
    with pytest.raises(PilotError, match="does not cover the manifest's own content"):
        v2.revalidate_role()


# --------------------------------------------------------------------------- slice 3B-0: lifecycle endpoint


def _calibration_result_for(manifest, **overrides):
    from datetime import datetime, timezone

    from ugence_workflow_fit_pilot.contracts.calibration import CalibrationResult

    kwargs = dict(
        schema_version="workflow_fit_pilot.calibration_result.v1",
        calibration_id="cal.1", manifest_digest=manifest.manifest_digest,
        evaluation_digest="b" * 64, attestation_digest="c" * 64,
        statistic_value="0.62", governed_unit="score.unit", score_count=50,
        sample_index_digest="d" * 64, commitment_identifier="workflow_fit_prepared_index.calibration.v1",
        index_digest="e" * 64, verdict_custody_ref="memory://workflow-fit-test/endpoint",
        formula_id="calfloor.linear_chain", formula_version="1", issued_by="tester",
        issued_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    kwargs.update(overrides)
    return CalibrationResult(**kwargs)


def _under_test_record(manifest):
    from datetime import datetime, timezone

    from ugence_workflow_fit_pilot.contracts.lifecycle import LifecycleEvent, propose, transition

    method = manifest.methods[0].method
    at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    proposed = propose(manifest, method, recorded_by="tester", recorded_at=at)
    return transition(proposed, LifecycleEvent.OBSERVATION_VALIDATED, manifest=manifest, recorded_by="tester", recorded_at=at)


def test_is_calibration_run_never_reinterprets_a_v1_manifest():
    from ugence_workflow_fit_pilot.contracts.lifecycle import is_calibration_run

    assert is_calibration_run(_calibration_manifest()) is True
    assert is_calibration_run(_confirmatory_manifest()) is False
    assert is_calibration_run(pf.manifest()) is False  # v1: no committed role


def test_a_calibration_run_at_under_test_with_a_bound_result_is_a_completed_calibration():
    from ugence_workflow_fit_pilot.contracts.lifecycle import require_calibration_endpoint

    manifest = _calibration_manifest()
    require_calibration_endpoint(
        _under_test_record(manifest), manifest=manifest, calibration_result=_calibration_result_for(manifest)
    )


def test_a_calibration_run_at_under_test_without_a_result_is_not_a_completed_calibration():
    from ugence_workflow_fit_pilot.contracts.lifecycle import require_calibration_endpoint

    manifest = _calibration_manifest()
    with pytest.raises(PilotError) as e:
        require_calibration_endpoint(_under_test_record(manifest), manifest=manifest, calibration_result=None)
    assert e.value.code is PilotErrorCode.ROLE_ARTIFACT_INCONSISTENT


def test_a_calibration_result_for_another_manifest_does_not_end_this_run():
    from ugence_workflow_fit_pilot.contracts.lifecycle import require_calibration_endpoint

    manifest = _calibration_manifest()
    other = _calibration_result_for(manifest, manifest_digest="f" * 64)
    with pytest.raises(PilotError) as e:
        require_calibration_endpoint(_under_test_record(manifest), manifest=manifest, calibration_result=other)
    assert e.value.code is PilotErrorCode.MANIFEST_MISMATCH


def test_a_proposed_record_is_not_a_completed_calibration():
    from datetime import datetime, timezone

    from ugence_workflow_fit_pilot.contracts.lifecycle import propose, require_calibration_endpoint

    manifest = _calibration_manifest()
    proposed = propose(manifest, manifest.methods[0].method, recorded_by="t", recorded_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    with pytest.raises(PilotError, match="ends successfully at UNDER_TEST"):
        require_calibration_endpoint(proposed, manifest=manifest, calibration_result=_calibration_result_for(manifest))


def test_the_endpoint_rule_does_not_apply_to_a_confirmatory_run():
    from ugence_workflow_fit_pilot.contracts.lifecycle import require_calibration_endpoint

    manifest = _confirmatory_manifest()
    with pytest.raises(PilotError, match="applies only to a v2 manifest committed to CALIBRATION"):
        require_calibration_endpoint(_under_test_record(manifest), manifest=manifest, calibration_result=None)


def test_a_calibration_run_never_emits_result_assessed():
    from ugence_workflow_fit_pilot.contracts.lifecycle import LifecycleEvent, transition

    manifest = _calibration_manifest()
    with pytest.raises(PilotError, match="never emits RESULT_ASSESSED and never becomes EVALUATED"):
        transition(
            _under_test_record(manifest), LifecycleEvent.RESULT_ASSESSED, manifest=manifest,
            result=None, recorded_by="t", recorded_at=_under_test_record(manifest).recorded_at,
        )


def test_a_hand_built_evaluated_record_on_a_calibration_manifest_fails_replay():
    """transition() would never produce it; validate_lineage refuses it on replay too."""
    from dataclasses import replace as dc_replace

    from ugence_workflow_fit_pilot.contracts.lifecycle import PilotConfigurationState, validate_lineage

    from ugence_reasoning_method_governance.api import FitOutcome

    manifest = _calibration_manifest()
    under_test = _under_test_record(manifest)
    # A bare state swap is refused by the record constructor, so the forgery is built with the
    # full EVALUATED shape it demands. Only the run role then stands between it and replay.
    forged = dc_replace(
        under_test, state=PilotConfigurationState.EVALUATED,
        fit_outcome=FitOutcome.SUFFICIENT_PARETO_EFFICIENT, result_digest="a" * 64, state_digest="",
    )
    with pytest.raises(PilotError, match="never becomes EVALUATED"):
        validate_lineage([forged], [manifest])
