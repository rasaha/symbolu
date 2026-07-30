"""KVPro prot-int8 validation — Phase 2/3/4 numerical A/B harness (CPU).

Isolates the ONLY variable under test: the protected-channel sidecar representation.

  Config A (BF16 protection): int4 affine residual (production math) for all channels,
                              protected channels overlaid with the EXACT bf16 key value.
  Config B (INT8 protection): identical int4 affine residual, protected channels overlaid
                              with prot_int8 static-asym roundtrip (PRODUCTION math:
                              phase5b_4c_paged_writer.prot_int8_{constants,quantize,dequantize}).
  Config C (Full BF16 KV):    the raw bf16 key (no quantization) — quality/perf reference only.

Because the int4 residual is byte-identical between A and B, every A-vs-B delta is attributable
purely to protected-sidecar precision (bf16 exact -> int8 static-asym). This is the B-A causal
comparison Phase 1 requires.

Real repo implementations used (no reimplementation):
  - CTM_plus/KVPolicy/kv_policy/phase5b_4c_paged_writer.py : prot_int8_* (PRODUCTION sidecar math)
  - experiments/kvpro_v3_symmetric_residual/quantizers.py  : quantize_k_sequence (PRODUCTION int4)

CPU-only. Emits numerical_error.csv, byte_accounting.csv, greedy_parity.csv.
"""
from __future__ import annotations

import csv
import math
import os
import sys
from pathlib import Path

import torch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "CTM_plus" / "KVPolicy"))
sys.path.insert(0, str(REPO / "experiments" / "kvpro_v3_symmetric_residual"))

from kv_policy import phase5b_4c_paged_writer as pw   # noqa: E402  PRODUCTION sidecar math
import quantizers as Q                                # noqa: E402  PRODUCTION int4 residual

ART = REPO / "artifacts" / "prot_int8"
ART.mkdir(parents=True, exist_ok=True)

BS = 32          # production block size
D = 128          # head dim
H = 4            # kv heads (Qwen2.5-7B)
MARGIN = 1.1     # calibration widen margin (matches _widen_minmax default usage)


def make_keys(S: int, dist: str, seed: int) -> torch.Tensor:
    """(S,H,D) bf16 keys from a named distribution (some adversarial)."""
    g = torch.Generator().manual_seed(seed)
    if dist == "normal":
        x = torch.randn(S, H, D, generator=g)
    elif dist == "heavy_tailed":                     # Student-t-like via normal/normal
        x = torch.randn(S, H, D, generator=g) / (torch.randn(S, H, D, generator=g).abs() + 0.3)
    elif dist == "outliers":
        x = torch.randn(S, H, D, generator=g)
        x[:, :, ::17] *= 25.0                        # planted high-magnitude channels
    elif dist == "asymmetric":                       # strictly positive, one-sided
        x = torch.rand(S, H, D, generator=g) * 8.0 + 0.5
    elif dist == "high_dynamic_range":
        scale = torch.logspace(-3, 3, D).view(1, 1, D)
        x = torch.randn(S, H, D, generator=g) * scale
    elif dist == "near_zero":
        x = torch.randn(S, H, D, generator=g) * 1e-3
    else:
        raise ValueError(dist)
    return x.to(torch.bfloat16)


def build_mask(n_protect: int, seed: int) -> torch.Tensor:
    """(H,D) int8 mask with n_protect distinct channels/head (deterministic, sorted)."""
    g = torch.Generator().manual_seed(seed + 999)
    mask = torch.zeros((H, D), dtype=torch.int8)
    if n_protect > 0:
        for h in range(H):
            idx = torch.randperm(D, generator=g)[:n_protect]
            mask[h, idx] = 1
    return mask


def calibrate_minmax(K: torch.Tensor, margin: float):
    """Static per-(H,D) min/max over the token axis, widened by margin — the calibrator's contract."""
    kf = K.float()
    kmin = kf.amin(dim=0)                # (H,D)
    kmax = kf.amax(dim=0)
    center = 0.5 * (kmin + kmax)
    half = 0.5 * (kmax - kmin) * margin
    return center - half, center + half


