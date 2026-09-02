"""Research-only pilot fixtures: one task class, seven-method catalog, rules.research.v0,
an advisory over the class's profile, a benchmark manifest of digested cases, declarations,
and the preregistered manifest. Every instant is fixed; nothing here is a governed value."""

from __future__ import annotations

import os
import sys
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, Optional, Tuple

import matrix_fixtures as fx
import rule_fixtures as rf
from ugence_governance_contracts.api import BenchmarkReference
from ugence_reasoning_method_advisor.api import ADVISORY_REQUEST_SCHEMA_VERSION, ReasoningMethodAdvisoryRequest, advise
from ugence_reasoning_method_governance.api import (
    PROFILE_SCHEMA_VERSION,
    RESEARCH_PLAN_SCHEMA_VERSION,
    TASK_CLASS_SCHEMA_VERSION,
    AggregationRef,
    BindingRef,
    ChallengerSamplingPolicy,
    ComparisonPolicy,
    ConsequenceClass,
    ReasoningMethodRef,
    ResearchComparisonPlan,
    ResourceDimension,
    SamplingKind,
    SufficiencyKind,
    SufficiencyRule,
    TaskClassIdentity,
    TaskProfile,
    TaskReversibility,
)
from ugence_uvi_policy_contracts.api import ComparisonOperator, GovernedThreshold
from ugence_workflow_fit_pilot._canon import digest_of
from ugence_workflow_fit_pilot.api import (
    ATTESTABLE_TELEMETRY_FIELDS,
    BENCHMARK_MANIFEST_SCHEMA_VERSION,
    PILOT_MANIFEST_SCHEMA_VERSION,
    BenchmarkManifest,
    CaptureBoundaryDeclaration,
    EvaluatorKind,
    ExecutionOutcome,
    PilotCase,
    PilotIdentity,
    PilotMethodAssignment,
    PilotRole,
    PilotStudyManifest,
    QualityEvaluatorDeclaration,
    admissible_methods,
    case_list_digest,
)

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 9, 2, 12, 30, tzinfo=timezone.utc)
TESTS_DIR = str(Path(__file__).resolve().parent)
TOKENS = ("comparison_request", "ambiguity_detected", "creative_synthesis")
QUALITY_AGG = AggregationRef("research.mean", "0", "calc:experiments.workflow_fit_study.mean_over_cases.v0")
RESOURCE_AGG = AggregationRef("pilot.sum_over_cases", "0", "calc:workflow_fit_pilot.sum_calls_over_case_set.v0")
IDENTITY = PilotIdentity("tenant:research", "subject:pilot", "adapter:pilot-runner", "requester:pilot", "model:stub")


def clock():
    """A caller-supplied instant sequence: strictly increasing so records are constructible."""
    t = [LATER]

    def now():
        t[0] = t[0].replace(microsecond=t[0].microsecond + 1) if t[0].microsecond < 999_999 else t[0].replace(second=t[0].second + 1, microsecond=0)
        return t[0]

    return now


def cases() -> Tuple[PilotCase, ...]:
    raw = [("case.1", "Compare vendor A and vendor B for a support desk.", ""), ("case.2", "Which of two refund policies resolves an ambiguous ticket?", "policy context")]
    out = []
    for cid, q, ctx in raw:
        out.append(PilotCase(cid, digest_of({"case_id": cid, "query": q, "context": ctx}), q, ctx))
    return tuple(sorted(out, key=lambda c: c.case_digest))


def benchmark(issued_at=NOW, extra_case: Optional[str] = None) -> BenchmarkManifest:
    digests = tuple(sorted(c.case_digest for c in cases()) + ([extra_case] if extra_case else []))
    head = BenchmarkReference("benchmark.pilot.hard", "1", case_list_digest(digests), "issuer:pilot-fixture")
    return BenchmarkManifest(BENCHMARK_MANIFEST_SCHEMA_VERSION, head, digests, len(digests), "issuer:pilot-fixture", issued_at)


def task_class(bm: Optional[BenchmarkManifest] = None, threshold: str = "0.9", rule_version: str = "0", tokens=TOKENS) -> TaskClassIdentity:
    bm = bm or benchmark()
    rule = SufficiencyRule("study.hard.sufficiency", rule_version, SufficiencyKind.THRESHOLD_BASED, GovernedThreshold("study.hard.tau", "score.unit", ComparisonOperator.GTE, threshold))
    policy = ComparisonPolicy("study.hard.policy", "0", rule, (ResourceDimension.LLM_CALLS,), QUALITY_AGG)
    return TaskClassIdentity(TASK_CLASS_SCHEMA_VERSION, "study.hard", "domain:support", "outcome:resolve", ConsequenceClass.RECOVERABLE, TaskReversibility.OUTCOME_COMPENSATABLE,
                             (), (), tokens, "population:support-tickets", bm.benchmark.benchmark_id, bm.benchmark_manifest_digest, policy)


def profile(tokens=TOKENS) -> TaskProfile:
    return TaskProfile(PROFILE_SCHEMA_VERSION, "profile.hard", "domain:support", "outcome:resolve", ConsequenceClass.RECOVERABLE, TaskReversibility.OUTCOME_REVERSIBLE, (), (), tokens, "population:support-tickets")


def catalog():
    return fx.c4_catalog()


def rule_set():
    return rf.research_rules_v0()


