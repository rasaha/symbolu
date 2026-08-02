"""Immutable adapter-registry projection.

The registry is a **resolved, immutable projection** consumed during a pilot — not
a mutable policy-administration database. Per adapter it declares the approved
source identity, approved versions, approved hosts/endpoints, approved signal
types, the maximum trust level a signal may claim, freshness/response limits, and
the credential-resolver *reference* (never the credential itself). Authorization
fails closed: an unregistered adapter/source, an unapproved version, or an
over-claimed trust level is refused.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

from ugence_action_clearance import SignalTrustLevel  # type: ignore

from .errors import AdapterConfigurationError
from .transport import TransportPolicy

_TRUST_ORDER = {
    SignalTrustLevel.LEVEL_1_TRUSTED_INGESTION: 1,
    SignalTrustLevel.LEVEL_2_AUTHENTICATED_ENVELOPE: 2,
    SignalTrustLevel.LEVEL_3_SIGNED_PRODUCER: 3,
}


@dataclass(frozen=True)
class AdapterRegistryEntry:
    """The approved configuration for one registered adapter/source."""

    adapter_id: str
    adapter_version: str
    source_id: str
    source_kind: str
    approved_signal_types: Tuple[str, ...]
    max_trust_level: SignalTrustLevel
    approved_adapter_versions: Tuple[str, ...] = ()
    approved_hosts: Tuple[str, ...] = ()
    approved_path_prefixes: Tuple[str, ...] = ()
    allow_head: bool = False
    max_response_bytes: int = 1_000_000
    timeout_s: float = 10.0
    allowed_content_types: Tuple[str, ...] = ("application/json",)
    max_redirects: int = 0
    freshness_max_age_s: int = 3600
    credential_resolver_ref: str = ""  # a *reference*, never the credential
    enabled: bool = True
    policy_refs: Tuple[str, ...] = ()

    def version_approved(self) -> bool:
        return (not self.approved_adapter_versions
                or self.adapter_version in self.approved_adapter_versions)

    def trust_within_max(self, claimed: SignalTrustLevel) -> bool:
        return _TRUST_ORDER[claimed] <= _TRUST_ORDER[self.max_trust_level]

    def transport_policy(self) -> TransportPolicy:
        return TransportPolicy(
            allowed_hosts=self.approved_hosts,
            allowed_path_prefixes=self.approved_path_prefixes,
            allow_head=self.allow_head,
            max_response_bytes=self.max_response_bytes,
            timeout_s=self.timeout_s,
            allowed_content_types=self.allowed_content_types,
            max_redirects=self.max_redirects)


@dataclass(frozen=True)
class AdapterRegistryProjection:
    """An immutable, tenant-bound projection of the approved adapter set."""

    registry_id: str
    registry_version: str
    tenant_id: str
    entries: Mapping[str, AdapterRegistryEntry] = field(default_factory=dict)
    policy_refs: Tuple[str, ...] = ()

    @property
    def projection_ref(self) -> str:
        return f"{self.registry_id}:{self.registry_version}"

    def entry_for(self, adapter_id: str) -> Optional[AdapterRegistryEntry]:
        return self.entries.get(adapter_id)

    def authorize(self, *, tenant_id: str, adapter_id: str, adapter_version: str,
                  source_id: str) -> AdapterRegistryEntry:
        """Return the approved entry or fail closed.

        Refuses cross-tenant use, an unregistered adapter, an unregistered source,
        a disabled adapter, or an unapproved version.
        """
        if self.tenant_id != tenant_id:
            raise AdapterConfigurationError("registry tenant does not match request tenant")
        entry = self.entries.get(adapter_id)
        if entry is None:
            raise AdapterConfigurationError(f"adapter {adapter_id!r} is not registered")
        if not entry.enabled:
            raise AdapterConfigurationError(f"adapter {adapter_id!r} is disabled")
        if entry.source_id != source_id:
            raise AdapterConfigurationError(
                f"source {source_id!r} is not registered for adapter {adapter_id!r}")
        if entry.adapter_version != adapter_version or not entry.version_approved():
            raise AdapterConfigurationError(
                f"adapter version {adapter_version!r} is not approved")
        return entry


__all__ = ["AdapterRegistryEntry", "AdapterRegistryProjection"]
