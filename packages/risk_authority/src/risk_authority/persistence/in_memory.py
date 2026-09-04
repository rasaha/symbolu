"""In-memory reference implementations of the repository contracts.

Tenant-scoped by construction: every key is ``(tenant_id, id)`` so a lookup can
never resolve across tenant boundaries (spec §39). Suitable for the conformance
suite and the MVP demo; production uses the Postgres-backed store.
"""

from __future__ import annotations

from typing import Optional

from ..domain.actions import ActionAuthorization
from ..domain.authority import AuthorityGrant
from ..domain.controls import ControlResult
from ..domain.decision import RiskDecision
from ..domain.envelope import RiskAuthorizationEnvelope
from ..domain.events import GovernanceEvent
from ..domain.evidence import ControlEvidenceRecord
from ..domain.risk_case import RiskDecisionCase

__all__ = [
    "InMemoryRiskCaseRepository",
    "InMemoryDecisionRepository",
    "InMemoryEnvelopeRepository",
    "InMemoryAuthorityRegistry",
    "InMemoryControlResultRepository",
    "InMemoryEvidenceRepository",
    "InMemoryGovernanceEventStore",
    "InMemoryAuthorizationRepository",
]


class InMemoryRiskCaseRepository:
    def __init__(self) -> None:
        self._cases: dict[tuple[str, str], RiskDecisionCase] = {}

    def save(self, case: RiskDecisionCase) -> None:
        self._cases[(case.tenant_id, case.case_id)] = case

    def get(self, tenant_id: str, case_id: str) -> Optional[RiskDecisionCase]:
        return self._cases.get((tenant_id, case_id))


class InMemoryDecisionRepository:
    def __init__(self) -> None:
        self._decisions: dict[tuple[str, str], RiskDecision] = {}

    def save(self, decision: RiskDecision) -> None:
        self._decisions[(decision.tenant_id, decision.decision_id)] = decision

    def get(self, tenant_id: str, decision_id: str) -> Optional[RiskDecision]:
        return self._decisions.get((tenant_id, decision_id))


class InMemoryEnvelopeRepository:
    def __init__(self) -> None:
        self._envelopes: dict[tuple[str, str], RiskAuthorizationEnvelope] = {}

    def save(self, envelope: RiskAuthorizationEnvelope) -> None:
        self._envelopes[(envelope.tenant_id, envelope.envelope_id)] = envelope

    def get(
        self, tenant_id: str, envelope_id: str
    ) -> Optional[RiskAuthorizationEnvelope]:
        return self._envelopes.get((tenant_id, envelope_id))


class InMemoryAuthorityRegistry:
    def __init__(self) -> None:
        self._grants: dict[tuple[str, str], AuthorityGrant] = {}

    def add_grant(self, grant: AuthorityGrant) -> None:
        self._grants[(grant.tenant_id, grant.principal_id)] = grant

    def get_grant(
        self, tenant_id: str, principal_id: str
    ) -> Optional[AuthorityGrant]:
        return self._grants.get((tenant_id, principal_id))


class InMemoryControlResultRepository:
    def __init__(self) -> None:
        self._results: dict[tuple[str, str], tuple[ControlResult, ...]] = {}

    def put(
        self, tenant_id: str, case_id: str, results: tuple[ControlResult, ...]
    ) -> None:
        self._results[(tenant_id, case_id)] = tuple(results)

    def get(self, tenant_id: str, case_id: str) -> tuple[ControlResult, ...]:
        return self._results.get((tenant_id, case_id), ())


class InMemoryEvidenceRepository:
    def __init__(self) -> None:
        self._evidence: dict[tuple[str, str], ControlEvidenceRecord] = {}

    def save(self, evidence: ControlEvidenceRecord) -> None:
        self._evidence[(evidence.tenant_id, evidence.evidence_id)] = evidence

    def get(
        self, tenant_id: str, evidence_id: str
    ) -> Optional[ControlEvidenceRecord]:
        return self._evidence.get((tenant_id, evidence_id))


class InMemoryAuthorizationRepository:
    def __init__(self) -> None:
        self._authorizations: dict[tuple[str, str], ActionAuthorization] = {}

    def save(self, authorization: ActionAuthorization) -> None:
        key = (authorization.tenant_id, authorization.authorization_id)
        stored = self._authorizations.get(key)
        if stored is not None:
            if stored.action_digest != authorization.action_digest:
                from .errors import PersistenceConflictError

                raise PersistenceConflictError(
                    f"authorization {authorization.authorization_id!r} exists for tenant "
                    f"{authorization.tenant_id!r} with another action digest")
            return
        self._authorizations[key] = authorization

    def get(self, tenant_id: str, authorization_id: str) -> Optional[ActionAuthorization]:
        return self._authorizations.get((tenant_id, authorization_id))


class InMemoryGovernanceEventStore:
    def __init__(self) -> None:
        self._events: list[GovernanceEvent] = []

    def append(self, event: GovernanceEvent) -> None:
        self._events.append(event)

    def for_aggregate(
        self, tenant_id: str, aggregate_id: str
    ) -> tuple[GovernanceEvent, ...]:
        return tuple(
            e
            for e in self._events
            if e.tenant_id == tenant_id and e.aggregate_id == aggregate_id
        )

    def all(self) -> tuple[GovernanceEvent, ...]:
        return tuple(self._events)
