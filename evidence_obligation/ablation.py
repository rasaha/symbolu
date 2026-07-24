"""Phases 18-19 - Ablation study + complexity challenge.

Ablation: disable each feature of the reference component and measure the downstream effect on clean
allow (utility) and unsafe allow (safety) - identifying load-bearing vs redundant features and the
minimum viable safe policy.

Complexity challenge: compare the full component against simple comparators (risk-only, claim+risk,
source+authority, claim+source+risk) and a learned comparator on utility, safety, and rule count.

Deterministic, read-only. Writes eval_results/ablation.json.
"""
from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List

from evidence_obligation import policy, downstream, baselines, dataset, schema as s

_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_results")

_ABLATIONS = ["authority_guard", "risk_escalation", "structural_floors", "source_role", "risk"]


def _predict_ablated(ablate: frozenset) -> Callable:
    def f(item):
        from evidence_obligation import classifier
        try:
            o = policy.assign(item, ablate=ablate)
        except Exception:
            return s.new_obligation(item.get("artifact_id", "c"), "",
                                    evidence_obligation_type=s.INDETERMINATE_OBLIGATION)
        return o
    return f


def _eval(predict) -> Dict[str, Any]:
    held = dataset.load_partition("HELD_OUT_NATURAL")
    adv = dataset.load_partition("ADVERSARIAL_OBLIGATION")
    h = downstream.evaluate_policy(held, predict)
    a = downstream.evaluate_policy(adv, predict)
    return {"clean_allow_rate": h["clean_allow_rate"], "over_qualification_rate": h["over_qualification_rate"],
            "held_unsafe_allow": h["unsafe_allow"], "high_risk_unsafe_allow": h["high_risk_unsafe_allow"],
            "adversarial_unsafe_allow": a["unsafe_allow"]}


def compute() -> Dict[str, Any]:
    baselines._train_S(dataset.load_partition("DEVELOPMENT"))
    full = _eval(_predict_ablated(frozenset()))

    ablations = {}
    for feat in _ABLATIONS:
        res = _eval(_predict_ablated(frozenset([feat])))
        ablations[feat] = {
            **res,
            "clean_allow_delta": round(res["clean_allow_rate"] - full["clean_allow_rate"], 4),
            "adversarial_unsafe_delta": res["adversarial_unsafe_allow"] - full["adversarial_unsafe_allow"],
            # load-bearing for SAFETY if removing it increases unsafe allows
            "load_bearing_for_safety": res["adversarial_unsafe_allow"] > full["adversarial_unsafe_allow"]
            or res["high_risk_unsafe_allow"] > full["high_risk_unsafe_allow"],
        }

    # complexity comparators (rule counts are indicative)
    comparators = {
        "Simple1_risk_only": (baselines.C_risk_only, 3),
        "Simple2_claim_risk": (baselines.G_claim_type_risk, 31),
        "Simple3_source_authority": (baselines.H_source_authority, 15),
        "Simple4_claim_source_risk": (baselines.J_claim_type_source_risk, 46),
        "Learned_S": (baselines.S_learned, 0),
        "Full_Q": (baselines.Q_reference, 90),
    }
    comp = {}
    for name, (fn, rules) in comparators.items():
        comp[name] = {**_eval(fn), "approx_rule_count": rules}

    load_bearing = [f for f, r in ablations.items() if r["load_bearing_for_safety"]]
    return {
        "full_component": full,
        "ablations": ablations,
        "load_bearing_for_safety": load_bearing,
        "redundant_for_safety": [f for f in _ABLATIONS if f not in load_bearing],
        "complexity_comparators": comp,
        "note": "ablation removes one feature from the full component; a feature is load-bearing for "
                "safety if removing it increases unsafe allows. Comparators contrast utility/safety vs "
                "approx rule count.",
    }


def freeze() -> Dict[str, Any]:
    import hashlib
    m = compute()
    m["ablation_sha256"] = hashlib.sha256(json.dumps(
        {"ablations": m["ablations"], "complexity_comparators": m["complexity_comparators"]},
        sort_keys=True).encode()).hexdigest()
    os.makedirs(_OUT, exist_ok=True)
    with open(os.path.join(_OUT, "ablation.json"), "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return m


if __name__ == "__main__":
    m = freeze()
    f = m["full_component"]
    print(f"FULL: clean={f['clean_allow_rate']} adv_unsafe={f['adversarial_unsafe_allow']} "
          f"hi_unsafe={f['high_risk_unsafe_allow']}")
    print(f"{'ablate feature':22s} {'clean':>7s} {'clean_d':>8s} {'adv_unsafe':>11s} {'load_bearing':>13s}")
    for feat, r in m["ablations"].items():
        print(f"{feat:22s} {r['clean_allow_rate']:>7.3f} {r['clean_allow_delta']:>8.3f} "
              f"{r['adversarial_unsafe_allow']:>11d} {str(r['load_bearing_for_safety']):>13s}")
    print("load-bearing for safety:", m["load_bearing_for_safety"])
    print(f"\n{'comparator':28s} {'clean':>7s} {'adv_unsafe':>11s} {'rules':>6s}")
    for name, r in m["complexity_comparators"].items():
        print(f"{name:28s} {r['clean_allow_rate']:>7.3f} {r['adversarial_unsafe_allow']:>11d} {r['approx_rule_count']:>6d}")
