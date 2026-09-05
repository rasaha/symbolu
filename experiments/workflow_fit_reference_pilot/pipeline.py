"""The five reference-pilot commands: prepare, run, verify, render, replay.

Every instant is caller-supplied through the fixture's instants document; no command reads
the wall clock. ``prepare`` and ``run`` build only the ratified 4A/Slice 1/Slice 2 contracts;
``verify`` rebuilds every artifact from its JSON and re-validates it against the ratified
validators; ``render`` prints the 4A report from the verified bundle; ``replay`` is verify +
render and never starts a boundary process or imports a provider factory.

Interpretations made here (workspace conventions, not contracts) are listed in README.md."""

from __future__ import annotations

import os
import sys
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from ugence_governance_contracts.api import BenchmarkReference, MetricClaim
from ugence_readiness_comparison import compare
from ugence_reasoning_method_advisor.api import ADVISORY_REQUEST_SCHEMA_VERSION, ReasoningMethodAdvisory, ReasoningMethodAdvisoryRequest, RuleSet, advise
from ugence_reasoning_method_governance.api import (
    RESEARCH_PLAN_SCHEMA_VERSION,
    AttestationEnvelope,
    ChallengerSamplingPolicy,
    QualityResult,
    ReadinessComparisonRequest,
    ReadinessComparisonResult,
    ReasoningMethodCatalog,
    ReasoningMethodExecutionRecord,
    ReasoningMethodRef,
    ResearchComparisonPlan,
    SamplingKind,
)
from ugence_workflow_fit_pilot._canon import digest_of
from ugence_workflow_fit_pilot.api import (
    BENCHMARK_MANIFEST_SCHEMA_VERSION,
    PILOT_MANIFEST_SCHEMA_VERSION,
    BenchmarkManifest,
    CaptureRecord,
    ChallengerCoverageReport,
    MethodRun,
    PilotCase,
    PilotConfigurationStateRecord,
    PilotMethodAssignment,
    PilotObservation,
    PilotRole,
    PilotRunResult,
    PilotStudyManifest,
    PreregistrationStatus,
    QualityEvaluationRecord,
    UNIX_SOCKETS_AVAILABLE,
    ValidatedManifest,
    WorkflowReportedDiagnostics,
    admissible_methods,
    build_coverage_report,
    capture_boundary_ref_of,
    case_list_digest,
    check_evaluator_identity,
    comparison_request_id,
    envelope_id_for,
    recompute_telemetry,
    render,
    run_pilot,
    supported_attested_fields,
    validate_lineage,
    validate_manifest,
    validate_observation,
)

from experiments.reasoning_method_advisor_demo.demo import research_catalog, research_rules_v0

from . import loaders
from .bundle import loads, read_artifact, rebuild, rebuild_artifact, verify_index, write_artifact, write_index
from .evaluator import ReferenceEvaluator, normalize, scoring_instruction_digest
from .synthetic_executor import SyntheticWorkflowExecutor
from .env import MODE_ENV

USAGE_LABEL = "MECHANISM_VALIDATION_ONLY; RESEARCH_ONLY; synthetic fixture; not benchmark-derived evidence; not reasoning-performance evidence"
REPO_ROOT = Path(__file__).resolve().parents[2]

FIXTURE_FILES = ("profile.json", "task_class.json", "cases.json", "expected.json", "provider.json", "evaluator.json", "aggregation.json", "binding.json", "boundary.json", "identity.json", "instants.json", "plan.json", "scenarios.json")
PREPARED_LAYOUT = ("benchmark_manifest.json", "pilot_manifest.json", "advisory.json", "catalog.json", "rule_set.json", "case_set.json", "preparation.json")
METHOD_COMPLETE_FILES = ("capture_records.json", "execution_record.json", "attestation_envelope.json", "quality_claim.json", "quality_result.json", "quality_evaluation.json", "observation.json")
METHOD_INCOMPLETE_FILES = ("capture_records.json",)
RUN_LAYOUT_FIXED = PREPARED_LAYOUT + ("validated_manifest.json", "run_status.json", "lifecycle_states.json", "coverage_report.json", "report.txt")
COMPARISON_FILES = ("comparison_request.json", "comparison_result.json")


