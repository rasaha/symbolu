"""
distance_eval.py — Phase-only focus decoding vs distance (§10/§11/§14.4).

Freeze a trained variant, generate test sequences of increasing length, and probe
focus decoding from the Phase readout g at the last anchor. Tests whether Phase v2
gives a FLATTER retention curve than v1's dense ~1/N dilution. Inference-only; the
model was trained at a fixed length. Streaming inference is used implicitly (the
recurrence is causal and length-agnostic).
"""
from __future__ import annotations

import torch
from .focus_data import generate_focus
from .focus_probe import probe_focus, features_at_last_anchor, fit_probe
from experiments.phase_guided_slots_v2.task_schema import VENDORS

DISTANCES = [64, 128, 256, 512, 1024]


@torch.no_grad()
def signal_stats(model, exs, pad_id):
    """focus-to-total state ratio (SNR proxy) and state norm at the last anchor."""
    if model.variant_name == "V1":
        return {}
    f = features_at_last_anchor(model, exs, pad_id)
    if "bank_state" not in f:
        return {}
    bs = f["bank_state"]
    return {"state_norm": bs.norm(dim=-1).mean().item()}


def run_distance(model, vocab, seed=1, n=160, n_distractors=24):
    out = {}
    for L in DISTANCES:
        exs = generate_focus(vocab, "test", seed, n, n_distractors=n_distractors, target_len=L)
        pr = probe_focus(model, exs, vocab.pad_id, feature="bank_state")
        row = {"phase_top1": pr["main"]["top1"], "phase_top3": pr["main"]["topk"],
               "shuffled_top1": pr["shuffled"]["top1"], "random_top1": pr["random"]["top1"],
               "chance": pr["chance"]}
        # local-only baseline at this distance
        prl = probe_focus(model, exs, vocab.pad_id, feature="h")
        row["local_top1"] = prl["main"]["top1"]
        row.update(signal_stats(model, exs, vocab.pad_id))
        out[str(L)] = row
    return out
