#!/usr/bin/env python3
"""Deterministic behavioural-equivalence capture for the Model Selection core.

Imports through the legacy ``execution_gate`` surface (which exists as REAL modules in
the pre-migration tree and as the logic-free compatibility surface over
``ugence_model_selection`` in the post-migration tree), so the SAME script runs in both
trees and any behavioural drift shows up as a byte difference.

Captured, over the frozen scenario battery (``execution_gate.scenarios.SCENARIOS`` at the
fixed instant ``T0``):

  * per-candidate eligibility decisions (state, reasons, full ``to_dict`` conditions),
  * selection results over each scenario's registry (selected, ranked utilities,
    abstained, reason, score components) with a fixed deterministic quality prior,
  * the full ``execution_gate.harness.run()`` pipeline result,
  * exception behaviour for malformed inputs,
  * deterministic fingerprints of every eligibility decision.

Usage:  python scripts/model_selection_equivalence_capture.py <out.json>
Output is canonical JSON (sorted keys) so ``diff`` / sha256 compare cleanly.
"""
from __future__ import annotations

import hashlib
import json
import sys

from execution_gate import harness, scenarios
from execution_gate.gate import ExecutionGate
from execution_gate.policy import PolicyWeights, select
from execution_gate.registry import ExecutableRegistry, ModelRecord
from execution_gate.model import Request
from execution_gate.states import EligibilityState

T0 = scenarios.T0
GATE = ExecutionGate()
WEIGHTS = PolicyWeights()  # defaults, frozen


def _fingerprint(payload) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _fixed_quality(scn):
    """Deterministic provider-neutral quality prior: the scenario's own capability prior
    when present, else a stable constant. Never reads ground truth."""
    def q(rec):
        return round(scn.quality.get(rec.candidate.model_id, 0.5), 6)
    return q


def _selection_capture(scn):
    reg = ExecutableRegistry(GATE)
    for c in scn.candidates:
        reg.upsert(ModelRecord(c.model_id, c, observed_latency_ms=(
            c.signals["observed_latency_ms"].value if "observed_latency_ms" in c.signals else None)))
    selectable, excluded = reg.evaluate(scn.request, T0)
    sel = select(selectable, scn.request, quality_of=_fixed_quality(scn), weights=WEIGHTS)
    return {
        "selected": sel.selected.internal_id if sel.selected else None,
        "abstained": sel.abstained,
        "reason": sel.reason,
        "ranked": [[rec.internal_id, util] for rec, util in sel.ranked],
        "eligible_ids": sorted(rec.internal_id for rec, _ in selectable),
        "excluded_ids": sorted(rec.internal_id for rec, _ in excluded),
    }


def _eligibility_capture(scn):
    out = []
    for c in scn.candidates:
        dec = GATE.evaluate(c, scn.request, T0)
        d = dec.to_dict()
        out.append({
            "model_id": c.model_id,
            "state": d["state"],
            "reasons": d["reasons"],
            "decision": d,
            "fingerprint": _fingerprint(d),
        })
    return out


def _exception_capture():
    """Exercise fail-closed / abstain edges deterministically."""
    cases = {}
    # empty eligible pool -> abstain
    reg = ExecutableRegistry(GATE)
    req = Request("empty", context_tokens=1000, approved_providers={"nobody"})
    sel = select(reg.evaluate(req, T0)[0], req, quality_of=lambda r: 0.9)
    cases["empty_pool_abstains"] = {"selected": sel.selected, "abstained": sel.abstained,
                                    "reason": sel.reason}
    return cases


def main() -> int:
    out_path = sys.argv[1]
    capture = {
        "scenario_count": len(scenarios.SCENARIOS),
        "T0": T0,
        "policy_weights": {"quality": WEIGHTS.quality, "cost": WEIGHTS.cost,
                           "latency": WEIGHTS.latency, "conditional_penalty": WEIGHTS.conditional_penalty},
        "eligibility_states": sorted(s.value for s in EligibilityState),
        "scenarios": {},
        "harness_run": harness.run(),
        "exceptions": _exception_capture(),
    }
    for scn in scenarios.SCENARIOS:
        capture["scenarios"][scn.id] = {
            "eligibility": _eligibility_capture(scn),
            "selection": _selection_capture(scn),
        }
    blob = json.dumps(capture, sort_keys=True, indent=2, default=str)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(blob)
    print(f"wrote {out_path}: {len(scenarios.SCENARIOS)} scenarios; "
          f"capture sha256 {hashlib.sha256(blob.encode()).hexdigest()[:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