class PipelineError(ValueError):
    """A command refused: inputs inconsistent, bundle incomplete, or a re-validation failed."""


# --------------------------------------------------------------------------- fixture

def _read_fixture(fixture_dir: Path) -> Dict[str, Any]:
    docs: Dict[str, Any] = {}
    for name in FIXTURE_FILES:
        path = fixture_dir / name
        if not path.is_file():
            raise PipelineError(f"fixture document {name} is absent")
        docs[name[:-5]] = loads(path.read_text(encoding="utf-8"))
    return docs


def expected_digest(case_id: str, expected: str) -> str:
    return digest_of({"case_id": case_id, "expected_normalized": normalize(expected)})


def build_cases(cases_doc: Any, expected_doc: Any) -> Tuple[PilotCase, ...]:
    """Case identity = digest over the workflow-visible input plus the digest of the expected
    answer, so the benchmark manifest commits to the expected answers without carrying them."""
    raw = loaders.load_cases(cases_doc)
    expected = loaders.load_expected(expected_doc, tuple(c["case_id"] for c in raw))
    out = [PilotCase(c["case_id"], digest_of({"case_id": c["case_id"], "query": c["query"], "context": c["context"], "expected_digest": expected_digest(c["case_id"], expected[c["case_id"]])}), c["query"], c["context"]) for c in raw]
    return tuple(sorted(out, key=lambda c: c.case_digest))


def load_scenarios(data: Any, method_ids: Tuple[str, ...], case_ids: Tuple[str, ...]) -> Dict[str, Dict[str, Any]]:
    d = loaders._obj(data, "scenarios", ("scenarios",))
    if not isinstance(d["scenarios"], Mapping) or not d["scenarios"]:
        raise loaders.InputDocumentError("scenarios.scenarios must be a non-empty JSON object")
    out: Dict[str, Dict[str, Any]] = {}
    for name, sc in d["scenarios"].items():
        s = loaders._obj(sc, f"scenarios[{name}]", ("provider_mode", "calls", "bypass_method", "fail_method"))
        calls = s["calls"]
        if not isinstance(calls, Mapping) or set(calls) != set(method_ids):
            raise loaders.InputDocumentError(f"scenarios[{name}].calls must cover exactly the manifest's method ids")
        table: Dict[str, Dict[str, int]] = {}
        for mid, per_case in calls.items():
            if not isinstance(per_case, Mapping) or set(per_case) != set(case_ids):
                raise loaders.InputDocumentError(f"scenarios[{name}].calls[{mid}] must cover exactly the case ids")
            for cid, n in per_case.items():
                if isinstance(n, bool) or not isinstance(n, int) or n < 0:
                    raise loaders.InputDocumentError(f"scenarios[{name}].calls[{mid}][{cid}] must be a non-negative JSON integer")
            table[mid] = {cid: int(n) for cid, n in per_case.items()}
        for key in ("bypass_method", "fail_method"):
            if s[key] is not None and (not isinstance(s[key], str) or s[key] not in method_ids):
                raise loaders.InputDocumentError(f"scenarios[{name}].{key} must be null or a manifest method id")
        out[name] = {"provider_mode": loaders._str(s["provider_mode"], "provider_mode"), "calls": table, "bypass_method": s["bypass_method"] or "", "fail_method": s["fail_method"] or ""}
    return out


# --------------------------------------------------------------------------- prepare

