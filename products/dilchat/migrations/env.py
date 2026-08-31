"""Alembic async migration environment.

The database URL is resolved from application settings (``DILCHAT_DATABASE_URL``);
it is never stored in ``alembic.ini``. All ORM models are imported so
``Base.metadata`` is complete for autogenerate and for offline SQL.
"""

from __future__ import annotations

import asyncio

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from ugence_dilchat.base import Base
from ugence_dilchat.config import get_settings
from ugence_dilchat.infrastructure import chat_orm as _chat_orm  # noqa: F401  (register models)
from ugence_dilchat.infrastructure import chat_safety_orm as _chat_safety_orm  # noqa: F401
from ugence_dilchat.infrastructure import devices_orm as _devices_orm  # noqa: F401  (register models)
from ugence_dilchat.infrastructure import orm as _orm  # noqa: F401  (register models)

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    return get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _url()
    engine = async_engine_from_config(
        configuration, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    async with engine.connect() as connection:
        await connection.run_sync(_do_run)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
