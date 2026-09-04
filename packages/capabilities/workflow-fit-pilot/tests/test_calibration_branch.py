"""Slice 3B-2: the calibration runner branch and test-only CalibrationResult production.

Revision 20 ruling 3: every CalibrationResult built here uses the in-memory double and is
never genuine custody evidence. No adapter, endpoint, credential or provider is exercised.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

_TESTS = Path(__file__).resolve().parent
for _p in (_TESTS, _TESTS / "contracts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import test_run_role_and_calibration as slice2  # noqa: E402

from ugence_workflow_fit_pilot.custody import (  # noqa: E402
    InMemoryVerdictCustody,
    VerdictCustodyRecord,
    VerifiedPreparedFacts,
    build_calibration_result,
)
from ugence_workflow_fit_pilot.errors import PilotError, PilotErrorCode  # noqa: E402

AT = datetime(2026, 1, 1, tzinfo=timezone.utc)
REF = "memory://workflow-fit-test/verdicts/rep0"
INDEX, SAMPLE = "1" * 64, "2" * 64
CASE_A, CASE_B = "a" * 64, "b" * 64


def _facts(manifest, **overrides) -> VerifiedPreparedFacts:
    kwargs = dict(
        commitment_identifier="workflow_fit_prepared_index.calibration.v1",
        index_digest=INDEX, sample_index_digest=SAMPLE,
        verdict_custody_ref=REF, manifest_digest=manifest.manifest_digest,
        case_digests=(CASE_A, CASE_B),
    )
    kwargs.update(overrides)
    return VerifiedPreparedFacts(**kwargs)


def _custody_record(manifest, **overrides) -> VerdictCustodyRecord:
    kwargs = dict(custody_ref=REF, manifest_digest=manifest.manifest_digest, index_digest=INDEX,
                  verdicts=((CASE_A, "correct"), (CASE_B, "incorrect")))
    kwargs.update(overrides)
    return VerdictCustodyRecord(**kwargs)


def _build(manifest, port, *, facts=None, record=None, **overrides):
    kwargs = dict(
        prepared=facts or _facts(manifest), custody=port, custody_record=record or _custody_record(manifest),
        calibration_id="cal.1", evaluation_digest="3" * 64, attestation_digest="4" * 64,
        # G2a: score_count must equal the number of verdicts in the custody record.
        statistic_value="0.62", score_count=2, formula_id="calfloor.linear_chain",
        formula_version="1", issued_by="tester", issued_at=AT,
    )
    kwargs.update(overrides)
    return build_calibration_result(**kwargs)


# --------------------------------------------------------------------------- prepared facts


def test_the_three_digests_stay_strictly_distinct():
    manifest = slice2._calibration_manifest()
    with pytest.raises(PilotError, match="strictly distinct"):
        _facts(manifest, sample_index_digest=INDEX)


def test_prepared_facts_require_real_digests_and_a_reference():
    from ugence_reasoning_method_governance.errors import ContractError

    manifest = slice2._calibration_manifest()
    with pytest.raises(ContractError, match="64 lowercase hex characters"):
        _facts(manifest, index_digest="short")
    with pytest.raises(ContractError, match="must be a non-blank string"):
        _facts(manifest, verdict_custody_ref="   ")


# --------------------------------------------------------------------------- custody gating


def test_a_calibration_result_is_produced_only_after_a_verified_custody_write():
    manifest = slice2._calibration_manifest()
    port = InMemoryVerdictCustody()
    result = _build(manifest, port)
    assert result.verdict_custody_ref == REF
    assert result.index_digest == INDEX and result.sample_index_digest == SAMPLE
    assert result.manifest_digest == manifest.manifest_digest
    assert port.written_references() == (REF,)  # the write really happened


def test_no_calibration_result_when_the_custody_write_fails():
    class RefusingWriter:
        def write(self, record):
            raise PilotError(PilotErrorCode.RETENTION_WRITE_FAILED, "store unavailable")

        def read_back(self, custody_ref):  # pragma: no cover - never reached
            raise AssertionError("read_back must not run after a write failure")

    manifest = slice2._calibration_manifest()
    with pytest.raises(PilotError) as e:
        _build(manifest, RefusingWriter())
    assert e.value.code is PilotErrorCode.RETENTION_WRITE_FAILED


def test_no_calibration_result_when_the_read_back_does_not_verify():
    manifest = slice2._calibration_manifest()

    class LyingStore:
        def write(self, record):
            return record.record_digest

        def read_back(self, custody_ref):
            return _custody_record(manifest, verdicts=((CASE_A, "incorrect"), (CASE_B, "correct")))

    with pytest.raises(PilotError) as e:
        _build(manifest, LyingStore())
    assert e.value.code is PilotErrorCode.RETENTION_VERIFY_FAILED


def test_a_custody_record_at_another_reference_is_refused_before_any_write():
    manifest = slice2._calibration_manifest()
    port = InMemoryVerdictCustody()
    with pytest.raises(PilotError, match="not addressed at the reference the prepared bundle committed"):
        _build(manifest, port, record=_custody_record(manifest, custody_ref="memory://workflow-fit-test/elsewhere"))
    assert port.written_references() == ()  # refused before writing anything


def test_a_custody_record_binding_another_bundle_is_refused_before_any_write():
    manifest = slice2._calibration_manifest()
    port = InMemoryVerdictCustody()
    with pytest.raises(PilotError, match="does not bind the prepared bundle's manifest and index digests"):
        _build(manifest, port, record=_custody_record(manifest, index_digest="9" * 64))
    assert port.written_references() == ()


def test_the_governed_unit_is_not_caller_supplied():
    """score.unit is fixed by the contract; build_calibration_result takes no unit argument."""
    import inspect

    assert "governed_unit" not in inspect.signature(build_calibration_result).parameters
    manifest = slice2._calibration_manifest()
    assert _build(manifest, InMemoryVerdictCustody()).governed_unit == "score.unit"


# --------------------------------------------------------------------------- the runner branch


def test_the_calibration_branch_builds_no_comparison_and_no_coverage():
    """Revision 13's role matrix: under CALIBRATION the comparison is unconstructible and
    coverage is absent, which makes a success summary impossible rather than empty.

    Asserted over the AST of the branch body, not its source text: a comment mentioning
    RESULT_ASSESSED must not be able to pass or fail this test."""
    import ast
    import inspect
    import textwrap

    from ugence_workflow_fit_pilot import runner

    tree = ast.parse(textwrap.dedent(inspect.getsource(runner.run_pilot)))
    fn = tree.body[0]
    branch = next(
        n for n in fn.body
        if isinstance(n, ast.If) and isinstance(n.test, ast.Call)
        and getattr(n.test.func, "id", None) == "is_calibration_run"
    )
    called = {
        n.func.id for n in ast.walk(branch)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "compare" not in called
    assert "build_coverage_report" not in called
    assert "transition" not in called
    assert "PilotRunResult" in called
    names = {n.attr for n in ast.walk(branch) if isinstance(n, ast.Attribute)}
    assert "RESULT_ASSESSED" not in names
    # The branch returns immediately: nothing downstream can reintroduce comparison.
    assert any(isinstance(n, ast.Return) for n in branch.body)
    call = next(n for n in ast.walk(branch) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "PilotRunResult")
    request_arg, result_arg, coverage_arg = call.args[3], call.args[4], call.args[6]
    assert all(isinstance(a, ast.Constant) and a.value is None for a in (request_arg, result_arg, coverage_arg))


def test_a_success_summary_has_no_coverage_report_to_permit_it_under_calibration():
    """Revision 24. This previously asserted `(AttributeError, TypeError)` and so codified an
    untyped crash as the guarantee, which revision 22 then described as a design property.

    The real guarantee is upstream and typed: `render` refuses a calibration result with
    ROLE_ARTIFACT_INCONSISTENT, so `success_summary` is never reached with None on any
    commissioned path. `success_summary` itself is a pure function that dereferences its
    argument (contracts/coverage.py:97) and is not the guard; calling it with None directly
    is a caller error, asserted here only to pin that it has not silently acquired a guard
    of its own."""
    from ugence_workflow_fit_pilot.contracts.coverage import success_summary
    from ugence_workflow_fit_pilot.report import render
    from ugence_workflow_fit_pilot.runner import PilotRunResult

    manifest = slice2._calibration_manifest()
    calibration_result = PilotRunResult(
        manifest=manifest, validated=None, runs=(), request=None, result=None,
        states=(), coverage=None, outcomes={}, evaluator_flags=(),
    )
    with pytest.raises(PilotError) as e:
        render(calibration_result)
    assert e.value.code is PilotErrorCode.ROLE_ARTIFACT_INCONSISTENT

    with pytest.raises(AttributeError):
        success_summary(None, manifest, {})


def test_confirmatory_and_v1_runs_keep_the_comparison_path():
    """The branch must not change historical behaviour: only a v2 CALIBRATION manifest takes it."""
    from ugence_workflow_fit_pilot.contracts.lifecycle import is_calibration_run

    import pilot_fixtures as pf

    assert is_calibration_run(slice2._calibration_manifest()) is True
    assert is_calibration_run(slice2._confirmatory_manifest()) is False
    assert is_calibration_run(pf.manifest()) is False


# --------------------------------------------------------------------------- slice 3B-3: G5 and G3


def test_a_calibration_run_executes_without_the_agentic_tree(tmp_path):
    """G5. `tests/pilot/test_end_to_end.py` proves the calibration branch behaviourally, but
    sits behind a module-level importorskip on the agentic tree, so on a minimal install the
    branch fell back to the AST assertion alone. This gives the same behavioural coverage
    through FakeExecutor, which imports nothing outside this package's own fixtures."""
    import pilot_fixtures as pf
    from ugence_workflow_fit_pilot.contracts.lifecycle import PilotConfigurationState, validate_lineage
    from ugence_workflow_fit_pilot.runner import run_phase_4c_pilot, run_pilot

    manifest = slice2._calibration_manifest()
    kwargs = dict(
        catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=None, cases=pf.cases(),
        executor=pf.FakeExecutor({"linear_chain": 1}), scorer=pf.KeywordScorer(),
        identity=pf.IDENTITY, provider_factory="stub_provider:make_provider",
        now=pf.clock(), boundary_env=pf.boundary_env(),
    )

    res = run_pilot(manifest, **kwargs)
    assert all(r.complete for r in res.runs), [(r.method.method_id, r.reasons) for r in res.runs]
    assert res.request is None and res.result is None and res.coverage is None and res.outcomes == {}
    assert [s.state for s in res.states] == [PilotConfigurationState.PROPOSED, PilotConfigurationState.UNDER_TEST]
    validate_lineage(res.states, [manifest])

    gated = run_phase_4c_pilot(manifest, **kwargs)
    assert gated.request is None and gated.coverage is None


