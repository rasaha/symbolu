"""
Deterministic governance-conflict detection.

A conflict is declared when two or more candidates survive all filtering and share the
TOP precedence key (no deterministic dominator) yet impose incompatible obligations —
e.g. a corporate policy vs a customer contract at equal effective precedence, or two
regulations from overlapping jurisdictions. Conflicts are surfaced explicitly; a winner
is never chosen silently.
"""
from __future__ import annotations
from typing import List, Tuple

from truth_assurance_pipeline.tap_e4_governance_truth.schema import (
    GovConflictType, GovernanceConflict,
)


def detect(tied_top: List) -> Tuple[GovernanceConflict, ...]:
    if len(tied_top) < 2:
        return ()
    values = {(_val(c)) for c in tied_top}
    if len(values) < 2:
        return ()                            # same obligation -> not a conflict
    names = tuple(sorted(c.name for c in tied_top))
    ctype = GovConflictType.AUTHORITY_CONFLICT
    tiers = {c.tier for c in tied_top}
    if any(c.is_contract for c in tied_top) and any(not c.is_contract for c in tied_top):
        ctype = GovConflictType.CONTRACT_POLICY_CONFLICT
    elif len({c.jurisdiction for c in tied_top}) > 1:
        ctype = GovConflictType.JURISDICTION_CONFLICT
    return (GovernanceConflict(
        conflict_id="GC1", conflict_type=ctype, authority_names=names,
        explanation=f"{len(tied_top)} authorities tie at top precedence with "
                    f"incompatible obligations {sorted(values)}"),)


def _val(c) -> str:
    return c.obligation_value or c.target
