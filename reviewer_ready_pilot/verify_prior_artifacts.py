"""Verification guard for the Reviewer-Ready Internal Pilot Preparation track.

Fails on drift of ANY prior outcome-bearing artifact this track must NOT modify. This track begins from
minimal_evidence_policy and consumes every completed component READ-ONLY: minimal_evidence_policy,
evidence_obligation, EvidenceAssurance, AssertionGate, ActionGate, ClaimIntegrity, ScopeIntegrity,
ExecutionGate, ModelPolicy, governed_inference_pilot, customer_shadow_readiness, bounded_shadow_pilot.

Guarded set = the 45 artifacts pinned by the minimal_evidence_policy guard (which already includes the
32 evidence_obligation-track artifacts + 13 minimal_evidence_policy outcome-bearing artifacts). Reused
verbatim so the hashes never diverge from the prior guard.
"""
from __future__ import annotations

import hashlib
import os
import sys

from minimal_evidence_policy.verify_prior_artifacts import FROZEN as _FROZEN

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FROZEN = dict(_FROZEN)


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
