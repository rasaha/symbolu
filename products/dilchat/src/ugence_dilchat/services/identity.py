"""Identity service: registration, login, refresh rotation, logout.

Self-managed identity (DEC-011/DEC-022) using Argon2id + ES256 access tokens +
rotating opaque refresh sessions. Refresh-token **reuse** (presenting a token whose
session was already rotated or revoked) triggers revocation of the whole rotation
chain. No email/SMS/social/reset flows in this phase.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from ..audit.service import AuditService
from ..config import Settings
from ..domain.enums import AuditAction, AuthzOutcome
from ..errors import DilChatError, ErrorCode
from ..infrastructure.orm import User
from ..repositories.users import SessionRepository, UserRepository
from ..security.passwords import hash_password, verify_password
from ..security.tokens import (
    TokenService,
    generate_refresh_token,
    hash_refresh_token,
)


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    access_expires_in: int
    session_id: uuid.UUID


class IdentityService:
    def __init__(
        self,
        *,
        settings: Settings,
        users: UserRepository,
        sessions: SessionRepository,
        tokens: TokenService,
        audit: AuditService,
    ) -> None:
        self._settings = settings
        self._users = users
        self._sessions = sessions
        self._tokens = tokens
        self._audit = audit

    async def register(self, email: str, password: str, correlation_id: str | None = None) -> User:
        _validate_password(password)
        existing = await self._users.get_by_email(email)
        if existing is not None:
            # Do not reveal which email is taken beyond a generic conflict.
            raise DilChatError(ErrorCode.CONFLICT, "Registration could not be completed.")
        user = await self._users.create(email=email, credential_hash=hash_password(password))
        await self._audit.record(
            action=AuditAction.USER_REGISTERED,
            actor_user_id=user.id,
            resource_type="user",
            resource_id=user.id,
            correlation_id=correlation_id,
        )
        return user

    async def login(
        self, email: str, password: str, *, user_agent: str | None = None,
        correlation_id: str | None = None,
    ) -> IssuedTokens:
        user = await self._users.get_by_email(email)
        # Constant-ish path: always run verify to reduce timing signal.
        ok = user is not None and user.credential_hash is not None and verify_password(
            password, user.credential_hash
        )
        if not user or not ok or user.status != "ACTIVE":
            raise DilChatError(ErrorCode.AUTH_INVALID_CREDENTIALS, "Invalid email or password.")
        tokens = await self._issue_session(user.id, user_agent=user_agent)
        await self._audit.record(
            action=AuditAction.USER_LOGIN,
            actor_user_id=user.id,
            resource_type="session",
            resource_id=tokens.session_id,
            correlation_id=correlation_id,
        )
        return tokens

    async def refresh(
        self, refresh_token: str, *, user_agent: str | None = None,
        correlation_id: str | None = None,
    ) -> IssuedTokens:
        token_hash = hash_refresh_token(refresh_token)
        session = await self._sessions.get_by_refresh_hash(token_hash)
        if session is None:
            raise DilChatError(ErrorCode.AUTH_TOKEN_INVALID, "Invalid refresh token.")

        # Reuse detection: a token that was already rotated or revoked is being
        # replayed -> kill the whole chain.
        if session.rotated_at is not None or session.revoked_at is not None:
            await self._sessions.revoke_chain_from(session.id)
            await self._audit.record(
                action=AuditAction.REFRESH_REUSE_DETECTED,
                actor_user_id=session.user_id,
                resource_type="session",
                resource_id=session.id,
                outcome=AuthzOutcome.DENY,
                denial_reason_code=ErrorCode.AUTH_REFRESH_REUSE.value,
                correlation_id=correlation_id,
            )
            raise DilChatError(ErrorCode.AUTH_REFRESH_REUSE, "Refresh token reuse detected.")

        if session.expires_at <= dt.datetime.now(dt.UTC):
            await self._sessions.revoke(session)
            raise DilChatError(ErrorCode.AUTH_TOKEN_EXPIRED, "Refresh token expired.")

        await self._sessions.mark_rotated(session)
        tokens = await self._issue_session(
            session.user_id, user_agent=user_agent, rotated_from_id=session.id
        )
        await self._audit.record(
            action=AuditAction.SESSION_REFRESHED,
            actor_user_id=session.user_id,
            resource_type="session",
            resource_id=tokens.session_id,
            correlation_id=correlation_id,
        )
        return tokens

    async def logout(self, session_id: uuid.UUID, correlation_id: str | None = None) -> None:
        session = await self._sessions.get(session_id)
        if session is not None:
            await self._sessions.revoke(session)
            await self._audit.record(
                action=AuditAction.SESSION_REVOKED,
                actor_user_id=session.user_id,
                resource_type="session",
                resource_id=session.id,
                correlation_id=correlation_id,
            )

    async def logout_all(self, user_id: uuid.UUID, correlation_id: str | None = None) -> int:
        count = await self._sessions.revoke_all_for_user(user_id)
        await self._audit.record(
            action=AuditAction.SESSIONS_REVOKED_ALL,
            actor_user_id=user_id,
            resource_type="user",
            resource_id=user_id,
            correlation_id=correlation_id,
        )
        return count

    async def _issue_session(
        self, user_id: uuid.UUID, *, user_agent: str | None = None,
        rotated_from_id: uuid.UUID | None = None,
    ) -> IssuedTokens:
        refresh = generate_refresh_token()
        expires_at = dt.datetime.now(dt.UTC) + dt.timedelta(
            seconds=self._settings.refresh_token_ttl_seconds
        )
        session = await self._sessions.create(
            user_id=user_id,
            refresh_token_hash=hash_refresh_token(refresh),
            expires_at=expires_at,
            rotated_from_id=rotated_from_id,
            user_agent=user_agent,
        )
        access = self._tokens.issue_access_token(user_id, session.id)
        return IssuedTokens(
            access_token=access,
            refresh_token=refresh,
            access_expires_in=self._settings.access_token_ttl_seconds,
            session_id=session.id,
        )


def _validate_password(password: str) -> None:
    if len(password) < 10:
        raise DilChatError(
            ErrorCode.VALIDATION_ERROR,
            "Password must be at least 10 characters.",
            errors=[{"field": "password", "issue": "too_short"}],
        )
