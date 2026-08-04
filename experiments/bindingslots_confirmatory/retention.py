#!/usr/bin/env python3
"""Frozen retention-trajectory categorizer for the BindingSlots confirmatory replication.

Categories are DEFINED BEFORE TRAINING and are explanatory diagnostics ONLY: they never override
the mechanical formation classifier. Pure stdlib.

Input: the per-checkpoint needle@d96 series (steps 0,60,120,300,600,900,1200) and the seed's final
formation boolean (from the frozen classifier). Output: one of the predefined categories.
"""
from __future__ import annotations

FORM_MIN = 0.075
CHECKPOINTS = [0, 60, 120, 300, 600, 900, 1200]


def trajectory_d96(seed_record):
    """Extract the ordered needle@d96 trajectory from a seed result record."""
    traj = seed_record.get("trajectory", [])
    by_step = {t["step"]: t.get("needle_d96") for t in traj if "needle_d96" in t}
    return [by_step.get(s) for s in CHECKPOINTS]


def classify(series, formed_final):
    """series: list of needle@d96 (may contain None). formed_final: bool from the frozen classifier."""
    vals = [(i, v) for i, v in enumerate(series) if v is not None]
    if not vals:
        return "OTHER_PREDEFINED"
    peak = max(v for _, v in vals)
    ever_formed = peak >= FORM_MIN
    idx_first_cross = next((i for i, v in vals if v >= FORM_MIN), None)
    last_step_idx = len(CHECKPOINTS) - 1  # step 1200

    if not ever_formed and not formed_final:
        return "NEVER_FORMED"

    if not formed_final and ever_formed:
        # crossed formation at some checkpoint but ended not-formed
        return "FORMED_THEN_COLLAPSED"

    # formed_final is True below
    if formed_final:
        # did it dip below FORM_MIN after first crossing, then recover?
        after = [v for i, v in vals if idx_first_cross is not None and i > idx_first_cross]
        dipped = any(v < FORM_MIN for v in after)
        if dipped:
            return "TRANSIENT_RECOVERY"
        # first crossing only at the final (or penultimate->final) checkpoint
        if idx_first_cross is not None and idx_first_cross >= last_step_idx - 1:
            # low before step 900
            early = [v for i, v in vals if i < last_step_idx - 1]
            if all(v < FORM_MIN for v in early):
                return "LATE_FORMATION"
        return "FORMED_AND_RETAINED"

    return "OTHER_PREDEFINED"


if __name__ == "__main__":
    # self-test on the known seed-9 pattern (peaked at step 300, decayed to 0)
    seed9 = [0.0, 0.0, 0.0, 1.0, 0.5, 0.1, 0.0]
    assert classify(seed9, formed_final=False) == "FORMED_THEN_COLLAPSED", classify(seed9, False)
    retained = [0.0, 0.1, 0.5, 0.9, 0.95, 0.9, 0.99]
    assert classify(retained, formed_final=True) == "FORMED_AND_RETAINED", classify(retained, True)
    late = [0.0, 0.0, 0.0, 0.0, 0.0, 0.02, 0.9]
    assert classify(late, formed_final=True) == "LATE_FORMATION", classify(late, True)
    never = [0.0, 0.0, 0.02, 0.03, 0.0, 0.01, 0.0]
    assert classify(never, formed_final=False) == "NEVER_FORMED", classify(never, False)
    transient = [0.0, 0.2, 0.9, 0.5, 0.0, 0.3, 0.9]
    assert classify(transient, formed_final=True) == "TRANSIENT_RECOVERY", classify(transient, True)
    print("retention self-test OK")
