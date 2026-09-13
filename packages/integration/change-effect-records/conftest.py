"""Make the ``src`` layout and the first-party dependency importable in-place.

Mirrors the sibling integration packages: tested from source without an editable
install. Nothing here needs a third-party package.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(__file__)
_REPO = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir, os.pardir))

for _src in (
    os.path.join(_HERE, "src"),
    os.path.join(_HERE, "tests"),
    os.path.join(_REPO, "packages", "governance-contracts", "src"),
    # The item 3.4 linkage module's single extra dependency. It is on the path because
    # linkage.py imports the immutable entry contract from it; nothing here appends.
    os.path.join(_REPO, "packages", "integration", "control-plane-root", "src"),
):
    if os.path.isdir(_src) and _src not in sys.path:
        sys.path.insert(0, _src)
