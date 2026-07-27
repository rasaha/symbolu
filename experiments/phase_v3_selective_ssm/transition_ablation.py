"""
transition_ablation.py — 2×2 transition ablation isolating dynamic decay γ_t vs
token-dependent rotation ω_t, with the write gate, curriculum, parameter budget, data,
seeds, state size, and readout held identical across cells.

    T-B      : γ=1,  ω=0        (selective write only; true persistence)
    T-Bgamma : γ_t, ω=0        (+ dynamic decay)          == recommended V3-AB0
    T-Bomega : γ=1,  ω_t        (+ token-dependent rotation)
    T-AB     : γ_t, ω_t        (both)

Three seeds, distance ladder through 4096. Reports state Top-1, selective-readout Top-1,
shuffled/random controls, and transition dynamics: state norm, effective γ, accumulated
rotation (Σω from cue→probe) and phase-alignment drift (cos of that rotation). Compared
against the completed V2-S runs (same curriculum + matched write-gate supervision).

Interpretation (as specified):
    B+γ > B      → dynamic retention helps
    B+ω < B      → rotation is harmful
    AB < B+γ     → rotation cancels the benefit of retention
    B+γ ≤ B      → input-dependent retention adds no value
    all < V2-S   → keep V2-S; stop increasing recurrence complexity
"""
from __future__ import annotations

import json
import math
import statistics as st
import time
from pathlib import Path

import torch

from .config import SEEDS, TrainCfg, DataCfg
from .dataset import build_vocab, generate, collate
from .train import FocusModel, train_focus
from .distance_eval import eval_distances

HERE = Path(__file__).resolve().parent
RAW = HERE / "results" / "raw"
CELLS = ("T-B", "T-Bgamma", "T-Bomega", "T-AB")
LABELS = {"T-B": "B (γ=1, ω=0)", "T-Bgamma": "B+γ (γ_t, ω=0)",
          "T-Bomega": "B+ω (γ=1, ω_t)", "T-AB": "AB (γ_t, ω_t)"}
DISTS = (64, 128, 256, 512, 1024, 2048, 4096)


@torch.no_grad()
def transition_dynamics(model, vocab, dcfg, distance=2048, seed=0, n=120):
    data = generate(vocab, dcfg, distance, n, 7700 + seed)
    ids, wt, pp, fo = collate(data, vocab.PAD)
    core = model.variant.core
    x = model.embed(ids)
    xn = core.norm(x)
    A, gamma, Bt, Ct = core._controls(xn)          # A:[B,N,H] complex
    omega = A.angle()                               # [B,N,H] per-token rotation
    # accumulated rotation applied to the cue (written at t=0), measured at the probe (t=N-1)
    acc_rot = omega[:, 1:].sum(dim=1)               # [B,H]
    mean_abs_acc_rot = acc_rot.abs().mean().item()
    turns = mean_abs_acc_rot / (2 * math.pi)
    # phase-alignment drift: cos of the accumulated rotation (1=aligned, →0 drifted)
    alignment = torch.cos(acc_rot).mean().item()
    # effective retention of the cue to the probe: Π γ over 1..probe
    log_gamma = torch.log(gamma[:, 1:].clamp(1e-6, 1.0)).sum(dim=1)   # [B,H]
    cue_retention = torch.exp(log_gamma).mean().item()
    d = core(x, return_diagnostics=True).diagnostics
    return {
        "distance": distance,
        "effective_gamma_per_head": gamma.mean(dim=(0, 1)).tolist(),
        "effective_gamma_mean": gamma.mean().item(),
        "mean_abs_accumulated_rotation_rad": mean_abs_acc_rot,
        "accumulated_rotation_turns": turns,
        "phase_alignment_cos": alignment,
        "cue_retention_to_probe": cue_retention,
        "state_norm_mean": d["state_norm_per_head"].mean().item(),
        "state_norm_per_head": d["state_norm_per_head"].tolist(),
        "write_rate_mean": d["write_rate_mean"].item(),
    }


def _load_v2s():
    """V2-S state_top1 per distance from the completed study (matched curriculum/supervision)."""
    out = {}
    for d in map(str, DISTS):
        xs = []
        for s in SEEDS:
            p = RAW / f"V2-S_B_annealed_s{s}.json"
            if p.exists():
                rec = json.loads(p.read_text())
                if d in rec["distances"]:
                    xs.append(rec["distances"][d]["state_top1"])
        if xs:
            out[d] = {"mean": st.mean(xs), "std": st.pstdev(xs) if len(xs) > 1 else 0.0}
    return out


def run(seeds=SEEDS):
    vocab = build_vocab(); dcfg = DataCfg(); t0 = time.time()
    cells = {}
    for name in CELLS:
        per_dist, per_dyn = [], []
        for seed in seeds:
            torch.manual_seed(seed)
            m = FocusModel(name, vocab.size)
            train_focus(m, vocab, TrainCfg(seed=seed), mode="B_annealed", dcfg=dcfg)
            dev = eval_distances(m, vocab, dcfg, DISTS, seed=seed)
            dyn = transition_dynamics(m, vocab, dcfg, 2048, seed)
            per_dist.append(dev); per_dyn.append(dyn)
            print(f"[{name} s{seed}] d1024 state={dev['1024']['state_top1']:.3f} "
                  f"d2048 state={dev['2048']['state_top1']:.3f} "
                  f"acc_rot={dyn['accumulated_rotation_turns']:.1f}turns "
                  f"align={dyn['phase_alignment_cos']:.2f} ({time.time()-t0:.0f}s)", flush=True)
        cells[name] = {"per_dist": per_dist, "per_dyn": per_dyn}

    agg = aggregate(cells, seeds)
    agg["v2s_reference"] = _load_v2s()
    agg["interpretation"] = interpret(agg)
    (HERE / "results" / "transition_ablation.json").write_text(json.dumps(agg, indent=2, default=float))
    write_tables(agg)
    print("TRANSITION DONE", flush=True)
    return agg


