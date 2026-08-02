"""Neutral immutable clearance-policy model (design §16).

The evaluator consumes an **already-resolved** policy projection. This package
implements no mutable policy database, no source registry, no enterprise policy
administration, and no remote policy loading.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

from ..models.constraints import EffectiveConstraint
from ..models.enums import ClearanceStatus, SignalTrustLevel, SignalType


@dataclass(frozen=True)
class ClearancePolicy:
    """A resolved, immutable clearance policy."""

    policy_id: str
    policy_version: str
    required_signal_types: Tuple[SignalType, ...] = ()
    minimum_signal_trust_levels: Mapping[str, SignalTrustLevel] = field(default_factory=dict)
    maximum_signal_age_s: Optional[int] = None
    maximum_clearance_lifetime_s: Optional[int] = None
    clock_skew_tolerance_s: int = 0
    # operational-state response policy
    incident_response: ClearanceStatus = ClearanceStatus.HOLD          # HOLD or ESCALATE
    consumption_reserved_response: ClearanceStatus = ClearanceStatus.HOLD  # HOLD or BLOCK
    constraint_conflict_response: ClearanceStatus = ClearanceStatus.ESCALATE  # ESCALATE or BLOCK
    # narrowing constraints the policy applies (structured, provably narrowing)
    clearance_constraints: Tuple[EffectiveConstraint, ...] = ()
    # narrower operational obligations clearance adds (never removes upstream)
    added_obligations: Tuple[str, ...] = ()
    # approved sources / adapter versions (presence-checked only; no network)
    approved_source_kinds: Mapping[str, Tuple[str, ...]] = field(default_factory=dict)
    approved_adapter_versions: Mapping[str, Tuple[str, ...]] = field(default_factory=dict)
    # signal types that require an integrity/provenance trust proof
    trust_required_signal_types: Tuple[SignalType, ...] = ()

    def required(self, signal_type: SignalType) -> bool:
        return signal_type in self.required_signal_types

    def min_trust_for(self, signal_type: SignalType) -> Optional[SignalTrustLevel]:
        return self.minimum_signal_trust_levels.get(signal_type.value)

    @property
    def policy_ref(self) -> str:
        return f"{self.policy_id}:{self.policy_version}"


__all__ = ["ClearancePolicy"]
