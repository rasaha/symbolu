"""Required-control-status supplied-snapshot adapter (read-only).

Produces a ``REQUIRED_CONTROL`` fact. An unsatisfied required control becomes a
non-CLEAR input through the unchanged clearance path.
"""
from __future__ import annotations

from typing import Optional, Tuple

from ugence_action_clearance import SignalType  # type: ignore

from .errors import AdapterFailureCode
from .models import CollectedSignalFact, FactConsistency
from .snapshot_base import SuppliedSnapshotAdapter
from .snapshot_schemas import ValidatedSnapshot


class ControlStatusSnapshotAdapter(SuppliedSnapshotAdapter):
    kind = "control_status"
    adapter_id = "cg.control_status_snapshot"
    signal_type = SignalType.REQUIRED_CONTROL.value

    def _extract_facts(
        self, validated: ValidatedSnapshot,
    ) -> Tuple[Tuple[CollectedSignalFact, ...], Optional[AdapterFailureCode]]:
        satisfied = validated.facts.get("satisfied")
        if not isinstance(satisfied, bool):
            return (), AdapterFailureCode.SOURCE_SCHEMA_INVALID
        value = {"satisfied": satisfied}
        control_id = validated.facts.get("control_id")
        if isinstance(control_id, str) and control_id:
            value["control_id"] = control_id
        fact = CollectedSignalFact(
            signal_type=self.signal_type, value=value,
            consistency=FactConsistency.AUTHORITATIVE, observed_at=validated.captured_at)
        return (fact,), None


__all__ = ["ControlStatusSnapshotAdapter"]
