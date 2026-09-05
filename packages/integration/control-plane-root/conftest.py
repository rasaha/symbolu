"""Make the ``src`` layout importable in-place, and governance-contracts available
**to the tests only**.

The package itself depends on nothing but the standard library: ``AuditReference``
is injected by the caller, and ``tests/test_boundaries.py`` asserts the package
names governance-contracts nowhere. The tests need the real contract to prove the
injection seam actually fits — a test that used a stand-in would prove only that
the stand-in fits.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(__file__)
_REPO = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir, os.pardir))

for _src in (
    os.path.join(_HERE, "src"),
    os.path.join(_HERE, "tests"),  # shared builders imported by bare name
    os.path.join(_REPO, "packages", "governance-contracts", "src"),  # tests only
):
    if os.path.isdir(_src) and _src not in sys.path:
        sys.path.insert(0, _src)
