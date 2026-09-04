"""Make this package and its dependencies importable in a bare source checkout.

Mirrors the 5B-0A/5B-0B convention. The neighbouring test trees are exposed so this suite
can drive the **genuine** chain — controller Phase-3 recommendation, 4C projection, Risk
Authority decision, 5A candidate, a real issued bounds policy, a real minted v2 attestation —
rather than a hand-rolled stub of any of them.
"""

from __future__ import annotations

import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def find_repo_root() -> "pathlib.Path | None":
    injected = os.environ.get("UGENCE_REPO_ROOT")
    if injected:
        return pathlib.Path(injected).resolve()
    for candidate in (HERE, *HERE.parents):
        if (candidate / "packages" / "risk_authority").is_dir() and (
            candidate / "packages" / "policy-authority"
        ).is_dir():
            return candidate
    return None


REPO = find_repo_root()
_SRC_PATHS: tuple = (HERE / "src",)
if REPO is not None:
    PACKAGES = REPO / "packages"
    INTEGRATION = PACKAGES / "integration"
    CONTROLLER = PACKAGES / "capabilities" / "cloud-scaling-controller"
    _SRC_PATHS += (
        PACKAGES / "risk_authority" / "src",
        PACKAGES / "trusted-evidence-authority" / "src",
        PACKAGES / "policy-authority" / "src",
        PACKAGES / "uvi-policy-contracts" / "src",
        PACKAGES / "governance-contracts" / "src",
        INTEGRATION / "cloud-scaling-risk-integration" / "src",
        INTEGRATION / "cloud-scaling-authorization-contracts" / "src",
        INTEGRATION / "cloud-scaling-policy-authenticity" / "src",
        INTEGRATION / "cloud-scaling-producer-attestation" / "src",
        CONTROLLER / "src",
        # Genuine builders (tests only).
        PACKAGES / "policy-authority" / "tests",
        INTEGRATION / "cloud-scaling-policy-authenticity" / "tests",
        INTEGRATION / "cloud-scaling-producer-attestation" / "tests",
        CONTROLLER / "tests",
        CONTROLLER / "tests" / "planning",
    )

for _p in _SRC_PATHS:
    sp = str(_p)
    if _p.exists() and sp not in sys.path:
        sys.path.insert(0, sp)
