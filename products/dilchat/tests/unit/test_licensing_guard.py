"""Swiss Ephemeris development-only licensing boundary (DEC-007) is enforced."""

from __future__ import annotations

import pytest

from ugence_dilchat.astrology.registry import build_provider
from ugence_dilchat.config import Environment, Settings
from ugence_dilchat.errors import DilChatError, ErrorCode


def test_production_config_rejects_swiss():
    with pytest.raises(ValueError):
        Settings(
            environment=Environment.PRODUCTION,
            astrology_provider="swiss",
            enable_swiss_ephemeris=True,
            access_token_private_key_pem="x",
        )


def test_production_requires_real_signing_key():
    with pytest.raises(ValueError):
        Settings(environment=Environment.PRODUCTION)


def test_registry_refuses_swiss_outside_dev_test():
    # A valid staging config uses the fake provider.
    s = Settings(
        environment=Environment.STAGING,
        astrology_provider="fake",
        access_token_private_key_pem="x",
    )
    assert build_provider(s).provider_id == "fake"
    # Force the registry path directly: even asked for swiss, staging refuses it
    # (defence in depth beyond the config-construction guard).
    s.astrology_provider = "swiss"
    with pytest.raises(DilChatError) as exc:
        build_provider(s)
    assert exc.value.code is ErrorCode.PROVIDER_DISABLED


def test_dev_swiss_moshier_builds():
    s = Settings(
        environment=Environment.DEVELOPMENT,
        astrology_provider="swiss",
        enable_swiss_ephemeris=True,
        swiss_ephemeris_mode="moshier",
    )
    provider = build_provider(s)
    assert provider.provider_id == "swiss"
    assert provider.ephemeris_mode == "moshier"


def test_default_provider_is_fake_and_production_safe():
    s = Settings(environment=Environment.DEVELOPMENT)
    assert s.astrology_provider == "fake"
    assert build_provider(s).provider_id == "fake"
