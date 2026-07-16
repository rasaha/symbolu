"""CPU synthetic generators — factorable vs. non-factorable metadata, and full
K/Q/V captures — so every analysis stage is testable with NO GPU and NO model.

The point of the falsification study is to DETECT structure when it exists and REFUSE
it when it doesn't; these generators give both ground truths.
"""
from __future__ import annotations

import torch

try:
    from . import quant_ref
except ImportError:  # pragma: no cover
    import quant_ref  # type: ignore


def factorable_scale(B: int, D: int, seed: int = 0, noise: float = 0.0) -> torch.Tensor:
    """s[b,d] = α_d · β_b (exact rank-1 multiplicative) + optional lognormal noise."""
    g = torch.Generator().manual_seed(seed)
    alpha = torch.rand(D, generator=g) * 2.0 + 0.1          # (D,) positive
    beta = torch.rand(B, generator=g) * 2.0 + 0.1           # (B,)
    s = beta[:, None] * alpha[None, :]
    if noise > 0:
        s = s * torch.exp(noise * torch.randn(B, D, generator=g))
    return s.clamp_min(1e-6)


def random_scale(B: int, D: int, seed: int = 1) -> torch.Tensor:
    """No low-rank structure: full-rank positive matrix (should FAIL the structural gate)."""
    g = torch.Generator().manual_seed(seed)
    return (torch.rand(B, D, generator=g) * 3.0 + 0.05)


def factorable_xmin(B: int, D: int, seed: int = 2, noise: float = 0.0) -> torch.Tensor:
    """x[b,d] = u_d + v_b (exact additive) + optional Gaussian noise."""
    g = torch.Generator().manual_seed(seed)
    u = torch.randn(D, generator=g)
    v = torch.randn(B, generator=g)
    x = u[None, :] + v[:, None]
    if noise > 0:
        x = x + noise * torch.randn(B, D, generator=g)
    return x


def random_xmin(B: int, D: int, seed: int = 3) -> torch.Tensor:
    g = torch.Generator().manual_seed(seed)
    return torch.randn(B, D, generator=g) * 2.0


def synthetic_metadata_manifest(n_layers: int = 2, H: int = 4, B: int = 8, D: int = 128,
                                factorable: bool = True, seed: int = 0) -> dict:
    """A manifest whose s_prod/xmin_prod are set DIRECTLY from the (non)factorable
    generators — the CLEAN detector self-check for the structural audit (bypasses the
    K→affine derivation so the ground truth is exact). factorable -> rank1/additive
    rel_frob ~0; random -> large."""
    layers = []
    for li in range(n_layers):
        s = torch.stack([(factorable_scale if factorable else random_scale)(B, D, seed + li * H + h)
                         for h in range(H)], dim=1)           # (B, H, D)
        x = torch.stack([(factorable_xmin if factorable else random_xmin)(B, D, seed + 100 + li * H + h)
                         for h in range(H)], dim=1)           # (B, H, D)
        layers.append({"layer": li, "s_prod": s, "xmin_prod": x})
    return {"model": f"SYNTHETIC_META_{'factorable' if factorable else 'random'}",
            "mask_path": None, "BS": 32, "n_protect": 5,
            "geom": {"n_layers": n_layers, "H_kv": H, "D": D, "S": B * 32, "n_blocks": B},
            "seed": seed, "layers": layers}


def synthetic_capture(n_layers: int = 2, S: int = 96, H: int = 4, H_q: int = 8,
                      D: int = 128, BS: int = 32, n_protect: int = 5, seed: int = 0,
                      factorable: bool = True) -> dict:
    """A full fake capture: post-RoPE K/Q/V + production scale/xmin (derived via the
    faithful affine quant) + a protect mask. When ``factorable``, K is built so its
    per-block per-channel scale is near rank-1 (query-fold should pass); otherwise K is
    generic (query-fold should lose more)."""
    g = torch.Generator().manual_seed(seed)
    n_blocks = (S + BS - 1) // BS
    layers = []
    for li in range(n_layers):
        if factorable:
            # K = (per-channel profile) * (per-block gain) * code-like content -> near rank-1 scale
            chan = (torch.rand(D, generator=g) * 2 + 0.2)
            gain = (torch.rand(n_blocks, generator=g) * 2 + 0.2)
            base = torch.randn(S, H, D, generator=g)
            blk_gain = gain.repeat_interleave(BS)[:S][:, None, None]
            K = base * chan[None, None, :] * blk_gain
        else:
            K = torch.randn(S, H, D, generator=g) * (torch.rand(D, generator=g) * 3 + 0.1)
        V = torch.randn(S, H, D, generator=g)
        Q = torch.randn(S, H_q, D, generator=g)                   # queries (use S rows)
        # store-precision FIRST, then derive metadata from the stored bf16 values so the
        # manifest is self-consistent (matches what the real capture does).
        K = K.to(torch.bfloat16)
        Kf = K.to(torch.float32)
        s_prod, xmin_prod, codes = quant_ref.production_k_metadata(Kf, BS)
        mask = torch.zeros(H, D, dtype=torch.int8)
        mask[:, :n_protect] = 1                                    # first n_protect channels protected
        layers.append({"layer": li, "K": K, "V": V.to(torch.bfloat16),
                       "Q": Q.to(torch.bfloat16), "s_prod": s_prod, "xmin_prod": xmin_prod,
                       "codes": codes, "protect_mask": mask})
    return {"model": "SYNTHETIC", "mask_path": None, "BS": BS, "n_protect": n_protect,
            "geom": {"n_layers": n_layers, "H_kv": H, "H_q": H_q, "D": D, "S": S,
                     "n_blocks": n_blocks}, "seed": seed, "factorable": factorable,
            "layers": layers}
