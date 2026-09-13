"""Temporal-boundary conformance: the envelope window is half-open here too.

One rule across every artifact: authority begins at ``not_before`` and ends immediately
upon reaching ``expires_at`` — ``[not_before, expires_at)``.

This seam is where the inconsistency that retired the old inclusive reading was visible.
At ``now == envelope.expires_at`` the envelope check used to pass, and the seam refused two
steps later with ``WINDOW_INVALID``, because ``not_after`` came out equal to ``issued_at``
and no credential validity remained. Fail-closed, but naming the wrong cause: the envelope
had expired, and the refusal said the credential window was malformed.

Two things make these tests less obvious than they look, and both are properties of the
fixture rather than of the rule:

* ``ActionAuthorization.expires_at`` is copied verbatim from the envelope at admission, so
  the two bounds coincide and the authorization check — which runs first — is what fires.
  Isolating the envelope comparison therefore needs an authorization that outlives it.
* the reservation lease (600s) expires well before the envelope (30min), so an instant
  just short of envelope expiry is past the lease. Isolating the envelope bound needs a
  longer lease too.

``_envelope_bound_world`` arranges both, so the envelope really is the binding constraint
and a mutation to its comparison actually changes an outcome here.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from _broker_fixtures import (
    BROKER_INSTANT,
    RESERVATION_INSTANT,
    materialization_request,
    reserve,
)

from ugence_cloud_scaling_credential_broker import CredentialRefusal as R

#: The smallest representable instant — the exact width of the window the superseded
#: inclusive reading left open.
EPS = timedelta(microseconds=1)

#: Any expiry refusal attributable to elapsed time, as opposed to a malformed window.
EXPIRY_REFUSALS = (R.AUTHORIZATION_EXPIRED, R.ENVELOPE_EXPIRED, R.LEASE_EXPIRED)


def _materialize_at(world, now):
    world.clock.at = now
    world.clock.reads = 0
    return world.seam().materialize(materialization_request(world))


def _envelope_bound_world(world):
    """Make the envelope the binding temporal constraint, not the authorization or lease.

    Extends the stored authorization and re-reserves with a lease long enough to outlive
    the envelope. Nothing about the envelope itself is touched — it stays the real signed
    artifact, with its real window.
    """

    beyond = world.envelope.expires_at + timedelta(hours=1)

    store = world.app.authorizations
    key = (world.authorization.tenant_id, world.authorization.authorization_id)
    extended = replace(world.authorization, expires_at=beyond)
    store._authorizations[key] = extended

    world.reservations._receipts.clear()
    world.reservations._reservations.clear()
    world.reservation = reserve(
        world.reservations,
        extended,
        world.action,
        world.target_scope,
        as_of=RESERVATION_INSTANT,
        ttl_s=int((beyond - RESERVATION_INSTANT).total_seconds()) + 60,
    )
    world.authorization = extended
    return world


def test_the_baseline_instant_still_materializes(world):
    """A control: the fixture's own instant is comfortably inside every window."""

    out = _materialize_at(world, BROKER_INSTANT)

    assert out.materialized, (out.refusal, out.detail)


def test_a_grant_still_materializes_just_before_the_envelope_expires(world):
    """The other half of the boundary: one microsecond earlier must still work.

    Without this, moving the boundary arbitrarily far earlier would also pass and the
    suite would only prove that *something* refuses eventually.
    """

    bound = _envelope_bound_world(world)
    out = _materialize_at(bound, bound.envelope.expires_at - EPS)

    assert out.materialized, (out.refusal, out.detail)


def test_exact_envelope_expiry_refuses_and_names_the_envelope(world):
    """At equality: refused, and attributed to the envelope rather than the window."""

    bound = _envelope_bound_world(world)
    out = _materialize_at(bound, bound.envelope.expires_at)

    assert not out.materialized
    assert out.refusal is R.ENVELOPE_EXPIRED, (out.refusal, out.detail)


def test_after_expiry_refuses_the_same_way(world):
    """Past the boundary the outcome is unchanged — no third behavior at the edge."""

    bound = _envelope_bound_world(world)
    out = _materialize_at(bound, bound.envelope.expires_at + EPS)

    assert not out.materialized
    assert out.refusal is R.ENVELOPE_EXPIRED, (out.refusal, out.detail)


def test_the_authorization_never_outlives_the_envelope_it_derives_from(world):
    """``ActionAuthorization.expires_at`` is the envelope's, so it must expire with it.

    On the unmodified fixture the two bounds coincide. An inclusive test on the
    authorization would let the derived artifact stay valid for one instant after the
    envelope it was derived from had expired.
    """

    assert world.authorization.expires_at == world.envelope.expires_at, (
        "fixture assumption: admission copies the envelope's expiry onto the authorization")

    out = _materialize_at(world, world.authorization.expires_at)

    assert not out.materialized
    assert out.refusal in EXPIRY_REFUSALS, (out.refusal, out.detail)


def test_the_seam_never_derives_a_zero_width_credential_window(world):
    """The invariant behind the ruling, stated directly.

    ``not_after`` is ``min(authorization, lease, envelope, now + cap)``. If any of those
    bounds were inclusive, the minimum could equal ``issued_at`` and the seam would be
    asked to mint a credential valid for no time at all. It must refuse, by name, before
    reaching that point — ``WINDOW_INVALID`` here would mean the expiry that caused it went
    unnamed.
    """

    bound = _envelope_bound_world(world)

    for now in (bound.envelope.expires_at, bound.envelope.expires_at + EPS):
        out = _materialize_at(bound, now)
        assert not out.materialized, (
            f"at {now.isoformat()} the seam produced a grant on a zero-width window")
        assert out.refusal is not R.WINDOW_INVALID, (
            "WINDOW_INVALID means the seam got as far as deriving a zero-width credential "
            "window; the expiry that caused it should have been named first")
