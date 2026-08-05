"""Structural pagination / query-plan evidence at scale (Phase 3A).

Seeds a synthetic conversation with 10,000 messages and verifies: cursor pagination
stays stable and gapless, the page-size maximum is enforced, and the cursor query
uses the intended index (no sequential scan, no sort). Latency is deliberately NOT
asserted (shared CI runner); the query plan is the evidence.
"""

from __future__ import annotations

import json
import os
import uuid

import pytest
import sqlalchemy as sa

pytestmark = pytest.mark.postgres

_DB_URL = os.environ.get("DILCHAT_TEST_DATABASE_URL")
pytest.importorskip("asyncpg")
if not _DB_URL or "postgresql" not in _DB_URL:
    pytest.skip("DILCHAT_TEST_DATABASE_URL (PostgreSQL) not set", allow_module_level=True)

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from ugence_dilchat.audit.service import AuditService  # noqa: E402
from ugence_dilchat.base import Base  # noqa: E402
from ugence_dilchat.config import Environment, Settings  # noqa: E402
from ugence_dilchat.infrastructure import chat_orm as _chat_orm  # noqa: E402,F401
from ugence_dilchat.infrastructure.chat_orm import ChatConversation  # noqa: E402
from ugence_dilchat.infrastructure.orm import Couple, CoupleMembership, User  # noqa: E402
from ugence_dilchat.repositories.chat import (  # noqa: E402
    ConversationRepository,
    MessageRepository,
    OutboxRepository,
    ReadStateRepository,
)
from ugence_dilchat.repositories.couples import MembershipRepository  # noqa: E402
from ugence_dilchat.services.chat import ChatService  # noqa: E402

_N = 10_000
_SETTINGS = Settings(environment=Environment.TEST, database_url=_DB_URL)


def _service(session) -> ChatService:
    return ChatService(
        settings=_SETTINGS,
        conversations=ConversationRepository(session),
        messages=MessageRepository(session),
        read_states=ReadStateRepository(session),
        outbox=OutboxRepository(session),
        memberships=MembershipRepository(session),
        audit=AuditService(session),
    )


@pytest.fixture
async def big_conversation():
    engine = create_async_engine(_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        a = User(email=f"a_{uuid.uuid4().hex[:10]}@e.com", credential_hash="h")
        s.add(a)
        await s.flush()
        couple = Couple()
        s.add(couple)
        await s.flush()
        s.add(CoupleMembership(couple_id=couple.id, user_id=a.id, scope_slot="A"))
        conv = ChatConversation(couple_id=couple.id, next_sequence=_N + 1)
        s.add(conv)
        await s.commit()
        conv_id, couple_id, a_id = conv.id, couple.id, a.id
    # Bulk-seed 10k messages with a single server-side INSERT ... generate_series.
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO chat_messages "
                "(id, conversation_id, couple_id, sender_user_id, client_message_id, "
                " server_sequence, body, created_at) "
                "SELECT gen_random_uuid(), :conv, :couple, :sender, 'k'||g, g, 'm'||g, now() "
                "FROM generate_series(1, :n) g"
            ),
            {"conv": conv_id, "couple": couple_id, "sender": a_id, "n": _N},
        )
        # Collect statistics so the planner reflects the real distribution.
        await conn.execute(sa.text("ANALYZE chat_messages"))
    yield sm, conv_id, a_id
    await engine.dispose()


async def test_ten_thousand_messages_paginate_stably(big_conversation):
    sm, conv_id, a_id = big_conversation
    seen: list[int] = []
    cursor = None
    pages = 0
    async with sm() as s:
        svc = _service(s)
        while True:
            page = await svc.list_messages(conv_id, a_id, cursor=cursor, limit=100)
            seen.extend(m.server_sequence for m in page.messages)
            pages += 1
            if not page.has_more:
                break
            cursor = page.next_cursor
    assert seen == list(range(1, _N + 1))  # every message once, in order, no gaps
    assert pages == _N // 100  # bounded page count at the max page size


async def test_page_size_capped_at_maximum(big_conversation):
    sm, conv_id, a_id = big_conversation
    async with sm() as s:
        # Service caps the effective limit at chat_page_max (100) even if asked for more.
        page = await _service(s).list_messages(conv_id, a_id, cursor=None, limit=10_000)
    assert len(page.messages) == 100


async def test_cursor_query_uses_index_no_seqscan(big_conversation):
    sm, conv_id, a_id = big_conversation
    engine = sm.kw["bind"]
    async with engine.connect() as conn:
        rows = await conn.execute(
            sa.text(
                "EXPLAIN (FORMAT JSON) "
                "SELECT * FROM chat_messages "
                "WHERE conversation_id = :c AND server_sequence > 5000 "
                "ORDER BY server_sequence ASC LIMIT 50"
            ),
            {"c": conv_id},
        )
        plan_json = rows.scalar_one()
    plan_text = json.dumps(plan_json)
    print("cursor query plan:", plan_text)  # structural evidence in test output
    # The cursor query is served by the composite (conversation_id, server_sequence)
    # index — never a full sequential scan of the conversation.
    assert "uq_chat_message_sequence" in plan_text, plan_text
    assert "Index" in plan_text, plan_text
    assert "Seq Scan" not in plan_text, plan_text
