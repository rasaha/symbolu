#!/usr/bin/env python3
"""Tests for the REPAIRED resolution measurement layer.

Lock the repair: owner-clean metrics, cheat-resistance, Mode G / Mode P
isolation, parser attribution, and always-abstain scoring poorly.
"""

from __future__ import annotations

import json

from agentic.hybrid_handover.evaluation.corpus import all_cases
from agentic.hybrid_handover.resolution.resolvers import ALL_RESOLVERS
from agentic.hybrid_handover.resolution.measurement.owners import (
    METRIC_OWNER, OWNERS, assert_single_owner,
)
from agentic.hybrid_handover.resolution.measurement.run_measurement import run


def test_every_metric_has_exactly_one_owner():
    assert assert_single_owner()
    for metric, owner in METRIC_OWNER.items():
        assert owner in OWNERS
    # dict keys are unique -> one owner per metric by construction
    assert len(METRIC_OWNER) == len(set(METRIC_OWNER))


def test_no_cheat_games_any_capability_metric():
    out = run()
    assert out["adversarial_revalidation"]["gamed_capability_metrics"] == {}


def test_always_abstain_scores_poorly_overall():
    out = run()
    aa = out["adversarial_revalidation"]["per_resolver"]["always_abstain"]
    assert aa["answer_coverage"] == 0.0
    assert aa["selective_accuracy"] == 0.0
    assert (aa["abstention_precision"] or 0) < 0.5   # high recall alone is not enough
    assert out["adversarial_revalidation"]["always_abstain_scores_poorly"] is True


def test_mode_G_isolates_governance():
    out = run()
    r = out["resolvers"]
    # given the gold graph, graph_traversal resolves governance perfectly;
    # weaker resolvers do not -> Mode G measures application alone
    assert r["graph_traversal"]["governance_accuracy_modeG"] == 1.0
    assert r["frozen"]["governance_accuracy_modeG"] < r["graph_traversal"]["governance_accuracy_modeG"]


def test_mode_P_isolates_packet_construction():
    out = run()
    # even with gold governance, packet realization is < 1.0 (the "requires N days"
    # phrasing gap) — proving it measures packet construction, not governance
    assert out["resolvers"]["graph_traversal"]["packet_realization_accuracy_modeP"] < 1.0


def test_discovery_recall_is_not_gameable():
    out = run()
    for name in ("always_abstain", "always_latest", "always_override", "null"):
        assert out["adversarial_revalidation"]["per_resolver"][name]["discovery_recall"] in (0.0, None)


def test_parser_metrics_are_resolver_independent():
    out = run()
    assert METRIC_OWNER["parser_negation_accuracy"] == "SemanticParser"
    assert out["parser"]["parser_negation_accuracy"] == 1.0
    assert out["parser"]["parser_type_accuracy"] == 1.0


def test_hidden_layer_reveals_wording_brittleness():
    out = run()
    rows = out["hidden"]["graph_traversal"]
    wording = [r for r in rows if r["family"] == "wording"]
    detected = sum(r["endpoint_discovered"] for r in wording)
    assert detected < len(wording)   # brittle to relationship wording


def test_measurement_is_deterministic():
    assert json.dumps(run(), sort_keys=True, default=str) == json.dumps(run(), sort_keys=True, default=str)
