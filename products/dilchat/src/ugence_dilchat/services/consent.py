"""Consent + shared-artifact service (DEC-013 / DEC-028).

A private->shared movement requires (1) an explicit consent event by the content
owner, then (2) creation of an immutable shared artifact holding a bounded snapshot
of the consented projection. The artifact keeps no pointer to the private source, so
deleting that source can never break or re-expose it.
"""

from __future__ import annotations

import datetime as dt
import uuid

from ..audit.service import AuditService
from ..domain.enums import (
    AuditAction,
    ConsentEventType,
    ConsentState,
    MembershipStatus,
    Scope,
    ScopeSlot,
)
from ..errors import DilChatError, ErrorCode
from ..infrastructure.orm import ConsentEvent, SharedArtifact
from ..repositories.consent import ConsentRepository, SharedArtifactRepository
from ..repositories.couples import MembershipRepository
from ..security.scope import authorize_shared


class ConsentService:
    def __init__(
        self,
        *,
        consent: ConsentRepository,
        artifacts: SharedArtifactRepository,
        memberships: MembershipRepository,
        audit: AuditService,
    ) -> None:
        self._consent = consent
        self._artifacts = artifacts
        self._memberships = memberships
        self._audit = audit

    async def _require_active_membership(self, couple_id: uuid.UUID, user_id: uuid.UUID):
        membership = await self._memberships.get_membership(
            couple_id=couple_id, user_id=user_id
        )
        fact = await self._memberships.membership_fact(couple_id=couple_id, user_id=user_id)
        authorize_shared(fact).raise_if_denied()
        return membership

    async def create_consent(
        self,
        *,
        couple_id: uuid.UUID,
        granter_user_id: uuid.UUID,
        artifact_type: str,
        bounded_summary: str,
        purpose: str | None = None,
        correlation_id: str | None = None,
    ) -> ConsentEvent:
        membership = await self._require_active_membership(couple_id, granter_user_id)
        # A granter may only share content from THEIR OWN private scope.
        source_scope = ScopeSlot(membership.scope_slot).private_scope
        event = ConsentEvent(
            couple_id=couple_id,
            granter_user_id=granter_user_id,
            event_type=ConsentEventType.GRANT.value,
            state=ConsentState.GRANTED.value,
            source_scope=source_scope.value,
            artifact_type=artifact_type,
            bounded_summary=bounded_summary,
            purpose=purpose,
        )
        await self._consent.add(event)
        await self._audit.record(
            action=AuditAction.CONSENT_GRANTED,
            actor_user_id=granter_user_id,
            resource_type="consent_event",
            resource_id=event.id,
            couple_id=couple_id,
            scope=source_scope,
            consent_event_id=event.id,
            correlation_id=correlation_id,
        )
        return event

    async def create_shared_artifact(
        self,
        *,
        actor_user_id: uuid.UUID,
        consent_event_id: uuid.UUID,
        payload_snapshot: str,
        correlation_id: str | None = None,
    ) -> SharedArtifact:
        event = await self._consent.get(consent_event_id)
        if event is None:
            raise DilChatError(ErrorCode.NOT_FOUND)
        await self._require_active_membership(event.couple_id, actor_user_id)
        # Only the granter's own consent authorizes sharing their private content.
        if event.granter_user_id != actor_user_id:
            raise DilChatError(ErrorCode.CONSENT_REQUIRED, "Consent was not granted by you.")
        if event.state != ConsentState.GRANTED.value or event.revoked_at is not None:
            raise DilChatError(ErrorCode.CONSENT_REQUIRED, "Consent is not active.")

        artifact = SharedArtifact(
            couple_id=event.couple_id,
            consent_event_id=event.id,
            source_scope=event.source_scope,
            artifact_type=event.artifact_type,
            payload_snapshot=payload_snapshot,  # immutable inline snapshot; no source pointer
            provenance={
                "consent_event_id": str(event.id),
                "source_scope": event.source_scope,
                "artifact_type": event.artifact_type,
                "created_at": dt.datetime.now(dt.UTC).isoformat(),
            },
        )
        await self._artifacts.add(artifact)
        await self._audit.record(
            action=AuditAction.SHARED_ARTIFACT_CREATED,
            actor_user_id=actor_user_id,
            resource_type="shared_artifact",
            resource_id=artifact.id,
            couple_id=event.couple_id,
            scope=Scope.SHARED,
            consent_event_id=event.id,
            correlation_id=correlation_id,
        )
        return artifact

    async def get_shared_artifact(
        self, artifact_id: uuid.UUID, actor_user_id: uuid.UUID
    ) -> SharedArtifact:
        artifact = await self._artifacts.get(artifact_id)
        if artifact is None:
            raise DilChatError(ErrorCode.NOT_FOUND)
        fact = await self._memberships.membership_fact(
            couple_id=artifact.couple_id, user_id=actor_user_id
        )
        # Non-members get 404 (existence non-disclosure); revoked members get 403.
        if fact.status is None:
            raise DilChatError(ErrorCode.NOT_FOUND)
        if fact.status is not MembershipStatus.ACTIVE:
            raise DilChatError(ErrorCode.COUPLE_NOT_ACTIVE, "Couple is no longer active.")
        return artifact
