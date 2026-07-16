"""Shared iteration + worst-case aggregation for the metadata-exploration gate (CPU).

The explore manifest is metadata-ONLY (no K/Q/V):
  {model, BS, geom{n_layers,H_kv,D,n_blocks}, captures:[{prompt_id, seed, layers:[{layer,
   s_prod:(B,H,D), xmin_prod:(B,H,D), protect_mask:(H,D)}]}]}
"""
from __future__ import annotations

from statistics import median
from typing import Dict, Iterator, List, Tuple

import torch

_KEY = {"scale": "s_prod", "xmin": "xmin_prod"}


def load_explore(path: str) -> dict:
    return torch.load(path, map_location="cpu", weights_only=False)


def iter_heads(manifest: dict, kind: str) -> Iterator[Tuple[dict, torch.Tensor]]:
    """Yield ({cap, prompt_id, seed, layer, head}, M[b,d]) for every (capture, layer, head)."""
    key = _KEY[kind]
    for ci, cap in enumerate(manifest["captures"]):
        for lyr in cap["layers"]:
            M = lyr[key]                                   # (B, H, D)
            for h in range(M.shape[1]):
                yield ({"cap": ci, "prompt_id": cap.get("prompt_id"), "seed": cap.get("seed"),
                        "layer": lyr["layer"], "head": h}, M[:, h, :].to(torch.float64))


def n_layer_head(manifest: dict) -> int:
    return sum(m["s_prod"].shape[1] for cap in manifest["captures"] for m in cap["layers"])


def agg_worst(vals: List[float], loc: List[dict], worst: str = "max") -> Dict[str, object]:
    """median + worst-case value with its (layer,head) location. worst='max' or 'min'."""
    if not vals:
        return {"median": None, "worst": None, "worst_loc": None, "n": 0}
    idx = (max if worst == "max" else min)(range(len(vals)), key=lambda i: vals[i])
    return {"median": round(median(vals), 6), "worst": round(vals[idx], 6),
            "worst_loc": {k: loc[idx].get(k) for k in ("layer", "head", "cap")}, "n": len(vals)}


def rel_frob(M: torch.Tensor, hat: torch.Tensor) -> float:
    den = torch.linalg.norm(M.reshape(-1)).item()
    num = torch.linalg.norm((M - hat).reshape(-1)).item()
    return num / den if den > 1e-12 else (0.0 if num <= 1e-12 else float("inf"))
