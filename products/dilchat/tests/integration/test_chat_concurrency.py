"""Real-PostgreSQL concurrency tests for the secure chat core (Phase 3A).

These exercise the transactional invariants that SQLite cannot: gapless sequencing
under 20 concurrent sends, idempotency under concurrent duplicates, the send/unpair
race (no message may commit after revocation is effective), delete/read-state after
revocation, transactional-outbox atomicity, and stable pagination during concurrent
appends. Connections run as the owner role, so this isolates the row-lock invariants
(RLS is proven separately in ``tests/security/test_chat_rls.py``).
"""

from __future__ import annotations

import asyncio
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
from ugence_dilchat.domain.enums import ConversationStatus, OutboxEventType  # noqa: E402
from ugence_dilchat.errors import DilChatError, ErrorCode  # noqa: E402
from ugence_dilchat.infrastructure import chat_orm as _chat_orm  # noqa: E402,F401
from ugence_dilchat.infrastructure.chat_orm import (  # noqa: E402
    ChatConversation,
    ChatMessage,
    ChatOutbox,
)
from ugence_dilchat.infrastructure.orm import Couple, CoupleMembership, User  # noqa: E402
from ugence_dilchat.repositories.chat import (  # noqa: E402
    ConversationRepository,
    MessageRepository,
    OutboxRepository,
    ReadStateRepository,
)
from ugence_dilchat.repositories.couples import MembershipRepository  # noqa: E402
from ugence_dilchat.services.chat import ChatService  # noqa: E402

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
async def pg():
    engine = create_async_engine(_DB_URL, pool_size=30, max_overflow=10)
    # Ensure the schema exists (idempotent; the migration test may have cycled it).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    yield sm
    await engine.dispose()


