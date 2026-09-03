"""Phase 4B reference-pilot qualification: mechanism validation over the synthetic fixture.

Nothing here is reasoning-performance evidence. Every run below is labelled
MECHANISM_VALIDATION_ONLY / RESEARCH_ONLY by the tooling itself."""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from ugence_reasoning_method_governance.api import ContractError, FitOutcome, RefusalCode, UsageAvailabilityToken
from ugence_workflow_fit_pilot.api import ATTESTABLE_TELEMETRY_FIELDS, PilotConfigurationState, PilotError, PilotErrorCode

from experiments.workflow_fit_reference_pilot import bundle as B
from experiments.workflow_fit_reference_pilot import cli, loaders, pipeline
from experiments.workflow_fit_reference_pilot.evaluator import ReferenceEvaluator, extract_answer

ROOT = Path(__file__).resolve().parents[3]
WS = ROOT / "experiments" / "workflow_fit_reference_pilot"
FIXTURE = WS / "fixture"
PROVIDER_MODULE = "experiments.workflow_fit_reference_pilot.synthetic_provider"
SCENARIOS = ("nominal", "no_usage", "provider_failure", "incomplete_capture", "engine_refusal")


@pytest.fixture(scope="module")
def prepared(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("prepared") / "p"
    pipeline.prepare(FIXTURE, out)
    return out


@pytest.fixture(scope="module")
def bundles(prepared, tmp_path_factory) -> dict:
    base = tmp_path_factory.mktemp("bundles")
    out = {}
    for sc in SCENARIOS:
        pipeline.run(FIXTURE, prepared, base / f"{sc}-unix", scenario=sc, transport="unix")
        out[sc] = base / f"{sc}-unix"
    pipeline.run(FIXTURE, prepared, base / "nominal-pipe", scenario="nominal", transport="pipe")
    out["nominal-pipe"] = base / "nominal-pipe"
    return out


def _copy(src: Path, tmp_path: Path) -> Path:
    dst = tmp_path / "copy"
    shutil.copytree(src, dst)
    return dst


def _reindex(root: Path) -> None:
    B.write_index(root)


# --------------------------------------------------------------------------- prepare

def test_prepare_is_deterministic_and_labelled(prepared, tmp_path):
    again = tmp_path / "again"
    pipeline.prepare(FIXTURE, again)
    a, b = json.loads((prepared / "index.json").read_text()), json.loads((again / "index.json").read_text())
    assert a == b
    prep = json.loads((prepared / "preparation.json").read_text())
    assert prep["usage_label"] == pipeline.USAGE_LABEL and "MECHANISM_VALIDATION_ONLY" in prep["usage_label"] and "RESEARCH_ONLY" in prep["usage_label"]
    assert prep["calibration_evidence_declared_absent"] == "true"
    assert prep["provider_factory"] == f"{PROVIDER_MODULE}:make_provider"
    manifest = json.loads((prepared / "pilot_manifest.json").read_text())
    assert manifest["usage_scope"] == "RESEARCH_ONLY" and manifest["preregistration_status"] == "DECLARED_UNVERIFIED"
    assert manifest["evaluator"]["independence_status"] == "DECLARED_UNVERIFIED"
    assert manifest["evaluator"]["calibration_evidence_ref"] == ""
    assert set(json.loads((prepared / "case_set.json").read_text())["cases"][0]) == {"case_id", "case_digest"}


def test_prepare_refuses_a_non_empty_output_directory(prepared):
    with pytest.raises(pipeline.PipelineError):
        pipeline.prepare(FIXTURE, prepared)


# --------------------------------------------------------------------------- run / transports

def test_boundary_runs_in_a_separate_process_and_the_provider_is_never_imported_here(bundles):
    assert PROVIDER_MODULE not in sys.modules
    status = json.loads((bundles["nominal"] / "run_status.json").read_text())
    assert status["transport"] == "unix" and status["usage_label"] == pipeline.USAGE_LABEL
    captures = json.loads((bundles["nominal"] / "methods" / "debate@1" / "capture_records.json").read_text())
    assert captures and all(c["provider_invoked"] == "true" and c["status"] == "SUCCEEDED" for c in captures)


def test_pipe_fallback_run_verifies(bundles):
    status = json.loads((bundles["nominal-pipe"] / "run_status.json").read_text())
    assert status["transport"] == "pipe"
    pipeline.verify(bundles["nominal-pipe"])


def test_transport_equivalence_socket_vs_pipe(bundles):
    u, p = bundles["nominal"], bundles["nominal-pipe"]
    same = ("validated_manifest.json", "coverage_report.json", "case_set.json", "pilot_manifest.json")
    for rel in same:
        assert (u / rel).read_bytes() == (p / rel).read_bytes(), rel
    assert set(json.loads((u / "index.json").read_text())["artifacts"]) == set(json.loads((p / "index.json").read_text())["artifacts"])
    for d in sorted((u / "methods").iterdir()):
        for rel in ("quality_claim.json", "quality_result.json"):
            assert (d / rel).read_bytes() == (p / "methods" / d.name / rel).read_bytes(), f"{d.name}/{rel}"
        # capture_refs carry boundary-issued fingerprints (attempt ids, boundary instants), so the record digest and
        # everything bound to it differ per run; every other field, including captured_at from the caller's clock, is equal.
        ru, rp = json.loads((d / "execution_record.json").read_text()), json.loads((p / "methods" / d.name / "execution_record.json").read_text())
        for r in (ru, rp):
            r.pop("record_digest"); r["telemetry"].pop("capture_refs")
        assert ru == rp, d.name
        eu, ep = json.loads((d / "quality_evaluation.json").read_text()), json.loads((p / "methods" / d.name / "quality_evaluation.json").read_text())
        for e in (eu, ep):
            e.pop("record_digest"); e.pop("evaluation_digest")
        assert eu == ep, d.name
        strip = {"captured_at", "attempt_id", "capture_fingerprint"}
        cu = [{k: v for k, v in c.items() if k not in strip} for c in json.loads((d / "capture_records.json").read_text())]
        cp = [{k: v for k, v in c.items() if k not in strip} for c in json.loads((p / "methods" / d.name / "capture_records.json").read_text())]
        assert cu == cp, d.name
        au, ap = json.loads((d / "attestation_envelope.json").read_text()), json.loads((p / "methods" / d.name / "attestation_envelope.json").read_text())
        assert au["attested_fields"] == ap["attested_fields"] and au["attester_identity"] == ap["attester_identity"]
    ru, rp = json.loads((u / "comparison_result.json").read_text()), json.loads((p / "comparison_result.json").read_text())
    assert [(a["method"]["method_id"], a["outcome"]) for a in ru["assessments"]] == [(a["method"]["method_id"], a["outcome"]) for a in rp["assessments"]]


# --------------------------------------------------------------------------- scenarios

def test_nominal_has_zero_one_and_multi_call_cases_and_every_run_is_complete(bundles):
    r = pipeline.verify(bundles["nominal"])
    assert all(x.complete for x in r.runs)
    per_case = {}
    for x in r.runs:
        counts = {}
        for c in x.capture_records:
            counts[c.case_digest] = counts.get(c.case_digest, 0) + 1
        per_case[x.method.method_id] = counts
    case_digests = r.manifest.benchmark.case_digests
    zero_call_cases = [(m, cd) for m, counts in per_case.items() for cd in case_digests if cd not in counts]
    assert zero_call_cases, "the fixture must contain at least one zero-call case"
    assert any(n == 1 for counts in per_case.values() for n in counts.values())
    assert any(n > 1 for counts in per_case.values() for n in counts.values())
    map_reduce = next(x for x in r.runs if x.method.method_id == "map_reduce")
    assert map_reduce.record.telemetry.llm_calls == 4 and map_reduce.diagnostics.harness_observed_calls == 4
    assert map_reduce.quality_result.value == str(Decimal(2) / Decimal(3))  # the zero-call case scored 0 (no ANSWER line)
    assert r.outcomes[map_reduce.method] is FitOutcome.INSUFFICIENT_QUALITY
    assert r.result.refusals == ()


def test_no_usage_scenario_attests_calls_only(bundles):
    r = pipeline.verify(bundles["no_usage"])
    for x in r.runs:
        assert x.complete and x.record.telemetry.token_usage is None
        assert x.record.telemetry.token_usage_availability is UsageAvailabilityToken.UNAVAILABLE_NOT_REPORTED
        assert x.attestation.attested_fields == ("telemetry.llm_calls",)
        assert x.attestation.attested_fields != ATTESTABLE_TELEMETRY_FIELDS


def test_provider_failure_scenario_marks_one_run_inconclusive_and_assesses_the_rest(bundles):
    r = pipeline.verify(bundles["provider_failure"])
    failed = next(x for x in r.runs if x.method.method_id == "tree_of_thought")
    assert not failed.complete and any(reason.startswith("WORKFLOW_FAILED") for reason in failed.reasons)
    assert failed.record is None and failed.observation is None
    st = [s for s in r.states if s.method == failed.method][-1]
    assert st.state is PilotConfigurationState.INCONCLUSIVE and "WORKFLOW_FAILED" in st.refusal_codes
    assert failed.method not in r.outcomes and len(r.outcomes) == 6
    assert failed.method in r.coverage.methods_without_record


def test_incomplete_capture_scenario_is_refused_by_the_boundary(bundles):
    r = pipeline.verify(bundles["incomplete_capture"])
    debate = next(x for x in r.runs if x.method.method_id == "debate")
    assert not debate.complete and any("captured" in reason and "harness_observed" in reason for reason in debate.reasons)
    st = [s for s in r.states if s.method == debate.method][-1]
    assert st.state is PilotConfigurationState.INCONCLUSIVE and PilotErrorCode.CAPTURE_INCOMPLETE.value in st.refusal_codes
    assert debate.diagnostics.harness_observed_calls == 6 and len(debate.capture_records) == 3


def test_engine_refusal_scenario_reaches_the_engine_refusal_path(bundles):
    r = pipeline.verify(bundles["engine_refusal"])
    baseline = next(x for x in r.runs if x.method.method_id == "linear_chain")
    assert not baseline.complete
    assert [x.code for x in r.result.refusals] == [RefusalCode.BASELINE_ABSENT]
    assert set(r.outcomes.values()) == {FitOutcome.COMPARISON_EVIDENCE_ABSENT}
    final = {}
    for s in r.states:
        final[s.method] = s
    assert all(s.state is PilotConfigurationState.INCONCLUSIVE for s in final.values()) and len(final) == 7
    assert "REFUSALS: BASELINE_ABSENT" in (bundles["engine_refusal"] / "report.txt").read_text()


def test_zero_call_run_is_complete_and_attested_under_the_owner_ruling(prepared, tmp_path):
    root = tmp_path / "z"
    r = pipeline.run(FIXTURE, prepared, root, scenario="zero_call_run", transport="unix")
    assert all(x.complete and x.capture_records == () for x in r.runs)
    for x in r.runs:
        assert x.record.telemetry.llm_calls == 0 and x.record.telemetry.token_usage is None
        assert x.record.telemetry.capture_refs == (r.manifest.manifest_digest,)
        assert x.attestation.attested_fields == ("telemetry.llm_calls",)
        assert x.quality_result.value == "0"  # no ANSWER line was ever produced: the mechanism, not a quality finding
    assert set(r.outcomes.values()) == {FitOutcome.INSUFFICIENT_QUALITY}
    pipeline.verify(root)
    assert "zero_call_run" in (WS / "README.md").read_text()


def test_unknown_scenario_is_refused(prepared, tmp_path):
    with pytest.raises(pipeline.PipelineError):
        pipeline.run(FIXTURE, prepared, tmp_path / "u", scenario="does_not_exist")


# --------------------------------------------------------------------------- verification fails closed

def test_verify_accepts_every_bundle_and_report_equals_rendering(bundles):
    for name, root in bundles.items():
        r = pipeline.verify(root)
        assert (root / "report.txt").read_text() == pipeline.render_bundle(root) + "\n"
        assert "RESEARCH-ONLY PILOT REPORT" in (root / "report.txt").read_text(), name


@pytest.mark.parametrize("rel", ["methods/debate@1/execution_record.json", "comparison_result.json", "lifecycle_states.json", "index.json", "report.txt"])
def test_omitted_artifact_is_refused(bundles, tmp_path, rel):
    root = _copy(bundles["nominal"], tmp_path)
    (root / rel).unlink()
    with pytest.raises(B.BundleError):
        pipeline.verify(root)


def test_substituted_artifact_is_refused_by_the_index(bundles, tmp_path):
    root = _copy(bundles["nominal"], tmp_path)
    path = root / "methods" / "debate@1" / "quality_result.json"
    path.write_text(path.read_text().replace('"value": "1"', '"value": "0"'))
    with pytest.raises(B.BundleError, match="substituted"):
        pipeline.verify(root)


def test_substituted_artifact_with_a_rewritten_index_is_refused_by_the_contract_digests(bundles, tmp_path):
    root = _copy(bundles["nominal"], tmp_path)
    path = root / "methods" / "debate@1" / "execution_record.json"
    path.write_text(path.read_text().replace('"llm_calls": "6"', '"llm_calls": "5"'))
    _reindex(root)
    with pytest.raises(ContractError):
        pipeline.verify(root)


def test_unexpected_and_duplicated_artifacts_are_refused(bundles, tmp_path):
    root = _copy(bundles["nominal"], tmp_path)
    (root / "extra.json").write_text("{}")
    with pytest.raises(B.BundleError, match="unexpected"):
        pipeline.verify(root)
    (root / "extra.json").unlink()
    shutil.copytree(root / "methods" / "debate@1", root / "methods" / "debate@2")
    with pytest.raises(B.BundleError, match="unexpected"):
        pipeline.verify(root)
    _reindex(root)
    with pytest.raises(B.BundleError, match="outside the deterministic layout"):
        pipeline.verify(root)


def test_duplicate_index_keys_and_index_digest_tamper_are_refused(bundles, tmp_path):
    root = _copy(bundles["nominal"], tmp_path)
    idx = root / "index.json"
    text = idx.read_text()
    idx.write_text(text.replace('"index_digest": "', '"index_digest": "0'))
    with pytest.raises(B.BundleError):
        pipeline.verify(root)
    first = re.search(r'\n    ("[^"]+": "[0-9a-f]{64}"),', text).group(1)
    idx.write_text(text.replace("{\n    " + first, "{\n    " + first + ",\n    " + first, 1))
    with pytest.raises(B.BundleError, match="duplicate key"):
        pipeline.verify(root)


def test_reordered_request_or_states_are_refused(bundles, tmp_path):
    root = _copy(bundles["nominal"], tmp_path)
    req = json.loads((root / "comparison_request.json").read_text())
    req["candidates"].reverse(); req["records"].reverse()
    (root / "comparison_request.json").write_text(json.dumps(req, indent=2, sort_keys=True) + "\n")
    _reindex(root)
    with pytest.raises(pipeline.PipelineError):
        pipeline.verify(root)
    root2 = _copy(bundles["nominal"], tmp_path / "b")
    states = json.loads((root2 / "lifecycle_states.json").read_text())
    states.reverse()
    (root2 / "lifecycle_states.json").write_text(json.dumps(states, indent=2, sort_keys=True) + "\n")
    _reindex(root2)
    with pytest.raises((pipeline.PipelineError, PilotError)):
        pipeline.verify(root2)


def test_method_and_run_attribution_are_checked(bundles, tmp_path):
    root = _copy(bundles["nominal"], tmp_path)
    src, dst = root / "methods" / "debate@1", root / "methods" / "map_reduce@1"
    shutil.copy(src / "capture_records.json", dst / "capture_records.json")
    _reindex(root)
    with pytest.raises(pipeline.PipelineError, match="attributed to another"):
        pipeline.verify(root)
    root2 = _copy(bundles["nominal"], tmp_path / "b")
    for rel in ("execution_record.json", "attestation_envelope.json", "quality_claim.json", "quality_result.json", "quality_evaluation.json", "observation.json", "capture_records.json"):
        shutil.copy(root2 / "methods" / "debate@1" / rel, root2 / "methods" / "map_reduce@1" / rel)
    _reindex(root2)
    with pytest.raises(pipeline.PipelineError, match="attributed to another"):
        pipeline.verify(root2)


def test_identity_swap_in_preparation_is_refused(bundles, tmp_path):
    root = _copy(bundles["nominal"], tmp_path)
    p = root / "preparation.json"
    p.write_text(p.read_text().replace("model:synthetic-canned-answers", "model:other"))
    _reindex(root)
    with pytest.raises(pipeline.PipelineError, match="identity"):
        pipeline.verify(root)


def test_run_status_completeness_flip_is_refused(bundles, tmp_path):
    root = _copy(bundles["provider_failure"], tmp_path)
    s = root / "run_status.json"
    s.write_text(s.read_text().replace('"complete": "false"', '"complete": "true"'))
    _reindex(root)
    with pytest.raises(B.BundleError):
        pipeline.verify(root)


# --------------------------------------------------------------------------- schema fidelity

def test_every_json_artifact_rebuilds_to_the_same_canonical_bytes(bundles):
    root = bundles["nominal"]
    typed = {
        "benchmark_manifest.json": "BenchmarkManifest", "pilot_manifest.json": "PilotStudyManifest", "validated_manifest.json": "ValidatedManifest",
        "coverage_report.json": "ChallengerCoverageReport", "comparison_result.json": "ReadinessComparisonResult", "comparison_request.json": "ReadinessComparisonRequest",
    }
    import ugence_reasoning_method_governance.api as gov
    import ugence_workflow_fit_pilot.api as wfp
    for rel, cls_name in typed.items():
        cls = getattr(wfp, cls_name, None) or getattr(gov, cls_name)
        obj = B.rebuild_artifact(root, rel, cls)
        assert B.dumps(obj) == (root / rel).read_text(), rel
    from typing import Tuple
    states = B.rebuild_artifact(root, "lifecycle_states.json", Tuple[wfp.PilotConfigurationStateRecord, ...])
    assert B.dumps(states) == (root / "lifecycle_states.json").read_text()


def test_rebuild_refuses_missing_unknown_and_coerced_fields():
    from ugence_workflow_fit_pilot.api import WorkflowReportedDiagnostics
    good = {"total_llm_calls_reported": "3", "harness_observed_calls": "3", "label": "RUNTIME_REPORTED_DIAGNOSTIC"}
    assert B.rebuild(WorkflowReportedDiagnostics, good) == WorkflowReportedDiagnostics(3, 3)
    for bad in ({k: v for k, v in good.items() if k != "label"}, {**good, "extra": "1"}, {**good, "harness_observed_calls": 3}, {**good, "harness_observed_calls": "3.0"}):
        with pytest.raises(B.BundleError):
            B.rebuild(WorkflowReportedDiagnostics, bad)
    with pytest.raises(B.BundleError):
        B.rebuild(bool, "True")


# --------------------------------------------------------------------------- loaders: strict, no defaults, no credentials

def _doc(name: str):
    return json.loads((FIXTURE / name).read_text())


@pytest.mark.parametrize("name,loader", [
    ("task_class.json", loaders.load_task_class), ("aggregation.json", loaders.load_aggregations), ("binding.json", loaders.load_binding),
    ("cases.json", loaders.load_cases), ("provider.json", loaders.load_provider_reference), ("boundary.json", loaders.load_boundary),
    ("identity.json", loaders.load_identity), ("instants.json", loaders.load_instants), ("plan.json", loaders.load_plan_fields),
])
def test_loaders_refuse_missing_unknown_and_credential_keys(name, loader):
    doc = _doc(name)
    loader(doc)
    key = next(iter(doc))
    with pytest.raises(loaders.InputDocumentError):
        loader({k: v for k, v in doc.items() if k != key})
    with pytest.raises(loaders.InputDocumentError):
        loader({**doc, "unexpected": "x"})
    with pytest.raises(loaders.InputDocumentError, match="credential-like"):
        loader({**{k: v for k, v in doc.items() if k != key}, "api_key": "x"})


def test_loaders_refuse_coercion_and_naive_instants():
    with pytest.raises(loaders.InputDocumentError):
        loaders.load_instants({**_doc("instants.json"), "issued_at": "2026-09-02T11:00:00"})
    tc = _doc("task_class.json")
    tc["comparison_policy"]["threshold"]["literal"] = 1
    with pytest.raises(loaders.InputDocumentError):
        loaders.load_task_class(tc)
    with pytest.raises(loaders.InputDocumentError):
        loaders.load_provider_reference({"provider_factory": "not a dotted path", "provider_ref": "x"})
    with pytest.raises(loaders.InputDocumentError):
        loaders.load_evaluator({**_doc("evaluator.json"), "kind": "programmatic"}, scoring_instruction_digest="0" * 64, benchmark_manifest_digest="0" * 64)
    with pytest.raises(loaders.InputDocumentError):
        loaders.load_expected({"expected": {"case.arith": "4"}}, ("case.arith", "case.capital"))
    sc = _doc("scenarios.json")
    sc["scenarios"]["nominal"]["calls"]["debate"]["case.arith"] = True
    with pytest.raises(loaders.InputDocumentError):
        pipeline.load_scenarios(sc, tuple(sc["scenarios"]["nominal"]["calls"]), ("case.arith", "case.capital", "case.boiling"))


def test_fixture_and_workspace_carry_no_credentials_prompt_or_response_text():
    for path in FIXTURE.glob("*.json"):
        text = path.read_text().lower()
        for key in loaders.CREDENTIAL_KEYS:
            assert f'"{key}"' not in text, (path.name, key)
    for path in WS.glob("*.py"):
        assert not re.search(r"^\s*(import|from)\s+(openai|anthropic|mistralai|requests|httpx|boto3|urllib)\b", path.read_text(), re.M), path.name


def test_expected_answers_prompts_and_responses_never_enter_a_bundle(bundles):
    for root in bundles.values():
        for path in root.rglob("*"):
            if path.is_file():
                text = path.read_text(encoding="utf-8")
                assert not re.search(r"\bparis\b|Reasoning omitted|two plus two|ANSWER:", text, re.I), path


def test_scorer_uses_expected_answers_outside_workflow_inputs():
    assert extract_answer("thinking...\nANSWER: Paris ") == "paris"
    assert extract_answer("no answer line") == ""
    s = ReferenceEvaluator({"d": "Paris"})
    assert s.score("d", "ANSWER: paris") == Decimal("1") and s.score("d", "ANSWER: (no call made)") == Decimal("0")


# --------------------------------------------------------------------------- source scans

def _sources():
    return {p.name: p.read_text() for p in WS.glob("*.py")}


def test_workspace_reads_no_clock():
    for name, src in _sources().items():
        assert not re.search(r"\.(now|utcnow|today)\(|time\.(time|monotonic|perf_counter)|import time\b", src), name


def test_workspace_imports_no_sdk_and_no_runtime_workflow():
    for name, src in _sources().items():
        tree = ast.parse(src)
        for node in ast.walk(tree):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else ([node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            for n in names:
                assert not n.startswith(("agentic", "openai", "anthropic", "mistralai", "requests", "httpx", "boto3")), (name, n)


def test_workspace_has_no_numeric_defaults():
    for name, src in _sources().items():
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for d in list(node.args.defaults) + [x for x in node.args.kw_defaults if x is not None]:
                    assert not (isinstance(d, ast.Constant) and isinstance(d.value, (int, float)) and not isinstance(d.value, bool)), (name, node.name)


def test_provider_and_executor_are_the_only_environment_readers():
    for name, src in _sources().items():
        if name in ("synthetic_provider.py", "pipeline.py"):
            continue
        assert "os.environ" not in src, name


# --------------------------------------------------------------------------- replay and CLI

def test_replay_never_starts_a_boundary_or_imports_the_provider(bundles, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("replay must not start a process")
    monkeypatch.setattr(subprocess, "Popen", boom)
    sys.modules.pop(PROVIDER_MODULE, None)
    out = pipeline.replay(bundles["provider_failure"])
    assert out == (bundles["provider_failure"] / "report.txt").read_text().rstrip("\n")
    assert PROVIDER_MODULE not in sys.modules


def test_cli_round_trip(prepared, bundles, tmp_path, capsys):
    assert cli.main(["prepare", "--fixture", str(FIXTURE), "--out", str(tmp_path / "p")]) == 0
    assert cli.main(["run", "--fixture", str(FIXTURE), "--prepared", str(tmp_path / "p"), "--out", str(tmp_path / "b"), "--scenario", "no_usage", "--transport", "pipe"]) == 0
    assert cli.main(["verify", "--bundle", str(tmp_path / "b")]) == 0
    assert cli.main(["render", "--bundle", str(tmp_path / "b")]) == 0
    assert cli.main(["replay", "--bundle", str(tmp_path / "b")]) == 0
    out = capsys.readouterr().out
    assert "MECHANISM_VALIDATION_ONLY" in out and "RESEARCH-ONLY PILOT REPORT" in out
    (tmp_path / "b" / "report.txt").unlink()
    assert cli.main(["verify", "--bundle", str(tmp_path / "b")]) == 1
    assert "REFUSED BundleError" in capsys.readouterr().err
