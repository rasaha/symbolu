"""Audit service: append-only recording of sensitive actions.

Audit rows never contain secrets, tokens, passwords, or raw sensitive payloads.
Only identifiers, action/outcome codes, scope, correlation id, consent id, and
non-sensitive calculation provenance are recorded.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.enums import AuditAction, AuthzOutcome, Scope
from ..infrastructure.orm import AuditEvent

# Provenance keys that are safe to persist in audit (no PII / secrets).
_SAFE_PROVENANCE_KEYS = {
    "provider_id",
    "provider_version",
    "ephemeris_mode",
    "ayanamsa",
    "numerical_precision_class",
    "fallback_used",
    "fallback_reason",
    "input_confidence",
    "time_assumption",
    "rule_pack_id",
    "provider_kind",
    "synthetic_calculation",
    "guna_eligibility",
}


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def record(
        self,
        *,
        action: AuditAction,
        actor_user_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | uuid.UUID | None = None,
        scope: Scope | None = None,
        couple_id: uuid.UUID | None = None,
        outcome: AuthzOutcome = AuthzOutcome.ALLOW,
        denial_reason_code: str | None = None,
        consent_event_id: uuid.UUID | None = None,
        correlation_id: str | None = None,
        provenance: dict | None = None,
    ) -> AuditEvent:
        safe_prov = None
        if provenance:
            safe_prov = {k: v for k, v in provenance.items() if k in _SAFE_PROVENANCE_KEYS}
        row = AuditEvent(
            action=action.value,
            actor_user_id=actor_user_id,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            scope=scope.value if scope else None,
            couple_id=couple_id,
            outcome=outcome.value,
            denial_reason_code=denial_reason_code,
            consent_event_id=consent_event_id,
            correlation_id=correlation_id,
            provenance=safe_prov,
        )
        self._s.add(row)
        await self._s.flush()
        return row
