"""Temporal-boundary conformance: one half-open rule, proved behaviorally.

Authority begins at ``not_before`` and ends immediately upon reaching ``expires_at``.
Every artifact that carries a validity window uses an **inclusive lower bound and an
exclusive upper bound** — ``[not_before, expires_at)``.

This supersedes the earlier reading in which the envelope alone was inclusive at both
ends. What retired it: the absence of chained envelope windows explained why an inclusive
upper bound caused no *overlap*, but never why a security validity artifact should stay
usable at its own stated expiry — and every usable downstream authorization already
refused there anyway.

Why this file exists rather than a source-text assertion
--------------------------------------------------------
The rule used to be pinned by asserting that a specific comparison string appeared in
``is_temporally_valid``'s source. That is not proof: equivalent correct code can be
written many ways (``not (now >= expires_at)``, an extracted predicate, a ``<`` with
reordered operands), and the assertion would fail on a correct refactor while passing on
any rewrite that kept the substring. It also said nothing at all about the four other
sites that decide the same question.

So the normative proof here is behavioral: one oracle, five boundary instants, applied to
every site. A source-text tripwire may still exist elsewhere as supplementary drift
detection, but it is not what establishes the rule.

The sites in this package are the envelope predicate, the canonical verifier, and decision
expiry at both issuance paths. The other two sites are proved in their own packages, which
this one may not import:

* ``risk-authority-runtime`` — ``tests/test_temporal_boundaries.py``
* ``cloud-scaling-credential-broker`` — ``tests/test_temporal_boundaries.py``
* ``risk-authority-status-runtime`` — ``tests/test_temporal_boundaries.py``
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from risk_authority.crypto.keys import KeyRing, SigningKeyRecord
from risk_authority.crypto.signing import SigningKey
from risk_authority.domain.envelope import RiskAuthorizationEnvelope
from risk_authority.domain.errors import RiskAuthorityError
from risk_authority.services.envelope_verifier import EnvelopeVerifier

from ..scenario import KEY_ID, approved_envelope, build_application

#: The smallest instant a ``datetime`` can represent. The boundary "overlap" the inclusive
#: reading opened was exactly this wide — a microsecond, not a second.
EPS = timedelta(microseconds=1)


@pytest.fixture(scope="module")
def envelope() -> RiskAuthorizationEnvelope:
    app = build_application()
    _evaluation, _decision, env = approved_envelope(app)
    return env


@pytest.fixture(scope="module")
def key_ring() -> KeyRing:
    return KeyRing.from_records(
        [SigningKeyRecord(KEY_ID, SigningKey.from_seed(bytes(range(32))))]
    )


# --------------------------------------------------------------- site 1: the predicate
def test_envelope_predicate_is_half_open(envelope):
    """``domain/envelope.py`` — ``[not_before, expires_at)`` at all five instants."""

    for now, expected in (
        (envelope.not_before - EPS, False),
        (envelope.not_before, True),
        (envelope.expires_at - EPS, True),
        (envelope.expires_at, False),
        (envelope.expires_at + EPS, False),
    ):
        assert envelope.is_temporally_valid(now) is expected, (
            f"is_temporally_valid({now.isoformat()}) should be {expected}; the window is "
            f"[{envelope.not_before.isoformat()}, {envelope.expires_at.isoformat()})")


# ----------------------------------------------------------------- site 2: the verifier
def test_verifier_agrees_with_the_predicate_at_every_instant(envelope, key_ring):
    """``services/envelope_verifier.py`` — the same window, reached independently.

    The verifier reimplements the comparison rather than calling the predicate, so the two
    can drift. This asserts they do not, at exactly the instants where drift would show.
    """

    app = build_application()
    verifier = EnvelopeVerifier()

    for now in (
        envelope.not_before - EPS,
        envelope.not_before,
        envelope.expires_at - EPS,
        envelope.expires_at,
        envelope.expires_at + EPS,
    ):
        verification = verifier.verify(
            envelope=envelope,
            key_ring=key_ring,
            revocation_state=app.revocation,
            now=now,
        )
        temporal_reasons = [
            r for r in verification.reasons if "(exp)" in r or "(nbf)" in r
        ]
        assert bool(temporal_reasons) is not envelope.is_temporally_valid(now), (
            f"verifier and predicate disagree at {now.isoformat()}: predicate says "
            f"valid={envelope.is_temporally_valid(now)}, verifier reasons="
            f"{temporal_reasons}")


def test_verifier_names_expiry_at_exactly_expires_at(envelope, key_ring):
    """The boundary instant refuses, and says *why* — not a generic invalidity."""

    app = build_application()
    verification = EnvelopeVerifier().verify(
        envelope=envelope,
        key_ring=key_ring,
        revocation_state=app.revocation,
        now=envelope.expires_at,
    )

    assert not verification.valid
    assert any("expired (exp)" in r for r in verification.reasons), verification.reasons


# ------------------------------------------------------------- sites 3+4: decision expiry
def _issue_at(app, decision, now: datetime):
    """Drive the real issuer at ``now``. Raises ``RiskAuthorityError`` when it refuses."""

    from ..scenario import ACTOR, MODEL

    return app._issuer_service.issue(
        envelope_id=f"env_boundary_{now.isoformat()}",
        decision=decision,
        audience="finance-agent-runtime",
        subject=ACTOR,
        model_id=MODEL,
        session_id="sess_boundary",
        nonce=f"nonce_{now.isoformat()}",
        key_record=app._key_record,
        revocation_state=app.revocation,
        now=now,
    )


def test_issuer_refuses_a_decision_at_exactly_its_expiry():
    """``services/envelope_issuer.py`` — DECISION expiry is half-open too.

    One microsecond earlier the issuer mints an envelope; at equality it refuses. Both
    halves are asserted, so the test fails if the boundary moves in either direction.
    """

    app = build_application()
    _evaluation, decision, _env = approved_envelope(app, case_id="rdc_expiry_issuer")
    expiry = decision.expires_at
    if expiry is None:  # pragma: no cover - the reference decision always carries one
        pytest.skip("reference decision carries no expiry")

    minted = _issue_at(app, decision, expiry - EPS)
    assert minted.decision_id == decision.decision_id, (
        "a microsecond before expiry the decision must still mint an envelope; if this "
        "fails the boundary moved too far, not just off equality")

    with pytest.raises(RiskAuthorityError, match="expired"):
        _issue_at(app, decision, expiry)


def test_issuance_seam_names_decision_expired_rather_than_an_invalid_ttl():
    """``api/envelope_issuance_seam.py`` — the stated rule, not the arithmetic accident.

    At exactly ``decision.expires_at`` this used to pass the DECISION_EXPIRED check and
    then fail two steps later, when ``ttl = min(ttl, expires_at - now)`` came out zero.
    The refusal reason happened to be right; the path to it was not. Now the named check
    fires, so the code refuses for the reason it claims to.
    """

    app = build_application()
    _evaluation, decision, _env = approved_envelope(app, case_id="rdc_expiry_seam")
    expiry = decision.expires_at
    if expiry is None:  # pragma: no cover
        pytest.skip("reference decision carries no expiry")

    # A generous TTL, so a zero-width window can only come from the decision bound. If the
    # named check were removed, this would still refuse — but via TTL_INVALID, and this
    # assertion on the reason is what tells the two paths apart.
    with pytest.raises(RiskAuthorityError, match="expired"):
        app._issuer_service.issue(
            envelope_id="env_seam_boundary",
            decision=decision,
            audience="finance-agent-runtime",
            subject=_actor(),
            model_id=_model(),
            session_id="sess_seam",
            nonce="nonce_seam",
            key_record=app._key_record,
            revocation_state=app.revocation,
            now=expiry,
            ttl=timedelta(hours=12),
        )


def _actor() -> str:
    from ..scenario import ACTOR

    return ACTOR


def _model() -> str:
    from ..scenario import MODEL

    return MODEL


# ------------------------------------------------------------------- the negative control
def test_an_inclusive_upper_bound_fails_this_suite():
    """The control: flip the upper bound back to ``<=`` and the oracle must reject it.

    Ruling 5 requires proof that this suite can fail. Without it, a conformance test that
    accepts both conventions is indistinguishable from one that accepts neither — it would
    pass whatever the code did.

    The two candidate implementations differ at exactly one instant, which is the whole
    point of the ruling, so the control targets that instant specifically.
    """

    not_before = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)
    expires_at = not_before + timedelta(minutes=30)

    def half_open(now: datetime) -> bool:
        return not_before <= now < expires_at

    def inclusive(now: datetime) -> bool:  # the superseded rule
        return not_before <= now <= expires_at

    def oracle(predicate) -> bool:
        """True iff ``predicate`` implements the ratified half-open window."""

        return all(
            predicate(now) is expected
            for now, expected in (
                (not_before - EPS, False),
                (not_before, True),
                (expires_at - EPS, True),
                (expires_at, False),
                (expires_at + EPS, False),
            )
        )

    assert oracle(half_open), "the ratified rule must satisfy its own oracle"
    assert not oracle(inclusive), (
        "the oracle accepted the superseded inclusive rule — it cannot distinguish the "
        "two conventions and therefore proves nothing")
    # And the two agree everywhere except the one instant under ruling.
    assert half_open(expires_at) is not inclusive(expires_at)
    assert all(
        half_open(t) is inclusive(t)
        for t in (not_before - EPS, not_before, expires_at - EPS, expires_at + EPS)
    )
