"""
Reproducible entry point for the TAP-E1.1 experiment.

Runs the full baseline comparison (deterministic vs real-model), the leakage audit,
and the metric audit, and writes ``results_v11.json``. Deterministic and offline
(replays the cached agent-model outputs).

Usage:
    python -m truth_assurance_pipeline.tap_e1_1_realmodel.experiments.run_experiment_v11
"""

from __future__ import annotations

import json
import os

from truth_assurance_pipeline.tap_e1_1_realmodel import harness, leakage_audit, metric_audit

_HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    result = harness.run_all()
    result["leakage_audit"] = leakage_audit.run()
    result["metric_audit"] = metric_audit.run()

    with open(os.path.join(_HERE, "results_v11.json"), "w") as fh:
        json.dump(result, fh, indent=2, sort_keys=True, default=str)

    print("verdict:", result["verdict"])
    print("selected baseline:", result["selection"]["selected_baseline"])
    print("leakage audit pass:", result["leakage_audit"]["all_pass"])
    print("metric audit pass:", result["metric_audit"]["all_pass"])
    print("wrote results_v11.json")


if __name__ == "__main__":
    main()
