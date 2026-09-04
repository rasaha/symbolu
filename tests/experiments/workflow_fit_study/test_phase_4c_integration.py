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
from ugence_workflow_fit_pilot.api import PilotCase, PilotError, PilotErrorCode  # noqa: E402

PROVIDER_FACTORY = "stub_provider:make_provider"
CUSTODY_REF = "memory://workflow-fit-test/integration/rep0"


# --------------------------------------------------------------------------- the external case path


def _write_case_directory(root: Path, cases) -> Path:
    """Ruling 2: cases live outside the repository and reach the run through a path. This
    writes the synthetic fixture cases to a temp directory in the shape such a directory would
    have, so the loader below is exercised rather than bypassed."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "cases.json").write_text(json.dumps(
        [{"case_id": c.case_id, "case_digest": c.case_digest, "query": c.query, "context": c.context} for c in cases],
        indent=2, sort_keys=True) + "\n")
    return root


def _load_cases(case_dir: Path, benchmark):
    """Read cases from a caller-supplied path and prove they reproduce the prepared benchmark
    manifest before anything runs — the check 4B performs at pipeline.py:261. Without it a run
    could execute a different case set than the one the bundle committed."""
    raw = json.loads((case_dir / "cases.json").read_text())
    cases = tuple(sorted(
        (PilotCase(c["case_id"], c["case_digest"], c["query"], c["context"]) for c in raw),
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


def test_a_case_set_that_does_not_reproduce_the_prepared_benchmark_is_refused(tmp_path):
    """The check that makes the external case path safe. Without it, a run could execute a
    different case set than the bundle committed and nothing downstream would notice."""
    manifest = slice2._calibration_manifest()
    _prepared_calibration_bundle(tmp_path / "prepared", manifest)
    wrong = tuple(PilotCase(c.case_id, c.case_digest, c.query, c.context) for c in pf.cases())[:1]
    case_dir = _write_case_directory(tmp_path / "cases", wrong)
    with pytest.raises(AssertionError, match="do not reproduce the prepared benchmark manifest"):
        _load_cases(case_dir, manifest.benchmark)


def test_the_run_stops_at_custody_because_no_d5_approved_adapter_exists(tmp_path):
    """Ruling 3: the custody step is reached and refuses, rather than being omitted so the
    blocker lives only in prose.

    There is no production `VerdictCustodyPort` implementation — the only one in the tree is
    `InMemoryVerdictCustody`, which revision 20 ruling 3 confines to tests. So a genuine
    `CalibrationResult` cannot be produced, and this asserts that inventory rather than
    asserting a refusal the package does not yet raise."""
    import inspect

    from ugence_workflow_fit_pilot import custody as custody_mod

    implementations = [
        name for name, obj in vars(custody_mod).items()
        if inspect.isclass(obj) and hasattr(obj, "write") and hasattr(obj, "read_back")
        and name != "VerdictCustodyPort"
    ]
    assert implementations == ["InMemoryVerdictCustody"], (
        f"a new VerdictCustodyPort implementation appeared: {implementations}. If it is a real "
        "adapter, D5 must have bound its endpoint, ACLs, identities, encryption and retention "
        "first, and this test and the note must be updated together."
    )
    assert "Test-only" in custody_mod.InMemoryVerdictCustody.__doc__


def test_a_calibration_result_over_the_double_is_reachable_but_test_only(tmp_path):
    """The remaining half of ruling 3: with the test-only double the whole path executes, so
    the integration is proven — and the result is never genuine evidence."""
    from ugence_workflow_fit_pilot.custody import (
        InMemoryVerdictCustody, VerdictCustodyRecord, VerifiedPreparedFacts, build_calibration_result,
    )
    from datetime import datetime, timezone

    manifest = slice2._calibration_manifest()
    _prepared_calibration_bundle(tmp_path / "prepared", manifest)
    verified = B.verify(tmp_path / "prepared", catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=None)

    case_digests = tuple(sorted(manifest.benchmark.case_digests))
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
        evaluation_digest="3" * 64, attestation_digest="4" * 64, statistic_value="0.62",
        score_count=len(case_digests), formula_id="calfloor.linear_chain", formula_version="1",
        issued_by="tester", issued_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    # Every digest the result carries came from the verified bundle, not from the caller.
    assert calibration.index_digest == verified.index_digest
    assert calibration.sample_index_digest == verified.sample_index_digest
    assert calibration.verdict_custody_ref == verified.verdict_custody_ref
    assert port.written_references() == (CUSTODY_REF,)
    assert isinstance(port, InMemoryVerdictCustody)  # test-only by ruling; never genuine evidence
