"""Ontology service — publish/retire/supersede/lookup capabilities.

Enforces hierarchy integrity (parent existence, no cycles) and immutability, and
audits every governance action. Capabilities are definitions; nothing here
scores or evaluates.
"""

from __future__ import annotations

from typing import Optional

from ..common import new_id
from ..domain.enums import ActorType, AuditEventType
from ..errors import CapabilityNotFoundError, OntologyError
from ..ontology.capability import Capability, CapabilityStatus
from ..ontology.registry import CapabilityGraph, build_graph
from ..repositories.ontology_repository import OntologyRepository
from .audit_service import AuditService


class OntologyService:
    def __init__(self, repository: OntologyRepository, audit_service: AuditService) -> None:
        self._repo = repository
        self._audit = audit_service

    def _validate_hierarchy(self, capability: Capability) -> None:
        if capability.parent_id is not None:
            if not self._repo.exists(capability.parent_id):
                raise CapabilityNotFoundError(
                    f"parent capability '{capability.parent_id}' does not exist")
            parent = self._repo.get(capability.parent_id)
            if parent.status not in (CapabilityStatus.PUBLISHED,
                                     CapabilityStatus.DEPRECATED):
                raise OntologyError(
                    f"parent '{capability.parent_id}' must be published before a child")
        # whole-graph cycle check including the candidate
        existing = [c for c in self._repo.list_latest()
                    if c.capability_id != capability.capability_id]
        build_graph(tuple(existing) + (capability,)).validate()

    def publish(
        self, capability: Capability, *, actor_id: str, correlation_id: Optional[str] = None
    ) -> Capability:
        """Validate and publish an immutable capability."""
        published = Capability(**{**capability.model_dump(),
                                  "status": CapabilityStatus.PUBLISHED})
        self._validate_hierarchy(published)
        stored = self._repo.add(published)
        self._audit.record(
            event_type=AuditEventType.CAPABILITY_PUBLISHED, entity_type="capability",
            entity_id=stored.capability_id, actor_type=ActorType.HUMAN, actor_id=actor_id,
            correlation_id=correlation_id or new_id("corr"),
            new_state=CapabilityStatus.PUBLISHED.value,
            payload={"version": stored.version, "category": stored.category})
        return stored

    def retire(
        self, capability_id: str, *, actor_id: str, correlation_id: Optional[str] = None
    ) -> Capability:
        current = self._repo.get(capability_id)
        retired = current.as_status(CapabilityStatus.RETIRED, deprecated=True)
        stored = self._repo.add(retired)
        self._audit.record(
            event_type=AuditEventType.CAPABILITY_RETIRED, entity_type="capability",
            entity_id=capability_id, actor_type=ActorType.HUMAN, actor_id=actor_id,
            correlation_id=correlation_id or new_id("corr"),
            new_state=CapabilityStatus.RETIRED.value, payload={"version": stored.version})
        return stored

    def supersede(
        self, old_capability_id: str, new_capability: Capability, *, actor_id: str,
        correlation_id: Optional[str] = None,
    ) -> Capability:
        """Publish a replacement capability and mark the old one SUPERSEDED."""
        corr = correlation_id or new_id("corr")
        old = self._repo.get(old_capability_id)
        replacement = Capability(**{**new_capability.model_dump(),
                                    "status": CapabilityStatus.PUBLISHED,
                                    "supersedes": old_capability_id})
        self._validate_hierarchy(replacement)
        stored = self._repo.add(replacement)
        self._repo.add(old.as_status(CapabilityStatus.SUPERSEDED, deprecated=True))
        self._audit.record(
            event_type=AuditEventType.CAPABILITY_SUPERSEDED, entity_type="capability",
            entity_id=old_capability_id, actor_type=ActorType.HUMAN, actor_id=actor_id,
            correlation_id=corr, new_state=CapabilityStatus.SUPERSEDED.value,
            payload={"superseded_by": stored.capability_id})
        return stored

    # --- reads -------------------------------------------------------------
    def get(self, capability_id: str) -> Capability:
        return self._repo.get(capability_id)

    def get_version(self, capability_id: str, version: int) -> Capability:
        return self._repo.get_version(capability_id, version)

    def history(self, capability_id: str) -> tuple[Capability, ...]:
        return self._repo.versions_of(capability_id)

    def list(self) -> tuple[Capability, ...]:
        return self._repo.list_latest()

    def by_status(self, status: CapabilityStatus) -> tuple[Capability, ...]:
        return self._repo.by_status(status)

    def graph(self) -> CapabilityGraph:
        return build_graph(self._repo.list_latest())
