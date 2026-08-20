"""D-5B0B-1: a historical resolution can never back an authorization.

The Policy Authority can legitimately return ``RESOLVED`` with ``historical=True`` — under
an explicitly selected non-default rule, for an ``as_of`` strictly before a verified
revocation. That answer describes the past, and its own type already says so:
``implies_current_validity`` is ``False`` for every historical answer.

Two properties are pinned here. The shipped production port cannot produce such an answer
at all, because it pins the fail-closed rule. And even when a port does produce one, the
verifier refuses it at admission rather than carrying it forward labelled — which is the
ruling, and is what stops the distinction from being pushed onto every downstream consumer.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from _policy_fixtures import ONE_SECOND, T_MID, T_TO, issued, port_for, revoke, verifier_for
from ugence_policy_authority.api import HistoricalResolutionRule, resolve_policy

from ugence_cloud_scaling_policy_authenticity import (
    REQUIRED_HISTORICAL_RESOLUTION_RULE,
    PolicyAuthenticityOutcome as O,
    PolicyAuthenticityVerifier,
)


@dataclass
class HistoricalAllowingPort:
    """A port wired against the authority's non-default historical rule.

    Not shipped, and deliberately not constructible from this package's API: the production
    port does not expose the knob. It exists here so the refusal is measured against a real
    historical resolution rather than a hand-built one.
    """

    authority: object

    @property
    def trust_configuration_digest(self) -> str:
        return port_for(self.authority).trust_configuration_digest

    is_production_authoritative: bool = False

    def resolve_policy_version(self, *, coordinate, expected_reference_tenant_id, as_of):
        return resolve_policy(
            reference=coordinate,
            expected_reference_tenant_id=expected_reference_tenant_id,
            as_of=as_of,
            registry=self.authority.registry,
            signature_verifier=self.authority.key_ring,
            adapters=self.authority.adapters,
            historical_resolution=HistoricalResolutionRule.ALLOW_BEFORE_REVOCATION,
        )


@pytest.mark.invariant
def test_the_production_port_pins_the_fail_closed_historical_rule():
    assert REQUIRED_HISTORICAL_RESOLUTION_RULE is HistoricalResolutionRule.DENY_ALWAYS
    # And the knob is genuinely absent from the port's constructor, not merely defaulted.
    import inspect

    from ugence_cloud_scaling_policy_authenticity import PolicyAuthorityResolutionPort

    parameters = inspect.signature(PolicyAuthorityResolutionPort.__init__).parameters
    assert "historical_resolution" not in parameters


@pytest.mark.adversarial
def test_a_genuine_historical_resolution_is_refused_at_admission():
    authority, record = issued()
    revoked_at = T_TO - ONE_SECOND
    revoke(authority, record, revoked_at=revoked_at)

    port = HistoricalAllowingPort(authority=authority)
    # The authority really does resolve it, historically, at an instant before revocation.
    answer = port.resolve_policy_version(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    )
    assert answer.resolved is True
    assert answer.historical is True
    assert answer.implies_current_validity is False

    # And this boundary refuses it anyway.
    result = PolicyAuthenticityVerifier(resolution_port=port).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    )
    assert result.outcome is O.HISTORICAL_RESOLUTION_REFUSED
    assert result.verified_policy is None


@pytest.mark.adversarial
def test_the_same_port_still_refuses_at_and_after_the_revocation_instant():
    authority, record = issued()
    revoked_at = T_TO - ONE_SECOND
    revoke(authority, record, revoked_at=revoked_at)
    verifier = PolicyAuthenticityVerifier(resolution_port=HistoricalAllowingPort(authority))
    assert (
        verifier.verify(
            coordinate=record.coordinate,
            expected_reference_tenant_id=record.coordinate.tenant_id,
            as_of=revoked_at,
        ).outcome
        is O.REVOKED
    )


@pytest.mark.invariant
def test_no_verified_artifact_can_report_itself_as_historical():
    authority, record = issued()
    verified = verifier_for(authority).verify(
        coordinate=record.coordinate,
        expected_reference_tenant_id=record.coordinate.tenant_id,
        as_of=T_MID,
    ).verified_policy

    assert verified.historical is False
    assert verified.implies_current_validity is True
    # A derived property, so the usual frozen-dataclass bypass cannot set it.
    with pytest.raises(AttributeError):
        object.__setattr__(verified, "historical", True)
