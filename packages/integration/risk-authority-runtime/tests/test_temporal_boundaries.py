"""Temporal-boundary conformance for the verified production path.

The ratified rule is one half-open window everywhere: authority begins at ``not_before``
and ends immediately upon reaching ``expires_at``. This file proves the RA-4.5 share of
it — that ``verify_and_bind`` refuses at exactly ``expires_at``, names the refusal, and
therefore never lets ``compose_verified`` mint a GRANT whose effective ``expires_at``
equals the evaluation instant.

That last property is the one the boundary ruling actually turned on. Before it, at
``now == envelope.expires_at`` this path produced an ALLOW whose effective window was zero
microseconds wide, and every consumer downstream refused it anyway — the credential broker
on a zero-width credential window, ``governance_contracts.Validity`` by being unable to
construct ``issued_at == expires_at`` at all. The envelope was the last artifact still
saying yes at an instant nothing could act on.

The proof is behavioral, not a source-text match: equivalent correct code can spell the
comparison many ways, and a substring assertion would fail on a correct refactor while
passing on any rewrite that kept the string.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from risk_authority.integrations.actiongate import ReferenceActionGate

from ugence_risk_authority_runtime import RiskAuthorityCompositionEngine, verify_and_bind
from ugence_risk_authority_runtime.contracts import (
    GovernanceVetoResult,
    RiskAuthorityDisposition,
    VetoDisposition,
)

#: The smallest instant a ``datetime`` can represent — the exact width of the window the
#: superseded inclusive reading left open.
EPS = timedelta(microseconds=1)

DA_NO_VETO = GovernanceVetoResult(
    source="decision_authority", disposition=VetoDisposition.NO_VETO)
AG_NO_VETO = GovernanceVetoResult(
    source="actiongate", disposition=VetoDisposition.NO_VETO)


def _bind_at(ra, now):
    """Run the whole verified path at ``now`` and return the bound result."""

    action = ra.action()
    authorization = ReferenceActionGate().authorize(
        authorization_id="auth_boundary",
        envelope=ra.envelope,
        action=action,
        identity=ra.identity(),
        key_ring=ra.key_ring,
        revocation_state=ra.revocation,
        now=ra.now,  # the gate's own instant is not what is under test here
    )
    return verify_and_bind(
        envelope=ra.envelope,
        authorization=authorization,
        action=action,
        identity=ra.identity(),
        key_ring=ra.key_ring,
        revocation_state=ra.revocation,
        now=now,
        production=True,
    )


@pytest.mark.parametrize(
    "offset,allowed,label",
    [
        (-EPS, False, "before-not_before"),
        (None, True, "at-not_before-INCLUSIVE"),
        ("expiry-eps", True, "just-before-expiry"),
        ("expiry", False, "at-expires_at-EXCLUSIVE"),
        ("expiry+eps", False, "after-expiry"),
    ],
)
def test_verified_path_is_half_open_at_every_boundary_instant(ra, offset, allowed, label):
    """All five instants, through the real verified production path."""

    if offset is None:
        now = ra.envelope.not_before
    elif offset == "expiry-eps":
        now = ra.envelope.expires_at - EPS
    elif offset == "expiry":
        now = ra.envelope.expires_at
    elif offset == "expiry+eps":
        now = ra.envelope.expires_at + EPS
    else:
        now = ra.envelope.not_before + offset

    verified = _bind_at(ra, now)
    is_allow = verified.result.disposition is RiskAuthorityDisposition.ALLOW

    assert is_allow is allowed, (
        f"{label}: expected allow={allowed} at {now.isoformat()} for window "
        f"[{ra.envelope.not_before.isoformat()}, {ra.envelope.expires_at.isoformat()})")


def test_exact_expiry_names_itself_rather_than_generic_invalidity(ra):
    """At equality the outcome is the stable typed *expired* one.

    Both the predicate and the canonical verifier now refuse at this instant, so which
    reason a caller sees depends on which check runs first. The verified path asks the
    temporal question up front precisely so the answer is stable: RA_EXPIRED, not a
    generic RA_ENVELOPE_INVALID that happens to carry an expiry string.
    """

    verified = _bind_at(ra, ra.envelope.expires_at)

    assert verified.result.disposition is RiskAuthorityDisposition.DENY
    assert "RA_EXPIRED" in verified.result.reason_codes, verified.result.reason_codes
    assert "RA_ENVELOPE_INVALID" not in verified.result.reason_codes, (
        "exact expiry must name expiry, not generic envelope invalidity")
    assert any("expires_at)" in r for r in verified.result.raw_reason_codes), (
        verified.result.raw_reason_codes)


def test_no_grant_is_ever_minted_with_a_zero_width_effective_window(ra):
    """The property the ruling turned on, asserted end to end.

    A microsecond earlier composition grants; at equality it must not — and the effective
    window of any decision it does grant must be strictly wider than zero.
    """

    engine = RiskAuthorityCompositionEngine()

    granted = engine.compose_verified(
        risk_authority=_bind_at(ra, ra.envelope.expires_at - EPS),
        decision_authority=DA_NO_VETO,
        actiongate=AG_NO_VETO,
    )
    assert granted.executable, "a microsecond before expiry must still grant"
    effective_expiry = granted.effective_constraints.expires_at
    if effective_expiry is not None:
        assert effective_expiry > ra.envelope.expires_at - EPS, (
            "a granted decision's effective window must be strictly wider than zero")

    at_expiry = engine.compose_verified(
        risk_authority=_bind_at(ra, ra.envelope.expires_at),
        decision_authority=DA_NO_VETO,
        actiongate=AG_NO_VETO,
    )
    assert not at_expiry.executable, (
        "at exactly expires_at composition must not produce an executable decision")
