"""Composition-root tests: the only place the Decision Authority kernel is imported.

The package under test imports nothing but governance-contracts and the standard
library — ``tests/test_boundaries.py`` asserts that over the AST. The *seam* between
the two, however, is a composition-root concern, so these tests import both sides and
wire them the way a real composition root would.

The kernel brings pydantic with it. When pydantic is unavailable the module skips, so
the default suite still runs dependency-free.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(__file__)
_REPO = os.path.abspath(os.path.join(_HERE, *([os.pardir] * 5)))
_DA_SRC = os.path.join(_REPO, "packages", "capabilities", "decision-authority", "src")

if os.path.isdir(_DA_SRC) and _DA_SRC not in sys.path:
    sys.path.insert(0, _DA_SRC)
