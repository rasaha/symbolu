"""Make the ``src`` layout and the one first-party dependency importable in-place.

Mirrors the sibling integration packages: tested from source without an editable
install. The single entry after ``src`` is the only distribution this package
declares — ``ugence-action-clearance``, for the frozen receipt type CE-2 forbids
redefining.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(__file__)
_REPO = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir, os.pardir))

for _src in (
    os.path.join(_HERE, "src"),
    os.path.join(_HERE, "tests"),  # shared builders (_fixtures) imported by bare name
    os.path.join(_REPO, "packages", "capabilities", "action-clearance", "src"),
):
    if os.path.isdir(_src) and _src not in sys.path:
        sys.path.insert(0, _src)