def test_the_phase_4c_study_never_calls_the_ungated_runner():
    """G3 tripwire. `run_pilot` is ungated by ruling and stays available for historical
    mechanism-validation tests, so nothing structurally forces a future Phase 4C pipeline to
    choose `run_phase_4c_pilot`.

    This is **vacuously true today**: `experiments/workflow_fit_study` contains no runner call
    at all, because the Phase 4C pipeline does not exist yet. It is a tripwire for when it
    does, not evidence that the gate is mandatory — G3 stays open until a pipeline exists and
    calls the gated entry point."""
    import ast
    import pathlib

    study = pathlib.Path(__file__).resolve().parents[4] / "experiments" / "workflow_fit_study"
    assert study.is_dir(), study
    offenders = []
    for path in sorted(study.rglob("*.py")):
        tree = ast.parse(path.read_text())
        # Revision 26: bare-name matching alone let `runner.run_pilot(...)`,
        # `api.run_pilot(...)`, an aliased import and a rebound variable through. Collect the
        # local names bound to run_pilot, then flag calls through any of them or through any
        # attribute access named run_pilot.
        aliases = {"run_pilot"}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                aliases |= {a.asname or a.name for a in node.names if a.name == "run_pilot"}
            elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Name) and node.value.id in aliases:
                aliases |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            hit = (isinstance(f, ast.Name) and f.id in aliases) or (isinstance(f, ast.Attribute) and f.attr == "run_pilot")
            if hit:
                offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == [], f"Phase 4C study calls the ungated run_pilot at {offenders}; use run_phase_4c_pilot"


