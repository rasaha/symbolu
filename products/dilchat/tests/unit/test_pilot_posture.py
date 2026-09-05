"""Enforced pilot posture (DILCHAT-D-PL-1).

The ratified pilot runs under the `qa` environment, which is NOT
`is_production_like` — so the round PR-A configuration guards would not apply
by default. The owner required the pilot to mirror production discipline
anyway; `pilot_mode` makes that requirement enforced rather than remembered.
"""

from __future__ import annotations

import pytest

from ugence_dilchat.config import _DEV_DATABASE_URL, Environment, Settings

_PEM = "-----BEGIN PRIVATE KEY-----\nSENTINEL_pilot_key\n-----END PRIVATE KEY-----"
_DSN = "postgresql+asyncpg://dilchat_app:pw@db.internal:5432/dilchat"


def _pilot(**kw) -> Settings:
    base: dict = dict(
        environment=Environment.QA,
        pilot_mode=True,
        astrology_provider="swiss",
        access_token_private_key_pem=_PEM,
        database_url=_DSN,
    )
    base.update(kw)
    return Settings(**base)


def test_a_valid_qa_pilot_configuration_starts():
    s = _pilot()
    assert s.environment is Environment.QA
    assert s.pilot_mode is True
    # D-PL-1 defers the Swiss production licensing decision for the qa pilot.
    assert s.swiss_production_licensed is False


def test_pilot_mode_applies_the_production_guards_under_qa():
    for broken, match in (
        (dict(debug=True), "debug"),
        (dict(access_token_private_key_pem=None), "access_token_private_key_pem"),
        (dict(database_url=_DEV_DATABASE_URL), "DILCHAT_DATABASE_URL"),
        (dict(database_url="sqlite+aiosqlite:///pilot.db"), "postgresql\\+asyncpg"),
        (dict(push_transport="expo", expo_push_url="http://exp.host/x"), "https"),
    ):
        with pytest.raises(ValueError, match=match):
            _pilot(**broken)


def test_those_guards_name_the_pilot_rather_than_production():
    with pytest.raises(ValueError, match="pilot_mode"):
        _pilot(debug=True)


def test_without_pilot_mode_qa_stays_permissive():
    """Proving the guards genuinely come FROM pilot_mode, not from qa itself."""
    s = Settings(environment=Environment.QA, astrology_provider="swiss", debug=True)
    assert s.debug is True  # qa alone does not enforce the discipline


def test_pilot_mode_refuses_the_synthetic_provider_outright():
    # Even with the qa opt-in that would normally permit it.
    with pytest.raises(ValueError, match="astrology_provider"):
        _pilot(astrology_provider="fake", allow_fake_in_qa=True)
    # Without pilot_mode that same configuration is permitted in qa.
    assert Settings(
        environment=Environment.QA, astrology_provider="fake", allow_fake_in_qa=True
    ).astrology_provider == "fake"


def test_pilot_mode_does_not_demand_the_deferred_swiss_licence():
    """D-PL-1 defers it for qa; staging/production still require it."""
    assert _pilot(swiss_production_licensed=False).astrology_provider == "swiss"
    # Staging without the licence is still refused — via the provider/environment
    # policy, which yields no permitted provider at all (DEC-029).
    with pytest.raises(ValueError, match="is not permitted in environment 'staging'"):
        Settings(
            environment=Environment.STAGING,
            astrology_provider="swiss",
            swiss_production_licensed=False,
            access_token_private_key_pem=_PEM,
            database_url=_DSN,
        )
    # With the licence recorded, staging starts.
    assert Settings(
        environment=Environment.STAGING,
        astrology_provider="swiss",
        swiss_production_licensed=True,
        access_token_private_key_pem=_PEM,
        database_url=_DSN,
    ).swiss_production_licensed is True


def test_ratified_pilot_defaults():
    s = _pilot()
    assert s.push_transport == "null"  # D-PL-2
    assert s.retention_purge_enabled is False  # unchanged standing limit
    default = Settings(environment=Environment.TEST, database_url="sqlite+aiosqlite://")
    assert default.pilot_mode is False  # opt-in, never implicit
