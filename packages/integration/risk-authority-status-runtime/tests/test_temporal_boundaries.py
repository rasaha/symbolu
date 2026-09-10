"""Temporal-boundary conformance for the RA-6 lifecycle reaper.

One rule across every artifact: authority begins at ``not_before`` and ends immediately
upon reaching ``expires_at`` — ``[not_before, expires_at)``.

This package reflects that rule rather than deciding it: the reaper's job is to make the
recorded case state agree with the envelope's window. So the property under test is
agreement, not an independent opinion. If the envelope is expired at an instant, a case
still recorded ACTIVE at that instant is a stale record — and previously, at exactly
``expires_at``, it stayed ACTIVE.

The proof is behavioral rather than a source-text match, because the same comparison can
be spelled many correct ways and a substring assertion would fail on a correct refactor
while passing on any rewrite that kept the string.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from risk_authority.domain import RequestedCapabilities, RiskCaseState, RiskDecisionCase
from risk_authority.services.revocation import RevocationState

from ugence_risk_authority_status_runtime.case_lifecycle import (
    expire_case_if_elapsed,
    reconcile_case_state,
)

import ra6_scenario as C

#: The smallest representable instant — the exact width of the window the superseded
#: inclusive reading left open.
EPS = timedelta(microseconds=1)

NOW = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)


def _active_case() -> RiskDecisionCase:
    return RiskDecisionCase(
        case_id="rdc_boundary", tenant_id="t", subject_id="a", model_id="m",
        purpose="p", domain="d", jurisdictions=("US",),
        requested=RequestedCapabilities(), workflow_ir_id="w",
        workflow_ir_version="1", workflow_ir_digest="dg", created_at=NOW,
        state=RiskCaseState.ACTIVE,
    )


def test_the_reaper_expires_a_case_at_exactly_expires_at():
    """Equality is expiry, not the last valid instant."""

    case = _active_case()
    event = expire_case_if_elapsed(case, expires_at=NOW, now=NOW)

    assert case.state is RiskCaseState.EXPIRED
    assert event is not None


def test_the_reaper_leaves_a_case_active_one_instant_earlier():
    """The other half: a microsecond before expiry the case is still ACTIVE.

    Without this, a reaper that expired everything unconditionally would also pass.
    """

    case = _active_case()
    event = expire_case_if_elapsed(case, expires_at=NOW, now=NOW - EPS)

    assert case.state is RiskCaseState.ACTIVE
    assert event is None


def test_reconciliation_agrees_with_the_envelope_at_every_boundary_instant():
    """The property that matters: the record never claims ACTIVE past the window.

    Asserted against ``is_temporally_valid`` itself rather than a restated rule, so the
    two cannot drift apart without this failing.
    """

    harness = C.build()
    envelope = harness.envelope

    for now in (
        envelope.expires_at - EPS,
        envelope.expires_at,
        envelope.expires_at + EPS,
    ):
        case = _active_case()
        reconcile_case_state(
            case, envelope=envelope, revocation_state=RevocationState(), now=now
        )
        envelope_valid = envelope.is_temporally_valid(now)
        case_active = case.state is RiskCaseState.ACTIVE

        assert case_active is envelope_valid, (
            f"at {now.isoformat()} the envelope is "
            f"{'valid' if envelope_valid else 'expired'} but the case is "
            f"{case.state.name}; the reaper must reflect the envelope window, not its own")


def test_expiry_still_precedes_revocation_at_the_boundary():
    """Precedence is unchanged by the boundary move: expiry wins at equality too."""

    harness = C.build()
    revocation = RevocationState()
    revocation.revoke_envelope(harness.envelope.envelope_id)

    case = _active_case()
    reconcile_case_state(
        case, envelope=harness.envelope, revocation_state=revocation,
        now=harness.envelope.expires_at,
    )

    assert case.state is RiskCaseState.EXPIRED
