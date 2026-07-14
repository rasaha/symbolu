#!/usr/bin/env python3
"""Part 1 — executable counterexamples against the direct action-BCVF port.

Exercises the REAL production scorer in
``symbolu_robotics/formulas/bcvf.py`` (no mocks). Every counterexample is a
self-checking assertion: it prints the evidence and records a machine-readable
row. Run:

    python -m robotics_reliability_bench.run_action_counterexamples

The claims we test (each tied to a line in the audit doc):

  CE1  Ranking is argmin-L, and beta cannot change the argmax winner — but
       beta *does* change the winner's normalized confidence, so any
       downstream *threshold* on normalized_weight flips with temperature
       alone (no new evidence).
  CE2  The consistency term (sf-sb)^2 makes a mediocre-but-consistent action
       beat a maximally-feasible (safest) action. "Most consistent" != safest.
  CE3  A weighted-blend consumer's commanded action moves with beta alone.
  CE4  All-unsafe / all-infeasible candidates still normalize into a
       confident-looking winner. There is no NO_SAFE_ACTION path.
  CE5  Cross-module score miscalibration (different sf/sb scales) silently
       flips the ranking with no change in the underlying physics.

Exit code 0 iff every counterexample reproduces as predicted.
"""
from __future__ import annotations

import json
import math
import os
from typing import Dict, List

import numpy as np

from symbolu_robotics.formulas.bcvf import (
    BCVFConfig,
    compute_bcvf_weight,
    compute_consistency_lagrangian,
    normalize_bcvf_weights,
    score_action_candidates,
)

RESULTS = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS, exist_ok=True)


def _winner(forward: List[float], backward: List[float], cfg: BCVFConfig) -> int:
    scores = score_action_candidates(forward, backward, cfg)
    return max(range(len(scores)), key=lambda i: scores[i].normalized_weight)


def _weights(forward: List[float], backward: List[float], cfg: BCVFConfig):
    scores = score_action_candidates(forward, backward, cfg)
    return [s.normalized_weight for s in scores]


def ce1_temperature_confidence() -> Dict:
    """Beta cannot flip the argmax, but it flips a confidence threshold."""
    # Two candidates: A is slightly more consistent, B slightly less.
    forward = [0.80, 0.85]
    backward = [0.78, 0.60]
    lo = BCVFConfig(beta=0.5)
    hi = BCVFConfig(beta=20.0)

    w_lo = _weights(forward, backward, lo)
    w_hi = _weights(forward, backward, hi)
    win_lo, win_hi = int(np.argmax(w_lo)), int(np.argmax(w_hi))

    # Argmax is beta-invariant (monotone exp + monotone normalization).
    argmax_invariant = win_lo == win_hi
    # But a downstream gate "act only if top weight > 0.6" flips with beta.
    gate = 0.60
    passes_lo = max(w_lo) > gate
    passes_hi = max(w_hi) > gate
    threshold_flips = passes_lo != passes_hi

    return {
        "id": "CE1",
        "claim": "beta leaves argmax fixed but moves confidence past a gate",
        "forward": forward,
        "backward": backward,
        "weights_beta0.5": [round(x, 4) for x in w_lo],
        "weights_beta20": [round(x, 4) for x in w_hi],
        "argmax_invariant_to_beta": argmax_invariant,
        "confidence_gate": gate,
        "gate_passes_low_beta": passes_lo,
        "gate_passes_high_beta": passes_hi,
        "threshold_flips_on_beta_alone": threshold_flips,
        "reproduced": argmax_invariant and threshold_flips,
    }