def prepare(fixture_dir: Path, out_dir: Path) -> PilotStudyManifest:
    docs = _read_fixture(fixture_dir)
    profile = loaders.load_profile(docs["profile"])
    build_task_class = loaders.load_task_class(docs["task_class"])
    cases = build_cases(docs["cases"], docs["expected"])
    provider_factory, provider_ref = loaders.load_provider_reference(docs["provider"])
    resource_agg, quality_agg = loaders.load_aggregations(docs["aggregation"])
    binding = loaders.load_binding(docs["binding"])
    boundary = loaders.load_boundary(docs["boundary"])
    identity = loaders.load_identity(docs["identity"])
    instants = loaders.load_instants(docs["instants"])
    plan_fields = loaders.load_plan_fields(docs["plan"])

    digests = tuple(c.case_digest for c in cases)
    head = BenchmarkReference(plan_fields["benchmark_id"], plan_fields["benchmark_version"], case_list_digest(digests), plan_fields["benchmark_issuer_ref"])
    benchmark = BenchmarkManifest(BENCHMARK_MANIFEST_SCHEMA_VERSION, head, digests, len(digests), plan_fields["benchmark_issuer_identity"], instants["issued_at"])
    task_class = build_task_class(benchmark.benchmark_manifest_digest)
    catalog, rule_set = research_catalog(), research_rules_v0()
    advisory = advise(ReasoningMethodAdvisoryRequest(ADVISORY_REQUEST_SCHEMA_VERSION, f"{plan_fields['plan_id']}:advice", profile, task_class, catalog, rule_set, identity.requester_identity), advised_at=instants["preregistered_at"])
    versions = {e.method_id: e.method_version for e in catalog.entries}
    if plan_fields["baseline_method_id"] not in versions:
        raise PipelineError("baseline_method_id is not a catalog method")
    baseline = ReasoningMethodRef(catalog.ref(), plan_fields["baseline_method_id"], versions[plan_fields["baseline_method_id"]])
    qualified = {q.method for q in advisory.qualifying}
    plan = ResearchComparisonPlan(RESEARCH_PLAN_SCHEMA_VERSION, plan_fields["plan_id"], task_class, binding, catalog.ref(), baseline, tuple(q.method for q in advisory.qualifying),
                                  ChallengerSamplingPolicy(SamplingKind.PREREGISTERED, plan_fields["sampling_policy_ref"], plan_fields["declared_coverage_ref"]), "RESEARCH_ONLY", plan_fields["preregistered_by"], instants["preregistered_at"])
    rule = task_class.comparison_policy.sufficiency
    evaluator = loaders.load_evaluator(docs["evaluator"], scoring_instruction_digest=scoring_instruction_digest(benchmark.benchmark_manifest_digest, rule.rule_id, rule.rule_version), benchmark_manifest_digest=benchmark.benchmark_manifest_digest)
    assignments = []
    for m in admissible_methods(catalog, rule_set):
        roles = ([PilotRole.GOVERNED_BASELINE] if m == baseline else []) + ([PilotRole.ADVISOR_QUALIFIED] if m in qualified else [PilotRole.CHALLENGER])
        assignments.append(PilotMethodAssignment(m, tuple(sorted(roles, key=list(PilotRole).index))))
    manifest = PilotStudyManifest(PILOT_MANIFEST_SCHEMA_VERSION, plan_fields["manifest_id"], plan, advisory.advisory_digest, advisory.rule_set, tuple(sorted(assignments, key=lambda a: a.method.sort_key)),
                                  benchmark, boundary, evaluator, resource_agg, quality_agg, PreregistrationStatus.DECLARED_UNVERIFIED, "RESEARCH_ONLY", plan_fields["preregistered_by"], instants["preregistered_at"])
    validate_manifest(manifest, catalog=catalog, rule_set=rule_set, advisory=advisory)
    check_evaluator_identity(evaluator, identity, boundary.boundary_identity)

    out_dir.mkdir(parents=True, exist_ok=True)
    if any(out_dir.iterdir()):
        raise PipelineError(f"output directory {out_dir} is not empty")
    write_artifact(out_dir, "benchmark_manifest.json", benchmark)
    write_artifact(out_dir, "pilot_manifest.json", manifest)
    write_artifact(out_dir, "advisory.json", advisory)
    write_artifact(out_dir, "catalog.json", catalog)
    write_artifact(out_dir, "rule_set.json", rule_set)
    write_artifact(out_dir, "case_set.json", {"case_count": len(cases), "cases": [{"case_id": c.case_id, "case_digest": c.case_digest} for c in cases]})
    write_artifact(out_dir, "preparation.json", {
        "usage_label": USAGE_LABEL, "provider_factory": provider_factory, "provider_ref": provider_ref, "identity": identity,
        "instants": instants, "calibration_evidence_declared_absent": evaluator.calibration_evidence_ref == "",
    })
    write_index(out_dir)
    return manifest


