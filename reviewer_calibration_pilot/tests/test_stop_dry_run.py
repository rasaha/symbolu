"""Phases 12-13 tests: stop conditions (immediate fail-closed, cumulative on frozen thresholds), dry-run
plumbing clean, mock never treated as human evidence."""
from reviewer_calibration_pilot import stop_conditions as sc, dry_run


def test_immediate_stop_fires():
    fired = sc.check_immediate({"native_actiongate_semantic_loss": True})
    assert "native_actiongate_semantic_loss" in fired


def test_clean_signals_no_immediate_stop():
    assert sc.check_immediate({c: False for c in sc._IMMEDIATE}) == []


def test_cumulative_no_fire_on_not_enough_human_evidence():
    assert sc.check_cumulative({"status": "NOT_ENOUGH_HUMAN_EVIDENCE"}) == []


def test_cumulative_fires_on_breach():
    m = {"status": "COMPUTED", "human_records": 100, "unsafe_allow_disagreement": 10,
         "explanation_usefulness_mean": 4.0}
    fired = sc.check_cumulative(m)
    assert "unsafe_allow_disagreement_above_threshold" in fired


def test_dry_run_clean_and_mock_not_validation():
    m = dry_run.run()
    assert m["all_plumbing_ok"] is True
    assert m["all_non_enforcing"] is True
    assert m["stop_machinery_ok"] is True
    assert m["metrics_status_on_mock"] == "NOT_ENOUGH_HUMAN_EVIDENCE"
