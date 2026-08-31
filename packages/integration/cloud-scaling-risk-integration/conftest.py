"""Make this package and its two dependencies importable in a bare source checkout.

Mirrors the RA-4.5 / RA-5 integration-package convention (no editable install required
to run the suite from the repository root).

* ``ugence_cloud_scaling_risk_integration`` — this package's ``src`` layout;
* ``ugence_cloud_scaling_controller``       — the advisory Cloud Scaling leaf;
* ``risk_authority``                        — the stdlib-only Risk Authority leaf.

The controller's own Phase-3 planning test helpers are additionally exposed so this
suite can build **genuine** recommendations through the real pipeline rather than
hand-rolled stubs — an adapter proven against a stub would prove nothing about the
contract it actually consumes.
"""

from __future__ import annotations

import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def find_repo_root() -> "pathlib.Path | None":
    """Locate the monorepo root without counting directory levels, or ``None``.

    ``UGENCE_REPO_ROOT`` overrides the search; otherwise walk upward for marker
    directories. ``None`` means there is no checkout — the ordinary case for a
    consumer running from an extracted sdist against installed distributions.
    """

    injected = os.environ.get("UGENCE_REPO_ROOT")
    if injected:
        return pathlib.Path(injected).resolve()
    for candidate in (HERE, *HERE.parents):
        if (candidate / "packages" / "capabilities" / "cloud-scaling-controller").is_dir() and (
            candidate / "packages" / "integration"
        ).is_dir():
            return candidate
    return None


REPO = find_repo_root()
_SRC_PATHS: tuple = (HERE / "src",)
if REPO is not None:
    CONTROLLER = REPO / "packages" / "capabilities" / "cloud-scaling-controller"
    _SRC_PATHS += (
        CONTROLLER / "src",
        REPO / "packages" / "risk_authority" / "src",
        # Genuine Phase-3 recommendation builders (tests only).
        CONTROLLER / "tests",
        CONTROLLER / "tests" / "planning",
    )

for _p in _SRC_PATHS:
    sp = str(_p)
    if _p.exists() and sp not in sys.path:
        sys.path.insert(0, sp)
