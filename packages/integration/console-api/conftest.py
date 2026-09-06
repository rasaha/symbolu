"""Make the ``src`` layout and the four platform dependencies importable in-place.

Mirrors the sibling integration packages: tested from source without an editable
install.

The four entries after ``src`` are exactly the packages declared as install-time
dependencies in ``pyproject.toml`` under ruling CP-5. They are listed here for the
source run only. Nothing in this file relaxes the ruling: the suite's packaging test
reads the declared dependency set from ``pyproject.toml``, not from this path list, so
a dependency that is importable here but undeclared there still fails.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(__file__)
_REPO = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir, os.pardir))

for _src in (
    os.path.join(_HERE, "src"),
    os.path.join(_REPO, "packages", "capabilities", "context-minimization", "src"),
    os.path.join(_REPO, "packages", "governance-provider-framework", "src"),
    os.path.join(_REPO, "packages", "providers", "actiongate", "src"),
    os.path.join(_REPO, "packages", "providers", "tap", "src"),
    # The three provider distributions above reach the shared contracts and the
    # canonical JSON serializer through their own imports.
    os.path.join(_REPO, "packages", "governance-contracts", "src"),
    os.path.join(_REPO, "packages", "jcs", "src"),
):
    if os.path.isdir(_src) and _src not in sys.path:
        sys.path.insert(0, _src)
