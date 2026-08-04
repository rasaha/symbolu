"""Area A provider-safety behavior end-to-end and the synthetic-persist guard."""

from __future__ import annotations

import types

import pytest
from httpx import ASGITransport, AsyncClient

from helpers import VALID_BIRTH_PROFILE, register_and_login
from ugence_dilchat import db as db_module
from ugence_dilchat.app import create_app
from ugence_dilchat.base import Base
from ugence_dilchat.config import Environment, Settings
from ugence_dilchat.errors import DilChatError, ErrorCode
from ugence_dilchat.services.natal import NatalService

pytest.importorskip("swisseph")


async def _swiss_ctx():
    settings = Settings(
        environment=Environment.DEVELOPMENT,
        database_url="sqlite+aiosqlite://",
        astrology_provider="swiss",
        enable_swiss_ephemeris=True,
        swiss_ephemeris_mode="moshier",
    )
    engine = db_module.init_engine(settings)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app = create_app(settings)
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    return client


async def test_real_provider_natal_is_authoritative():
    client = await _swiss_ctx()
    try:
        auth = await register_and_login(client)
        h = {"Authorization": auth["Authorization"]}
        r = await client.post("/v1/birth-profiles", json=VALID_BIRTH_PROFILE, headers=h)
        assert r.status_code == 201
        natal = await client.post("/v1/natal/moon", headers=h)
        assert natal.status_code == 201, natal.text
        body = natal.json()
        assert body["synthetic_calculation"] is False
        assert body["authoritative"] is True
        assert body["test_only"] is False
        assert body["provenance"]["provider_kind"] == "REAL"
        assert body["provenance"]["ephemeris_mode"] == "moshier"
    finally:
        await client.aclose()
        await db_module.dispose_engine()


def test_synthetic_persist_guard_rejects_authoritative():
    # A synthetic result may never be persisted as authoritative (Area A).
    snap = types.SimpleNamespace(synthetic=True, authoritative=True, test_only=False)
    with pytest.raises(DilChatError) as exc:
        NatalService._assert_persist_allowed(snap)
    assert exc.value.code is ErrorCode.SYNTHETIC_PERSIST_FORBIDDEN


def test_synthetic_persist_guard_requires_test_only():
    snap = types.SimpleNamespace(synthetic=True, authoritative=False, test_only=False)
    with pytest.raises(DilChatError) as exc:
        NatalService._assert_persist_allowed(snap)
    assert exc.value.code is ErrorCode.SYNTHETIC_PERSIST_FORBIDDEN


def test_synthetic_persist_guard_allows_tagged_test_only():
    snap = types.SimpleNamespace(synthetic=True, authoritative=False, test_only=True)
    NatalService._assert_persist_allowed(snap)  # no raise


def test_real_result_persist_allowed():
    snap = types.SimpleNamespace(synthetic=False, authoritative=True, test_only=False)
    NatalService._assert_persist_allowed(snap)  # no raise
