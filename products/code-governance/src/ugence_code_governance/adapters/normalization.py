"""Normalize read-only adapter results into the existing clearance input surface.

Adapter results are combined into a :class:`CodeGovernanceOperationalSnapshot` and
a :class:`TrustedSignalSourceProjection`, which feed the *unchanged* MVP 1B
clearance path. Source failures never become positive signals: a failed or
unavailable fact becomes a missing/unknown signal (fail closed), and conflicting
facts for the same signal type are marked unknown and recorded as conflicts.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from ugence_action_clearance import SignalType  # type: ignore

from ..clearance.snapshot import CodeGovernanceOperationalSnapshot
from ..clearance.source_projection import (
    SignalSourceEntry,
    TrustedSignalSourceProjection,
)
from .models import AdapterResult, FactConsistency
from .registry import AdapterRegistryProjection


@dataclass(frozen=True)
class NormalizedOperationalInput:
    """The normalized clearance input derived from a set of adapter results."""

    snapshot: CodeGovernanceOperationalSnapshot
    source_projection: TrustedSignalSourceProjection
    conflicts: Tuple[str, ...] = ()
    failures: Tuple[Tuple[str, str], ...] = ()  # (source_kind, failure_code)
    unavailable_signal_types: Tuple[str, ...] = ()
    adapter_result_refs: Tuple[str, ...] = ()


# Snapshot-field setter per signal type; each reads the fact's normalized value.
def _apply_fact(kwargs: Dict, signal_type: str, value) -> None:
    if signal_type == SignalType.AUTHORIZATION_VALIDITY.value:
        kwargs["authorization_validity"] = value.get("state")
    elif signal_type == SignalType.ACTOR_STATUS.value:
        kwargs["actor_state"] = value.get("state")
    elif signal_type == SignalType.ARTIFACT_IDENTITY.value:
        kwargs["artifact_action_fingerprint"] = value.get("action_fingerprint")
        if value.get("target_ref") is not None:
            kwargs["artifact_target_ref"] = value.get("target_ref")
    elif signal_type == SignalType.POLICY_VALIDITY.value:
        kwargs["policy_accepted"] = value.get("accepted")
    elif signal_type == SignalType.CHANGE_FREEZE.value:
        kwargs["change_freeze_active"] = value.get("active")
    elif signal_type == SignalType.ACTIVE_INCIDENT.value:
        kwargs["incident_active"] = value.get("active")
    elif signal_type == SignalType.TARGET_AVAILABILITY.value:
        kwargs["target_available"] = value.get("available")
    elif signal_type == SignalType.REQUIRED_CONTROL.value:
        kwargs["required_control_satisfied"] = value.get("satisfied")
    elif signal_type == SignalType.PRIOR_CONSUMPTION.value:
        kwargs["consumption_state"] = value.get("state")


def normalize_results(
    results: Tuple[AdapterResult, ...],
    *,
    tenant_id: str,
    captured_at: datetime,
    valid_until: datetime,
    registry: AdapterRegistryProjection,
    projection_id: str = "cg-adapter-projection",
    policy_refs: Tuple[str, ...] = (),
) -> NormalizedOperationalInput:
    """Combine adapter results into a snapshot + source projection (fail closed)."""
    kwargs: Dict = {}
    entries: Dict[SignalType, SignalSourceEntry] = {}
    seen_values: Dict[str, object] = {}
    conflicts: List[str] = []
    failures: List[Tuple[str, str]] = []
    unavailable: List[str] = []
    unknown_facts: List[str] = []
    result_refs: List[str] = []

    for result in results:
        result_refs.append(result.result_fingerprint)
        for code in result.failure_codes:
            failures.append((result.source.source_kind, code.value))
        for fact in result.collected_facts:
            st = fact.signal_type
            if fact.consistency is FactConsistency.UNAVAILABLE:
                unavailable.append(st)
                unknown_facts.append(st)
                continue
            # Conflict: a second differing value for the same signal type.
            key = str(sorted((str(k), str(v)) for k, v in fact.value.items()))
            if st in seen_values and seen_values[st] != key:
                conflicts.append(st)
                unknown_facts.append(st)
                continue
            seen_values[st] = key
            _apply_fact(kwargs, st, fact.value)
            # Register the approved source for this signal type from the registry.
            entry = registry.entry_for(result.adapter.adapter_id)
            if entry is not None:
                try:
                    stype = SignalType(st)
                except ValueError:
                    continue
                entries[stype] = SignalSourceEntry(
                    source_id=entry.source_id, source_kind=entry.source_kind,
                    adapter_id=entry.adapter_id, adapter_version=entry.adapter_version,
                    ingestion_boundary=entry.source_kind, provenance_ref=result.result_fingerprint,
                    max_trust_level=entry.max_trust_level,
                    approved_adapter_versions=entry.approved_adapter_versions)

    # Conflicting / unavailable required facts are reported UNKNOWN (fail closed).
    dedup_unknown = tuple(sorted(set(unknown_facts)))
    snapshot = CodeGovernanceOperationalSnapshot(
        captured_at=captured_at, valid_until=valid_until,
        unknown_facts=dedup_unknown, **kwargs)
    source_projection = TrustedSignalSourceProjection(
        projection_id=projection_id, projection_version=registry.registry_version,
        tenant_id=tenant_id, entries=entries, policy_refs=policy_refs or registry.policy_refs)
    return NormalizedOperationalInput(
        snapshot=snapshot, source_projection=source_projection,
        conflicts=tuple(sorted(set(conflicts))), failures=tuple(failures),
        unavailable_signal_types=tuple(sorted(set(unavailable))),
        adapter_result_refs=tuple(result_refs))


__all__ = ["NormalizedOperationalInput", "normalize_results"]
