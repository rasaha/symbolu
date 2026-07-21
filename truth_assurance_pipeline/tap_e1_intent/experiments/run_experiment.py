"""
Reproducible entry point for the TAP-E1 experiment.

Runs the full ablation evaluation deterministically and writes:
  * results_v1.json        — the full result manifest (metrics, gates, verdict)
  * experiment_lock.json   — frozen-component + corpus hashes for drift detection

Usage:
    python -m truth_assurance_pipeline.tap_e1_intent.experiments.run_experiment
"""

from __future__ import annotations

import json
import os

from truth_assurance_pipeline.tap_e1_intent import evaluator
from truth_assurance_pipeline.tap_e1_intent.corpus import cases as corpus_cases

_HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    result = evaluator.run_all()
    with open(os.path.join(_HERE, "results_v1.json"), "w") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)

    lock = {
        "schema_version": result["schema_version"],
        "frozen_components_hash": result["frozen_components_hash"],
        "corpus": corpus_cases.corpus_manifest(),
        "gates": result["gates"]["gates"],
        "selected_config": result["selection"]["selected_config"],
        "verdict": result["verdict"],
    }
    with open(os.path.join(_HERE, "experiment_lock.json"), "w") as fh:
        json.dump(lock, fh, indent=2, sort_keys=True)

    print("verdict:", result["verdict"])
    print("selected:", result["selection"]["selected_config"])
    print("frozen_components_hash:", result["frozen_components_hash"])
    print("wrote results_v1.json and experiment_lock.json")


if __name__ == "__main__":
    main()
