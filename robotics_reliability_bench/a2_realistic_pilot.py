#!/usr/bin/env python3
"""Amendment A2 — realistic-noise pilot (evaluation-only, NO tuning).

REAL-SENSOR GATE NOT DISCHARGED. ``NuScenesAdapter`` is unimplemented
scaffolding, no dataset is on disk, and nuscenes.org is unreachable from the
execution environment, so this pilot runs on the repository's
``RealisticNoiseAdapter`` (AR(1)-correlated noise, heavy-tailed outlier
frames) plus bench-side dropouts. Everything below is preregistered in
``PREDICTOR_TRUST_V2_PREREGISTRATION.md`` §7 A2 and scored with frozen
system configurations only.

Sub-corpus R1: the 14 ``fault_corpus`` families injected on realistic-noise
              nominal streams (M=3, T=100).
Sub-corpus R2: adapter-native scenes (M=4, T=400): gps_multipath,
              map_misalignment, constant_bias_sanity, camera_degradation
              (variance fault, reported separately), benign_native.

    python -m robotics_reliability_bench.a2_realistic_pilot

Writes ``results/a2_realistic_pilot.json``.
"""
from __future__ import annotations

import json
import os
from dataclasses import replace
from typing import Dict, List, Optional

import numpy as np

from symbolu_robotics.bcvf_autonomous.datasets.synthetic_realistic import (
    RealisticNoiseAdapter, RealisticNoiseConfig)
from robotics_reliability_bench import fault_corpus as fc
from robotics_reliability_bench.detectors import (BaselineDetector, BCVFDetector,
                                                  FusionDetector, LLTKalmanDetector)
from robotics_reliability_bench.fault_corpus import (FaultBundle, HARM_BENIGN,
                                                     HARM_COMMON, HARM_STATE)
from robotics_reliability_bench.llt_kalman_trust import A1_CONFIG
from robotics_reliability_bench.metrics import aggregate, score_family
from robotics_reliability_bench.run_incremental_value import (BCVF_MARGIN_THRESHOLD,
                                                             DETECTOR_WINDOW)

RESULTS = os.path.join(os.path.dirname(__file__), "results")
A2_SEEDS = list(range(200, 230))          # fresh; never used in any tuning
R1_M, R1_T, DT, V = 3, 100, 0.1, 5.0
DROPOUT_P, DROPOUT_LEN = 0.2, 5
R2_STEPS = 400

DATA_SOURCE = ("synthetic-realistic: symbolu_robotics.bcvf_autonomous.datasets."
               "synthetic_realistic.RealisticNoiseAdapter (AR(1) alpha=0.8 "
               "sigma=0.02, outlier frames 2% at 5x) + bench-side dropouts; "
               "NOT real sensor data")


# ---- realistic nominal streams --------------------------------------------

def _adapter(sigma_scale: float = 1.0) -> RealisticNoiseAdapter:
    cfg = RealisticNoiseConfig()
    return RealisticNoiseAdapter(replace(cfg, correlated_noise_sigma=cfg.correlated_noise_sigma * sigma_scale))


def realistic_nominal(M: int, T: int, rng: np.random.Generator,
                      sigma_scale: float = 1.0) -> np.ndarray:
    """(M, T, 3) straight-path state streams with the adapter's noise pipeline.

    Uses the adapter's own ``_apply_correlated_noise`` / ``_apply_outlier_frames``
    on an (T, 1, 3) horizon so the per-step state is exactly ``traj[t, 0, :]``.
    """
    ad = _adapter(sigma_scale)
    t = np.arange(T) * DT
    preds = {}
    for m in range(M):
        traj = np.zeros((T, 1, 3), dtype=np.float64)
        traj[:, 0, 0] = V * t
        preds[f"M{m+1}"] = traj
    ad._apply_correlated_noise(preds, rng)
    ad._apply_outlier_frames(preds, rng)
    return np.stack([preds[f"M{m+1}"][:, 0, :] for m in range(M)], axis=0)


def bench_dropouts(M: int, T: int, rng: np.random.Generator,
                   trajs: np.ndarray) -> Optional[np.ndarray]:
    """Per predictor, with prob DROPOUT_P, one DROPOUT_LEN-tick hold with
    valid_mask False at a seeded position in ticks 5..T-10. In place."""
    masks = np.ones((M, T), dtype=bool)
    any_drop = False
    for m in range(M):
        if rng.random() < DROPOUT_P:
            s = int(rng.integers(5, T - 10))
            trajs[m, s:s + DROPOUT_LEN, :] = trajs[m, s, :]
            masks[m, s:s + DROPOUT_LEN] = False
            any_drop = True
    return masks if any_drop else None


