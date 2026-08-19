"""Make this package and its three dependencies importable in a bare source checkout.

Mirrors the Phase 4C convention (no editable install required to run the suite from the
repository root). The controller's Phase-3 planning helpers are additionally exposed so
this suite can build a **genuine** recommendation through the real pipeline: a Phase 5A
contract proven against a hand-rolled stub would prove nothing about the Phase 4C artifact
it actually consumes.
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
# packages/integration/cloud-scaling-authorization-contracts -> integration -> packages -> repo
REPO = HERE.parents[2]
CONTROLLER = REPO / "packages" / "capabilities" / "cloud-scaling-controller"

_SRC_PATHS = (
    HERE / "src",
    CONTROLLER / "src",
    REPO / "packages" / "risk_authority" / "src",
    REPO / "packages" / "integration" / "cloud-scaling-risk-integration" / "src",
    # Genuine Phase-3 recommendation builders (tests only).
    CONTROLLER / "tests",
    CONTROLLER / "tests" / "planning",
)

for _p in _SRC_PATHS:
    sp = str(_p)
    if _p.exists() and sp not in sys.path:
        sys.path.insert(0, sp)
