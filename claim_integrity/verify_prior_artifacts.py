"""Verification guard (Phase 1). Fails on drift of ANY prior outcome-bearing artifact that this track
must not modify: AGE, AssertionGate robustness, and EvidenceAssurance (corpus + frozen evaluation
outputs). ClaimIntegrity is upstream research and touches none of these. Run in CI/tests before any
outcome-bearing evaluation.
"""
from __future__ import annotations

import hashlib
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FROZEN = {
    # AGE (assertion governance) — corpus + evaluation
    "assertion_governance/data/corpus_v1.json":
        "f16ed3885a5124f18d1f223535b24dc8e416035be7d31008961bf6ef6512ce95",
    "assertion_governance/eval_results/evaluation_v1.json":
        "90dc6b3a235404193f784090b0372169d2eb7c341b0b0169abb2200e8c49325d",
    # AssertionGate robustness — corpus + evaluation
    "assertion_gate_robustness/data/v1/corpus.json":
        "b86c24be5dcb6585ad083cdf710790d4236e0a4a19e2e90baafad791e3350297",
    "assertion_gate_robustness/eval_results/robustness_v1.json":
        "d2d5d0f8a9d4c390048ca16882aa1fb1ddf70a63fdb752447daa15da41b0661e",
    # EvidenceAssurance — corpus + frozen evaluation outputs
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
