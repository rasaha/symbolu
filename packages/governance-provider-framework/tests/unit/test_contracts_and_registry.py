"""Distinct contracts + registry behavior."""
from __future__ import annotations

import pytest

from ugence_governance_provider_framework.contracts import (
    ActionGovernanceProvider, AssertionGovernanceProvider, ExternalExecutionProvider)
from ugence_governance_provider_framework.metadata import ProviderKind
from ugence_governance_provider_framework.errors import (
    ProviderCompatibilityError, ProviderRegistrationError, ProviderResolutionError)
from ugence_governance_provider_framework.registry import ProviderRegistry
from ugence_governance_provider_framework.metadata import (
    ProviderCapabilities, ProviderCompatibility, ProviderDescriptor)
from ugence_governance_provider_framework.reference import (
    DeterministicActionGovernanceProvider, DeterministicAssertionProvider)


def test_three_distinct_kinds():
    assert {k.value for k in ProviderKind} == {
        "ASSERTION_GOVERNANCE", "ACTION_GOVERNANCE", "EXTERNAL_EXECUTION"}


def test_contracts_are_distinct_protocols():
    assert len({AssertionGovernanceProvider, ActionGovernanceProvider,
                ExternalExecutionProvider}) == 3
    # an assertion provider is NOT an action or execution provider
    a = DeterministicAssertionProvider()
    assert isinstance(a, AssertionGovernanceProvider)
    assert not isinstance(a, ActionGovernanceProvider)
    assert not isinstance(a, ExternalExecutionProvider)


def test_registry_discovery(registry):
    assert set(registry.ids) == {
        "deterministic-assertion", "deterministic-action", "deterministic-execution"}
    assert registry.list_by_kind(ProviderKind.ACTION_GOVERNANCE)[0].provider_id == "deterministic-action"
    assert registry.find_by_capability(ProviderKind.ACTION_GOVERNANCE, "authorize")


def test_duplicate_registration_rejected(registry):
    with pytest.raises(ProviderRegistrationError):
        registry.register(DeterministicAssertionProvider().descriptor())


def test_incompatible_kernel_major_rejected():
    reg = ProviderRegistry()
    d = ProviderDescriptor(
        provider_id="bad", kind=ProviderKind.ACTION_GOVERNANCE, implementation_version="0.1.0",
        compatibility=ProviderCompatibility(contract_version="1.0.0",
                                            compatible_kernel_majors=frozenset({"2"})),
        capabilities=ProviderCapabilities(kind=ProviderKind.ACTION_GOVERNANCE), factory=lambda: None)
    with pytest.raises(ProviderCompatibilityError):
        reg.register(d)


def test_incompatible_contract_version_rejected():
    reg = ProviderRegistry()
    d = ProviderDescriptor(
        provider_id="bad", kind=ProviderKind.ACTION_GOVERNANCE, implementation_version="0.1.0",
        compatibility=ProviderCompatibility(contract_version="2.0.0"),
        capabilities=ProviderCapabilities(kind=ProviderKind.ACTION_GOVERNANCE), factory=lambda: None)
    with pytest.raises(ProviderCompatibilityError):
        reg.register(d)


def test_ambiguous_default_rejected():
    reg = ProviderRegistry()
    reg.register(DeterministicActionGovernanceProvider(provider_id="a", default=True).descriptor())
    with pytest.raises(ProviderRegistrationError):
        reg.register(DeterministicActionGovernanceProvider(provider_id="b", default=True).descriptor())


def test_deregister(registry):
    registry.deregister("deterministic-action")
    with pytest.raises(ProviderResolutionError):
        registry.get_descriptor("deterministic-action")
