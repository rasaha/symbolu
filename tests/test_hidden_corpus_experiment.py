#!/usr/bin/env python3
"""
Tests for the Exploratory Resolver Study v0.1 (preregistered resolver comparison).

These tests assert the DISCIPLINE and the REPRODUCIBILITY of the study, not a
particular "good" score: determinism, frozen-component integrity, protocol
conformance, isolation of the discovery layer, and the correctness of the
statistics primitives. The headline numbers are pinned so a regression in the
harness is caught, but the verdict logic (non-inferiority) is asserted as a
property, not a hoped-for outcome.
"""

from __future__ import annotations

import json

from agentic.hybrid_handover.resolution.audit.adversarial import AlwaysAbstain, NullResolver
from agentic.hybrid_handover.resolution.experiment import hidden_metrics, lock, stats
from agentic.hybrid_handover.resolution.experiment import run_experiment as R
from agentic.hybrid_handover.resolution.experiment.hidden_data import hidden_cases
from agentic.hybrid_handover.resolution.experiment.hybrid_resolver import (
    ABLATIONS, HybridRelationshipResolver,
)
from agentic.hybrid_handover.resolution.resolvers import GraphTraversalResolver


# --------------------------------------------------------------------------- #
# frozen-component integrity + corpus immutability
# --------------------------------------------------------------------------- #
def test_lock_has_no_drift():
    # every locked source + frozen dependency is byte-identical to lock time
    assert lock.verify() == []


def test_hidden_corpus_is_the_frozen_60_and_seed_unchanged():
    cases = hidden_cases()
    assert len(cases) == 60
    assert sum(1 for c in cases if c["source"] == "seed") == 22
    assert sum(1 for c in cases if c["source"] == "pilot") == 38


# --------------------------------------------------------------------------- #
# protocol conformance + method boundary (deterministic, no LLM/training)
# --------------------------------------------------------------------------- #
def test_hybrid_conforms_to_resolver_protocol():
    r = HybridRelationshipResolver()
    for m in ("resolve_relationships", "resolve_governance", "resolve", "intermediate_artifacts"):
        assert callable(getattr(r, m))
    c = hidden_cases()[0]
    res = r.resolve(c["question"], c["evidence"])
    assert hasattr(res, "graph") and hasattr(res, "governance")


def test_hybrid_is_deterministic():
    c = hidden_cases()[0]
    a = HybridRelationshipResolver().intermediate_artifacts(c["question"], c["evidence"])
    b = HybridRelationshipResolver().intermediate_artifacts(c["question"], c["evidence"])
    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


# --------------------------------------------------------------------------- #
# isolation: governance + packet are the frozen components, unchanged
# --------------------------------------------------------------------------- #
def test_gain_is_isolated_to_discovery():
    cases = hidden_cases()
    gt = hidden_metrics.evaluate(GraphTraversalResolver(), cases)["metrics"]
    hy = hidden_metrics.evaluate(HybridRelationshipResolver(), cases)["metrics"]
    # governance (Mode G) and packet (Mode P) identical → gain is discovery-only
    assert hy["governance_accuracy_modeG"] == gt["governance_accuracy_modeG"]
    assert hy["packet_realization_accuracy_modeP"] == gt["packet_realization_accuracy_modeP"]
    # discovery genuinely improves
    assert hy["discovery_recall"] > gt["discovery_recall"]


def test_ablation_A1_returns_to_baseline():
    # removing the semantic proposal layer must collapse the gain to GraphTraversal
    cases = hidden_cases()
    base = hidden_metrics.evaluate(GraphTraversalResolver(), cases)["metrics"]["primary_macro"]
    a1 = hidden_metrics.evaluate(
        HybridRelationshipResolver(ABLATIONS["A1_no_semantic"]), cases)["metrics"]["primary_macro"]
    assert a1 == base


# --------------------------------------------------------------------------- #
# statistics primitives
# --------------------------------------------------------------------------- #
def test_mcnemar_exact_symmetry_and_bounds():
    assert stats.mcnemar_exact([True] * 5, [True] * 5)["p_value"] == 1.0
    m = stats.mcnemar_exact([True, True, True, False], [False, False, False, False])
    assert m["b10_candidate_fixes"] == 3 and m["b01_candidate_breaks"] == 0
    assert 0.0 <= m["p_value"] <= 1.0


def test_bootstrap_is_seed_deterministic():
    a = stats.paired_bootstrap_diff([1, 1, 1, 0, 1], [0, 0, 1, 0, 1])
    b = stats.paired_bootstrap_diff([1, 1, 1, 0, 1], [0, 0, 1, 0, 1])
    assert a == b


def test_holm_monotone_rejection():
    out = stats.holm({"a": 0.001, "b": 0.04, "c": 0.5})
    assert out["a"]["reject_null"] is True
    assert out["c"]["reject_null"] is False


# --------------------------------------------------------------------------- #
# end-to-end study result: reproducible, and the preregistered verdict logic holds
# --------------------------------------------------------------------------- #
def test_study_reproducible_and_primary_endpoint():
    out = R.run()
    assert out["byte_identical_reps"] is True
    p = out["primary_endpoint"]
    # pinned headline numbers (regression guard on the harness)
    assert p["graph_traversal"] == 0.4973
    assert p["hybrid_relationship"] == 0.5761
    assert p["macro_gain"] == 0.0788
    assert p["practically_significant"] is True
    # bootstrap CI excludes zero
    assert out["statistics"]["bootstrap_macro_hybrid_minus_graph"]["excludes_zero"] is True


def test_non_inferiority_verdict_is_honest():
    # the study must NOT claim a clean win: precision + selective violations stand,
    # while safety (unsafe answers) is not worse.
    out = R.run()
    ni = out["non_inferiority"]["hybrid_relationship"]
    assert ni["passes_non_inferiority"] is False
    assert ni["rows"]["discovery_precision"]["violated"] is True
    assert ni["rows"]["unsafe_answers"]["violated"] is False


def test_adversarial_comparators_do_not_win():
    # a gameable macro would let Null/Always-abstain approach the real resolvers
    cases = hidden_cases()
    null = hidden_metrics.evaluate(NullResolver(), cases)["metrics"]["primary_macro"]
    aba = hidden_metrics.evaluate(AlwaysAbstain(), cases)["metrics"]["primary_macro"]
    hy = hidden_metrics.evaluate(HybridRelationshipResolver(), cases)["metrics"]["primary_macro"]
    assert hy > null + 0.3 and hy > aba + 0.3
