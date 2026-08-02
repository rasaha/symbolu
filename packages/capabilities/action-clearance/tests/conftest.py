"""Test wiring for the Action Clearance package (path + fixture only).

Shared builders live in ``ac_helpers`` (uniquely named to avoid the repo-root
``conftest`` shadowing that plain ``from conftest import`` would trigger).
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SRC = _HERE.parent / "src"
for _p in (str(_HERE), str(_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from ac_helpers import ActionClearanceEvaluator  # noqa: E402


@pytest.fixture
def evaluator():
    return ActionClearanceEvaluator()
