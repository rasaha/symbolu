"""Reproducible evaluation harness.

Runs arms A-G across three telemetry regimes (cold / partial / mature), scores
every arm against ground truth, computes the mandatory G-vs-F self-assessment
ablation (per regime), tests adversarial-advisory harm and routing stability,
and writes all artifacts into ./results.

Deterministic end to end. Run:  python3 harness.py
"""

from __future__ import annotations

import os
from typing import Any, Dict

import baselines as bl
import metrics as met
import simulator as sim
from common import (
    REGIMES,
    RESULTS_DIR,
    load_corpus,
    load_policy,
    load_registry,
    save_json,
)
from simulator import ADVISORY_PREFLIGHT_COST, ADVISORY_PREFLIGHT_LATENCY_MS


def _advisory_map(task: Dict[str, Any], adversarial: bool = False) -> Dict[str, Any]:
    return {mid: sim.advisory_feed(mid, task, adversarial=adversarial) for mid in sim.MODEL_IDS}


def _charge_preflight(rec: Dict[str, Any]) -> None:
    if not rec["abstained"] and rec["selected"] is not None:
        rec["preflight_cost"] = ADVISORY_PREFLIGHT_COST
        rec["preflight_latency_ms"] = ADVISORY_PREFLIGHT_LATENCY_MS


def run_all() -> Dict[str, Any]:
    registry = load_registry()
    corpus = load_corpus()
    policy = load_policy()
    ent_policy = corpus["enterprise_policy"]
    approved = ent_policy["approved_providers"]
    tasks = corpus["tasks"]

    by_regime: Dict[str, Dict[str, Any]] = {}
    records_store: Dict[str, Dict[str, Dict[str, Any]]] = {}  # regime -> arm -> {tid: rec}

    for regime in REGIMES:
        telemetry = sim.telemetry_feed(regime)
        by_regime[regime] = {}
        records_store[regime] = {}
        for arm, fn in bl.ARMS.items():
            recs: Dict[str, Dict[str, Any]] = {}
            for task in tasks:
                advisory = _advisory_map(task) if arm == "G" else None
                rec = fn(task, registry, ent_policy, telemetry, policy, regime, advisory)
                if arm == "G":
                    _charge_preflight(rec)
                recs[task["task_id"]] = rec
            records_store[regime][arm] = recs
            by_regime[regime][arm] = met.score_records(recs, corpus, approved)

    # -------- mandatory ablation: G - F per regime --------
    ablation: Dict[str, Any] = {}
    ablate_metrics = ["mean_regret", "quality_threshold_success_rate", "constraint_violation_rate",
                      "mean_cost_per_successful_task", "p95_latency_ms", "unnecessary_strongest_use_rate"]
    for regime in REGIMES:
        f, g = by_regime[regime]["F"], by_regime[regime]["G"]
        d = {}
        for m in ablate_metrics:
            if f[m] is None or g[m] is None:
                d[m] = None
            else:
                d[m] = round(g[m] - f[m], 4)
        ablation[regime] = {"G_minus_F": d, "F": {m: f[m] for m in ablate_metrics},
                            "G": {m: g[m] for m in ablate_metrics}}

    # -------- adversarial advisory harm test (overconfident self-assessment) --------
    adversarial: Dict[str, Any] = {}
    for regime in REGIMES:
        telemetry = sim.telemetry_feed(regime)
        recs: Dict[str, Dict[str, Any]] = {}
        for task in tasks:
            adv = _advisory_map(task, adversarial=True)
            rec = bl.arm_G_policy_selfassess(task, registry, ent_policy, telemetry, policy, regime, adv)
            _charge_preflight(rec)
            recs[task["task_id"]] = rec
        gadv = met.score_records(recs, corpus, approved)
        f = by_regime[regime]["F"]
        adversarial[regime] = {
            "G_adversarial": {m: gadv[m] for m in ablate_metrics},
            "F": {m: f[m] for m in ablate_metrics},
            "regret_delta_vs_F": (round(gadv["mean_regret"] - f["mean_regret"], 4)),
        }

    # -------- routing stability (selection agreement under 1% quality perturbation) --------
    stability: Dict[str, Any] = {}
    for arm in ("F", "G"):
        stability[arm] = {}
        for regime in REGIMES:
            base_tel = sim.telemetry_feed(regime)
            pert_tel = {mid: {tc: {"estimate": min(1.0, v["estimate"] * 1.01), "n": v["n"]}
                              for tc, v in cls.items()} for mid, cls in base_tel.items()}
            unchanged = 0
            for task in tasks:
                advisory = _advisory_map(task) if arm == "G" else None
                r1 = bl.ARMS[arm](task, registry, ent_policy, base_tel, policy, regime, advisory)
                r2 = bl.ARMS[arm](task, registry, ent_policy, pert_tel, policy, regime, advisory)
                if r1["selected"] == r2["selected"]:
                    unchanged += 1
            stability[arm][regime] = round(unchanged / len(tasks), 4)

    # -------- determinism check --------
    telemetry = sim.telemetry_feed("mature")
    det_ok = True
    for task in tasks[:10]:
        a = bl.arm_F_policy(task, registry, ent_policy, telemetry, policy, "mature")
        b = bl.arm_F_policy(task, registry, ent_policy, telemetry, policy, "mature")
        if a != b:
            det_ok = False
            break

    results = {
        "meta": {
            "registry_version": registry["version"],
            "corpus_version": corpus["version"],
            "policy_version": policy["version"],
            "ground_truth_version": sim._GT["version"],
            "n_tasks": len(tasks),
            "regimes": REGIMES,
            "arm_labels": bl.ARM_LABELS,
            "advisory_preflight_cost": ADVISORY_PREFLIGHT_COST,
            "advisory_preflight_latency_ms": ADVISORY_PREFLIGHT_LATENCY_MS,
            "synthetic_assumptions": {
                "registry": registry["synthetic_assumptions"],
                "context_rot_soft": sim.CONTEXT_ROT_SOFT,
                "advisory_bias": sim.ADVISORY_BIAS,
                "advisory_noise": sim.ADVISORY_NOISE,
                "telemetry_obs_noise": sim.OBS_NOISE_BASE,
            },
        },
        "by_regime": by_regime,
        "ablation_G_minus_F": ablation,
        "adversarial_advisory": adversarial,
        "routing_stability": stability,
        "determinism_check_passed": det_ok,
    }

    # -------- persist decision records (F & G, mature) + sample full records --------
    fg_mature = {"F": records_store["mature"]["F"], "G": records_store["mature"]["G"]}
    save_json(os.path.join(RESULTS_DIR, "decision_records_FG_mature.json"), fg_mature)

    sample_ids = ["t900_reasoning_trap", "t901_ctx_trap", "t902_cheap_fails_quality",
                  "t903_zero_eligible", "t904_ambiguous"]
    samples = {tid: {"F": records_store["mature"]["F"][tid], "G": records_store["mature"]["G"][tid]}
               for tid in sample_ids if tid in records_store["mature"]["F"]}
    save_json(os.path.join(RESULTS_DIR, "decision_record_samples.json"), samples)

    save_json(os.path.join(RESULTS_DIR, "aggregate_metrics.json"), results)
    return results