def ce2_consistency_beats_safety() -> Dict:
    """Consistency penalty prefers mediocre-consistent over maximally-safe.

    Action A: perfectly feasible/safe (sf=1.0) but modest goal (sb=0.5).
    Action B: mediocre on both (sf=sb=0.7) — perfectly self-consistent.
    With default weights B wins purely because (sf-sb)^2 punishes A's honest
    feasibility>goal gap. The *safest* action loses.
    """
    cfg = BCVFConfig()  # lambda_f=1, lambda_b=1, lambda_c=0.5, beta=2
    # A = safest, B = consistent-mediocre
    forward = [1.00, 0.70]
    backward = [0.50, 0.70]

    L_A = compute_consistency_lagrangian(
        forward[0], backward[0], cfg.lambda_forward, cfg.lambda_backward,
        cfg.lambda_consistency)
    L_B = compute_consistency_lagrangian(
        forward[1], backward[1], cfg.lambda_forward, cfg.lambda_backward,
        cfg.lambda_consistency)
    winner = _winner(forward, backward, cfg)
    consistency_contribution_A = cfg.lambda_consistency * (forward[0] - backward[0]) ** 2

    return {
        "id": "CE2",
        "claim": "consistency term makes safest action (sf=1.0) lose to mediocre-consistent",
        "action_A_safest": {"sf": forward[0], "sb": backward[0], "L": round(L_A, 4)},
        "action_B_consistent": {"sf": forward[1], "sb": backward[1], "L": round(L_B, 4)},
        "consistency_penalty_charged_to_A": round(consistency_contribution_A, 4),
        "winner_index": winner,
        "winner_is_less_feasible_action": winner == 1,
        "reproduced": winner == 1 and L_B < L_A,
    }


def ce3_temperature_moves_blend() -> Dict:
    """A weighted-average consumer commands a different action as beta varies."""
    # 3 candidate scalar controls (e.g., commanded accel m/s^2). The controls
    # average to 0, so a near-uniform (low-beta) blend commands ~0, while a
    # peaked (high-beta) blend commands the argmin-L candidate's control.
    controls = np.array([3.0, 0.0, -3.0])
    forward = [0.85, 0.70, 0.60]
    backward = [0.85, 0.50, 0.90]

    blends = {}
    for beta in (0.5, 2.0, 10.0):
        w = np.array(_weights(forward, backward, BCVFConfig(beta=beta)))
        blends[beta] = float(np.dot(w, controls))
    spread = max(blends.values()) - min(blends.values())
    return {
        "id": "CE3",
        "claim": "trust-weighted blended command moves with beta alone",
        "controls": controls.tolist(),
        "forward": forward,
        "backward": backward,
        "blended_command_by_beta": {str(k): round(v, 4) for k, v in blends.items()},
        "command_spread_across_beta": round(spread, 4),
        "reproduced": spread > 0.25,  # >0.25 m/s^2 swing from temperature only
    }


def ce4_all_unsafe_still_wins() -> Dict:
    """Every candidate is unsafe/infeasible, yet one is crowned a winner."""
    # All candidates near-zero feasibility and goal (e.g., all collide).
    forward = [0.10, 0.05, 0.08]
    backward = [0.09, 0.06, 0.07]
    cfg = BCVFConfig()
    weights = _weights(forward, backward, cfg)
    winner = _winner(forward, backward, cfg)
    # Normalized weights always sum to 1 -> winner looks "chosen".
    sums_to_one = math.isclose(sum(weights), 1.0, abs_tol=1e-6)
    winner_weight = max(weights)
    # There is no abstain: the API returns an index no matter how bad the inputs.
    return {
        "id": "CE4",
        "claim": "all-unsafe candidates normalize to a confident winner; no abstain",
        "forward": forward,
        "backward": backward,
        "normalized_weights": [round(x, 4) for x in weights],
        "weights_sum_to_one": sums_to_one,
        "winner_index": winner,
        "winner_normalized_weight": round(winner_weight, 4),
        "abstain_available": False,
        "reproduced": sums_to_one and winner is not None,
    }


