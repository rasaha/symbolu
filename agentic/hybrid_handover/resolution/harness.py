#!/usr/bin/env python3
"""
Resolution evaluation harness. Runs each resolver under each evidence mode, scores
component metrics, attributes failures to a single stage, and produces per-case
analysis. Reports SEEB pipeline metrics unchanged (via the frozen aggregator) for
context — it does not redefine them.
"""

from __future__ import annotations

from agentic.hybrid_handover.evaluation.corpus import all_cases

from .attribution import attribute
from .gold import GOLD
from .metrics import ResolverScore, score_case, summarise
from .modes import MODES
from .resolvers import ALL_RESOLVERS, RESOLVER_ORDER


def _per_case(case, evidence, result, expected):
    gold = GOLD[case.case_id]
    stage = attribute(case.case_id, evidence, result, expected)
    return {
        "case_id": case.case_id,
        "retrieved_evidence": [s.citation for s in evidence],
        "relationship_graph": [list(e.triple()) for e in result.graph.edges],
        "governing_evidence": result.governance.governing,
        "discarded_evidence": result.governance.discarded,
        "abstained": result.governance.abstain,
        "abstain_reason": result.governance.abstain_reason,
        "final_packet": {"tfc": result.tfc, "notice_days": result.notice_days, "penalty": result.penalty},
        "expected": {"tfc": expected.termination_for_convenience,
                     "notice_days": expected.notice_days, "penalty": expected.penalty,
                     "abstain": gold.abstain},
        "correct": stage == "none",
        "failure_stage": stage,
    }


def evaluate_resolver(resolver, mode_name):
    mode_fn = MODES[mode_name]
    score = ResolverScore()
    per_case = []
    stage_counts = {}
    for case in all_cases():
        evidence = mode_fn(case)
        result = resolver.resolve(case.question, evidence)
        score_case(case.case_id, result, case.expected_answer, score)
        pc = _per_case(case, evidence, result, case.expected_answer)
        per_case.append(pc)
        stage_counts[pc["failure_stage"]] = stage_counts.get(pc["failure_stage"], 0) + 1
    return {
        "metrics": summarise(score),
        "n_correct": sum(1 for p in per_case if p["correct"]),
        "n_cases": len(per_case),
        "failure_attribution": stage_counts,
        "per_case": per_case,
    }


def run_all():
    from .pipeline_bridge import pipeline_metrics
    out = {"benchmark": "SEEB", "benchmark_version": "1.0.0", "synthetic": True,
           "resolvers": {}}
    for rname in RESOLVER_ORDER:
        resolver = ALL_RESOLVERS[rname]()
        out["resolvers"][rname] = {}
        for mode_name in MODES:
            out["resolvers"][rname][mode_name] = evaluate_resolver(resolver, mode_name)
        # existing SEEB pipeline metrics, unchanged, via the frozen aggregator
        out["resolvers"][rname]["pipeline_metrics_seeb_B_bm25"] = pipeline_metrics(resolver, "B_bm25")
    return out
