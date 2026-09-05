"""User-block routes (Phase 3B, DILCHAT-D3B-1/2).

A block is a communication/safety restriction, not a relationship transition:
it silently denies message sends in both directions while active, and never
changes pairing state. The surface is blocker-only — a blocked user has no
route that reveals the block's existence. Creation targets the current active
partner only (anything else is 404), so the endpoint exposes no
account-enumeration surface.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from ..deps import (
    AuthPrincipal,
    ServiceRegistry,
    get_correlation_id,
    get_current_principal,
    get_services,
)
from ..schemas import BlockCreateRequest, BlockListResponse, BlockResponse

router = APIRouter(prefix="/blocks", tags=["safety"])


def _block_response(block) -> BlockResponse:
    return BlockResponse(
        block_id=block.id,
        blocked_user_id=block.blocked_user_id,
        status=block.status,
        created_at=block.created_at,
        revoked_at=block.revoked_at,
    )


@router.post("", response_model=BlockResponse, status_code=status.HTTP_201_CREATED)
async def create_block(
    payload: BlockCreateRequest,
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
    correlation_id: str | None = Depends(get_correlation_id),
) -> BlockResponse:
    block = await services.blocks.create_block(
        principal.user_id, payload.blocked_user_id, correlation_id
    )
    return _block_response(block)


@router.post("/{block_id}/revoke", response_model=BlockResponse)
async def revoke_block(
    block_id: uuid.UUID,
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
    correlation_id: str | None = Depends(get_correlation_id),
) -> BlockResponse:
    block = await services.blocks.revoke_block(block_id, principal.user_id, correlation_id)
    return _block_response(block)


@router.get("", response_model=BlockListResponse)
async def list_blocks(
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
) -> BlockListResponse:
    blocks = await services.blocks.list_blocks(principal.user_id)
    return BlockListResponse(blocks=[_block_response(b) for b in blocks])
