"""Secure shared chat service (Phase 3A).

Transactional invariants live here:

- **Lock ordering.** Both message send and unpair revocation take the SAME single
  row lock — the ``chat_conversations`` row (``SELECT ... FOR UPDATE``) — so the
  send/unpair race is deterministic and deadlock-free. A message can commit before
  revocation acquires the lock (then revocation follows), or revocation commits
  first and the send is rejected; a message can NEVER commit after revocation is
  effective.
- **Idempotency.** Message creation is idempotent on
  ``(conversation, sender, client_message_id)``; a retry returns the original
  result with no new row and no new outbox event; reuse of the key with a different
  body on a live message is a conflict.
- **Transactional outbox.** Every state change writes its outbox event in the same
  DB transaction; a rollback removes both. Outbox payloads carry IDs/metadata only
  — never a message body.
- **Authorization.** Membership is always resolved from the authoritative couple
  memberships via ``authorize_shared``; a client-supplied conversation/message id
  never establishes access. PostgreSQL RLS independently enforces the same rule.
"""

from __future__ import annotations

import unicodedata
import uuid
from dataclasses import dataclass

from ..audit.service import AuditService
from ..base import utcnow
from ..config import Settings
from ..domain.enums import AuditAction, ConversationStatus, OutboxEventType, RetentionState
from ..errors import DilChatError, ErrorCode, not_found, scope_denied
from ..infrastructure.chat_orm import ChatConversation, ChatMessage, ChatReadState
from ..infrastructure.chat_safety_orm import ChatConversationRetention
from ..repositories.chat import (
    ConversationRepository,
    MessageRepository,
    OutboxRepository,
    ReadStateRepository,
)
from ..repositories.couples import MembershipRepository
from ..repositories.safety import BlockRepository, RetentionRepository
from ..security.scope import authorize_shared
from .ratelimit import RateLimiter

# Control characters that are permitted inside a message body.
_ALLOWED_CONTROL = {"\n", "\r", "\t"}


@dataclass(frozen=True)
class MessagePage:
    messages: list[ChatMessage]
    next_cursor: str | None
    has_more: bool


@dataclass(frozen=True)
class ConversationView:
    conversation: ChatConversation
    latest_sequence: int
    last_read_sequence: int


