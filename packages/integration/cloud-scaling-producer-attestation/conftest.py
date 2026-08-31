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


def find_repo_root() -> "pathlib.Path | None":
    """Locate the monorepo root without counting directory levels, or ``None``.

    Counting ``parents[n]`` breaks the moment this tree is copied elsewhere — which the
    guard sweep does on every mutation, into a disposable directory outside the repository.
    ``UGENCE_REPO_ROOT`` is how the sweep tells a copy where the real checkout is; otherwise
    the search walks upward for the marker directories.

    Returns ``None`` when there is no checkout at all. That is the ordinary case for a
    consumer who extracted the sdist: the suite then runs against the **installed**
    distributions, which is exactly what a downstream re-run is supposed to verify.
    """

    injected = os.environ.get("UGENCE_REPO_ROOT")
    if injected:
        return pathlib.Path(injected).resolve()
    for candidate in (HERE, *HERE.parents):
        if (candidate / "packages" / "risk_authority").is_dir() and (
            candidate / "packages" / "trusted-evidence-authority"
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
#: Source trees to expose, in a checkout. Outside one, ``REPO`` is ``None`` and the suite
#: imports every dependency from site-packages instead — which is the point of shipping it.
_SRC_PATHS: tuple = (HERE / "src",)
if REPO is not None:
    CONTROLLER = REPO / "packages" / "capabilities" / "cloud-scaling-controller"
    PHASE_5A = REPO / "packages" / "integration" / "cloud-scaling-authorization-contracts"
    _SRC_PATHS += (
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
