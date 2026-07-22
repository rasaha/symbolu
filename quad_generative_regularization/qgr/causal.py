"""Read-only causal localization of associative binding.

Nothing here trains, fine-tunes, or changes the model. All tools operate on frozen trained
checkpoints via inference-time forward hooks (ablation / patching), frozen-feature linear
probes (which update ONLY a small external probe, never the model), and gradient attribution.

Pathway taxonomy for the 2-layer model. Each block is:
    x = x + attn(x)      # Quad retrieval == attention output (the two coincide in this model)
    x = x + ff(x)        # MLP / feed-forward output
The residual stream (hidden-state geometry) is the running `x`; the identity skip cannot be
ablated without destroying the model, so we ablate the CONTRIBUTIONS added to it (attn, ff).
"""

from __future__ import annotations

from typing import Dict, List, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

from .mqar import MQARConfig, generate_batch, split_seed, IGNORE_INDEX
from .metrics import evaluate


# ----------------------------- ablation hooks -----------------------------------------

class Ablator:
    """Registers inference-time forward hooks that ablate a pathway's output. Read-only:
    hooks modify activations during the forward pass only and are removed on clear()."""

    def __init__(self, model):
        self.model = model
        self.handles = []
        self._gen = torch.Generator().manual_seed(1234)

    def _attn_hook(self, mode):
        gen = self._gen
        def hook(module, inp, out):
            o, score = out                      # QuadAttention returns (output, quad_score)
            if mode == "zero":
                o2 = torch.zeros_like(o)
            elif mode == "mean":
                o2 = o.mean(dim=1, keepdim=True).expand_as(o)      # position-invariant
            elif mode == "shuffle":
                perm = torch.randperm(o.shape[1], generator=gen)
                o2 = o[:, perm, :]                                  # break query->key alignment
            else:
                raise ValueError(mode)
            return (o2, score)
        return hook

    def _ff_hook(self, mode):
        def hook(module, inp, out):
            if mode == "zero":
                return torch.zeros_like(out)
            if mode == "mean":
                return out.mean(dim=1, keepdim=True).expand_as(out)
            raise ValueError(mode)
        return hook

    def ablate_attn(self, layers: List[int], mode: str = "zero"):
        for L in layers:
            h = self.model.blocks[L].attn.register_forward_hook(self._attn_hook(mode))
            self.handles.append(h)
        return self

    def ablate_ff(self, layers: List[int], mode: str = "zero"):
        for L in layers:
            h = self.model.blocks[L].ff.register_forward_hook(self._ff_hook(mode))
            self.handles.append(h)
        return self

    def clear(self):
        for h in self.handles:
            h.remove()
        self.handles = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.clear()


@torch.no_grad()
def eval_conditions_ablated(model, fc, seed, ablation_fn, n_batches=10) -> Dict[str, float]:
    """Evaluate accuracy on all four conditions with an ablation active.

    ablation_fn(ablator) sets up hooks; conditions are evaluated; hooks are cleared.
    """
    from .experiment import hard_condition_cfgs
    out = {}
    for name, mq in hard_condition_cfgs(fc).items():
        ab = Ablator(model)
        ablation_fn(ab)
        try:
            out[name] = evaluate(model, mq, seed, "test", n_batches, fc.batch_size)["acc"]
        finally:
            ab.clear()
    return out


# ----------------------------- linear probes (frozen features) ------------------------

