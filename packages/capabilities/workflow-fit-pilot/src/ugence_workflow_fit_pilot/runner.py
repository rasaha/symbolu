"""§7 pilot runner: validates the manifest, starts the boundary process, runs every
assigned method through the caller's workflow executor behind the gateway stub, adapts
records at Slice 1's aggregation boundary, obtains attestations, evaluates quality under
the declared evaluator, validates every observation, calls the comparison engine, keeps
the state ledger and builds the coverage report.

The runner reads no clock: every instant is caller-supplied. Execution happens through the
caller's ``WorkflowExecutorPort`` (the research harness), never through any runtime."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Protocol, Sequence, Tuple

from ugence_governance_contracts.api import MetricClaim, SourceBasis, TransformationMethod
from ugence_readiness_comparison import compare
from ugence_reasoning_method_advisor.api import ReasoningMethodAdvisory, RuleSet
from ugence_reasoning_method_governance.api import (
    COMPARISON_REQUEST_SCHEMA_VERSION,
    RECORD_SCHEMA_VERSION,
    AttestationEnvelope,
    CountBasis,
    ExecutionTelemetry,
    FitOutcome,
    QualityResult,
    ReadinessComparisonRequest,
    ReadinessComparisonResult,
    ReasoningMethodCatalog,
    ReasoningMethodExecutionRecord,
    ReasoningMethodRef,
    ResolvedAuthority,
    TokenUsageSnapshot,
    UsageAvailabilityToken,
)

from ._canon import digest_of, payload
from .boundary.attestation import envelope_id_for, record_canonical_payload
from .boundary.client import BoundaryConnection, GatewayStubClient, method_to_json
from .boundary.frames import CaptureRecord, capture_from_json
from .contracts.coverage import ChallengerCoverageReport, build_coverage_report
from .contracts.lifecycle import LifecycleEvent, PilotConfigurationStateRecord, propose, transition
from .contracts.manifest import PilotStudyManifest, ValidatedManifest, validate_manifest
from .contracts.observation import (
    PILOT_OBSERVATION_SCHEMA_VERSION,
    QUALITY_EVALUATION_SCHEMA_VERSION,
    PilotObservation,
    QualityEvaluationRecord,
    WorkflowReportedDiagnostics,
    claim_digest,
    quality_result_digest,
    validate_observation,
)
from .errors import PilotError, PilotErrorCode

QUALITY_UNIT = "score.unit"
QUALITY_METRIC_ID = "pilot.quality.aggregated_over_cases"
_STARTUP_POLL_SECONDS = 1 / 50  # boundary start-up wait; an operational interval, not an evidence figure


@dataclass(frozen=True)
class PilotCase:
    case_id: str
    case_digest: str
    query: str
    context: str = ""


@dataclass(frozen=True)
class ExecutionOutcome:
    final_response: str
    total_llm_calls_reported: int


class WorkflowExecutorPort(Protocol):
    def execute(self, method: ReasoningMethodRef, query: str, context: str, client) -> ExecutionOutcome: ...


class QualityScorerPort(Protocol):
    def score(self, case_digest: str, response: str) -> Decimal: ...


@dataclass(frozen=True)
class PilotIdentity:
    tenant_id: str
    subject_id: str
    record_issuer_identity: str
    requester_identity: str
    model_ref: str


def check_evaluator_identity(declaration, identity: "PilotIdentity", boundary_identity: str) -> Tuple[str, ...]:
    """§5 obligations: the evaluator identity must differ from the record issuer, the requester
    and the boundary (EVALUATOR_SELF_LOOP); an LLM evaluator sharing the tested workflow's
    model_ref is reported, never refused. Returns the report flags."""
    if declaration.evaluator_identity in (identity.record_issuer_identity, identity.requester_identity, boundary_identity):
        raise PilotError(PilotErrorCode.EVALUATOR_SELF_LOOP, "evaluator identity coincides with the record issuer, requester or boundary")
    flags: List[str] = []
    if declaration.model_ref is not None and declaration.model_ref == identity.model_ref:
        flags.append("EVALUATOR_SHARES_MODEL")
    return tuple(flags)


class _CountingStub:
    """In-process count of calls the workflow made through the stub: the harness-observed
    figure the boundary is compared against."""

    def __init__(self, inner: GatewayStubClient) -> None:
        self._inner = inner
        self.calls = 0

    def call(self, prompt: str) -> str:
        self.calls += 1
        return self._inner.call(prompt)


@dataclass(frozen=True)
class MethodRun:
    method: ReasoningMethodRef
    complete: bool
    reasons: Tuple[str, ...]
    capture_records: Tuple[CaptureRecord, ...]
    record: Optional[ReasoningMethodExecutionRecord]
    attestation: Optional[AttestationEnvelope]
    quality_claim: Optional[MetricClaim]
    quality_result: Optional[QualityResult]
    evaluation: Optional[QualityEvaluationRecord]
    observation: Optional[PilotObservation]
    diagnostics: WorkflowReportedDiagnostics


@dataclass(frozen=True)
class PilotRunResult:
    manifest: PilotStudyManifest
    validated: ValidatedManifest
    runs: Tuple[MethodRun, ...]
    request: Optional[ReadinessComparisonRequest]
    result: Optional[ReadinessComparisonResult]
    states: Tuple[PilotConfigurationStateRecord, ...]
    coverage: ChallengerCoverageReport
    outcomes: Dict[ReasoningMethodRef, FitOutcome]
    evaluator_flags: Tuple[str, ...] = ()


class BoundaryProcess:
    """Starts and stops the separate boundary process (§4.1)."""

    def __init__(self, manifest: PilotStudyManifest, provider_factory: str, *, env: Optional[Dict[str, str]] = None) -> None:
        self.manifest = manifest
        self.dir = tempfile.mkdtemp(prefix="wfp-boundary-")
        self.endpoint = os.path.join(self.dir, "boundary.sock")
        decl = manifest.capture_boundary
        args = [
            sys.executable, "-m", "ugence_workflow_fit_pilot.boundary.entry", "--endpoint", self.endpoint,
            "--manifest-digest", manifest.manifest_digest, "--provider-factory", provider_factory,
            "--declaration-json", json.dumps({
                "boundary_identity": decl.boundary_identity, "boundary_version": decl.boundary_version, "process_separation_ref": decl.process_separation_ref,
                "port_ref": decl.port_ref, "allowed_attested_fields": list(decl.allowed_attested_fields),
            }),
        ]
        self.proc = subprocess.Popen(args, env=env or os.environ.copy(), stderr=subprocess.PIPE, text=True)
        deadline = time.monotonic() + 30
        while not os.path.exists(self.endpoint):
            if self.proc.poll() is not None:
                err = self.proc.stderr.read() if self.proc.stderr else ""
                raise PilotError(PilotErrorCode.PROVIDER_FACTORY_INVALID, f"boundary process exited before serving: {err.strip()}")
            if time.monotonic() > deadline:
                self.proc.kill()
                raise PilotError(PilotErrorCode.CAPTURE_INCOMPLETE, "boundary process did not start")
            time.sleep(_STARTUP_POLL_SECONDS)

    def connect(self) -> BoundaryConnection:
        return BoundaryConnection(self.endpoint)

    def stop(self) -> None:
        try:
            conn = BoundaryConnection(self.endpoint)
            conn._stream.write(b'{"kind": "SHUTDOWN"}\n')
            conn._stream.flush()
            conn.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()


def _mean(values: Sequence[Decimal]) -> str:
    return str(sum(values, Decimal(0)) / Decimal(len(values)))


def run_pilot(
    manifest: PilotStudyManifest,
    *,
    catalog: ReasoningMethodCatalog,
    rule_set: RuleSet,
    advisory: Optional[ReasoningMethodAdvisory],
    cases: Sequence[PilotCase],
    executor: WorkflowExecutorPort,
    scorer: QualityScorerPort,
    identity: PilotIdentity,
    provider_factory: str,
    now: Callable[[], datetime],
    boundary_env: Optional[Dict[str, str]] = None,
) -> PilotRunResult:
    """``now`` is caller-supplied (tests pass a fixed instant); the runner reads no clock."""
    validated = validate_manifest(manifest, catalog=catalog, rule_set=rule_set, advisory=advisory)
    evaluator_flags = check_evaluator_identity(manifest.evaluator, identity, manifest.capture_boundary.boundary_identity)
    case_digests = tuple(c.case_digest for c in cases)
    if tuple(sorted(case_digests)) != manifest.benchmark.case_digests:
        raise PilotError(PilotErrorCode.BENCHMARK_MANIFEST_MISMATCH, "supplied cases are not the benchmark manifest's case set")
    boundary = BoundaryProcess(manifest, provider_factory, env=boundary_env)
    runs: List[MethodRun] = []
    states: List[PilotConfigurationStateRecord] = []
    latest: Dict[ReasoningMethodRef, PilotConfigurationStateRecord] = {}
    try:
        conn = boundary.connect()
        for assignment in manifest.methods:
            method = assignment.method
            proposed = propose(manifest, method, recorded_by=identity.requester_identity, recorded_at=now())
            states.append(proposed); latest[method] = proposed
            run = _run_method(conn, manifest, method, cases, executor, scorer, identity, now)
            runs.append(run)
            if not run.complete:
                refusal = PilotErrorCode.WORKFLOW_FAILED.value if any(r.startswith(PilotErrorCode.WORKFLOW_FAILED.value) for r in run.reasons) else PilotErrorCode.CAPTURE_INCOMPLETE.value
                rec = transition(proposed, LifecycleEvent.RESULT_INCONCLUSIVE, manifest=manifest, capture_refusal=refusal, recorded_by=identity.requester_identity, recorded_at=now())
                states.append(rec); latest[method] = rec
                continue
            validate_observation(
                run.observation, validated=validated, manifest=manifest, plan=manifest.plan, record=run.record, benchmark=manifest.benchmark,
                evaluation=run.evaluation, quality_claim=run.quality_claim, quality_result=run.quality_result, advisory=advisory, attestation=run.attestation,
            )
            rec = transition(proposed, LifecycleEvent.OBSERVATION_VALIDATED, manifest=manifest, recorded_by=identity.requester_identity, recorded_at=now())
            states.append(rec); latest[method] = rec
        conn.close()
    finally:
        boundary.stop()
    complete_runs = [r for r in runs if r.complete]
    request = result = None
    outcomes: Dict[ReasoningMethodRef, FitOutcome] = {}
    baseline = manifest.plan.baseline
    if complete_runs:  # the engine decides; an absent baseline is its request-level refusal, never the runner's silence
        request = ReadinessComparisonRequest(
            schema_version=COMPARISON_REQUEST_SCHEMA_VERSION, request_id=f"{manifest.manifest_id}:comparison", task_class=manifest.plan.task_class,
            catalog=catalog.ref(), baseline=baseline, candidates=tuple(r.method for r in complete_runs),
            records=tuple(r.record for r in complete_runs), quality_results=tuple(r.quality_result for r in complete_runs), quality_claims=tuple(r.quality_claim for r in complete_runs),
            attestation_envelopes=tuple(r.attestation for r in complete_runs if r.attestation is not None),
            resolved_authorities=(ResolvedAuthority(manifest.capture_boundary.boundary_identity, f"resolution:requester-asserted:{manifest.capture_boundary.boundary_identity}"),),
            requester_identity=identity.requester_identity,
        )
        result = compare(request, produced_at=now())
        outcomes = {a.method: a.outcome for a in result.assessments}
        for r in complete_runs:
            prev = latest[r.method]
            event = LifecycleEvent.RESULT_ASSESSED if outcomes.get(r.method) in (FitOutcome.INSUFFICIENT_QUALITY, FitOutcome.SUFFICIENT_RESOURCE_DOMINATED, FitOutcome.SUFFICIENT_PARETO_EFFICIENT) else LifecycleEvent.RESULT_INCONCLUSIVE
            rec = transition(prev, event, manifest=manifest, result=result, recorded_by=identity.requester_identity, recorded_at=now())
            states.append(rec); latest[r.method] = rec
    coverage = build_coverage_report(manifest, validated, tuple(r.method for r in complete_runs))
    return PilotRunResult(manifest, validated, tuple(runs), request, result, tuple(states), coverage, outcomes, evaluator_flags)


def _run_method(conn: BoundaryConnection, manifest: PilotStudyManifest, method: ReasoningMethodRef, cases: Sequence[PilotCase], executor: WorkflowExecutorPort, scorer: QualityScorerPort, identity: PilotIdentity, now: Callable[[], datetime]) -> MethodRun:
    run_id = f"{manifest.manifest_id}:{method.method_id}@{method.method_version}:run"
    md = manifest.manifest_digest
    conn.send({"kind": "RUN_BEGIN", "manifest_digest": md, "run_id": run_id, "method": method_to_json(method)})
    stub = GatewayStubClient(conn, manifest_digest=md, method=method, run_id=run_id)
    counting = _CountingStub(stub)
    reported_total = 0
    scores: List[Decimal] = []
    responses: Dict[str, str] = {}
    failure: Optional[str] = None
    for case in cases:
        conn.send({"kind": "CASE_BEGIN", "run_id": run_id, "case_digest": case.case_digest})
        stub.set_case(case.case_digest)
        before = counting.calls
        try:
            outcome = executor.execute(method, case.query, case.context, counting)
        except Exception as e:  # the workflow did not survive a provider failure: the run ends incomplete
            failure = f"{PilotErrorCode.WORKFLOW_FAILED.value}: {type(e).__name__} in case {case.case_digest[:12]}"
            conn.send({"kind": "CASE_END", "run_id": run_id, "case_digest": case.case_digest, "harness_observed_calls": counting.calls - before})
            break
        reported_total += int(outcome.total_llm_calls_reported)
        responses[case.case_digest] = outcome.final_response
        conn.send({"kind": "CASE_END", "run_id": run_id, "case_digest": case.case_digest, "harness_observed_calls": counting.calls - before})
    end = conn.send({"kind": "RUN_END", "run_id": run_id, "case_digests": [c.case_digest for c in cases], "harness_observed_calls": counting.calls})
    captures = tuple(capture_from_json(c) for c in end["capture_records"])
    diagnostics = WorkflowReportedDiagnostics(reported_total, counting.calls)
    if failure is not None or not end["complete"]:
        reasons = tuple(end.get("reasons", ())) + ((failure,) if failure else ())
        return MethodRun(method, False, reasons, captures, None, None, None, None, None, None, diagnostics)
    t = end["telemetry"]
    usage = None if t["token_usage"] is None else TokenUsageSnapshot(**{k: (None if v is None else int(v)) for k, v in t["token_usage"].items() if k in TokenUsageSnapshot._count_fields})
    telemetry = ExecutionTelemetry(
        llm_calls=int(t["llm_calls"]), llm_calls_basis=CountBasis(t["llm_calls_basis"]), token_usage_availability=UsageAvailabilityToken(t["token_usage_availability"]),
        token_usage=usage, token_count_basis=CountBasis(t["token_count_basis"]), duration_ms=None, capture_refs=tuple(t["capture_refs"]),
    )
    record = ReasoningMethodExecutionRecord(
        schema_version=RECORD_SCHEMA_VERSION, record_id=f"{run_id}:record", tenant_id=identity.tenant_id, subject_id=identity.subject_id, invocation_id=run_id,
        method=method, binding=manifest.plan.binding, task_class_ref=manifest.plan.task_class.task_class_id, task_class_digest=manifest.plan.task_class.task_class_digest,
        input_digest=manifest.benchmark.benchmark_manifest_digest, model_ref=identity.model_ref, policy_refs=(), artifacts=(), telemetry=telemetry,
        self_reported_quality=None, issuer_identity=identity.record_issuer_identity, captured_at=now(), parent_record_digest=None,
    )
    envelope_id = envelope_id_for(record.record_digest, manifest.capture_boundary.boundary_identity)
    att = conn.send({"kind": "ATTEST", "run_id": run_id, "record_payload": record_canonical_payload(record), "record_issuer_identity": identity.record_issuer_identity, "requester_identity": identity.requester_identity, "envelope_id": envelope_id})
    e = att["envelope"]
    attestation = AttestationEnvelope(e["schema_version"], e["envelope_id"], e["record_digest"], e["attester_identity"], e["capture_boundary_ref"], tuple(e["attested_fields"]), datetime.fromisoformat(e["attested_at"].replace("Z", "+00:00")), e["envelope_digest"])
    for case in cases:
        scores.append(Decimal(str(scorer.score(case.case_digest, responses[case.case_digest]))))
    value = _mean(scores)
    evaluation_id = f"{run_id}:evaluation"
    claim = MetricClaim(
        f"{run_id}:quality-claim", identity.tenant_id, identity.subject_id, QUALITY_METRIC_ID, value, QUALITY_UNIT, SourceBasis.REPORTED, TransformationMethod.CALCULATED,
        evidence_refs=(evaluation_id,), input_evidence_refs=tuple(f"{run_id}:case:{c.case_digest[:16]}:score" for c in cases), calculation_ref=manifest.quality_aggregation.calculation_ref,
    )
    quality_result = QualityResult(method, claim.claim_id, QUALITY_UNIT, value, manifest.quality_aggregation)
    evaluation = QualityEvaluationRecord(
        QUALITY_EVALUATION_SCHEMA_VERSION, evaluation_id, md, method, record.record_digest, manifest.benchmark.benchmark_manifest_digest,
        manifest.evaluator.declaration_digest, manifest.evaluator.scoring_instruction_digest, manifest.quality_aggregation, claim_digest(claim), quality_result_digest(quality_result),
        manifest.evaluator.evaluator_identity, now(),
    )
    assignment = manifest.assignment(method)
    observation = PilotObservation(
        PILOT_OBSERVATION_SCHEMA_VERSION, f"{run_id}:observation", md, method, assignment.roles, manifest.plan.task_class.task_class_digest, manifest.plan.binding,
        identity.model_ref, manifest.benchmark.benchmark_manifest_digest, manifest.benchmark.case_count, manifest.resource_aggregation, manifest.quality_aggregation,
        record.record_digest, attestation.envelope_digest, evaluation.evaluation_digest, diagnostics, now(),
    )
    return MethodRun(method, True, (), captures, record, attestation, claim, quality_result, evaluation, observation, diagnostics)


__all__ = ["PilotCase", "ExecutionOutcome", "WorkflowExecutorPort", "QualityScorerPort", "PilotIdentity", "MethodRun", "PilotRunResult", "BoundaryProcess", "run_pilot", "check_evaluator_identity", "QUALITY_UNIT", "QUALITY_METRIC_ID"]
