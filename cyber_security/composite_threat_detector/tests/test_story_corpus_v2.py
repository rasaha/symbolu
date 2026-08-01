"""Expanded adversarial corpus, splits, metrics, and the frozen final run (§12-§16)."""

from __future__ import annotations

import pytest

from evaluation import freeze
from evaluation import story_corpus_v2 as S


def test_corpus_is_large_and_labeled():
    assert len(S.CORPUS) >= 100
    labels = {c.label for c in S.CORPUS}
    assert labels == {"HARMFUL", "BENIGN"}
    fams = {c.family for c in S.CORPUS}
    assert len(fams) >= 30                            # many benign + harmful families


def test_all_cases_match_expected_completion():
    m = S.evaluate_corpus()
    wrong = [pc["case_id"] for pc in m["per_case"]
             if pc["completes"] != pc["expect_would_complete"]]
    assert not wrong, wrong


def test_splits_are_deterministic_and_nonempty():
    a = {c.case_id: S.split_of(c.case_id) for c in S.CORPUS}
    b = {c.case_id: S.split_of(c.case_id) for c in S.CORPUS}
    assert a == b
    for sp in S.SPLITS:
        assert S.cases_for_split(sp), f"split {sp} is empty"


def test_defect_category_eliminated():
    # the ORIGINAL defect: benign partials escalating via THREAT_CONSISTENT.
    m = S.evaluate_corpus()
    assert m["benign_threat_consistent_rate"] == 0.0
    assert m["benign_escalate_rate"] <= S.PREREGISTERED_GATES["max_benign_escalate_rate"]


def test_completion_separation():
    m = S.evaluate_corpus()
    assert m["encoded_completion_detection_rate"] == 1.0
    assert m["benign_false_completion_rate"] == 0.0
    assert m["evasion_false_completion_rate"] == 0.0


def test_integrity_metrics():
    m = S.evaluate_corpus()
    assert m["deterministic_replay_pass_rate"] == 1.0
    assert m["non_mutation_pass_rate"] == 1.0
    assert m["witness_minimality_pass_rate"] == 1.0            # all completions
    assert m["duplicate_equivalence_canonicalization_rate"] == 1.0


def test_not_evaluable_edges_are_measured():
    # partial stories genuinely produce NOT_EVALUABLE edges (never silently satisfied)
    m = S.evaluate_corpus()
    assert m["edge_state_totals"]["NOT_EVALUABLE"] > 0
    assert m["not_evaluable_edge_rate"] > 0.0


def test_metrics_carry_strict_evidence_label_and_notruns():
    m = S.evaluate_corpus()
    assert "NOT fraud-detection accuracy" in m["evidence_label"]
    assert m["not_run"]                                # honest NOT-RUN list


def test_preregistered_gates_pass_on_full_corpus():
    assert S.check_gates()["all_pass"] is True


def test_frozen_final_split_runs_once_and_passes():
    fz = freeze.build_freeze("run2-final", profile="final")
    res = S.run_final_split(fz)
    assert res["metrics"]["split"] == "final"
    assert res["gates"]["all_pass"] is True


def test_final_eval_refuses_on_drift():
    fz = freeze.build_freeze("run2-final", profile="final")
    tampered = dict(fz)
    tampered["matcher_semantics"] = "ctd.storygraph.matcher/9.9.9"
    with pytest.raises(freeze.FreezeViolation):
        S.run_final_split(tampered)


def test_unknown_pattern_stays_undetected():
    # a genuinely novel/unencoded sequence must not escalate or complete.
    m = S.evaluate_corpus()
    unknown = [pc for pc in m["per_case"] if pc["family"] == "unknown_unencoded_sequence"]
    assert unknown
    assert all(not pc["completes"] and pc["signal"] != "ESCALATE" for pc in unknown)
