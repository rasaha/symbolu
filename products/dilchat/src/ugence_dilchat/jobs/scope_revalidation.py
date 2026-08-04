"""DEC-027: background jobs re-validate scope immediately before writing.

Authorization captured when a job was *queued* is not sufficient. Before any SHARED
write, the job re-reads the current membership fact inside the write transaction and
aborts (auditing the abort) if authorization has since been revoked (e.g. the couple
unpaired between enqueue and execution).
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..audit.service import AuditService
from ..domain.enums import AuditAction, AuthzOutcome, Scope
from ..repositories.couples import MembershipRepository
from ..security.scope import authorize_job_write


class JobScopeRevoked(Exception):
    """Raised when a job's shared-write authorization was revoked before execution."""


async def run_shared_write_job(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    couple_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    write_fn: Callable[[AsyncSession], Awaitable[None]],
    correlation_id: str | None = None,
) -> None:
    """Run ``write_fn`` only if the actor still has active membership at write time."""
    async with sessionmaker() as session:
        try:
            memberships = MembershipRepository(session)
            fact = await memberships.membership_fact(
                couple_id=couple_id, user_id=actor_user_id
            )
            result = authorize_job_write(fact)
            if not result.allowed:
                await AuditService(session).record(
                    action=AuditAction.JOB_WRITE_ABORTED_SCOPE,
                    actor_user_id=actor_user_id,
                    resource_type="couple",
                    resource_id=couple_id,
                    couple_id=couple_id,
                    scope=Scope.SHARED,
                    outcome=AuthzOutcome.DENY,
                    denial_reason_code=result.reason_code,
                    correlation_id=correlation_id,
                )
                await session.commit()
                raise JobScopeRevoked(result.reason_code)
            await write_fn(session)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
