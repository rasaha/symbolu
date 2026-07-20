#!/usr/bin/env python3
"""
Tests for the Edge Prioritization Experiment v0.1 (HybridRelationshipResolver v0.3).

Assert the discipline: P0 reproduces v0.2 exactly; prioritization is structurally
incapable of changing discovery / Mode G / Mode P (they are delegated to frozen code);
the priority vector is decomposable; and the preregistered outcome (no protected-metric
degradation) holds. The result itself is NO CLEAR SIGNAL — the tests pin that honestly
(net-zero decision change), not a hoped-for improvement.
"""

from __future__ import annotations

import json

from agentic.hybrid_handover.evaluation.corpus import all_cases
from agentic.hybrid_handover.resolution.experiment import hidden_metrics
from agentic.hybrid_handover.resolution.experiment.hidden_data import hidden_cases
from agentic.hybrid_handover.resolution.experiment_v2.hybrid_resolver_v2 import HybridRelationshipResolverV2
from agentic.hybrid_handover.resolution.experiment_v2.validator import ABLATIONS as V
from agentic.hybrid_handover.resolution.experiment_v3 import lock_v3
from agentic.hybrid_handover.resolution.experiment_v3 import run_prioritization_experiment as RP
from agentic.hybrid_handover.resolution.experiment_v3.hybrid_resolver_v3 import HybridRelationshipResolverV3
from agentic.hybrid_handover.resolution.experiment_v3.prioritizer import ABLATIONS as P
from agentic.hybrid_handover.resolution.measurement.stage_metrics import discovery_classification


def test_lock_v3_no_drift():
    assert lock_v3.verify() == []


def test_p0_reproduces_v2_on_visible_and_hidden():
    cases = all_cases()
    v2 = discovery_classification(HybridRelationshipResolverV2(V["V4_full"]), cases)
    p0 = discovery_classification(HybridRelationshipResolverV3(P["P0_none"]), cases)
    assert v2 == p0
    hc = hidden_cases()
    m2 = hidden_metrics.evaluate(HybridRelationshipResolverV2(V["V4_full"]), hc)["metrics"]
    m0 = hidden_metrics.evaluate(HybridRelationshipResolverV3(P["P0_none"]), hc)["metrics"]
    assert m2 == m0


def test_prioritization_cannot_change_discovery_modeG_modeP():
    hc = hidden_cases()
    m0 = hidden_metrics.evaluate(HybridRelationshipResolverV3(P["P0_none"]), hc)["metrics"]
    m4 = hidden_metrics.evaluate(HybridRelationshipResolverV3(P["P4_full"]), hc)["metrics"]
    for k in ("discovery_precision", "discovery_recall", "classification_accuracy",
              "governance_accuracy_modeG", "packet_realization_accuracy_modeP", "unsafe_answers"):
        assert m4[k] == m0[k], k


def test_priority_vector_is_decomposable():
    from agentic.hybrid_handover.resolution.experiment_v3.prioritizer import (
        COMPONENT_ORDER, GOVERNANCE_SOURCE_TYPES, priority_vector,
    )
    r = HybridRelationshipResolverV3(P["P4_full"])
    for case in hidden_cases():
        graph = r.resolve_relationships(case["question"], case["evidence"])
        conf = dict(r._v2._conf)
        srcs = {e.src for e in graph.edges if e.type in GOVERNANCE_SOURCE_TYPES}
        for n in graph.nodes:
            if n.key in srcs:
                v = priority_vector(n, graph, conf)
                assert set(v) == set(COMPONENT_ORDER)
                assert all(0.0 <= v[c] <= 1.0 for c in COMPONENT_ORDER)
                return  # one governance source is enough to exercise the vector


def test_primary_endpoint_no_protected_degradation_and_reproducible():
    out = RP.run()
    assert out["byte_identical_reps"] is True
    assert out["primary_endpoint"]["no_protected_degradation"] is True
    # honest pinning of the NO CLEAR SIGNAL result
    assert out["primary_endpoint"]["selective_gain"] == 0.0
    mc = out["statistics"]["mcnemar_answer_correct_p4_vs_p0"]
    assert mc["b10_candidate_fixes"] == 1 and mc["b01_candidate_breaks"] == 1
    assert out["competition"]["governance_decisions_changed"] == 2


def test_study_byte_identical():
    a = RP.run()
    b = RP.run()
    strip = lambda d: json.dumps({k: v for k, v in d.items() if not k.startswith("_")},
                                 sort_keys=True, default=str)
    assert strip(a) == strip(b)
