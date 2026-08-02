"""Immutable, credential-free models for read-only enterprise adapters.

An ``AdapterRequest`` binds the exact governed change + requested signal types. An
``AdapterResult`` is **data only**: collected facts, provenance, freshness, and a
read-only guarantee. Neither model ever carries a credential, token, secret, or
authorization header — those live only inside the transport boundary and never
cross into a result, a fingerprint, an error, or the durable store.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Optional, Tuple

from ..fingerprints import domain_hash
from .errors import AdapterFailureCode

#: Fingerprint domains for the adapter layer (domain-separated SHA-256).
DOMAIN_ADAPTER_REQUEST = "cg.adapter.request.v1"
DOMAIN_ADAPTER_RESULT = "cg.adapter.result.v1"
DOMAIN_SOURCE_RESPONSE = "cg.adapter.source_response.v1"


class FactConsistency(str, Enum):
    """How much a collected source fact can be relied upon."""

    AUTHORITATIVE = "AUTHORITATIVE"
    EVENTUALLY_CONSISTENT = "EVENTUALLY_CONSISTENT"
    ADVISORY = "ADVISORY"
    UNAVAILABLE = "UNAVAILABLE"


class AdapterFetchStatus(str, Enum):
    """Overall status of an adapter collection attempt."""

    OK = "OK"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


@dataclass(frozen=True)
class AdapterIdentity:
    """Identity of the adapter implementation that produced a result."""

    adapter_id: str
    adapter_version: str
    source_kind: str


@dataclass(frozen=True)
class AdapterSourceIdentity:
    """Identity of the enterprise source an adapter read from."""

    source_id: str
    source_kind: str
    endpoint_class: str = "supplied-snapshot"


@dataclass(frozen=True)
class AdapterCapability:
    """What signal types an adapter is capable of producing."""

    adapter_id: str
    source_kind: str
    produced_signal_types: Tuple[str, ...] = ()
    read_only: bool = True


@dataclass(frozen=True)
class CollectedSignalFact:
    """One normalized, governance-relevant fact from a source (no raw payload)."""

    signal_type: str
    value: Mapping[str, Any]
    consistency: FactConsistency
    observed_at: Optional[datetime] = None
    note: str = ""


@dataclass(frozen=True)
class ProvenanceMetadata:
    """Non-cryptographic provenance for an adapter result."""

    adapter_id: str
    adapter_version: str
    source_id: str
    source_kind: str
    endpoint_class: str
    registry_projection_version: str
    source_response_fingerprint: str


@dataclass(frozen=True)
class AdapterRequest:
    """An immutable request binding an adapter collection to a governed change."""

    tenant_id: str
    workflow_id: str
    workflow_revision_id: str
    repository: str
    pull_request_number: int
    base_sha: str
    head_sha: str
    target_branch: str
    prepared_action_fingerprint: str
    authorization_fingerprint: str
    requested_signal_types: Tuple[str, ...]
    collection_time: datetime
    source_config_ref: str

    @property
    def request_fingerprint(self) -> str:
        """Content-addressed request id (excludes credentials and transport timing)."""
        return domain_hash(DOMAIN_ADAPTER_REQUEST, {
            "tenant_id": self.tenant_id,
            "workflow_id": self.workflow_id,
            "workflow_revision_id": self.workflow_revision_id,
            "repository": self.repository,
            "pull_request_number": self.pull_request_number,
            "base_sha": self.base_sha,
            "head_sha": self.head_sha,
            "target_branch": self.target_branch,
            "prepared_action_fingerprint": self.prepared_action_fingerprint,
            "authorization_fingerprint": self.authorization_fingerprint,
            "requested_signal_types": sorted(self.requested_signal_types),
            "source_config_ref": self.source_config_ref,
        })


@dataclass(frozen=True)
class AdapterResult:
    """The immutable, data-only outcome of one adapter collection."""

    adapter: AdapterIdentity
    source: AdapterSourceIdentity
    requested_signal_types: Tuple[str, ...]
    collected_facts: Tuple[CollectedSignalFact, ...]
    captured_at: datetime
    valid_until: datetime
    fetch_status: AdapterFetchStatus
    failure_codes: Tuple[AdapterFailureCode, ...]
    provenance: ProvenanceMetadata
    read_only: bool = True

    @property
    def ok(self) -> bool:
        return self.fetch_status is AdapterFetchStatus.OK and not self.failure_codes

    @property
    def result_fingerprint(self) -> str:
        """Content-addressed result id (excludes credentials + transport timing)."""
        return domain_hash(DOMAIN_ADAPTER_RESULT, {
            "adapter_id": self.adapter.adapter_id,
            "adapter_version": self.adapter.adapter_version,
            "source_id": self.source.source_id,
            "source_kind": self.source.source_kind,
            "requested_signal_types": sorted(self.requested_signal_types),
            "facts": sorted(
                (f.signal_type, f.consistency.value,
                 tuple(sorted((str(k), str(v)) for k, v in f.value.items())))
                for f in self.collected_facts),
            "fetch_status": self.fetch_status.value,
            "failure_codes": sorted(c.value for c in self.failure_codes),
            "source_response_fingerprint": self.provenance.source_response_fingerprint,
            "registry_projection_version": self.provenance.registry_projection_version,
        })


def source_response_fingerprint(normalized_response: Mapping[str, Any]) -> str:
    """Deterministic fingerprint over a normalized source response (no credentials)."""
    return domain_hash(DOMAIN_SOURCE_RESPONSE, normalized_response)


__all__ = [
    "FactConsistency",
    "AdapterFetchStatus",
    "AdapterIdentity",
    "AdapterSourceIdentity",
    "AdapterCapability",
    "CollectedSignalFact",
    "ProvenanceMetadata",
    "AdapterRequest",
    "AdapterResult",
    "source_response_fingerprint",
    "DOMAIN_ADAPTER_REQUEST",
    "DOMAIN_ADAPTER_RESULT",
    "DOMAIN_SOURCE_RESPONSE",
]
