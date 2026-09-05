"""Make this package and its dependencies importable in a bare source checkout.

The 5B-4 test tree is exposed on purpose: this suite drives the genuine chain through
``cloud-scaling-envelope-issuance``'s fixtures (controller recommendation, 4C projection,
Risk Authority decision, 5A candidate, issued bounds policy, minted attestation, issued
envelope) and admits the capacity action that envelope was issued for.
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
        INTEGRATION / "cloud-scaling-envelope-issuance" / "src",
        CONTROLLER / "src",
        # Genuine builders (tests only).
        PACKAGES / "policy-authority" / "tests",
        INTEGRATION / "cloud-scaling-policy-authenticity" / "tests",
        INTEGRATION / "cloud-scaling-producer-attestation" / "tests",
        INTEGRATION / "cloud-scaling-envelope-issuance" / "tests",
        CONTROLLER / "tests",
        CONTROLLER / "tests" / "planning",
    )

for _p in _SRC_PATHS:
    sp = str(_p)
    if _p.exists() and sp not in sys.path:
        sys.path.insert(0, sp)
