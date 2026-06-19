"""
test_hallucinated_capability_validation.py — shadow-only corpus integration.

Verifies end-to-end participation (shadow mode through the real gateway, durable persistence +
driver, shadow_report aggregation, `intended` classification, safe invariants) and that
legacy still executes (no behaviour change). Covers all five required corpus cases.
"""

from __future__ import annotations

from experiments.trust_signal import shadow_report
from experiments.trust_signal.hallucinated_capability_validation import (
    CORPUS,
    main,
    run_validation,
)


def test_corpus_covers_required_cases():
    names = {n for n, _, _ in CORPUS}
    assert {"valid_control", "unregistered_capability", "hallucinated_tool_name",
            "unsupported_action_claim", "capability_alias"} <= names


def test_validation_participates_and_is_clean(tmp_path):
    db = str(tmp_path / "cap.db")
    res = run_validation(db_path=db, jsonl_path=str(tmp_path / "cap.jsonl"))
    store, rep = res["store"], res["report"]
    try:
        recs = store.list_recent(limit=store.count())
        assert store.count() == len(CORPUS)
        assert all("trust_shadow" in r["request_snapshot"] for r in recs)
        assert store.verify_chain().valid
        # three violations escalate (hallucinated tool, unsupported cap, impossible claim);
        # valid + alias controls do not.
        assert rep.mismatch_by_driver.get("hallucinated_capability", 0) == 3
        assert rep.intended == 3
        assert rep.unintended == 0 and rep.unsafe_relaxation == 0
        assert rep.matches == 2
        assert shadow_report.verdict(rep)["exit_code"] == 0
        assert "allowed" in {r["decision_outcome"] for r in recs}   # legacy executed
        assert (tmp_path / "cap.jsonl").exists()
    finally:
        store.close()


def test_main_smoke_exits_zero():
    assert main(["--fail-on-unintended"]) == 0
