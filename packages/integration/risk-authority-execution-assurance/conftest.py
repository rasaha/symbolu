"""Make the ``src`` layout (and the first-party deps) importable in-place.

Mirrors the RA-7 runtime-assurance package: tested from source without an
editable install, so this package's ``src`` and each first-party dependency's
``src`` are prepended to ``sys.path``. CI that pip-installs the wheels resolves the
same modules from site-packages; this only adds a source fallback for in-place
runs. (Decision Authority still needs its third-party ``pydantic`` from the
environment — RA-8 legitimately composes DA, which is pydantic-backed.)
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(__file__)
_REPO = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir, os.pardir))

for _src in (
    os.path.join(_HERE, "src"),
    os.path.join(_REPO, "packages", "risk_authority", "src"),
    os.path.join(
        _REPO, "packages", "integration", "risk-authority-status-runtime", "src"
    ),
    os.path.join(_REPO, "packages", "capabilities", "decision-authority", "src"),
    os.path.join(_REPO, "packages", "governance-contracts", "src"),
):
    if os.path.isdir(_src) and _src not in sys.path:
        sys.path.insert(0, _src)
