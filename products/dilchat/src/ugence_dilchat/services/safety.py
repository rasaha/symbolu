"""Phase 3B safety services: user blocks and reports (DILCHAT-D3B-1..5).

Ratified semantics enforced here:

- **Blocks are behavioral, not metadata (D3B-1).** While either participant has
  an ACTIVE block, message sends are denied in BOTH directions with one generic,
  non-disclosing error (the enforcement itself lives in ``ChatService`` inside
  the send transaction; this module owns block lifecycle). The API never
  discloses who blocked whom.
- **Blocking does not unpair (D3B-2).** Block lifecycle never touches couple or
  conversation state.
- **Reports stay SUBMITTED (D3B-3).** There is no moderation-transition surface
  and no fabricated adjudication state. Reports are durable and idempotent on
  ``(reporter, conversation, client_report_id)``.
- **Reporters never read evidence back (D3B-5).** Evidence, cases, and case
  events are INSERT-only for the app role (RLS-enforced); responses carry only
  the reporter-visible report reference and status. The reporter's description
  is SENSITIVE: stored on the report row only, never echoed, logged, audited,
  or copied into evidence/case events.
- **Evidence never exceeds the reporter's own access.** Snapshots are taken only
  for a currently ACTIVE member (who can read the messages being snapshotted);
  a former member reporting inside the post-revocation window
  (``chat_report_after_revocation_days``) files a CONVERSATION-target report
  with no message evidence — their message access is already revoked and is
  not resurrected here.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import uuid
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit.service import AuditService
from ..base import utcnow
from ..config import Settings
from ..domain import enums
from ..domain.enums import AuditAction
from ..errors import DilChatError, ErrorCode, not_found, scope_denied
from ..infrastructure.chat_orm import ChatMessage
from ..infrastructure.chat_safety_orm import (
    ChatConversationRetention,
    ChatReport,
    ChatReportEvidence,
    ChatSafetyCase,
    ChatUserBlock,
)
from ..repositories.chat import ConversationRepository, MessageRepository
from ..repositories.couples import MembershipRepository
from ..repositories.safety import BlockRepository, RetentionRepository, SafetyReportRepository
from ..security.scope import authorize_shared
from .ratelimit import RateLimiter

_CLIENT_REPORT_ID_RE = re.compile(r"^[A-Za-z0-9._:\-]{1,64}$")


@dataclass(frozen=True)
class ConversationContext:
    couple_id: uuid.UUID
    status: str
    revoked_at: dt.datetime | None


class BlockService:
    """Directional block lifecycle. Creation targets the CURRENT active partner
    only — the only person a DilChat account can message — which also keeps the
    endpoint free of any account-enumeration surface (anything else is 404)."""

    def __init__(
        self,
        *,
        blocks: BlockRepository,
        memberships: MembershipRepository,
        rate_limiter: RateLimiter,
        audit: AuditService,
    ) -> None:
        self._blocks = blocks
        self._memberships = memberships
        self._rate_limiter = rate_limiter
        self._audit = audit

    async def _current_partner_id(self, user_id: uuid.UUID) -> uuid.UUID | None:
        mine = await self._memberships.active_membership_for_user(user_id)
        if mine is None:
            return None
        for m in await self._memberships.for_couple(mine.couple_id):
            if m.user_id != user_id and m.status == enums.MembershipStatus.ACTIVE.value:
                return m.user_id
        return None

    async def create_block(
        self, blocker_user_id: uuid.UUID, blocked_user_id: uuid.UUID,
        correlation_id: str | None = None,
    ) -> ChatUserBlock:
        if blocked_user_id == blocker_user_id:
            raise DilChatError(ErrorCode.VALIDATION_ERROR, "You cannot block yourself.")
        partner = await self._current_partner_id(blocker_user_id)
        if partner is None or blocked_user_id != partner:
            raise not_found()  # not the current partner: no existence disclosure
        existing = await self._blocks.get_pair(blocker_user_id, blocked_user_id)
        if existing is not None and existing.status == enums.BlockStatus.ACTIVE.value:
            return existing  # idempotent: re-blocking an active block is a no-op
        await self._rate_limiter.enforce_block_mutation(blocker_user_id)
        if existing is not None:
            existing.status = enums.BlockStatus.ACTIVE.value
            existing.revoked_at = None
            block = existing
        else:
            block = await self._blocks.add(
                ChatUserBlock(
                    blocker_user_id=blocker_user_id,
                    blocked_user_id=blocked_user_id,
                    status=enums.BlockStatus.ACTIVE.value,
                )
            )
        await self._audit.record(
            action=AuditAction.USER_BLOCK_CREATED,
            actor_user_id=blocker_user_id,
            resource_type="chat_user_block",
            resource_id=block.id,
            correlation_id=correlation_id,
        )
        return block

    async def revoke_block(
        self, block_id: uuid.UUID, actor_user_id: uuid.UUID,
        correlation_id: str | None = None,
    ) -> ChatUserBlock:
        block = await self._blocks.get(block_id)
        if block is None or block.blocker_user_id != actor_user_id:
            raise not_found()  # foreign/unknown block: no existence disclosure
        if block.status == enums.BlockStatus.REVOKED.value:
            return block  # idempotent
        await self._rate_limiter.enforce_block_mutation(actor_user_id)
        block.status = enums.BlockStatus.REVOKED.value
        block.revoked_at = utcnow()
        await self._audit.record(
            action=AuditAction.USER_BLOCK_REVOKED,
            actor_user_id=actor_user_id,
            resource_type="chat_user_block",
            resource_id=block.id,
            correlation_id=correlation_id,
        )
        return block

    async def list_blocks(self, blocker_user_id: uuid.UUID) -> list[ChatUserBlock]:
        return await self._blocks.list_for_blocker(blocker_user_id)


class ReportService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        settings: Settings,
        reports: SafetyReportRepository,
        conversations: ConversationRepository,
        messages: MessageRepository,
        memberships: MembershipRepository,
        retention: RetentionRepository,
        rate_limiter: RateLimiter,
        audit: AuditService,
    ) -> None:
        self._session = session
        self._settings = settings
        self._reports = reports
        self._conversations = conversations
        self._messages = messages
        self._memberships = memberships
        self._retention = retention
        self._rate_limiter = rate_limiter
        self._audit = audit

    # -- context / authorization -------------------------------------------- #
    async def _conversation_context(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> ConversationContext | None:
        """Bounded conversation facts for a caller who was EVER a member.

        On PostgreSQL this uses the ``app_conversation_context`` SECURITY DEFINER
        helper (RLS hides a revoked conversation from a former member, yet the
        post-revocation reporting window requires them to address it). The helper
        itself enforces the caller-was-a-member bound; it returns nothing for
        strangers. On SQLite (no RLS) the equivalent direct queries apply.
        """
        session = self._session  # the same request transaction every repo shares
        if session.bind is not None and session.bind.dialect.name == "postgresql":
            res = await session.execute(
                sa.text(
                    "SELECT couple_id, status, revoked_at "
                    "FROM app_conversation_context(:cid)"
                ),
                {"cid": conversation_id},
            )
            row = res.first()
            if row is None:
                return None
            return ConversationContext(
                couple_id=row.couple_id, status=row.status, revoked_at=row.revoked_at
            )
        conv = await self._conversations.get(conversation_id)
        if conv is None:
            return None
        membership = await self._memberships.get_membership(
            couple_id=conv.couple_id, user_id=user_id
        )
        if membership is None:
            return None
        return ConversationContext(
            couple_id=conv.couple_id, status=conv.status, revoked_at=conv.revoked_at
        )

    async def _is_active_member(self, couple_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        fact = await self._memberships.membership_fact(couple_id=couple_id, user_id=user_id)
        return authorize_shared(fact).allowed

    def _require_within_revocation_window(self, ctx: ConversationContext) -> None:
        if ctx.revoked_at is None:
            raise scope_denied("Reporting is not available for this conversation.")
        window = dt.timedelta(days=self._settings.chat_report_after_revocation_days)
        if utcnow() - ctx.revoked_at > window:
            raise scope_denied("The reporting window for this conversation has closed.")

    # -- validation ---------------------------------------------------------- #
    def _validate(
        self, *, target_type: str, target_message_id: uuid.UUID | None,
        reason: str, description: str | None, client_report_id: str,
    ) -> None:
        if target_type not in {t.value for t in enums.ReportTargetType}:
            raise DilChatError(ErrorCode.VALIDATION_ERROR, "Unknown report target type.")
        if reason not in {r.value for r in enums.ReportReason}:
            raise DilChatError(ErrorCode.VALIDATION_ERROR, "Unknown report reason.")
        if not _CLIENT_REPORT_ID_RE.match(client_report_id):
            raise DilChatError(ErrorCode.VALIDATION_ERROR, "Invalid client_report_id.")
        if target_type == enums.ReportTargetType.MESSAGE.value and target_message_id is None:
            raise DilChatError(
                ErrorCode.VALIDATION_ERROR, "A message report requires target_message_id."
            )
        is_conversation = target_type == enums.ReportTargetType.CONVERSATION.value
        if is_conversation and target_message_id is not None:
            raise DilChatError(
                ErrorCode.VALIDATION_ERROR, "A conversation report takes no target_message_id."
            )
        if description is not None and len(description) > (
            self._settings.safety_report_description_max_code_points
        ):
            raise DilChatError(
                ErrorCode.VALIDATION_ERROR,
                "Report description exceeds "
                f"{self._settings.safety_report_description_max_code_points} code points.",
            )

    # -- evidence ------------------------------------------------------------ #
    @staticmethod
    def _integrity(message: ChatMessage, body_snapshot: str) -> str:
        canonical = "|".join(
            [
                str(message.id),
                str(message.conversation_id),
                str(message.sender_user_id or ""),
                str(message.server_sequence),
                body_snapshot,
                message.created_at.isoformat() if message.created_at else "",
            ]
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async def _snapshot_evidence(
        self, *, report: ChatReport, conversation_id: uuid.UUID,
        target_message: ChatMessage | None,
    ) -> int:
        window = self._settings.safety_evidence_window_default
        latest = await self._messages.max_sequence(conversation_id)
        after = max(0, latest - window)
        rows = await self._messages.list_page(
            conversation_id=conversation_id, after_sequence=after, limit=window
        )
        if target_message is not None and all(r.id != target_message.id for r in rows):
            rows = [target_message, *rows]  # older than the window: keep it anyway
        rows = rows[: self._settings.safety_evidence_window_max]
        for seq, message in enumerate(rows, start=1):
            body_snapshot = "" if message.deleted_at is not None else message.body
            await self._reports.add_evidence(
                ChatReportEvidence(
                    report_id=report.id,
                    evidence_sequence=seq,
                    source_conversation_id=message.conversation_id,
                    source_message_id=message.id,
                    source_sender_id=message.sender_user_id,
                    source_server_sequence=message.server_sequence,
                    body_snapshot=body_snapshot,
                    source_deleted_at=message.deleted_at,
                    source_created_at=message.created_at,
                    integrity_sha256=self._integrity(message, body_snapshot),
                )
            )
        return len(rows)

    # -- retention ------------------------------------------------------------ #
    async def _preserve_retention(
        self, conversation_id: uuid.UUID, couple_id: uuid.UUID
    ) -> None:
        row = await self._retention.get_by_conversation(conversation_id)
        if row is None:
            await self._retention.add(
                ChatConversationRetention(
                    conversation_id=conversation_id,
                    couple_id=couple_id,
                    state=enums.RetentionState.PRESERVED_FOR_REPORT.value,
                )
            )
            return
        if row.state != enums.RetentionState.PURGED.value:
            # PRESERVED_FOR_REPORT wins over ACTIVE and REVOKED_PENDING_POLICY.
            row.state = enums.RetentionState.PRESERVED_FOR_REPORT.value

    # -- API ------------------------------------------------------------------ #
    async def create_report(
        self,
        *,
        reporter_user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        target_type: str,
        target_message_id: uuid.UUID | None,
        reason: str,
        description: str | None,
        client_report_id: str,
        correlation_id: str | None = None,
    ) -> ChatReport:
        self._validate(
            target_type=target_type,
            target_message_id=target_message_id,
            reason=reason,
            description=description,
            client_report_id=client_report_id,
        )
        ctx = await self._conversation_context(conversation_id, reporter_user_id)
        if ctx is None:
            raise not_found()  # unknown conversation or never a member: no disclosure

        active = await self._is_active_member(ctx.couple_id, reporter_user_id)
        if not active:
            # Former participant: allowed only inside the post-revocation window,
            # and only as a CONVERSATION report with no message evidence — their
            # message access is revoked and reporting does not resurrect it.
            self._require_within_revocation_window(ctx)
            if target_type == enums.ReportTargetType.MESSAGE.value:
                raise DilChatError(
                    ErrorCode.VALIDATION_ERROR,
                    "After the connection has ended, report the conversation as a whole.",
                )

        existing = await self._reports.get_by_idempotency(
            reporter_user_id=reporter_user_id,
            conversation_id=conversation_id,
            client_report_id=client_report_id,
        )
        if existing is not None:
            same = (
                existing.target_type == target_type
                and existing.target_message_id == target_message_id
                and existing.reason == reason
            )
            if not same:
                raise DilChatError(
                    ErrorCode.IDEMPOTENCY_CONFLICT,
                    "client_report_id reused with a different report.",
                )
            return existing  # idempotent replay: no new case/evidence/audit

        target_message: ChatMessage | None = None
        if target_type == enums.ReportTargetType.MESSAGE.value and target_message_id is not None:
            target_message = await self._messages.get(target_message_id)
            if target_message is None or target_message.conversation_id != conversation_id:
                raise not_found()

        await self._rate_limiter.enforce_report(reporter_user_id)

        case = await self._reports.add_case(
            ChatSafetyCase(
                state=enums.SafetyCaseState.OPEN.value,
                conversation_id=conversation_id,
                couple_id=ctx.couple_id,
            )
        )
        report = await self._reports.add_report(
            ChatReport(
                reporter_user_id=reporter_user_id,
                conversation_id=conversation_id,
                couple_id=ctx.couple_id,
                target_type=target_type,
                target_message_id=target_message_id,
                reason=reason,
                description=description,
                status=enums.ReportStatus.SUBMITTED.value,
                case_id=case.id,
                client_report_id=client_report_id,
            )
        )
        await self._reports.add_case_event(
            case_id=case.id,
            event_type=enums.SafetyCaseEventType.CASE_OPENED,
            actor_type=enums.SafetyActorType.USER,
            actor_internal_id=reporter_user_id,
        )
        await self._reports.add_case_event(
            case_id=case.id,
            event_type=enums.SafetyCaseEventType.REPORT_LINKED,
            actor_type=enums.SafetyActorType.SYSTEM,
            meta={"report_id": str(report.id)},
        )
        evidence_count = 0
        if active:
            evidence_count = await self._snapshot_evidence(
                report=report, conversation_id=conversation_id, target_message=target_message
            )
        await self._reports.add_case_event(
            case_id=case.id,
            event_type=enums.SafetyCaseEventType.EVIDENCE_PRESERVED,
            actor_type=enums.SafetyActorType.SYSTEM,
            meta={"report_id": str(report.id), "evidence_count": evidence_count},
        )
        await self._preserve_retention(conversation_id, ctx.couple_id)
        # Body-free audit: identifiers only; the description is never audited.
        await self._audit.record(
            action=AuditAction.SAFETY_CASE_OPENED,
            actor_user_id=reporter_user_id,
            resource_type="chat_safety_case",
            resource_id=case.id,
            couple_id=ctx.couple_id,
            correlation_id=correlation_id,
        )
        await self._audit.record(
            action=AuditAction.CHAT_REPORT_CREATED,
            actor_user_id=reporter_user_id,
            resource_type="chat_report",
            resource_id=report.id,
            couple_id=ctx.couple_id,
            correlation_id=correlation_id,
        )
        return report

    async def list_reports(self, reporter_user_id: uuid.UUID) -> list[ChatReport]:
        return await self._reports.list_for_reporter(reporter_user_id)
