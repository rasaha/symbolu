"""Make this package and its declared dependencies importable from a bare checkout.

Outside a checkout (an extracted sdist), nothing is added and the suite runs
against installed distributions, which is what a downstream re-run verifies.
The governance contracts pull in their own three leaves (jcs, governance
contracts, UVI policy contracts), so those are added too.
"""

from __future__ import annotations

import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def find_repo_root():
    injected = os.environ.get("UGENCE_REPO_ROOT")
    if injected:
        return pathlib.Path(injected).resolve()
    for candidate in (HERE, *HERE.parents):
        if (candidate / "packages" / "capabilities" / "reasoning-method-governance").is_dir() and (
            candidate / "packages" / "trusted-evidence-authority"
        ).is_dir():
            return candidate
    return None


REPO = find_repo_root()
_SRC_PATHS: tuple = (HERE / "src", HERE / "tests")
if REPO is not None:
    _SRC_PATHS += (
        REPO / "packages" / "capabilities" / "reasoning-method-governance" / "src",
        REPO / "packages" / "trusted-evidence-authority" / "src",
        REPO / "packages" / "governance-contracts" / "src",
        REPO / "packages" / "uvi-policy-contracts" / "src",
        REPO / "packages" / "jcs" / "src",
    )
for _p in _SRC_PATHS:
    sp = str(_p)
    if _p.exists() and sp not in sys.path:
        sys.path.insert(0, sp)
