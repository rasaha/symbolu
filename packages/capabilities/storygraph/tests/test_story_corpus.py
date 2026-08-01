"""Adversarial story-corpus metrics harness (§11, §12, §16).

Asserts the deterministic matcher separates the true harmful completion from hard
benign look-alikes and evasive variants on a hand-built, labeled corpus. Evidence
label is strict: this is encoded-pattern structural separation, not fraud accuracy.
"""

from __future__ import annotations

from ugence_storygraph.evaluation import story_corpus as S


def test_corpus_is_labeled_and_balanced():
    assert len(S.CASES) >= 8
    labels = {c.label for c in S.CASES}
    assert labels == {"HARMFUL", "BENIGN"}


def test_every_case_matches_expected_completion_outcome():
    m = S.evaluate_corpus()
    assert m["all_cases_correct"] is True, m["incorrect_cases"]


def test_true_assembly_completes_evasions_do_not():
    m = S.evaluate_corpus()
    assert m["true_completion_detection_rate"] == 1.0
    assert m["evasion_false_completion_rate"] == 0.0


def test_no_benign_lookalike_reaches_would_complete():
    m = S.evaluate_corpus()
    assert m["benign_false_completion_rate"] == 0.0


def test_metrics_carry_strict_evidence_label():
    m = S.evaluate_corpus()
    assert "NOT fraud-detection accuracy" in m["evidence_label"]


def test_benign_escalation_limitation_is_reported_not_hidden():
    # the harness must SURFACE benign look-alikes that reach an ESCALATE advisory
    # (a known limitation) rather than silently omitting them.
    m = S.evaluate_corpus()
    assert "benign_escalate_advisory_rate" in m
    assert isinstance(m["benign_escalate_advisory_cases"], list)


def test_corpus_result_is_deterministic():
    a = S.evaluate_corpus()["per_case"]
    b = S.evaluate_corpus()["per_case"]
    assert a == b
