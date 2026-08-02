"""Target health/availability supplied-snapshot adapter (read-only).

Produces a ``TARGET_AVAILABILITY`` fact. An unavailable target becomes a HOLD
input through the unchanged clearance path (never a CLEAR).
"""
from __future__ import annotations

from typing import Optional, Tuple

from ugence_action_clearance import SignalType  # type: ignore

from .errors import AdapterFailureCode
from .models import CollectedSignalFact, FactConsistency
from .snapshot_base import SuppliedSnapshotAdapter
from .snapshot_schemas import ValidatedSnapshot


class TargetHealthSnapshotAdapter(SuppliedSnapshotAdapter):
    kind = "target_health"
    adapter_id = "cg.target_health_snapshot"
    signal_type = SignalType.TARGET_AVAILABILITY.value

    def _extract_facts(
        self, validated: ValidatedSnapshot,
    ) -> Tuple[Tuple[CollectedSignalFact, ...], Optional[AdapterFailureCode]]:
        available = validated.facts.get("available")
        if not isinstance(available, bool):
            return (), AdapterFailureCode.SOURCE_SCHEMA_INVALID
        fact = CollectedSignalFact(
            signal_type=self.signal_type, value={"available": available},
            consistency=FactConsistency.AUTHORITATIVE, observed_at=validated.captured_at)
        return (fact,), None


__all__ = ["TargetHealthSnapshotAdapter"]
