"""Make the ``src`` layout and the first-party dependencies importable in-place.

Mirrors the RA-8 package: tested from source without an editable install, so this
package's ``src`` and each first-party dependency's ``src`` are prepended to
``sys.path``. Decision Authority still needs its third-party ``pydantic`` from the
environment; this package defines no pydantic model of its own.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(__file__)
_REPO = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir, os.pardir))

for _src in (
    os.path.join(_HERE, "src"),
    os.path.join(_HERE, "tests"),  # shared builders (_fixtures) imported by bare name
    os.path.join(_REPO, "packages", "governance-contracts", "src"),
    os.path.join(_REPO, "packages", "capabilities", "action-clearance", "src"),
    os.path.join(_REPO, "packages", "capabilities", "decision-authority", "src"),
):
    if os.path.isdir(_src) and _src not in sys.path:
        sys.path.insert(0, _src)
