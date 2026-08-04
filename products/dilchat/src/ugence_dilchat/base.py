"""SQLAlchemy declarative base, portable column types, and common mixins.

Types are chosen to be portable across PostgreSQL (primary, production) and
SQLite (fast unit tests): ``sa.Uuid`` and timezone-aware ``DateTime``. JSON uses
JSONB on PostgreSQL and JSON elsewhere. Enumerations are stored as ``String``
with CHECK constraints rather than native ENUM to keep migrations portable.
"""

from __future__ import annotations

import datetime as dt
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

# JSON that is JSONB on PostgreSQL, generic JSON elsewhere.
JSONVariant = sa.JSON().with_variant(JSONB, "postgresql")


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class UTCDateTime(TypeDecorator):
    """Timezone-aware DateTime that always returns UTC-aware values.

    PostgreSQL ``timestamptz`` already returns aware datetimes; SQLite (used for
    fast unit tests) returns naive ones. This decorator normalises both directions
    so application code never compares naive and aware datetimes.
    """

    impl = sa.DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt.UTC)
        return value.astimezone(dt.UTC)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=dt.UTC)
        return value.astimezone(dt.UTC)


class Base(DeclarativeBase):
    pass


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime, nullable=False, default=utcnow
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        UTCDateTime, nullable=False, default=utcnow, onupdate=utcnow
    )
