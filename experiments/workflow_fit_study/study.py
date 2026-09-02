"""Workflow-Fit offline validation study — research harness.

Implements the *research configuration* the merged scoping note
``docs/architecture/WORKFLOW_FIT_READINESS_SCOPING_NOTE.md`` (§3, §8, §11)
says may proceed without any owner ballot:

* a caller-declared **provisional baseline** (no default);
* **runtime-recorded call count** as the only usable resource;
* **latency diagnostic only** — recorded, never compared;
* **independently scored quality** — the caller supplies a scorer over the
  final response; the workflow's own ``quality_score`` is carried for a future
  calibration study and is **never** read by the assessment;
* ``COMPARISON_EVIDENCE_ABSENT`` whenever the comparison cannot be made.

This is a harness, not a governed package. It changes no contract, no enum
and no runtime. Everything it records is **runtime-reported** — captured in
the same process that ran the workflow — and is labelled as such. Nothing here
is independently verified evidence.

Declared research rule (not ratified): resource comparison is **calls only,
strict**. With one resource, Pareto domination reduces to "another sufficient
tested workflow used strictly fewer calls". Ties are not domination. The note
records this reduction as an implicit cost rule chosen by omission.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_EVEN
from enum import Enum
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from agentic.agentic_framework.adaptive_prompts import ComplexityDetector
from agentic.agentic_framework.reasoning_workflows import (
    LLMClient,
    WorkflowRegistry,
    WorkflowResult,
    WorkflowSelector,
    WorkflowType,
    create_workflow_registry,
    create_workflow_selector,
)

__all__ = [
    "FitOutcome",
    "MEASUREMENT_SOURCE",
    "QUALITY_SOURCE",
    "RESOURCE_RULE",
    "TaskCase",
    "StudyConfig",
    "RunRecord",
    "ClassAggregate",
    "FitAssessment",
    "SelectorValidation",
    "StudyResult",
    "run_study",
    "assess",
    "validate_selector",
    "render_report",
]

MEASUREMENT_SOURCE = "RUNTIME_REPORTED (OBSERVED / UNATTESTED / UNVERIFIED)"
QUALITY_SOURCE = "INDEPENDENT_SCORER (caller-supplied; never the workflow's own score)"
RESOURCE_RULE = "calls-only-strict (declared research rule, not ratified)"
SUFFICIENCY_RULE = (
    "threshold-based (quality above tau carries no further value; a cheaper "
    "sufficient workflow dominates) — resolves scoping-note §11 ballot 3 in one "
    "direction for this study only; the ballot remains open"
)

_Q = Decimal("0.0001")


def _dec(x) -> Decimal:
    return Decimal(str(x)).quantize(_Q, rounding=ROUND_HALF_EVEN)


class FitOutcome(str, Enum):
    INSUFFICIENT_QUALITY = "INSUFFICIENT_QUALITY"
    SUFFICIENT_RESOURCE_DOMINATED = "SUFFICIENT_RESOURCE_DOMINATED"
    SUFFICIENT_PARETO_EFFICIENT = "SUFFICIENT_PARETO_EFFICIENT"
    COMPARISON_EVIDENCE_ABSENT = "COMPARISON_EVIDENCE_ABSENT"


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class TaskCase:
    """One benchmark case. ``scorer`` maps the final response to quality in [0, 1]
    and must be independent of the workflow — it never sees ``quality_score``."""

    case_id: str
    task_class: str
    query: str
    scorer: Callable[[str], Decimal]
    context: str = ""


@dataclass(frozen=True)
class StudyConfig:
    """Research configuration. No field has a default that encodes a judgement."""

    workflows: Tuple[WorkflowType, ...]
    baseline: WorkflowType
    sufficiency: Mapping[str, Decimal]  # tau per task class; absence => evidence absent
    max_llm_calls: int

    def __post_init__(self) -> None:
        if self.baseline not in self.workflows:
            raise ValueError("baseline must be one of the studied workflows")
        if len(set(self.workflows)) != len(self.workflows):
            raise ValueError("duplicate workflow in study set")
        if self.max_llm_calls <= 0:
            raise ValueError("max_llm_calls must be positive")
        for k, v in self.sufficiency.items():
            d = Decimal(str(v))
            if not (Decimal(0) <= d <= Decimal(1)):
                raise ValueError(f"sufficiency for {k!r} must lie in [0, 1]")


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RunRecord:
    case_id: str
    task_class: str
    workflow: WorkflowType
    quality: Decimal  # independent scorer
    calls_runtime_reported: int  # WorkflowResult.total_llm_calls
    calls_harness_observed: int  # counted at the client boundary by this harness
    duration_ms: float  # diagnostic only
    self_reported_quality: float  # carried for calibration study; never used here
    measurement_source: str = MEASUREMENT_SOURCE


class _CountingClient:
    """Wraps the caller's client at the harness boundary and counts calls.

    Still the same process and trust domain as the workflow, so this is a
    *second runtime-reported* count, not independent evidence. Its value is
    that a mismatch with ``WorkflowResult.total_llm_calls`` is detectable.
    """

    def __init__(self, inner: LLMClient) -> None:
        self._inner = inner
        self.calls = 0

    def call(self, prompt: str) -> str:
        self.calls += 1
        return self._inner.call(prompt)


def run_study(
    cases: Sequence[TaskCase],
    config: StudyConfig,
    llm_factory: Callable[[], LLMClient],
    registry: Optional[WorkflowRegistry] = None,
) -> List[RunRecord]:
    """Execute every studied workflow on every case. Deterministic given the
    client; each run gets a fresh client from ``llm_factory``."""

    reg = registry or create_workflow_registry()
    records: List[RunRecord] = []
    for case in cases:
        for wt in config.workflows:
            wf = reg.get(wt)
            client = _CountingClient(llm_factory())
            result: WorkflowResult = wf.execute(
                case.query, client, context=case.context, max_llm_calls=config.max_llm_calls
            )
            q = _dec(case.scorer(result.final_response))
            if not (Decimal(0) <= q <= Decimal(1)):
                raise ValueError(f"scorer returned {q} outside [0, 1] for {case.case_id}")
            records.append(
                RunRecord(
                    case_id=case.case_id,
                    task_class=case.task_class,
                    workflow=wt,
                    quality=q,
                    calls_runtime_reported=int(result.total_llm_calls),
                    calls_harness_observed=client.calls,
                    duration_ms=float(result.total_duration_ms),
                    self_reported_quality=float(result.quality_score),
                )
            )
    return records


# --------------------------------------------------------------------------- #
# Aggregation + assessment
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ClassAggregate:
    task_class: str
    workflow: WorkflowType
    n: int
    mean_quality: Decimal
    mean_calls: Decimal
    mean_duration_ms: Decimal  # diagnostic only
    call_count_mismatches: int  # runs where runtime-reported != harness-observed


def aggregate(records: Iterable[RunRecord]) -> Dict[Tuple[str, WorkflowType], ClassAggregate]:
    groups: Dict[Tuple[str, WorkflowType], List[RunRecord]] = defaultdict(list)
    for r in records:
        groups[(r.task_class, r.workflow)].append(r)
    out: Dict[Tuple[str, WorkflowType], ClassAggregate] = {}
    for key in sorted(groups, key=lambda k: (k[0], k[1].value)):
        rs = groups[key]
        n = len(rs)
        out[key] = ClassAggregate(
            task_class=key[0],
            workflow=key[1],
            n=n,
            mean_quality=_dec(sum(r.quality for r in rs) / n),
            mean_calls=_dec(Decimal(sum(r.calls_runtime_reported for r in rs)) / n),
            mean_duration_ms=_dec(Decimal(str(sum(r.duration_ms for r in rs))) / n),
            call_count_mismatches=sum(
                1 for r in rs if r.calls_runtime_reported != r.calls_harness_observed
            ),
        )
    return out


@dataclass(frozen=True)
class FitAssessment:
    task_class: str
    workflow: WorkflowType
    outcome: FitOutcome
    quality_margin: Optional[Decimal]  # mean_quality - tau; None when evidence absent
    resource_delta_calls: Optional[Decimal]  # mean_calls - cheapest sufficient; None when n/a
    dominated_by: Tuple[WorkflowType, ...]
    reason: str


def assess(
    records: Iterable[RunRecord], config: StudyConfig
) -> Dict[Tuple[str, WorkflowType], FitAssessment]:
    """Apply the four outcomes per (task class, workflow).

    Evidence is absent when: the class has no declared sufficiency threshold;
    the workflow has no runs in the class; or the baseline has no runs in the
    class (there is no comparison set). Quality below tau is
    INSUFFICIENT_QUALITY regardless of cost. Among sufficient workflows,
    domination is strictly-fewer mean calls (RESOURCE_RULE). Nothing here reads
    ``self_reported_quality``.
    """

    aggs = aggregate(records)
    classes = sorted({k[0] for k in aggs})
    out: Dict[Tuple[str, WorkflowType], FitAssessment] = {}
    for tc in classes:
        tau = config.sufficiency.get(tc)
        present = {wt: aggs[(tc, wt)] for wt in config.workflows if (tc, wt) in aggs}
        absent_reason = None
        if tau is None:
            absent_reason = "no sufficiency threshold declared for task class"
        elif config.baseline not in present:
            absent_reason = "baseline has no runs in task class; no comparison set"
        for wt in config.workflows:
            if wt not in present:
                out[(tc, wt)] = FitAssessment(tc, wt, FitOutcome.COMPARISON_EVIDENCE_ABSENT, None, None, (), "no runs for workflow in task class")
                continue
            if absent_reason:
                out[(tc, wt)] = FitAssessment(tc, wt, FitOutcome.COMPARISON_EVIDENCE_ABSENT, None, None, (), absent_reason)
                continue
        if absent_reason or tau is None:
            continue
        tau_d = _dec(tau)
        sufficient = {wt: a for wt, a in present.items() if a.mean_quality >= tau_d}
        cheapest = min((a.mean_calls for a in sufficient.values()), default=None)
        for wt, a in present.items():
            margin = _dec(a.mean_quality - tau_d)
            if a.mean_quality < tau_d:
                out[(tc, wt)] = FitAssessment(tc, wt, FitOutcome.INSUFFICIENT_QUALITY, margin, None, (), "mean quality below declared sufficiency threshold")
                continue
            dominators = tuple(
                v for v, b in sorted(sufficient.items(), key=lambda kv: kv[0].value)
                if v != wt and b.mean_calls < a.mean_calls
            )
            delta = _dec(a.mean_calls - cheapest) if cheapest is not None else None
            if dominators:
                out[(tc, wt)] = FitAssessment(tc, wt, FitOutcome.SUFFICIENT_RESOURCE_DOMINATED, margin, delta, dominators, "sufficient, but a sufficient alternative used strictly fewer calls")
            else:
                out[(tc, wt)] = FitAssessment(tc, wt, FitOutcome.SUFFICIENT_PARETO_EFFICIENT, margin, delta, (), "sufficient and no tested sufficient alternative used fewer calls")
    return out


# --------------------------------------------------------------------------- #
# Selector validation
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class SelectorValidation:
    case_id: str
    task_class: str
    routed: WorkflowType
    routing_reason: str
    routed_outcome: FitOutcome
    note: str


def validate_selector(
    cases: Sequence[TaskCase],
    assessments: Mapping[Tuple[str, WorkflowType], FitAssessment],
    config: StudyConfig,
    selector: Optional[WorkflowSelector] = None,
    detector: Optional[ComplexityDetector] = None,
) -> List[SelectorValidation]:
    """Route each case through the existing deterministic selector and report
    the fit outcome of the workflow it chose. The selector picks one workflow,
    so set-valued advisor measures do not apply here; this is the per-case
    dominated / insufficient / efficient rate of a single-choice router."""

    sel = selector or create_workflow_selector()
    det = detector or ComplexityDetector()
    out: List[SelectorValidation] = []
    for case in cases:
        routed, reason = sel.select(det.analyze(case.query))
        key = (case.task_class, routed)
        if routed not in config.workflows or key not in assessments:
            out.append(SelectorValidation(case.case_id, case.task_class, routed, reason, FitOutcome.COMPARISON_EVIDENCE_ABSENT, "routed workflow was not in the study set"))
            continue
        a = assessments[key]
        out.append(SelectorValidation(case.case_id, case.task_class, routed, reason, a.outcome, a.reason))
    return out


# --------------------------------------------------------------------------- #
# Result + report
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class StudyResult:
    config: StudyConfig
    records: Tuple[RunRecord, ...]
    aggregates: Mapping[Tuple[str, WorkflowType], ClassAggregate]
    assessments: Mapping[Tuple[str, WorkflowType], FitAssessment]
    selector: Tuple[SelectorValidation, ...]

    def selector_rates(self) -> Dict[str, Decimal]:
        n = len(self.selector)
        if n == 0:
            return {}
        counts = defaultdict(int)
        for s in self.selector:
            counts[s.routed_outcome.value] += 1
        return {o.value: _dec(Decimal(counts[o.value]) / n) for o in FitOutcome}


def run_full_study(
    cases: Sequence[TaskCase],
    config: StudyConfig,
    llm_factory: Callable[[], LLMClient],
    registry: Optional[WorkflowRegistry] = None,
) -> StudyResult:
    records = run_study(cases, config, llm_factory, registry)
    assessments = assess(records, config)
    return StudyResult(
        config=config,
        records=tuple(records),
        aggregates=aggregate(records),
        assessments=assessments,
        selector=tuple(validate_selector(cases, assessments, config)),
    )


def render_report(result: StudyResult) -> str:
    """Deterministic Markdown. Margins and deltas are attributes; nothing is
    combined into a score. Latency is shown as diagnostic only."""

    L: List[str] = []
    L.append("# Workflow-Fit offline validation study — research configuration")
    L.append("")
    L.append(f"- Quality source: {QUALITY_SOURCE}")
    L.append(f"- Telemetry source: {MEASUREMENT_SOURCE}")
    L.append(f"- Resource rule: {RESOURCE_RULE}")
    L.append(f"- Sufficiency rule: {SUFFICIENCY_RULE}")
    L.append(f"- Baseline (provisional, caller-declared): `{result.config.baseline.value}`")
    L.append(f"- Studied workflows: {', '.join('`'+w.value+'`' for w in result.config.workflows)}")
    L.append("- Latency: diagnostic only; not part of any comparison")
    L.append("- The workflow's own `quality_score` is recorded for a future calibration study and is never used here")
    L.append("")
    classes = sorted({k[0] for k in result.aggregates})
    for tc in classes:
        tau = result.config.sufficiency.get(tc)
        L.append(f"## Task class `{tc}` — τ = {('undeclared' if tau is None else _dec(tau))}")
        L.append("")
        L.append("| workflow | n | mean quality | margin (Q−τ) | mean calls | Δcalls vs cheapest sufficient | mean ms (diag.) | count mismatches | outcome | dominated by |")
        L.append("|---|---|---|---|---|---|---|---|---|---|")
        for wt in result.config.workflows:
            a = result.aggregates.get((tc, wt)); f = result.assessments.get((tc, wt))
            if a is None or f is None:
                L.append(f"| `{wt.value}` | 0 | — | — | — | — | — | — | `{FitOutcome.COMPARISON_EVIDENCE_ABSENT.value}` | — |")
                continue
            L.append(
                f"| `{wt.value}` | {a.n} | {a.mean_quality} | {'—' if f.quality_margin is None else f.quality_margin} | {a.mean_calls} | "
                f"{'—' if f.resource_delta_calls is None else f.resource_delta_calls} | {a.mean_duration_ms} | {a.call_count_mismatches} | `{f.outcome.value}` | "
                f"{', '.join('`'+d.value+'`' for d in f.dominated_by) or '—'} |"
            )
        L.append("")
    L.append("## Selector validation (existing deterministic `WorkflowSelector`)")
    L.append("")
    L.append("Single-choice router: set-valued advisor measures do not apply. Per-case outcome of the routed workflow:")
    L.append("")
    L.append("| case | task class | routed | outcome | note |")
    L.append("|---|---|---|---|---|")
    for s in result.selector:
        L.append(f"| `{s.case_id}` | `{s.task_class}` | `{s.routed.value}` | `{s.routed_outcome.value}` | {s.note} |")
    L.append("")
    rates = result.selector_rates()
    if rates:
        L.append("Routed-outcome rates: " + ", ".join(f"`{k}` {v}" for k, v in sorted(rates.items())))
        L.append("")
    L.append("_Nothing in this report is independently verified evidence. Method identity and telemetry are runtime-reported; quality is from the caller's scorer._")
    return "\n".join(L)
