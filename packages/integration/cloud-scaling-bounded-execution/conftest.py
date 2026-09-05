"""Make this package and its dependencies importable in a bare source checkout.

The 5C and 5X test trees are exposed so this suite drives the genuine chain: the 5B-4 world, an
issued envelope, an admitted capacity action, a genuine CLEAR clearance receipt, a
reservation in the execution ledger, and then a credential grant.
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
    CAPABILITIES = PACKAGES / "capabilities"
    CONTROLLER = CAPABILITIES / "cloud-scaling-controller"
    _SRC_PATHS += (
        PACKAGES / "risk_authority" / "src",
        PACKAGES / "trusted-evidence-authority" / "src",
        PACKAGES / "policy-authority" / "src",
        PACKAGES / "uvi-policy-contracts" / "src",
        PACKAGES / "governance-contracts" / "src",
        CAPABILITIES / "action-clearance" / "src",
        CAPABILITIES / "decision-authority" / "src",
        INTEGRATION / "execution-reservation" / "src",
        INTEGRATION / "cloud-scaling-risk-integration" / "src",
        INTEGRATION / "cloud-scaling-authorization-contracts" / "src",
        INTEGRATION / "cloud-scaling-policy-authenticity" / "src",
        INTEGRATION / "cloud-scaling-producer-attestation" / "src",
        INTEGRATION / "cloud-scaling-envelope-issuance" / "src",
        INTEGRATION / "cloud-scaling-action-admission" / "src",
        INTEGRATION / "cloud-scaling-credential-broker" / "src",
        INTEGRATION / "risk-authority-execution-assurance" / "src",
        CAPABILITIES / "cloud-scaling-operations" / "src",
        CONTROLLER / "src",
        # Genuine builders (tests only).
        PACKAGES / "policy-authority" / "tests",
        INTEGRATION / "cloud-scaling-policy-authenticity" / "tests",
        INTEGRATION / "cloud-scaling-producer-attestation" / "tests",
        INTEGRATION / "cloud-scaling-envelope-issuance" / "tests",
        INTEGRATION / "cloud-scaling-action-admission" / "tests",
        INTEGRATION / "cloud-scaling-credential-broker" / "tests",
        CONTROLLER / "tests",
        CONTROLLER / "tests" / "planning",
    )

for _p in _SRC_PATHS:
    sp = str(_p)
    if _p.exists() and sp not in sys.path:
        sys.path.insert(0, sp)
