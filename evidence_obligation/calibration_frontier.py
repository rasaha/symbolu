"""Phase 17 - Calibration without safety loss: the safety-utility frontier.

Assembles the safety-utility frontier from the downstream evaluation for each utility-improvement
strategy, so the frontier makes explicit which strategies buy clean-allow WITHOUT buying unsafe allows.
The full policy must earn its complexity: a strategy is only admissible if it improves utility over the
prior 0% AND holds unsafe allows at (near) zero.

Deterministic, read-only. Writes eval_results/calibration_frontier.json.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from evidence_obligation import downstream

_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_results")

# strategy -> downstream policy name
_STRATEGIES = {
    "global_threshold_lowering": "K_global_threshold_reduction",
    "lowrisk_bypass": "O_nogate_all_lowrisk",
    "claim_type_contextual": "E_claim_type_only",
    "risk_only_contextual": "C_risk_only",
    "simple_contextual": "P_simple_contextual",
    "full_evidence_obligation": "Q_reference",
    "learned_comparator": "S_learned",
    "oracle_obligation": "R_oracle",
    "prior_uniform": "prior_derivation_uniform",
}


def compute() -> Dict[str, Any]:
    ds = downstream.compute()["policies"]
    points: List[Dict[str, Any]] = []
    for strat, pname in _STRATEGIES.items():
        h = ds[pname]["held_out_natural"]
        a = ds[pname]["adversarial"]
        points.append({
            "strategy": strat,
            "clean_allow_rate": h["clean_allow_rate"],
            "over_qualification_rate": h["over_qualification_rate"],
            "held_unsafe_allow": h["unsafe_allow"],
            "high_risk_unsafe_allow": h["high_risk_unsafe_allow"],
            "adversarial_unsafe_allow": a["unsafe_allow"],
            # admissible = improves utility over prior 0% AND zero adversarial + <=1 high-risk unsafe
            "safe": a["unsafe_allow"] == 0 and h["high_risk_unsafe_allow"] <= 1,
            "useful": h["clean_allow_rate"] > 0.0,
        })
    points.sort(key=lambda p: (-p["clean_allow_rate"]))

    # frontier = safe AND useful strategies, ranked by clean allow
    admissible = [p for p in points if p["safe"] and p["useful"]]
    admissible.sort(key=lambda p: -p["clean_allow_rate"])
    best_safe = admissible[0] if admissible else None

    return {
        "prior_clean_allow": 0.0, "prior_over_qualification": 0.855,
        "frontier": points,
        "admissible_safe_and_useful": [p["strategy"] for p in admissible],
        "best_safe_useful_strategy": best_safe["strategy"] if best_safe else None,
        "best_safe_useful_clean_allow": best_safe["clean_allow_rate"] if best_safe else None,
        "interpretation": (
            "Strategies that reach high clean-allow by stripping the evidence burden "
            "(global_threshold_lowering, lowrisk_bypass) also buy large unsafe-allow counts and are "
            "inadmissible. The oracle and the learned comparator sit on the safe-and-useful frontier; "
            "the full reference component reaches higher clean-allow but crosses into unsafe territory, "
            "so it does not yet dominate the simpler safe strategies."
        ),
    }


def freeze() -> Dict[str, Any]:
    import hashlib
    m = compute()
    m["frontier_sha256"] = hashlib.sha256(json.dumps(m["frontier"], sort_keys=True).encode()).hexdigest()
    os.makedirs(_OUT, exist_ok=True)
    with open(os.path.join(_OUT, "calibration_frontier.json"), "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return m


if __name__ == "__main__":
    m = freeze()
    print(f"{'strategy':28s} {'clean':>7s} {'hi_unsafe':>10s} {'adv_unsafe':>11s} {'safe&useful':>12s}")
    for p in m["frontier"]:
        flag = "YES" if (p["safe"] and p["useful"]) else ""
        print(f"{p['strategy']:28s} {p['clean_allow_rate']:>7.3f} {p['high_risk_unsafe_allow']:>10d} "
              f"{p['adversarial_unsafe_allow']:>11d} {flag:>12s}")
    print(f"\nbest safe+useful: {m['best_safe_useful_strategy']} @ clean={m['best_safe_useful_clean_allow']}")
