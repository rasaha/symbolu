"""Make this package and its dependency importable in a bare source checkout.

Mirrors the Phase 5A/5B convention (no editable install required to run the suite
from the repository root). The Policy Authority's own test tree is additionally
exposed so this suite can drive a **genuine** issuance and resolution through the
real pipeline: an adapter proven against a hand-rolled stub core would prove
nothing about the authority it is supposed to register with.
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
        if (candidate / "packages" / "policy-authority").is_dir() and (
            candidate / "packages" / "integration"
        ).is_dir():
            return candidate
    return None


REPO = find_repo_root()
_SRC_PATHS: tuple = (HERE / "src",)
if REPO is not None:
    PACKAGES = REPO / "packages"
    _SRC_PATHS += (
        PACKAGES / "policy-authority" / "src",
        PACKAGES / "uvi-policy-contracts" / "src",
        PACKAGES / "governance-contracts" / "src",
        # Genuine builders (tests only): the authority's own issuance fixtures.
        PACKAGES / "policy-authority" / "tests",
    )

for _p in _SRC_PATHS:
    sp = str(_p)
    if _p.exists() and sp not in sys.path:
        sys.path.insert(0, sp)
