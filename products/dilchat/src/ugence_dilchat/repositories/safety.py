"""Repositories for the Phase 3B safety layer (blocks, reports, retention, limits).

Pure persistence adapters — authorization and policy live in the services and,
independently, in PostgreSQL RLS. The rate-limit counter uses an atomic
INSERT ... ON CONFLICT DO UPDATE so concurrent requests within one window can
never lose an increment.
"""

from __future__ import annotations

import datetime as dt
import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from ..base import utcnow
from ..domain import enums
from ..infrastructure.chat_safety_orm import (
    ChatConversationRetention,
    ChatRateLimit,
    ChatReport,
    ChatReportEvidence,
    ChatSafetyCase,
    ChatSafetyCaseEvent,
    ChatUserBlock,
)


class BlockRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, block_id: uuid.UUID) -> ChatUserBlock | None:
        return await self._s.get(ChatUserBlock, block_id)

    async def get_pair(
        self, blocker_user_id: uuid.UUID, blocked_user_id: uuid.UUID
    ) -> ChatUserBlock | None:
        res = await self._s.execute(
            sa.select(ChatUserBlock).where(
                ChatUserBlock.blocker_user_id == blocker_user_id,
                ChatUserBlock.blocked_user_id == blocked_user_id,
            )
        )
        return res.scalar_one_or_none()

    async def list_for_blocker(self, blocker_user_id: uuid.UUID) -> list[ChatUserBlock]:
        res = await self._s.execute(
            sa.select(ChatUserBlock)
            .where(ChatUserBlock.blocker_user_id == blocker_user_id)
            .order_by(ChatUserBlock.created_at)
        )
        return list(res.scalars().all())

    async def add(self, row: ChatUserBlock) -> ChatUserBlock:
        self._s.add(row)
        await self._s.flush()
        return row

    async def active_block_between(self, user_a: uuid.UUID, user_b: uuid.UUID) -> bool:
        """True when an ACTIVE block exists in EITHER direction between the two users.

        On PostgreSQL this MUST go through the ``app_block_exists`` SECURITY DEFINER
        helper: the blocker-only RLS policy hides a block from the blocked user, so a
        plain query under the runtime role would miss the "other user blocked me"
        direction. The helper runs with the caller's transaction-local
        ``app.current_user_id`` context, so ``user_a`` must be the acting user.
        On SQLite (unit-test engine, no RLS) a direct query is equivalent.
        """
        if self._s.bind is not None and self._s.bind.dialect.name == "postgresql":
            res = await self._s.execute(
                sa.text("SELECT app_block_exists(:other)"), {"other": user_b}
            )
            return bool(res.scalar_one())
        res = await self._s.execute(
            sa.select(sa.func.count())
            .select_from(ChatUserBlock)
            .where(
                ChatUserBlock.status == enums.BlockStatus.ACTIVE.value,
                sa.or_(
                    sa.and_(
                        ChatUserBlock.blocker_user_id == user_a,
                        ChatUserBlock.blocked_user_id == user_b,
                    ),
                    sa.and_(
                        ChatUserBlock.blocker_user_id == user_b,
                        ChatUserBlock.blocked_user_id == user_a,
                    ),
                ),
            )
        )
        return (res.scalar_one() or 0) > 0


class SafetyReportRepository:
    """Reports plus their INTERNAL case / evidence / case-event rows.

    The app role may only INSERT the internal rows (never read them back) — the
    service must therefore never depend on reading a case or evidence row after
    writing it.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_idempotency(
        self, *, reporter_user_id: uuid.UUID, conversation_id: uuid.UUID, client_report_id: str
    ) -> ChatReport | None:
        res = await self._s.execute(
            sa.select(ChatReport).where(
                ChatReport.reporter_user_id == reporter_user_id,
                ChatReport.conversation_id == conversation_id,
                ChatReport.client_report_id == client_report_id,
            )
        )
        return res.scalar_one_or_none()

    async def list_for_reporter(self, reporter_user_id: uuid.UUID) -> list[ChatReport]:
        res = await self._s.execute(
            sa.select(ChatReport)
            .where(ChatReport.reporter_user_id == reporter_user_id)
            .order_by(ChatReport.created_at)
        )
        return list(res.scalars().all())

    async def add_case(self, case: ChatSafetyCase) -> ChatSafetyCase:
        self._s.add(case)
        await self._s.flush()
        return case

    async def add_report(self, report: ChatReport) -> ChatReport:
        self._s.add(report)
        await self._s.flush()
        return report

    async def add_evidence(self, row: ChatReportEvidence) -> None:
        self._s.add(row)
        await self._s.flush()

    async def add_case_event(
        self,
        *,
        case_id: uuid.UUID,
        event_type: enums.SafetyCaseEventType,
        actor_type: enums.SafetyActorType,
        actor_internal_id: uuid.UUID | None = None,
        meta: dict | None = None,
    ) -> None:
        # Meta carries IDs/codes only — never a body or a reporter description.
        self._s.add(
            ChatSafetyCaseEvent(
                case_id=case_id,
                event_type=event_type.value,
                actor_type=actor_type.value,
                actor_internal_id=actor_internal_id,
                meta=meta,
            )
        )
        await self._s.flush()


class RetentionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_conversation(
        self, conversation_id: uuid.UUID
    ) -> ChatConversationRetention | None:
        res = await self._s.execute(
            sa.select(ChatConversationRetention).where(
                ChatConversationRetention.conversation_id == conversation_id
            )
        )
        return res.scalar_one_or_none()

    async def add(self, row: ChatConversationRetention) -> ChatConversationRetention:
        self._s.add(row)
        await self._s.flush()
        return row


class RateLimitRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def increment(
        self,
        *,
        subject_user_id: uuid.UUID,
        action_key: str,
        window_seconds: int,
        now: dt.datetime | None = None,
    ) -> int:
        """Atomically increment the fixed-window counter and return the new count.

        The unique key (subject, action, window_start, window_seconds) plus
        ON CONFLICT DO UPDATE makes concurrent increments within one window safe
        on both PostgreSQL and SQLite.
        """
        current = now or utcnow()
        epoch = int(current.timestamp())
        window_start = dt.datetime.fromtimestamp(
            epoch - (epoch % window_seconds), tz=dt.UTC
        )
        if self._s.bind is not None and self._s.bind.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as upsert
        else:
            from sqlalchemy.dialects.sqlite import insert as upsert  # type: ignore[assignment]
        stmt = (
            upsert(ChatRateLimit)
            .values(
                id=uuid.uuid4(),
                subject_user_id=subject_user_id,
                action_key=action_key,
                window_start=window_start,
                window_seconds=window_seconds,
                count=1,
            )
            .on_conflict_do_update(
                index_elements=["subject_user_id", "action_key", "window_start", "window_seconds"],
                set_={"count": ChatRateLimit.count + 1},
            )
        )
        await self._s.execute(stmt)
        res = await self._s.execute(
            sa.select(ChatRateLimit.count).where(
                ChatRateLimit.subject_user_id == subject_user_id,
                ChatRateLimit.action_key == action_key,
                ChatRateLimit.window_start == window_start,
                ChatRateLimit.window_seconds == window_seconds,
            )
        )
        return int(res.scalar_one())
