"""Make the ``src`` layout (and the RA leaf + RA-6 status runtime) importable in-place.

Mirrors the governance leaves: the package is tested from source without an
editable install, so this package's ``src``, the RA leaf's ``src``, and the RA-6
status-runtime ``src`` are prepended to ``sys.path``. CI that pip-installs the
wheels resolves the same modules from site-packages; this only adds a source
fallback for in-place runs.
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
):
    if os.path.isdir(_src) and _src not in sys.path:
        sys.path.insert(0, _src)