def test_a_confirmatory_run_accepts_a_real_comparison_result():
    """Revision 26. The test this replaces passed `result=None`, so the G4 guard could not
    fire for any role and it asserted a refusal while claiming to show acceptance — vacuous
    for its stated purpose. This obtains a real ReadinessComparisonResult by running a
    confirmatory manifest through the boundary, and asserts the transition SUCCEEDS."""
    import pilot_fixtures as pf
    from ugence_workflow_fit_pilot.contracts.lifecycle import (
        LifecycleEvent, PilotConfigurationState, propose, transition,
    )
    from ugence_reasoning_method_governance.api import ReadinessComparisonResult
    from ugence_workflow_fit_pilot.runner import run_pilot

    manifest = slice2._confirmatory_manifest()
    res = run_pilot(
        manifest, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=pf.advisory(manifest.plan.task_class),
        cases=pf.cases(), executor=pf.FakeExecutor({m.method.method_id: 1 for m in manifest.methods}),
        scorer=pf.KeywordScorer(), identity=pf.IDENTITY, provider_factory="stub_provider:make_provider",
        now=pf.clock(), boundary_env=pf.boundary_env(),
    )
    assert isinstance(res.result, ReadinessComparisonResult)

    method = manifest.methods[0].method
    at = res.states[0].recorded_at
    under_test = transition(
        propose(manifest, method, recorded_by="t", recorded_at=at),
        LifecycleEvent.OBSERVATION_VALIDATED, manifest=manifest, recorded_by="t", recorded_at=at,
    )
    outcome = next((a.outcome for a in res.result.assessments if a.method == method), None)
    event = LifecycleEvent.RESULT_ASSESSED if outcome is not None and outcome.name.startswith(("SUFFICIENT", "INSUFFICIENT")) else LifecycleEvent.RESULT_INCONCLUSIVE
    out = transition(under_test, event, manifest=manifest, result=res.result, recorded_by="t", recorded_at=at)
    assert out.result_digest == res.result.result_digest
    assert out.state in (PilotConfigurationState.EVALUATED, PilotConfigurationState.INCONCLUSIVE)


