"""What a composition root may and may not wire, checked at construction rather than at use."""

from __future__ import annotations

import pytest

from _policy_fixtures import ForeignTypePort, RaisingPort, make_authority, port_for
from ugence_policy_authority.api import AdapterRegistry, InMemoryPolicyRegistry, PolicyKeyRing

from ugence_cloud_scaling_policy_authenticity import (
    REFERENCE_GRADE_REGISTRIES,
    DenyAllPolicyResolutionPort,
    PolicyAuthenticityConfigurationError,
    PolicyAuthenticityVerifier,
    PolicyAuthorityResolutionPort,
    require_production_resolution_port,
)


@pytest.mark.adversarial
def test_a_verifier_requires_a_port_there_is_no_default():
    with pytest.raises(PolicyAuthenticityConfigurationError):
        PolicyAuthenticityVerifier(resolution_port=None)


@pytest.mark.adversarial
def test_a_port_that_cannot_name_its_trust_configuration_is_refused():
    class Nameless:
        def resolve_policy_version(self, **kwargs):  # pragma: no cover - never reached
            raise AssertionError("must not be reached")

    with pytest.raises(PolicyAuthenticityConfigurationError):
        PolicyAuthenticityVerifier(resolution_port=Nameless())


@pytest.mark.adversarial
def test_an_object_that_is_not_a_port_at_all_is_refused():
    with pytest.raises(PolicyAuthenticityConfigurationError):
        PolicyAuthenticityVerifier(resolution_port=object())


@pytest.mark.adversarial
def test_the_reference_grade_in_memory_registry_cannot_reach_a_production_determination():
    """The authority documents its in-memory registry as reference-grade, not persistence."""

    authority = make_authority()
    port = port_for(authority)
    assert isinstance(authority.registry, REFERENCE_GRADE_REGISTRIES)
    assert port.is_production_authoritative is False
    with pytest.raises(PolicyAuthenticityConfigurationError):
        PolicyAuthenticityVerifier(resolution_port=port, production_mode=True)


@pytest.mark.adversarial
@pytest.mark.parametrize("port", [RaisingPort(), ForeignTypePort()])
def test_a_port_that_has_not_opted_in_is_refused_in_production(port):
    with pytest.raises(PolicyAuthenticityConfigurationError):
        PolicyAuthenticityVerifier(resolution_port=port, production_mode=True)


@pytest.mark.happy
def test_the_deny_all_port_is_production_admissible_because_it_can_only_refuse():
    verifier = PolicyAuthenticityVerifier(
        resolution_port=DenyAllPolicyResolutionPort(), production_mode=True
    )
    assert verifier.production_mode is True
    assert require_production_resolution_port(DenyAllPolicyResolutionPort()) is not None


@pytest.mark.happy
def test_a_port_on_a_non_reference_registry_opts_in():
    """A registry the authority does not document as reference-grade satisfies the guard."""

    class DurableRegistry:
        def __init__(self):
            self._inner = InMemoryPolicyRegistry()

        def append_issuance(self, record):
            return self._inner.append_issuance(record)

        def get_issued(self, coordinate):
            return self._inner.get_issued(coordinate)

        def issued_records_for_identity(self, **kwargs):
            return self._inner.issued_records_for_identity(**kwargs)

        def append_revocation(self, record):
            return self._inner.append_revocation(record)

        def revocations_for(self, coordinate):
            return self._inner.revocations_for(coordinate)

    port = PolicyAuthorityResolutionPort(
        registry=DurableRegistry(),
        signature_verifier=PolicyKeyRing(),
        adapters=AdapterRegistry(),
    )
    assert port.is_production_authoritative is True
    assert PolicyAuthenticityVerifier(resolution_port=port, production_mode=True) is not None


@pytest.mark.adversarial
def test_a_verifier_cannot_have_its_port_swapped_after_construction():
    authority = make_authority()
    verifier = PolicyAuthenticityVerifier(resolution_port=port_for(authority))
    with pytest.raises(AttributeError):
        verifier._port = RaisingPort()
    with pytest.raises(AttributeError):
        del verifier._port


@pytest.mark.adversarial
def test_a_port_cannot_have_its_trust_store_swapped_after_construction():
    authority = make_authority()
    port = port_for(authority)
    with pytest.raises(AttributeError):
        port._signature_verifier = PolicyKeyRing()
    with pytest.raises(AttributeError):
        del port._registry


@pytest.mark.adversarial
def test_a_port_refuses_a_missing_registry_key_ring_or_adapter_registry():
    authority = make_authority()
    with pytest.raises(PolicyAuthenticityConfigurationError):
        PolicyAuthorityResolutionPort(
            registry=None, signature_verifier=authority.key_ring, adapters=authority.adapters
        )
    with pytest.raises(PolicyAuthenticityConfigurationError):
        PolicyAuthorityResolutionPort(
            registry=authority.registry, signature_verifier=None, adapters=authority.adapters
        )
    with pytest.raises(PolicyAuthenticityConfigurationError):
        PolicyAuthorityResolutionPort(
            registry=authority.registry,
            signature_verifier=authority.key_ring,
            adapters=[],
        )
