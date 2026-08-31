"""Push-device registration routes (Phase 3C, owner-ratified device model).

A registration is a device-installation endpoint owned by the authenticated
user — not a session credential. Responses never echo the push token; the
token cannot authenticate anything. Logout of the registering session revokes
that device; logout-all revokes every device (wired in the auth routes).
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
from ..schemas import DeviceListResponse, DeviceRegisterRequest, DeviceResponse

router = APIRouter(prefix="/devices", tags=["devices"])


def _device_response(device) -> DeviceResponse:
    return DeviceResponse(
        device_id=device.id,
        platform=device.platform,
        status=device.status,
        created_at=device.created_at,
        revoked_at=device.revoked_at,
    )


@router.post("", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def register_device(
    payload: DeviceRegisterRequest,
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
    correlation_id: str | None = Depends(get_correlation_id),
) -> DeviceResponse:
    device = await services.devices.register(
        user_id=principal.user_id,
        session_id=principal.session_id,
        push_token=payload.push_token,
        platform=payload.platform,
        correlation_id=correlation_id,
    )
    return _device_response(device)


@router.delete("/{device_id}", response_model=DeviceResponse)
async def revoke_device(
    device_id: uuid.UUID,
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
    correlation_id: str | None = Depends(get_correlation_id),
) -> DeviceResponse:
    device = await services.devices.revoke(device_id, principal.user_id, correlation_id)
    return _device_response(device)


@router.get("", response_model=DeviceListResponse)
async def list_devices(
    principal: AuthPrincipal = Depends(get_current_principal),
    services: ServiceRegistry = Depends(get_services),
) -> DeviceListResponse:
    devices = await services.devices.list_devices(principal.user_id)
    return DeviceListResponse(devices=[_device_response(d) for d in devices])
