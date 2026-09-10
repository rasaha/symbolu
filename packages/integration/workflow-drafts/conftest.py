"""Make the ``src`` layout importable in-place.

Mirrors the sibling integration packages: tested from source without an editable
install. Nothing here needs a third-party package, and this package has no first-party
dependency to add.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(__file__)

for _src in (os.path.join(_HERE, "src"), os.path.join(_HERE, "tests")):
    if os.path.isdir(_src) and _src not in sys.path:
        sys.path.insert(0, _src)
