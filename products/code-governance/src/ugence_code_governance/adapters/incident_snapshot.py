"""Incident-state supplied-snapshot adapter (read-only).

Produces an ``ACTIVE_INCIDENT`` fact. A critical active incident routes to a
non-CLEAR outcome (HOLD/ESCALATE) through the unchanged clearance path + product
routing; an incident state never means "execution permitted".
"""
from __future__ import annotations

from typing import Optional, Tuple

from ugence_action_clearance import SignalType  # type: ignore

from .errors import AdapterFailureCode
from .models import CollectedSignalFact, FactConsistency
from .snapshot_base import SuppliedSnapshotAdapter
from .snapshot_schemas import ValidatedSnapshot


class IncidentSnapshotAdapter(SuppliedSnapshotAdapter):
    kind = "incident"
    adapter_id = "cg.incident_snapshot"
    signal_type = SignalType.ACTIVE_INCIDENT.value

    def _extract_facts(
        self, validated: ValidatedSnapshot,
    ) -> Tuple[Tuple[CollectedSignalFact, ...], Optional[AdapterFailureCode]]:
        active = validated.facts.get("incident_active")
        if not isinstance(active, bool):
            return (), AdapterFailureCode.SOURCE_SCHEMA_INVALID
        value = {"active": active}
        severity = validated.facts.get("severity")
        if isinstance(severity, str) and severity:
            value["severity"] = severity
        fact = CollectedSignalFact(
            signal_type=self.signal_type, value=value,
            consistency=FactConsistency.AUTHORITATIVE, observed_at=validated.captured_at)
        return (fact,), None


__all__ = ["IncidentSnapshotAdapter"]
