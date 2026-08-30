"""Make this package and its dependencies importable in a bare source checkout.

Mirrors the capacity-bounds convention (no editable install required to run the
suite from the repository root). Two dependency test trees are additionally
exposed so this suite can drive the **genuine** pipeline on both sides of the
boundary it integrates:

* the Policy Authority's fixtures, for real issuance, real Ed25519 signing, the
  real registry and real resolution;
* the Agentic Proposer's specification mirror, for the injected domain-evaluation
  stub and the deliberately mis-echoing resolver stub the ratified proof
  obligations call for.

A resolver proven against stubs on both sides would prove nothing about the two
packages it exists to join.
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
        PACKAGES / "integration" / "agentic-proposer-strategy-permission-policy" / "src",
        PACKAGES / "policy-authority" / "src",
        PACKAGES / "uvi-policy-contracts" / "src",
        PACKAGES / "governance-contracts" / "src",
        PACKAGES / "capabilities" / "agentic-proposer" / "src",
        PACKAGES / "jcs" / "src",
        # Genuine builders (tests only), from both sides of this integration.
        PACKAGES / "policy-authority" / "tests",
        PACKAGES / "capabilities" / "agentic-proposer" / "tests",
    )

for _p in _SRC_PATHS:
    sp = str(_p)
    if _p.exists() and sp not in sys.path:
        sys.path.insert(0, sp)
