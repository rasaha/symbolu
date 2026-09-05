"""Make this package and its dependencies importable in a bare source checkout.

Mirrors the conformance distribution's convention (no editable install required
to run the suite from the repository root). Two dependency test trees are
additionally exposed so this suite can drive the **genuine** pipeline end to
end:

* the Policy Authority's fixtures, for the recording verifier/signer/registry
  wrappers and the registry-snapshot helper — the ephemeral keys themselves are
  minted in this suite's own fixtures, at run time, from process randomness;
* the Agentic Proposer's specification mirror, for the injected
  domain-evaluation and strategy-policy stubs the ratified bind leg needs — the
  constitution side of that leg is the real resolved artifact, not a stub.
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
        PACKAGES / "capabilities" / "agentic-proposer" / "src",
        PACKAGES / "jcs" / "src",
        # The two constitution distributions this root composes.
        PACKAGES / "integration" / "agent-constitution-policy" / "src",
        PACKAGES / "integration" / "agent-constitution-conformance" / "src",
        # Genuine builders (tests only), from both sides of this integration.
        PACKAGES / "policy-authority" / "tests",
        PACKAGES / "capabilities" / "agentic-proposer" / "tests",
    )

for _p in _SRC_PATHS:
    sp = str(_p)
    if _p.exists() and sp not in sys.path:
        sys.path.insert(0, sp)
