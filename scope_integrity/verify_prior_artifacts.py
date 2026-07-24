"""Verification guard. Fails on drift of ANY prior outcome-bearing artifact this study must not modify:
AGE, AssertionGate robustness, EvidenceAssurance, and the completed ClaimIntegrity study (corpus +
frozen eval outputs). This scope-conjunction study is a small, isolated extension and touches none of
them. Run in CI/tests before any outcome-bearing evaluation.
"""
from __future__ import annotations

import hashlib
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FROZEN = {
    "assertion_governance/data/corpus_v1.json":
        "f16ed3885a5124f18d1f223535b24dc8e416035be7d31008961bf6ef6512ce95",
    "assertion_governance/eval_results/evaluation_v1.json":
        "90dc6b3a235404193f784090b0372169d2eb7c341b0b0169abb2200e8c49325d",
    "assertion_gate_robustness/data/v1/corpus.json":
        "b86c24be5dcb6585ad083cdf710790d4236e0a4a19e2e90baafad791e3350297",
    "assertion_gate_robustness/eval_results/robustness_v1.json":
        "d2d5d0f8a9d4c390048ca16882aa1fb1ddf70a63fdb752447daa15da41b0661e",
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
    "claim_integrity/data/v1/corpus.json":
        "1fe856cc10de9d473ec5b533053b6f39e7ed5441bf59460848b4302f3de2c17a",
    "claim_integrity/eval_results/baselines.json":
        "d4276b3b460c6ca538b9e6895b534fd2851f44b8427930e252a05425fa0f7123",
    "claim_integrity/eval_results/adversarial.json":
        "f22e830d0d1a6f6b1c8a683366278a3508d43b43a2439055b6025ba0520fa5a7",
    "claim_integrity/eval_results/downstream.json":
        "d459c26ab5ef3af3ad1d24ac30be40c02c8e6e554f308c3dde624c4d2259f0a7",
    "claim_integrity/eval_results/ablation.json":
        "7af3acd437ab68d52bf9a736d6ac6f8c16b35931ec369678202aee85d06c923d",
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
