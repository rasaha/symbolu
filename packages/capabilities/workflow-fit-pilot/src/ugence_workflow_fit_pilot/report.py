"""§7 pilot report: evidence axes per field, preregistration and independence statuses,
diagnostics under their label, every judgment labelled RESEARCH_ONLY, and a success summary
only when the coverage report permits one."""

from __future__ import annotations

from typing import List

from ugence_reasoning_method_governance.api import FitOutcome

from .contracts.coverage import success_summary
from .errors import PilotError, PilotErrorCode
from .runner import PilotRunResult

FORBIDDEN_RENDERINGS = ("verified", "trusted", "qualified", "success")


def _outcome_line(method_id: str, outcome: FitOutcome) -> str:
    return f"  - {method_id}: {outcome.value} [RESEARCH_ONLY; evidence reported/unverified; non-authoritative]"


def render(result: PilotRunResult) -> str:
    if result.coverage is None:
        # Slice 3B-2 made PilotRunResult.coverage Optional and left this reader unchanged, so
        # a calibration result crashed here with AttributeError. Recorded and corrected in
        # revision 23. Refusing closed is right: this renderer's whole shape — the coverage
        # line, the success summary, the outcome lines — is confirmatory, and a calibration
        # report is a slice-3B output-bundle concern that is not commissioned. It must not
        # silently render a partial one. ROLE_ARTIFACT_INCONSISTENT, not a new code
        # (revision 20 ruling 4): the artifact this role produced is not the one this
        # renderer consumes.
        raise PilotError(
            PilotErrorCode.ROLE_ARTIFACT_INCONSISTENT,
            "render() builds a confirmatory report and a CALIBRATION run carries no coverage; "
            "calibration output bundles are not commissioned",
        )
    m = result.manifest
    lines: List[str] = [
        f"RESEARCH-ONLY PILOT REPORT manifest={m.manifest_digest} preregistration_status={m.preregistration_status.value}",
        f"task_class={m.plan.task_class.task_class_id} ({m.plan.task_class.task_class_digest[:16]}...) benchmark_manifest={m.benchmark.benchmark_manifest_digest[:16]}... cases={m.benchmark.case_count}",
        f"evaluator={m.evaluator.evaluator_identity}@{m.evaluator.evaluator_version} kind={m.evaluator.kind.value} independence_status={m.evaluator.independence_status} calibration_blank={m.evaluator.calibration_is_blank}",
        f"capture_boundary={m.capture_boundary.boundary_identity} (process separation declared: {m.capture_boundary.process_separation_ref})",
    ]
    if result.evaluator_flags:
        lines.append("evaluator flags: " + ", ".join(result.evaluator_flags))
    if result.coverage.qualified_declared == 0:
        lines.append("NO_QUALIFYING_METHOD: the advisory qualified no method for this task class; the pilot ran the governed baseline and challengers only")
    if result.result is not None:
        lines.append(f"authority_resolution_basis={result.result.authority_resolution_basis}; engine={result.result.engine_identity}@{result.result.engine_version}; result_digest={result.result.result_digest}")
    lines.append("METHODS:")
    views = {} if result.result is None else {v.record_digest: v for v in result.result.evidence_status}
    for run in result.runs:
        mid = f"{run.method.method_id}@{run.method.method_version}"
        if not run.complete:
            lines.append(f"  - {mid}: state INCONCLUSIVE ({'; '.join(run.reasons)}) [RESEARCH_ONLY]")
            continue
        rec, view = run.record, views.get(run.record.record_digest)
        att = run.attestation.attested_fields if run.attestation else ()
        for f in ("telemetry.llm_calls", "telemetry.token_usage.total_tokens"):
            value = rec.telemetry.llm_calls if f.endswith("llm_calls") else (None if rec.telemetry.token_usage is None else rec.telemetry.token_usage.total_tokens)
            a_status = (view.attestation_status.value if view is not None and f in view.attested_fields else "UNATTESTED")
            v_status = view.verification_status.value if view is not None else "UNVERIFIED"
            lines.append(f"  - {mid} {f}={value} source_basis=OBSERVED attestation={a_status} verification={v_status}")
        lines.append(f"  - {mid} quality={run.quality_result.value} source_basis={run.quality_claim.source_basis.value} independence_status={run.evaluation.independence_status} calibration_blank={m.evaluator.calibration_is_blank} [RESEARCH_ONLY]")
        d = run.diagnostics
        lines.append(f"  - {mid} {d.label}: total_llm_calls_reported={d.total_llm_calls_reported} harness_observed_calls={d.harness_observed_calls}")
        if run.method in result.outcomes:
            lines.append(_outcome_line(mid, result.outcomes[run.method]))
    if result.result is not None and result.result.refusals:
        lines.append("REFUSALS: " + "; ".join(f"{r.code.value}{'(' + r.method.method_id + ')' if r.method else ''}" for r in result.result.refusals))
    c = result.coverage
    lines.append(f"COVERAGE: admissible={c.admissible_method_count} assigned={c.methods_assigned} with_record={c.methods_with_record} baseline_has_record={c.baseline_has_record} qualified={c.qualified_with_record}/{c.qualified_declared} challengers={c.challengers_with_record}/{c.challengers_declared} without_record={[x.method_id for x in c.methods_without_record]} summary_permitted={c.summary_permitted}")
    summary = success_summary(c, m, result.outcomes)
    if summary is not None:
        lines.append("SUMMARY: " + summary.line())
    lines.append("LIFECYCLE:")
    for s in result.states:
        lines.append(f"  - {s.method.method_id}: {s.state.value} fit_outcome={s.fit_outcome.value if s.fit_outcome else None} refusals={list(s.refusal_codes)} approval_status={s.approval_status} usage_scope={s.usage_scope}")
    return "\n".join(lines)


__all__ = ["render", "FORBIDDEN_RENDERINGS"]
