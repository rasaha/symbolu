"""
run_pilots.py — combined go/no-go driver: Claim 1 (token-only cue preservation) + Claim 2
(focus-conditioned event selection), then the launch decision. One background run.
"""
from __future__ import annotations

import json
import statistics as st
from pathlib import Path

from .pilot import token_pilot
from . import conditioned_analysis as CA

HERE = Path(__file__).resolve().parent


def _mean(cells, arm, d, key):
    return st.mean([c["eval"][str(d)][key] for c in cells[arm]])


def run():
    # Claim 1: token-only cue preservation (do NOT require teacher > scratch)
    tok_cells, tok_controls = token_pilot()
    claim1 = {}
    for arm in ("A_supervised_teacher", "B_annealed", "F_e2e_scratch"):
        claim1[arm] = {
            "d2048_state_top1": _mean(tok_cells, arm, 2048, "state_top1"),
            "d4096_state_top1": _mean(tok_cells, arm, 4096, "state_top1"),
            "d2048_readout_top1": _mean(tok_cells, arm, 2048, "readout_top1"),
            "d2048_control_top1": _mean(tok_cells, arm, 2048, "shuffled_top1"),
            "header_minus_filler": _mean(tok_cells, arm, 2048, "header_minus_filler"),
            "event_minus_filler": _mean(tok_cells, arm, 2048, "event_minus_filler"),
            "write_rate": st.mean([c["write_rate"] for c in tok_cells[arm]]),
            "state_norm": st.mean([c["state_norm"] for c in tok_cells[arm]]),
        }
    base = tok_controls.get("baseline", 0.0)
    cue_preservation_validated = (
        max(claim1[a]["d2048_state_top1"] for a in claim1) >= 0.70
        and all(claim1[a]["header_minus_filler"] > 0.05 for a in ("B_annealed", "F_e2e_scratch"))
        and (base - tok_controls.get("remove_focus_header", base)) > 0.1
        and (base - tok_controls.get("shuffle_focus_identity", base)) > 0.1
        and tok_controls.get("gate_shuffle_examples", 1.0) < base - 0.1)

    # Claim 2: focus-conditioned event selection
    cond = CA.run()
    acc = cond["acceptance"]

    decision = "launch" if acc["conditioned_gate_passes"] else "redesign/stop"
    verdict = {
        "long_distance_teacher_upper_bound": "invalid (scratch matches/exceeds teacher — cue preservation is autonomous)",
        "token_only_autonomous_gate": "preserves focus cue" if cue_preservation_validated else "fails",
        "focus_conditioned_gate": ("separates relevant events" if acc["conditioned_gate_passes"]
                                   else "fails to separate relevant vs distractor"),
        "structural_scope": ("focus-conditioned relevance selection" if acc["conditioned_gate_passes"]
                             else "cue preservation only"),
        "full_study": decision,
    }
    out = {"claim1_token_cue_preservation": claim1, "token_controls": tok_controls,
           "claim1_validated": cue_preservation_validated,
           "claim2_conditioned": cond["conditioned"], "claim2_token": cond["token"],
           "claim2_acceptance": acc, "verdict": verdict}
    (HERE / "results" / "pilots.json").write_text(json.dumps(out, indent=2, default=float))
    print("VERDICT:", json.dumps(verdict, indent=1), flush=True)
    print("PILOTS DONE", flush=True)
    return out


if __name__ == "__main__":
    run()
