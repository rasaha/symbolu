"""The harness adapter round-trips a study into governed records and claims whose
digests are stable across two runs, and the engine reproduces the harness's
outcomes (spec §9 items 5 and definition of done)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from agentic.agentic_framework.reasoning_workflows import WorkflowType
from experiments.workflow_fit_study.governed_adapter import (
    RESEARCH_MEAN,
    AdapterRefusal,
    StudyClassDeclaration,
    adapt_class,
    build_task_class,
)
from experiments.workflow_fit_study.study import FitOutcome as HarnessOutcome
from experiments.workflow_fit_study.study import RunRecord, StudyConfig, assess
from ugence_readiness_comparison import compare
from ugence_reasoning_method_governance.api import (
    CATALOG_SCHEMA_VERSION,
    BindingRef,
    ConsequenceClass,
    CountBasis,
    FitOutcome,
    ImplementationEvidence,
    ImplementationEvidenceKind,
    ReasoningMethodCatalog,
    ReasoningMethodEntry,
    SufficiencyKind,
    TaskReversibility,
)

NOW = datetime(2026, 9, 2, tzinfo=timezone.utc)
HEX = "e" * 64
LC, TOT, DEB = WorkflowType.LINEAR_CHAIN, WorkflowType.TREE_OF_THOUGHT, WorkflowType.DEBATE


def rec(tc, wf, q, calls, case, self_q=0.5):
    return RunRecord(case, tc, wf, Decimal(str(q)), calls, calls, 1.0, self_q)


def catalog():
    ev = (ImplementationEvidence(ImplementationEvidenceKind.CONCRETE_CLASS_REGISTERED, "agentic/agentic_framework/reasoning_workflows.py", NOW),)
    entries = tuple(sorted((ReasoningMethodEntry(w.value, "1", w.value, ev, (), ()) for w in (LC, TOT, DEB)), key=lambda e: e.sort_key))
    return ReasoningMethodCatalog(CATALOG_SCHEMA_VERSION, "cat.study", "1", entries, "issuer:study", NOW)


def declaration(tc):
    return StudyClassDeclaration(tc, "domain:study", "outcome:study", ConsequenceClass.RECOVERABLE, TaskReversibility.OUTCOME_REVERSIBLE, "population:study", "benchmarks:study", HEX, ("comparison_request",), SufficiencyKind.THRESHOLD_BASED)


def adapt(records, config, tc, request_id="req"):
    task_class = build_task_class(declaration(tc), config)
    return adapt_class(
        records=records, task_class=task_class, study_class=tc, catalog=catalog(), method_versions={w.value: "1" for w in (LC, TOT, DEB)},
        binding=BindingRef("binding.study", "config.study", HEX, HEX, HEX), tenant_id="tenant.study", subject_id="subject.study",
        issuer_identity="adapter:workflow_fit_study", model_ref="model:stub", captured_at=NOW, baseline_workflow=LC.value, request_id=request_id,
    )


STUDY = [
    rec("easy", LC, 0.92, 1, "c1"), rec("easy", LC, 0.90, 1, "c2"),
    rec("easy", TOT, 0.94, 4, "c1"), rec("easy", TOT, 0.96, 5, "c2"),
    rec("easy", DEB, 0.95, 5, "c1"), rec("easy", DEB, 0.95, 5, "c2"),
    rec("hard", LC, 0.72, 1, "c1"), rec("hard", LC, 0.70, 1, "c2"),
    rec("hard", TOT, 0.91, 4, "c1"), rec("hard", TOT, 0.93, 4, "c2"),
    rec("hard", DEB, 0.93, 5, "c1"), rec("hard", DEB, 0.95, 6, "c2"),
]
CONFIG = StudyConfig(workflows=(LC, TOT, DEB), baseline=LC, sufficiency={"easy": Decimal("0.90"), "hard": Decimal("0.90")}, max_llm_calls=10)


def test_adapter_emits_one_record_and_one_calculated_claim_per_method():
    req = adapt(STUDY, CONFIG, "easy")
    assert len(req.records) == 3 and len(req.quality_results) == 3 and len(req.quality_claims) == 3
    assert all(q.aggregation == RESEARCH_MEAN for q in req.quality_results)
    assert req.task_class.comparison_policy.quality_aggregation == RESEARCH_MEAN
    assert all(c.transformation_method.value == "CALCULATED" and c.calculation_ref == RESEARCH_MEAN.calculation_ref for c in req.quality_claims)
    assert all(r.telemetry.llm_calls_basis is CountBasis.CALLER_SUPPLIED for r in req.records)
    tot = next(r for r in req.records if r.method.method_id == "tree_of_thought")
    assert tot.telemetry.llm_calls == 9 and len([c for c in tot.telemetry.capture_refs if ":case:" in c]) == 2
    assert not any("self_reported_quality" in ref for c in req.quality_claims for ref in c.input_evidence_refs + c.evidence_refs)


def test_engine_reproduces_harness_outcomes():
    harness = assess(STUDY, CONFIG)
    mapping = {
        HarnessOutcome.INSUFFICIENT_QUALITY: FitOutcome.INSUFFICIENT_QUALITY,
        HarnessOutcome.SUFFICIENT_RESOURCE_DOMINATED: FitOutcome.SUFFICIENT_RESOURCE_DOMINATED,
        HarnessOutcome.SUFFICIENT_PARETO_EFFICIENT: FitOutcome.SUFFICIENT_PARETO_EFFICIENT,
        HarnessOutcome.COMPARISON_EVIDENCE_ABSENT: FitOutcome.COMPARISON_EVIDENCE_ABSENT,
    }
    for tc in ("easy", "hard"):
        res = compare(adapt(STUDY, CONFIG, tc, request_id=f"req.{tc}"), produced_at=NOW)
        assert [r.code.value for r in res.refusals] == []
        got = {a.method.method_id: a.outcome for a in res.assessments}
        for wf in (LC, TOT, DEB):
            assert got[wf.value] is mapping[harness[(tc, wf)].outcome], (tc, wf)
        assert all(a.usage_scope == "RESEARCH_ONLY" for a in res.assessments)


def test_digests_stable_across_two_runs():
    a, b = adapt(STUDY, CONFIG, "easy"), adapt(STUDY, CONFIG, "easy")
    assert [r.record_digest for r in a.records] == [r.record_digest for r in b.records]
    assert a.task_class.task_class_digest == b.task_class.task_class_digest
    assert compare(a, produced_at=NOW).result_digest == compare(b, produced_at=NOW).result_digest


def test_adapter_refuses_without_threshold_and_with_mismatched_case_sets():
    with pytest.raises(AdapterRefusal):
        build_task_class(declaration("easy"), StudyConfig(workflows=(LC, TOT), baseline=LC, sufficiency={}, max_llm_calls=5))
    uneven = STUDY + [rec("easy", TOT, 0.9, 4, "c3")]
    with pytest.raises(AdapterRefusal):
        adapt(uneven, CONFIG, "easy")


def test_self_reported_quality_flip_does_not_change_outcomes():
    flipped = [RunRecord(r.case_id, r.task_class, r.workflow, r.quality, r.calls_runtime_reported, r.calls_harness_observed, r.duration_ms, 1.0) for r in STUDY]
    a = compare(adapt(STUDY, CONFIG, "hard"), produced_at=NOW)
    b = compare(adapt(flipped, CONFIG, "hard"), produced_at=NOW)
    assert [(x.method.method_id, x.outcome, x.quality_margin) for x in a.assessments] == [(x.method.method_id, x.outcome, x.quality_margin) for x in b.assessments]