def _m(xs):
    return {"mean": st.mean(xs), "std": st.pstdev(xs) if len(xs) > 1 else 0.0, "raw": xs}


def aggregate(cells, seeds):
    out = {"cells": {}}
    for name, c in cells.items():
        table = {}
        for d in map(str, DISTS):
            table[d] = {
                "state_top1": _m([p[d]["state_top1"] for p in c["per_dist"]]),
                "selective_top1": _m([p[d]["selective_top1"] for p in c["per_dist"]]),
                "control_top1": _m([max(p[d]["shuffled_top1"], p[d]["random_top1"]) for p in c["per_dist"]]),
            }
        dyn = {k: _m([dd[k] for dd in c["per_dyn"]])
               for k in ("effective_gamma_mean", "accumulated_rotation_turns",
                         "phase_alignment_cos", "cue_retention_to_probe", "state_norm_mean",
                         "write_rate_mean")}
        out["cells"][name] = {"distances": table, "dynamics_d2048": dyn}
    return out


def interpret(agg):
    def s(name, d="2048"):
        return agg["cells"][name]["distances"][d]["state_top1"]["mean"]
    B, Bg, Bw, AB = s("T-B"), s("T-Bgamma"), s("T-Bomega"), s("T-AB")
    v2 = agg.get("v2s_reference", {}).get("2048", {}).get("mean")
    verdict = {
        "at_distance": 2048,
        "B": B, "B+gamma": Bg, "B+omega": Bw, "AB": AB, "V2-S": v2,
        "dynamic_retention_helps (B+γ>B)": Bg > B + 0.02,
        "rotation_harmful (B+ω<B)": Bw < B - 0.02,
        "rotation_cancels_retention (AB<B+γ)": AB < Bg - 0.02,
        "retention_adds_no_value (B+γ≤B)": Bg <= B + 0.02,
    }
    if v2 is not None:
        verdict["all_v3_below_V2S"] = max(B, Bg, Bw, AB) < v2 - 0.02
    # decision
    if verdict["dynamic_retention_helps (B+γ>B)"] and not verdict["rotation_harmful (B+ω<B)"]:
        dec = "Build V3-AB0 (selective write + dynamic decay, no rotation)."
    elif verdict.get("all_v3_below_V2S"):
        dec = "Keep V2-S as the winning architecture; stop increasing recurrence complexity and invest in autonomous gate learning."
    elif verdict["retention_adds_no_value (B+γ≤B)"]:
        dec = "Keep V2-S; dynamic retention is unnecessary."
    else:
        dec = "Mixed; see per-cell numbers."
    if verdict["rotation_harmful (B+ω<B)"]:
        dec += " Remove token-dependent rotation from persistent memory."
    verdict["decision"] = dec
    return verdict


def write_tables(agg):
    L = ["# Phase v3 — 2×2 transition ablation (γ_t vs ω_t)", "",
         "State focus Top-1 (3-seed mean), write gate / curriculum / budget / readout matched.", "",
         "| cell | " + " | ".join(f"d{d}" for d in DISTS) + " |",
         "|" + "---|" * (len(DISTS) + 1)]
    for name in CELLS:
        t = agg["cells"][name]["distances"]
        L.append(f"| {LABELS[name]} | " + " | ".join(f"{t[str(d)]['state_top1']['mean']:.3f}" for d in DISTS) + " |")
    v2 = agg.get("v2s_reference", {})
    if v2:
        L.append("| V2-S (reference) | " + " | ".join(f"{v2[str(d)]['mean']:.3f}" if str(d) in v2 else "—" for d in DISTS) + " |")
    L += ["", "## Transition dynamics at d2048 (3-seed mean)",
          "| cell | eff γ | acc. rotation (turns) | phase align cos | cue retention | state norm |",
          "|---|---:|---:|---:|---:|---:|"]
    for name in CELLS:
        dy = agg["cells"][name]["dynamics_d2048"]
        L.append(f"| {LABELS[name]} | {dy['effective_gamma_mean']['mean']:.4f} | "
                 f"{dy['accumulated_rotation_turns']['mean']:.1f} | {dy['phase_alignment_cos']['mean']:+.2f} | "
                 f"{dy['cue_retention_to_probe']['mean']:.3f} | {dy['state_norm_mean']['mean']:.1f} |")
    it = agg.get("interpretation", {})
    L += ["", "## Interpretation", f"**Decision:** {it.get('decision','')}", ""]
    for k in ("dynamic_retention_helps (B+γ>B)", "rotation_harmful (B+ω<B)",
              "rotation_cancels_retention (AB<B+γ)", "retention_adds_no_value (B+γ≤B)", "all_v3_below_V2S"):
        if k in it:
            L.append(f"- {k}: **{it[k]}**")
    (HERE / "results" / "transition_tables.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    run()
