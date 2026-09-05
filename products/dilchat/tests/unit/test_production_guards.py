"""Production-readiness fail-fast guards (owner round D-PR, round PR-A).

A staging/production process must refuse to start on debug output, the
local-development database default, a non-PostgreSQL engine, a cleartext push
URL, or a missing signing key — and Settings repr/str must never surface
credentials.
"""

from __future__ import annotations

import pytest

from ugence_dilchat.config import Environment, Settings

_PEM = "-----BEGIN PRIVATE KEY-----\nSENTINEL_PR_A_key_material\n-----END PRIVATE KEY-----"
_PROD_DB = "postgresql+asyncpg://dilchat_app:SENTINEL_PR_A_db_password@db.internal:5432/dilchat"


def _prod(**kw) -> Settings:
    """A minimal VALID production configuration; tests break one field at a time."""
    base: dict = dict(
        environment=Environment.PRODUCTION,
        astrology_provider="swiss",
        swiss_production_licensed=True,
        access_token_private_key_pem=_PEM,
        database_url=_PROD_DB,
    )
    base.update(kw)
    return Settings(**base)


def test_valid_production_configuration_starts():
    s = _prod()
    assert s.environment is Environment.PRODUCTION


def test_debug_refused_in_production():
    with pytest.raises(ValueError, match="debug"):
        _prod(debug=True)


def test_dev_database_default_refused_in_production():
    from ugence_dilchat.config import _DEV_DATABASE_URL

    with pytest.raises(ValueError, match="DILCHAT_DATABASE_URL"):
        _prod(database_url=_DEV_DATABASE_URL)


def test_non_postgresql_engine_refused_in_production():
    with pytest.raises(ValueError, match="postgresql\\+asyncpg"):
        _prod(database_url="sqlite+aiosqlite:///prod.db")


def test_missing_signing_key_refused_in_production():
    with pytest.raises(ValueError, match="access_token_private_key_pem"):
        _prod(access_token_private_key_pem=None)


def test_cleartext_expo_url_refused_in_production():
    with pytest.raises(ValueError, match="https"):
        _prod(push_transport="expo", expo_push_url="http://exp.host/--/api/v2/push/send")
    # https passes.
    s = _prod(push_transport="expo")
    assert s.expo_push_url.startswith("https://")


def test_staging_gets_the_same_guards():
    with pytest.raises(ValueError, match="debug"):
        _prod(environment=Environment.STAGING, debug=True)


def test_development_keeps_permissive_defaults():
    s = Settings(environment=Environment.DEVELOPMENT)
    assert s.debug is False  # default, but permitted to be True in development
    Settings(environment=Environment.DEVELOPMENT, debug=True)  # must not raise


def test_settings_repr_never_contains_credentials():
    s = _prod()
    for rendered in (repr(s), str(s)):
        assert "SENTINEL_PR_A_key_material" not in rendered
        assert "SENTINEL_PR_A_db_password" not in rendered
        assert _PROD_DB not in rendered
