"""ScopeIntegrity freeze guard (M6). Pins the corpus and the two evaluation-result artifacts.

Reproduce before checking:
    python -c "from scope_integrity import dataset; dataset.dump_json('scope_integrity/data/v1/corpus.json')"
    python -m scope_integrity.eval_downstream
    python -m scope_integrity.eval_ablation
Then: python -m scope_integrity.verify_frozen
"""
from __future__ import annotations

import hashlib
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FROZEN = {
    "scope_integrity/data/v1/corpus.json":
        "13207b376bce748565f90646488bd9fe9a91625965b8ab5d458ec9f00399bc3c",
    "scope_integrity/eval_results/downstream.json":
        "4da5851bd1b947e3d89a4c5be41c1c2f3ca9bade10c5f1bed8adcb7aaa4d7213",
    "scope_integrity/eval_results/ablation.json":
        "c27515763612aedf66161c15b5c3c9570546040e081c2e02ab40f0d867277658",
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
