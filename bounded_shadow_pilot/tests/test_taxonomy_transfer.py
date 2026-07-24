"""Phase 13-14 tests: failure taxonomy is exhaustive/deterministic and the transfer analysis reads the
frozen structured evaluation read-only and reaches the expected mixed verdict.
"""
from bounded_shadow_pilot import failure_taxonomy as ft
from bounded_shadow_pilot import transfer_analysis as ta


def test_taxonomy_partitions_all_artifacts():
    m = ft.build()
    assert sum(m["category_counts"].values()) == m["n"]
    assert m["category_counts"]["UNSAFE_PERMIT"] == 0          # no fully-supported unsafe permit
    assert m["interpretation"]["dominant_failure"] == "OVER_QUALIFICATION"


def test_taxonomy_cause_dominated_by_missing_evidence():
    m = ft.build()
    top_cause = next(iter(m["nl_cause_counts"]))
    assert top_cause == "NO_EXTERNAL_EVIDENCE"


def test_transfer_verdicts_mixed():
    m = ta.analyze()
    v = m["transfer_verdicts"]
    assert v["safety"] == "TRANSFERS"
    assert v["utility"] == "DOES_NOT_TRANSFER"
    assert v["actiongate_native_semantics"] == "PRESERVED"
    # structured reference was read (frozen), not recomputed
    assert m["structured_reference"]["corpus"] == "gip_corpus_v1"
    assert m["structured_reference"]["clean_low_risk_unnecessary_qualification"] == 0.0
