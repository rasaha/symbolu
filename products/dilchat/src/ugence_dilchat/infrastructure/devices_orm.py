"""SQLAlchemy ORM for push-device registrations (Phase 3C).

A device registration is a DEVICE INSTALLATION endpoint belonging to the
authenticated user — never a session credential and never usable for
authentication (D3C ratification). The optional ``session_id`` records only
which session registered it, so logging out of that device can revoke it;
logout-all revokes every registration the user holds.

Privacy invariants:

- ``push_token`` is SENSITIVE: never logged, audited, echoed by any API
  response, or exposed to the read-only/safety roles (they hold no grant).
- A token maps to at most one ACTIVE registration globally (partial unique
  index); a device handed to a new user displaces the previous registration
  via the bounded ``app_release_push_token`` definer.
"""

from __future__ import annotations

import datetime as dt
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, TimestampMixin, UTCDateTime, uuid_pk
from ..domain import enums
from .orm import SENSITIVE, _enum_check


class ChatDevice(Base, TimestampMixin):
    __tablename__ = "chat_devices"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Association only (which session registered this device) — not an auth bind.
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("user_sessions.id", ondelete="SET NULL"), index=True
    )
    platform: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    status: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, default=enums.DeviceStatus.ACTIVE.value
    )
    push_token: Mapped[str] = mapped_column(sa.Text, nullable=False, info=SENSITIVE)
    # Set when the provider permanently rejected the token (DeviceNotRegistered).
    provider_rejected_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)

    __table_args__ = (
        _enum_check("status", enums.DeviceStatus),
        _enum_check("platform", enums.DevicePlatform),
        sa.Index(
            "ux_chat_device_active_token",
            "push_token",
            unique=True,
            postgresql_where=sa.text("status = 'ACTIVE'"),
            sqlite_where=sa.text("status = 'ACTIVE'"),
        ),
    )