def _fmt(v: Any) -> str:
    return "  n/a" if v is None else f"{v:>6}"


def print_summary(results: Dict[str, Any]) -> None:
    arms = ["A", "B", "C", "D", "E", "F", "G"]
    key_metrics = [("mean_regret", "regret"), ("constraint_violation_rate", "viol"),
                   ("quality_threshold_success_rate", "qok"),
                   ("mean_cost_per_successful_task", "$/ok"),
                   ("p95_latency_ms", "p95ms"),
                   ("unnecessary_strongest_use_rate", "overuse"),
                   ("explanation_completeness_rate", "explOK")]
    for regime in results["meta"]["regimes"]:
        print(f"\n=== regime: {regime} ===")
        header = "arm  " + "".join(f"{lbl:>9}" for _, lbl in key_metrics)
        print(header)
        for arm in arms:
            m = results["by_regime"][regime][arm]
            row = f" {arm}   " + "".join(f"{_fmt(m[k]):>9}" for k, _ in key_metrics)
            print(row)
    print("\n=== G - F ablation (self-assessment marginal value) ===")
    for regime in results["meta"]["regimes"]:
        d = results["ablation_G_minus_F"][regime]["G_minus_F"]
        print(f" {regime:8} dRegret={d['mean_regret']}  dQok={d['quality_threshold_success_rate']}  "
              f"dViol={d['constraint_violation_rate']}  dOveruse={d['unnecessary_strongest_use_rate']}")
    print("\n=== adversarial (overconfident) advisory: regret delta vs F ===")
    for regime in results["meta"]["regimes"]:
        print(f" {regime:8} {results['adversarial_advisory'][regime]['regret_delta_vs_F']}")
    print("\n=== routing stability (selection agreement under 1% perturbation) ===")
    for arm in ("F", "G"):
        print(f" arm {arm}: " + "  ".join(f"{r}={results['routing_stability'][arm][r]}" for r in REGIMES))
    print(f"\ndeterminism check passed: {results['determinism_check_passed']}")


if __name__ == "__main__":
    res = run_all()
    print_summary(res)
