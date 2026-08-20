#!/usr/bin/env python3
"""Regenerate ``tests/data/phase5a_candidate.json`` from the genuine Phase 5A chain.

The payload lets the shipped sdist suite reconstruct the very candidate the real
Phase-3 → Phase 4C → Risk Authority → Phase 5A chain produces, through Phase 5A's exact
public types, without the monorepo test trees — which no distribution ships.

It is a **serialization of the genuine artifact**, not a hand-written stub: this script
builds the real chain and writes what it produced. ``tests/test_sdist_payload.py`` asserts
the file still reproduces the frozen candidate digest, so a drift between the chain and the
payload fails the suite rather than silently under-testing the sdist.

Run from a checkout after any deliberate change to the Phase 5A fixture chain:

    python packages/integration/cloud-scaling-producer-attestation/scripts/generate_frozen_candidate.py
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import sys
from datetime import timezone

PKG = pathlib.Path(__file__).resolve().parents[1]
REPO = PKG.parents[2]
for _path in (
    PKG / "src",
    PKG / "tests",
    REPO / "packages" / "integration" / "cloud-scaling-authorization-contracts" / "src",
    REPO / "packages" / "capabilities" / "cloud-scaling-controller" / "src",
    REPO / "packages" / "risk_authority" / "src",
    REPO / "packages" / "integration" / "cloud-scaling-risk-integration" / "src",
    REPO / "packages" / "trusted-evidence-authority" / "src",
    REPO / "packages" / "capabilities" / "cloud-scaling-controller" / "tests",
    REPO / "packages" / "capabilities" / "cloud-scaling-controller" / "tests" / "planning",
):
    if _path.exists():
        sys.path.insert(0, str(_path))

TARGET = PKG / "tests" / "data" / "phase5a_candidate.json"


def _canonical_ts(value) -> str:
    """The spelling the packages canonicalize to: UTC, microseconds, trailing Z."""

    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def main() -> int:
    import _producer_fixtures as fixtures  # type: ignore[import-not-found]

    if fixtures.P5A is None:
        raise SystemExit(
            "the Phase 5A test tree is not reachable; this script must run from a checkout"
        )
    candidate = fixtures.P5A.build_candidate()

    scalars, datetimes = {}, {}
    for field in dataclasses.fields(candidate):
        value = getattr(candidate, field.name)
        if field.name in (
            "target_scope",
            "policy_binding",
            "producer_attestation",
            "evidence_references",
        ):
            continue
        if hasattr(value, "isoformat"):
            datetimes[field.name] = _canonical_ts(value)
        else:
            scalars[field.name] = value

    payload = {
        "note": (
            "Frozen serialization of the genuine Phase 5A CapacityAuthorizationCandidate. "
            "Regenerate with scripts/generate_frozen_candidate.py. The shipped sdist suite "
            "reconstructs this through Phase 5A's exact public types and asserts the "
            "candidate digest below, so a drift from the chain fails rather than passes."
        ),
        "expected_candidate_digest": candidate.candidate_digest,
        "scalars": scalars,
        "datetimes": datetimes,
        "evidence_references": list(candidate.evidence_references),
        "target_scope": {
            f.name: getattr(candidate.target_scope, f.name)
            for f in dataclasses.fields(candidate.target_scope)
        },
        "policy_binding": {
            f.name: getattr(candidate.policy_binding, f.name)
            for f in dataclasses.fields(candidate.policy_binding)
        },
        "producer_attestation": {
            key: (_canonical_ts(value) if hasattr(value, "isoformat") else value)
            for key, value in candidate.producer_attestation.to_canonical_dict().items()
            if key != "trust_state"
        },
    }
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {TARGET} (candidate digest {candidate.candidate_digest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
