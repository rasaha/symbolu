"""Identity/account-validity supplied-snapshot adapter (read-only).

Produces an ``ACTOR_STATUS`` fact. Only governance-relevant identity fields are
read; any prohibited field (salary, medical, performance content, personal
contact, unrelated demographics, …) present under ``facts`` fails closed. Stable
subject references are used, never full employee profiles.
"""
from __future__ import annotations

from typing import Optional, Tuple

from ugence_action_clearance import SignalType  # type: ignore

from .errors import AdapterFailureCode
from .models import CollectedSignalFact, FactConsistency
from .snapshot_base import SuppliedSnapshotAdapter
from .snapshot_schemas import IDENTITY_ALLOWED_FACT_KEYS, ValidatedSnapshot


class IdentitySnapshotAdapter(SuppliedSnapshotAdapter):
    kind = "identity"
    adapter_id = "cg.identity_snapshot"
    signal_type = SignalType.ACTOR_STATUS.value

    def _extract_facts(
        self, validated: ValidatedSnapshot,
    ) -> Tuple[Tuple[CollectedSignalFact, ...], Optional[AdapterFailureCode]]:
        # Data minimization: reject any non-allowlisted (potentially sensitive) key.
        for key in validated.facts:
            if key not in IDENTITY_ALLOWED_FACT_KEYS:
                return (), AdapterFailureCode.SOURCE_SCHEMA_INVALID
        active = validated.facts.get("account_active")
        if not isinstance(active, bool):
            return (), AdapterFailureCode.SOURCE_SCHEMA_INVALID
        fact = CollectedSignalFact(
            signal_type=self.signal_type,
            value={"state": "ACTIVE" if active else "DISABLED"},
            consistency=FactConsistency.AUTHORITATIVE,
            observed_at=validated.captured_at)
        return (fact,), None


__all__ = ["IdentitySnapshotAdapter"]
