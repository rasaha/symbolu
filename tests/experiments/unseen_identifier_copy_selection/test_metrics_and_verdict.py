"""Tests for pure metrics and the frozen verdict-precedence engine (every boundary)."""
from __future__ import annotations

from dataclasses import replace

from experiments.unseen_identifier_copy_selection.config import FIXTURE_SEEDS
from experiments.unseen_identifier_copy_selection.metrics import (
    exact_accuracy,
    false_answer_rate,
    split_metrics,
)
from experiments.unseen_identifier_copy_selection.parser import parse
from experiments.unseen_identifier_copy_selection.tasks import generate_split
from experiments.unseen_identifier_copy_selection.verdict import VerdictInputs, evaluate

FS = FIXTURE_SEEDS[0]


def _passing() -> VerdictInputs:
    seeds = (True,) * 5
    return VerdictInputs(
        c1_exact=0.90, c1_token=0.97, c1_fabricated=0.0,
        c2_exact=0.85, c2_position_min=0.80, c2_wrong_in_context=0.05, c2_fabricated=0.0,
        c3_exact=0.85, c3_fabricated=0.0,
        c4_position_min=0.80, c4_spread=0.05, c5_degradation=0.0,
        c6_exact=0.95, c7_exact=0.85, c8_abstention=0.95, c8_false_answer=0.0, c8_fabricated=0.0,
        c1_seed_pass=seeds, c2_seed_pass=seeds, c3_seed_pass=seeds, c7_seed_pass=seeds,
    )


def test_confirmed_when_all_pass():
    assert evaluate(_passing()).label == "UNSEEN_IDENTIFIER_COPY_SELECTION_CONFIRMED"


def test_protocol_violation_outranks_everything():
    assert evaluate(replace(_passing(), protocol_ok=False)).label == "UNSEEN_IDENTIFIER_PROTOCOL_VIOLATED"
    assert evaluate(replace(_passing(), shortcut_ok=False)).label == "UNSEEN_IDENTIFIER_PROTOCOL_VIOLATED"
    assert evaluate(replace(_passing(), determinism_ok=False)).label == "UNSEEN_IDENTIFIER_PROTOCOL_VIOLATED"


def test_resource_block():
    assert evaluate(replace(_passing(), resource_ok=False)).label == "UNSEEN_IDENTIFIER_RESOURCE_BLOCKED"


def test_generalization_failed_c6_pass_c7_fail():
    v = replace(_passing(), c7_exact=0.50, c7_seed_pass=(False,) * 5)
    assert evaluate(v).label == "UNSEEN_IDENTIFIER_GENERALIZATION_FAILED"


def test_copy_capability_not_found_c6_c7_fail_c1_low():
    v = replace(_passing(), c6_exact=0.50, c7_exact=0.50, c1_exact=0.50,
                c1_seed_pass=(False,) * 5, c7_seed_pass=(False,) * 5)
    assert evaluate(v).label == "UNSEEN_IDENTIFIER_COPY_CAPABILITY_NOT_FOUND"


def test_selection_failed_c1_pass_c2_fail():
    v = replace(_passing(), c2_exact=0.50, c2_seed_pass=(False,) * 5)
    assert evaluate(v).label == "UNSEEN_IDENTIFIER_SELECTION_FAILED"


def test_evidence_lookup_failed():
    v = replace(_passing(), c3_exact=0.50, c3_seed_pass=(False,) * 5)
    assert evaluate(v).label == "UNSEEN_IDENTIFIER_EVIDENCE_LOOKUP_FAILED"


def test_abstention_gate_failed():
    v = replace(_passing(), c8_abstention=0.50)
    assert evaluate(v).label == "UNSEEN_IDENTIFIER_ABSTENTION_GATE_FAILED"


def test_cooccurring_c1_and_c8_failure_resolves_to_copy_base():
    # C1 fails AND C8 fails -> copy base wins (COPY_CAPABILITY_NOT_FOUND), not abstention.
    v = replace(_passing(), c1_exact=0.50, c6_exact=0.50, c7_exact=0.50, c8_abstention=0.10,
                c1_seed_pass=(False,) * 5, c7_seed_pass=(False,) * 5)
    assert evaluate(v).label == "UNSEEN_IDENTIFIER_COPY_CAPABILITY_NOT_FOUND"


def test_boundary_exactly_at_threshold_passes():
    # C1 exactly at 0.85 mean and token exactly 0.95 -> still passes its gate
    v = replace(_passing(), c1_exact=0.85, c1_token=0.95)
    assert evaluate(v).label == "UNSEEN_IDENTIFIER_COPY_SELECTION_CONFIRMED"


def test_boundary_one_below_threshold_fails_selection_gate():
    v = replace(_passing(), c2_exact=0.7999, c2_seed_pass=(True, True, True, False, False))
    assert evaluate(v).label == "UNSEEN_IDENTIFIER_SELECTION_FAILED"


def test_copy_masks_selection_low_c1_no_selection_verdict():
    # C1 below gate but C6 seen-competent -> generalization, never a selection verdict.
    v = replace(_passing(), c1_exact=0.50, c1_seed_pass=(False,) * 5, c2_exact=0.50)
    label = evaluate(v).label
    assert label == "UNSEEN_IDENTIFIER_GENERALIZATION_FAILED"
    assert "SELECTION" not in label


def test_metrics_on_gold_predictions_are_perfect():
    exs = generate_split("C2", "unseen", FS, n=12)
    pairs = [(e, parse(e.expected_output, e)) for e in exs]
    assert exact_accuracy(pairs) == 1.0
    m = split_metrics("C2", pairs)
    assert m.exact == 1.0 and m.malformed == 0.0 and m.fabricated == 0.0


def test_false_answer_rate_on_c8():
    exs = generate_split("C8", "unseen", FS, n=10)
    # model wrongly answers an in-context identifier instead of abstaining
    pairs = [(e, parse(e.pairs[0][1], e)) for e in exs]
    assert false_answer_rate(pairs) == 1.0
