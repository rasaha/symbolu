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