# ---- R1: corpus families on realistic noise --------------------------------

def r1_bundle(family: str, seed: int) -> FaultBundle:
    """Mirror of each ``fault_corpus`` family with the realistic nominal in
    place of ``_nominal``. Magnitudes, targets, onsets, labels are the corpus's."""
    M, H = R1_M, R1_T
    rng = np.random.default_rng(seed)
    trajs = realistic_nominal(M, H, rng)
    masks = bench_dropouts(M, H, np.random.default_rng(seed + 1000), trajs)
    t = np.arange(H)
    ts = t * DT
    kw = dict(valid_masks=masks)

    if family == "gaussian_noise":
        return FaultBundle(family, trajs, None, None, False, HARM_BENIGN, False, **kw,
                           metadata={"note": "realistic nominal, no injection"})
    if family == "constant_bias":
        trajs[1, :, 1] += 0.5
        return FaultBundle(family, trajs, 1, 0, True, HARM_STATE, False, **kw)
    if family == "slow_bias":
        trajs[1, :, 1] += np.clip(t - 10, 0, None) * 0.02
        return FaultBundle(family, trajs, 1, 10, True, HARM_STATE, False, **kw)
    if family == "linear_drift":
        trajs[1, :, 1] += 0.05 * t
        return FaultBundle(family, trajs, 1, 0, True, HARM_STATE, False, **kw)
    if family == "accelerating":
        trajs[1, :, 1] += np.where(t >= 5, 0.5 * 0.5 * (ts - 5 * DT) ** 2, 0.0)
        return FaultBundle(family, trajs, 1, 5, True, HARM_STATE, True, **kw)
    if family == "abrupt_jump":
        trajs[1, 25:, 1] += 0.8
        return FaultBundle(family, trajs, 1, 25, True, HARM_STATE, True, **kw)
    if family == "stuck_sensor":
        trajs[1, 15:, :] = trajs[1, 15, :]
        return FaultBundle(family, trajs, 1, 15, True, HARM_STATE, False, **kw)
    if family == "delayed_predictor":
        src = trajs[1].copy()
        trajs[1, 6:, :] = src[:-6, :]
        trajs[1, :6, :] = src[0, :]
        return FaultBundle(family, trajs, 1, 0, True, HARM_STATE, False, **kw)
    if family == "stale_predictor":
        trajs[2, 20:, :] = trajs[2, 20, :]
        m2 = np.ones((M, H), dtype=bool) if masks is None else masks.copy()
        m2[2, 20:] = False
        return FaultBundle(family, trajs, 2, 20, True, HARM_STATE, False, valid_masks=m2)
    if family == "correlated_failure":
        trajs[1, :, 1] += 0.5
        trajs[2, :, 1] += 0.5
        return FaultBundle(family, trajs, None, 0, True, HARM_STATE, False, **kw)
    if family == "all_wrong":
        for m in range(M):
            trajs[m, :, 1] += 0.05 * t
        return FaultBundle(family, trajs, None, 0, True, HARM_COMMON, False, **kw)
    if family == "precise_biased":
        low = realistic_nominal(1, H, np.random.default_rng(seed + 99), sigma_scale=0.1)[0]
        trajs[1] = low
        trajs[1, :, 1] += 0.4
        return FaultBundle(family, trajs, 1, 0, True, HARM_STATE, False, **kw)
    if family == "noisy_unbiased":
        trajs[1] += np.random.default_rng(seed + 7).normal(0.0, 0.15, size=trajs[1].shape)
        return FaultBundle(family, trajs, None, None, False, HARM_BENIGN, True, **kw)
    if family == "calibration_drift":
        g = np.clip(t - 20, 0, None) / max(1, (H - 20))
        trajs[1] += np.random.default_rng(seed + 13).normal(0.0, 1.0, size=(H, 3)) * (0.2 * g)[:, None]
        return FaultBundle(family, trajs, None, 20, False, HARM_BENIGN, True, **kw)
    raise ValueError(family)


# ---- R2: adapter-native scenes ----------------------------------------------

