"""Pins for the ratified Phase 3C relay policy (D3C-1..4)."""

from __future__ import annotations

import pytest

from ugence_dilchat.config import Environment, Settings


def _settings(**kw) -> Settings:
    return Settings(environment=Environment.TEST, database_url="sqlite+aiosqlite://", **kw)


def test_ratified_relay_defaults():
    s = _settings()
    # D3C-1: the null transport is the safe default; expo is the pilot opt-in.
    assert s.push_transport == "null"
    # D3C-3: published-row pruning window.
    assert s.outbox_prune_after_days == 30
    # I2 bookkeeping bounds.
    assert s.relay_max_attempts == 8
    assert s.relay_backoff_base_seconds == 30
    assert s.relay_backoff_cap_seconds == 3600


def test_unknown_transport_fails_closed():
    with pytest.raises(ValueError, match="push_transport"):
        _settings(push_transport="carrier-pigeon")


def test_transport_builder_fails_closed_and_notification_text_is_generic():
    from ugence_dilchat.relay.transports import (
        NOTIFICATION_BODY,
        NOTIFICATION_TITLE,
        NullTransport,
        build_transport,
    )

    assert isinstance(build_transport("null", expo_url="x"), NullTransport)
    with pytest.raises(ValueError):
        build_transport("smoke-signals", expo_url="x")
    # D3C-2: the ratified generic text — no sender, no body, no metadata.
    assert NOTIFICATION_BODY == "You have a new message."
    assert NOTIFICATION_TITLE == "DilChat"
