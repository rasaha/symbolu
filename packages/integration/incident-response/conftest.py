"""Make the ``src`` layout and the first-party dependency importable in-place.

Mirrors the sibling integration packages: tested from source without an editable
install. Nothing here needs a third-party package.

RA-6 (``packages/risk_authority``) is on the path **for the tests only**. The
package itself must never import it — ``tests/test_boundaries.py`` enforces that —
but the cross-package signal contract can only be pinned by a test that imports
both sides, and a test that does not is the vacuous kind this package's own
review caught.
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
    os.path.join(_REPO, "packages", "risk_authority", "src"),  # tests only; see above
):
    if os.path.isdir(_src) and _src not in sys.path:
        sys.path.insert(0, _src)
