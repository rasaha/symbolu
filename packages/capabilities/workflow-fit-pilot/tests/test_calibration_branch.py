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
        statistic_value="0.62", score_count=50, formula_id="calfloor.linear_chain",
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


def test_a_success_summary_is_impossible_without_a_coverage_report():
    from ugence_workflow_fit_pilot.contracts.coverage import success_summary

    with pytest.raises((AttributeError, TypeError)):
        success_summary(None, slice2._calibration_manifest(), {})


def test_confirmatory_and_v1_runs_keep_the_comparison_path():
    """The branch must not change historical behaviour: only a v2 CALIBRATION manifest takes it."""
    from ugence_workflow_fit_pilot.contracts.lifecycle import is_calibration_run

    import pilot_fixtures as pf

    assert is_calibration_run(slice2._calibration_manifest()) is True
    assert is_calibration_run(slice2._confirmatory_manifest()) is False
    assert is_calibration_run(pf.manifest()) is False
