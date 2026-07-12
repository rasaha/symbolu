"""Aggregate analysis, paired bootstrap, and the mechanical verdict.

Reads results/events.jsonl, tunes each arm's operating threshold on the DEV
split, evaluates everything on the held-out EVAL split, runs paired bootstrap
CIs for H vs I, and emits the preregistered verdict. The verdict is a pure
function of the held-out numbers.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from .config import (
    ADAPTIVE_ATTACK_FAMILIES,
    ATTACK_FAMILIES,
    DET_FIXED_FAR,
    DRIFT_FRICTION_FAMILIES,
    FAR_BUDGET,
    LEGIT_FAMILIES,
    N_BOOT,
    BOOT_SEED,
    THRESHOLD_SWEEP,
    StudyConfig,
)
from .metrics import NO_CHALLENGE, damage_weighted_loss, detected_and_delay

RESULTS_DIR = Path(__file__).parent / "results"


def load_records(path: Path) -> List[dict]:
    with path.open() as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _index(records: List[dict]):
    """index[split][arm] -> list; paired[split][(family,seed)][arm] -> rec."""
    index: Dict[str, Dict[str, List[dict]]] = {}
    paired: Dict[str, Dict[Tuple[str, int], Dict[str, dict]]] = {}
    for r in records:
        sp, arm = r["split"], r["arm"]
        index.setdefault(sp, {}).setdefault(arm, []).append(r)
        key = (r["family"], r["seed"])
        paired.setdefault(sp, {}).setdefault(key, {})[arm] = r
    return index, paired


def _far(records: List[dict], thr_idx: int, families) -> float:
    legit = [r for r in records if r["family"] in families]
    if not legit:
        return 0.0
    fp = sum(1 for r in legit if r["challenge_curve"][thr_idx] != NO_CHALLENGE)
    return fp / len(legit)


def _det(records: List[dict], thr_idx: int, families) -> float:
    atk = [r for r in records if r["family"] in families]
    if not atk:
        return 0.0
    hit = sum(
        1
        for r in atk
        if detected_and_delay(r["challenge_curve"][thr_idx], r["onset"])[0]
    )
    return hit / len(atk)


def tune_threshold(dev_records: List[dict]) -> int:
    """Smallest threshold index whose dev pooled-legit FAR <= FAR_BUDGET."""
    for idx in range(len(THRESHOLD_SWEEP)):
        if _far(dev_records, idx, LEGIT_FAMILIES) <= FAR_BUDGET:
            return idx
    return len(THRESHOLD_SWEEP) - 1


def frontier(eval_records: List[dict]) -> Dict[str, List[float]]:
    fars, det_adapt, det_all = [], [], []
    for idx in range(len(THRESHOLD_SWEEP)):
        fars.append(_far(eval_records, idx, LEGIT_FAMILIES))
        det_adapt.append(_det(eval_records, idx, ADAPTIVE_ATTACK_FAMILIES))
        det_all.append(_det(eval_records, idx, ATTACK_FAMILIES))
    return {"far": fars, "det_adaptive": det_adapt, "det_all": det_all}


def _bootstrap_mean_diff(diffs: List[float]) -> Dict[str, float]:
    if not diffs:
        return {"mean": 0.0, "lo": 0.0, "hi": 0.0, "n": 0}
    rng = np.random.default_rng(BOOT_SEED)
    arr = np.asarray(diffs, dtype=np.float64)
    boots = np.empty(N_BOOT, dtype=np.float64)
    n = arr.shape[0]
    for b in range(N_BOOT):
        idx = rng.integers(0, n, size=n)
        boots[b] = float(arr[idx].mean())
    return {
        "mean": float(arr.mean()),
        "lo": float(np.percentile(boots, 2.5)),
        "hi": float(np.percentile(boots, 97.5)),
        "n": n,
    }


def _bootstrap_rate_diff(
    pairs: List[Tuple[bool, bool]]
) -> Dict[str, float]:
    """Bootstrap CI of rate(H) - rate(I) over paired detection outcomes."""
    if not pairs:
        return {"mean": 0.0, "lo": 0.0, "hi": 0.0, "n": 0}
    rng = np.random.default_rng(BOOT_SEED + 1)
    h = np.array([p[0] for p in pairs], dtype=np.float64)
    i = np.array([p[1] for p in pairs], dtype=np.float64)
    n = h.shape[0]
    boots = np.empty(N_BOOT, dtype=np.float64)
    for b in range(N_BOOT):
        idx = rng.integers(0, n, size=n)
        boots[b] = float(h[idx].mean() - i[idx].mean())
    return {
        "mean": float(h.mean() - i.mean()),
        "lo": float(np.percentile(boots, 2.5)),
        "hi": float(np.percentile(boots, 97.5)),
        "n": n,
    }


def operating_metrics(
    eval_records: List[dict], op_idx: int, cfg: StudyConfig
) -> dict:
    adapt = [r for r in eval_records if r["family"] in ADAPTIVE_ATTACK_FAMILIES]
    delays = []
    damages = []
    for r in adapt:
        cs = r["challenge_curve"][op_idx]
        det, delay = detected_and_delay(cs, r["onset"])
        if det:
            delays.append(delay)
        damages.append(damage_weighted_loss(cs, r["onset"], cfg))
    sparse = [r for r in eval_records if r["family"] == "F12_sparse_missing_evidence"]
    sparse_fail = (
        sum(
            1
            for r in sparse
            if not detected_and_delay(r["challenge_curve"][op_idx], r["onset"])[0]
        )
        / len(sparse)
        if sparse
        else None
    )
    # calibration sensitivity: FAR spread across sigma at op threshold
    sigmas = sorted({r["params"]["sigma"] for r in eval_records})
    far_by_sigma = {}
    for s in sigmas:
        sub = [r for r in eval_records if r["params"]["sigma"] == s]
        far_by_sigma[s] = _far(sub, op_idx, LEGIT_FAMILIES)
    cal_spread = (max(far_by_sigma.values()) - min(far_by_sigma.values())
                  if far_by_sigma else 0.0)
    # poisoning template metrics (family F09)
    pois = [r for r in eval_records if r["family"] == "F09_gate_aware_poisoning"]
    d_par = [r["template"]["d_parallel"] for r in pois
             if r["template"]["d_parallel"] is not None]
    d_perp = [r["template"]["d_perp"] for r in pois
              if r["template"]["d_perp"] is not None]
    erosion = [r["template"]["margin_erosion"] for r in pois
               if r["template"]["margin_erosion"] is not None]

    return {
        "op_threshold_idx": op_idx,
        "op_threshold": THRESHOLD_SWEEP[op_idx],
        "eval_far_pooled_legit": _far(eval_records, op_idx, LEGIT_FAMILIES),
        "det_adaptive": _det(eval_records, op_idx, ADAPTIVE_ATTACK_FAMILIES),
        "det_abrupt_F06": _det(eval_records, op_idx, ["F06_abrupt_takeover"]),
        "drift_far": _far(eval_records, op_idx, DRIFT_FRICTION_FAMILIES),
        "median_delay": float(statistics.median(delays)) if delays else None,
        "p95_delay": (float(np.percentile(delays, 95)) if delays else None),
        "mean_damage_weighted_loss": float(np.mean(damages)) if damages else None,
        "sparse_failure_rate": sparse_fail,
        "calibration_far_spread": cal_spread,
        "poison_d_parallel_mean": float(np.mean(d_par)) if d_par else None,
        "poison_d_perp_mean": float(np.mean(d_perp)) if d_perp else None,
        "poison_margin_erosion_mean": float(np.mean(erosion)) if erosion else None,
        "poison_template_update_mean": float(np.mean(
            [r["template"]["template_update_amount"] for r in pois])) if pois else None,
    }


def compare_H_vs_I(
    paired_eval: Dict[Tuple[str, int], Dict[str, dict]],
    op_idx_H: int,
    op_idx_I: int,
    cfg: StudyConfig,
) -> dict:
    det_pairs: List[Tuple[bool, bool]] = []
    damage_diffs: List[float] = []
    dpar_diffs: List[float] = []
    drift_fp_pairs: List[Tuple[bool, bool]] = []

    for (family, _seed), byarm in paired_eval.items():
        if "H" not in byarm or "I" not in byarm:
            continue
        rH, rI = byarm["H"], byarm["I"]
        if family in ADAPTIVE_ATTACK_FAMILIES:
            dH = detected_and_delay(rH["challenge_curve"][op_idx_H], rH["onset"])[0]
            dI = detected_and_delay(rI["challenge_curve"][op_idx_I], rI["onset"])[0]
            det_pairs.append((dH, dI))
            damage_diffs.append(
                damage_weighted_loss(rH["challenge_curve"][op_idx_H], rH["onset"], cfg)
                - damage_weighted_loss(rI["challenge_curve"][op_idx_I], rI["onset"], cfg)
            )
            if (rH["template"]["d_parallel"] is not None
                    and rI["template"]["d_parallel"] is not None):
                dpar_diffs.append(
                    rH["template"]["d_parallel"] - rI["template"]["d_parallel"]
                )
        if family in DRIFT_FRICTION_FAMILIES:
            fH = rH["challenge_curve"][op_idx_H] != NO_CHALLENGE
            fI = rI["challenge_curve"][op_idx_I] != NO_CHALLENGE
            drift_fp_pairs.append((fH, fI))

    return {
        "detection_rate_diff_H_minus_I": _bootstrap_rate_diff(det_pairs),
        "damage_loss_diff_H_minus_I": _bootstrap_mean_diff(damage_diffs),
        "d_parallel_diff_H_minus_I": _bootstrap_mean_diff(dpar_diffs),
        "drift_false_challenge_diff_H_minus_I": _bootstrap_rate_diff(drift_fp_pairs),
    }


def decide_verdict(cmp: dict) -> Tuple[str, List[str]]:
    reasons: List[str] = []
    det = cmp["detection_rate_diff_H_minus_I"]
    dmg = cmp["damage_loss_diff_H_minus_I"]
    dpar = cmp["d_parallel_diff_H_minus_I"]
    drift = cmp["drift_false_challenge_diff_H_minus_I"]

    det_better = det["lo"] > 0.0                      # H detects strictly more
    dmg_better = dmg["hi"] < 0.0                      # H strictly less damage
    dpar_better = dpar["hi"] < 0.0 and dpar["n"] > 0  # H strictly less displacement

    if det_better:
        reasons.append("H detection rate on adaptive attacks strictly exceeds I "
                       f"(95% CI {det['lo']:.3f}..{det['hi']:.3f}).")
    if dmg_better:
        reasons.append("H damage-weighted loss strictly below I "
                       f"(95% CI {dmg['lo']:.3f}..{dmg['hi']:.3f}).")
    if dpar_better:
        reasons.append("H attacker-direction displacement strictly below I "
                       f"(95% CI {dpar['lo']:.4f}..{dpar['hi']:.4f}).")

    if det_better or dmg_better or dpar_better:
        return "SECOND_ORDER_ADDS_SECURITY_VALUE", reasons

    friction_better = drift["hi"] < 0.0               # H fewer drift false challenges
    if friction_better:
        reasons.append("H reduces legitimate-drift false challenges vs I "
                       f"(95% CI {drift['lo']:.3f}..{drift['hi']:.3f}), "
                       "but shows no adaptive-attack security improvement.")
        return "FRICTION_ONLY_INCREMENTAL_VALUE", reasons

    reasons.append("No held-out adaptive-attack improvement and no drift-friction "
                   "reduction survives the paired bootstrap CI.")
    return "SECOND_ORDER_DIFFERENTIATION_NOT_SUPPORTED", reasons


def analyze(cfg: StudyConfig, results_dir: Path = RESULTS_DIR) -> dict:
    records = load_records(results_dir / "events.jsonl")
    index, paired = _index(records)

    arms = sorted(index.get("eval", {}).keys())
    per_arm: Dict[str, dict] = {}
    frontiers: Dict[str, dict] = {}
    op_idx: Dict[str, int] = {}

    for arm in arms:
        dev = index["dev"][arm]
        ev = index["eval"][arm]
        idx = tune_threshold(dev)
        op_idx[arm] = idx
        per_arm[arm] = operating_metrics(ev, idx, cfg)
        frontiers[arm] = frontier(ev)

    cmp = compare_H_vs_I(paired["eval"], op_idx["H"], op_idx["I"], cfg)
    verdict, reasons = decide_verdict(cmp)

    out = {
        "operating_threshold_idx": op_idx,
        "per_arm": per_arm,
        "frontiers": frontiers,
        "H_vs_I": cmp,
        "verdict": verdict,
        "verdict_reasons": reasons,
        "det_fixed_far": DET_FIXED_FAR,
        "far_budget": FAR_BUDGET,
    }
    with (results_dir / "analysis.json").open("w") as fh:
        json.dump(out, fh, indent=2)
    return out
