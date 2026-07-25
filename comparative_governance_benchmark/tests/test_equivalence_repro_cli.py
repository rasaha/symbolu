"""Strategy-D/Phase-5I equivalence, reproducibility, and CLI (Tasks 5/17/18)."""
from __future__ import annotations

import json
import pathlib

from comparative_governance_benchmark import run as run_module
from comparative_governance_benchmark.benchmark import run_benchmark
from comparative_governance_benchmark.schemas.dataset import load_frozen_dataset
from comparative_governance_benchmark.strategies import build_strategy
from enterprise_validation_pilot.runners.workflow import run_scenario as pilot_run


def test_strategy_d_reproduces_phase5i():
    ds = load_frozen_dataset()
    full = build_strategy("full_governance")
    for s in ds.ordered():
        r = full.run(s)
        run = pilot_run(s)
        assert r.dispatched == run.dispatched, s.scenario_id
        assert r.assertion_outcome == run.tap_outcome, s.scenario_id
        if run.proceeded_to_action:
            assert r.authorization_outcome == run.actiongate_outcome, s.scenario_id


def test_substantive_digest_reproducible():
    assert run_benchmark().substantive_digest == run_benchmark().substantive_digest


def test_report_formatting_does_not_change_metrics():
    # regenerating reports must not alter the substantive digest/metrics
    from comparative_governance_benchmark.reporting.generate import comparative_report_md
    res = run_benchmark()
    d1 = res.substantive_digest
    _ = comparative_report_md(res)     # produce a report
    assert res.substantive_digest == d1


def test_cli_writes_seven_reports_and_exits_zero(tmp_path):
    out = tmp_path / "phase6a"
    code = run_module.main(["--output", str(out)])
    assert code == 0
    for name in ("PHASE_6A_COMPARATIVE_BENCHMARK.md", "PHASE_6A_STRATEGY_METRICS.json",
                 "PHASE_6A_SCENARIO_COMPARISON.json", "PHASE_6A_FAILURE_COMPARISON.json",
                 "PHASE_6A_GOVERNANCE_COST.json", "PHASE_6A_INVARIANTS.json",
                 "PHASE_6A_PAIRED_ANALYSIS.json"):
        assert (out / name).exists(), name


def test_cli_rejects_unknown_dataset(tmp_path):
    assert run_module.main(["--dataset", "other", "--output", str(tmp_path)]) == 2


def test_cli_domain_filter(tmp_path):
    out = tmp_path / "proc"
    code = run_module.main(["--domains", "procurement", "--output", str(out)])
    assert code == 0
    data = json.loads((out / "PHASE_6A_SCENARIO_COMPARISON.json").read_text())
    assert {r["domain"] for r in data["scenarios"]} == {"procurement"}