@torch.no_grad()
def _collect_features(model, mq: MQARConfig, seed: int, split: str, n_batches: int,
                      batch_size: int):
    """Collect per-query-position features (hidden, proj-q, proj-k) and the answer label."""
    feats = {"hidden": [], "proj_q": [], "proj_k": [], "score_vec": []}
    labels = []
    attn = model.blocks[model._aux_layer].attn
    for i in range(n_batches):
        b = generate_batch(mq, split_seed(seed, split, i), batch_size)
        out = model(b.tokens, expose_quad=True, expose_hidden=True)
        h = out["aux_hidden"]                                # [B,N,D]
        q = attn.W_q(attn.norm_q(h))                          # [B,N,D]
        k = attn.W_k(attn.norm_m(h))
        score = out["quad_score"].mean(1)                     # [B,N,N]
        qmask = b.key_pos >= 0
        for bi, t in qmask.nonzero(as_tuple=False).tolist():
            feats["hidden"].append(h[bi, t])
            feats["proj_q"].append(q[bi, t])
            kp = int(b.key_pos[bi, t])
            feats["proj_k"].append(k[bi, kp])                 # correct key's projected key
            # score vector over candidate positions, padded/truncated to first N (fixed len)
            feats["score_vec"].append(score[bi, t])
            labels.append(int(b.targets[bi, t]))              # answer value token
    X = {k: torch.stack(v) for k, v in feats.items()}
    y = torch.tensor(labels, dtype=torch.long)
    return X, y


def linear_probe(model, mq: MQARConfig, seed: int, vocab: int, feature: str,
                 n_train=20, n_test=8, batch_size=32, steps=300) -> float:
    """Train a linear probe (external, frozen model) to predict the answer token from a
    representation; return held-out probe accuracy. Only the probe is optimized."""
    Xtr, ytr = _collect_features(model, mq, seed, "train", n_train, batch_size)
    Xte, yte = _collect_features(model, mq, seed, "test", n_test, batch_size)
    xtr, xte = Xtr[feature], Xte[feature]
    d = xtr.shape[1]
    probe = nn.Linear(d, vocab)
    opt = torch.optim.Adam(probe.parameters(), lr=1e-2)
    for _ in range(steps):
        opt.zero_grad()
        loss = F.cross_entropy(probe(xtr.detach()), ytr)
        loss.backward()
        opt.step()
    with torch.no_grad():
        acc = (probe(xte.detach()).argmax(1) == yte).float().mean().item()
    return acc


# ----------------------------- activation patching (mediation) ------------------------

@torch.no_grad()
def activation_patching(model, mq: MQARConfig, seed: int, layer: int, batch_size=32,
                        n_batches=6) -> Dict[str, float]:
    """Causal mediation via activation patching of the Quad retrieval (attention) output.

    For each query, a CLEAN run and a CORRUPTED run (queries' Quad attention output shuffled
    across positions) are compared. We then patch the CLEAN attention output into the corrupted
    run. If prediction follows the patched Quad output (recovers clean answer), Quad MEDIATES;
    if the corrupted run already predicts the clean answer (or patching does nothing), the
    answer is carried by the un-patched residual/hidden pathway (Quad is reflective).
    """
    clean_acc = corrupt_acc = patched_acc = 0.0
    total = 0
    for i in range(n_batches):
        b = generate_batch(mq, split_seed(seed, "test", i), batch_size)
        qmask = b.targets != IGNORE_INDEX

        clean = model(b.tokens)["logits"].argmax(-1)
        # corrupted: shuffle attention output at `layer`
        ab = Ablator(model); ab.ablate_attn([layer], "shuffle")
        corrupt = model(b.tokens)["logits"].argmax(-1)
        ab.clear()

        # capture clean attention output, then patch it into a shuffled run
        cap = {}
        def capture(m, inp, out):
            cap["o"] = out[0].clone(); return out
        h1 = model.blocks[layer].attn.register_forward_hook(capture)
        model(b.tokens)
        h1.remove()
        def patch(m, inp, out):
            return (cap["o"], out[1])
        h2 = model.blocks[layer].attn.register_forward_hook(patch)
        patched = model(b.tokens)["logits"].argmax(-1)
        h2.remove()

        clean_acc += ((clean == b.targets) & qmask).sum().item()
        corrupt_acc += ((corrupt == b.targets) & qmask).sum().item()
        patched_acc += ((patched == b.targets) & qmask).sum().item()
        total += qmask.sum().item()
    return {"clean": clean_acc / total, "corrupt": corrupt_acc / total,
            "patched": patched_acc / total,
            "recovery": (patched_acc - corrupt_acc) / max(clean_acc - corrupt_acc, 1e-9)}


