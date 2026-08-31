"""Push-device registration lifecycle (Phase 3C, owner-ratified device model).

- A registration belongs to the authenticated USER (a device installation
  endpoint); the session that created it is recorded as an association only,
  so logging out of that device revokes it — logout-all revokes every
  registration the user holds. A push token is never an auth credential.
- One user may hold multiple active devices; a token is revocable/replaceable
  and maps to at most one ACTIVE registration globally: registering a token
  displaces any previous registration (same device, new owner) via the bounded
  ``app_release_push_token`` definer.
- Tokens are SENSITIVE: validated, stored, and never logged, audited, or
  echoed by any response.
"""

from __future__ import annotations

import uuid

from ..audit.service import AuditService
from ..base import utcnow
from ..domain import enums
from ..domain.enums import AuditAction
from ..errors import DilChatError, ErrorCode, not_found
from ..infrastructure.devices_orm import ChatDevice
from ..repositories.devices import DeviceRepository

_TOKEN_MAX_LENGTH = 2048


class DeviceService:
    def __init__(self, *, devices: DeviceRepository, audit: AuditService) -> None:
        self._devices = devices
        self._audit = audit

    @staticmethod
    def _validate_token(push_token: str) -> None:
        if not push_token or len(push_token) > _TOKEN_MAX_LENGTH:
            raise DilChatError(ErrorCode.VALIDATION_ERROR, "Invalid push token.")
        if any(ord(ch) < 0x20 or ch == "\x7f" for ch in push_token):
            raise DilChatError(ErrorCode.VALIDATION_ERROR, "Invalid push token.")

    async def register(
        self,
        *,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        push_token: str,
        platform: str,
        correlation_id: str | None = None,
    ) -> ChatDevice:
        self._validate_token(push_token)
        if platform not in {p.value for p in enums.DevicePlatform}:
            raise DilChatError(ErrorCode.VALIDATION_ERROR, "Unknown device platform.")
        own = await self._devices.get_own_by_token(user_id, push_token)
        if own is not None and own.status == enums.DeviceStatus.ACTIVE.value:
            # Idempotent re-registration: refresh the session association only.
            own.session_id = session_id
            own.platform = platform
            return own
        # The token addresses one physical installation: displace any previous
        # ACTIVE registration (possibly another user's, hidden by RLS).
        await self._devices.release_token(push_token)
        if own is not None:
            own.status = enums.DeviceStatus.ACTIVE.value
            own.revoked_at = None
            own.provider_rejected_at = None
            own.session_id = session_id
            own.platform = platform
            device = own
        else:
            device = await self._devices.add(
                ChatDevice(
                    user_id=user_id,
                    session_id=session_id,
                    platform=platform,
                    status=enums.DeviceStatus.ACTIVE.value,
                    push_token=push_token,
                )
            )
        await self._audit.record(
            action=AuditAction.DEVICE_REGISTERED,
            actor_user_id=user_id,
            resource_type="chat_device",
            resource_id=device.id,
            correlation_id=correlation_id,
        )
        return device

    async def revoke(
        self, device_id: uuid.UUID, user_id: uuid.UUID, correlation_id: str | None = None
    ) -> ChatDevice:
        device = await self._devices.get(device_id)
        if device is None or device.user_id != user_id:
            raise not_found()  # foreign/unknown device: no existence disclosure
        if device.status == enums.DeviceStatus.REVOKED.value:
            return device  # idempotent
        device.status = enums.DeviceStatus.REVOKED.value
        device.revoked_at = utcnow()
        await self._audit.record(
            action=AuditAction.DEVICE_REVOKED,
            actor_user_id=user_id,
            resource_type="chat_device",
            resource_id=device.id,
            correlation_id=correlation_id,
        )
        return device

    async def list_devices(self, user_id: uuid.UUID) -> list[ChatDevice]:
        return await self._devices.list_for_user(user_id)

    async def revoke_for_session(self, user_id: uuid.UUID, session_id: uuid.UUID) -> int:
        """Logout of THIS device: revoke registrations created by this session."""
        from ..infrastructure.devices_orm import ChatDevice as D

        return await self._devices.revoke_where(
            D.user_id == user_id, D.session_id == session_id
        )

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> int:
        """Logout-all: revoke every registration the user holds."""
        from ..infrastructure.devices_orm import ChatDevice as D

        return await self._devices.revoke_where(D.user_id == user_id)
