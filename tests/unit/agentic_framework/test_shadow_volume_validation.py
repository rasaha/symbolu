"""
test_shadow_volume_validation.py — smoke checks for the real SHADOW-volume runner.

Verifies the validation runner persists trust_shadow durably, the hash chain stays valid,
legacy still executes (no behaviour change), and the shadow_report verdict/exit code is
correct on a clean corpus. No trust_core flip, no policy change.
"""

from __future__ import annotations

from agentic.agentic_framework.trust.parity import REVIEWED_POLICY
from experiments.trust_signal import shadow_report
from experiments.trust_signal.parity_harness import CORPUS
from experiments.trust_signal.shadow_volume_validation import (
    assemble_corpus,
    main,
    run_validation,
)


def test_assemble_corpus_has_realistic_volume():
    corpus = assemble_corpus()
    assert len(corpus) > len(CORPUS)              # external + signal_gov add real volume
    assert len(corpus) >= 80                      # committed fixtures are present


def test_run_validation_persists_trust_shadow_and_is_clean(tmp_path):
    db = str(tmp_path / "v.db")
    res = run_validation(policy=REVIEWED_POLICY, corpus=list(CORPUS), db_path=db,
                         jsonl_path=str(tmp_path / "v.jsonl"))
    store, rep = res["store"], res["report"]
    try:
        assert store.count() == len(CORPUS)
        recs = store.list_recent(limit=store.count())
        assert all("trust_shadow" in r["request_snapshot"] for r in recs)   # persisted
        assert store.verify_chain().valid                                   # tamper-evident
        assert rep.unsafe_relaxation == 0 and rep.unintended == 0           # clean
        assert rep.intended >= 1                                            # JEPA demotions
        assert shadow_report.verdict(rep)["exit_code"] == 0
    finally:
        store.close()
    assert (tmp_path / "v.jsonl").exists()                                  # JSONL exported


def test_legacy_still_executes_in_shadow(tmp_path):
    # SHADOW must not change runtime behaviour: legacy still decides AND executes.
    db = str(tmp_path / "e.db")
    res = run_validation(policy=REVIEWED_POLICY, corpus=list(CORPUS), db_path=db)
    store = res["store"]
    try:
        outcomes = {r["decision_outcome"]
                    for r in store.list_recent(limit=store.count())}
        assert "allowed" in outcomes              # clean scenarios actually executed
    finally:
        store.close()


def test_main_smoke_exits_zero():
    # authority-only corpus (no external/signal_gov) → fast, deterministic, clean → exit 0
    assert main(["--no-external", "--no-signalgov"]) == 0
