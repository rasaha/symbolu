"""Deterministic conversion of an operational snapshot into TrustedSignals.

Builds canonical Action Clearance ``TrustedSignal`` objects through the Action
Clearance public API only. It preserves source/adapter identity, capture time and
validity, binds tenant/subject/authorization/action, assigns only policy-permitted
trust levels, and computes canonical content/provenance fingerprints via the
public model (never re-implementing the fingerprint algorithm). It fails closed on
an unapproved source, an unapproved adapter version, or an over-claimed trust level.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Any, List, Optional, Tuple

from ugence_action_clearance import (  # type: ignore
    SignalBundle,
    SignalProvenance,
    SignalStatus,
    SignalType,
    TrustedSignal,
)

from ..errors import CodeGovernanceError
from .snapshot import CodeGovernanceOperationalSnapshot
from .source_projection import TrustedSignalSourceProjection


class ClearanceInputError(CodeGovernanceError):
    """A supplied operational input could not be admitted (fail closed)."""


# Map each present snapshot fact to (SignalType, normalized value).
def _facts(snapshot: CodeGovernanceOperationalSnapshot):
    out = []
    if snapshot.authorization_validity is not None:
        out.append((SignalType.AUTHORIZATION_VALIDITY, {"state": snapshot.authorization_validity}))
    if snapshot.actor_state is not None:
        out.append((SignalType.ACTOR_STATUS, {"state": snapshot.actor_state}))
    if snapshot.artifact_action_fingerprint is not None:
        v: dict = {"action_fingerprint": snapshot.artifact_action_fingerprint}
        if snapshot.artifact_target_ref is not None:
            v["target_ref"] = snapshot.artifact_target_ref
        out.append((SignalType.ARTIFACT_IDENTITY, v))
    if snapshot.policy_accepted is not None:
        out.append((SignalType.POLICY_VALIDITY, {"accepted": snapshot.policy_accepted}))
    if snapshot.change_freeze_active is not None:
        out.append((SignalType.CHANGE_FREEZE, {"active": snapshot.change_freeze_active}))
    if snapshot.incident_active is not None:
        out.append((SignalType.ACTIVE_INCIDENT, {"active": snapshot.incident_active}))
    if snapshot.target_available is not None:
        out.append((SignalType.TARGET_AVAILABILITY, {"available": snapshot.target_available}))
    if snapshot.required_control_satisfied is not None:
        out.append((SignalType.REQUIRED_CONTROL, {"satisfied": snapshot.required_control_satisfied}))
    if snapshot.consumption_state is not None:
        out.append((SignalType.PRIOR_CONSUMPTION, {"state": snapshot.consumption_state}))
    return out


def build_trusted_signals(
    snapshot: CodeGovernanceOperationalSnapshot,
    projection: TrustedSignalSourceProjection,
    *,
    tenant_id: str,
    subject_ref: str,
    authorization_ref: str,
    action_fingerprint: str,
    required_signal_types: Tuple[SignalType, ...],
) -> SignalBundle:
    """Deterministically build a canonical ``SignalBundle`` from a snapshot.

    Fails closed (``ClearanceInputError``) on tenant mismatch or on any fact whose
    source is unapproved / adapter version unapproved / trust level over-claimed.
    """
    if projection.tenant_id != tenant_id:
        raise ClearanceInputError("source projection tenant does not match request tenant")

    signals: List[TrustedSignal] = []
    seen_types = set()
    for signal_type, value in _facts(snapshot):
        if signal_type in seen_types:
            raise ClearanceInputError(f"duplicate operational fact for {signal_type.value}")
        seen_types.add(signal_type)

        entry = projection.entry_for(signal_type)
        if entry is None:
            raise ClearanceInputError(f"no approved source for {signal_type.value}")
        if not entry.version_approved():
            raise ClearanceInputError(f"adapter version unapproved for {signal_type.value}")
        # trust level is the source's declared maximum (never over-claimed here)
        trust = entry.max_trust_level
        if not entry.trust_within_max(trust):  # defensive; always true
            raise ClearanceInputError(f"trust level over-claimed for {signal_type.value}")

        status = (SignalStatus.UNKNOWN if signal_type.value in snapshot.unknown_facts
                  else SignalStatus.PRESENT)
        provenance = SignalProvenance(
            source_id=entry.source_id, source_kind=entry.source_kind,
            ingestion_boundary=entry.ingestion_boundary, trust_level=trust,
            provenance_ref=entry.provenance_ref, adapter_id=entry.adapter_id,
            adapter_version=entry.adapter_version, policy_refs=tuple(projection.policy_refs))
        signal = TrustedSignal(
            signal_id=f"cg-{signal_type.value}",
            signal_type=signal_type, tenant_id=tenant_id, subject_ref=subject_ref,
            source_ref=entry.source_id, source_kind=entry.source_kind,
            captured_at=snapshot.captured_at, status=status, value=value,
            provenance_ref=entry.provenance_ref, valid_until=snapshot.valid_until,
            authorization_ref=authorization_ref, action_fingerprint=action_fingerprint,
            provenance=provenance)
        # Bind a matching content integrity digest via the public content fingerprint.
        signal = dataclasses.replace(signal, integrity_digest=signal.content_fingerprint)
        signals.append(signal)

    signals.sort(key=lambda s: s.signal_id)
    return SignalBundle(signals=tuple(signals), required_signal_types=tuple(required_signal_types))


__all__ = ["build_trusted_signals", "ClearanceInputError"]
