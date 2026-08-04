"""Make the package ``src`` and the ``tests`` directory importable.

Allows the package-local suite to run standalone (``pytest packages/.../tests``) or
from an installed wheel, without an editable install.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(__file__)
_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))

# Prefer an installed distribution if present; otherwise fall back to the source tree.
try:  # pragma: no cover - environment dependent
    import ugence_cloud_scaling_controller  # noqa: F401
except ImportError:  # pragma: no cover
    if _SRC not in sys.path:
        sys.path.insert(0, _SRC)

sys.path.insert(0, _HERE)  # so tests can 'import support'
