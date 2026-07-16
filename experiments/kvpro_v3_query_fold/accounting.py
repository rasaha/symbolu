"""KVPro V3 query-fold — Phase G systems-value model (MODELED bytes/ops, NEVER TPS).

A candidate is a systems win ONLY if it moves real decode work:
  * fewer scale/xmin metadata bytes per block, AND
  * the per-element affine RECONSTRUCT ops removed (folded to per-token/per-block), AND
  * the replacement cost (Q-fold O(D) once/token + O(1..R)/block) does not cancel it.

A lossless rearrangement that keeps the full per-(b,d) residual (block_meta == D) saves
nothing and returns metadata_bytes_saved_pct == 0 → systems FAIL. Everything here is
modeled bytes/instructions; it is NOT a throughput measurement.
"""
from __future__ import annotations

from typing import Dict

try:
    from . import candidates
except ImportError:  # pragma: no cover
    import candidates  # type: ignore

_BF16 = 2  # bytes


def _block_meta_values(candidate: str, D: int) -> Dict[str, int]:
    """Per-block metadata VALUES kept by the candidate (independent of data)."""
    spec = candidates.CANDIDATE_SPECS[candidate]
    scale_bm = {"production": D, "rank1_mult": 1, "svd": int(spec.get("scale_rank", 2))}[spec["scale"]]
    xmin_bm = {"production": D, "additive": 1, "svd": int(spec.get("xmin_rank", 2))}[spec["xmin"]]
    return {"scale": scale_bm, "xmin": xmin_bm}


def systems_value(candidate: str, D: int = 128, BS: int = 32,
                  w_bytes: float = 0.5, w_ops: float = 0.5) -> Dict[str, object]:
    """MODELED per-(block,head) systems accounting for one candidate.

    Production keeps 2·D metadata values/block (scale D + xmin D). The modeled K-path
    reduction blends the metadata-byte saving with the per-element reconstruct-op saving
    (both leave the per-element path when the residual is dropped). Weights are explicit."""
    prod_vals = 2 * D
    bm = _block_meta_values(candidate, D)
    cand_vals = bm["scale"] + bm["xmin"]
    bytes_saved_frac = (prod_vals - cand_vals) / prod_vals
    per_elem_reconstruct_removed = candidate != "affine"   # scale-mul + xmin-add folded off per-element
    ops_removed_frac = 1.0 if per_elem_reconstruct_removed else 0.0
    modeled = 100.0 * (w_bytes * bytes_saved_frac + w_ops * ops_removed_frac)
    # replacement cost: Q-fold is O(D) ONCE per decode token (amortized ~D/BS per token per block);
    # per block adds `scale` scalars + a Q·xmin dot of `xmin` values. Not per-element -> does not cancel.
    replacement = {
        "q_fold_muls_per_token": (0 if candidate == "affine" else D),   # once/token, folds α_d (and u_d)
        "per_block_scale_scalars": bm["scale"],
        "per_block_xmin_dot_len": bm["xmin"],
        "cancels_saving": False if candidate != "affine" else None,
    }
    return {
        "candidate": candidate,
        "prod_meta_values_per_block": prod_vals,
        "cand_meta_values_per_block": cand_vals,
        "metadata_bytes_per_block_prod": prod_vals * _BF16,
        "metadata_bytes_per_block_cand": cand_vals * _BF16,
        "metadata_bytes_saved_pct": round(100.0 * bytes_saved_frac, 3),
        "per_element_reconstruct_removed": per_elem_reconstruct_removed,
        "modeled_kpath_reduction_pct": round(modeled, 3),
        "modeled_note": ("MODELED reduction of the K reconstruct/dequant SUB-path "
                         "(w_bytes·bytes + w_ops·ops); NOT end-to-end, NOT measured TPS."),
        "replacement_cost": replacement,
    }


def all_candidates(D: int = 128) -> Dict[str, dict]:
    return {c: systems_value(c, D=D) for c in candidates.candidate_names()}
