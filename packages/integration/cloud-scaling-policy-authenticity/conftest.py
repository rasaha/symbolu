"""Make this package and its dependencies importable in a bare source checkout.

Mirrors the Phase 5A/5B-0A convention (no editable install required to run the suite from
the repository root). The Policy Authority's own test tree and the Phase 5A test tree are
additionally exposed so this suite can build a **genuine** issued policy record through the
real issuance pipeline, and a **genuine** Phase 5A candidate through the real Phase 3/4C/5A
pipeline. A policy-authenticity contract proven against a hand-rolled stub record would
prove nothing about the artifact it actually consumes.
"""

from __future__ import annotations

import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def find_repo_root() -> "pathlib.Path | None":
    """Locate the monorepo root without counting directory levels, or ``None``.

    Counting ``parents[n]`` breaks the moment this tree is copied elsewhere.
    ``UGENCE_REPO_ROOT`` overrides the search; otherwise it walks upward for marker
    directories. ``None`` means there is no checkout at all — the ordinary case for a
    consumer who extracted the sdist, where the suite then runs against the **installed**
    distributions, which is what a downstream re-run is supposed to verify.
    """

    injected = os.environ.get("UGENCE_REPO_ROOT")
    if injected:
        return pathlib.Path(injected).resolve()
    for candidate in (HERE, *HERE.parents):
        if (candidate / "packages" / "policy-authority").is_dir() and (
            candidate / "packages" / "integration"
        ).is_dir():
            return candidate
    return None


def repo_root() -> pathlib.Path:
    """The monorepo root, or a clear failure. For callers that genuinely require one."""

    found = find_repo_root()
    if found is None:
        raise RuntimeError(
            f"could not locate the monorepo root from {HERE}; set UGENCE_REPO_ROOT"
        )
    return found


REPO = find_repo_root()
_SRC_PATHS: tuple = (HERE / "src",)
if REPO is not None:
    PACKAGES = REPO / "packages"
    CONTROLLER = PACKAGES / "capabilities" / "cloud-scaling-controller"
    PHASE_5A = PACKAGES / "integration" / "cloud-scaling-authorization-contracts"
    _SRC_PATHS += (
        PACKAGES / "policy-authority" / "src",
        PACKAGES / "uvi-policy-contracts" / "src",
        PACKAGES / "governance-contracts" / "src",
        PHASE_5A / "src",
        CONTROLLER / "src",
        PACKAGES / "risk_authority" / "src",
        PACKAGES / "integration" / "cloud-scaling-risk-integration" / "src",
        # Genuine builders (tests only): the authority's issuance fixtures, and the
        # controller's Phase-3 recommendation helpers the Phase 5A conftest needs.
        PACKAGES / "policy-authority" / "tests",
        CONTROLLER / "tests",
        CONTROLLER / "tests" / "planning",
    )

for _p in _SRC_PATHS:
    sp = str(_p)
    if _p.exists() and sp not in sys.path:
        sys.path.insert(0, sp)
