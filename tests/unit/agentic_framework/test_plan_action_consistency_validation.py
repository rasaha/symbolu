"""
test_plan_action_consistency_validation.py — shadow-only corpus integration.
"""

from __future__ import annotations

from experiments.trust_signal import shadow_report
from experiments.trust_signal.plan_action_consistency_validation import (
    CORPUS,
    main,
    run_validation,
)


def test_corpus_covers_each_mismatch_kind():
    names = {n for n, _, _ in CORPUS}
    assert {"consistent_control", "read_plan_mutating", "confirm_plan_executes",
            "no_external_external_action", "resource_mismatch"} <= names


def test_validation_participates_and_is_clean(tmp_path):
    db = str(tmp_path / "pa.db")
    res = run_validation(db_path=db, jsonl_path=str(tmp_path / "pa.jsonl"))
    store, rep = res["store"], res["report"]
    try:
        recs = store.list_recent(limit=store.count())
        assert store.count() == len(CORPUS)
        assert all("trust_shadow" in r["request_snapshot"] for r in recs)
        assert store.verify_chain().valid
        assert rep.mismatch_by_driver.get("plan_action_consistency", 0) == 4
        assert rep.intended == 4
        assert rep.unintended == 0 and rep.unsafe_relaxation == 0
        assert rep.matches == 1
        assert shadow_report.verdict(rep)["exit_code"] == 0
        assert "allowed" in {r["decision_outcome"] for r in recs}   # legacy executed
    finally:
        store.close()


def test_main_smoke_exits_zero():
    assert main(["--fail-on-unintended"]) == 0
