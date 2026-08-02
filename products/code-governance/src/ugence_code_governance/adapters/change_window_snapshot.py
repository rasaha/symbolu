"""Change-window / freeze-state supplied-snapshot adapter (read-only).

Produces a ``CHANGE_FREEZE`` fact. An active freeze becomes a HOLD input through
the unchanged Action Clearance path (never a CLEAR).
"""
from __future__ import annotations

from typing import Optional, Tuple

from ugence_action_clearance import SignalType  # type: ignore

from .errors import AdapterFailureCode
from .models import CollectedSignalFact, FactConsistency
from .snapshot_base import SuppliedSnapshotAdapter
from .snapshot_schemas import ValidatedSnapshot


class ChangeWindowSnapshotAdapter(SuppliedSnapshotAdapter):
    kind = "change_window"
    adapter_id = "cg.change_window_snapshot"
    signal_type = SignalType.CHANGE_FREEZE.value

    def _extract_facts(
        self, validated: ValidatedSnapshot,
    ) -> Tuple[Tuple[CollectedSignalFact, ...], Optional[AdapterFailureCode]]:
        active = validated.facts.get("freeze_active")
        if not isinstance(active, bool):
            return (), AdapterFailureCode.SOURCE_SCHEMA_INVALID
        fact = CollectedSignalFact(
            signal_type=self.signal_type, value={"active": active},
            consistency=FactConsistency.AUTHORITATIVE, observed_at=validated.captured_at)
        return (fact,), None


__all__ = ["ChangeWindowSnapshotAdapter"]
