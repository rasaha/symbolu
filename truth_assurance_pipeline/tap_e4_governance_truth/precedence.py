"""
Deterministic precedence resolution (documented rules).

Ordering key (highest first), applied to candidates that already passed jurisdiction,
scope, temporal, supersession, and exception filtering:

  1. authority tier rank (law/regulation > corporate > department > sop > work
     instruction > recommendation > draft);
  2. customer-contract override — a contract may override CORPORATE/DEPARTMENT policy
     but NEVER law or regulation (immutable tiers);
  3. emergency override — an emergency-procedure candidate wins for emergency situations;
  4. scope specificity (role/environment-specific beats broad);
  5. version recency (higher version number).

Drafts are never selectable. Ties are broken deterministically by authority name.
"""
from __future__ import annotations
from typing import List, Tuple

from truth_assurance_pipeline.tap_e4_governance_truth import authority as auth

PRECEDENCE_RULES_VERSION = "tap-e4-precedence/1.0.0"


def _key(c) -> Tuple:
    contract_boost = 1 if (c.is_contract and not auth.is_immutable(c.tier)) else 0
    emergency_boost = 1 if c.is_emergency_override else 0
    return (auth.rank(c.tier), contract_boost, emergency_boost, c.specificity, c.version,
            c.name)


def order(candidates: List) -> List:
    return sorted(candidates, key=_key, reverse=True)


def select(candidates: List):
    """Return (winner, ordered, tied_top) among selectable candidates. ``tied_top`` is the
    set of candidates sharing the top precedence key (a potential unresolved conflict)."""
    selectable = [c for c in candidates if auth.is_selectable(c.tier)]
    if not selectable:
        return None, [], []
    ordered = order(selectable)
    top = ordered[0]
    top_key = _key(top)[:-1]                 # ignore the name tiebreak for "tie" detection
    tied = [c for c in ordered if _key(c)[:-1] == top_key]
    return top, ordered, tied
