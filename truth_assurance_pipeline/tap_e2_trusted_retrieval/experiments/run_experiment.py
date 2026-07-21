"""
Reproducible entry point for the TAP-E2 experiment.

Runs all six baselines through the frozen TAP-E1 -> TAP-E2 pipeline, applies the
preregistered gates to the DEV-selected configuration on the locked eval split, and
writes results_v2.json + experiment_lock.json. Metrics are deterministic; only the
reported mean latency is timing-dependent.

    python -m truth_assurance_pipeline.tap_e2_trusted_retrieval.experiments.run_experiment
"""

from __future__ import annotations

import json
import os

from truth_assurance_pipeline.tap_e2_trusted_retrieval import harness
from truth_assurance_pipeline.tap_e2_trusted_retrieval.corpus import corpus_manifest, queries

_HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    result = harness.run_all()
    with open(os.path.join(_HERE, "results_v2.json"), "w") as fh:
        json.dump(result, fh, indent=2, sort_keys=True, default=str)

    lock = {
        "schema_version": result["schema_version"],
        "frozen_components_hash": result["frozen_components_hash"],
        "corpus": corpus_manifest(),
        "eval_lock": queries.eval_lock(),
        "gates": result["gates"]["gates"],
        "selected_config": result["selection"]["selected_config"],
        "verdict": result["verdict"],
    }
    with open(os.path.join(_HERE, "experiment_lock.json"), "w") as fh:
        json.dump(lock, fh, indent=2, sort_keys=True, default=str)

    print("verdict:", result["verdict"])
    print("selected:", result["selection"]["selected_config"])
    print("frozen_components_hash:", result["frozen_components_hash"][:16])
    print("wrote results_v2.json and experiment_lock.json")


if __name__ == "__main__":
    main()
