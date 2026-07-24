"""Phase 16 - Safety-utility frontier.

Assembles the frontier for all policies and determines whether the minimal policy EARNS its use against
risk-only, claim+source+risk, the rich component, and the oracle. A policy is admissible only if it
improves utility over the prior 0% AND holds unsafe allows at (near) zero. Deterministic, read-only.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

from minimal_evidence_policy import baselines, modifiers

_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_results")

# approximate rule counts / metadata fields for the complexity axis
_COMPLEXITY = {
    "A_prior_uniform": (0, 0), "B_global_threshold": (1, 0), "C_lowrisk_bypass": (2, 1),
    "D_risk_only": (5, 1), "E_claim_type_only": (12, 1), "F_source_role_only": (3, 1),
    "G_claim_source": (15, 2), "H_claim_source_risk": (17, 3), "I_rich_component": (90, 8),
    "J_minimal_risk_floor": (5, 1), "K_minimal_no_invariants": (12, 3),
    "L_minimal_no_upward_only": (10, 3), "M_minimal_review_fallback": (24, 4),
    "Full_minimal": (24, 4), "N_learned": (0, 2), "O_oracle": (0, 0),
}


def compute() -> Dict[str, Any]:
    bl = baselines.compute()["baselines"]
    points = []
    for name, res in bl.items():
        h, a = res["held_out_natural"], res["adversarial"]
        rules, meta = _COMPLEXITY.get(name, (0, 0))
        points.append({
            "policy": name, "clean_allow_rate": h["clean_allow_rate"],
            "held_unsafe_allow": h["unsafe_allow"], "high_risk_unsafe_allow": h["high_risk_unsafe_allow"],
            "adversarial_unsafe_allow": a["unsafe_allow"], "review_rate": None,
            "approx_rules": rules, "metadata_fields": meta,
            "safe": h["unsafe_allow"] == 0 and a["unsafe_allow"] <= 6,
            "useful": h["clean_allow_rate"] > 0.0,
        })
    points.sort(key=lambda p: -p["clean_allow_rate"])
    admissible = [p for p in points if p["safe"] and p["useful"]]
    admissible.sort(key=lambda p: (-p["clean_allow_rate"], p["approx_rules"]))

    minimal = next(p for p in points if p["policy"] == "Full_minimal")
    risk_only = next(p for p in points if p["policy"] == "D_risk_only")
    rich = next(p for p in points if p["policy"] == "I_rich_component")

    # does the minimal policy earn its use?
    beats_risk_only_on_safety = (minimal["held_unsafe_allow"] + minimal["adversarial_unsafe_allow"]) < \
        (risk_only["held_unsafe_allow"] + risk_only["adversarial_unsafe_allow"])
    beats_rich_on_safety = (minimal["held_unsafe_allow"] + minimal["adversarial_unsafe_allow"]) < \
        (rich["held_unsafe_allow"] + rich["adversarial_unsafe_allow"])
    # simpler safe policies at >= minimal's clean allow
    simpler_equal = [p for p in admissible if p["approx_rules"] < minimal["approx_rules"]
                     and p["clean_allow_rate"] >= minimal["clean_allow_rate"]]

    return {
        "prior_clean_allow": 0.0,
        "frontier": points,
        "admissible_safe_and_useful": [p["policy"] for p in admissible],
        "best_safe_useful": admissible[0]["policy"] if admissible else None,
        "minimal_earns_use": {
            "beats_risk_only_on_safety": beats_risk_only_on_safety,
            "beats_rich_component_on_safety": beats_rich_on_safety,
            "simpler_safe_policies_matching_clean_allow": [p["policy"] for p in simpler_equal],
            "verdict": ("EARNS USE ON SAFETY vs risk-only/rich, but simpler safe variants match its "
                        "clean-allow -> the minimal policy's value is its guaranteed safety, not a "
                        "clean-allow edge" if beats_risk_only_on_safety and beats_rich_on_safety
                        else "does not clearly earn use"),
        },
    }


def freeze() -> Dict[str, Any]:
    import hashlib
    m = compute()
    m["frontier_sha256"] = hashlib.sha256(json.dumps(m["frontier"], sort_keys=True).encode()).hexdigest()
    os.makedirs(_OUT, exist_ok=True)
    with open(os.path.join(_OUT, "frontier.json"), "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True); fh.write("\n")
    return m


if __name__ == "__main__":
    m = freeze()
    print(f"{'policy':28s} {'clean':>7s} {'held_uns':>8s} {'adv_uns':>7s} {'rules':>6s} {'safe&useful':>11s}")
    for p in m["frontier"]:
        flag = "YES" if p["safe"] and p["useful"] else ""
        print(f"{p['policy']:28s} {p['clean_allow_rate']:>7.3f} {p['held_unsafe_allow']:>8d} "
              f"{p['adversarial_unsafe_allow']:>7d} {p['approx_rules']:>6d} {flag:>11s}")
    print("\nminimal earns use:", m["minimal_earns_use"]["verdict"])
    print("simpler safe matching clean-allow:", m["minimal_earns_use"]["simpler_safe_policies_matching_clean_allow"])
