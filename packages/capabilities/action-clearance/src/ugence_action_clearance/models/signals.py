"""Trusted-signal models (design §8, §9; merged trusted_signal schema).

A ``TrustedSignal`` is immutable, tenant-bound, subject-bound, time-bound,
source-identified, integrity-verifiable, freshness-evaluable, deterministically
serializable, and content-fingerprinted. It carries no credentials, secrets,
network clients, or provider SDK objects — only normalized data and references.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional, Tuple

from ..errors import ValidationError
from ..fingerprinting import (
    signal_bundle_fingerprint,
    signal_content_fingerprint,
    signal_provenance_fingerprint,
)
from ..normalization import normalize_timestamp
from .enums import SignalStatus, SignalTrustLevel, SignalType


@dataclass(frozen=True)
class SignalProvenance:
    """Additive provenance/integrity projection over a trusted signal.

    Consumed (never fetched). The evaluator validates that required provenance
    fields + trust level are present and policy-compliant; it does NOT verify PKI,
    retrieve keys, or contact identity/adapter systems.
    """

    source_id: str
    source_kind: str
    ingestion_boundary: str
    trust_level: SignalTrustLevel
    provenance_ref: str
    adapter_id: Optional[str] = None
    adapter_version: Optional[str] = None
    signature_ref: Optional[str] = None
    policy_refs: Tuple[str, ...] = ()

    @property
    def fingerprint(self) -> str:
        return signal_provenance_fingerprint({
            "source_id": self.source_id,
            "source_kind": self.source_kind,
            "ingestion_boundary": self.ingestion_boundary,
            "trust_level": self.trust_level.value,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "signature_ref": self.signature_ref,
            "policy_refs": sorted(self.policy_refs),
        })


@dataclass(frozen=True)
class TrustedSignal:
    """One immutable trusted current-state signal."""

    signal_id: str
    signal_type: SignalType
    tenant_id: str
    subject_ref: str
    source_ref: str
    source_kind: str
    captured_at: datetime
    status: SignalStatus
    value: Any
    provenance_ref: str
    valid_until: Optional[datetime] = None
    integrity_digest: Optional[str] = None
    policy_ref: Optional[str] = None
    # provenance projection (optional; required for trust-required signals by policy)
    authorization_ref: Optional[str] = None
    action_fingerprint: Optional[str] = None
    provenance: Optional[SignalProvenance] = None

    def __post_init__(self) -> None:
        for name in ("signal_id", "tenant_id", "subject_ref", "source_ref", "provenance_ref"):
            if not getattr(self, name):
                raise ValidationError(f"TrustedSignal.{name} must be non-empty")

    @property
    def content_fingerprint(self) -> str:
        """Content-addressed digest over the signal's identity + value."""
        return signal_content_fingerprint({
            "signal_type": self.signal_type.value,
            "tenant_id": self.tenant_id,
            "subject_ref": self.subject_ref,
            "captured_at": normalize_timestamp(self.captured_at),
            "valid_until": normalize_timestamp(self.valid_until) if self.valid_until else None,
            "status": self.status.value,
            "value": self.value,
            "authorization_ref": self.authorization_ref,
            "action_fingerprint": self.action_fingerprint,
        })

    @property
    def trust_level(self) -> Optional[SignalTrustLevel]:
        return self.provenance.trust_level if self.provenance else None


@dataclass(frozen=True)
class SignalBundle:
    """An immutable bundle of trusted signals + the required-signal-type set."""

    signals: Tuple[TrustedSignal, ...]
    required_signal_types: Tuple[SignalType, ...]

    def __post_init__(self) -> None:
        seen = set()
        for s in self.signals:
            if s.signal_id in seen:
                raise ValidationError(f"duplicate signal_id in bundle: {s.signal_id}")
            seen.add(s.signal_id)

    def by_type(self, signal_type: SignalType) -> Tuple[TrustedSignal, ...]:
        return tuple(s for s in self.signals if s.signal_type is signal_type)

    @property
    def fingerprint(self) -> str:
        """Order-independent bundle fingerprint (signals sorted by signal_id)."""
        ordered = sorted(self.signals, key=lambda s: s.signal_id)
        return signal_bundle_fingerprint({
            "signals": [s.content_fingerprint for s in ordered],
            "required_signal_types": sorted(t.value for t in self.required_signal_types),
        })


__all__ = ["SignalProvenance", "TrustedSignal", "SignalBundle"]
