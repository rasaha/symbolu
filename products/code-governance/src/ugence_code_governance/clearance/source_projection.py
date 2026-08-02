"""Immutable trusted-signal source-registry projection.

``TrustedSignalSourceProjection`` is an **immutable** projection the product
consumes — never a mutable source-registry service or database. It declares, per
signal type, the approved source/adapter identity and the maximum trust level a
signal of that type may claim. The signal adapter fails closed when a fact has no
approved source, an unapproved adapter version, or claims a trust level above what
the source is authorized for.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

from ugence_action_clearance import SignalTrustLevel, SignalType  # type: ignore

_TRUST_ORDER = {
    SignalTrustLevel.LEVEL_1_TRUSTED_INGESTION: 1,
    SignalTrustLevel.LEVEL_2_AUTHENTICATED_ENVELOPE: 2,
    SignalTrustLevel.LEVEL_3_SIGNED_PRODUCER: 3,
}


@dataclass(frozen=True)
class SignalSourceEntry:
    """The approved source metadata for one signal type."""

    source_id: str
    source_kind: str
    adapter_id: str
    adapter_version: str
    ingestion_boundary: str
    provenance_ref: str
    max_trust_level: SignalTrustLevel
    approved_adapter_versions: Tuple[str, ...] = ()

    def version_approved(self) -> bool:
        return (not self.approved_adapter_versions
                or self.adapter_version in self.approved_adapter_versions)

    def trust_within_max(self, claimed: SignalTrustLevel) -> bool:
        return _TRUST_ORDER[claimed] <= _TRUST_ORDER[self.max_trust_level]


@dataclass(frozen=True)
class TrustedSignalSourceProjection:
    """An immutable per-signal-type source projection bound to a tenant."""

    projection_id: str
    projection_version: str
    tenant_id: str
    entries: Mapping[SignalType, SignalSourceEntry] = field(default_factory=dict)
    subject_binding_required: bool = True
    policy_refs: Tuple[str, ...] = ()

    def entry_for(self, signal_type: SignalType) -> Optional[SignalSourceEntry]:
        return self.entries.get(signal_type)

    @property
    def projection_ref(self) -> str:
        return f"{self.projection_id}:{self.projection_version}"


__all__ = ["SignalSourceEntry", "TrustedSignalSourceProjection"]
