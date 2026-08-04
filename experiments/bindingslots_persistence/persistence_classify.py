#!/usr/bin/env python3
"""Frozen per-seed classifier for the persistence execution. Reuses the inherited Stage-B formation +
causal rules and the functional-routing routing thresholds. Same-seed A+ reference. Pure stdlib."""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
SBS = REPO / "hybrid_llm_vnext_lab" / "experiments" / "slot_formation_stabilization"
FR = REPO / "experiments" / "bindingslots_functional_routing"
for p in (str(SBS), str(FR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import classify_stage_b as FROZEN  # noqa: E402  frozen formation + causal rules
import fr_classifier as FRC        # noqa: E402  frozen routing thresholds + helpers

RT = FRC.RT  # correct_slot_probability_min 0.50, rank <=5, margin >=3.0


def _routing_1200(rec):
    return FRC.routing_at(rec, 1200)


def _needle_traj(rec):
    return FRC.needle_traj(rec)


def classify_seed(arm_rec, aplus_rec):
    """Return the frozen per-seed classification against the SAME-SEED A+. clean_stable is True only
    when every CLEAN_STABLE condition holds at step 1200."""
    d96 = FROZEN.d(arm_rec, 96)
    formed = FROZEN.forming(arm_rec, aplus_rec)
    traj = _needle_traj(arm_rec)
    at600 = (traj.get(600, 0) or 0) >= FROZEN.FORM_MIN
    at900 = (traj.get(900, 0) or 0) >= FROZEN.FORM_MIN
    endpoint = d96 >= FROZEN.FORM_MIN
    peak = max([v for v in traj.values() if v is not None] or [0.0])

    routing_clean = FRC.correct_slot_ok(arm_rec, 1200)
    causal = FROZEN.causal_ok(arm_rec, aplus_rec)
    slots_off = FRC.slots_off_ok(arm_rec, aplus_rec)
    rand_addr = FRC.rand_addr_ok(arm_rec, aplus_rec)

    # per-seed quality + distance vs same-seed A+
    q_ok = arm_rec["ppl"]["256"] <= 1.20 * aplus_rec["ppl"]["256"]
    d16_ok = FROZEN.d(arm_rec, 16) >= FROZEN.d(aplus_rec, 16) - 0.050
    d220_ok = (FROZEN.d(arm_rec, 220) - FROZEN.d(aplus_rec, 220)) > 0
    dist_ok = d16_ok and d220_ok

    clean_stable = bool(formed and at600 and at900 and endpoint and routing_clean
                        and slots_off and rand_addr and q_ok and dist_ok)

    if clean_stable:
        category = "CLEAN_STABLE"
    elif not q_ok:
        category = "QUALITY_FAILED"
    elif not formed and peak >= FROZEN.FORM_MIN:
        category = "FORMED_THEN_COLLAPSED"
    elif not formed:
        category = "NEVER_FORMED"
    elif not (endpoint and at600 and at900):
        category = "FORMED_THEN_COLLAPSED"
    elif not (slots_off and rand_addr):
        category = "FORMED_AND_RETAINED_BUT_CAUSALLY_UNCLEAN"
    elif not routing_clean:
        category = "FORMED_AND_CLEAN_BUT_ROUTING_METRICS_DECAYED"
    else:
        category = "FORMED_AND_RETAINED_BUT_CAUSALLY_UNCLEAN"

    r = _routing_1200(arm_rec)
    return {
        "clean_stable": clean_stable,
        "category": category,
        "needle_d96_1200": d96,
        "aplus_needle_d96_1200": FROZEN.d(aplus_rec, 96),
        "correct_slot_prob_1200": r.get("read_prob_on_highest_write_slot"),
        "correct_slot_rank_1200": r.get("rank_of_highest_write_slot_under_read"),
        "address_margin_1200": r.get("address_logit_margin"),
        "routing_clean": routing_clean,
        "slots_off": arm_rec.get("ablation", {}).get("slots_off"),
        "randomized_address": arm_rec.get("ablation", {}).get("randomized_address"),
        "slots_off_ok": slots_off, "randomized_address_ok": rand_addr,
        "quality_ok": q_ok, "distance_ok": dist_ok,
        "needle_step600": traj.get(600), "needle_step1200": traj.get(1200),
        "correct_slot_prob_step600": (FRC.routing_at(arm_rec, 600) or {}).get("read_prob_on_highest_write_slot"),
    }
