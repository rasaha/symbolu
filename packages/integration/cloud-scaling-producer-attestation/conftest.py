"""Make this package and its dependencies importable in a bare source checkout.

Mirrors the Phase 4C/5A convention (no editable install required to run the suite from the
repository root). The Phase 5A test tree and the controller's Phase-3 planning helpers are
additionally exposed so this suite can build a **genuine** Phase 5A candidate through the
real pipeline: a producer-authenticity contract proven against a hand-rolled stub candidate
would prove nothing about the artifact it actually consumes.
"""

from __future__ import annotations

import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def repo_root() -> pathlib.Path:
    """Locate the monorepo root without counting directory levels.

    Counting ``parents[n]`` breaks the moment this tree is copied somewhere else — which
    the guard sweep does on every mutation, deliberately, into a disposable directory
    outside the repository. ``UGENCE_REPO_ROOT`` is how the sweep tells a copy where the
    real repository is; otherwise the search walks upward for the marker directories.
    """

    injected = os.environ.get("UGENCE_REPO_ROOT")
    if injected:
        return pathlib.Path(injected).resolve()
    for candidate in (HERE, *HERE.parents):
        if (candidate / "packages" / "risk_authority").is_dir() and (
            candidate / "packages" / "trusted-evidence-authority"
        ).is_dir():
            return candidate
    raise RuntimeError(
        "could not locate the monorepo root from "
        f"{HERE}; set UGENCE_REPO_ROOT to the checkout"
    )


REPO = repo_root()
CONTROLLER = REPO / "packages" / "capabilities" / "cloud-scaling-controller"
PHASE_5A = REPO / "packages" / "integration" / "cloud-scaling-authorization-contracts"

_SRC_PATHS = (
    HERE / "src",
    PHASE_5A / "src",
    CONTROLLER / "src",
    REPO / "packages" / "risk_authority" / "src",
    REPO / "packages" / "integration" / "cloud-scaling-risk-integration" / "src",
    REPO / "packages" / "trusted-evidence-authority" / "src",
    # Genuine Phase-3 recommendation builders (tests only).
    CONTROLLER / "tests",
    CONTROLLER / "tests" / "planning",
)

for _p in _SRC_PATHS:
    sp = str(_p)
    if _p.exists() and sp not in sys.path:
        sys.path.insert(0, sp)