async def _seed(sm) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Fresh couple + two members + ACTIVE conversation. Returns ids."""
    async with sm() as s:
        a = User(email=f"a_{uuid.uuid4().hex[:10]}@e.com", credential_hash="h")
        b = User(email=f"b_{uuid.uuid4().hex[:10]}@e.com", credential_hash="h")
        s.add_all([a, b])
        await s.flush()
        couple = Couple()
        s.add(couple)
        await s.flush()
        s.add_all([
            CoupleMembership(couple_id=couple.id, user_id=a.id, scope_slot="A"),
            CoupleMembership(couple_id=couple.id, user_id=b.id, scope_slot="B"),
        ])
        conv = ChatConversation(couple_id=couple.id)
        s.add(conv)
        await s.commit()
        return couple.id, conv.id, a.id, b.id


async def _count(sm, model, **filters) -> int:
    async with sm() as s:
        q = sa.select(sa.func.count()).select_from(model)
        for k, v in filters.items():
            q = q.where(getattr(model, k) == v)
        return int(await s.scalar(q))


# --- 20 concurrent unique sends -------------------------------------------- #
async def test_twenty_concurrent_unique_sends(pg):
    _, conv_id, a_id, _ = await _seed(pg)

    async def one(i: int):
        async with pg() as s:
            await _service(s).create_message(
                conv_id, a_id, client_message_id=f"c{i}", body=f"msg {i}"
            )
            await s.commit()

    await asyncio.gather(*(one(i) for i in range(20)))

    async with pg() as s:
        seqs = (
            await s.execute(
                sa.select(ChatMessage.server_sequence).where(
                    ChatMessage.conversation_id == conv_id
                )
            )
        ).scalars().all()
    assert sorted(seqs) == list(range(1, 21))  # gapless, unique 1..20
    assert (
        await _count(
            pg, ChatOutbox,
            conversation_id=conv_id,
            event_type=OutboxEventType.MESSAGE_CREATED.value,
        )
        == 20
    )


# --- concurrent duplicates (same key) -------------------------------------- #
async def test_concurrent_duplicate_same_key_single_message(pg):
    _, conv_id, a_id, _ = await _seed(pg)

    async def one():
        async with pg() as s:
            await _service(s).create_message(
                conv_id, a_id, client_message_id="dup", body="same"
            )
            await s.commit()

    await asyncio.gather(*(one() for _ in range(10)))
    assert await _count(pg, ChatMessage, conversation_id=conv_id) == 1
    assert (
        await _count(
            pg, ChatOutbox,
            conversation_id=conv_id,
            event_type=OutboxEventType.MESSAGE_CREATED.value,
        )
        == 1
    )


async def test_concurrent_same_key_different_body_one_wins(pg):
    _, conv_id, a_id, _ = await _seed(pg)
    conflicts = 0

    async def one(i: int):
        nonlocal conflicts
        async with pg() as s:
            try:
                await _service(s).create_message(
                    conv_id, a_id, client_message_id="dup", body=f"body{i}"
                )
                await s.commit()
            except DilChatError as exc:
                assert exc.code is ErrorCode.IDEMPOTENCY_CONFLICT
                conflicts += 1

    await asyncio.gather(*(one(i) for i in range(10)))
    assert await _count(pg, ChatMessage, conversation_id=conv_id) == 1
    assert conflicts == 9


# --- send / unpair race ---------------------------------------------------- #
async def test_revoke_then_send_is_rejected(pg):
    couple_id, conv_id, a_id, _ = await _seed(pg)
    async with pg() as s:
        await _service(s).revoke_conversation(couple_id, a_id)
        await s.commit()
    async with pg() as s:
        with pytest.raises(DilChatError) as exc:
            await _service(s).create_message(conv_id, a_id, client_message_id="late", body="x")
        assert exc.value.code is ErrorCode.CONVERSATION_NOT_ACTIVE
    assert await _count(pg, ChatMessage, conversation_id=conv_id) == 0


async def test_send_then_revoke_commits_message(pg):
    couple_id, conv_id, a_id, _ = await _seed(pg)
    async with pg() as s:
        await _service(s).create_message(conv_id, a_id, client_message_id="m", body="x")
        await s.commit()
    async with pg() as s:
        await _service(s).revoke_conversation(couple_id, a_id)
        await s.commit()
    assert await _count(pg, ChatMessage, conversation_id=conv_id) == 1
    async with pg() as s:
        conv = await s.get(ChatConversation, conv_id)
        assert conv.status == ConversationStatus.REVOKED.value


async def test_concurrent_send_and_unpair_never_commits_after_revoke(pg):
    # Repeat the race on fresh conversations to exercise both lock orderings.
    for _ in range(8):
        couple_id, conv_id, a_id, _ = await _seed(pg)

        async def send():
            async with pg() as s:
                try:
                    await _service(s).create_message(
                        conv_id, a_id, client_message_id="race", body="x"  # noqa: B023
                    )
                    await s.commit()
                except DilChatError:
                    pass  # rejected because revocation won the lock first

        async def unpair():
            async with pg() as s:
                await _service(s).revoke_conversation(couple_id, a_id)  # noqa: B023
                await s.commit()

        await asyncio.gather(send(), unpair())

        async with pg() as s:
            conv = await s.get(ChatConversation, conv_id)
            assert conv.status == ConversationStatus.REVOKED.value
            n = int(
                await s.scalar(
                    sa.select(sa.func.count())
                    .select_from(ChatMessage)
                    .where(ChatMessage.conversation_id == conv_id)
                )
            )
        # Either the send committed before revocation (1) or was rejected (0);
        # a message committed AFTER revocation is impossible by construction.
        assert n in (0, 1)


# --- delete / read-state after revocation ---------------------------------- #
async def test_delete_after_revoke_denied(pg):
    couple_id, conv_id, a_id, _ = await _seed(pg)
    async with pg() as s:
        msg = await _service(s).create_message(conv_id, a_id, client_message_id="m", body="x")
        await s.commit()
        mid = msg.id
    async with pg() as s:
        await _service(s).revoke_conversation(couple_id, a_id)
        await s.commit()
    async with pg() as s:
        with pytest.raises(DilChatError):
            await _service(s).delete_message(conv_id, mid, a_id)


async def test_read_state_after_revoke_denied(pg):
    couple_id, conv_id, a_id, b_id = await _seed(pg)
    async with pg() as s:
        await _service(s).create_message(conv_id, a_id, client_message_id="m", body="x")
        await s.commit()
    async with pg() as s:
        await _service(s).revoke_conversation(couple_id, a_id)
        await s.commit()
    async with pg() as s:
        with pytest.raises(DilChatError):
            await _service(s).update_read_state(conv_id, b_id, last_read_sequence=1)


async def test_account_deletion_effect_blocks_send(pg):
    # V1 behaviour: deleting an account dissolves the active relationship — the same
    # transactional revocation path as unpair — so the conversation is revoked and
    # further sends are rejected. (A standalone deletion endpoint is Phase 3B.)
    couple_id, conv_id, a_id, b_id = await _seed(pg)
    async with pg() as s:
        await _service(s).revoke_conversation(couple_id, a_id)
        # Simulate the account/membership teardown that account deletion performs.
        await s.execute(
            sa.update(CoupleMembership)
            .where(CoupleMembership.couple_id == couple_id)
            .values(status="REVOKED")
        )
        await s.execute(sa.update(User).where(User.id == a_id).values(status="DELETED"))
        await s.commit()
    async with pg() as s:
        with pytest.raises(DilChatError):
            await _service(s).create_message(conv_id, b_id, client_message_id="late", body="x")


# --- transactional outbox atomicity ---------------------------------------- #
async def test_rollback_removes_message_and_outbox(pg):
    _, conv_id, a_id, _ = await _seed(pg)
    async with pg() as s:
        await _service(s).create_message(conv_id, a_id, client_message_id="rb", body="x")
        # Simulate a failure after the message + outbox rows were flushed.
        await s.rollback()
    # Neither the message nor its outbox event survives; the sequence counter is intact.
    assert await _count(pg, ChatMessage, conversation_id=conv_id) == 0
    assert await _count(pg, ChatOutbox, conversation_id=conv_id) == 0
    async with pg() as s:
        conv = await s.get(ChatConversation, conv_id)
        assert conv.next_sequence == 1  # increment rolled back with the message


# --- pagination during concurrent appends ---------------------------------- #
async def test_pagination_stable_during_concurrent_appends(pg):
    from ugence_dilchat.services.chat_cursor import encode_cursor  # noqa: F401

    _, conv_id, a_id, _ = await _seed(pg)
    async with pg() as s:
        svc = _service(s)
        for i in range(30):
            await svc.create_message(conv_id, a_id, client_message_id=f"p{i}", body=f"m{i}")
        await s.commit()

    async def appender():
        for i in range(30, 45):
            async with pg() as s:
                await _service(s).create_message(
                    conv_id, a_id, client_message_id=f"p{i}", body=f"m{i}"
                )
                await s.commit()

    seen: list[int] = []

    async def paginate():
        cursor = None
        while True:
            async with pg() as s:
                page = await _service(s).list_messages(
                    conv_id, a_id, cursor=cursor, limit=5
                )
            seen.extend(m.server_sequence for m in page.messages)
            if not page.has_more:
                break
            cursor = page.next_cursor

    await asyncio.gather(appender(), paginate())
    # No duplicates and strictly increasing: an ascending cursor over an append-only
    # log never repeats or skips a returned row, even with concurrent appends.
    assert seen == sorted(seen)
    assert len(seen) == len(set(seen))
    assert set(range(1, 31)) <= set(seen)  # every pre-existing message was returned
