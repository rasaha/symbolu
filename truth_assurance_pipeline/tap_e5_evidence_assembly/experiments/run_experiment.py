"""
Reproducible entry point for the TAP-E5 experiment. Deterministic and offline.

    python -m truth_assurance_pipeline.tap_e5_evidence_assembly.experiments.run_experiment
"""

from __future__ import annotations

import json
import os

from truth_assurance_pipeline.tap_e5_evidence_assembly import harness
from truth_assurance_pipeline.tap_e5_evidence_assembly.corpus import cases as corpus

_HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    result = harness.run_all()
    with open(os.path.join(_HERE, "results_v5.json"), "w") as fh:
        json.dump(result, fh, indent=2, sort_keys=True, default=str)
    lock = {
        "schema_version": result["schema_version"],
        "frozen_components_hash": result["frozen_components_hash"],
        "corpus": corpus.manifest(), "eval_lock": corpus.eval_lock(),
        "gates": result["gates"]["gates"],
        "selected_config": result["selection"]["selected_config"],
        "verdict": result["verdict"],
    }
    with open(os.path.join(_HERE, "experiment_lock.json"), "w") as fh:
        json.dump(lock, fh, indent=2, sort_keys=True, default=str)
    print("verdict:", result["verdict"])
    print("selected:", result["selection"]["selected_config"])
    print("frozen_components_hash:", result["frozen_components_hash"][:16])
    print("wrote results_v5.json and experiment_lock.json")


if __name__ == "__main__":
    main()
