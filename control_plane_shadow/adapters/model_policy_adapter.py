"""Real ModelPolicy adapter (Phase 5). Wraps model_selection_experiment.policy.route (TIER 3)
on the real policy_v1 / registry_v1 configs. Preserves the full decision record, emits canonical
selection, normalizes to MODEL.*. Deterministic; no network; no mutation.

Selection is constrained to the ExecutionGate-eligible set (invariant 1): route() runs on the
full registry, then the adapter intersects its `selected`/`eligible` with the upstream eligible
set. If route() would select outside the eligible set, the adapter emits
MODEL.SELECTED_MODEL_NOT_ELIGIBLE rather than overriding either component.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from model_selection_experiment import policy as msp

from control_plane_shadow.adapters.base import AdapterHealth, ShadowAdapter

_DATA = os.path.join(os.path.dirname(msp.__file__), "data")


def _load(name: str) -> Dict[str, Any]:
    with open(os.path.join(_DATA, name), encoding="utf-8") as fh:
        return json.load(fh)


class ModelPolicyAdapter(ShadowAdapter):
    component = "ModelPolicy"
    source_version = "policy_v1/registry_v1"

    def __init__(self):
        self.registry = _load("registry_v1.json")
        self.policy = _load("policy_v1.json")
        self._providers = sorted({(m["declared"].get("provider", {}) or {}).get("value")
                                  if isinstance(m["declared"].get("provider"), dict)
                                  else m["declared"].get("provider")
                                  for m in self.registry["models"].values()})

    def health(self) -> AdapterHealth:
        return AdapterHealth(self.component, available=True, determinism="deterministic",
                             live_call_risk=False, real_action_risk=False,
                             source_version=self.source_version, adapter_version=self.adapter_version,
                             capabilities=["selection", "hard_quality_gate", "fallback_chain", "utility"])

    def _eligible_registry(self, eligible_model_ids: List[str]) -> Dict[str, Any]:
        """Sub-registry with ONLY the ExecutionGate-eligible models (invariant 1, structural).
        ModelPolicy then normalizes utility over the eligible set, never widening it."""
        allowed = set(eligible_model_ids)
        sub = dict(self.registry)
        sub["models"] = {mid: m for mid, m in self.registry["models"].items() if mid in allowed}
        return sub

    def select(self, task: Dict[str, Any], eligible_model_ids: List[str],
               eligibility_decision_id: str, regime: str = "mature"):
        ent = {"approved_providers": list(self._providers)}
        reg = self._eligible_registry(eligible_model_ids)      # constrain to eligible set
        rec = msp.route(task, reg, ent, telemetry={}, policy=self.policy, regime=regime)  # REAL
        loss: List[str] = ["scored[].evidence quality detail summarized to predicted_quality"]
        # invariant 1 defensive guard: route() saw only eligible models, so selection is within set
        selected = rec["selected"]
        within = (selected in eligible_model_ids) if selected else True
        if rec["abstained"] or selected is None:
            canonical = {"selected_candidate": None, "eligibility_decision_id": eligibility_decision_id,
                         "abstained": True, "abstain_reason": rec["abstain_reason"]}
            res = self._result(tier="TIER3", canonical=canonical, source_output=rec,
                               reason_codes=["MODEL.NO_SELECTION"], information_loss=loss)
            res.canonical["state"] = "NO_SELECTION"
            return res
        if not within:
            canonical = {"selected_candidate": selected, "eligibility_decision_id": eligibility_decision_id,
                         "not_eligible": True}
            res = self._result(tier="TIER3", canonical=canonical, source_output=rec,
                               reason_codes=["MODEL.SELECTED_MODEL_NOT_ELIGIBLE"], information_loss=loss)
            res.canonical["state"] = "SELECTED_NOT_ELIGIBLE"
            return res
        canonical = {
            "selected_candidate": selected, "eligibility_decision_id": eligibility_decision_id,
            "selection_rationale": "highest-utility eligible model (real route())",
            "ranked_alternatives": rec["fallback_chain"],
            "utility_breakdown": {s["model"]: s["utility"] for s in rec["scored"]},
            "policy_version": rec["policy_version"], "registry_version": rec["registry_version"],
            "state": "SELECTED",
        }
        return self._result(tier="TIER3", canonical=canonical, source_output=rec,
                            reason_codes=[], information_loss=loss,
                            derived_fields=["selection_rationale"])
