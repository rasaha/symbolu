"""Verification guard for the Real Reviewer Calibration and Internal Single-Tenant Utility Pilot.

Fails on drift of ANY prior outcome-bearing artifact this track must NOT modify. Consumes every completed
component READ-ONLY: minimal_evidence_policy, evidence_obligation, EvidenceAssurance, AssertionGate,
ActionGate, ClaimIntegrity, ScopeIntegrity, ExecutionGate, ModelPolicy, governed_inference_pilot,
customer_shadow_readiness, bounded_shadow_pilot.

Guarded set = the 45 artifacts pinned by the minimal_evidence_policy guard PLUS the 14 outcome-bearing
artifacts produced by the completed minimal_evidence_policy study. 59 total.
"""
from __future__ import annotations

import hashlib
import os
import sys

from minimal_evidence_policy.verify_prior_artifacts import FROZEN as _PRIOR_FROZEN

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_MINIMAL_EVIDENCE_POLICY = {
    "minimal_evidence_policy/eval_results/ablation.json":
        "6b30d703fb8617f080c696ae17ac4fe51abc00bfec68da5c6c95bce644bb7748",
    "minimal_evidence_policy/eval_results/baselines.json":
        "8fe9e41aa99022d694079171726a24a08a31409ea67cf8acb02ffa20662b19c8",
    "minimal_evidence_policy/eval_results/decision.json":
        "70db8ed33bc528fd06de6962f539bf37b4858828be20a18d5dd802436c646787",
    "minimal_evidence_policy/eval_results/error_propagation.json":
        "75e02e340c9a71c34be41b910191d4c9d5a4f42f6605845f1f25241c922ea391",
    "minimal_evidence_policy/eval_results/evaluation_freeze.json":
        "708bb7a41e2895b560a22af32ef0cc7351348b17900ac4d12be7b329b9a1baeb",
    "minimal_evidence_policy/eval_results/final_evaluation.json":
        "4fd54da87fe069b6b79f808dd314693412f46684d3ac4723e51d06ca158bb2ab",
    "minimal_evidence_policy/eval_results/frontier.json":
        "b010e6d15a536e93753f16855da819f4e8fd44c7ea348c10cf31380984c1b1e6",
    "minimal_evidence_policy/eval_results/internal_pilot.json":
        "48591902679c8377fd5bc5191a5e2c8cfd7fe93e0488208a07bdd2612f1a6782",
    "minimal_evidence_policy/eval_results/review_study.json":
        "7550d26c11c6d86ed8823dbbf81192af5414088e560f54a7260a222ac62c2b16",
    "minimal_evidence_policy/data/v1/adversarial_invariants.json":
        "813cd262dffb41ae564ec8d73cb1b1dd902f5e777e0ab6156dda378b1a760b1a",
    "minimal_evidence_policy/data/v1/development.json":
        "2b0fe667bfc440671dc7ec1ebe157ce4250fd06cef625489b387390b58fd0301",
    "minimal_evidence_policy/data/v1/held_out_natural.json":
        "a01a97180c85b5c5fc6e6aef9400c4a5d91e05c66a35371420055a0cd10aa551",
    "minimal_evidence_policy/data/v1/human_review_set.json":
        "83e8583c216bec65776fb80ac084973dc910a7674bc4847441ba96466f848a8a",
    "minimal_evidence_policy/data/v1/manifest.json":
        "dfe14ff15c4537b1013cd17802f58ab981094c743d1c232c345190ca4b7d8078",
}

FROZEN = {**_PRIOR_FROZEN, **_MINIMAL_EVIDENCE_POLICY}


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
