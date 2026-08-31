"""Security: sensitive values must not reach logs or audit rows."""

from __future__ import annotations

import uuid

import sqlalchemy as sa

from ugence_dilchat.audit.service import AuditService
from ugence_dilchat.domain.enums import AuditAction
from ugence_dilchat.infrastructure.orm import AuditEvent, User
from ugence_dilchat.logging import _redact


def test_redaction_processor_drops_sensitive_keys():
    event = {
        "event": "login",
        "password": "correcthorse7!",
        "refresh_token": "abc",
        "latitude": 19.07,
        "longitude": 72.87,
        "user_id": "ok-to-log",
    }
    out = _redact(None, "info", dict(event))
    assert out["password"] == "[REDACTED]"
    assert out["refresh_token"] == "[REDACTED]"
    assert out["latitude"] == "[REDACTED]"
    assert out["longitude"] == "[REDACTED]"
    assert out["user_id"] == "ok-to-log"


async def test_audit_provenance_strips_unsafe_keys(ctx):
    async with ctx.sessionmaker() as s:
        user = User(email=f"{uuid.uuid4().hex}@e.com", credential_hash="x")
        s.add(user)
        await s.flush()
        audit = AuditService(s)
        await audit.record(
            action=AuditAction.NATAL_MOON_COMPUTED,
            actor_user_id=user.id,
            provenance={
                "provider_id": "fake",
                "ayanamsa": "lahiri",
                "latitude": 19.07,          # must be stripped
                "longitude": 72.87,         # must be stripped
                "refresh_token": "secret",  # must be stripped
            },
        )
        await s.commit()
        row = await s.scalar(sa.select(AuditEvent).where(AuditEvent.actor_user_id == user.id))
        assert row is not None
        assert row.provenance == {"provider_id": "fake", "ayanamsa": "lahiri"}
        assert "latitude" not in row.provenance
        assert "refresh_token" not in row.provenance


def test_redaction_processor_covers_pr_a_additions():
    """Round PR-A: push/device tokens, report evidence/description, message
    bodies, identifiers, and DSNs are dropped by the structlog processor."""
    event = {
        "event": "device_registered",
        "push_token": "ExponentPushToken[x]",
        "device_token": "y",
        "expo_push_token": "z",
        "token": "t",
        "evidence": "quoted message text",
        "description": "reporter free text",
        "message_body": "hello",
        "body": "hello",
        "email": "user@example.com",
        "database_url": "postgresql+asyncpg://u:pw@h/db",
        "device_id": "ok-to-log",
    }
    out = _redact(None, "info", dict(event))
    for key in event:
        if key in ("event", "device_id"):
            assert out[key] == event[key]
        else:
            assert out[key] == "[REDACTED]", key


def test_relay_error_code_clamp_is_strict():
    from ugence_dilchat.relay.worker import _safe_error_code

    assert _safe_error_code("EXPO_UNAVAILABLE") == "EXPO_UNAVAILABLE"
    assert _safe_error_code("UNKNOWN_EVENT_TYPE") == "UNKNOWN_EVENT_TYPE"
    for unsafe in (
        "",
        "provider said: 502",
        "ExponentPushToken[abc]",
        "lower_case",
        "A" * 65,
        "CODE WITH SPACE",
    ):
        assert _safe_error_code(unsafe) == "TRANSPORT_UNAVAILABLE", unsafe
