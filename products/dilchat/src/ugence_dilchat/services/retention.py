"""Retention purge ELIGIBILITY evaluation and the read-only report (round PR-B).

Ratified rule (DEC-PR-3). A revoked conversation becomes purge-ELIGIBLE — which
is not deletion — only when ALL of the following hold:

    retention_purge_enabled = true
    AND revocation age >= chat_retention_revoked_days (30)
    AND retention state is still REVOKED_PENDING_POLICY
    AND no report/case requires preservation
    AND no PRESERVED_FOR_REPORT state exists
    AND no legal/operational hold applies
    AND no active policy-specific retention exception applies

``PRESERVED_FOR_REPORT`` dominates unconditionally: it is never purge-eligible
at any age. The retention window must never undercut the bounded post-revocation
reporting right (``chat_report_after_revocation_days``), so the settings guard
refuses a retention window shorter than the reporting window.

**This module performs NO deletion.** By ratified amendment, destructive purging
stays unimplemented and ``retention_purge_enabled`` stays false until the
remaining gates pass (purge implementation tests, preservation-state tests,
report-window boundary tests, documented backup implications, legal/privacy
review of the period, and dry-run evidence). The only executable path here is
``RetentionPurgeService.report_only()``, which reports what WOULD be considered
and deletes nothing — there is deliberately no delete/purge method to call, and
a source guard test pins that absence.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import enum
import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..base import utcnow
from ..config import Settings
from ..db import set_transaction_context
from ..domain.enums import RetentionState
from ..infrastructure.chat_orm import ChatConversation
from ..infrastructure.chat_safety_orm import ChatConversationRetention


class PurgeBlocker(str, enum.Enum):
    """Why a conversation is NOT purge-eligible. Machine codes only (no content)."""

    PURGE_DISABLED = "PURGE_DISABLED"  # retention_purge_enabled is false
    NOT_REVOKED_STATE = "NOT_REVOKED_STATE"  # ACTIVE — the couple is still paired
    PRESERVED_FOR_REPORT = "PRESERVED_FOR_REPORT"  # dominates unconditionally
    ALREADY_PURGED = "ALREADY_PURGED"
    WITHIN_RETENTION_WINDOW = "WITHIN_RETENTION_WINDOW"  # reporting right may still be used
    MISSING_REVOCATION_TIMESTAMP = "MISSING_REVOCATION_TIMESTAMP"  # fail closed
    LEGAL_HOLD = "LEGAL_HOLD"  # legal/operational hold or policy exception


def purge_eligibility(
    *,
    purge_enabled: bool,
    state: str,
    revoked_at: dt.datetime | None,
    hold_reason: str | None,
    retention_days: int,
    now: dt.datetime,
) -> PurgeBlocker | None:
    """Return the blocking reason, or ``None`` when every ratified condition holds.

    Pure and total: every input combination yields a decision, and anything
    unexpected fails CLOSED (not eligible). Order is reporting order — the most
    fundamental reason is named first — but eligibility requires ALL conditions,
    so no ordering can make an ineligible conversation eligible.
    """
    # A hold and PRESERVED_FOR_REPORT are checked before the flag so a report
    # states the real protection rather than the global switch.
    if state == RetentionState.PRESERVED_FOR_REPORT.value:
        return PurgeBlocker.PRESERVED_FOR_REPORT
    if hold_reason is not None:
        return PurgeBlocker.LEGAL_HOLD
    if state == RetentionState.PURGED.value:
        return PurgeBlocker.ALREADY_PURGED
    if not purge_enabled:
        return PurgeBlocker.PURGE_DISABLED
    if state not in (
        RetentionState.REVOKED_PENDING_POLICY.value,
        RetentionState.ELIGIBLE_FOR_PURGE.value,
    ):
        return PurgeBlocker.NOT_REVOKED_STATE
    if revoked_at is None:
        return PurgeBlocker.MISSING_REVOCATION_TIMESTAMP
    if now - revoked_at < dt.timedelta(days=retention_days):
        return PurgeBlocker.WITHIN_RETENTION_WINDOW
    return None


@dataclasses.dataclass(frozen=True)
class RetentionPurgeReport:
    """Content-free summary of what a purge WOULD consider. Nothing is deleted."""

    evaluated_at: dt.datetime
    purge_enabled: bool
    retention_days: int
    reporting_window_days: int
    total_rows: int
    eligible_conversation_ids: tuple[uuid.UUID, ...]
    blocked_counts: dict[str, int]

    @property
    def eligible_count(self) -> int:
        return len(self.eligible_conversation_ids)

    def as_dict(self) -> dict:
        return {
            "evaluated_at": self.evaluated_at.isoformat(),
            "purge_enabled": self.purge_enabled,
            "retention_days": self.retention_days,
            "reporting_window_days": self.reporting_window_days,
            "total_rows": self.total_rows,
            "eligible_count": self.eligible_count,
            "eligible_conversation_ids": [str(c) for c in self.eligible_conversation_ids],
            "blocked_counts": dict(sorted(self.blocked_counts.items())),
            "deleted": 0,
            "mode": "REPORT_ONLY",
        }


class RetentionPurgeService:
    """Read-only evaluator. Deliberately exposes no destructive operation."""

    def __init__(
        self,
        *,
        settings: Settings,
        sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        self._settings = settings
        self._sessionmaker = sessionmaker

    async def report_only(self, *, now: dt.datetime | None = None) -> RetentionPurgeReport:
        """Evaluate every retention row and report the outcome. Deletes nothing."""
        now = now or utcnow()
        async with self._sessionmaker() as session:
            # Worker posture: the report is infrastructure, never a user surface.
            await set_transaction_context(session, user_id=None, actor_type="worker")
            rows = (
                await session.execute(
                    sa.select(
                        ChatConversationRetention.conversation_id,
                        ChatConversationRetention.state,
                        ChatConversationRetention.hold_reason,
                        ChatConversation.revoked_at,
                    ).join(
                        ChatConversation,
                        ChatConversation.id == ChatConversationRetention.conversation_id,
                    )
                )
            ).all()
            # Read-only by construction: the session is never committed and no
            # mutation is issued; roll back so nothing can linger in a transaction.
            await session.rollback()

        eligible: list[uuid.UUID] = []
        blocked: dict[str, int] = {}
        for conversation_id, state, hold_reason, revoked_at in rows:
            blocker = purge_eligibility(
                purge_enabled=self._settings.retention_purge_enabled,
                state=state,
                revoked_at=revoked_at,
                hold_reason=hold_reason,
                retention_days=self._settings.chat_retention_revoked_days,
                now=now,
            )
            if blocker is None:
                eligible.append(conversation_id)
            else:
                blocked[blocker.value] = blocked.get(blocker.value, 0) + 1

        return RetentionPurgeReport(
            evaluated_at=now,
            purge_enabled=self._settings.retention_purge_enabled,
            retention_days=self._settings.chat_retention_revoked_days,
            reporting_window_days=self._settings.chat_report_after_revocation_days,
            total_rows=len(rows),
            eligible_conversation_ids=tuple(eligible),
            blocked_counts=blocked,
        )