def advisory(tc: Optional[TaskClassIdentity] = None, tokens=TOKENS):
    tc = tc or task_class(tokens=tokens)
    req = ReasoningMethodAdvisoryRequest(ADVISORY_REQUEST_SCHEMA_VERSION, "pilot.advice", profile(tokens), tc, catalog(), rule_set(), "requester:pilot")
    return advise(req, advised_at=NOW)


def binding(configuration_digest: str = fx.HEX_A) -> BindingRef:
    return BindingRef("binding.pilot", "config.pilot", configuration_digest, fx.HEX_B, digest_of({"binding": "pilot", "configuration_digest": configuration_digest}))


def plan(tc: Optional[TaskClassIdentity] = None, adv=None, bnd: Optional[BindingRef] = None, baseline_id: str = "linear_chain") -> ResearchComparisonPlan:
    tc = tc or task_class()
    adv = adv if adv is not None else advisory(tc)
    cat = catalog()
    baseline = ReasoningMethodRef(cat.ref(), baseline_id, "1")
    recommended = tuple(q.method for q in adv.qualifying) if adv is not None else ()
    return ResearchComparisonPlan(RESEARCH_PLAN_SCHEMA_VERSION, "plan.pilot.hard", tc, bnd or binding(), cat.ref(), baseline, recommended,
                                  ChallengerSamplingPolicy(SamplingKind.PREREGISTERED, "prereg:exhaustive-catalog", "coverage:exhaustive-declared"), "RESEARCH_ONLY", "owner:pilot", NOW)


def boundary_decl(fields=ATTESTABLE_TELEMETRY_FIELDS, identity: str = "boundary:pilot-gateway") -> CaptureBoundaryDeclaration:
    return CaptureBoundaryDeclaration(identity, "0.1.0", "separation:declared:separate-os-process:unverified", "unix-socket:runner-owned-tempdir", tuple(fields))


def evaluator_decl(bm: Optional[BenchmarkManifest] = None, kind: EvaluatorKind = EvaluatorKind.PROGRAMMATIC, model_ref=None, identity: str = "evaluator:keyword-scorer", calibration: str = "") -> QualityEvaluatorDeclaration:
    bm = bm or benchmark()
    return QualityEvaluatorDeclaration(identity, "0", kind, model_ref, "separation:declared:runner-process-scorer", digest_of({"instructions": "score 1 if ANSWER present else 0.5", "benchmark": bm.benchmark_manifest_digest, "rule": "study.hard.sufficiency"}), bm.benchmark_manifest_digest, calibration)


def assignments(adv=None, cat=None, rs=None, baseline_id: str = "linear_chain") -> Tuple[PilotMethodAssignment, ...]:
    cat, rs = cat or catalog(), rs or rule_set()
    qualified = {q.method for q in adv.qualifying} if adv is not None else set()
    out = []
    for m in admissible_methods(cat, rs):
        roles = []
        if m.method_id == baseline_id:
            roles.append(PilotRole.GOVERNED_BASELINE)
        if m in qualified:
            roles.append(PilotRole.ADVISOR_QUALIFIED)
        else:
            roles.append(PilotRole.CHALLENGER)
        out.append(PilotMethodAssignment(m, tuple(sorted(roles, key=list(PilotRole).index))))
    return tuple(sorted(out, key=lambda a: a.method.sort_key))


def manifest(*, adv="default", tc: Optional[TaskClassIdentity] = None, bm: Optional[BenchmarkManifest] = None, methods=None, boundary=None, evaluator=None, quality_agg=QUALITY_AGG, resource_agg=RESOURCE_AGG, preregistered_at=NOW, manifest_id="manifest.pilot.hard", bnd=None) -> PilotStudyManifest:
    bm = bm or benchmark()
    tc = tc or task_class(bm)
    a = advisory(tc) if adv == "default" else adv
    p = plan(tc, a, bnd)
    return PilotStudyManifest(
        PILOT_MANIFEST_SCHEMA_VERSION, manifest_id, p, a.advisory_digest if a is not None else None, a.rule_set if a is not None else None,
        methods if methods is not None else assignments(a), bm, boundary or boundary_decl(), evaluator or evaluator_decl(bm), resource_agg, quality_agg, "owner:pilot", preregistered_at,
    )


class FakeExecutor:
    """Calls the client a declared number of times per method and returns canned text."""

    def __init__(self, calls_per_method: Dict[str, int], response: str = "ANSWER: fake", report_offset: int = 0) -> None:
        self.calls_per_method, self.response, self.report_offset = calls_per_method, response, report_offset
        self.counts: Dict[str, int] = {}

    def execute(self, method, query, context, client) -> ExecutionOutcome:
        n = self.calls_per_method[method.method_id]
        text = ""
        for i in range(n):
            self.counts[method.method_id] = self.counts.get(method.method_id, 0) + 1
            text = client.call(f"{query} [{method.method_id} call {self.counts[method.method_id]}]")
        return ExecutionOutcome(final_response=text or self.response, total_llm_calls_reported=n + self.report_offset)


class KeywordScorer:
    def score(self, case_digest: str, response: str) -> Decimal:
        return Decimal("1.0") if "ANSWER" in response else Decimal("0.5")


def boundary_env(mode: str = "ok") -> Dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([TESTS_DIR] + [p for p in sys.path if p])
    env["WFP_STUB_MODE"] = mode
    return env


DEFAULT_CALLS = {"linear_chain": 1, "tree_of_thought": 4, "iterative_refinement": 3, "debate": 5, "map_reduce": 2, "socratic_progressive": 3, "metacognitive": 2}
