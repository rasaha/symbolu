"""Phases 17-18 - Ablation study + complexity challenge.

Ablation: disable each policy element and measure the downstream effect on clean allow (utility) and
unsafe allow (safety), identifying safety-critical / utility-critical / redundant elements and the
minimum viable policy.

Complexity challenge: incremental comparators from risk-only up to the full minimal policy, plus the
rich component. Deterministic, read-only. Writes eval_results/ablation.json.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

from minimal_evidence_policy import classifier, adapters, metrics, dataset, schema as s, baselines

_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_results")
_ELEMENTS = ["risk_floor", "claim_type", "temporal", "actionability", "invariants"]


def _predict(ablate: frozenset):
    def f(item):
        d = classifier.classify(item, ablate=ablate)
        steer = adapters.to_evidence_steer(d, item)
        return steer["evidence_state"], d.final_obligation
    return f


def _eval(ablate: frozenset) -> Dict[str, Any]:
    held = dataset.load_partition("HELD_OUT_NATURAL")
    adv = dataset.load_partition("ADVERSARIAL_INVARIANTS")
    h = metrics.score(held, _predict(ablate))
    a = metrics.score(adv, _predict(ablate))
    return {"clean_allow_rate": h["clean_allow_rate"], "held_unsafe_allow": h["unsafe_allow"],
            "adversarial_unsafe_allow": a["unsafe_allow"]}


def compute() -> Dict[str, Any]:
    full = _eval(frozenset())

    ablations = {}
    for el in _ELEMENTS:
        r = _eval(frozenset([el]))
        ablations[el] = {
            **r,
            "clean_delta": round(r["clean_allow_rate"] - full["clean_allow_rate"], 4),
            "unsafe_delta": (r["held_unsafe_allow"] + r["adversarial_unsafe_allow"])
            - (full["held_unsafe_allow"] + full["adversarial_unsafe_allow"]),
            "safety_critical": (r["held_unsafe_allow"] + r["adversarial_unsafe_allow"])
            > (full["held_unsafe_allow"] + full["adversarial_unsafe_allow"]),
            "utility_critical": r["clean_allow_rate"] < full["clean_allow_rate"] - 0.03,
        }

    # complexity comparators (incremental)
    comparators = {
        "risk_only": (frozenset(["claim_type", "temporal", "actionability", "invariants"]), 5),
        "risk+anti_self_verification": (frozenset(["claim_type", "temporal", "actionability"]), 17),
        "risk+actionability": (frozenset(["claim_type", "temporal", "invariants"]), 6),
        "risk+claim_type": (frozenset(["temporal", "actionability", "invariants"]), 12),
        "risk+claim+temporal+action": (frozenset(["invariants"]), 12),
        "full_minimal": (frozenset(), 24),
    }
    comp = {name: {**_eval(ab), "approx_rules": rules} for name, (ab, rules) in comparators.items()}
    # rich component
    rich_h = metrics.score(dataset.load_partition("HELD_OUT_NATURAL"), baselines.I_rich_component)
    rich_a = metrics.score(dataset.load_partition("ADVERSARIAL_INVARIANTS"), baselines.I_rich_component)
    comp["rich_component"] = {"clean_allow_rate": rich_h["clean_allow_rate"],
                              "held_unsafe_allow": rich_h["unsafe_allow"],
                              "adversarial_unsafe_allow": rich_a["unsafe_allow"], "approx_rules": 90}

    safety_critical = [e for e, r in ablations.items() if r["safety_critical"]]
    utility_critical = [e for e, r in ablations.items() if r["utility_critical"]]
    # minimum viable safe policy = smallest comparator with 0 held + <=0 adversarial-marginal unsafe
    mvp = None
    for name in ("risk_only", "risk+claim_type", "risk+anti_self_verification",
                 "risk+claim+temporal+action", "full_minimal"):
        c = comp[name]
        if c["held_unsafe_allow"] == 0 and c["adversarial_unsafe_allow"] == 0:
            mvp = name; break

    return {
        "full_minimal": full,
        "ablations": ablations,
        "safety_critical_elements": safety_critical,
        "utility_critical_elements": utility_critical,
        "redundant_on_this_data": [e for e in _ELEMENTS if e not in safety_critical and e not in utility_critical],
        "complexity_comparators": comp,
        "minimum_viable_safe_policy": mvp,
    }


def freeze() -> Dict[str, Any]:
    import hashlib
    m = compute()
    m["ablation_sha256"] = hashlib.sha256(json.dumps(
        {"a": m["ablations"], "c": m["complexity_comparators"]}, sort_keys=True).encode()).hexdigest()
    os.makedirs(_OUT, exist_ok=True)
    with open(os.path.join(_OUT, "ablation.json"), "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True); fh.write("\n")
    return m


if __name__ == "__main__":
    m = freeze()
    f = m["full_minimal"]
    print(f"FULL: clean={f['clean_allow_rate']} held_unsafe={f['held_unsafe_allow']} adv_unsafe={f['adversarial_unsafe_allow']}")
    print(f"{'ablate':16s} {'clean':>7s} {'clean_d':>8s} {'unsafe_d':>9s} {'safety_crit':>12s} {'util_crit':>10s}")
    for el, r in m["ablations"].items():
        print(f"{el:16s} {r['clean_allow_rate']:>7.3f} {r['clean_delta']:>8.3f} {r['unsafe_delta']:>9d} "
              f"{str(r['safety_critical']):>12s} {str(r['utility_critical']):>10s}")
    print("safety-critical:", m["safety_critical_elements"], "utility-critical:", m["utility_critical_elements"])
    print(f"\n{'comparator':30s} {'clean':>7s} {'held_uns':>9s} {'adv_uns':>8s} {'rules':>6s}")
    for name, c in m["complexity_comparators"].items():
        print(f"{name:30s} {c['clean_allow_rate']:>7.3f} {c['held_unsafe_allow']:>9d} {c['adversarial_unsafe_allow']:>8d} {c['approx_rules']:>6d}")
    print("minimum viable safe policy:", m["minimum_viable_safe_policy"])