R2_HARM = {"gps_multipath": 50, "map_misalignment": 50, "constant_bias_sanity": 0}


def r2_bundle(family: str, seed: int) -> FaultBundle:
    cfg = RealisticNoiseConfig(seed=seed, num_scenes=4)
    ad = RealisticNoiseAdapter(cfg)
    if family == "benign_native":
        rng = np.random.default_rng(seed * 1000 + 99)
        T, H = cfg.steps_per_scene, cfg.horizon
        preds = {}
        for name in ("M1", "M2", "M3", "M4"):
            traj = np.zeros((T, H, 3))
            for h in range(H):
                traj[:, h, 0] = np.arange(T) * cfg.dt * 5.0 + (h + 1) * cfg.dt * 5.0
            preds[name] = traj
        ad._apply_correlated_noise(preds, rng)
        ad._apply_outlier_frames(preds, rng)
        trajs = np.stack([preds[n][:, 0, :] for n in ("M1", "M2", "M3", "M4")])
        return FaultBundle(family, trajs, None, None, False, HARM_BENIGN, False,
                           metadata={"note": "adapter noise pipeline, no failure"})
    idx = list(cfg.failure_types).index(family)
    sc = ad.load_scene(f"scene_{seed}_{idx:03d}_{family}")
    trajs = np.stack([sc.predictor_trajectories[n][:, 0, :] for n in ("M1", "M2", "M3", "M4")])
    if family in R2_HARM:
        return FaultBundle(family, trajs, 3, R2_HARM[family], True, HARM_STATE,
                           bcvf_visible=(family != "constant_bias_sanity"),
                           metadata={"note": "adapter-native failure on M4"})
    if family == "camera_degradation":
        # variance fault: excluded from recall aggregate; reported separately
        return FaultBundle(family, trajs, 3, 50, True, HARM_STATE, True,
                           metadata={"variance_fault": True})
    raise ValueError(family)


R2_FAMILIES = ["gps_multipath", "map_misalignment", "constant_bias_sanity",
               "camera_degradation", "benign_native"]


# ---- scoring -----------------------------------------------------------------

def _systems() -> List:
    baseline = BaselineDetector()
    a1 = LLTKalmanDetector(A1_CONFIG, name="LLTKalman-A1")
    bcvf = BCVFDetector(margin_threshold=BCVF_MARGIN_THRESHOLD, window=DETECTOR_WINDOW)
    fus = FusionDetector(a1, bcvf)
    fus.name = "Fusion(LLT-A1+BCVF)"
    return [baseline, a1, bcvf, fus]


def _degraded_rate(det, bundles: List[FaultBundle], target: int) -> Optional[float]:
    """Rate at which the target predictor is at least DEGRADED (deterministic
    detectors expose per-predictor states; BCVF does not -> None)."""
    n = 0
    for b in bundles:
        out = det.detect(b)
        pp = out.metadata.get("per_predictor")
        if pp is None:
            return None
        st = {i: s for i, s, _ in pp}.get(target)
        n += int(st in ("DEGRADED", "SUSPECT", "ABSTAIN"))
    return n / len(bundles)


def _fam_row(fs) -> Dict:
    return {"harm_class": fs.harm_class, "fault_active": fs.fault_active,
            "detected_rate": round(fs.detected_rate, 3),
            "attribution_acc": None if fs.attribution_acc is None else round(fs.attribution_acc, 3),
            "mean_delay": None if fs.mean_delay is None else round(fs.mean_delay, 1),
            "abstain_rate": round(fs.abstain_rate, 3),
            "false_alarm": fs.false_alarm, "runtime_us": round(fs.mean_runtime_us, 1)}


def _round(d: Dict) -> Dict:
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()}


