"""ClaimIntegrity freeze guard (Phase 25). Pins the corpus and the four evaluation-result artifacts for
final evaluation. After this freeze any change that moves these bytes is a DRIFT and must be a
deliberate, versioned re-freeze - not a silent edit.

Reproduce before checking:
    python -c "from claim_integrity import dataset; dataset.dump_json('claim_integrity/data/v1/corpus.json')"
    python -m claim_integrity.eval_baselines
    python -m claim_integrity.eval_adversarial
    python -m claim_integrity.eval_downstream
    python -m claim_integrity.eval_ablation
Then: python -m claim_integrity.verify_frozen
"""
from __future__ import annotations

import hashlib
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FROZEN = {
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
