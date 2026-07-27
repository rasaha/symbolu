"""
ablations.py — § 'Required causal controls' for the autonomous-gate study.

Each control is applied at EVAL to a trained model; the focus probe is refit on the resulting
state so a surviving decode means the state truly carries relevance, not sparsity/regularization.

    gate_force_one / gate_force_zero      : dense / empty writes
    gate_shuffle_examples / _positions    : right gate values, wrong binding
    gate_random_matched                   : random gate matched to the model's write rate
    remove_focus_header                   : blank the cue (positions 0)
    shuffle_focus_identity                : relabel the focus (probe target) — should destroy decode
"""
from __future__ import annotations

import torch

from experiments.phase_v3_selective_ssm import dataset as D
from experiments.phase_v3_selective_ssm.config import DataCfg
from experiments.phase_v3_selective_ssm.focus_probe import _fit_linear


@torch.no_grad()
def _state_probe(model, vocab, dcfg, distance, seed, gate_fn=None, mutate=None, n_train=500, n_eval=350):
    def feats(data):
        Xs, ys = [], []
        for i in range(0, len(data), 32):
            b = data[i:i + 32]
            if mutate:
                b = [mutate(dict(e)) for e in b]
            ids, wt, pp, fo = D.collate(b, vocab.PAD)
            gate = gate_fn(model, ids) if gate_fn else model.gate(ids)
            f = model.features(ids, gate=gate)
            ar = torch.arange(ids.shape[0])
            Xs.append(f["state"][ar, pp]); ys.append(fo)
        return torch.cat(Xs), torch.cat(ys)
    Xtr, ytr = feats(D.generate(vocab, dcfg, distance, n_train, 5000 + seed))
    Xte, yte = feats(D.generate(vocab, dcfg, distance, n_eval, 9000 + seed))
    return _fit_linear(Xtr, ytr, Xte, yte, dcfg.num_entities, seed=seed)["top1"]


def run_controls(model, vocab, dcfg, distance=512, seed=0):
    out = {}
    out["baseline"] = _state_probe(model, vocab, dcfg, distance, seed)
    out["gate_force_one"] = _state_probe(model, vocab, dcfg, distance, seed,
                                         gate_fn=lambda m, ids: torch.ones_like(m.gate(ids)))
    out["gate_force_zero"] = _state_probe(model, vocab, dcfg, distance, seed,
                                          gate_fn=lambda m, ids: torch.zeros_like(m.gate(ids)))
    out["gate_shuffle_examples"] = _state_probe(
        model, vocab, dcfg, distance, seed,
        gate_fn=lambda m, ids: m.gate(ids)[torch.randperm(ids.shape[0])])
    out["gate_shuffle_positions"] = _state_probe(
        model, vocab, dcfg, distance, seed,
        gate_fn=lambda m, ids: m.gate(ids)[:, torch.randperm(ids.shape[1])])

    def matched(m, ids):
        g = m.gate(ids); rate = g.mean()
        return (torch.rand_like(g) < rate).float()
    out["gate_random_matched"] = _state_probe(model, vocab, dcfg, distance, seed, gate_fn=matched)

    def blank_header(e):
        e = dict(e); e["tokens"] = list(e["tokens"]); e["tokens"][0] = vocab.PAD; return e
    out["remove_focus_header"] = _state_probe(model, vocab, dcfg, distance, seed, mutate=blank_header)

    # shuffle_focus_identity: relabel the probe target randomly → decode should fall to chance
    def shuffle_focus(e):
        e = dict(e); e["focus_id"] = int(torch.randint(0, dcfg.num_entities, (1,)).item()); return e
    out["shuffle_focus_identity"] = _state_probe(model, vocab, dcfg, distance, seed, mutate=shuffle_focus)
    return out
