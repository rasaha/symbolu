"""KVPro V3 query-fold — attention-level metrics (CPU-pure, self-contained).

NOT tensor-MSE alone: reports K reconstruction (overall + protected/unprotected), QK
logit error + rank correlation, softmax KL, top-attended-token overlap, and attention
output MSE/cosine. GQA is handled by expanding KV heads to the query-head count.
"""
from __future__ import annotations

from typing import Dict

import torch


def _cos(a: torch.Tensor, b: torch.Tensor) -> float:
    a, b = a.reshape(-1).float(), b.reshape(-1).float()
    return torch.nn.functional.cosine_similarity(a, b, dim=0).item()


def _mse(a, b): return ((a.float() - b.float()) ** 2).mean().item()
def _maxabs(a, b): return (a.float() - b.float()).abs().max().item()


def gqa_expand(kv: torch.Tensor, h_q: int) -> torch.Tensor:
    """kv: (S, H_kv, D) -> (S, H_q, D) by repeating each KV head h_q//H_kv times."""
    S, h_kv, D = kv.shape
    if h_kv == h_q:
        return kv
    if h_q % h_kv != 0:
        raise ValueError(f"H_q={h_q} not a multiple of H_kv={h_kv}")
    return kv.repeat_interleave(h_q // h_kv, dim=1)


def _attn(Q: torch.Tensor, K: torch.Tensor, V: torch.Tensor):
    """Q:(Sq,Hq,D) K,V:(S,Hq,D) -> logits:(Hq,Sq,S), probs, out:(Sq,Hq,D)."""
    Qh, Kh, Vh = Q.permute(1, 0, 2).float(), K.permute(1, 0, 2).float(), V.permute(1, 0, 2).float()
    scale = 1.0 / (Q.shape[-1] ** 0.5)
    logits = torch.matmul(Qh, Kh.transpose(1, 2)) * scale       # (Hq,Sq,S)
    probs = torch.softmax(logits, dim=-1)
    out = torch.matmul(probs, Vh).permute(1, 0, 2)              # (Sq,Hq,D)
    return logits, probs, out


def _spearman(a: torch.Tensor, b: torch.Tensor) -> float:
    """Mean rank correlation of logits over the key axis (last dim)."""
    ar = a.argsort(-1).argsort(-1).float()
    br = b.argsort(-1).argsort(-1).float()
    ar = ar - ar.mean(-1, keepdim=True)
    br = br - br.mean(-1, keepdim=True)
    num = (ar * br).sum(-1)
    den = (ar.norm(dim=-1) * br.norm(dim=-1)).clamp_min(1e-9)
    return (num / den).mean().item()


def _softmax_kl(p_fp: torch.Tensor, p_hat: torch.Tensor) -> float:
    kl = (p_fp * (p_fp.clamp_min(1e-9).log() - p_hat.clamp_min(1e-9).log())).sum(-1)
    return kl.mean().item()


def _topk_overlap(l_fp: torch.Tensor, l_hat: torch.Tensor, k: int) -> float:
    k = min(k, l_fp.shape[-1])
    mf = torch.zeros_like(l_fp, dtype=torch.bool).scatter_(-1, l_fp.topk(k, -1).indices, True)
    mh = torch.zeros_like(l_hat, dtype=torch.bool).scatter_(-1, l_hat.topk(k, -1).indices, True)
    return ((mf & mh).sum(-1).float() / k).mean().item()


def metrics(Q: torch.Tensor, K_fp: torch.Tensor, V_fp: torch.Tensor,
            K_hat: torch.Tensor, V_hat: torch.Tensor, protect_mask_hd: torch.Tensor,
            topk: int = 10) -> Dict[str, float]:
    """Q:(Sq,Hq,D); K_*/V_*:(S,H_kv,D); protect_mask_hd:(H_kv,D). All-vs-all attention
    (query rows attend to every key). Returns the full metric set."""
    h_q = Q.shape[1]
    mask = protect_mask_hd.to(torch.bool)
    # --- K reconstruction (pre-GQA, at KV-head granularity) ---
    out: Dict[str, float] = {
        "k_recon_mse": _mse(K_fp, K_hat),
        "k_recon_cos": _cos(K_fp, K_hat),
        "k_recon_maxabs": _maxabs(K_fp, K_hat),
    }
    if mask.any():
        out["k_recon_mse_protected"] = _mse(K_fp[:, mask], K_hat[:, mask])
    if (~mask).any():
        out["k_recon_mse_unprotected"] = _mse(K_fp[:, ~mask], K_hat[:, ~mask])
    # --- attention (expand KV to query heads) ---
    Kf, Vf = gqa_expand(K_fp, h_q), gqa_expand(V_fp, h_q)
    Kh, Vh = gqa_expand(K_hat, h_q), gqa_expand(V_hat, h_q)
    lf, pf, of = _attn(Q, Kf, Vf)
    lh, ph, oh = _attn(Q, Kh, Vh)
    out.update({
        "qk_logit_mse": _mse(lf, lh),
        "qk_logit_maxabs": _maxabs(lf, lh),
        "logit_spearman": _spearman(lf, lh),
        "softmax_kl": _softmax_kl(pf, ph),
        "topk_overlap": _topk_overlap(lf, lh, topk),
        "attn_out_mse": _mse(of, oh),
        "attn_out_cos": _cos(of, oh),
    })
    return out
