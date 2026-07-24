"""Phase 11 - Baselines A-O on the natural corpus.

Fifteen baselines scored against the blinded ground truth, so the governed runtime's value on natural
artifacts is measured against naive heuristics AND against simpler configurations of itself (ablation).
A-J are non-governed heuristics; K-O run the FROZEN orchestrator read-only under each risk-tier config.

Deterministic, stdlib-only, non-enforcing. Writes eval_results/baselines.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Dict, List

from governed_inference_pilot import orchestrator as gip_orch

from bounded_shadow_pilot import case_builder, metrics

_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "natural_pilot_v1")
_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_results")

_SEC = re.compile(r"\b(exploit|vulnerab|attack|credential|secret|injection|rce|backdoor)\w*", re.I)
_CLAIM = re.compile(r"\b(always|never|guarantee|100\s*%|proven|completely\s+safe|zero\s+risk)\b", re.I)


def _load():
    corpus = json.load(open(os.path.join(_DATA, "corpus.json")))
    gt = json.load(open(os.path.join(_DATA, "ground_truth.json")))
    gts = {g["artifact_id"]: g for g in gt["labels"]}
    return corpus["artifacts"], gts


def _pseudo_bit(artifact_id: str) -> int:
    return int(hashlib.sha256(artifact_id.encode()).hexdigest(), 16) & 1


# ---- heuristic baselines (A-J): each returns a shadow-style final -------------------------------
def _heuristic_final(name: str, a: Dict[str, Any]) -> str:
    text = a["text"]
    sec = bool(_SEC.search(text))
    claim = bool(_CLAIM.search(text))
    long_ = a["char_len"] >= 500
    cyber = a["use_case"] == "cybersecurity_advisory_review"
    return {
        "A_always_allow":        "WOULD_ALLOW",
        "B_always_qualify":      "WOULD_QUALIFY",
        "C_always_reject":       "WOULD_REJECT",
        "D_always_escalate":     "WOULD_ESCALATE",
        "E_random_50":           "WOULD_ESCALATE" if _pseudo_bit(a["artifact_id"]) else "WOULD_ALLOW",
        "F_keyword_security":    "WOULD_ESCALATE" if sec else "WOULD_ALLOW",
        "G_keyword_claim":       "WOULD_ESCALATE" if claim else "WOULD_ALLOW",
        "H_keyword_sec_and_claim": "WOULD_ESCALATE" if (sec and claim) else "WOULD_ALLOW",
        "I_length_threshold":    "WOULD_ESCALATE" if long_ else "WOULD_ALLOW",
        "J_use_case_cyber":      "WOULD_ESCALATE" if cyber else "WOULD_ALLOW",
    }[name]


HEURISTICS = ["A_always_allow", "B_always_qualify", "C_always_reject", "D_always_escalate",
              "E_random_50", "F_keyword_security", "G_keyword_claim", "H_keyword_sec_and_claim",
              "I_length_threshold", "J_use_case_cyber"]

# governed configurations (K-O) -> frozen orchestrator config
GOVERNED = {
    "K_governed_mvc": "MINIMUM_VIABLE_CONTROL_PLANE",
    "L_governed_assertion": "ASSERTION_GOVERNANCE",
    "M_governed_action": "ACTION_GOVERNANCE",
    "N_governed_full_stack": "FULL_STACK_HIGH_RISK",
    "O_governed_full_stack_dup": "FULL_STACK_HIGH_RISK",   # determinism control (must equal N)
}


def _governed_final(config: str, a: Dict[str, Any], gt: Dict[str, Any]) -> str:
    case = case_builder.build_case(a, gt)
    trace = gip_orch.run_case(case, config=config)
    return trace.final_shadow_disposition


def compute() -> Dict[str, Any]:
    artifacts, gts = _load()
    artifacts = sorted(artifacts, key=lambda x: x["artifact_id"])
    results: Dict[str, Any] = {}

    # heuristics
    for name in HEURISTICS:
        preds = [{"artifact_id": a["artifact_id"], "final": _heuristic_final(name, a),
                  "gt_expected_class": gts[a["artifact_id"]]["gt_expected_class"]} for a in artifacts]
        results[name] = metrics.score(preds)

    # governed configs (frozen orchestrator, read-only)
    gov_finals: Dict[str, List[str]] = {}
    for name, config in GOVERNED.items():
        preds = []
        finals = []
        for a in artifacts:
            gt = gts[a["artifact_id"]]
            f = _governed_final(config, a, gt)
            finals.append(f)
            preds.append({"artifact_id": a["artifact_id"], "final": f,
                          "gt_expected_class": gt["gt_expected_class"]})
        gov_finals[name] = finals
        results[name] = metrics.score(preds)

    determinism_ok = gov_finals["N_governed_full_stack"] == gov_finals["O_governed_full_stack_dup"]

    payload = {
        "corpus_id": "natural_pilot_v1",
        "n": len(artifacts),
        "baselines": results,
        "governed_full_stack_deterministic": determinism_ok,
        "notes": "A-J heuristic (non-governed); K-O frozen orchestrator read-only; O duplicates N as a "
                 "determinism control.",
    }
    payload["baselines_sha256"] = hashlib.sha256(
        json.dumps(results, sort_keys=True).encode()).hexdigest()
    return payload


def freeze() -> Dict[str, Any]:
    m = compute()
    os.makedirs(_OUT, exist_ok=True)
    with open(os.path.join(_OUT, "baselines.json"), "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return m


if __name__ == "__main__":
    m = freeze()
    print(f"baselines on n={m['n']}  full_stack_deterministic={m['governed_full_stack_deterministic']}")
    print(f"{'baseline':28s} {'unsafe_permit':>13s} {'unsafe_deliver':>14s} "
          f"{'false_withhold':>14s} {'over_qualify':>12s}")
    for name in HEURISTICS + list(GOVERNED):
        s = m["baselines"][name]
        print(f"{name:28s} {s['safety']['unsafe_permit']:>13d} {s['safety']['unsafe_deliver_any']:>14d} "
              f"{s['utility']['false_withhold']:>14d} {s['utility']['over_qualify']:>12d}")
