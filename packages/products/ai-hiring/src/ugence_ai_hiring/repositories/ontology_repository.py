"""Capability ontology repository (port + in-memory adapter).

Capabilities are immutable and versioned; a published version can never be
overwritten. Stores full version history and supports lookup by latest version,
by specific version, and by status.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from ..errors import CapabilityNotFoundError, VersionConflictError
from ..ontology.capability import Capability, CapabilityStatus


@runtime_checkable
class OntologyRepository(Protocol):
    def add(self, capability: Capability) -> Capability: ...
    def get(self, capability_id: str) -> Capability: ...
    def get_version(self, capability_id: str, version: int) -> Capability: ...
    def exists(self, capability_id: str) -> bool: ...
    def versions_of(self, capability_id: str) -> tuple[Capability, ...]: ...
    def list_latest(self) -> tuple[Capability, ...]: ...
    def by_status(self, status: CapabilityStatus) -> tuple[Capability, ...]: ...


class InMemoryOntologyRepository:
    def __init__(self) -> None:
        self._data: dict[str, dict[int, Capability]] = {}

    def add(self, capability: Capability) -> Capability:
        versions = self._data.setdefault(capability.capability_id, {})
        if capability.version in versions:
            raise VersionConflictError(
                f"capability '{capability.capability_id}' version "
                f"{capability.version} already exists; capabilities are immutable")
        versions[capability.version] = capability
        return capability

    def get(self, capability_id: str) -> Capability:
        versions = self._data.get(capability_id)
        if not versions:
            raise CapabilityNotFoundError(f"capability '{capability_id}' not found")
        return versions[max(versions)]

    def get_version(self, capability_id: str, version: int) -> Capability:
        versions = self._data.get(capability_id)
        if not versions or version not in versions:
            raise CapabilityNotFoundError(
                f"capability '{capability_id}' version {version} not found")
        return versions[version]

    def exists(self, capability_id: str) -> bool:
        return capability_id in self._data

    def versions_of(self, capability_id: str) -> tuple[Capability, ...]:
        versions = self._data.get(capability_id, {})
        return tuple(versions[v] for v in sorted(versions))

    def list_latest(self) -> tuple[Capability, ...]:
        return tuple(self.get(cid) for cid in sorted(self._data))

    def by_status(self, status: CapabilityStatus) -> tuple[Capability, ...]:
        return tuple(c for c in self.list_latest() if c.status is status)
