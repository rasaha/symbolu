"""Shared fixtures for provider-framework tests."""
from __future__ import annotations

import pytest

from decision_governance_provider import ProviderDescriptor, ProviderRegistry
from decision_governance_provider.mock import (
    MockAssertionProvider,
    MockAuthorizationProvider,
    MockExecutionProvider,
)


def descriptor_for(provider, *, default=True):
    return ProviderDescriptor(provider.metadata(), provider.capabilities(),
                              (lambda: provider), default=default)


@pytest.fixture
def registry():
    reg = ProviderRegistry()
    for p in (MockAssertionProvider(), MockAuthorizationProvider(), MockExecutionProvider()):
        reg.register(descriptor_for(p))
    return reg