# --------------------------------------------------------------------------- shared rebuild

class Prepared:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.benchmark = rebuild_artifact(root, "benchmark_manifest.json", BenchmarkManifest)
        self.manifest = rebuild_artifact(root, "pilot_manifest.json", PilotStudyManifest)
        self.advisory = rebuild_artifact(root, "advisory.json", ReasoningMethodAdvisory)
        self.catalog = rebuild_artifact(root, "catalog.json", ReasoningMethodCatalog)
        self.rule_set = rebuild_artifact(root, "rule_set.json", RuleSet)
        case_set = read_artifact(root, "case_set.json")
        prep = read_artifact(root, "preparation.json")
        if not isinstance(prep, Mapping) or set(prep) != {"usage_label", "provider_factory", "provider_ref", "identity", "instants", "calibration_evidence_declared_absent"}:
            raise PipelineError("preparation.json is not the prepared shape")
        self.identity = loaders.load_identity(prep["identity"])
        self.instants = loaders.load_instants({k: v for k, v in prep["instants"].items()})
        self.provider_factory, self.provider_ref = loaders.load_provider_reference({"provider_factory": prep["provider_factory"], "provider_ref": prep["provider_ref"]})
        self.usage_label = prep["usage_label"]
        if not isinstance(case_set, Mapping) or set(case_set) != {"case_count", "cases"} or not isinstance(case_set["cases"], list):
            raise PipelineError("case_set.json is not {case_count, cases}")
        self.case_ids = tuple(c["case_id"] for c in case_set["cases"])
        self.case_digests = tuple(c["case_digest"] for c in case_set["cases"])
        if self.manifest.benchmark != self.benchmark or self.case_digests != self.benchmark.case_digests or int(case_set["case_count"]) != self.benchmark.case_count:
            raise PipelineError("benchmark manifest, pilot manifest and case set disagree")
        if prep["calibration_evidence_declared_absent"] != ("true" if self.manifest.evaluator.calibration_evidence_ref == "" else "false"):
            raise PipelineError("preparation.json misstates the calibration-evidence declaration")
        self.validated = validate_manifest(self.manifest, catalog=self.catalog, rule_set=self.rule_set, advisory=self.advisory)
        self.evaluator_flags = check_evaluator_identity(self.manifest.evaluator, self.identity, self.manifest.capture_boundary.boundary_identity)


def _method_dir(m: ReasoningMethodRef) -> str:
    return f"methods/{m.method_id}@{m.method_version}"


def _clock(start: datetime):
    """Caller-supplied instant sequence: the fixture's run_started_at advanced by one
    microsecond per request. An interpretation of 'explicit caller-supplied timestamps'."""
    t = [start]

    def now() -> datetime:
        t[0] = t[0] + timedelta(microseconds=1)
        return t[0]

    return now


def _boundary_env(mode: str) -> Dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(REPO_ROOT)] + [p for p in sys.path if p])
    env[MODE_ENV] = mode
    return env


# --------------------------------------------------------------------------- run

def run(fixture_dir: Path, prepared_dir: Path, out_dir: Path, *, scenario: str, transport: Optional[str] = None) -> PilotRunResult:
    verify_index(prepared_dir, PREPARED_LAYOUT)
    prepared = Prepared(prepared_dir)
    docs = _read_fixture(fixture_dir)
    cases = build_cases(docs["cases"], docs["expected"])
    if tuple(c.case_digest for c in cases) != prepared.benchmark.case_digests:
        raise PipelineError("fixture cases do not reproduce the prepared benchmark manifest")
    provider_factory, _ = loaders.load_provider_reference(docs["provider"])
    if provider_factory != prepared.provider_factory:
        raise PipelineError("fixture provider reference differs from the prepared one")
    expected = loaders.load_expected(docs["expected"], tuple(c.case_id for c in cases))
    method_ids = tuple(a.method.method_id for a in prepared.manifest.methods)
    scenarios = load_scenarios(docs["scenarios"], method_ids, tuple(c.case_id for c in cases))
    if scenario not in scenarios:
        raise PipelineError(f"unknown scenario {scenario!r}; fixture declares {sorted(scenarios)}")
    sc = scenarios[scenario]
    executor = SyntheticWorkflowExecutor(sc["calls"], bypass_method=sc["bypass_method"], fail_method=sc["fail_method"]).bind_cases(cases)
    scorer = ReferenceEvaluator({c.case_digest: expected[c.case_id] for c in cases})
    result = run_pilot(prepared.manifest, catalog=prepared.catalog, rule_set=prepared.rule_set, advisory=prepared.advisory, cases=cases, executor=executor, scorer=scorer,
                       identity=prepared.identity, provider_factory=provider_factory, now=_clock(prepared.instants["run_started_at"]), boundary_env=_boundary_env(sc["provider_mode"]), transport=transport)
    _write_run_bundle(prepared, result, out_dir, scenario=scenario, transport=transport or ("unix" if UNIX_SOCKETS_AVAILABLE else "pipe"), provider_mode=sc["provider_mode"])
    return result


