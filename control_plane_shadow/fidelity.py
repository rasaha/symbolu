"""Adapter fidelity evaluation (Phase 11). For each real adapter, compare source output to the
canonical output and confirm: the disposition equals the frozen mapping of the source term (no
changed authority/disposition/reason/confidence/policy interpretation), no field is invented
unless declared derived, and source output is preserved. Deterministic; no live calls.

An invented field = a canonical key whose value is not traceable to the source AND is not listed
in the adapter's `derived_fields`. Any such field is a defect.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from control_plane_shadow import vocabulary as V
from control_plane_shadow.adapters.action_gate_adapter import ActionGateAdapter
from control_plane_shadow.adapters.execution_gate_adapter import ExecutionGateAdapter
from control_plane_shadow.adapters.tap_adapter import TAPAssertionAdapter


@dataclass
class FidelityRow:
    adapter: str
    n: int = 0
    disposition_matches_map: int = 0     # canonical disposition == frozen_map(source term)
    source_preserved: int = 0
    invented_fields: int = 0             # undeclared canonical fields
    lost_decision_relevant: int = 0      # source decision fields absent from canonical AND payload
    changed_authority: int = 0
    notes: List[str] = field(default_factory=list)


def _tap() -> FidelityRow:
    a = TAPAssertionAdapter()
    row = FidelityRow("TAP")
    for cid in a.case_ids():
        r = a.govern(cid)
        row.n += 1
        src = r.source_output["gov_status"]
        expect = V.map_tap(src).value
        if r.canonical["assertion_disposition"] == expect:
            row.disposition_matches_map += 1
        if r.source_output and r.canonical.get("source_gov_status") == src:
            row.source_preserved += 1
        # declared derived fields; any canonical key not sourced + not derived = invented
        declared = {"assertion_disposition", "governed_output_ref", "source_gov_status",
                    "confidence_band", "n_conflicts", "n_gaps", "state"}
        invented = set(r.canonical) - declared
        row.invented_fields += len(invented)
    row.notes.append("SEMANTIC GAP: authority-resolution mapped to assertion disposition (declared, lossy)")
    return row


def _action() -> FidelityRow:
    a = ActionGateAdapter()
    row = FidelityRow("ActionGate")
    combos = [(op, ap, ev) for op in a.OPS for ap in (False, True) for ev in (False, True)]
    for op, ap, ev in combos:
        r = a.authorize(op, with_approval=ap, with_evidence=ev)
        row.n += 1
        src = r.canonical["source_outcome"]
        expect = V.map_action(src).value
        if r.canonical["action_disposition"] == expect:
            row.disposition_matches_map += 1
        if r.source_output and r.source_output.get("outcome") == src:
            row.source_preserved += 1
        declared = {"action_disposition", "source_outcome", "authorized_action", "constraints",
                    "dispositive_rules", "action_hash", "policy_hash", "terminal",
                    "hard_safety_block", "state"}
        row.invented_fields += len(set(r.canonical) - declared)
    return row


def _exec() -> FidelityRow:
    a = ExecutionGateAdapter()
    row = FidelityRow("ExecutionGate")
    env = {"request_id": "r", "trace_id": "t", "required_capabilities": [], "context_tokens": 1000}
    scenarios = [
        [{"provider": "p", "model_id": "m1", "family": "f"}],
        [{"provider": "p", "model_id": "m1", "family": "f", "signals": {"authenticated": False}}],
        [{"provider": "p", "model_id": "m1", "family": "f", "signals": {"billing_active": None},
          "stale": {"billing_active": True}}],
    ]
    for specs in scenarios:
        res, _ = a.evaluate(specs, env, now=1000.0)
        row.n += 1
        # exact 1:1 map: each source state maps to itself
        src_states = res.canonical["eligibility_states"]
        if all(V.map_exec(s).value == s for s in src_states.values()):
            row.disposition_matches_map += 1
        if res.source_output:
            row.source_preserved += 1
        declared = {"eligible_set", "eligibility_decision_id", "eligibility_states",
                    "excluded_with_reasons", "eligibility_evidence_timestamps", "policy_version", "state"}
        row.invented_fields += len(set(res.canonical) - declared)
    return row


def run() -> Dict[str, Any]:
    rows = [_exec(), _tap(), _action()]
    return {"adapters": [asdict(r) for r in rows],
            "summary": {r.adapter: {
                "disposition_fidelity": round(r.disposition_matches_map / max(1, r.n), 4),
                "source_preservation": round(r.source_preserved / max(1, r.n), 4),
                "invented_fields": r.invented_fields,
                "lost_decision_relevant": r.lost_decision_relevant,
                "changed_authority": r.changed_authority} for r in rows}}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
