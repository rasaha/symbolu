#!/usr/bin/env python3
"""
Tests for the Competing Operative Resolution Experiment v0.1 (HybridRelationshipResolver
v0.5). Assert: C0 reproduces G3; protected stages identical across C0-C4; the five G3
fixes are retained under C4; co-occurrence alone never abstains while a genuine conflict
does (synthetic gates C8/C9); non-inferiority holds; and the honest NO CLEAR SIGNAL
outcome (zero genuine conflicts, zero fixes/breaks) is pinned.
"""

from __future__ import annotations

import json

from agentic.hybrid_handover.resolution.experiment import hidden_metrics
from agentic.hybrid_handover.resolution.experiment.hidden_data import hidden_cases
from agentic.hybrid_handover.resolution.experiment_v4 import governance_semantics as GS
from agentic.hybrid_handover.resolution.experiment_v4.hybrid_resolver_v4 import HybridRelationshipResolverV4
from agentic.hybrid_handover.resolution.experiment_v5 import competing_operative as CO
from agentic.hybrid_handover.resolution.experiment_v5 import lock_v5, synthetic_fixtures
from agentic.hybrid_handover.resolution.experiment_v5 import run_competing_operative_experiment as RC
from agentic.hybrid_handover.resolution.experiment_v5.hybrid_resolver_v5 import HybridRelationshipResolverV5

G3_FIXES = {"HX59d7a3eb1c", "HP059f01c294", "HP7d8d12efac", "HPb3463204c9", "HPebe6e8abf0"}


def test_lock_v5_and_prior_locks_clean():
    assert lock_v5.verify() == []
    prior = lock_v5.verify_prior_locks()
    assert all(v == [] for v in prior.values())


def test_c0_reproduces_g3():
    hc = hidden_cases()
    m0 = hidden_metrics.evaluate(HybridRelationshipResolverV5(CO.ABLATIONS["C0_g3_control"]), hc)["metrics"]
    mg3 = hidden_metrics.evaluate(HybridRelationshipResolverV4(GS.ABLATIONS["G3_operative"]), hc)["metrics"]
    assert m0 == mg3


def test_protected_stages_identical_across_ablations():
    hc = hidden_cases()
    keys = ("discovery_precision", "discovery_recall", "classification_accuracy",
            "governance_accuracy_modeG", "packet_realization_accuracy_modeP")
    base = None
    for name in ["C0_g3_control", "C1_extract", "C2_scope", "C3_classify", "C4_full"]:
        m = hidden_metrics.evaluate(HybridRelationshipResolverV5(CO.ABLATIONS[name]), hc)["metrics"]
        cur = tuple(m[k] for k in keys)
        base = base or cur
        assert cur == base, name


def test_calibration_gates_pass():
    g = RC._calibration_gates()
    assert all(g.values()), g


def test_synthetic_fixtures_cooccurrence_and_genuine_conflict():
    assert synthetic_fixtures.check() == []
    # co-occurrence across domains does NOT abstain
    fx = synthetic_fixtures.fixtures()["scoped_non_conflict_diff_domain"]
    assert CO.resolve(fx[0], fx[1], fx[1][0], {}, CO.ABLATIONS["C4_full"]).operative_abstention is False
    # genuine same-domain unresolved conflict DOES abstain
    gc = synthetic_fixtures.fixtures()["genuine_unresolved_conflict"]
    op = CO.resolve(gc[0], gc[1], gc[1][0], {}, CO.ABLATIONS["C4_full"])
    assert op.operative_abstention is True
    assert op.operative_abstention_reason == CO.AB_GENUINE_UNRESOLVED


def test_all_five_g3_fixes_retained_under_c4():
    hc = hidden_cases()
    pc4 = hidden_metrics.evaluate(HybridRelationshipResolverV5(CO.ABLATIONS["C4_full"]), hc)["per_case"]
    for cid in G3_FIXES:
        assert pc4[cid]["answer_correct"] is True and pc4[cid]["abstain"] is False, cid


def test_no_over_abstention_vs_g4():
    hc = hidden_cases()
    c4 = hidden_metrics.evaluate(HybridRelationshipResolverV5(CO.ABLATIONS["C4_full"]), hc)["metrics"]
    g4 = hidden_metrics.evaluate(HybridRelationshipResolverV4(GS.ABLATIONS["G4_full"]), hc)["metrics"]
    # precise model keeps coverage high and false-abstention zero, unlike G4
    assert c4["answer_coverage"] > 0.9 and c4["false_abstention_rate"] == 0.0
    assert g4["answer_coverage"] < 0.4 and g4["false_abstention_rate"] >= 0.4


def test_honest_no_clear_signal():
    out = RC.run()
    assert out["byte_identical_reps"] is True
    assert out["calibration_gates_pass"] is True
    assert out["all_g3_fixes_retained"] is True
    assert out["non_inferiority"]["passes"] is True
    assert out["transitions"]["fixes"] == 0 and out["transitions"]["breaks"] == 0
    assert out["conflict_analysis"]["category_counts"].get("GENUINE_UNRESOLVED_CONFLICT", 0) == 0
    assert out["verdict"] == "NO CLEAR SIGNAL"


def test_study_byte_identical():
    a = RC.run()
    b = RC.run()
    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)
