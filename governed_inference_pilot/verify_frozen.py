"""GovernedInferencePilot freeze guard (Phase 26). Pins the corpus and the three evaluation-result
artifacts. Reproduce (deterministic) then check:
    python -c "from governed_inference_pilot import dataset; dataset.dump_json('governed_inference_pilot/data/v1/corpus.json')"
    python -m governed_inference_pilot.evaluate
    python -m governed_inference_pilot.cascade_analysis
    python -m governed_inference_pilot.mvc_study
    python -m governed_inference_pilot.verify_frozen
"""
from __future__ import annotations

import hashlib
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FROZEN = {
    "governed_inference_pilot/data/v1/corpus.json":
        "8f04960c9e876c925eb89ad2be214defd57af887723967fa4fe238951e8fc354",
    "governed_inference_pilot/eval_results/evaluation.json":
        "3cc5dd8f946f07c075c17b95bc99159bac4670bd3ebc62e4f24e17f6ab244a10",
    "governed_inference_pilot/eval_results/cascade_latency_cost.json":
        "5350d0280c118563ade53c535e6ac86d471f2e079920821a755f476e573064e1",
    "governed_inference_pilot/eval_results/mvc.json":
        "1fbe5ddfd9ad7ade093398d68930140d690ffddb3f766ce8bbccae09580c442a",
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
