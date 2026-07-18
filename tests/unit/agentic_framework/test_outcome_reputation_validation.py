"""
test_outcome_reputation_validation.py — shadow-only corpus integration for the observable.

Verifies the observable participates end-to-end (shadow mode through the real gateway reading
its own audit-chain history, durable persistence + driver, shadow_report aggregation, the
`intended` advisory classification, and 0 unsafe_relaxation / 0 unintended), and that legacy
still executes (no behaviour change).
"""

from __future__ import annotations

from experiments.trust_signal import shadow_report
from experiments.trust_signal.outcome_reputation_validation import (
    CORPUS,
    main,
    run_validation,
)


def test_corpus_covers_good_poor_egregious_and_new():
    names = {n for n, _, _ in CORPUS}
    assert {"reputation_reliable", "reputation_denied", "reputation_violations",
            "reputation_new_tool"} <= names


def test_validation_participates_and_is_clean(tmp_path):
    db = str(tmp_path / "rep.db")
    res = run_validation(db_path=db, jsonl_path=str(tmp_path / "rep.jsonl"))
    store, rep = res["store"], res["report"]
    try:
        recs = store.list_recent(limit=store.count())
        assert store.count() == len(CORPUS)
        assert all("trust_shadow" in r["request_snapshot"] for r in recs)
        assert store.verify_chain().valid
        # only the poor + egregious histories escalate; both are intended advisory
        assert rep.mismatch_by_driver.get("outcome_reputation", 0) == 2
        assert rep.intended == 2
        assert rep.unintended == 0 and rep.unsafe_relaxation == 0
        assert shadow_report.verdict(rep)["exit_code"] == 0
        # good + new tools did NOT escalate (asymmetry / inertness)
        assert rep.matches == 2
        # legacy still executed (read-only clean tools ran)
        assert "allowed" in {r["decision_outcome"] for r in recs}
        assert (tmp_path / "rep.jsonl").exists()
    finally:
        store.close()


def test_main_smoke_exits_zero():
    assert main(["--fail-on-unintended"]) == 0
