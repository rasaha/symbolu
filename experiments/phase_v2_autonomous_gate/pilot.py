"""
pilot.py — go/no-go pilots BEFORE the full autonomous-gate study (per the reviewer plan).

§1 Token-only long-distance pilot: arms A_supervised / B_annealed / F_scratch, seeds {0,1},
   distances {1024,2048,4096} (d64–d512 are non-discriminative — sanity only). Reports state
   & readout Top-1, shuffled/random controls, focus-header/event/filler write scores, state
   norm, write rate, and (arm B) post-supervision performance.

§2 Upper-bound gate: require teacher−scratch ≥0.20 @2048 (pref ≥0.15 @4096), and that removing
   / shuffling the focus header materially reduces teacher decode and shuffled gates do not
   reproduce it.

§4–5 Focus-conditioned gate pilot: token-only vs focus-conditioned gate (both SUPERVISED, the
   fair learnability test), reporting header-vs-filler and relevant-vs-distractor write margins,
   long-distance decode, and remove/shuffle-focus controls.

§6 Emits the launch decision (launch / redesign / stop) and the §7 report fields.
"""
from __future__ import annotations

import json
import statistics as st
import time
from pathlib import Path

import torch

from experiments.phase_v3_selective_ssm.dataset import build_vocab
from experiments.phase_v3_selective_ssm.config import DataCfg
from .config import TrainCfg
from .train import build_model, train_arm
from .distance_eval import probe_at
from .ablations import run_controls
from .dynamics_analysis import analyze

HERE = Path(__file__).resolve().parent
DISTS = (1024, 2048, 4096)
PILOT_SEEDS = (0, 1)


def _pilot_cfg(seed):
    # reduced but meaningful budget
    return TrainCfg(seed=seed, stages=[(64, 120), (128, 150), (256, 200)], post_anneal_steps=150)


def _eval(m, vocab, dcfg, seed):
    out = {}
    for d in DISTS:
        r = probe_at(m, vocab, dcfg, d, seed=seed)
        wc = r["write_by_category"]
        out[str(d)] = {
            "state_top1": r["state"]["top1"], "readout_top1": r["readout"]["top1"],
            "shuffled_top1": r["shuffled_state"]["top1"], "random_top1": r["random_state"]["top1"],
            "header_write": wc["cue"], "event_write": 0.5 * (wc["relevant"] + wc["distractor"]),
            "filler_write": wc["filler"],
            "header_minus_filler": wc["cue"] - wc["filler"],
            "event_minus_filler": 0.5 * (wc["relevant"] + wc["distractor"]) - wc["filler"],
            "relevant_minus_distractor": wc["relevant"] - wc["distractor"],
        }
    return out


def token_pilot():
    vocab = build_vocab(); dcfg = DataCfg(); t0 = time.time()
    arms = ("A_supervised_teacher", "B_annealed", "F_e2e_scratch")
    cells = {a: [] for a in arms}
    teacher0 = None
    for seed in PILOT_SEEDS:
        teacher = build_model(vocab, "sigmoid", seed)
        train_arm(teacher, "A_supervised_teacher", vocab, _pilot_cfg(seed), dcfg=dcfg)
        if seed == 0:
            teacher0 = teacher
        for arm in arms:
            m = teacher if arm == "A_supervised_teacher" else build_model(vocab, "sigmoid", seed)
            if arm != "A_supervised_teacher":
                train_arm(m, arm, vocab, _pilot_cfg(seed), dcfg=dcfg, teacher=teacher)
            ev = _eval(m, vocab, dcfg, seed)
            dyn = analyze(m, vocab, dcfg, 2048, seed)
            cells[arm].append({"eval": ev, "state_norm": dyn["state_norm_mean"], "write_rate": dyn["write_rate_mean"]})
            print(f"[tok {arm} s{seed}] d2048 state={ev['2048']['state_top1']:.3f} d4096={ev['4096']['state_top1']:.3f} "
                  f"hdr-fill={ev['2048']['header_minus_filler']:+.2f} ({time.time()-t0:.0f}s)", flush=True)
    controls = run_controls(teacher0, vocab, dcfg, distance=2048, seed=0)
    return cells, controls


