"""Evaluation engine (Phases 12-15). Robustness curves across noise severity, correlated-failure
study, ablation, and complexity-comparator comparison. Deterministic; no live calls.

Noise application: at severity s, each eval item receives a deterministic rotating perturbation
from the chosen set; methods see the perturbed bundle, gold is the reality-based label. Separate
curves for detectable-only, silent-only, and all noise expose where uncertainty propagation helps.
"""
from __future__ import annotations

import copy
import json
from dataclasses import replace
from typing import Callable, Dict, List

from assertion_gate_robustness import metrics as M
from assertion_gate_robustness.baselines import build_all, oracle
from assertion_gate_robustness.dataset import BaseItem, clean_bundle, observed, split
from assertion_gate_robustness.gate import govern_disposition, govern
from assertion_gate_robustness.perturbations import DETECTABLE, SILENT, apply
from assertion_gate_robustness.signals import SignalBundle

SEVERITIES = [0.0, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50]


def _method_map():
    methods, params = build_all()
    methods["N_assertion_gate"] = lambda b, claim: govern_disposition(b, claim)
    params["N_assertion_gate"] = 9  # bounded rule count (reported)
    return methods, params


def _perturbed(items: List[BaseItem], severity: float, pset: List[str]):
    """Return list of (bundle, item) with a rotating perturbation from pset at `severity`."""
    out = []
    for i, it in enumerate(items):
        pert = "clean" if severity == 0.0 else pset[i % len(pset)]
        out.append((apply(pert, clean_bundle(it), severity), it))
    return out


def _score(method: Callable, pairs) -> Dict[str, float]:
    preds = [method(b, it.claim_strength) for b, it in pairs]
    golds = [it.gold for _, it in pairs]
    return M.full(preds, golds)


def robustness_curves(pset_name: str = "all") -> Dict:
    items = split("eval")
    methods, params = _method_map()
    pset = {"all": DETECTABLE + SILENT, "detectable": DETECTABLE, "silent": SILENT}[pset_name]
    curves = {}
    for name, fn in methods.items():
        curve = {}
        for s in SEVERITIES:
            curve[str(s)] = _score(fn, _perturbed(items, s, pset))
        curves[name] = curve
    # oracle upper bound (uses truth; noise-invariant)
    golds = [it.gold for it in items]
    curves["O_oracle"] = {str(s): M.full([oracle(it) for it in items], golds) for s in SEVERITIES}
    return {"perturbation_set": pset_name, "severities": SEVERITIES, "curves": curves, "params": params}


def _auc_escape(curve: Dict) -> float:
    """Area under the escape curve across severities (lower is safer)."""
    ys = [curve[str(s)]["escape"] for s in SEVERITIES]
    area = sum((SEVERITIES[i + 1] - SEVERITIES[i]) * (ys[i] + ys[i + 1]) / 2 for i in range(len(SEVERITIES) - 1))
    return round(area, 4)


def failure_threshold(curve: Dict, key: str = "escape", limit: float = 0.10) -> float:
    """First severity at which `key` exceeds `limit` (or 0.5+ if never)."""
    for s in SEVERITIES:
        if curve[str(s)][key] > limit:
            return s
    return 0.55


def correlated_failure_study() -> Dict:
    """Escape on SILENT/correlated perturbations vs DETECTABLE, at severity 0.3."""
    items = split("eval")
    methods, _ = _method_map()
    out = {}
    for name, fn in methods.items():
        det = _score(fn, _perturbed(items, 0.3, DETECTABLE))
        sil = _score(fn, _perturbed(items, 0.3, SILENT))
        corr = _score(fn, [(apply("correlated", clean_bundle(it), 0.3), it) for it in items])
        out[name] = {"detectable_escape": det["escape"], "silent_escape": sil["escape"],
                     "correlated_escape": corr["escape"],
                     "detectable_false_block": det["false_blocking"]}
    return out


# --- ablation (Phase 14): neutralize one signal before the gate ------------

def _ablate_bundle(b: SignalBundle, drop: str) -> SignalBundle:
    b = copy.deepcopy(b)
    if drop == "uncertainty":
        b.grounding.confidence = 1.0; b.entailment.confidence = 1.0
        b.grounding_calibration = b.entailment_calibration = b.risk_calibration = 1.0
        b.evidence.provenance_present = True
    elif drop == "adequacy":
        b.evidence.adequacy = 1.0
    elif drop == "conflict":
        b.evidence.conflict = "none"
    elif drop == "freshness":
        b.evidence.age_days = 0.0
    elif drop == "authority":
        b.evidence.authority = "authorized"
    elif drop == "risk":
        b.risk_class = "low"
    return b


def ablation_study() -> Dict:
    items = split("eval")
    drops = ["none", "uncertainty", "adequacy", "conflict", "freshness", "authority", "risk"]
    out = {}
    for drop in drops:
        pairs = []
        for i, it in enumerate(items):
            pert = (DETECTABLE + SILENT)[i % len(DETECTABLE + SILENT)]
            b = apply(pert, clean_bundle(it), 0.3)
            if drop != "none":
                b = _ablate_bundle(b, drop)
            pairs.append((b, it))
        preds = [govern_disposition(b, it.claim_strength) for b, it in pairs]
        golds = [it.gold for _, it in pairs]
        out[drop] = {"escape": M.escape_rate(preds, golds), "false_blocking": M.false_blocking(preds, golds),
                     "accuracy": M.accuracy(preds, golds)}
    return out


def run_all() -> Dict:
    all_c = robustness_curves("all")
    det_c = robustness_curves("detectable")
    sil_c = robustness_curves("silent")
    summary = {}
    for name in all_c["curves"]:
        summary[name] = {
            "clean_accuracy": all_c["curves"][name]["0.0"]["accuracy"],
            "escape_auc_all": _auc_escape(all_c["curves"][name]),
            "escape_auc_detectable": _auc_escape(det_c["curves"][name]),
            "escape_auc_silent": _auc_escape(sil_c["curves"][name]),
            "escape_fail_threshold_all": failure_threshold(all_c["curves"][name], "escape", 0.10),
            "false_block_at_0.3_all": all_c["curves"][name]["0.3"]["false_blocking"],
            "params": all_c["params"].get(name, 0),
        }
    return {"summary": summary, "curves_all": all_c["curves"], "curves_detectable": det_c["curves"],
            "curves_silent": sil_c["curves"], "correlated_failure": correlated_failure_study(),
            "ablation": ablation_study(), "severities": SEVERITIES}


if __name__ == "__main__":
    print(json.dumps(run_all()["summary"], indent=2))
