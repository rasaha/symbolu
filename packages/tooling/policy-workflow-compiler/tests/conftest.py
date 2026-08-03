"""Pytest fixtures for the compiler test suite.

Adds the tests directory to ``sys.path`` so tests can ``from _builders import
...`` the shared synthetic pack builders under ``--import-mode=importlib``.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import pytest  # noqa: E402

from _builders import build_full_synthetic_pack  # noqa: E402


@pytest.fixture
def synthetic_pack():
    return build_full_synthetic_pack()


@pytest.fixture
def procurement_pack():
    from ugence_policy_workflow_compiler.reference.procurement import (
        build_procurement_policy_pack,
    )

    return build_procurement_policy_pack()
