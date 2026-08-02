"""Lifecycle dimension — the governance chain ran to a terminal reconciliation."""
from __future__ import annotations

from .results import fail, ok


def check(fixture, platform, outcome):
    results = []
    results.append(
        ok("lifecycle", "reconciled") if outcome.reconciliation_status == "RECONCILED"
        else fail("lifecycle", "reconciled",
                  f"expected RECONCILED, got {outcome.reconciliation_status}"))
    results.append(
        ok("lifecycle", "produced_records") if outcome.records
        else fail("lifecycle", "produced_records", "no kernel records captured"))
    return results
