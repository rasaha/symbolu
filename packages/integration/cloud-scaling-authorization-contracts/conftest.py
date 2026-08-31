"""Make this package and its three dependencies importable in a bare source checkout.

Mirrors the Phase 4C convention (no editable install required to run the suite from the
repository root). The controller's Phase-3 planning helpers are additionally exposed so
this suite can build a **genuine** recommendation through the real pipeline: a Phase 5A
contract proven against a hand-rolled stub would prove nothing about the Phase 4C artifact
it actually consumes.
"""

from __future__ import annotations

import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
# packages/integration/cloud-scaling-authorization-contracts -> integration -> packages -> repo
#
# ``UGENCE_REPO_ROOT`` overrides the count, and the gate-removal mutation sweep is why. The
# sweep runs this suite from a disposable copy of the package **outside** the repository, so
# counting three directories upward lands somewhere that has no ``packages/`` at all: the
# controller's Phase-3 test builders stop resolving and every collection fails with
# ``No module named 'ph_helpers'`` before a single guard is scored. Locating the checkout by
# an explicit environment variable is what the producer-attestation tree already does, for
# exactly this reason. Unset — every ordinary run — the count is unchanged.
_declared = os.environ.get("UGENCE_REPO_ROOT")
REPO = pathlib.Path(_declared).resolve() if _declared else HERE.parents[2]
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
