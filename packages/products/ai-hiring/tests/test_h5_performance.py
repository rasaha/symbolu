"""H5 — performance characterization (local, descriptive only)."""
from __future__ import annotations

from ugence_ai_hiring.validation.performance import batch_audit_growth, time_case


def test_time_case_returns_descriptive_stats():
    stats = time_case(repeats=3)
    assert stats["repeats"] == 3 and stats["median_s"] >= 0
    assert "NOT a production-scale claim" in stats["note"]


def test_batch_audit_growth_is_bounded():
    g = batch_audit_growth(n=6)
    assert g["cases"] == 6 and g["hiring_audit_events"] > 0 and g["kernel_audit_events"] > 0
