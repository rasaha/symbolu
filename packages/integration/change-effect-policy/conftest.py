"""Make this package and its dependencies importable in a bare source checkout.

Mirrors the strategy-permission convention exactly: no editable install is required to
run the suite from the repository root, and the Policy Authority's own test tree is
exposed so this suite can drive a genuine issuance through the real pipeline rather than
against a stub. An adapter proven against a hand-rolled core would prove nothing about
the authority it registers with.
"""

from __future__ import annotations

import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def find_repo_root() -> "pathlib.Path | None":
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
_SRC_PATHS: tuple = (HERE / "src", HERE / "tests")
if REPO is not None:
    PACKAGES = REPO / "packages"
    _SRC_PATHS += (
        PACKAGES / "policy-authority" / "src",
        PACKAGES / "uvi-policy-contracts" / "src",
        PACKAGES / "governance-contracts" / "src",
        PACKAGES / "jcs" / "src",
        PACKAGES / "policy-authority" / "tests",
    )

for _p in _SRC_PATHS:
    sp = str(_p)
    if _p.exists() and sp not in sys.path:
        sys.path.insert(0, sp)
