"""Phase 4C integration: the first test that wires slice 3A to slice 3B end to end.

Commissioned in place of a Phase 4C pipeline module (revision 29 ruling 1). A pipeline built
*in order to* close G3 would invert the tripwire's purpose — G3 exists to catch a future
pipeline bypassing the F3 gate, not as a defect to clear — so **G3 stays open**: this test
adds no production caller of `run_phase_4c_pilot`.

What it does establish is that the pieces fit together, which nothing had checked before:

    prepared bundle written (3A) -> verified (3A) -> cases loaded from an external path and
    proved to reproduce the prepared benchmark -> gated entry point (3B-1) -> calibration
    branch (3B-2) -> custody, where the run stops because no D5-approved adapter exists.

Every fixture is synthetic and written at runtime. No real BBH prompt or target appears here,
and the case directory is a temporary path outside the repository (revision 29 ruling 2).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PILOT_TESTS = _REPO_ROOT / "packages" / "capabilities" / "workflow-fit-pilot" / "tests"
for _p in (_PILOT_TESTS, _PILOT_TESTS / "contracts",
           _REPO_ROOT / "packages" / "capabilities" / "reasoning-method-governance" / "tests",
           _REPO_ROOT / "packages" / "capabilities" / "reasoning-method-advisor" / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import pilot_fixtures as pf  # noqa: E402
import test_run_role_and_calibration as slice2  # noqa: E402

from experiments.workflow_fit_study import prepared_bundle as B  # noqa: E402
from experiments.workflow_fit_study.bbh_sample import index_list_digest, select_indexes  # noqa: E402
from ugence_workflow_fit_pilot._canon import digest_of  # noqa: E402
from ugence_workflow_fit_pilot.api import PilotCase  # noqa: E402
from ugence_workflow_fit_pilot.contracts.calibration import (  # noqa: E402
    canonical_decimal_rendering,
    require_matching_canonical_rendering,
)

PROVIDER_FACTORY = "stub_provider:make_provider"
CUSTODY_REF = "memory://workflow-fit-test/integration/rep0"


# --------------------------------------------------------------------------- the external case path


def _write_case_directory(root: Path, cases) -> Path:
    """Ruling 2: cases live outside the repository and reach the run through a path. Only the
    workflow-visible content is written — **no digest column** — so the loader below has
    nothing to trust and must recompute."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "cases.json").write_text(json.dumps(
        [{"case_id": c.case_id, "query": c.query, "context": c.context} for c in cases],
        indent=2, sort_keys=True) + "\n")
    return root


def _load_cases(case_dir: Path, benchmark):
    """Read cases from a caller-supplied path, **recompute** each case digest from content,
    and require the result to reproduce the prepared benchmark manifest.

    Recomputation is the whole point (revision 30). An earlier version trusted a `case_digest`
    column in the file and compared labels: cases whose `query` and `context` had been replaced
    wholesale, with the digest column left intact, were accepted and drove a complete run. That
    is a label match, not reproduction. 4B recomputes for the same reason
    (`workflow_fit_reference_pilot/pipeline.py:116`), over its own digest scheme — which
    additionally binds the expected-answer digest; this uses the scheme the pilot fixtures use,
    because that is what the prepared benchmark here commits to."""
    raw = json.loads((case_dir / "cases.json").read_text())
    cases = tuple(sorted(
        (PilotCase(c["case_id"],
                   digest_of({"case_id": c["case_id"], "query": c["query"], "context": c["context"]}),
                   c["query"], c["context"])
         for c in raw),
        key=lambda c: c.case_digest,
    ))
    if tuple(sorted(c.case_digest for c in cases)) != benchmark.case_digests:
        raise AssertionError("cases at the supplied path do not reproduce the prepared benchmark manifest")
    return cases


def _prepared_calibration_bundle(out_dir: Path, manifest):
    indexes = select_indexes(seed=2924744787006253617, population_size=250, sample_size=50)
    design = B.ExperimentalDesign(
        manifest_id=manifest.manifest_id, manifest_digest=manifest.manifest_digest, run_role="CALIBRATION",
        benchmark_id=manifest.benchmark.benchmark.benchmark_id,
        benchmark_version=manifest.benchmark.benchmark.version,
        benchmark_content_digest=manifest.benchmark.benchmark.content_digest,
        execution_order_rule="ascending_case_digest", verdict_custody_ref=CUSTODY_REF,
        sampling_algorithm_id="bbh_hash_rank_select", sampling_algorithm_version="1",
        seed="2924744787006253617", population_size=250, sample_size=50,
        selected_indexes=tuple(str(i) for i in indexes), sample_index_digest=index_list_digest(indexes),
        formula_id="calfloor.linear_chain", formula_version="1",
    )
    return B.prepare(
        out_dir, manifest=manifest, benchmark=manifest.benchmark, catalog=pf.catalog(),
        rule_set=pf.rule_set(), advisory=None,
        case_set={"case_count": len(manifest.benchmark.case_digests),
                  "cases": [{"case_id": f"case-{i}", "case_digest": d}
                            for i, d in enumerate(manifest.benchmark.case_digests)]},
        # The bundle must commit the *same* provider factory the run will use; 4B asserts this
        # equality at pipeline.py:263 and a mismatch is a preparation error, not a run error.
        provider_configuration=B.ProviderConfiguration(provider_factory=PROVIDER_FACTORY),
        experimental_design=design, preparation={},
    )


