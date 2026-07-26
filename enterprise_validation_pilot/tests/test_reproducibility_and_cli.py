"""Reproducibility (Task 115) and the deterministic run CLI (Task 116)."""
from __future__ import annotations

import json
import pathlib

from enterprise_validation_pilot import run as run_module
from enterprise_validation_pilot.datasets.build_dataset import build
from enterprise_validation_pilot.pilot import run_pilot


def test_substantive_digest_is_stable_across_runs():
    ds = build()
    assert run_pilot(ds).substantive_digest == run_pilot(ds).substantive_digest


def test_full_trace_is_reproducible():
    from enterprise_validation_pilot.runners.workflow import run_scenario
    s = build().by_id("finance_operations-002")
    t1, t2 = run_scenario(s).trace, run_scenario(s).trace
    # kernel-opaque authorization_id is a permitted volatile field; all else stable
    volatile = {"authorization_id"}
    assert {k: v for k, v in t1.items() if k not in volatile} == \
           {k: v for k, v in t2.items() if k not in volatile}


def test_run_cli_writes_all_reports_and_exits_zero(tmp_path):
    out = tmp_path / "results"
    code = run_module.main(["--output", str(out)])
    assert code == 0
    for name in ("PHASE_5I_METRICS.json", "PHASE_5I_SCENARIO_RESULTS.json",
                 "PHASE_5I_INVARIANTS.json", "PHASE_5I_FAILURE_INJECTION.json",
                 "PHASE_5I_TRACE_COMPLETENESS.json", "PHASE_5I_ENTERPRISE_VALIDATION.md"):
        assert (out / name).exists(), name
    metrics = json.loads((out / "PHASE_5I_METRICS.json").read_text())
    assert set(metrics["metrics_by_layer"]) == {"tap", "actiongate", "workflow"}


def test_metrics_are_reported_per_layer_not_aggregated(tmp_path):
    out = tmp_path / "results"
    run_module.main(["--output", str(out)])
    metrics = json.loads((out / "PHASE_5I_METRICS.json").read_text())
    assert "governance_score" not in json.dumps(metrics)  # no single aggregate score
