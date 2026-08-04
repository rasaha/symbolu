"""Provider/environment safety policy (Area A) and Swiss dev-only licensing."""

from __future__ import annotations

import pytest

from ugence_dilchat.astrology.registry import build_provider
from ugence_dilchat.config import Environment, Settings
from ugence_dilchat.errors import DilChatError, ErrorCode


def _settings(**kw):
    base = dict(access_token_private_key_pem="x")  # satisfy prod key requirement
    base.update(kw)
    return Settings(**base)


# --- policy matrix --------------------------------------------------------- #
def test_fake_allowed_in_test():
    s = Settings(environment=Environment.TEST, astrology_provider="fake")
    assert build_provider(s).provider_id == "fake"


def test_fake_allowed_in_local_development():
    s = Settings(environment=Environment.DEVELOPMENT, astrology_provider="fake")
    assert build_provider(s).provider_id == "fake"


def test_fake_rejected_in_qa_unless_permitted():
    with pytest.raises(ValueError):
        Settings(environment=Environment.QA, astrology_provider="fake")
    # Explicit opt-in permits it.
    s = Settings(
        environment=Environment.QA, astrology_provider="fake", allow_fake_in_qa=True
    )
    assert build_provider(s).provider_id == "fake"


def test_fake_rejected_in_staging():
    with pytest.raises(ValueError):
        _settings(environment=Environment.STAGING, astrology_provider="fake")


def test_fake_rejected_in_production():
    with pytest.raises(ValueError):
        _settings(environment=Environment.PRODUCTION, astrology_provider="fake")


def test_swiss_rejected_in_production_without_license():
    with pytest.raises(ValueError):
        _settings(environment=Environment.PRODUCTION, astrology_provider="swiss")


def test_swiss_allowed_in_production_with_license_flag():
    s = _settings(
        environment=Environment.PRODUCTION,
        astrology_provider="swiss",
        swiss_production_licensed=True,
        enable_swiss_ephemeris=True,
    )
    # Config validates; registry builds a real provider.
    assert s.permitted_providers() == {"swiss"}
    provider = build_provider(s)
    assert provider.provider_id == "swiss"


def test_missing_production_provider_fails_startup_not_fake():
    # Default provider is fake; production must NOT auto-accept it.
    with pytest.raises(ValueError):
        _settings(environment=Environment.PRODUCTION)  # provider defaults to 'fake'


def test_dev_swiss_moshier_builds():
    s = Settings(
        environment=Environment.DEVELOPMENT,
        astrology_provider="swiss",
        enable_swiss_ephemeris=True,
        swiss_ephemeris_mode="moshier",
    )
    provider = build_provider(s)
    assert provider.provider_id == "swiss" and provider.ephemeris_mode == "moshier"


def test_registry_defense_in_depth_rejects_unpermitted():
    s = Settings(environment=Environment.DEVELOPMENT, astrology_provider="fake")
    # Force an out-of-policy provider post-construction; registry must still refuse.
    s.astrology_provider = "swiss"
    s.enable_swiss_ephemeris = False
    with pytest.raises(DilChatError) as exc:
        build_provider(s)
    assert exc.value.code in (ErrorCode.PROVIDER_DISABLED, ErrorCode.PROVIDER_NOT_PERMITTED)


# --- provider provenance & synthetic marking ------------------------------- #
def test_fake_provider_marks_synthetic_calculation():
    import datetime as dt

    from ugence_dilchat.astrology.fake import FakeAstrologyProvider

    p = FakeAstrologyProvider()
    r = p.compute_moon(dt.datetime(2000, 1, 1, tzinfo=dt.UTC), input_confidence=1.0)
    assert r.provenance.synthetic_calculation is True
    assert r.provenance.provider_kind == "SYNTHETIC"
    assert r.provenance.to_dict()["synthetic_calculation"] is True
