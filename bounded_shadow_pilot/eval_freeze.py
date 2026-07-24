"""Phase 18 - Evaluation freeze.

Freezes the pilot's evaluation: pins the SHA-256 of every pilot eval artifact so the final pilot run
(Phase 19) scores the FROZEN set exactly once and cannot be silently re-fit. This is the pilot's own
freeze manifest; it is distinct from `verify_prior_artifacts.py` (which guards the PRIOR completed
work). Regenerating any eval artifact and re-freezing is allowed during development; after the eval
freeze, drift is a hard failure.

Deterministic, read-only over the eval_results directory. Writes freeze_manifest.json.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict

_PKG = os.path.dirname(os.path.abspath(__file__))
_EVAL = os.path.join(_PKG, "eval_results")
_DATA = os.path.join(_PKG, "data", "natural_pilot_v1")

# the frozen evaluation surface (relative to the package dir)
FROZEN_EVAL_ARTIFACTS = [
    "data/natural_pilot_v1/corpus.json",
    "data/natural_pilot_v1/ground_truth.json",
    "eval_results/baselines.json",
    "eval_results/failure_taxonomy.json",
    "eval_results/transfer_analysis.json",
    "eval_results/perf_cost_burden.json",
    "eval_results/falsification.json",
]

EVAL_CONFIG = {
    "config": "FULL_STACK_HIGH_RISK",
    "derivation_version": "natural_derivation_v1",
    "evidence_base": "VERIFIED_WITH_LIMITATIONS",
    "labeler_version": "blinded_gt_v1",
    "actiongate_contract_version": "native_actiongate_contract_v1",
    "score_once": True,
    "threshold_tuning_on_final_set": False,
}


def _sha(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def build_manifest() -> Dict[str, Any]:
    hashes = {}
    for rel in FROZEN_EVAL_ARTIFACTS:
        p = os.path.join(_PKG, rel)
        hashes[rel] = _sha(p) if os.path.exists(p) else None
    manifest_hash = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    return {"eval_config": EVAL_CONFIG, "artifact_sha256": hashes,
            "manifest_sha256": manifest_hash, "n_artifacts": len(FROZEN_EVAL_ARTIFACTS)}


def freeze() -> Dict[str, Any]:
    m = build_manifest()
    with open(os.path.join(_EVAL, "freeze_manifest.json"), "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return m


def verify() -> bool:
    """Verify the current eval artifacts match the frozen manifest. Fail on drift or missing artifact."""
    manifest_path = os.path.join(_EVAL, "freeze_manifest.json")
    if not os.path.exists(manifest_path):
        print("MISSING freeze_manifest.json"); return False
    frozen = json.load(open(manifest_path))
    ok = True
    for rel, expect in frozen["artifact_sha256"].items():
        p = os.path.join(_PKG, rel)
        got = _sha(p) if os.path.exists(p) else None
        status = "OK" if got == expect else ("MISSING" if got is None else "DRIFT")
        print(f"{status}: {rel}")
        if got != expect:
            ok = False
    return ok


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        sys.exit(0 if verify() else 1)
    m = freeze()
    print(f"eval freeze: {m['n_artifacts']} artifacts, manifest {m['manifest_sha256'][:16]}")
    for rel, h in m["artifact_sha256"].items():
        print(f"  {h[:16] if h else 'MISSING':16s} {rel}")