# --------------------------------------------------------------------------- revision 27: G1 and G2


def test_score_count_must_equal_the_custody_verdict_count():
    """G2a. Catches a truncated or partial custody write before any result is built."""
    manifest = slice2._calibration_manifest()
    port = InMemoryVerdictCustody()
    with pytest.raises(PilotError, match="holds 2 verdicts but score_count is 3") as e:
        _build(manifest, port, score_count=3)
    assert e.value.code is PilotErrorCode.RETENTION_VERIFY_FAILED
    assert port.written_references() == ()  # refused before writing


def test_custody_verdicts_must_cover_exactly_the_prepared_case_set():
    """G2b. The sampled subset the run executed is authoritative — neither a different set of
    the same size nor a partial cover is accepted."""
    manifest = slice2._calibration_manifest()
    other = "c" * 64
    for facts, record in (
        # right count, wrong case
        (_facts(manifest, case_digests=(CASE_A, other)), _custody_record(manifest)),
        # verdicts cover only part of the prepared set: three cases prepared, two scored
        (_facts(manifest, case_digests=(CASE_A, CASE_B, other)), _custody_record(manifest)),
    ):
        port = InMemoryVerdictCustody()
        with pytest.raises(PilotError) as e:
            _build(manifest, port, facts=facts, record=record,
                   score_count=len(record.verdicts))
        assert e.value.code is PilotErrorCode.RETENTION_VERIFY_FAILED
        assert port.written_references() == ()


def test_prepared_facts_require_a_non_empty_duplicate_free_case_set():
    manifest = slice2._calibration_manifest()
    with pytest.raises(PilotError, match="non-empty case set"):
        _facts(manifest, case_digests=())
    with pytest.raises(PilotError, match="repeats a case"):
        _facts(manifest, case_digests=(CASE_A, CASE_A))


def test_validate_lineage_re_runs_role_validation_on_every_supplied_manifest():
    """G1b. The replay verifier no longer trusts run_role: a v1 manifest whose role was set by
    circumventing the frozen dataclass keeps a digest that still verifies, and is refused here."""
    import pilot_fixtures as pf
    from ugence_workflow_fit_pilot.contracts.calibration import PilotRunRole
    from ugence_workflow_fit_pilot.contracts.lifecycle import propose, validate_lineage

    v1 = pf.manifest()
    record = propose(v1, v1.methods[0].method, recorded_by="t", recorded_at=pf.NOW)
    validate_lineage([record], [v1])  # untampered: replays cleanly

    object.__setattr__(v1, "run_role", PilotRunRole.CALIBRATION)
    with pytest.raises(PilotError) as e:
        validate_lineage([record], [v1])
    assert e.value.code is PilotErrorCode.RUN_ROLE_INVALID


def test_is_calibration_run_stays_a_cheap_field_read():
    """G1a ruling: the predicate is a convenience, not a trust boundary. Pinned so a later
    change cannot quietly make it revalidate — the cost would fall on every transition and
    every record replayed."""
    import ast
    import inspect
    import textwrap

    from ugence_workflow_fit_pilot.contracts import lifecycle

    tree = ast.parse(textwrap.dedent(inspect.getsource(lifecycle.is_calibration_run)))
    called = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "revalidate_role" not in called
