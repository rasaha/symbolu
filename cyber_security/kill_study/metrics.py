"""Per-event metric extraction and aggregation helpers.

A per-event record is the raw unit of analysis: it stores the challenge step
for every threshold in the sweep (so the full DET frontier is reconstructable
with no re-simulation) plus the threshold-independent template/poisoning
metrics. All aggregation and statistics live in analysis.py.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from .config import THRESHOLD_SWEEP, StudyConfig
from .detectors import ArmOutput
from .observers import challenge_rate, challenge_step_for_threshold
from .trajectories import TrajectoryEvent

NO_CHALLENGE = -1


def challenge_curve(arm_out: ArmOutput, cfg: StudyConfig) -> List[int]:
    """Challenge step at each threshold in the sweep (-1 = never)."""
    out: List[int] = []
    for thr in THRESHOLD_SWEEP:
        cs = challenge_step_for_threshold(
            arm_out.s_norm, thr, arm_out.guarded, cfg
        )
        out.append(NO_CHALLENGE if cs is None else int(cs))
    return out


def template_metrics(
    arm_out: ArmOutput, event: TrajectoryEvent
) -> Dict[str, Optional[float]]:
    tr = arm_out.trace
    disp = tr.m_slow[-1] - tr.m_slow[0]
    out: Dict[str, Optional[float]] = {
        "template_update_amount": float(tr.template_update_amount),
        "d_parallel": None,
        "d_perp": None,
        "margin_erosion": None,
    }
    if event.v_attack is not None:
        v = event.v_attack / (np.linalg.norm(event.v_attack) + 1e-12)
        d_par = float(np.dot(disp, v))
        d_perp = float(np.linalg.norm(disp - d_par * v))
        out["d_parallel"] = d_par
        out["d_perp"] = d_perp
    if event.mu_a is not None:
        # score = negative distance; erosion>0 means attacker became more acceptable
        s0 = -float(np.linalg.norm(event.mu_a - tr.m_slow[0]))
        sT = -float(np.linalg.norm(event.mu_a - tr.m_slow[-1]))
        out["margin_erosion"] = sT - s0
    return out


def damage_weighted_loss(
    challenge_step: int, onset: int, cfg: StudyConfig
) -> float:
    """Fixed-policy damage accrued between onset and response.

    Undetected (or challenge before onset) -> response deferred to the end of
    the damage horizon, i.e. maximal accrued damage.
    """
    dmg = cfg.damage
    detected = challenge_step != NO_CHALLENGE and challenge_step >= onset
    if detected:
        response = challenge_step
    else:
        response = onset + dmg.horizon
    steps = int(min(response - onset, dmg.horizon))
    return float(sum(dmg.weight(s) for s in range(0, max(steps, 0) + 1)))


def event_record(
    arm_key: str,
    arm_out: ArmOutput,
    event: TrajectoryEvent,
    cfg: StudyConfig,
    split: str,
) -> dict:
    return {
        "split": split,
        "arm": arm_key,
        "arm_name": arm_out.arm,
        "guarded": arm_out.guarded,
        "family": event.name,
        "is_attack": event.is_attack,
        "onset": int(event.onset),
        "params": event.params,
        "challenge_curve": challenge_curve(arm_out, cfg),
        "template": template_metrics(arm_out, event),
    }


# --- frontier reconstruction from records -----------------------------------


def detected_and_delay(cs: int, onset: int) -> tuple[bool, Optional[int]]:
    if cs != NO_CHALLENGE and cs >= onset:
        return True, cs - onset
    return False, None


def far_at_threshold(legit_curves: List[List[int]], thr_idx: int) -> float:
    """False-challenge rate = fraction of legit events challenged at all."""
    if not legit_curves:
        return 0.0
    fp = sum(1 for c in legit_curves if c[thr_idx] != NO_CHALLENGE)
    return fp / len(legit_curves)


def det_at_threshold(attack_curves: List[List[int]], onsets: List[int], thr_idx: int) -> float:
    if not attack_curves:
        return 0.0
    hit = sum(
        1
        for c, on in zip(attack_curves, onsets)
        if detected_and_delay(c[thr_idx], on)[0]
    )
    return hit / len(attack_curves)
