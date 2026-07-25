"""Registry: registration, discovery, capability lookup, validation, lifecycle."""
from __future__ import annotations

import pytest

from decision_governance_provider import (
    ProviderDescriptor, ProviderKind, ProviderRegistry)
from decision_governance_provider.errors import (
    IncompatibleProviderVersionError, ProviderConflictError, ProviderNotFoundError)
from decision_governance_provider.metadata import ProviderCapabilities, ProviderMetadata
from decision_governance_provider.mock import MockAssertionProvider

from .conftest import descriptor_for


def test_register_and_discover(registry):
    assert set(registry.names) == {"mock-assertion", "mock-authorization", "mock-execution"}
    assert registry.list_descriptors(ProviderKind.ASSERTION)[0].name == "mock-assertion"


def test_duplicate_registration_conflicts(registry):
    dup = descriptor_for(MockAssertionProvider())  # same name "mock-assertion"
    with pytest.raises(ProviderConflictError):
        registry.register(dup)


def test_unknown_lookup_raises(registry):
    with pytest.raises(ProviderNotFoundError):
        registry.get_descriptor("nope")


def test_capability_lookup(registry):
    found = registry.find_by_capability(ProviderKind.EXECUTION, "dispatch")
    assert [d.name for d in found] == ["mock-execution"]
    assert registry.find_by_capability(ProviderKind.EXECUTION, "nonexistent") == ()


def test_default_for_single(registry):
    assert registry.default_for(ProviderKind.ASSERTION).name == "mock-assertion"


def test_default_for_ambiguous_raises():
    reg = ProviderRegistry()
    reg.register(descriptor_for(MockAssertionProvider(name="a"), default=True))
    reg.register(descriptor_for(MockAssertionProvider(name="b"), default=True))
    from decision_governance_provider.errors import ProviderError
    with pytest.raises(ProviderError):
        reg.default_for(ProviderKind.ASSERTION)


def test_incompatible_version_rejected():
    reg = ProviderRegistry()
    bad = ProviderDescriptor(
        ProviderMetadata(name="bad", version="0.1.0", kind=ProviderKind.ASSERTION,
                         kernel_port_version="99.0.0"),
        ProviderCapabilities(kind=ProviderKind.ASSERTION), factory=lambda: None)
    with pytest.raises(IncompatibleProviderVersionError):
        reg.register(bad)


def test_kind_mismatch_rejected():
    from decision_governance_provider.errors import ProviderError
    reg = ProviderRegistry()
    bad = ProviderDescriptor(
        ProviderMetadata(name="x", version="0.1.0", kind=ProviderKind.ASSERTION,
                         kernel_port_version="1.0.0"),
        ProviderCapabilities(kind=ProviderKind.EXECUTION), factory=lambda: None)
    with pytest.raises(ProviderError):
        reg.register(bad)


def test_lifecycle_start_stop(registry):
    p = registry.get_provider("mock-assertion")
    assert p.health().healthy
    registry.unregister("mock-assertion")
    with pytest.raises(ProviderNotFoundError):
        registry.get_descriptor("mock-assertion")
