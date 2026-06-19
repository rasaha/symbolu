"""
test_permission_overclaim_validation.py — shadow-only corpus integration for the observable.

Verifies the observable participates end-to-end: shadow mode through the real gateway,
durable audit persistence (trust_shadow + driver), shadow_report aggregation, the `intended`
advisory classification, and the safety invariants (0 unsafe_relaxation / 0 unintended). Also
confirms legacy still executes (no behaviour change).
"""

from __future__ import annotations

from experiments.trust_signal import shadow_report
from experiments.trust_signal.permission_overclaim_validation import (
    CORPUS,
    main,
    run_validation,
)


def test_corpus_covers_all_six_overclaim_kinds():
    names = {n for n, _, _ in CORPUS}
    assert {"capability_escalation", "authority_escalation", "scope_escalation",
            "cross_tenant", "policy_bypass"} <= names
    assert "within_grant_clean" in names and "no_context_inert" in names


def test_validation_participates_and_is_clean(tmp_path):
    db = str(tmp_path / "po.db")
    res = run_validation(db_path=db, jsonl_path=str(tmp_path / "po.jsonl"))
    store, rep = res["store"], res["report"]
    try:
        # persisted: every event carries trust_shadow; chain valid
        recs = store.list_recent(limit=store.count())
        assert store.count() == len(CORPUS)
        assert all("trust_shadow" in r["request_snapshot"] for r in recs)
        assert store.verify_chain().valid
        # shadow_report aggregates the driver; all escalations are intended; safe
        assert rep.mismatch_by_driver.get("permission_overclaim", 0) == 6
        assert rep.intended == 6
        assert rep.unintended == 0 and rep.unsafe_relaxation == 0
        assert shadow_report.verdict(rep)["exit_code"] == 0
        # legacy still executed (no behaviour change): clean tools ran
        outcomes = {r["decision_outcome"] for r in recs}
        assert "allowed" in outcomes
        assert (tmp_path / "po.jsonl").exists()
    finally:
        store.close()


def test_main_smoke_exits_zero():
    assert main(["--fail-on-unintended"]) == 0