def _write_run_bundle(prepared: Prepared, result: PilotRunResult, out_dir: Path, *, scenario: str, transport: str, provider_mode: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if any(out_dir.iterdir()):
        raise PipelineError(f"output directory {out_dir} is not empty")
    for rel in PREPARED_LAYOUT:
        (out_dir / rel).write_bytes((prepared.root / rel).read_bytes())
    write_artifact(out_dir, "validated_manifest.json", result.validated)
    status: Dict[str, Any] = {"usage_label": USAGE_LABEL, "scenario": scenario, "transport": transport, "provider_mode": provider_mode, "methods": {}}
    for run_ in result.runs:
        d = _method_dir(run_.method)
        write_artifact(out_dir, f"{d}/capture_records.json", run_.capture_records)
        status["methods"][f"{run_.method.method_id}@{run_.method.method_version}"] = {
            "complete": run_.complete, "reasons": list(run_.reasons),
            "total_llm_calls_reported": run_.diagnostics.total_llm_calls_reported, "harness_observed_calls": run_.diagnostics.harness_observed_calls,
        }
        if run_.complete:
            write_artifact(out_dir, f"{d}/execution_record.json", run_.record)
            write_artifact(out_dir, f"{d}/attestation_envelope.json", run_.attestation)
            write_artifact(out_dir, f"{d}/quality_claim.json", run_.quality_claim)
            write_artifact(out_dir, f"{d}/quality_result.json", run_.quality_result)
            write_artifact(out_dir, f"{d}/quality_evaluation.json", run_.evaluation)
            write_artifact(out_dir, f"{d}/observation.json", run_.observation)
    if result.request is not None:
        write_artifact(out_dir, "comparison_request.json", result.request)
        write_artifact(out_dir, "comparison_result.json", result.result)
    write_artifact(out_dir, "lifecycle_states.json", result.states)
    write_artifact(out_dir, "coverage_report.json", result.coverage)
    write_artifact(out_dir, "run_status.json", status)
    write_artifact(out_dir, "report.txt", render(result) + "\n")
    write_index(out_dir)


# --------------------------------------------------------------------------- verify

def _load_status(root: Path, manifest: PilotStudyManifest) -> Dict[str, Any]:
    status = read_artifact(root, "run_status.json")
    if not isinstance(status, Mapping) or set(status) != {"usage_label", "scenario", "transport", "provider_mode", "methods"}:
        raise PipelineError("run_status.json is not the run shape")
    if status["usage_label"] != USAGE_LABEL:
        raise PipelineError("run_status.json does not carry the mechanism-validation usage label")
    keys = {f"{a.method.method_id}@{a.method.method_version}" for a in manifest.methods}
    if not isinstance(status["methods"], Mapping) or set(status["methods"]) != keys:
        raise PipelineError("run_status.json methods differ from the manifest's assignments")
    for k, v in status["methods"].items():
        if not isinstance(v, Mapping) or set(v) != {"complete", "reasons", "total_llm_calls_reported", "harness_observed_calls"} or v["complete"] not in ("true", "false"):
            raise PipelineError(f"run_status.json entry {k} is malformed")
    return status


def run_layout(root: Path) -> Tuple[str, ...]:
    """The complete expected artifact set, derived from the manifest and the run status."""
    manifest = rebuild_artifact(root, "pilot_manifest.json", PilotStudyManifest)
    status = _load_status(root, manifest)
    layout: List[str] = list(RUN_LAYOUT_FIXED)
    any_complete = False
    for a in manifest.methods:
        d = _method_dir(a.method)
        complete = status["methods"][f"{a.method.method_id}@{a.method.method_version}"]["complete"] == "true"
        any_complete |= complete
        layout += [f"{d}/{f}" for f in (METHOD_COMPLETE_FILES if complete else METHOD_INCOMPLETE_FILES)]
    if any_complete:
        layout += list(COMPARISON_FILES)
    return tuple(sorted(layout))


def _int_or_none(v: Any) -> Optional[int]:
    return None if v is None else rebuild(int, v)


def verify(bundle_dir: Path) -> PilotRunResult:
    """Rebuild every artifact from the bundle and re-establish every claim the run made:
    index coverage; contract digests (via each constructor); manifest validation; capture
    -> telemetry -> record -> attestation -> evaluation -> observation per method; the
    comparison engine's result at its stored produced_at; lineage; coverage; and the report."""
    root = Path(bundle_dir)
    verify_index(root, run_layout(root))
    prepared = Prepared(root)
    manifest, validated = prepared.manifest, prepared.validated
    stored_validated = rebuild_artifact(root, "validated_manifest.json", ValidatedManifest)
    if stored_validated != validated:
        raise PipelineError("validated_manifest.json differs from a fresh validation of the manifest")
    status = _load_status(root, manifest)
    runs: List[MethodRun] = []
    seen_record_digests: Dict[str, str] = {}
    for a in manifest.methods:
        method, d = a.method, _method_dir(a.method)
        st = status["methods"][f"{method.method_id}@{method.method_version}"]
        captures: Tuple[CaptureRecord, ...] = rebuild_artifact(root, f"{d}/capture_records.json", Tuple[CaptureRecord, ...])
        run_id = f"{manifest.manifest_id}:{method.method_id}@{method.method_version}:run"
        for c in captures:
            if c.manifest_digest != manifest.manifest_digest or c.method != method or c.run_id != run_id:
                raise PipelineError(f"{d}: a capture record is attributed to another manifest, method or run")
        diagnostics = WorkflowReportedDiagnostics(_int_or_none(st["total_llm_calls_reported"]), _int_or_none(st["harness_observed_calls"]))
        if st["complete"] == "false":
            reasons = tuple(st["reasons"])
            if not reasons:
                raise PipelineError(f"{d}: an incomplete run must state its reasons")
            runs.append(MethodRun(method, False, reasons, captures, None, None, None, None, None, None, diagnostics))
            continue
        record = rebuild_artifact(root, f"{d}/execution_record.json", ReasoningMethodExecutionRecord)
        attestation = rebuild_artifact(root, f"{d}/attestation_envelope.json", AttestationEnvelope)
        claim = rebuild_artifact(root, f"{d}/quality_claim.json", MetricClaim)
        quality_result = rebuild_artifact(root, f"{d}/quality_result.json", QualityResult)
        evaluation = rebuild_artifact(root, f"{d}/quality_evaluation.json", QualityEvaluationRecord)
        observation = rebuild_artifact(root, f"{d}/observation.json", PilotObservation)
        if record.method != method or record.invocation_id != run_id or record.record_id != f"{run_id}:record":
            raise PipelineError(f"{d}: execution record is attributed to another method or run")
        if record.record_digest in seen_record_digests:
            raise PipelineError(f"{d}: execution record duplicates {seen_record_digests[record.record_digest]}")
        seen_record_digests[record.record_digest] = d
        if (record.tenant_id, record.subject_id, record.issuer_identity, record.model_ref) != (prepared.identity.tenant_id, prepared.identity.subject_id, prepared.identity.record_issuer_identity, prepared.identity.model_ref):
            raise PipelineError(f"{d}: execution record identity differs from preparation.json")
        recomputed = recompute_telemetry(manifest.manifest_digest, captures)
        if replace(recomputed, duration_ms=None) != record.telemetry:
            raise PipelineError(f"{d}: record telemetry differs from the recomputation over the bundled capture records")
        if attestation.record_digest != record.record_digest or attestation.envelope_id != envelope_id_for(record.record_digest, manifest.capture_boundary.boundary_identity):
            raise PipelineError(f"{d}: attestation is not over this record")
        if attestation.attester_identity != manifest.capture_boundary.boundary_identity or attestation.capture_boundary_ref != capture_boundary_ref_of(record.telemetry.capture_refs):
            raise PipelineError(f"{d}: attestation attester or capture boundary ref differs from the declaration")
        if attestation.attested_fields != supported_attested_fields(manifest.capture_boundary, record.telemetry):
            raise PipelineError(f"{d}: attested fields are not the supported subset of the declared fields")
        validate_observation(observation, validated=validated, manifest=manifest, plan=manifest.plan, record=record, benchmark=manifest.benchmark, evaluation=evaluation,
                             quality_claim=claim, quality_result=quality_result, advisory=prepared.advisory, attestation=attestation)
        if observation.diagnostics != diagnostics:
            raise PipelineError(f"{d}: run_status diagnostics differ from the observation's")
        runs.append(MethodRun(method, True, (), captures, record, attestation, claim, quality_result, evaluation, observation, diagnostics))
    complete = [r for r in runs if r.complete]
    request = result = None
    outcomes = {}
    if complete:
        request = rebuild_artifact(root, "comparison_request.json", ReadinessComparisonRequest)
        result = rebuild_artifact(root, "comparison_result.json", ReadinessComparisonResult)
        if request.request_id != comparison_request_id(manifest.manifest_digest) or request.task_class != manifest.plan.task_class or request.baseline != manifest.plan.baseline:
            raise PipelineError("comparison request is not this manifest's")
        if request.candidates != tuple(r.method for r in complete) or request.records != tuple(r.record for r in complete):
            raise PipelineError("comparison request candidates or records differ from the bundled complete runs")
        if request.quality_results != tuple(r.quality_result for r in complete) or request.quality_claims != tuple(r.quality_claim for r in complete) or request.attestation_envelopes != tuple(r.attestation for r in complete):
            raise PipelineError("comparison request quality inputs or attestations differ from the bundled runs")
        replayed = compare(request, produced_at=result.produced_at)
        if replayed.result_digest != result.result_digest or replayed != result:
            raise PipelineError("comparison result is not what the engine produces from the bundled request at the stored produced_at")
        outcomes = {x.method: x.outcome for x in result.assessments}
    states: Tuple[PilotConfigurationStateRecord, ...] = rebuild_artifact(root, "lifecycle_states.json", Tuple[PilotConfigurationStateRecord, ...])
    validate_lineage(states, [manifest], [result] if result is not None else ())
    if {s.method for s in states} != {a.method for a in manifest.methods}:
        raise PipelineError("lifecycle states do not cover exactly the manifest's methods")
    coverage = rebuild_artifact(root, "coverage_report.json", ChallengerCoverageReport)
    if coverage != build_coverage_report(manifest, validated, tuple(r.method for r in complete)):
        raise PipelineError("coverage report differs from a rebuild over the complete runs")
    rebuilt = PilotRunResult(manifest, validated, tuple(runs), request, result, states, coverage, outcomes, prepared.evaluator_flags)
    if (root / "report.txt").read_text(encoding="utf-8") != render(rebuilt) + "\n":
        raise PipelineError("report.txt differs from a fresh rendering of the verified bundle")
    return rebuilt


def render_bundle(bundle_dir: Path) -> str:
    return render(verify(bundle_dir))


def replay(bundle_dir: Path) -> str:
    """Verify + render from artifacts alone. Starts no boundary, imports no provider factory."""
    return render_bundle(bundle_dir)


__all__ = ["USAGE_LABEL", "PipelineError", "FIXTURE_FILES", "PREPARED_LAYOUT", "build_cases", "expected_digest", "load_scenarios", "prepare", "Prepared", "run", "run_layout", "verify", "render_bundle", "replay"]
