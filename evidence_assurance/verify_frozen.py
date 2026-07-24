"""EvidenceAssurance freeze guard (Phase 21). Freezes the corpus and the four evaluation-result
artifacts for final evaluation. After this freeze, any change to dataset generation, the layers, or
the component that moves these bytes is a DRIFT and must be a deliberate, versioned re-freeze — not a
silent edit. This is the analogue of verify_prior_artifacts.py, for this track's own outputs.

Reproduce before checking:
    python -m evidence_assurance.eval_baselines
    python -m evidence_assurance.eval_assurance
    python -m evidence_assurance.experiments
    python -m evidence_assurance.eval_ablation
    python -c "from evidence_assurance import dataset; dataset.dump_json('evidence_assurance/data/ea_corpus_v1_1.json')"
Then: python -m evidence_assurance.verify_frozen
"""
from __future__ import annotations

import hashlib
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FROZEN = {
    "evidence_assurance/data/ea_corpus_v1_1.json":
        "92fa5e7943fee313b9cd90f746d80e465e1c5540c713ed79b1d81d3d41746dbd",
    "evidence_assurance/eval_results/baselines_v1.json":
        "4cdeee9f04161753ac49a1e796d0d2e2d193d8be686b1ba86da893565ac32a3d",
    "evidence_assurance/eval_results/assurance_v1.json":
        "6035d11f0df9ee40050e42bfbfd2d5620eb1fedd0fbef9ffb20d847d51267e03",
    "evidence_assurance/eval_results/experiments_v1.json":
        "92017ea785fbdd442f97017b5ed36d43054f5a38cdd5d71c2de91ca1a8ff5636",
    "evidence_assurance/eval_results/ablation_v1.json":
        "7fd70408df6333edaa4183d9412cb2f570765d5dc320b21ad9664c608641013f",
}


def _sha(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def verify() -> bool:
    ok = True
    for rel, expect in FROZEN.items():
        p = os.path.join(_ROOT, rel)
        if not os.path.exists(p):
            print(f"MISSING: {rel}"); ok = False; continue
        got = _sha(p)
        print(f"{'OK' if got == expect else 'DRIFT'}: {rel} {got[:16]}")
        if got != expect:
            ok = False
    return ok


if __name__ == "__main__":
    sys.exit(0 if verify() else 1)
