"""
dilution_eval.py — focus signal vs distractor count (§11).

Sweep distractor count at a fixed length; probe Phase-only focus decoding and the
persistent-bank state norm. Tests whether Phase v2 avoids the v1 pattern
(focus signal fraction ∝ 1/N).
"""
from __future__ import annotations

import torch
from .focus_data import generate_focus
from .focus_probe import probe_focus

DISTRACTORS = [0, 8, 16, 32, 64, 128]


def run_dilution(model, vocab, seed=2, n=160, target_len=512):
    out = {}
    for nd in DISTRACTORS:
        exs = generate_focus(vocab, "test", seed, n, n_distractors=nd, target_len=target_len)
        pr = probe_focus(model, exs, vocab.pad_id, feature="g")
        out[str(nd)] = {"phase_top1": pr["main"]["top1"], "chance": pr["chance"]}
    return out