def conditioned_pilot():
    vocab = build_vocab(); dcfg = DataCfg(); t0 = time.time()
    out = {}
    for mode in ("token", "conditioned"):
        per = []
        for seed in PILOT_SEEDS:
            m = build_model(vocab, "sigmoid", seed, gate_mode=mode)
            train_arm(m, "A_supervised_teacher", vocab, _pilot_cfg(seed), dcfg=dcfg)  # supervised = fair learnability test
            ev = _eval(m, vocab, dcfg, seed)
            ctrl = run_controls(m, vocab, dcfg, distance=2048, seed=seed) if seed == 0 else None
            per.append({"eval": ev, "controls": ctrl})
            print(f"[cond {mode} s{seed}] d2048 state={ev['2048']['state_top1']:.3f} "
                  f"rel-distr={ev['2048']['relevant_minus_distractor']:+.3f} "
                  f"hdr-fill={ev['2048']['header_minus_filler']:+.2f} ({time.time()-t0:.0f}s)", flush=True)
        out[mode] = per
    return out


def _mean(cells, arm, d, key):
    return st.mean([c["eval"][str(d)][key] for c in cells[arm]])


def decide(tok_cells, tok_controls, cond):
    teach2048 = _mean(tok_cells, "A_supervised_teacher", 2048, "state_top1")
    scr2048 = _mean(tok_cells, "F_e2e_scratch", 2048, "state_top1")
    teach4096 = _mean(tok_cells, "A_supervised_teacher", 4096, "state_top1")
    scr4096 = _mean(tok_cells, "F_e2e_scratch", 4096, "state_top1")
    gap2048 = teach2048 - scr2048
    gap4096 = teach4096 - scr4096
    base = tok_controls.get("baseline", 0.0)
    header_causal = (base - tok_controls.get("remove_focus_header", base)) > 0.1
    focusid_causal = (base - tok_controls.get("shuffle_focus_identity", base)) > 0.1
    shuffle_gate_ok = tok_controls.get("gate_shuffle_examples", 1.0) < base - 0.1
    # conditioned gate relevant-vs-distractor margin
    cond_rel_distr = st.mean([c["eval"]["2048"]["relevant_minus_distractor"] for c in cond["conditioned"]])
    tok_rel_distr = st.mean([c["eval"]["2048"]["relevant_minus_distractor"] for c in cond["token"]])
    upper_bound_valid = gap2048 >= 0.20
    condA = upper_bound_valid and header_causal and focusid_causal
    condB = cond_rel_distr > 0.05 and _mean(tok_cells, "A_supervised_teacher", 2048, "state_top1") > 0.5
    decision = ("launch" if (condA or condB) else "redesign/stop")
    return {
        "teacher_state_top1_2048": teach2048, "scratch_state_top1_2048": scr2048,
        "teacher_minus_scratch_2048": gap2048, "teacher_minus_scratch_4096": gap4096,
        "upper_bound_valid (gap2048>=0.20)": upper_bound_valid,
        "gap4096_ge_0.15": gap4096 >= 0.15,
        "header_causal": header_causal, "focus_identity_causal": focusid_causal,
        "shuffled_gate_does_not_reproduce": shuffle_gate_ok,
        "token_relevant_minus_distractor_2048": tok_rel_distr,
        "conditioned_relevant_minus_distractor_2048": cond_rel_distr,
        "conditionA_cue_preservation": condA, "conditionB_focus_conditioned": condB,
        "launch_decision": decision,
    }


def run():
    t0 = time.time()
    tok_cells, tok_controls = token_pilot()
    cond = conditioned_pilot()
    dec = decide(tok_cells, tok_controls, cond)
    result = {"token_pilot": tok_cells, "token_controls": tok_controls,
              "conditioned_pilot": cond, "decision": dec}
    (HERE / "results" / "pilot.json").write_text(json.dumps(result, indent=2, default=float))
    print("PILOT DECISION:", json.dumps(dec, indent=1, default=float), flush=True)
    print(f"PILOT DONE {time.time()-t0:.0f}s", flush=True)
    return result


if __name__ == "__main__":
    run()
