#!/usr/bin/env python3
"""Tests for the relationship-benchmark AUDIT.

These lock the audit's falsification findings: which metrics are gameable, the
mirror brittleness, ground-truth cleanliness, and leakage cleanliness.
"""

from __future__ import annotations

import json

from agentic.hybrid_handover.resolution.parse import allows_terminate
from agentic.hybrid_handover.resolution.audit.run_audit import run


def test_neither_is_not_allows_after_bugfix():
    # the objective parsing bug the audit found and fixed
    assert allows_terminate("Either party may terminate for convenience.") is True
    assert allows_terminate("Neither party may terminate for convenience.") is False


def test_audit_finds_gameable_abstention_metrics():
    out = run()
    gm = out["adversarial"]["gameable_metrics"]
    # trivial always-abstain maxes cycle detection & abstention
    for k in ("cycle_detection_accuracy", "abstention_accuracy"):
        assert k in gm and "always_abstain" in gm[k]["cheats"]
    # and it does so while falsely abstaining on every non-abstain case
    assert out["adversarial"]["per_resolver"]["always_abstain"]["false_abstention"] == "11/11"


def test_edge_recall_is_not_gameable():
    out = run()
    # relationship edge recall must NOT be maxable by any cheat
    assert "relationship_edge_recall" not in out["adversarial"]["gameable_metrics"]


def test_mirrors_show_wording_brittleness():
    out = run()
    for r in ("rule", "graph_traversal"):
        ent = out["mirrors"][r]["entity_detected"]
        wrd = out["mirrors"][r]["wording_detected"]
        assert ent == "4/4"      # generalises across entity/order/number
        assert wrd != "4/4"      # brittle to relationship wording


def test_ground_truth_is_structurally_clean():
    out = run()
    assert out["ground_truth"]["structural_issues"] == []


def test_leakage_probe_clean():
    out = run()
    assert out["leakage"]["leak_findings"] == []
    assert out["leakage"]["signature_clean"] is True


def test_robustness_reveals_no_relevance_filter():
    out = run()
    # an irrelevant unconnected node pollutes the governing set
    gov = out["robustness"]["irrelevant_node"]["result"]["governing"]
    assert "D" in gov


def test_audit_is_deterministic():
    assert json.dumps(run(), sort_keys=True, default=str) == json.dumps(run(), sort_keys=True, default=str)