# --------------------------------------------------------------------------- the integration


def test_prepared_bundle_verifies_and_drives_a_gated_calibration_run(tmp_path):
    from ugence_workflow_fit_pilot.contracts.lifecycle import PilotConfigurationState, validate_lineage
    from ugence_workflow_fit_pilot.runner import run_phase_4c_pilot

    manifest = slice2._calibration_manifest()

    # 3A: write and verify the bundle.
    written = _prepared_calibration_bundle(tmp_path / "prepared", manifest)
    verified = B.verify(tmp_path / "prepared", catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=None)
    assert verified.index_digest == written.index_digest
    assert verified.run_role == "CALIBRATION"
    assert verified.verdict_custody_ref == CUSTODY_REF

    # Cases arrive from a path outside the repository and must reproduce the prepared benchmark.
    case_dir = _write_case_directory(tmp_path / "cases", pf.cases())
    cases = _load_cases(case_dir, manifest.benchmark)

    # 3B-1 and 3B-2: the gated entry point admits a v2 CALIBRATION manifest and takes the
    # calibration branch.
    result = run_phase_4c_pilot(
        manifest, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=None, cases=cases,
        executor=pf.FakeExecutor({"linear_chain": 1}), scorer=pf.KeywordScorer(),
        identity=pf.IDENTITY, provider_factory=PROVIDER_FACTORY, now=pf.clock(),
        boundary_env=pf.boundary_env(),
    )
    assert all(r.complete for r in result.runs), [(r.method.method_id, r.reasons) for r in result.runs]
    assert result.request is None and result.result is None and result.coverage is None
    assert [s.state for s in result.states] == [PilotConfigurationState.PROPOSED, PilotConfigurationState.UNDER_TEST]
    validate_lineage(result.states, [manifest])


@pytest.mark.parametrize("tamper", ["query", "context", "case_id", "drop"])
def test_cases_whose_content_does_not_reproduce_the_prepared_benchmark_are_refused(tmp_path, tamper):
    """Revision 30. The earlier version of this test asserted an AssertionError raised by a
    helper in this same file that merely compared digest *labels* — circular, and satisfied by
    content-tampered cases. Now the loader recomputes, so tampering with any field the digest
    covers is caught, and dropping a case is caught too."""
    manifest = slice2._calibration_manifest()
    _prepared_calibration_bundle(tmp_path / "prepared", manifest)
    case_dir = _write_case_directory(tmp_path / "cases", pf.cases())

    raw = json.loads((case_dir / "cases.json").read_text())
    if tamper == "drop":
        raw = raw[:1]
    else:
        raw[0][tamper] = "TAMPERED " + raw[0][tamper]
    (case_dir / "cases.json").write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n")

    with pytest.raises(AssertionError, match="do not reproduce the prepared benchmark manifest"):
        _load_cases(case_dir, manifest.benchmark)


def test_the_run_stops_at_custody_because_no_d5_approved_adapter_exists(tmp_path):
    """Ruling 3: the custody step is reached and refuses, rather than being omitted so the
    blocker lives only in prose.

    There is no production `VerdictCustodyPort` implementation in `custody.py`'s namespace —
    only `InMemoryVerdictCustody`, which revision 20 ruling 3 confines to tests — so a genuine
    `CalibrationResult` cannot be produced. This asserts that inventory rather than a refusal
    the package does not raise.

    **Scope of the assertion (revision 30).** It scans one module's namespace. An adapter
    defined in a sibling module and never imported here, or a subclass of the double defined
    elsewhere, is **not** detected. It is a reminder, not a control."""
    import inspect

    from ugence_workflow_fit_pilot import custody as custody_mod

    implementations = [
        name for name, obj in vars(custody_mod).items()
        if inspect.isclass(obj) and hasattr(obj, "write") and hasattr(obj, "read_back")
        and name != "VerdictCustodyPort"
    ]
    assert implementations == ["InMemoryVerdictCustody"], (
        f"a new VerdictCustodyPort implementation appeared in custody.py: {implementations}. If it is a real "
        "adapter, D5 must have bound its endpoint, ACLs, identities, encryption and retention "
        "first, and this test and the note must be updated together."
    )
    assert "Test-only" in custody_mod.InMemoryVerdictCustody.__doc__


