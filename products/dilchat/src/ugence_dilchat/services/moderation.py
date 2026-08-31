"""Minimal privileged moderation READ-BACK (round PR-D, DEC-PR-4).

Three operations, all read-only: list submitted reports/cases, read one case,
read that case's preserved evidence. Nothing else exists — deliberately.

**The database role is not the human.** ``dilchat_safety`` is an enforcement
posture; every access here requires an individually authenticated
``ReviewerPrincipal``, and the type system makes that unavoidable: no read
function can be called without one. A reviewer never connects to the database
directly, and there is no shared "admin" identity to borrow.

**Every access is audited.** Each read appends immutable
``chat_safety_case_events`` rows attributed to that individual reviewer
(``actor_internal_id``), carrying the reviewer label, role, per-invocation
session id, and a machine-style access reason. Audit metadata is content-free:
it records THAT a case or N evidence items were read, never what they said.

**No adjudication.** There is no state transition, resolution, enforcement, or
assignment path in this round: reports stay ``SUBMITTED`` (DEC-3B-3) and case
state is untouched, so nothing here fabricates a moderation outcome. Reading a
case is not deciding it. A source guard test pins that absence.

**Not a user surface.** No API route may import this module; the reporter-facing
API still cannot read evidence back (DEC-3B-5), and an ordinary support or
operator role has no path here at all.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import re
import secrets
import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from ..base import utcnow
from ..domain.enums import (
    ReviewerRole,
    ReviewerStatus,
    SafetyActorType,
    SafetyCaseEventType,
)
from ..infrastructure.chat_safety_orm import (
    ChatReport,
    ChatReportEvidence,
    ChatSafetyCase,
    ChatSafetyCaseEvent,
    SafetyReviewer,
)
from ..security.passwords import hash_password, verify_password

# Access reasons are machine codes, never free text about a person.
_REASON = re.compile(r"^[A-Z][A-Z0-9_]{2,31}$")


class ModerationAccessError(Exception):
    """Authentication or authorization failure. Message is generic by design."""


@dataclasses.dataclass(frozen=True)
class ReviewerPrincipal:
    """An authenticated individual reviewer. Minted per invocation, never shared."""

    reviewer_id: uuid.UUID
    label: str
    role: str
    authenticated_at: dt.datetime
    session_id: uuid.UUID

    def audit_meta(self, reason: str, **extra: object) -> dict:
        """Content-free provenance recorded on every access."""
        return {
            "reviewer_label": self.label,
            "reviewer_role": self.role,
            "reviewer_session_id": str(self.session_id),
            "authenticated_at": self.authenticated_at.isoformat(),
            "access_reason": reason,
            **extra,
        }


@dataclasses.dataclass(frozen=True)
class CaseSummary:
    """Listing row. IDs, codes, and counts only — no report or evidence text."""

    case_id: uuid.UUID
    state: str
    conversation_id: uuid.UUID | None
    created_at: dt.datetime
    report_count: int
    reasons: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class ReportDetail:
    """One report as a reviewer sees it. ``description`` is the reporter's own
    words: the reviewer surface is the ONLY place it may be read (DEC-3B-5), and
    it must never be logged, audited, or copied elsewhere."""

    report_id: uuid.UUID
    reporter_user_id: uuid.UUID
    target_type: str
    target_message_id: uuid.UUID | None
    reason: str
    status: str
    description: str | None
    created_at: dt.datetime


@dataclasses.dataclass(frozen=True)
class CaseDetail:
    case_id: uuid.UUID
    state: str
    conversation_id: uuid.UUID | None
    couple_id: uuid.UUID | None
    created_at: dt.datetime
    reports: tuple[ReportDetail, ...]


@dataclasses.dataclass(frozen=True)
class EvidenceItem:
    """A preserved message snapshot. ``body_snapshot`` is SENSITIVE."""

    evidence_id: uuid.UUID
    evidence_sequence: int
    source_message_id: uuid.UUID | None
    source_sender_id: uuid.UUID | None
    source_server_sequence: int | None
    source_created_at: dt.datetime | None
    source_deleted_at: dt.datetime | None
    body_snapshot: str


def generate_reviewer_key() -> str:
    """A high-entropy reviewer credential. Shown once; only its hash is stored."""
    return secrets.token_urlsafe(32)


class ModerationService:
    """Read-only moderation access. Exposes no adjudication operation."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    # -- reviewer principals -------------------------------------------------- #

    async def provision_reviewer(self, label: str) -> tuple[SafetyReviewer, str]:
        """Create an individual reviewer and return the one-time key.

        The key is returned to the caller exactly once and never persisted in
        plaintext, logged, or echoed thereafter.
        """
        if not label or len(label) > 64:
            raise ModerationAccessError("invalid reviewer label")
        key = generate_reviewer_key()
        reviewer = SafetyReviewer(
            label=label,
            credential_hash=hash_password(key),
            role=ReviewerRole.READ_ONLY_REVIEWER.value,
            status=ReviewerStatus.ACTIVE.value,
        )
        self._s.add(reviewer)
        await self._s.flush()
        return reviewer, key

    async def revoke_reviewer(self, label: str) -> bool:
        row = await self._s.scalar(
            sa.select(SafetyReviewer).where(SafetyReviewer.label == label)
        )
        if row is None or row.status == ReviewerStatus.REVOKED.value:
            return False
        row.status = ReviewerStatus.REVOKED.value
        row.revoked_at = utcnow()
        await self._s.flush()
        return True

    async def authenticate(self, label: str, key: str) -> ReviewerPrincipal:
        """Authenticate one individual reviewer.

        Failure is a single generic error whatever went wrong (unknown label,
        wrong key, revoked reviewer) — the surface never discloses which.
        """
        row = await self._s.scalar(
            sa.select(SafetyReviewer).where(SafetyReviewer.label == label)
        )
        # Verify even when the label is unknown, against a dummy hash, so the
        # failure path costs the same either way.
        stored = row.credential_hash if row is not None else hash_password("unused-placeholder")
        valid = verify_password(key, stored)
        if row is None or not valid or row.status != ReviewerStatus.ACTIVE.value:
            raise ModerationAccessError("reviewer authentication failed")
        now = utcnow()
        row.last_authenticated_at = now
        await self._s.flush()
        return ReviewerPrincipal(
            reviewer_id=row.id,
            label=row.label,
            role=row.role,
            authenticated_at=now,
            session_id=uuid.uuid4(),
        )

    # -- audited reads -------------------------------------------------------- #

    def _require_reason(self, reason: str) -> str:
        if not _REASON.fullmatch(reason or ""):
            raise ModerationAccessError(
                "access reason must be a machine-style code (A-Z0-9_), never free text"
            )
        return reason

    def _record(
        self,
        principal: ReviewerPrincipal,
        *,
        case_id: uuid.UUID,
        event_type: SafetyCaseEventType,
        reason: str,
        **extra: object,
    ) -> None:
        self._s.add(
            ChatSafetyCaseEvent(
                case_id=case_id,
                event_type=event_type.value,
                actor_type=SafetyActorType.SAFETY.value,
                actor_internal_id=principal.reviewer_id,
                meta=principal.audit_meta(reason, **extra),
            )
        )

    async def list_cases(
        self,
        principal: ReviewerPrincipal,
        *,
        reason: str,
        limit: int = 50,
    ) -> list[CaseSummary]:
        """List cases with their linked report counts, newest first."""
        self._require_reason(reason)
        limit = max(1, min(int(limit), 200))
        cases = list(
            (
                await self._s.execute(
                    sa.select(ChatSafetyCase)
                    .order_by(ChatSafetyCase.created_at.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        summaries: list[CaseSummary] = []
        for case in cases:
            reports = list(
                (
                    await self._s.execute(
                        sa.select(ChatReport.reason).where(ChatReport.case_id == case.id)
                    )
                )
                .scalars()
                .all()
            )
            summaries.append(
                CaseSummary(
                    case_id=case.id,
                    state=case.state,
                    conversation_id=case.conversation_id,
                    created_at=case.created_at,
                    report_count=len(reports),
                    reasons=tuple(sorted(set(reports))),
                )
            )
            # Auditing the listing per case keeps every case's own trail complete.
            self._record(
                principal,
                case_id=case.id,
                event_type=SafetyCaseEventType.CASE_ACCESSED,
                reason=reason,
                access_scope="LIST",
            )
        await self._s.flush()
        return summaries

    async def read_case(
        self, principal: ReviewerPrincipal, case_id: uuid.UUID, *, reason: str
    ) -> CaseDetail:
        """Read one case and its linked reports. Never changes case state."""
        self._require_reason(reason)
        case = await self._s.get(ChatSafetyCase, case_id)
        if case is None:
            raise ModerationAccessError("case not found")
        reports = list(
            (
                await self._s.execute(
                    sa.select(ChatReport)
                    .where(ChatReport.case_id == case.id)
                    .order_by(ChatReport.created_at)
                )
            )
            .scalars()
            .all()
        )
        self._record(
            principal,
            case_id=case.id,
            event_type=SafetyCaseEventType.CASE_ACCESSED,
            reason=reason,
            access_scope="DETAIL",
            report_count=len(reports),
        )
        await self._s.flush()
        return CaseDetail(
            case_id=case.id,
            state=case.state,
            conversation_id=case.conversation_id,
            couple_id=case.couple_id,
            created_at=case.created_at,
            reports=tuple(
                ReportDetail(
                    report_id=r.id,
                    reporter_user_id=r.reporter_user_id,
                    target_type=r.target_type,
                    target_message_id=r.target_message_id,
                    reason=r.reason,
                    status=r.status,
                    description=r.description,
                    created_at=r.created_at,
                )
                for r in reports
            ),
        )

    async def read_evidence(
        self, principal: ReviewerPrincipal, report_id: uuid.UUID, *, reason: str
    ) -> list[EvidenceItem]:
        """Read the evidence preserved with one report, in captured order."""
        self._require_reason(reason)
        report = await self._s.get(ChatReport, report_id)
        if report is None:
            raise ModerationAccessError("report not found")
        rows = list(
            (
                await self._s.execute(
                    sa.select(ChatReportEvidence)
                    .where(ChatReportEvidence.report_id == report_id)
                    .order_by(ChatReportEvidence.evidence_sequence)
                )
            )
            .scalars()
            .all()
        )
        # Content-free audit: how many items were read, never what they said.
        self._record(
            principal,
            case_id=report.case_id,
            event_type=SafetyCaseEventType.EVIDENCE_ACCESSED,
            reason=reason,
            report_id=str(report_id),
            evidence_count=len(rows),
        )
        await self._s.flush()
        return [
            EvidenceItem(
                evidence_id=r.id,
                evidence_sequence=r.evidence_sequence,
                source_message_id=r.source_message_id,
                source_sender_id=r.source_sender_id,
                source_server_sequence=r.source_server_sequence,
                source_created_at=r.source_created_at,
                source_deleted_at=r.source_deleted_at,
                body_snapshot=r.body_snapshot,
            )
            for r in rows
        ]
