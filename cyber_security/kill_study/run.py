"""CLI entry point: run the full kill study end to end.

    python -m cyber_security.kill_study.run

Steps: simulate -> raw records + manifest -> analyze -> verdict -> plots ->
results record. Deterministic; safe to re-run (overwrites results/).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .analysis import analyze
from .config import StudyConfig
from .experiment import RESULTS_DIR, run as run_experiment
from .plots import render_all
from .results_record import write_results_record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="BCVF-Bio synthetic kill study")
    parser.add_argument("--quick", action="store_true",
                        help="tiny seed count for a smoke run")
    args = parser.parse_args(argv)

    cfg = StudyConfig()
    if args.quick:
        cfg = StudyConfig(dev_seeds_per_cell=2, eval_seeds_per_cell=3)

    manifest = run_experiment(cfg, RESULTS_DIR)
    analysis = analyze(cfg, RESULTS_DIR)
    plots = render_all(cfg, analysis)
    record_path = write_results_record(cfg, manifest, analysis, RESULTS_DIR)

    print(f"records written : {manifest['records_written']}")
    print(f"eval per family : {manifest['eval_events_per_family']}")
    print(f"verdict         : {analysis['verdict']}")
    for r in analysis["verdict_reasons"]:
        print(f"  - {r}")
    print(f"plots           : {[str(p) for p in plots]}")
    print(f"results record  : {record_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
