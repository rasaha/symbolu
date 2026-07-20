#!/usr/bin/env python3
"""
Tests for the Governance Semantics Experiment v0.1 (HybridRelationshipResolver v0.4).

Assert the discipline: G0 reproduces v0.2; the protected stages (discovery,
classification, validation, packet Mode P) are bit-identical across G0-G4; the
governing set (Mode G) is preserved; and the preregistered outcome holds — operative
selection (G3) improves selective accuracy cleanly while the full layer (G4) fails
non-inferiority via coverage collapse. Honest pinning of a NO CLEAR SIGNAL topline with
a clean G3 sub-signal.
"""

from __future__ import annotations

import json

from agentic.hybrid_handover.evaluation.corpus import all_cases
from agentic.hybrid_handover.resolution.experiment import hidden_metrics
from agentic.hybrid_handover.resolution.experiment.hidden_data import hidden_cases
from agentic.hybrid_handover.resolution.experiment_v2.hybrid_resolver_v2 import HybridRelationshipResolverV2
from agentic.hybrid_handover.resolution.experiment_v2.validator import ABLATIONS as V
from agentic.hybrid_handover.resolution.experiment_v4 import governance_semantics as GS
from agentic.hybrid_handover.resolution.experiment_v4 import lock_v4
from agentic.hybrid_handover.resolution.experiment_v4 import run_governance_experiment as RG
from agentic.hybrid_handover.resolution.experiment_v4.hybrid_resolver_v4 import HybridRelationshipResolverV4
from agentic.hybrid_handover.resolution.measurement.stage_metrics import discovery_classification


def test_lock_v4_and_prior_locks_clean():
    assert lock_v4.verify() == []
    prior = lock_v4.verify_prior_locks()
    assert prior["v0.1"] == [] and prior["v0.2"] == [] and prior["v0.3"] == []


def test_g0_reproduces_v2():
    cases = all_cases()
    assert discovery_classification(HybridRelationshipResolverV4(GS.ABLATIONS["G0_frozen"]), cases) \
        == discovery_classification(HybridRelationshipResolverV2(V["V4_full"]), cases)
    hc = hidden_cases()
    m0 = hidden_metrics.evaluate(HybridRelationshipResolverV4(GS.ABLATIONS["G0_frozen"]), hc)["metrics"]
    m2 = hidden_metrics.evaluate(HybridRelationshipResolverV2(V["V4_full"]), hc)["metrics"]
    assert m0 == m2


def test_protected_stages_identical_across_ablations():
    hc = hidden_cases()
    base = None
    for name in ["G0_frozen", "G1_supersession_amendment", "G2_parallel", "G3_operative", "G4_full"]:
        m = hidden_metrics.evaluate(HybridRelationshipResolverV4(GS.ABLATIONS[name]), hc)["metrics"]
        key = (m["discovery_precision"], m["discovery_recall"], m["discovery_f1"],
               m["classification_accuracy"], m["packet_realization_accuracy_modeP"])
        base = base or key
        assert key == base, name


def test_calibration_gates_pass():
    g = RG._calibration_gates()
    assert all(g.values()), g


def test_operative_selection_is_clean_signal():
    # G3 improves selective with coverage and mode G held fixed (non-coverage-driven)
    hc = hidden_cases()
    m0 = hidden_metrics.evaluate(HybridRelationshipResolverV4(GS.ABLATIONS["G0_frozen"]), hc)["metrics"]
    m3 = hidden_metrics.evaluate(HybridRelationshipResolverV4(GS.ABLATIONS["G3_operative"]), hc)["metrics"]
    assert m3["selective_accuracy"] > m0["selective_accuracy"]
    assert m3["answer_coverage"] == m0["answer_coverage"]
    assert m3["governance_accuracy_modeG"] == m0["governance_accuracy_modeG"]
    assert m3["unsafe_answers"] == m0["unsafe_answers"]


def test_full_layer_verdict_is_honest():
    out = RG.run()
    assert out["byte_identical_reps"] is True
    # primary G4 gain is large but non-inferiority fails (coverage-driven)
    assert out["primary_endpoint"]["selective_gain"] > 0.03
    assert out["non_inferiority"]["passes"] is False
    assert out["non_inferiority"]["bounded"]["answer_coverage"]["violated"] is True
    # 5 fixes, 0 breaks; unsafe not increased
    assert out["fix_break"]["fixes"] == 5 and out["fix_break"]["breaks"] == 0
    assert out["non_inferiority"]["unsafe_not_increased"] is True
    assert out["verdict"] == "NO CLEAR SIGNAL"


def test_study_byte_identical():
    a = RG.run()
    b = RG.run()
    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)