def reconstruct(K: torch.Tensor, mask: torch.Tensor, mode: str, kmin=None, kmax=None):
    """Return reconstructed (S,H,D) float32 K under config A/B/C, isolating the protect sidecar."""
    if mode == "C":                                  # full bf16 (reference)
        return K.float()
    # int4 affine residual — PRODUCTION math, identical for A and B
    K_int4 = Q.quantize_k_sequence(K, BS, "affine").float()
    m = mask.to(torch.bool)
    if not m.any():
        return K_int4
    prot3 = m.view(1, H, D).expand(K.shape[0], H, D)
    if mode == "A":                                  # bf16 protection = EXACT bf16 value
        prot_vals = K.float()
    elif mode == "B":                                # int8 static-asym protection (PRODUCTION)
        # gather protected channels per head in mask order, quantize+dequant, scatter back
        rec = K_int4.clone()
        for h in range(H):
            dch = torch.nonzero(m[h], as_tuple=True)[0]
            if dch.numel() == 0:
                continue
            vals = K.float()[:, h, dch]              # (S, n_h)
            qmin, qscale = pw.prot_int8_constants(kmin[h, dch], kmax[h, dch])
            codes = pw.prot_int8_quantize(vals, qmin, qscale)
            deq = pw.prot_int8_dequantize(codes, qmin, qscale, torch.bfloat16).float()
            rec[:, h, dch] = deq
        return rec
    else:
        raise ValueError(mode)
    return torch.where(prot3, prot_vals, K_int4)


def err_metrics(ref: torch.Tensor, test: torch.Tensor, restrict_mask=None):
    """A dict of error metrics comparing test vs ref (float32)."""
    if restrict_mask is not None:
        rm = restrict_mask.to(torch.bool).view(1, H, D).expand_as(ref)
        a = ref[rm].flatten(); b = test[rm].flatten()
    else:
        a = ref.flatten(); b = test.flatten()
    if a.numel() == 0:
        return {"n": 0}
    diff = (b - a)
    ad = diff.abs()
    l2 = torch.linalg.vector_norm(diff) / (torch.linalg.vector_norm(a) + 1e-12)
    cos = torch.nn.functional.cosine_similarity(a, b, dim=0).item()
    return {
        "n": int(a.numel()),
        "max_abs": ad.max().item(),
        "mean_abs": ad.mean().item(),
        "rmse": diff.pow(2).mean().sqrt().item(),
        "rel_l2": l2.item(),
        "cosine": cos,
        "p50": ad.quantile(0.50).item(),
        "p90": ad.quantile(0.90).item(),
        "p99": ad.quantile(0.99).item(),
        "p999": ad.quantile(0.999).item(),
        "nan_inf": int((~torch.isfinite(diff)).sum().item()),
    }


def attention(Q_: torch.Tensor, K: torch.Tensor, V: torch.Tensor):
    """Single-query decode attention over (S,H,D). Q_:(H,D). Returns (logits(H,S), probs, out(H,D))."""
    scale = 1.0 / math.sqrt(D)
    logits = torch.einsum("hd,shd->hs", Q_.float(), K.float()) * scale   # (H,S)
    probs = torch.softmax(logits, dim=-1)
    out = torch.einsum("hs,shd->hd", probs, V.float())
    return logits, probs, out


def kl(p, q):
    p = p.clamp_min(1e-12); q = q.clamp_min(1e-12)
    return (p * (p.log() - q.log())).sum(-1)


