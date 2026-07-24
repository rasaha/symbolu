"""Verification guard for the Minimal Evidence Obligation Policy and Internal Utility Pilot.

Fails on drift of ANY prior outcome-bearing artifact this simplification track must NOT modify. Consumes
every completed component READ-ONLY: EvidenceAssurance, AssertionGate, ActionGate, ClaimIntegrity,
ScopeIntegrity, ExecutionGate, ModelPolicy, governed_inference_pilot, customer_shadow_readiness,
bounded_shadow_pilot, and evidence_obligation.

Guarded set = the 32 artifacts pinned by the evidence_obligation guard PLUS the 13 outcome-bearing
artifacts produced by the completed evidence_obligation study. 45 total.
"""
from __future__ import annotations

import hashlib
import os
import sys

from evidence_obligation.verify_prior_artifacts import FROZEN as _PRIOR_FROZEN

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_EVIDENCE_OBLIGATION = {
    "evidence_obligation/eval_results/ablation.json":
        "eb705b36026c775ddf1bd0e81e49ff48438e487cae41c5086f2a096e80435000",
    "evidence_obligation/eval_results/baselines.json":
        "261170df318e5ff29d9a5e4c9e5129be9e6a4f280c9cae1106bb472f489d2998",
    "evidence_obligation/eval_results/calibration_frontier.json":
        "2fd70c348ef57e58d23c1d02807e7f8a39dbac8eb3e127289692ed112e886a4a",
    "evidence_obligation/eval_results/decision.json":
        "782ca74206e7956e932b59a60e6cfef92e0ea8eba25f16192bb40c1c8a4c1331",
    "evidence_obligation/eval_results/downstream.json":
        "1e6e54b80471a658583a050594daaa80b47723459a6399cc392f1c714013f317",
    "evidence_obligation/eval_results/error_propagation.json":
        "ddab2e219e7d6ef942c69cbdad126ec215893d3435ceddf83bce33b7968914e0",
    "evidence_obligation/eval_results/evaluation_freeze.json":
        "7ce44c9ee05701b5e5d395703ce116f77b03e74dbd72479758a40ca9ff0161fe",
    "evidence_obligation/eval_results/final_evaluation.json":
        "a12c5fc49e6a9704d730ff5458efa8156a4958706d23666fa78eb8b78a2fda2f",
    "evidence_obligation/eval_results/review_study.json":
        "349da03e833f660ca2643f4e60a2c014f4b3ec2d596b0e16a3720b10f507f285",
    "evidence_obligation/data/v1/adversarial_obligation.json":
        "4f8b76a0f46b9935c2e23d7925948b138eb8295a76f7094c43caf2fa8a5aabc2",
    "evidence_obligation/data/v1/development.json":
        "6ebe5d1a8f92d3378b91c461ef29960136586b4cbdeedd268560179b88a6d5f5",
    "evidence_obligation/data/v1/held_out_natural.json":
        "e4164ea2343610771e15ff0493b235221d6338ebc3eb88ab34e7f53accb0ffa8",
    "evidence_obligation/data/v1/manifest.json":
        "c8ad58b3e43aa55b5d751ec227beb9fcfe0ef89b54b55b4b8f57ffd35b425d79",
}

FROZEN = {**_PRIOR_FROZEN, **_EVIDENCE_OBLIGATION}


def _sha(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def verify() -> bool:
    ok = True
    for rel, expect in FROZEN.items():
        p = os.path.join(_ROOT, rel)
        if not os.path.exists(p):
            print(f"MISSING: {rel}"); ok = False; continue
        if _sha(p) != expect:
            print(f"DRIFT: {rel}"); ok = False
    print(f"total guarded artifacts: {len(FROZEN)} ({'OK' if ok else 'DRIFT DETECTED'})")
    return ok


if __name__ == "__main__":
    sys.exit(0 if verify() else 1)