def run() -> Dict:
    r1 = {fam: [r1_bundle(fam, s) for s in A2_SEEDS] for fam in fc.FAMILIES}
    r2 = {fam: [r2_bundle(fam, s) for s in A2_SEEDS] for fam in R2_FAMILIES}
    out: Dict = {"amendment": "A2", "real_sensor_gate_discharged": False,
                 "data_source": DATA_SOURCE, "seeds": A2_SEEDS,
                 "r1": {"M": R1_M, "T": R1_T, "dropout_p": DROPOUT_P, "dropout_len": DROPOUT_LEN},
                 "r2": {"M": 4, "T": R2_STEPS, "families": R2_FAMILIES,
                        "note": "gps_multipath and map_misalignment share identical "
                                "injection code in RealisticNoiseAdapter"},
                 "per_detector": {}}
    for det in _systems():
        r1_scores = [score_family(det, b) for b in r1.values()]
        r2_all = {fam: score_family(det, b) for fam, b in r2.items()}
        r2_scores = [s for fam, s in r2_all.items() if fam != "camera_degradation"]
        # per-predictor DEGRADED-or-worse rate on M4 for the variance fault
        cam_deg = _degraded_rate(det, r2["camera_degradation"], target=3)
        # BaselineDetector lacks per_predictor metadata -> compute via its trust object
        if cam_deg is None and hasattr(det, "det") and hasattr(det.det, "evaluate"):
            n = 0
            for b in r2["camera_degradation"]:
                d = det.det.evaluate(b.trajectories, b.valid_masks)
                n += int(d.per_predictor[3].state.value != "TRUSTED")
            cam_deg = n / len(r2["camera_degradation"])
        out["per_detector"][det.name] = {
            "r1_aggregate": _round(aggregate(r1_scores)),
            "r1_per_family": {s.family: _fam_row(s) for s in r1_scores},
            "r2_aggregate_excl_camera": _round(aggregate(r2_scores)),
            "r2_per_family": {fam: _fam_row(s) for fam, s in r2_all.items()},
            "r2_camera_degradation_m4_degraded_or_worse_rate":
                None if cam_deg is None else round(cam_deg, 3),
        }
    out["verdict"] = _verdict(out)
    return out


def _verdict(out: Dict) -> Dict:
    pd = out["per_detector"]
    b, a, v = pd["DeterministicBaseline"], pd["LLTKalman-A1"], pd["BCVF"]
    ba, aa, va = b["r1_aggregate"], a["r1_aggregate"], v["r1_aggregate"]
    c = {
        "C1_recall": aa["fault_detection_recall"] >= ba["fault_detection_recall"],
        "C2_false_alarm": aa["false_alarm_rate"] <= ba["false_alarm_rate"],
        "C3_common_mode_zero": aa["common_mode_false_detection_rate"] == 0.0,
        "C4_delay": aa["detection_delay_ticks"] < ba["detection_delay_ticks"],
        "C5_H2_reproduces": (va["false_alarm_rate"] >= 2.0 * ba["false_alarm_rate"]
                             or va["fault_detection_recall"] < ba["fault_detection_recall"]),
    }
    r2a = a["r2_per_family"]
    c["C6_native_harm_attributed"] = all(
        (r2a[f]["attribution_acc"] or 0.0) >= 0.90 for f in R2_HARM)
    c["C7_native_benign"] = r2a["benign_native"]["detected_rate"] <= 0.05
    r1_ok = all(c[k] for k in ("C1_recall", "C2_false_alarm", "C3_common_mode_zero",
                              "C4_delay", "C5_H2_reproduces"))
    r2_ok = c["C6_native_harm_attributed"] and c["C7_native_benign"]
    label = ("A2_REPRODUCES" if r1_ok and r2_ok
             else "A2_PARTIAL" if (r1_ok or r2_ok) else "A2_FAILS")
    return {"header": "REAL_SENSOR_GATE_NOT_DISCHARGED", "conditions": c,
            "label": label}


def _print(out: Dict) -> None:
    for det, d in out["per_detector"].items():
        a = d["r1_aggregate"]
        print(f"{det:22s} R1 recall={a['fault_detection_recall']} FA={a['false_alarm_rate']} "
              f"cm={a['common_mode_false_detection_rate']} delay={a['detection_delay_ticks']} "
              f"attr={a['attribution_accuracy']}")
        for fam, r in d["r2_per_family"].items():
            print(f"    R2 {fam:22s} det={r['detected_rate']:.2f} attr={r['attribution_acc']} "
                  f"delay={r['mean_delay']}")
        print(f"    R2 camera_degradation M4 degraded-or-worse rate: "
              f"{d['r2_camera_degradation_m4_degraded_or_worse_rate']}")
    print("VERDICT:", json.dumps(out["verdict"]))


def main() -> int:
    os.makedirs(RESULTS, exist_ok=True)
    out = run()
    path = os.path.join(RESULTS, "a2_realistic_pilot.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    _print(out)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
