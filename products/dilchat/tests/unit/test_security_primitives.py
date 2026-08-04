"""Unit tests for password hashing, token issue/verify, and provenance."""

from __future__ import annotations

import datetime as dt
import uuid

import pytest

from ugence_dilchat.astrology.provider import Provenance
from ugence_dilchat.config import Environment, Settings
from ugence_dilchat.errors import DilChatError, ErrorCode
from ugence_dilchat.security.passwords import hash_password, verify_password
from ugence_dilchat.security.tokens import (
    TokenService,
    generate_refresh_token,
    hash_refresh_token,
)


def test_password_hash_and_verify():
    h = hash_password("correcthorse7!")
    assert h != "correcthorse7!"
    assert verify_password("correcthorse7!", h)
    assert not verify_password("wrong", h)


def test_password_verify_malformed_hash_is_false():
    assert not verify_password("x", "not-a-valid-hash")


def _svc() -> TokenService:
    return TokenService(Settings(environment=Environment.TEST))


def test_access_token_roundtrip():
    svc = _svc()
    uid, sid = uuid.uuid4(), uuid.uuid4()
    token = svc.issue_access_token(uid, sid)
    claims = svc.verify_access_token(token)
    assert claims["sub"] == str(uid)
    assert claims["sid"] == str(sid)


def test_access_token_tampered_rejected():
    svc = _svc()
    token = svc.issue_access_token(uuid.uuid4(), uuid.uuid4())
    with pytest.raises(DilChatError) as exc:
        svc.verify_access_token(token + "x")
    assert exc.value.code in (ErrorCode.AUTH_TOKEN_INVALID, ErrorCode.AUTH_TOKEN_EXPIRED)


def test_refresh_token_opaque_and_hashed():
    t = generate_refresh_token()
    assert len(t) >= 40
    h = hash_refresh_token(t)
    assert len(h) == 64 and h != t
    assert hash_refresh_token(t) == h  # deterministic


def test_provenance_serialization():
    p = Provenance(
        provider_id="fake",
        provider_version="fake-1",
        ephemeris_mode="synthetic",
        ayanamsa="lahiri",
        calculation_timestamp=dt.datetime(2024, 1, 1, tzinfo=dt.UTC),
        numerical_precision_class="synthetic_non_astronomical",
        fallback_used=False,
        fallback_reason=None,
        input_confidence=1.0,
    )
    d = p.to_dict()
    assert d["provider_id"] == "fake"
    assert d["ayanamsa"] == "lahiri"
    assert d["calculation_timestamp"] == "2024-01-01T00:00:00+00:00"
    assert "time_assumption" not in d  # omitted when None