def run():
    dists = ["normal", "heavy_tailed", "outliers", "asymmetric", "high_dynamic_range", "near_zero"]
    protect_pcts = [0, 1, 2, 4, 8]     # % of D=128 -> n_protect = round(pct/100*128)
    seqlens = [128, 512, 2048]
    seeds = [0, 1, 2]

    num_rows = []
    parity_rows = []
    for pct in protect_pcts:
        n_protect = max(0, round(pct / 100 * D)) if pct > 0 else 0
        for S in seqlens:
            for dist in dists:
                for seed in seeds:
                    K = make_keys(S, dist, seed)
                    g = torch.Generator().manual_seed(seed + 7)
                    V = torch.randn(S, H, D, generator=g).to(torch.bfloat16)
                    Qd = torch.randn(H, D, generator=g).to(torch.bfloat16)
                    mask = build_mask(n_protect, seed)
                    kmin, kmax = calibrate_minmax(K, MARGIN)

                    Ka = reconstruct(K, mask, "A", kmin, kmax)
                    Kb = reconstruct(K, mask, "B", kmin, kmax)

                    # Level 1: protected-value reconstruction (restricted to mask)
                    l1 = err_metrics(Ka, Kb, restrict_mask=mask) if n_protect else {"n": 0}
                    # Level 2: full reconstructed K
                    l2 = err_metrics(Ka, Kb)
                    # Levels 3-5: attention on identical Q,V — delta flows only through protected K
                    la, pa, oa = attention(Qd, Ka, V)
                    lb, pb, ob = attention(Qd, Kb, V)
                    logit_abs = (lb - la).abs()
                    top1_a = la.argmax(-1); top1_b = lb.argmax(-1)
                    top1_agree = (top1_a == top1_b).float().mean().item()
                    k = min(5, S)
                    topk_a = set(la.topk(k, -1).indices.flatten().tolist())
                    topk_b = set(lb.topk(k, -1).indices.flatten().tolist())
                    topk_overlap = len(topk_a & topk_b) / max(1, len(topk_a | topk_b))
                    kl_ab = kl(pa, pb).mean().item()
                    m_pq = 0.5 * (pa + pb)
                    jsd = (0.5 * kl(pa, m_pq) + 0.5 * kl(pb, m_pq)).mean().item()
                    tvd = 0.5 * (pa - pb).abs().sum(-1).mean().item()
                    out_l2 = (torch.linalg.vector_norm(ob - oa) /
                              (torch.linalg.vector_norm(oa) + 1e-12)).item()
                    out_cos = torch.nn.functional.cosine_similarity(
                        oa.flatten(), ob.flatten(), dim=0).item()

                    num_rows.append({
                        "protect_pct": pct, "n_protect": n_protect, "seqlen": S,
                        "dist": dist, "seed": seed,
                        "L1_recon_max_abs": l1.get("max_abs", 0.0),
                        "L1_recon_rmse": l1.get("rmse", 0.0),
                        "L1_recon_cosine": l1.get("cosine", 1.0),
                        "L1_recon_p999": l1.get("p999", 0.0),
                        "L1_nan_inf": l1.get("nan_inf", 0),
                        "L2_K_rel_l2": l2["rel_l2"], "L2_K_cosine": l2["cosine"],
                        "L3_logit_max_abs": logit_abs.max().item(),
                        "L3_logit_rel_l2": (torch.linalg.vector_norm(lb - la) /
                                            (torch.linalg.vector_norm(la) + 1e-12)).item(),
                        "L3_top1_agree": top1_agree, "L3_top5_overlap": topk_overlap,
                        "L4_kl": kl_ab, "L4_jsd": jsd, "L4_tvd": tvd,
                        "L5_out_rel_l2": out_l2, "L5_out_cosine": out_cos,
                    })
                    # greedy-parity proxy (no model): does the argmax-attended position agree?
                    parity_rows.append({
                        "protect_pct": pct, "n_protect": n_protect, "seqlen": S,
                        "dist": dist, "seed": seed,
                        "top1_attn_pos_agree_frac": top1_agree,
                        "K_bitidentical_AB": bool(torch.equal(Ka, Kb)),
                        "logit_max_abs_delta": logit_abs.max().item(),
                    })

    _write_csv(ART / "numerical_error.csv", num_rows)
    _write_csv(ART / "greedy_parity.csv", parity_rows)
    print(f"wrote numerical_error.csv ({len(num_rows)} rows), greedy_parity.csv ({len(parity_rows)} rows)")

    # ---- summary to stdout ----
    import statistics as st
    nz = [r for r in num_rows if r["n_protect"] > 0]
    print("\n=== A-vs-B (INT8 - BF16 protection) summary over", len(nz), "protected configs ===")
    print(f"  worst L1 protected-recon max_abs : {max(r['L1_recon_max_abs'] for r in nz):.4e}")
    print(f"  worst L2 full-K rel_L2           : {max(r['L2_K_rel_l2'] for r in nz):.4e}")
    print(f"  worst L3 logit rel_L2            : {max(r['L3_logit_rel_l2'] for r in nz):.4e}")
    print(f"  min   L3 top1 attn agreement     : {min(r['L3_top1_agree'] for r in nz):.4f}")
    print(f"  worst L4 KL(A||B)                : {max(r['L4_kl'] for r in nz):.4e}")
    print(f"  worst L5 attn-out rel_L2         : {max(r['L5_out_rel_l2'] for r in nz):.4e}")
    print(f"  min   L5 attn-out cosine         : {min(r['L5_out_cosine'] for r in nz):.6f}")
    print(f"  total NaN/Inf                    : {sum(r['L1_nan_inf'] for r in nz)}")
    print(f"  any K bit-identical(A==B)?       : {any(p['K_bitidentical_AB'] for p in parity_rows if p['n_protect']>0)}")


def _write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    run()