class ChatService:
    def __init__(
        self,
        *,
        settings: Settings,
        conversations: ConversationRepository,
        messages: MessageRepository,
        read_states: ReadStateRepository,
        outbox: OutboxRepository,
        memberships: MembershipRepository,
        audit: AuditService,
        blocks: BlockRepository | None = None,
        retention: RetentionRepository | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self._settings = settings
        self._conversations = conversations
        self._messages = messages
        self._read_states = read_states
        self._outbox = outbox
        self._memberships = memberships
        self._audit = audit
        # Phase 3B safety collaborators. Optional so 3A-era unit tests that build
        # the service directly keep working; the API wiring always provides them.
        self._blocks = blocks
        self._retention = retention
        self._rate_limiter = rate_limiter

    # -- validation --------------------------------------------------------- #
    def _validate_body(self, body: str) -> str:
        if len(body) > self._settings.chat_message_max_code_points:
            raise DilChatError(
                ErrorCode.VALIDATION_ERROR,
                f"Message body exceeds {self._settings.chat_message_max_code_points} code points.",
            )
        if body.strip() == "":
            raise DilChatError(ErrorCode.VALIDATION_ERROR, "Message body cannot be empty.")
        for ch in body:
            if ch in _ALLOWED_CONTROL:
                continue
            if ch == "\x00" or unicodedata.category(ch) in ("Cc", "Cs"):
                raise DilChatError(
                    ErrorCode.VALIDATION_ERROR,
                    "Message body contains unsupported control characters.",
                )
        return body

    async def _require_active_member(
        self, couple_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        fact = await self._memberships.membership_fact(couple_id=couple_id, user_id=user_id)
        authorize_shared(fact).raise_if_denied()

    # -- lifecycle (pairing / unpair) --------------------------------------- #
    async def provision_conversation(
        self, couple_id: uuid.UUID, actor_user_id: uuid.UUID | None = None,
        correlation_id: str | None = None,
    ) -> ChatConversation:
        """Create the conversation for a couple, idempotently (used at pairing).

        Uniqueness is enforced by ``uq_chat_conversation_couple`` so concurrent
        acceptance cannot create duplicate conversations; a second call returns the
        existing row without a second outbox event.
        """
        existing = await self._conversations.get_by_couple(couple_id)
        if existing is not None:
            return existing
        conv = await self._conversations.create(couple_id)
        # Phase 3B: every conversation carries an explicit retention row from
        # birth (migration d4e5f6a7b8c9 backfilled pre-existing conversations).
        if self._retention is not None:
            if await self._retention.get_by_conversation(conv.id) is None:
                await self._retention.add(
                    ChatConversationRetention(
                        conversation_id=conv.id,
                        couple_id=couple_id,
                        state=RetentionState.ACTIVE.value,
                    )
                )
        await self._audit.record(
            action=AuditAction.CONVERSATION_CREATED,
            actor_user_id=actor_user_id,
            resource_type="chat_conversation",
            resource_id=conv.id,
            couple_id=couple_id,
            correlation_id=correlation_id,
        )
        await self._outbox.add(
            event_type=OutboxEventType.CONVERSATION_CREATED,
            conversation_id=conv.id,
            couple_id=couple_id,
            payload={"conversation_id": str(conv.id), "couple_id": str(couple_id)},
        )
        return conv

    async def revoke_conversation(
        self, couple_id: uuid.UUID, actor_user_id: uuid.UUID,
        correlation_id: str | None = None,
    ) -> None:
        """Revoke a couple's conversation in the unpair transaction.

        MUST run BEFORE membership revocation so the actor is still an active member
        (RLS permits the update). Takes the conversation row lock, so it is serialised
        against concurrent message sends.
        """
        # Self-authorising: only a current active member may drive revocation.
        fact = await self._memberships.membership_fact(
            couple_id=couple_id, user_id=actor_user_id
        )
        if not authorize_shared(fact).allowed:
            raise not_found()
        conv = await self._conversations.get_by_couple_for_update(couple_id)
        if conv is None or conv.status != ConversationStatus.ACTIVE.value:
            return  # no conversation, or already revoked (idempotent)
        conv.status = ConversationStatus.REVOKED.value
        conv.revoked_at = utcnow()
        conv.version += 1
        # Phase 3B: an unpaired conversation enters the revoked-pending retention
        # state — unless a report already preserved it (PRESERVED_FOR_REPORT is
        # never downgraded; no purge is executed in this phase).
        if self._retention is not None:
            row = await self._retention.get_by_conversation(conv.id)
            if row is None:
                await self._retention.add(
                    ChatConversationRetention(
                        conversation_id=conv.id,
                        couple_id=couple_id,
                        state=RetentionState.REVOKED_PENDING_POLICY.value,
                    )
                )
            elif row.state == RetentionState.ACTIVE.value:
                row.state = RetentionState.REVOKED_PENDING_POLICY.value
        await self._audit.record(
            action=AuditAction.CONVERSATION_REVOKED,
            actor_user_id=actor_user_id,
            resource_type="chat_conversation",
            resource_id=conv.id,
            couple_id=couple_id,
            correlation_id=correlation_id,
        )
        await self._outbox.add(
            event_type=OutboxEventType.CONVERSATION_REVOKED,
            conversation_id=conv.id,
            couple_id=couple_id,
            payload={"conversation_id": str(conv.id), "couple_id": str(couple_id)},
        )

    # -- reads -------------------------------------------------------------- #
    async def current_conversation(self, user_id: uuid.UUID) -> ConversationView:
        membership = await self._memberships.active_membership_for_user(user_id)
        if membership is None:
            raise not_found("No active conversation.")
        conv = await self._conversations.get_by_couple(membership.couple_id)
        if conv is None or conv.status != ConversationStatus.ACTIVE.value:
            raise not_found("No active conversation.")
        latest = await self._messages.max_sequence(conv.id)
        rs = await self._read_states.get(conversation_id=conv.id, user_id=user_id)
        return ConversationView(
            conversation=conv,
            latest_sequence=latest,
            last_read_sequence=rs.last_read_sequence if rs else 0,
        )

    async def _authorized_active_conversation(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID, *, lock: bool = False
    ) -> ChatConversation:
        conv = (
            await self._conversations.get_for_update(conversation_id)
            if lock
            else await self._conversations.get(conversation_id)
        )
        if conv is None:
            raise not_found()  # anti-enumeration for a non-existent/foreign conversation
        await self._require_active_member(conv.couple_id, user_id)
        return conv

    async def list_messages(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID, *,
        cursor: str | None, limit: int,
    ) -> MessagePage:
        from .chat_cursor import decode_cursor, encode_cursor

        conv = await self._authorized_active_conversation(conversation_id, user_id)
        if conv.status != ConversationStatus.ACTIVE.value:
            raise not_found()  # revoked conversation: anti-enumeration
        limit = max(1, min(limit, self._settings.chat_page_max))
        after = decode_cursor(cursor, conversation_id) if cursor else 0
        # Fetch one extra row to determine has_more without a second query.
        rows = await self._messages.list_page(
            conversation_id=conversation_id, after_sequence=after, limit=limit + 1
        )
        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor = (
            encode_cursor(conversation_id, page[-1].server_sequence) if has_more and page else None
        )
        return MessagePage(messages=page, next_cursor=next_cursor, has_more=has_more)

    # -- writes ------------------------------------------------------------- #
    async def create_message(
        self, conversation_id: uuid.UUID, sender_user_id: uuid.UUID, *,
        client_message_id: str, body: str, correlation_id: str | None = None,
    ) -> ChatMessage:
        self._validate_body(body)
        # Lock the conversation row: serialises sends against each other and against
        # unpair revocation, and yields a gapless server_sequence.
        conv = await self._conversations.get_for_update(conversation_id)
        if conv is None:
            raise not_found()
        await self._require_active_member(conv.couple_id, sender_user_id)
        if conv.status != ConversationStatus.ACTIVE.value:
            raise DilChatError(
                ErrorCode.CONVERSATION_NOT_ACTIVE, "Conversation is no longer active."
            )

        existing = await self._messages.get_by_idempotency(
            conversation_id=conversation_id,
            sender_user_id=sender_user_id,
            client_message_id=client_message_id,
        )
        if existing is not None:
            if existing.deleted_at is None and existing.body != body:
                raise DilChatError(
                    ErrorCode.IDEMPOTENCY_CONFLICT,
                    "client_message_id reused with a different body.",
                )
            return existing  # idempotent replay: no new row, no new outbox event

        # Phase 3B (DILCHAT-D3B-1): while EITHER participant has an ACTIVE block,
        # new sends are denied in BOTH directions with one identical, generic
        # error — the surface never discloses who blocked whom. Checked after the
        # idempotent-replay branch (a retry of an already-committed message must
        # keep returning that message) and inside the conversation lock.
        if self._blocks is not None:
            for member in await self._memberships.for_couple(conv.couple_id):
                if member.user_id == sender_user_id:
                    continue
                if await self._blocks.active_block_between(sender_user_id, member.user_id):
                    raise scope_denied("Messaging is unavailable for this conversation.")
        # Phase 3B (DILCHAT-D3B-4): rate-limit only genuinely new sends, after
        # every authorization check has passed (a 429 never masks a 404/403).
        if self._rate_limiter is not None:
            await self._rate_limiter.enforce_send(sender_user_id)

        seq = conv.next_sequence
        conv.next_sequence = seq + 1
        conv.version += 1
        message = ChatMessage(
            conversation_id=conv.id,
            couple_id=conv.couple_id,
            sender_user_id=sender_user_id,
            client_message_id=client_message_id,
            server_sequence=seq,
            body=body,
        )
        await self._messages.add(message)
        await self._outbox.add(
            event_type=OutboxEventType.MESSAGE_CREATED,
            conversation_id=conv.id,
            couple_id=conv.couple_id,
            payload={
                "conversation_id": str(conv.id),
                "couple_id": str(conv.couple_id),
                "message_id": str(message.id),
                "sender_user_id": str(sender_user_id),
                "server_sequence": seq,
            },
        )
        return message

    async def delete_message(
        self, conversation_id: uuid.UUID, message_id: uuid.UUID, actor_user_id: uuid.UUID,
        correlation_id: str | None = None,
    ) -> ChatMessage:
        conv = await self._authorized_active_conversation(
            conversation_id, actor_user_id, lock=True
        )
        message = await self._messages.get(message_id)
        if message is None or message.conversation_id != conversation_id:
            raise not_found()  # missing or cross-conversation message id
        if message.sender_user_id != actor_user_id:
            raise scope_denied("Only the sender may delete this message.")
        if message.deleted_at is not None:
            return message  # idempotent: already tombstoned, no second outbox event
        if conv.status != ConversationStatus.ACTIVE.value:
            raise DilChatError(
                ErrorCode.CONVERSATION_NOT_ACTIVE, "Conversation is no longer active."
            )
        message.deleted_at = utcnow()
        message.deleted_by_user_id = actor_user_id
        message.body = ""  # physical body erasure; row + metadata retained (tombstone)
        await self._audit.record(
            action=AuditAction.MESSAGE_DELETED,
            actor_user_id=actor_user_id,
            resource_type="chat_message",
            resource_id=message.id,
            couple_id=conv.couple_id,
            correlation_id=correlation_id,
        )
        await self._outbox.add(
            event_type=OutboxEventType.MESSAGE_DELETED,
            conversation_id=conv.id,
            couple_id=conv.couple_id,
            payload={
                "conversation_id": str(conv.id),
                "couple_id": str(conv.couple_id),
                "message_id": str(message.id),
                "sender_user_id": str(message.sender_user_id),
                "server_sequence": message.server_sequence,
                "deleted_by_user_id": str(actor_user_id),
            },
        )
        return message

    async def update_read_state(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID, *,
        last_read_sequence: int, correlation_id: str | None = None,
    ) -> ChatReadState:
        conv = await self._authorized_active_conversation(
            conversation_id, user_id, lock=True
        )
        if conv.status != ConversationStatus.ACTIVE.value:
            raise DilChatError(
                ErrorCode.CONVERSATION_NOT_ACTIVE, "Conversation is no longer active."
            )
        latest = await self._messages.max_sequence(conversation_id)
        if last_read_sequence < 0 or last_read_sequence > latest:
            raise DilChatError(
                ErrorCode.VALIDATION_ERROR,
                "Read-state target is beyond the latest message.",
            )
        rs = await self._read_states.get(conversation_id=conversation_id, user_id=user_id)
        advanced = False
        if rs is None:
            rs = ChatReadState(
                conversation_id=conversation_id,
                couple_id=conv.couple_id,
                user_id=user_id,
                last_read_sequence=last_read_sequence,
            )
            await self._read_states.add(rs)
            advanced = last_read_sequence > 0
        elif last_read_sequence > rs.last_read_sequence:
            rs.last_read_sequence = last_read_sequence  # forward-only
            advanced = True
        # else: no-op (repeat/backward update is idempotent; emits no event)

        if advanced:
            await self._outbox.add(
                event_type=OutboxEventType.READ_STATE_UPDATED,
                conversation_id=conv.id,
                couple_id=conv.couple_id,
                payload={
                    "conversation_id": str(conv.id),
                    "couple_id": str(conv.couple_id),
                    "user_id": str(user_id),
                    "last_read_sequence": last_read_sequence,
                },
            )
        return rs