# ----------------------------- integrated gradients (attribution) ---------------------

def integrated_gradients_pathways(model, mq: MQARConfig, seed: int, layer: int,
                                  steps=16, batch_size=16) -> Dict[str, float]:
    """Integrated-gradients attribution of the correct-token logit to the attention vs FF
    output activations at `layer` (baseline = zero activation). Read-only (model params fixed;
    gradients are only used for attribution, never applied)."""
    b = generate_batch(mq, split_seed(seed, "test", 0), batch_size)
    qmask = b.targets != IGNORE_INDEX
    captured = {}

    def cap_attn(m, inp, out):
        captured["attn"] = out[0]; return out
    def cap_ff(m, inp, out):
        captured["ff"] = out; return out
    h1 = model.blocks[layer].attn.register_forward_hook(cap_attn)
    h2 = model.blocks[layer].ff.register_forward_hook(cap_ff)
    with torch.no_grad():
        model(b.tokens)
    h1.remove(); h2.remove()
    attn_act = captured["attn"].detach()
    ff_act = captured["ff"].detach()

    attrs = {"attn": 0.0, "ff": 0.0}
    for name, act in (("attn", attn_act), ("ff", ff_act)):
        total_grad = torch.zeros_like(act)
        for s in range(1, steps + 1):
            scale = s / steps
            scaled = (act * scale).clone().requires_grad_(True)
            if name == "attn":
                def inj(m, inp, out, sc=scaled):
                    return (sc, out[1])
                hh = model.blocks[layer].attn.register_forward_hook(inj)
            else:
                def inj(m, inp, out, sc=scaled):
                    return sc
                hh = model.blocks[layer].ff.register_forward_hook(inj)
            logits = model(b.tokens)["logits"]
            sel = logits[qmask]
            tgt = b.targets[qmask]
            score = sel.gather(1, tgt.unsqueeze(1)).sum()
            g, = torch.autograd.grad(score, scaled)
            total_grad += g.detach()
            hh.remove()
        ig = (act * total_grad / steps)
        attrs[name] = float(ig.abs().sum())
    tot = attrs["attn"] + attrs["ff"] + 1e-9
    return {"attn_attr": attrs["attn"], "ff_attr": attrs["ff"],
            "attn_frac": attrs["attn"] / tot, "ff_frac": attrs["ff"] / tot}


# ----------------------------- representation similarity (RSA) -------------------------

@torch.no_grad()
def rsa_quad_vs_hidden(model, mq: MQARConfig, seed: int, batch_size=32) -> Dict[str, float]:
    """Does the Quad score mirror hidden-state geometry? Correlate the query-position
    representational dissimilarity matrices (RDMs) of hidden states vs Quad scores. High
    correlation => the Quad score reflects hidden geometry rather than adding new structure."""
    b = generate_batch(mq, split_seed(seed, "test", 3), batch_size)
    out = model(b.tokens, expose_quad=True, expose_hidden=True)
    h = out["aux_hidden"]
    score = out["quad_score"].mean(1)
    qmask = b.key_pos >= 0
    idx = qmask.nonzero(as_tuple=False)
    hs = torch.stack([h[bi, t] for bi, t in idx.tolist()])          # [P,D]
    ss = torch.stack([score[bi, t] for bi, t in idx.tolist()])      # [P,N]
    ss = torch.nan_to_num(ss, neginf=0.0)
    def rdm(x):
        x = F.normalize(x - x.mean(0), dim=1)
        return 1 - (x @ x.t())
    rh, rs = rdm(hs), rdm(ss)
    iu = torch.triu_indices(rh.shape[0], rh.shape[0], offset=1)
    a, c = rh[iu[0], iu[1]], rs[iu[0], iu[1]]
    corr = float(((a - a.mean()) * (c - c.mean())).mean() / (a.std() * c.std() + 1e-9))
    return {"rdm_correlation_hidden_vs_quad": corr}
