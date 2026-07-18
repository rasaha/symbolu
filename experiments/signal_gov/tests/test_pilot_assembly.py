"""
test_pilot_assembly.py — balanced 30-50 pilot assembly (CPU only, no GPU/checkpoint).

Validates the assembler, the enterprise pool, the committed pilot_30_50.jsonl, and that the
assembled pilot plugs into the harness. NO model is run; NO success claim.
"""

from __future__ import annotations

import json
from collections import Counter

import pytest

from experiments.signal_gov import pilot
from experiments.signal_gov.dataset import (
    BENCHMARK_CATEGORIES,
    load_dataset,
    load_scenarios_jsonl,
)
from experiments.signal_gov.oracle import verify_consistency


def test_enterprise_pool_oracle_consistent():
    pool = pilot.load_pool()
    assert len(pool) == 20  # 10 destructive + 10 ambiguous
    assert verify_consistency(pool) == []
    cats = Counter(s.category for s in pool)
    assert cats["destructive_enterprise"] == 10
    assert cats["ambiguous_hallucinated"] == 10


def test_assemble_pilot_balanced_30():
    sc = pilot.assemble_pilot(per_category=10)
    assert len(sc) == 30
    cats = Counter(s.category for s in sc)
    for c in BENCHMARK_CATEGORIES:
        assert cats[c] == 10
    assert verify_consistency(sc) == []
    ids = [s.scenario_id for s in sc]
    assert len(ids) == len(set(ids))
    # label mix: every category has both safe and unsafe
    for c in BENCHMARK_CATEGORIES:
        labels = {s.unsafe_label for s in sc if s.category == c}
        assert labels == {0, 1}, f"{c} not label-mixed"


def test_assemble_pilot_45():
    sc = pilot.assemble_pilot(per_category=15)
    assert len(sc) == 45
    assert all(v == 15 for v in Counter(s.category for s in sc).values())
    assert verify_consistency(sc) == []


def test_assemble_raises_when_too_few():
    # 16/category exceeds the available destructive/ambiguous candidates (15 each).
    with pytest.raises(ValueError, match="per_category"):
        pilot.assemble_pilot(per_category=16)


def test_committed_pilot_matches_assembler():
    # Guard against drift: the committed jsonl must equal a fresh per_category=10 assembly.
    committed = load_dataset("pilot_30_50")
    fresh = pilot.assemble_pilot(per_category=10)
    assert [s.scenario_id for s in committed] == [s.scenario_id for s in fresh]
    assert [s.unsafe_label for s in committed] == [s.unsafe_label for s in fresh]


def test_committed_pilot_is_balanced_and_consistent():
    sc = load_dataset("pilot_30_50")
    assert len(sc) == 30
    assert all(v == 10 for v in Counter(s.category for s in sc).values())
    assert sum(s.unsafe_label for s in sc) == 15
    assert verify_consistency(sc) == []


def test_load_scenarios_jsonl_roundtrip(tmp_path):
    sc = pilot.assemble_pilot(per_category=10)
    p = tmp_path / "p.jsonl"
    p.write_text("\n".join(json.dumps(s.to_dict()) for s in sc), encoding="utf-8")
    back = load_scenarios_jsonl(str(p))
    assert [s.to_dict() for s in back] == [s.to_dict() for s in sc]


def test_missing_scenarios_file_raises():
    with pytest.raises(FileNotFoundError):
        load_scenarios_jsonl("/no/such/pilot.jsonl")


def test_assembled_pilot_runs_in_harness_with_power_disclaimer(tmp_path):
    # mock features (NOT a result) — just verify the pilot plugs in and the small-N
    # power disclaimer is emitted automatically.
    from experiments.signal_gov.run_experiment import run
    res = run("mock", "pilot_30_50",
              tmp_path,
              scenarios_path="experiments/signal_gov/data/pilot_30_50.jsonl",
              n_boot=100, make_plots=False)
    assert res.results["dataset"]["n_total"] == 30
    report = (tmp_path / "experiment_report.md").read_text()
    assert "Power & significance" in report
    assert "UNDERPOWERED" in report
