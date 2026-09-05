"""Composition-root tests: the only place the approval workflow is imported.

The package under test imports nothing but governance-contracts and the standard
library — ``tests/test_boundaries.py`` asserts that over the AST. The *seam* between
the directory and its consumer is a composition-root concern, so these tests import
both sides and wire them the way a real composition root would.

The module skips when the approval workflow is unavailable, so the default suite runs
without it.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(__file__)
_REPO = os.path.abspath(os.path.join(_HERE, *([os.pardir] * 5)))
_CONSUMER_SRC = os.path.join(_REPO, "packages", "integration", "approval-workflow", "src")

if os.path.isdir(_CONSUMER_SRC) and _CONSUMER_SRC not in sys.path:
    sys.path.insert(0, _CONSUMER_SRC)
