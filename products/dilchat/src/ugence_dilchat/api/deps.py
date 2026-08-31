"""FastAPI dependencies: settings, DB session, auth principal, service wiring."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..astrology.provider import AstrologyProvider
from ..audit.service import AuditService
from ..config import Settings
from ..db import get_session, set_transaction_context
from ..errors import DilChatError, ErrorCode
from ..repositories.birth_profiles import BirthProfileRepository, NatalRepository
from ..repositories.chat import (
    ConversationRepository,
    MessageRepository,
    OutboxRepository,
    ReadStateRepository,
)
from ..repositories.consent import ConsentRepository, SharedArtifactRepository
from ..repositories.couples import (
    CoupleRepository,
    InvitationRepository,
    MembershipRepository,
)
from ..repositories.devices import DeviceRepository
from ..repositories.safety import (
    BlockRepository,
    RateLimitRepository,
    RetentionRepository,
    SafetyReportRepository,
)
from ..repositories.users import SessionRepository, UserRepository
from ..security.tokens import TokenService
from ..services.birth_profiles import BirthProfileService
from ..services.chat import ChatService
from ..services.consent import ConsentService
from ..services.couples import CoupleService
from ..services.devices import DeviceService
from ..services.identity import IdentityService
from ..services.natal import NatalService
from ..services.ratelimit import RateLimiter
from ..services.safety import BlockService, ReportService


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_token_service(request: Request) -> TokenService:
    return request.app.state.token_service


def get_provider(request: Request) -> AstrologyProvider:
    return request.app.state.astrology_provider


def get_correlation_id(request: Request) -> str | None:
    return getattr(request.state, "correlation_id", None)


@dataclass(frozen=True)
class AuthPrincipal:
    user_id: uuid.UUID
    session_id: uuid.UUID


async def get_current_principal(
    request: Request,
    session: AsyncSession = Depends(get_session),
    tokens: TokenService = Depends(get_token_service),
) -> AuthPrincipal:
    header = request.headers.get("authorization")
    if not header or not header.lower().startswith("bearer "):
        raise DilChatError(ErrorCode.AUTH_REQUIRED, "Missing bearer token.")
    token = header[7:].strip()
    claims = tokens.verify_access_token(token)  # raises AUTH_TOKEN_* on failure
    user_id = uuid.UUID(claims["sub"])
    session_id = uuid.UUID(claims["sid"])
    # Upgrade the transaction-local RLS context to the authenticated user (from the
    # cryptographically-verified JWT) BEFORE any scoped query runs (DEC-030).
    await set_transaction_context(session, user_id=user_id, actor_type="user")
    # Server-side session check: revoked/rotated/expired sessions are rejected even
    # if the (still-unexpired) access token verifies.
    sess = await SessionRepository(session).get(session_id)
    if sess is None or sess.user_id != user_id or not sess.is_active:
        raise DilChatError(ErrorCode.AUTH_SESSION_REVOKED, "Session is no longer valid.")
    return AuthPrincipal(user_id=user_id, session_id=session_id)


@dataclass
class ServiceRegistry:
    session: AsyncSession
    settings: Settings
    audit: AuditService
    identity: IdentityService
    birth_profiles: BirthProfileService
    natal: NatalService
    couples: CoupleService
    consent: ConsentService
    chat: ChatService
    blocks: BlockService
    reports: ReportService
    devices: DeviceService
    membership_repo: MembershipRepository
    couple_repo: CoupleRepository
    birth_profile_repo: BirthProfileRepository


def get_services(
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    tokens: TokenService = Depends(get_token_service),
    provider: AstrologyProvider = Depends(get_provider),
) -> ServiceRegistry:
    audit = AuditService(session)
    users = UserRepository(session)
    sessions = SessionRepository(session)
    bp_repo = BirthProfileRepository(session)
    natal_repo = NatalRepository(session)
    couple_repo = CoupleRepository(session)
    membership_repo = MembershipRepository(session)
    invitation_repo = InvitationRepository(session)
    consent_repo = ConsentRepository(session)
    artifact_repo = SharedArtifactRepository(session)
    conversation_repo = ConversationRepository(session)
    message_repo = MessageRepository(session)
    read_state_repo = ReadStateRepository(session)
    outbox_repo = OutboxRepository(session)
    block_repo = BlockRepository(session)
    report_repo = SafetyReportRepository(session)
    retention_repo = RetentionRepository(session)
    rate_limiter = RateLimiter(settings=settings, counters=RateLimitRepository(session))
    device_repo = DeviceRepository(session)

    return ServiceRegistry(
        session=session,
        settings=settings,
        audit=audit,
        identity=IdentityService(
            settings=settings, users=users, sessions=sessions, tokens=tokens, audit=audit
        ),
        birth_profiles=BirthProfileService(settings=settings, profiles=bp_repo, audit=audit),
        natal=NatalService(
            provider=provider, profiles=bp_repo, natal=natal_repo, audit=audit
        ),
        couples=CoupleService(
            couples=couple_repo,
            memberships=membership_repo,
            invitations=invitation_repo,
            audit=audit,
        ),
        consent=ConsentService(
            consent=consent_repo,
            artifacts=artifact_repo,
            memberships=membership_repo,
            audit=audit,
        ),
        chat=ChatService(
            settings=settings,
            conversations=conversation_repo,
            messages=message_repo,
            read_states=read_state_repo,
            outbox=outbox_repo,
            memberships=membership_repo,
            audit=audit,
            blocks=block_repo,
            retention=retention_repo,
            rate_limiter=rate_limiter,
        ),
        blocks=BlockService(
            blocks=block_repo,
            memberships=membership_repo,
            rate_limiter=rate_limiter,
            audit=audit,
        ),
        reports=ReportService(
            session=session,
            settings=settings,
            reports=report_repo,
            conversations=conversation_repo,
            messages=message_repo,
            memberships=membership_repo,
            retention=retention_repo,
            rate_limiter=rate_limiter,
            audit=audit,
        ),
        devices=DeviceService(devices=device_repo, audit=audit),
        membership_repo=membership_repo,
        couple_repo=couple_repo,
        birth_profile_repo=bp_repo,
    )
