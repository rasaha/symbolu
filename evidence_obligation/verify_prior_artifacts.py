"""Verification guard for the Contextual Evidence Obligation and Utility Calibration Study.

Fails on drift of ANY prior outcome-bearing artifact this calibration track must NOT modify. This track
consumes every completed component READ-ONLY: EvidenceAssurance, AssertionGate, ActionGate,
ClaimIntegrity, ScopeIntegrity, ExecutionGate, ModelPolicy, governed_inference_pilot,
customer_shadow_readiness, and bounded_shadow_pilot.

Guarded set = the 22 artifacts pinned by the bounded_shadow_pilot guard (17 research-track + 4 GIP
frozen + 1 CSR study) PLUS the 10 outcome-bearing artifacts produced by the completed
bounded_shadow_pilot natural-artifact track. 32 total. Run in CI/tests before any outcome-bearing work.
"""
from __future__ import annotations

import hashlib
import os
import sys

# Reuse the prior track's frozen set verbatim (imported read-only) so the 22 hashes are never
# transcribed by hand and can never silently diverge from the prior guard.
from bounded_shadow_pilot.verify_prior_artifacts import FROZEN as _PRIOR_FROZEN

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# outcome-bearing artifacts produced by the completed bounded_shadow_pilot track
_BOUNDED_SHADOW_PILOT = {
    "bounded_shadow_pilot/data/natural_pilot_v1/corpus.json":
        "dfa196d5d32ab562e69110415912f53312cb1e519d958760b2aaae8d2afc03aa",
    "bounded_shadow_pilot/data/natural_pilot_v1/ground_truth.json":
        "2348962892160c97b10cc0ea3ad6b3e88abe9b00b867bb2722ba3dfdb9df309b",
    "bounded_shadow_pilot/eval_results/baselines.json":
        "8539f6cb16866dcd00c635649d4593de333ffaefab2e86d80ed51ae6af3d48ff",
    "bounded_shadow_pilot/eval_results/failure_taxonomy.json":
        "42e42a075d0508f8bc6f2ed9e1d6ea309b4faa4d8e20bc86fe359dd7eeadddd9",
    "bounded_shadow_pilot/eval_results/transfer_analysis.json":
        "98b59f4ace7a15cc5e67fe6051d1c46021c48770331cbca550b6a0d1ae5c705b",
    "bounded_shadow_pilot/eval_results/perf_cost_burden.json":
        "f0751356bcd5d074173cfcdbff0f53b4e8f66390888ae826bf89f3d5b394b718",
    "bounded_shadow_pilot/eval_results/falsification.json":
        "1b95c6a0d73dbc6e7d39b65616aa4c4c9119e61d5689faa37a0373f8c90ad3d6",
    "bounded_shadow_pilot/eval_results/pilot_execution.json":
        "a9110b43b102477a7479cb39b5e6d2091cc92658480dbaaafa28f165de1e8987",
    "bounded_shadow_pilot/eval_results/architectural_decision.json":
        "6f80f89462f241d576a6ecca21dab87c46b7372c73c174908e475b4d68217e31",
    "bounded_shadow_pilot/eval_results/freeze_manifest.json":
        "462ecdad65bdb12ca7cbec95d5947aa090eddacabb21e19a6d294b344181ea52",
}

FROZEN = {**_PRIOR_FROZEN, **_BOUNDED_SHADOW_PILOT}


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
        if got != expect:
            print(f"DRIFT: {rel} {got[:16]}"); ok = False
    print(f"total guarded artifacts: {len(FROZEN)} ({'OK' if ok else 'DRIFT DETECTED'})")
    return ok


if __name__ == "__main__":
    sys.exit(0 if verify() else 1)
