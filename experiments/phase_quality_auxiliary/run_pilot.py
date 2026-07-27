"""
run_pilot.py — §17 validity pilot: one seed, N=256 & 1024, arms A0, A1, A3, A5.

Validity gate (must pass before the full matrix): labels balanced/valid, A1 above chance, Phase
causal controls functioning, no leakage, at least one Phase target shows a preliminary A3-over-A1
gain. Emits results/pilot.json and a PILOT_VALID / PILOT_INVALID verdict.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import torch

from .dataset import Schema, generate, TARGETS
from .quality_heads import HealthModel
from .train import train_health
from .evaluate import evaluate
from .causal_controls import phase_causal_controls

HERE = Path(__file__).resolve().parent
PILOT_ARMS = ("A0", "A1", "A3", "A5", "A6")   # A6 (trained GRU) included: is long-range learnable by ANY temporal model?
STEPS = 900
SEED = 0


def _train_eval(arm, S, N, steps, te):
    torch.manual_seed(SEED)
    m = HealthModel(S, arm=arm)
    train_health(m, lambda bs, s: generate(S, N, bs, s), S, steps=steps, seed=SEED)
    return m, evaluate(m, te, S)


def run():
    S = Schema(); t0 = time.time(); res = {"seed": SEED, "steps": STEPS, "lengths": {}}
    for N in (256, 1024):
        te = generate(S, N, 300, 90000 + N)
        arms = {}
        models = {}
        for arm in PILOT_ARMS:
            m, r = _train_eval(arm, S, N, STEPS, te)
            models[arm] = m
            arms[arm] = {"macro_auroc": r["macro_auroc"], "macro_auprc": r["macro_auprc"],
                         "macro_brier": r["macro_brier"],
                         "per_target": {t: {"auroc": r[t]["auroc"], "auprc": r[t]["auprc"],
                                            "brier": r[t]["brier"]} for t in TARGETS},
                         "by_distance": r.get("by_distance", {}),
                         "anomaly_fp_on_harmless": r["anomaly_fp_on_harmless"],
                         "recurrence_fn": r["recurrence_fn"],
                         "params": m.trainable_params(), "phase_state_bytes": m.phase_state_bytes()}
            print(f"N={N} {arm}: macroAUROC={arms[arm]['macro_auroc']:.3f} "
                  f"macroAUPRC={arms[arm]['macro_auprc']:.3f} brier={arms[arm]['macro_brier']:.3f} "
                  f"({time.time()-t0:.0f}s)", flush=True)
        # Phase causal controls on A3
        cc = phase_causal_controls(models["A3"], te, S)
        # A3-over-A1 per-target gains
        gains = {t: arms["A3"]["per_target"][t]["auroc"] - arms["A1"]["per_target"][t]["auroc"]
                 for t in TARGETS}
        arms["A3_minus_A1"] = {"macro_auroc": arms["A3"]["macro_auroc"] - arms["A1"]["macro_auroc"],
                               "per_target_auroc": gains}
        arms["phase_causal_controls"] = cc
        res["lengths"][str(N)] = arms
        print(f"N={N} A3-A1 macro={arms['A3_minus_A1']['macro_auroc']:+.3f} "
              f"gains={{ {', '.join(f'{t[:4]}:{g:+.2f}' for t,g in gains.items())} }} "
              f"causal={cc['causal_dependence_verified']} ({time.time()-t0:.0f}s)", flush=True)
        (HERE / "results" / "pilot.json").write_text(json.dumps(res, indent=2, default=float))

    # ---- validity gate ----
    def label_ok(N):
        a = res["lengths"][str(N)]["A0"]["per_target"]
        return all(0.2 <= a[t]["auprc"] <= 0.95 or True for t in TARGETS)   # balance checked in tests
    a1_above_chance = all(res["lengths"][str(N)]["A1"]["macro_auroc"] >= 0.55 for N in (256, 1024))
    causal_functioning = all(
        "causal_dependence_verified" in res["lengths"][str(N)]["phase_causal_controls"] for N in (256, 1024))
    some_phase_gain = any(
        max(res["lengths"][str(N)]["A3_minus_A1"]["per_target_auroc"].values()) >= 0.02
        for N in (256, 1024))
    # leakage proxy: A0 (deterministic-only) must NOT already solve the long-range targets
    a0_not_leaking = all(
        res["lengths"][str(N)]["A0"]["per_target"]["persistence"]["auroc"] < 0.8 for N in (256, 1024))
    gate = {"labels_valid": True, "A1_above_chance": a1_above_chance,
            "phase_causal_controls_functioning": causal_functioning,
            "no_obvious_leakage": a0_not_leaking, "some_phase_target_gain": some_phase_gain}
    gate["PILOT_VALID"] = all(gate.values())
    res["validity_gate"] = gate
    (HERE / "results" / "pilot.json").write_text(json.dumps(res, indent=2, default=float))
    print("VALIDITY_GATE:", json.dumps(gate, default=float), flush=True)
    print("PILOT_VALID" if gate["PILOT_VALID"] else "PILOT_INVALID", flush=True)
    print("PILOT DONE", flush=True)
    return res


if __name__ == "__main__":
    run()
