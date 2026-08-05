"""Secure shared chat routes (Phase 3A).

A deliberately bounded REST surface. There is NO arbitrary conversation-creation
endpoint: conversations are provisioned only through the pairing lifecycle. Route
handlers contain no business logic — every invariant lives in ``ChatService``.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from ..deps import (
    AuthPrincipal,
    ServiceRegistry,
    get_correlation_id,
    get_current_principal,
    get_services,
)
from ..schemas import (
    ConversationResponse,
    MessageCreateRequest,
    MessageListResponse,
    MessageResponse,
    ReadStateResponse,
    ReadStateUpdateRequest,
)

router = APIRouter(prefix="/conversations", tags=["chat"])


def _message_response(message) -> MessageResponse:
    deleted = message.deleted_at is not None
    return MessageResponse(
        message_id=message.id,
        conversation_id=message.conversation_id,
        sender_user_id=message.sender_user_id,
        client_message_id=message.client_message_id,
        server_sequence=message.server_sequence,
        body=None if deleted else message.body,
        created_at=message.created_at,
        deleted=deleted,
        deleted_at=message.deleted_at,
    )


@router.get("/current", response_model=ConversationResponse)
async def current_conversation(
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
) -> ConversationResponse:
    view = await services.chat.current_conversation(principal.user_id)
    members = await services.membership_repo.for_couple(view.conversation.couple_id)
    return ConversationResponse(
        conversation_id=view.conversation.id,
        couple_id=view.conversation.couple_id,
        status=view.conversation.status,
        created_at=view.conversation.created_at,
        latest_sequence=view.latest_sequence,
        last_read_sequence=view.last_read_sequence,
        member_user_ids=[m.user_id for m in members],
    )


@router.get("/{conversation_id}/messages", response_model=MessageListResponse)
async def list_messages(
    conversation_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=100),
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
) -> MessageListResponse:
    page = await services.chat.list_messages(
        conversation_id,
        principal.user_id,
        cursor=cursor,
        limit=limit if limit is not None else services.settings.chat_page_default,
    )
    return MessageListResponse(
        messages=[_message_response(m) for m in page.messages],
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_message(
    conversation_id: uuid.UUID,
    payload: MessageCreateRequest,
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
    correlation_id: str | None = Depends(get_correlation_id),
) -> MessageResponse:
    message = await services.chat.create_message(
        conversation_id,
        principal.user_id,
        client_message_id=payload.client_message_id,
        body=payload.body,
        correlation_id=correlation_id,
    )
    return _message_response(message)


@router.delete("/{conversation_id}/messages/{message_id}", response_model=MessageResponse)
async def delete_message(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
    correlation_id: str | None = Depends(get_correlation_id),
) -> MessageResponse:
    message = await services.chat.delete_message(
        conversation_id, message_id, principal.user_id, correlation_id
    )
    return _message_response(message)


@router.put("/{conversation_id}/read-state", response_model=ReadStateResponse)
async def update_read_state(
    conversation_id: uuid.UUID,
    payload: ReadStateUpdateRequest,
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
    correlation_id: str | None = Depends(get_correlation_id),
) -> ReadStateResponse:
    rs = await services.chat.update_read_state(
        conversation_id,
        principal.user_id,
        last_read_sequence=payload.last_read_sequence,
        correlation_id=correlation_id,
    )
    return ReadStateResponse(
        conversation_id=rs.conversation_id,
        user_id=rs.user_id,
        last_read_sequence=rs.last_read_sequence,
        updated_at=rs.updated_at,
    )
