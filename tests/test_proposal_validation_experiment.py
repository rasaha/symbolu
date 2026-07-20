#!/usr/bin/env python3
"""
Tests for the Proposal Validation Experiment v0.1 (HybridRelationshipResolver v0.2).

Assert the discipline: V0 reproduces Hybrid v0.1 exactly, the validator is a no-op on
the all-correct visible corpus, the frozen governance/packet are untouched, the
confidence vector is decomposable, and the preregistered primary endpoint holds
(precision recovered at zero recall loss, no correct edge rejected).
"""

from __future__ import annotations

import json

from agentic.hybrid_handover.evaluation.corpus import all_cases
from agentic.hybrid_handover.resolution.experiment import hidden_metrics
from agentic.hybrid_handover.resolution.experiment.hidden_data import hidden_cases
from agentic.hybrid_handover.resolution.experiment.hybrid_resolver import HybridRelationshipResolver
from agentic.hybrid_handover.resolution.experiment_v2 import lock_v2
from agentic.hybrid_handover.resolution.experiment_v2 import run_validation_experiment as RV
from agentic.hybrid_handover.resolution.experiment_v2.hybrid_resolver_v2 import HybridRelationshipResolverV2
from agentic.hybrid_handover.resolution.experiment_v2.validator import ABLATIONS
from agentic.hybrid_handover.resolution.measurement.stage_metrics import discovery_classification


def test_lock_v2_no_drift():
    assert lock_v2.verify() == []


def test_v0_reproduces_hybrid_v1_on_visible_and_hidden():
    cases = all_cases()
    v1 = discovery_classification(HybridRelationshipResolver(), cases)
    v0 = discovery_classification(HybridRelationshipResolverV2(ABLATIONS["V0_none"]), cases)
    assert v1 == v0
    hc = hidden_cases()
    m1 = hidden_metrics.evaluate(HybridRelationshipResolver(), hc)["metrics"]
    m0 = hidden_metrics.evaluate(HybridRelationshipResolverV2(ABLATIONS["V0_none"]), hc)["metrics"]
    assert m1 == m0


def test_full_validator_rejects_no_correct_visible_edge():
    cases = all_cases()
    v0 = discovery_classification(HybridRelationshipResolverV2(ABLATIONS["V0_none"]), cases)
    v4 = discovery_classification(HybridRelationshipResolverV2(ABLATIONS["V4_full"]), cases)
    # visible is all-correct; the validator must not drop recall or precision
    assert v4["discovery_recall"] == v0["discovery_recall"] == 1.0
    assert v4["discovery_precision"] == v0["discovery_precision"] == 1.0


def test_governance_and_packet_unchanged_by_validation():
    hc = hidden_cases()
    m0 = hidden_metrics.evaluate(HybridRelationshipResolverV2(ABLATIONS["V0_none"]), hc)["metrics"]
    m4 = hidden_metrics.evaluate(HybridRelationshipResolverV2(ABLATIONS["V4_full"]), hc)["metrics"]
    assert m4["governance_accuracy_modeG"] == m0["governance_accuracy_modeG"]
    assert m4["packet_realization_accuracy_modeP"] == m0["packet_realization_accuracy_modeP"]
    assert m4["unsafe_answers"] <= m0["unsafe_answers"]


def test_confidence_vector_is_decomposable():
    r = HybridRelationshipResolverV2(ABLATIONS["V4_full"])
    c = hidden_cases()[0]
    recs = r.validation_records(c["question"], c["evidence"])
    for rec in recs:
        v = rec["confidence_vector"]
        assert set(v) == {"lexical", "structural", "authority", "reference"}
        assert all(0.0 <= v[k] <= 1.0 for k in v)


def test_primary_endpoint_precision_recovered_at_zero_recall_loss():
    out = RV.run()
    p = out["primary_endpoint"]
    assert p["precision_gain"] > 0
    assert p["recall_loss"] <= 0.03
    assert p["endpoint_met"] is True
    # no correct edge rejected; some incorrect removed
    tax = out["rejection_taxonomy"]
    assert tax["correct_rejected"] == 0
    assert tax["incorrect_removed"] > 0


def test_study_is_byte_identical_reproducible():
    a = RV.run()
    b = RV.run()
    strip = lambda d: json.dumps({k: v for k, v in d.items() if k != "_per_edge"},
                                 sort_keys=True, default=str)
    assert a["byte_identical_reps"] is True
    assert strip(a) == strip(b)
