"""
test_smoke.py — CI smoke test for the signal-governance harness.

Validates (fixed seed, deterministic labels, deterministic mock features):
  - the 10-scenario smoke dataset loads with the pre-registered schema
  - the rule-based oracle reproduces every authored label
  - the metric output conforms to the documented schema
  - the ablation ordering C4 >= C3 >= C2 >= C1 holds on the mock set
  - all required artifacts are written
  - the run is deterministic (same inputs -> identical AUROCs)

This validates the HARNESS plumbing. It does NOT validate the scientific
hypothesis (mock features are synthetic by construction).
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from experiments.signal_gov import dataset as ds
from experiments.signal_gov.configs import CONFIG_ORDER
from experiments.signal_gov.metrics import PER_CONFIG_KEYS
from experiments.signal_gov.oracle import verify_consistency
from experiments.signal_gov.run_experiment import RESULTS_SCHEMA_KEYS, run

SEED = 1234
REQUIRED_ARTIFACTS = (
    "results.json", "metrics.csv", "signal_importance.csv",
    "roc_overlay.png", "catch_at_budget.png", "experiment_report.md",
)


def test_smoke_dataset_schema_and_size():
    scenarios = ds.load_smoke()
    assert len(scenarios) == 10
    cats = set(s.category for s in scenarios)
    assert cats == set(ds.BENCHMARK_CATEGORIES)  # all 3 categories represented
    for s in scenarios:
        d = s.to_dict()
        for field in ds.SCHEMA_FIELDS:
            assert field in d, f"{s.scenario_id} missing schema field {field}"
        assert s.unsafe_label in (0, 1)
        assert s.tool_risk_level in ds.RISK_LEVELS


def test_oracle_reproduces_authored_labels():
    # Both the smoke subset and the full hand-built set must be self-consistent.
    assert verify_consistency(ds.load_smoke()) == []
    assert verify_consistency(ds.load_handbuilt()) == []


def test_smoke_run_artifacts_and_schema(tmp_path):
    res = run("mock", "smoke", tmp_path, seed=SEED, n_boot=200)

    # artifacts exist
    for name in REQUIRED_ARTIFACTS:
        p = tmp_path / name
        assert p.exists() and p.stat().st_size > 0, f"missing/empty artifact {name}"

    results = res.results
    # top-level results schema
    for key in RESULTS_SCHEMA_KEYS:
        assert key in results, f"results.json missing key {key}"

    # per-config metric schema
    assert set(results["configs"].keys()) == set(CONFIG_ORDER)
    for name, m in results["configs"].items():
        for key in PER_CONFIG_KEYS:
            assert key in m, f"{name} metrics missing {key}"
        assert set(m["catch_at_budget"].keys()) == {"0.05", "0.10", "0.20"}

    # results.json on disk parses and matches returned dict on AUROCs
    on_disk = json.loads((tmp_path / "results.json").read_text())
    for name in CONFIG_ORDER:
        assert on_disk["configs"][name]["auroc"] == pytest.approx(
            results["configs"][name]["auroc"], abs=1e-9)


def test_smoke_ablation_ordering(tmp_path):
    res = run("mock", "smoke", tmp_path, seed=SEED, n_boot=200, make_plots=False)
    aurocs = [res.results["configs"][n]["auroc"] for n in CONFIG_ORDER]
    assert not any(np.isnan(a) for a in aurocs)
    # C4 >= C3 >= C2 >= C1 (the harness must compute a correct ablation ordering
    # when the added signals are informative, as they are in mock mode).
    for a, b in zip(aurocs, aurocs[1:]):
        assert b >= a - 1e-9, f"ablation ordering violated: {list(zip(CONFIG_ORDER, aurocs))}"
    assert res.results["ordering_ok"] is True


def test_smoke_determinism(tmp_path):
    r1 = run("mock", "smoke", tmp_path / "a", seed=SEED, n_boot=100, make_plots=False)
    r2 = run("mock", "smoke", tmp_path / "b", seed=SEED, n_boot=100, make_plots=False)
    for name in CONFIG_ORDER:
        assert r1.results["configs"][name]["auroc"] == pytest.approx(
            r2.results["configs"][name]["auroc"], abs=1e-12)
