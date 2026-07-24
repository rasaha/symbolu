"""Verification guard (Phase 1). Fails if any prior AGE outcome-bearing artifact drifts. The
robustness study must NOT modify the completed AGE experiment. Run in CI/tests before evaluation.
"""
from __future__ import annotations

import hashlib
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# frozen hashes of prior AGE outcome-bearing artifacts (recorded at robustness-study start)
FROZEN = {
    "assertion_governance/data/corpus_v1.json":
        "f16ed3885a5124f18d1f223535b24dc8e416035be7d31008961bf6ef6512ce95",
    "assertion_governance/eval_results/evaluation_v1.json":
        "90dc6b3a235404193f784090b0372169d2eb7c341b0b0169abb2200e8c49325d",
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
        status = "OK" if got == expect else "DRIFT"
        if got != expect:
            ok = False
        print(f"{status}: {rel} {got[:16]}")
    return ok


if __name__ == "__main__":
    sys.exit(0 if verify() else 1)
