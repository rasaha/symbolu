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

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
# packages/integration/cloud-scaling-risk-integration -> packages/integration -> packages -> repo
REPO = HERE.parents[2]
CONTROLLER = REPO / "packages" / "capabilities" / "cloud-scaling-controller"

_SRC_PATHS = (
    HERE / "src",
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
