"""Shared fixtures for the Governance Provider Framework package tests.

The kernel-lifecycle integration helper lives in :mod:`kernel_lifecycle` (importable
because the package ``conftest.py`` puts this ``tests`` directory on ``sys.path``),
so the subdivided test modules can share it without a package-relative import
across the hyphenated distribution directory.
"""

from __future__ import annotations

import pytest

from ugence_governance_provider_framework.registry import ProviderRegistry
from ugence_governance_provider_framework.reference import (
    DeterministicActionGovernanceProvider,
    DeterministicAssertionProvider,
    DeterministicExecutionProvider,
)


@pytest.fixture
def registry():
    reg = ProviderRegistry()
    reg.register(DeterministicAssertionProvider().descriptor())
    reg.register(DeterministicActionGovernanceProvider().descriptor())
    reg.register(DeterministicExecutionProvider().descriptor())
    return reg
