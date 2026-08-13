"""Make the ``src`` layout importable when running the suite in-place.

Mirrors the other governance leaves: the package is tested from source without
an editable install, so the ``src`` directory is prepended to ``sys.path``.
"""

from __future__ import annotations

import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