def test_a_calibration_result_is_built_from_the_run_and_ends_the_calibration(tmp_path):
    """The other half of ruling 3, and the half revision 29 claimed but did not have.

    The earlier version fabricated `evaluation_digest`, `attestation_digest` and
    `statistic_value` as literal constants, so its "every digest came from the verified bundle"
    assertion was false for two of five fields and the run→result link was never exercised.
    This builds the result from the **actual run's** evaluation and attestation digests and its
    canonical quality value, then calls `require_calibration_endpoint` — slice 3B-0's rule for
    when a calibration has genuinely ended."""
    from datetime import datetime, timezone

    from ugence_workflow_fit_pilot.contracts.lifecycle import (
        PilotConfigurationState, require_calibration_endpoint,
    )
    from ugence_workflow_fit_pilot.custody import (
        InMemoryVerdictCustody, VerdictCustodyRecord, VerifiedPreparedFacts, build_calibration_result,
    )
    from ugence_workflow_fit_pilot.runner import run_phase_4c_pilot

    manifest = slice2._calibration_manifest()
    _prepared_calibration_bundle(tmp_path / "prepared", manifest)
    verified = B.verify(tmp_path / "prepared", catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=None)
    cases = _load_cases(_write_case_directory(tmp_path / "cases", pf.cases()), manifest.benchmark)

    result = run_phase_4c_pilot(
        manifest, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=None, cases=cases,
        executor=pf.FakeExecutor({"linear_chain": 1}), scorer=pf.KeywordScorer(),
        identity=pf.IDENTITY, provider_factory=PROVIDER_FACTORY, now=pf.clock(),
        boundary_env=pf.boundary_env(),
    )
    run = result.runs[0]
    assert run.complete and run.evaluation is not None and run.attestation is not None

    case_digests = tuple(sorted(c.case_digest for c in cases))
    facts = VerifiedPreparedFacts(
        commitment_identifier=verified.commitment_identifier, index_digest=verified.index_digest,
        sample_index_digest=verified.sample_index_digest, verdict_custody_ref=verified.verdict_custody_ref,
        manifest_digest=verified.manifest_digest, case_digests=case_digests,
    )
    record = VerdictCustodyRecord(
        custody_ref=verified.verdict_custody_ref, manifest_digest=verified.manifest_digest,
        index_digest=verified.index_digest,
        verdicts=tuple(sorted((d, "correct") for d in case_digests)),
    )
    port = InMemoryVerdictCustody()
    calibration = build_calibration_result(
        prepared=facts, custody=port, custody_record=record, calibration_id="cal.integration",
        # From the run, not fabricated.
        evaluation_digest=run.evaluation.evaluation_digest,
        attestation_digest=run.attestation.envelope_digest,
        statistic_value=canonical_decimal_rendering(run.quality_result.value),
        score_count=len(case_digests), formula_id="calfloor.linear_chain", formula_version="1",
        issued_by="tester", issued_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    # Bundle-sourced fields.
    assert calibration.index_digest == verified.index_digest
    assert calibration.sample_index_digest == verified.sample_index_digest
    assert calibration.verdict_custody_ref == verified.verdict_custody_ref
    assert calibration.manifest_digest == verified.manifest_digest
    # Run-sourced fields — the link revision 29 asserted without having.
    assert calibration.evaluation_digest == run.evaluation.evaluation_digest
    assert calibration.attestation_digest == run.attestation.envelope_digest
    # Revision 31: the governed renderer, not a test-local one. The gap this test surfaced is
    # closed, and the run's own spelling is still not accepted as-is.
    assert calibration.statistic_value == canonical_decimal_rendering(run.quality_result.value)
    assert str(run.quality_result.value) != calibration.statistic_value
    require_matching_canonical_rendering(
        calibration.statistic_value, run.quality_result.value, "statistic_value")
    assert port.written_references() == (CUSTODY_REF,)

    # Slice 3B-0: with that result, the UNDER_TEST record is a completed calibration.
    under_test = result.states[-1]
    assert under_test.state is PilotConfigurationState.UNDER_TEST
    require_calibration_endpoint(under_test, manifest=manifest, calibration_result=calibration)
