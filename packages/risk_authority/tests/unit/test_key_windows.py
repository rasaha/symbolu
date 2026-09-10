"""Signing-key validity windows — issue #1398 (F-G item 2).

Before this, ``SigningKeyRecord.not_before`` / ``not_after`` were declared and read
nowhere: ``KeyRing.from_records`` dropped them, so no verification path could see a window
even in principle. These tests pin all four ratified rulings.

The interval is **half-open**, ``[not_before, not_after)``: valid at exactly
``not_before``, invalid at exactly ``not_after``. The envelope window now has the same
shape; the boundary conformance suite that proves it lives in
``tests/unit/test_temporal_boundaries.py``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from risk_authority.crypto.keys import (
    KeyRing,
    KeyWindowError,
    SigningKeyRecord,
    VerificationKeyRecord,
    key_window_valid_at,
)
from risk_authority.crypto.signing import SigningKey
from risk_authority.domain.errors import RiskAuthorityError
from risk_authority.services.envelope_signer import ReferenceEnvelopeSigner

T0 = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
HOUR = timedelta(hours=1)
KEY = SigningKey.from_seed(bytes(range(32)))


def _record(not_before=None, not_after=None) -> SigningKeyRecord:
    return SigningKeyRecord("k1", KEY, not_before=not_before, not_after=not_after)


# ------------------------------------------------------- ruling 1: absent = unbounded
def test_absent_bounds_are_unbounded_valid():
    """The compatibility guarantee: all 27 existing constructions omit the window."""

    record = _record()
    assert record.not_before is None and record.not_after is None
    for instant in (T0 - 10_000 * HOUR, T0, T0 + 10_000 * HOUR):
        assert record.is_valid_at(instant)


def test_lower_bound_only():
    record = _record(not_before=T0)
    assert not record.is_valid_at(T0 - HOUR)
    assert record.is_valid_at(T0 + 10_000 * HOUR)


def test_upper_bound_only():
    record = _record(not_after=T0)
    assert record.is_valid_at(T0 - 10_000 * HOUR)
    assert not record.is_valid_at(T0 + HOUR)


def test_a_valid_bounded_window():
    record = _record(not_before=T0, not_after=T0 + HOUR)
    assert not record.is_valid_at(T0 - timedelta(seconds=1))
    assert record.is_valid_at(T0 + timedelta(minutes=30))
    assert not record.is_valid_at(T0 + HOUR + timedelta(seconds=1))


# ------------------------------------------------------- ruling 1: malformed structure
@pytest.mark.parametrize("not_before,not_after", [
    (T0, T0),               # empty interval: no instant satisfies it
    (T0 + HOUR, T0),        # inverted
])
def test_a_malformed_window_is_refused_at_construction(not_before, not_after):
    """Fails closed *before* signing or verification, not silently always-invalid."""

    with pytest.raises(KeyWindowError):
        _record(not_before=not_before, not_after=not_after)
    with pytest.raises(KeyWindowError):
        VerificationKeyRecord(KEY.verify_key, not_before=not_before, not_after=not_after)


def test_a_non_datetime_bound_is_refused():
    with pytest.raises(KeyWindowError):
        _record(not_after="2026-06-01")


# ------------------------------------------------------- ruling 2: the exact boundaries
def test_exact_lower_boundary_is_valid():
    """At exactly ``not_before`` the key IS valid — the inclusive half."""

    assert _record(not_before=T0).is_valid_at(T0)
    assert key_window_valid_at(T0, not_before=T0, not_after=None)


def test_exact_upper_boundary_is_invalid():
    """At exactly ``not_after`` the key is NOT valid — the exclusive half.

    This is what makes two adjacent rotation windows non-overlapping at the instant they
    meet: a key valid until T and its successor valid from T are never both live.
    """

    assert not _record(not_after=T0).is_valid_at(T0)
    assert not key_window_valid_at(T0, not_before=None, not_after=T0)

    successor = _record(not_before=T0)
    predecessor = _record(not_after=T0)
    assert successor.is_valid_at(T0) and not predecessor.is_valid_at(T0)


def test_the_key_upper_bound_is_exclusive():
    """The one property this module owns: a key is invalid at exactly ``not_after``.

    The envelope now shares this shape. That agreement is proved behaviorally in
    ``test_temporal_boundaries.py`` across every site that decides it; this test is
    deliberately narrow and makes no claim about the envelope.
    """

    assert not key_window_valid_at(T0, not_before=None, not_after=T0)
    assert key_window_valid_at(T0, not_before=T0, not_after=None)


# ------------------------------------------------------- ruling 3: the window survives
def test_from_records_retains_the_window():
    """The actual defect: ``from_records`` used to discard both bounds."""

    ring = KeyRing.from_records([_record(not_before=T0, not_after=T0 + HOUR)])
    resolved = ring.resolve_record("k1")

    assert resolved is not None
    assert resolved.not_before == T0
    assert resolved.not_after == T0 + HOUR
    assert resolved.bounded is True


def test_a_bare_verify_key_ring_entry_stays_unbounded():
    """Compatibility: ``KeyRing({kid: verify_key})`` keeps working, unbounded."""

    ring = KeyRing({"k1": KEY.verify_key})
    record = ring.resolve_record("k1")
    assert record is not None and record.bounded is False
    assert record.is_valid_at(T0)
    # and the raw, non-validating accessor still returns the bare key
    assert ring.resolve("k1") == KEY.verify_key


def test_unknown_key_resolves_to_none_on_both_accessors():
    ring = KeyRing.from_records([_record()])
    assert ring.resolve("absent") is None
    assert ring.resolve_record("absent") is None


def test_with_key_can_attach_a_window():
    ring = KeyRing().with_key("k1", KEY.verify_key, not_before=T0, not_after=T0 + HOUR)
    assert ring.resolve_record("k1").not_after == T0 + HOUR


# ------------------------------------------------------- ruling 3: end-to-end enforcement
def test_an_out_of_window_key_cannot_sign():
    """Issuance-side enforcement, independent of any later verification."""

    from tests import scenario as S
    from risk_authority.services.envelope_issuer import EnvelopeIssuer

    app = S.build_application()
    _evaluation, decision, envelope = S.approved_envelope(app)

    # Re-issue the same decision under an expired key at the same trusted instant.
    expired = SigningKeyRecord(
        S.KEY_ID, SigningKey.from_seed(bytes(range(32))),
        not_after=S.FIXED_NOW - HOUR)

    with pytest.raises(RiskAuthorityError, match="validity window"):
        EnvelopeIssuer().issue(
            envelope_id="rae_expired_key",
            decision=decision,
            audience=envelope.audience,
            subject=envelope.subject,
            model_id=envelope.model_id,
            session_id=envelope.session_id,
            nonce="n2",
            key_record=expired,
            revocation_state=app.revocation,
            now=S.FIXED_NOW,
        )


def test_an_expired_key_cannot_verify_an_already_signed_envelope():
    """Verification-side enforcement — the half the window could not reach before."""

    from tests import scenario as S
    from risk_authority.services.envelope_verifier import EnvelopeVerifier

    app = S.build_application()
    _evaluation, decision, envelope = S.approved_envelope(app)
    verifier = EnvelopeVerifier()

    unbounded = KeyRing.from_records(
        [SigningKeyRecord(S.KEY_ID, SigningKey.from_seed(bytes(range(32))))])
    assert verifier.verify(
        envelope=envelope, key_ring=unbounded, revocation_state=app.revocation,
        now=S.FIXED_NOW).valid

    # Same envelope, same signature, same instant — only the key's window changed.
    expired = KeyRing.from_records([SigningKeyRecord(
        S.KEY_ID, SigningKey.from_seed(bytes(range(32))),
        not_after=S.FIXED_NOW - HOUR)])
    result = verifier.verify(
        envelope=envelope, key_ring=expired, revocation_state=app.revocation,
        now=S.FIXED_NOW)
    assert not result.valid
    assert any("validity window" in r for r in result.reasons)


def test_verification_checks_the_window_before_the_signature():
    """An out-of-window key is refused on its window, not on a signature mismatch."""

    from tests import scenario as S
    from dataclasses import replace
    from risk_authority.services.envelope_verifier import EnvelopeVerifier

    app = S.build_application()
    _evaluation, decision, envelope = S.approved_envelope(app)
    tampered = replace(envelope, signature=b"\x00" * 64)

    expired = KeyRing.from_records([SigningKeyRecord(
        S.KEY_ID, SigningKey.from_seed(bytes(range(32))),
        not_after=S.FIXED_NOW - HOUR)])
    result = EnvelopeVerifier().verify(
        envelope=tampered, key_ring=expired, revocation_state=app.revocation,
        now=S.FIXED_NOW)

    assert not result.valid
    assert any("validity window" in r for r in result.reasons)
    assert not any("invalid signature" in r for r in result.reasons)


def test_a_not_yet_valid_key_cannot_verify():
    from tests import scenario as S
    from risk_authority.services.envelope_verifier import EnvelopeVerifier

    app = S.build_application()
    _evaluation, decision, envelope = S.approved_envelope(app)
    future = KeyRing.from_records([SigningKeyRecord(
        S.KEY_ID, SigningKey.from_seed(bytes(range(32))),
        not_before=S.FIXED_NOW + HOUR)])

    result = EnvelopeVerifier().verify(
        envelope=envelope, key_ring=future, revocation_state=app.revocation,
        now=S.FIXED_NOW)
    assert not result.valid and any("validity window" in r for r in result.reasons)


def test_every_signature_verification_path_funnels_through_the_verifier():
    """The boundary test ruling 3 requires.

    ``KeyRing.resolve`` is raw and non-validating: it takes no instant and so cannot
    enforce a window. Nothing that reaches a trust decision may call it. The one caller
    permitted to resolve a key at all is ``EnvelopeVerifier``, and it must use
    ``resolve_record``.
    """

    import pathlib
    import re

    src = pathlib.Path(__file__).resolve().parents[2] / "src" / "risk_authority"
    # Only key-ring resolution. The package has unrelated `.resolve(` callers (policy and
    # evidence resolver ports) which this rule has nothing to say about.
    key_resolve = re.compile(r"\bkey_ring\.resolve\(|\b_key_ring\.resolve\(|\bring\.resolve\(")
    offenders = []
    for path in src.rglob("*.py"):
        if path.name == "keys.py":
            continue  # the definition site
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if key_resolve.search(line):
                offenders.append(f"{path.relative_to(src)}:{lineno}: {line.strip()}")
    assert not offenders, (
        "these call the non-validating KeyRing.resolve; a signature-verification path "
        "must use resolve_record and check is_valid_at:\n" + "\n".join(offenders))

    verifier_src = (src / "services" / "envelope_verifier.py").read_text(encoding="utf-8")
    assert "resolve_record" in verifier_src and "is_valid_at" in verifier_src


def test_an_external_signer_outside_its_window_cannot_issue():
    """Ruling 4: a bounded external signer cannot bypass issuance-time validation."""

    from tests import scenario as S
    from risk_authority.services.envelope_issuer import EnvelopeIssuer

    app = S.build_application()
    _evaluation, decision, envelope = S.approved_envelope(app)

    class _WindowedSigner:
        is_production_authoritative = False
        key_id = S.KEY_ID
        signature_alg = "ed25519"
        not_before = None
        not_after = S.FIXED_NOW - HOUR  # expired at the trusted instant
        signed = False

        def sign(self, payload):
            type(self).signed = True
            return b"\x00" * 64

    with pytest.raises(RiskAuthorityError, match="validity window"):
        EnvelopeIssuer().issue(
            envelope_id="rae_signer", decision=decision, audience=envelope.audience,
            subject=envelope.subject, model_id=envelope.model_id,
            session_id=envelope.session_id, nonce="n3",
            signer=_WindowedSigner(), revocation_state=app.revocation, now=S.FIXED_NOW,
        )
    assert _WindowedSigner.signed is False, "sign() must not be reached"


def test_an_external_signer_inside_its_window_still_issues():
    from tests import scenario as S
    from risk_authority.services.envelope_issuer import EnvelopeIssuer
    from risk_authority.services.envelope_signer import ReferenceEnvelopeSigner

    app = S.build_application()
    _evaluation, decision, envelope = S.approved_envelope(app)

    signer = ReferenceEnvelopeSigner(SigningKeyRecord(
        S.KEY_ID, SigningKey.from_seed(bytes(range(32))),
        not_before=S.FIXED_NOW - HOUR, not_after=S.FIXED_NOW + HOUR))

    issued = EnvelopeIssuer().issue(
        envelope_id="rae_ok", decision=decision, audience=envelope.audience,
        subject=envelope.subject, model_id=envelope.model_id,
        session_id=envelope.session_id, nonce="n4",
        signer=signer, revocation_state=app.revocation, now=S.FIXED_NOW,
    )
    assert issued.signature


# ------------------------------------------------------- ruling 4: the signer contract
def test_a_signer_declaring_no_window_is_unbounded():
    """No existing signer implementation changes behavior."""

    from risk_authority.services.envelope_signer import signer_window

    class _Bare:
        key_id = "k"
        signature_alg = "ed25519"
        is_production_authoritative = False

        def sign(self, payload):  # pragma: no cover - not reached
            return b"x"

    assert signer_window(_Bare()) == (None, None)


def test_the_reference_signer_exposes_its_records_window():
    signer = ReferenceEnvelopeSigner(_record(not_before=T0, not_after=T0 + HOUR))
    assert signer.not_before == T0 and signer.not_after == T0 + HOUR


def test_a_signer_with_a_malformed_window_is_refused_not_read_as_unbounded():
    """A signer that tried to express bounds and got them wrong must not pass silently."""

    from risk_authority.services.envelope_signer import signer_window

    class _Malformed:
        key_id = "k"
        not_before = T0 + HOUR
        not_after = T0

    with pytest.raises(KeyWindowError):
        signer_window(_Malformed())
