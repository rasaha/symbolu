"""Verification guard (Phase 1). Fails on drift of any prior outcome-bearing artifact from the
completed AGE experiment and AssertionGate robustness study. This track is upstream research and
must NOT modify those. Run in CI/tests before evaluation.
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
