"""Test wiring for the Code Governance product package.

Puts the product ``src`` and the capability ``src`` trees on ``sys.path`` so a
source checkout resolves the product and its public-API dependencies without an
editable install (mirrors the repo-root ``conftest.py`` convention).
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve()
_PRODUCT_SRC = _HERE.parents[1] / "src"
_REPO_ROOT = _HERE.parents[3]

_SRC_PATHS = [
    _HERE.parent,  # tests dir — makes cg_helpers importable regardless of CWD
    _PRODUCT_SRC,
    _REPO_ROOT / "packages" / "governance-contracts" / "src",
    _REPO_ROOT / "packages" / "governance-provider-framework" / "src",
    _REPO_ROOT / "packages" / "capabilities" / "storygraph" / "src",
    _REPO_ROOT / "packages" / "capabilities" / "decision-authority" / "src",
    _REPO_ROOT / "packages" / "capabilities" / "action-clearance" / "src",
]
for _p in _SRC_PATHS:
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import pytest  # noqa: E402

from cg_helpers import CodeGovernanceService  # noqa: E402


@pytest.fixture
def service() -> CodeGovernanceService:
    return CodeGovernanceService()