def ce5_cross_module_miscalibration() -> Dict:
    """Same physics, two modules' score scales -> different winner.

    Module P reports feasibility in a calibrated [0,1]. Module Q reports the
    *same* physical feasibilities compressed into [0,0.6] (a common when one
    module is conservative). The relative ordering of physics is identical;
    only the scale differs. The BCVF winner flips.
    """
    cfg = BCVFConfig()
    # Underlying physics: candidate 0 is most feasible, 1 mid, 2 least.
    backward = [0.55, 0.85, 0.80]  # goal achievement identical in both worlds

    forward_calibrated = [0.90, 0.70, 0.55]
    forward_compressed = [0.90 * 0.6, 0.70 * 0.6, 0.55 * 0.6]

    win_cal = _winner(forward_calibrated, backward, cfg)
    win_comp = _winner(forward_compressed, backward, cfg)
    return {
        "id": "CE5",
        "claim": "uncalibrated sf scale across modules flips the winner with no physics change",
        "backward_scores": backward,
        "forward_calibrated": forward_calibrated,
        "forward_compressed_x0.6": [round(x, 4) for x in forward_compressed],
        "winner_calibrated": win_cal,
        "winner_compressed": win_comp,
        "winner_flipped_on_scale_only": win_cal != win_comp,
        "reproduced": win_cal != win_comp,
    }


def ce6_post_multiplier_beta_flip() -> Dict:
    """Real coordination-site pattern: winner = argmax(exp(-beta L) * bonus).

    Models `conflict_resolution.py:392-412` and `task_allocation.py:358-372`,
    where the normalized BCVF weight is multiplied by a safety/priority bonus
    and then argmax'd. Unlike pure argmax, THIS winner is beta-dependent: at
    low beta the exp() terms flatten and the bonus decides; at high beta the
    min-L candidate dominates. Same candidates, no new evidence, different
    winner. We also show the emergency-stop profile (sf=1.0, sb=0.3) carries
    the WORST BCVF weight because the consistency term punishes it.
    """
    # Candidate 0 = emergency MUTUAL_STOP (safest, sf=1.0/sb=0.3, high bonus).
    # Candidate 1 = an efficient-but-less-safe maneuver (consistent, low bonus).
    forward = [1.00, 0.80]
    backward = [0.30, 0.78]
    safety_bonus = [1.0, 0.5]          # stop is safest
    safety_weight = 2.0

    L0 = compute_consistency_lagrangian(forward[0], backward[0], 1.0, 1.0, 0.5)
    L1 = compute_consistency_lagrangian(forward[1], backward[1], 1.0, 1.0, 0.5)

    winners = {}
    for beta in (0.3, 2.0, 15.0):
        w = np.array(normalize_bcvf_weights(
            [compute_bcvf_weight(L0, beta), compute_bcvf_weight(L1, beta)]))
        adj = w * np.array([1.0 + safety_weight * b for b in safety_bonus])
        winners[beta] = int(np.argmax(adj))

    flipped = len(set(winners.values())) > 1
    stop_has_worst_bcvf = L0 > L1  # emergency stop is worst-scored by BCVF
    return {
        "id": "CE6",
        "claim": "post-normalization bonus makes winner beta-dependent; consistency term demotes emergency-stop",
        "forward": forward,
        "backward": backward,
        "L_emergency_stop": round(L0, 4),
        "L_efficient_maneuver": round(L1, 4),
        "emergency_stop_worst_bcvf_score": stop_has_worst_bcvf,
        "winner_by_beta": {str(k): v for k, v in winners.items()},
        "winner_flips_on_beta_alone": flipped,
        "reproduced": flipped and stop_has_worst_bcvf,
    }


def main() -> int:
    cases = [
        ce1_temperature_confidence(),
        ce2_consistency_beats_safety(),
        ce3_temperature_moves_blend(),
        ce4_all_unsafe_still_wins(),
        ce5_cross_module_miscalibration(),
        ce6_post_multiplier_beta_flip(),
    ]
    all_ok = True
    for c in cases:
        status = "REPRODUCED" if c["reproduced"] else "NOT-REPRODUCED"
        print(f"[{c['id']}] {status}: {c['claim']}")
        for k, v in c.items():
            if k in ("id", "claim", "reproduced"):
                continue
            print(f"        {k}: {v}")
        print()
        all_ok = all_ok and c["reproduced"]

    out = os.path.join(RESULTS, "action_counterexamples.json")
    with open(out, "w") as f:
        json.dump({"cases": cases, "all_reproduced": all_ok}, f, indent=2)
    print(f"wrote {out}")
    print(f"ALL COUNTEREXAMPLES REPRODUCED: {all_ok}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
