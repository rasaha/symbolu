"""Resolution: default / named / capability / deterministic, config-driven."""
from __future__ import annotations

import pytest

from decision_governance_provider import (
    ProviderConfiguration, ProviderKind, ProviderSelection,
    resolve_configuration, resolve_provider)
from decision_governance_provider.errors import (
    ProviderNotFoundError, ProviderResolutionError)


def test_default_resolution(registry):
    p = resolve_provider(registry, ProviderSelection(ProviderKind.AUTHORIZATION))
    assert p.metadata().name == "mock-authorization"


def test_named_resolution(registry):
    p = resolve_provider(registry, ProviderSelection(ProviderKind.EXECUTION, name="mock-execution"))
    assert p.metadata().name == "mock-execution"


def test_named_resolution_missing(registry):
    with pytest.raises(ProviderNotFoundError):
        resolve_provider(registry, ProviderSelection(ProviderKind.EXECUTION, name="ghost"))


def test_capability_resolution(registry):
    p = resolve_provider(registry, ProviderSelection(ProviderKind.AUTHORIZATION, capability="constraints"))
    assert p.metadata().name == "mock-authorization"


def test_capability_resolution_unmatched(registry):
    with pytest.raises(ProviderResolutionError):
        resolve_provider(registry, ProviderSelection(ProviderKind.ASSERTION, capability="telepathy"))


def test_deterministic_only(registry):
    # all mocks are deterministic → resolves
    p = resolve_provider(registry, ProviderSelection(ProviderKind.EXECUTION, deterministic_only=True))
    assert p.capabilities().deterministic


def test_resolve_configuration(registry):
    config = ProviderConfiguration(tuple(ProviderSelection(k) for k in ProviderKind))
    resolved = resolve_configuration(registry, config)
    assert set(resolved) == set(ProviderKind)
