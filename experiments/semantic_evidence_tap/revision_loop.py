"""
revision_loop.py — T4: bounded forced-revision loop over TAP dispositions (§13).

Claims marked REVISE are re-drafted (in the simulation: dropped or down-qualified); claims marked
ESCALATE are removed from the user-facing response and routed to human/governance. The loop is
bounded (max_rounds) and every change is logged — no silent mutation.
"""
from __future__ import annotations

from typing import List, Tuple

from .tap_validator import TAPResult, govern, admissible, REVISE, ESCALATE, QUALIFY, PASS, SUPPORTED
from .claim_decomposer import Claim


def revise(claims: List[Claim], finding, max_rounds=2) -> Tuple[List[Claim], List[dict]]:
    log = []
    current = list(claims)
    for rnd in range(max_rounds):
        results = govern(current, finding, arm="T4")
        kept = []
        changed = False
        for r in results:
            if r.disposition in (PASS, QUALIFY):
                kept.append(r.claim)
            elif r.disposition == REVISE:
                # a bounded revision: drop the unsupported claim (a real loop would re-ask the model)
                log.append({"round": rnd, "action": "drop_revise", "kind": r.claim.kind}); changed = True
            elif r.disposition == ESCALATE:
                log.append({"round": rnd, "action": "escalate", "kind": r.claim.kind}); changed = True
        current = kept
        if not changed:
            break
    return current, log
