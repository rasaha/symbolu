"""KVPro V3 Gate-1 — error metrics (reconstruction + attention-output proxy).

Per-layer metrics over fp vs reconstructed K/V. The DECISIVE signal is the attention chain
(logits -> softmax -> output), NOT reconstruction MSE alone (explicit study requirement).
All functions are pure torch (CPU-runnable).
"""
from __future__ import annotations

import math
from typing import Dict, Optional

import torch


def _cos(a: torch.Tensor, b: torch.Tensor) -> float:
    a, b = a.float().reshape(-1), b.float().reshape(-1)
    d = (a.norm() * b.norm()).clamp(min=1e-12)
    return float((a @ b) / d)


def _mse(a: torch.Tensor, b: torch.Tensor) -> float:
    return float((a.float() - b.float()).pow(2).mean())


def _maxabs(a: torch.Tensor, b: torch.Tensor) -> float:
    return float((a.float() - b.float()).abs().max())


def recon_metrics(fp: torch.Tensor, hat: torch.Tensor,
                  protect_mask_hd: Optional[torch.Tensor] = None, tag: str = "") -> Dict[str, float]:
    """Reconstruction error for one tensor (S,H,D): overall + per-head, and protected/unprotected
    split when a K mask is given."""
    out = {f"{tag}mse": _mse(fp, hat), f"{tag}cos": _cos(fp, hat), f"{tag}maxabs": _maxabs(fp, hat)}
    # per-head cosine (min across heads = worst head)
    H = fp.shape[1]
    head_cos = [_cos(fp[:, h], hat[:, h]) for h in range(H)]
    out[f"{tag}head_cos_min"] = min(head_cos)
    out[f"{tag}head_cos_mean"] = sum(head_cos) / len(head_cos)
    if protect_mask_hd is not None:
        m = protect_mask_hd.to(torch.bool)                       # (H,D)
        prot = m.view(1, *m.shape).expand_as(fp)
        if m.any():
            out[f"{tag}prot_mse"] = _mse(fp[prot], hat[prot])
        if (~m).any():
            unp = ~prot
            out[f"{tag}unprot_mse"] = _mse(fp[unp], hat[unp])
            out[f"{tag}unprot_cos"] = _cos(fp[unp], hat[unp])
    return out


def _gqa_expand(kv: torch.Tensor, h_q: int) -> torch.Tensor:
    """(S, H_kv, D) -> (S, H_q, D) by repeating each kv head over its query group."""
    S, H_kv, D = kv.shape
    if h_q == H_kv:
        return kv
    g = h_q // H_kv
    return kv.unsqueeze(2).expand(S, H_kv, g, D).reshape(S, h_q, D)


def attention_metrics(Q: torch.Tensor, K_fp: torch.Tensor, V_fp: torch.Tensor,
                      K_hat: torch.Tensor, V_hat: torch.Tensor) -> Dict[str, float]:
    """Decode-attention proxy. Q:(Sq,Hq,D) query rows; K/V:(S,Hkv,D). Computes logit error, softmax
    KL/JS divergence, and attention-OUTPUT error (the metric that actually matters)."""
    Sq, Hq, D = Q.shape
    S = K_fp.shape[0]
    scale = 1.0 / math.sqrt(D)
    Kf, Vf = _gqa_expand(K_fp, Hq), _gqa_expand(V_fp, Hq)
    Kh, Vh = _gqa_expand(K_hat, Hq), _gqa_expand(V_hat, Hq)

    # logits: (Hq, Sq, S)
    lf = torch.einsum("qhd,khd->hqk", Q.float(), Kf.float()) * scale
    lh = torch.einsum("qhd,khd->hqk", Q.float(), Kh.float()) * scale
    pf = torch.softmax(lf, dim=-1)
    ph = torch.softmax(lh, dim=-1)
    eps = 1e-9
    kl = (pf * ((pf + eps).log() - (ph + eps).log())).sum(-1)                 # (Hq,Sq)
    m = 0.5 * (pf + ph)
    js = 0.5 * (pf * ((pf + eps).log() - (m + eps).log())).sum(-1) \
       + 0.5 * (ph * ((ph + eps).log() - (m + eps).log())).sum(-1)
    of = torch.einsum("hqk,khd->qhd", pf, Vf.float())                         # attn output fp
    oh = torch.einsum("hqk,khd->qhd", ph, Vh.float())
    return {
        "logit_mse": _mse(lf, lh), "logit_maxabs": _maxabs(lf, lh),
        "softmax_kl_mean": float(kl.mean()), "softmax_kl_max": float(kl.max()),
        "softmax_js_mean": float(js.mean()),
        "attn_out_mse": _mse(of, oh), "attn_out_cos": _cos(of, oh),
        "attn_out_maxabs": _maxabs(of, oh),
    }


def relative_to_affine(cand: Dict[str, float], affine: Dict[str, float], keys) -> Dict[str, float]:
    """Ratio cand/affine for the given metric keys (how much worse than the accepted baseline)."""
    out = {}
    for k in keys:
        if k in cand and k in affine and affine[k] > 0:
            out[f"{k}_vs_affine"] = cand[k] / affine[k]
    return out
