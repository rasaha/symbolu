"""Repository contracts (ports) for durable risk-authority state (spec §26).

Services depend on these Protocols, not on a concrete store, so the same logic
runs against the in-memory reference (tests, demo) and a Postgres-backed store
(production) without change. Authority-changing writes require strong
consistency (spec §26); the in-memory store trivially satisfies that, and the
Postgres skeleton documents the DDL.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from ..domain.actions import ActionAuthorization
from ..domain.authority import AuthorityGrant
from ..domain.controls import ControlResult
from ..domain.decision import RiskDecision
from ..domain.envelope import RiskAuthorizationEnvelope
from ..domain.events import GovernanceEvent
from ..domain.evidence import ControlEvidenceRecord
from ..domain.risk_case import RiskDecisionCase

__all__ = [
    "RiskCaseRepository",
    "DecisionRepository",
    "EnvelopeRepository",
    "AuthorityRegistry",
    "ControlResultRepository",
    "EvidenceRepository",
    "GovernanceEventStore",
    "AuthorizationRepository",
]


@runtime_checkable
class RiskCaseRepository(Protocol):
    def save(self, case: RiskDecisionCase) -> None: ...
    def get(self, tenant_id: str, case_id: str) -> Optional[RiskDecisionCase]: ...


@runtime_checkable
class DecisionRepository(Protocol):
    def save(self, decision: RiskDecision) -> None: ...
    def get(self, tenant_id: str, decision_id: str) -> Optional[RiskDecision]: ...


@runtime_checkable
class EnvelopeRepository(Protocol):
    def save(self, envelope: RiskAuthorizationEnvelope) -> None: ...
    def get(
        self, tenant_id: str, envelope_id: str
    ) -> Optional[RiskAuthorizationEnvelope]: ...


@runtime_checkable
class AuthorityRegistry(Protocol):
    def add_grant(self, grant: AuthorityGrant) -> None: ...
    def get_grant(
        self, tenant_id: str, principal_id: str
    ) -> Optional[AuthorityGrant]: ...


@runtime_checkable
class ControlResultRepository(Protocol):
    def put(self, tenant_id: str, case_id: str, results: tuple[ControlResult, ...]) -> None: ...
    def get(self, tenant_id: str, case_id: str) -> tuple[ControlResult, ...]: ...


@runtime_checkable
class EvidenceRepository(Protocol):
    def save(self, evidence: ControlEvidenceRecord) -> None: ...
    def get(
        self, tenant_id: str, evidence_id: str
    ) -> Optional[ControlEvidenceRecord]: ...


@runtime_checkable
class AuthorizationRepository(Protocol):
    """Phase 5C admissions (D-3). ``save`` refuses an existing id whose stored
    ``action_digest`` differs; the same id with the same digest is idempotent."""

    def save(self, authorization: ActionAuthorization) -> None: ...
    def get(
        self, tenant_id: str, authorization_id: str
    ) -> Optional[ActionAuthorization]: ...


@runtime_checkable
class GovernanceEventStore(Protocol):
    def append(self, event: GovernanceEvent) -> None: ...
    def for_aggregate(
        self, tenant_id: str, aggregate_id: str
    ) -> tuple[GovernanceEvent, ...]: ...
