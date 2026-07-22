"""Read-only attention-organization diagnostics for the consistency study."""

from __future__ import annotations

import math
import os
import sys
from typing import Dict, List

import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir,
                                "quad_generative_regularization"))
from qgr.mqar import MQARConfig, generate_batch, split_seed  # noqa

from .consistency import js_divergence, distribution_drift, pair_distribution
from .paired_mqar import staged_partner


def _capture_layer_scores(model, tokens):
    """Return list of per-layer quad_score tensors [B,H,N,N] via read-only forward hooks."""
    scores = [None] * len(model.blocks)
    handles = []
    for li, blk in enumerate(model.blocks):
        def mk(idx):
            def hook(m, inp, out):
                scores[idx] = out[1].detach()
                return out
            return hook
        handles.append(blk.attn.register_forward_hook(mk(li)))
    with torch.no_grad():
        model(tokens)
    for h in handles:
        h.remove()
    return scores


@torch.no_grad()
def head_diagnostics(model, mq: MQARConfig, seed: int, n_batches: int = 6, batch_size: int = 32
                     ) -> Dict[str, float]:
    """Entropy, cross-head diversity, head specialization, layer diversity, selection acc."""
    m = mq.num_kv
    ent_sum = div_sum = spec_sum = uni_sum = layer_sum = sel_sum = 0.0
    cnt = 0
    aux = model._aux_layer
    for i in range(n_batches):
        b = generate_batch(mq, split_seed(seed, "test", i), batch_size)
        layer_scores = _capture_layer_scores(model, b.tokens)
        score = layer_scores[aux]                      # [B,H,N,N]
        B, H, N, _ = score.shape
        qmask = b.key_pos >= 0
        idx = qmask.nonzero(as_tuple=False)
        for bi, t in idx.tolist():
            cand = b.cand_mask[bi, t].nonzero(as_tuple=False).flatten()
            if len(cand) < 2:
                continue
            logits = score[bi, :, t, :][:, cand]        # [H, ncand]
            A = F.softmax(logits, dim=-1)               # per-head candidate dist
            # entropy (mean over heads), uniformity
            H_ent = -(A.clamp_min(1e-9) * A.clamp_min(1e-9).log()).sum(-1)   # [H]
            ent_sum += float(H_ent.mean())
            uni_sum += float(H_ent.mean()) / math.log(len(cand))
            # cross-head diversity: mean pairwise JS between head distributions
            if H > 1:
                js = 0.0; npair = 0
                for a in range(H):
                    for c in range(a + 1, H):
                        js += float(js_divergence(A[a], A[c])); npair += 1
                div_sum += js / max(npair, 1)
                # specialization: 1 - fraction of head pairs sharing the argmax candidate
                am = A.argmax(-1)
                agree = 0; np2 = 0
                for a in range(H):
                    for c in range(a + 1, H):
                        agree += int(am[a] == am[c]); np2 += 1
                spec_sum += 1.0 - agree / max(np2, 1)
            # layer diversity: JS between layer-0 and aux-layer head-mean candidate dists
            if len(layer_scores) > 1:
                A0 = F.softmax(layer_scores[0][bi, :, t, :][:, cand], dim=-1).mean(0)
                Aa = A.mean(0)
                layer_sum += float(js_divergence(A0, Aa))
            # selection accuracy: head-mean argmax == correct key
            kp = int(b.key_pos[bi, t])
            correct_slot = (cand == kp).nonzero(as_tuple=False)
            if len(correct_slot):
                sel_sum += int(A.mean(0).argmax() == int(correct_slot[0]))
            cnt += 1
    n = max(cnt, 1)
    return {"entropy": ent_sum / n, "uniformity": uni_sum / n,
            "cross_head_diversity": div_sum / n, "head_specialization": spec_sum / n,
            "layer_diversity": layer_sum / n, "selection_acc": sel_sum / n}


@torch.no_grad()
def perturbation_stability_curve(model, mq: MQARConfig, seed: int, batch_size: int = 32
                                 ) -> List[float]:
    """Progressive-perturbation degradation: retrieval distribution drift (JS) between the base
    and each stage 0..5. Higher = retrieval changes more under that perturbation stage."""
    curve = []
    for stage in range(6):
        P = staged_partner(mq, split_seed(seed, "test", 100 + stage), batch_size, stage)
        sx = model(P.x_tokens, expose_quad=True)["quad_score"]
        st = model(P.xt_tokens, expose_quad=True)["quad_score"]
        curve.append(distribution_drift(sx, P, st))
    return curve
