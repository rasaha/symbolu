"""Phase TIER5B — prefix KV snapshot / restore for int4_protected (warm-tier reuse).

The missing half of the warm-tier story: a tensor-level RELOAD that re-injects a
saved prefix's blocks (packed K/V nibbles + all 5 sidecars) back into a fresh paged
allocation, the inverse of the paged writer's existing dump
(`phase5b_4c_paged_writer._maybe_dump_block` under INT4_PROTECTED_DUMP_BLOCKS).

⚠️ HARDWARE-UNTESTED. The tensor ops require torch + a live int4_protected writer +
its paged kv_cache; they are NOT exercised by CPU CI. `verify_roundtrip` is the
built-in byte-gate — run it FIRST on the pod (snapshot → zero → restore → byte-compare)
to prove the primitive before trusting it, exactly as the protocol's Phase-0 gate
requires. Only the pure helpers (plan_restore / check_meta_compatible /
summarize_snapshot) are CPU-tested.

Layout this matches (verified from phase5b_4c_paged_writer.py, per block b):
  packed_k/v      = kv_cache[0|1, b, :, :, :D//2]   (BS, H, D//2)   nibble-packed
  k_scale/k_xmin  = writer.k_{scale,xmin}_ext[b]     (H, D)          per-block
  v_scale/v_xmin  = writer.v_{scale,xmin}_ext[b]     (BS, H, v_groups) per-position
  k_protect       = writer.k_protect_ext[b]          (BS, H, n_protect) in storage fmt
The dump stores k_protect DEQUANTED to bf16 + a format marker; restore re-encodes via
`writer._protect_store` (bf16 -> storage). quantize∘dequant is identity on the uint8
code lattice (round((c*s+m-m)/s)=c), so the round-trip is byte-clean under prot-int8 too.
"""
from __future__ import annotations

from typing import Any, List, Tuple

# Mirror of the writer-module markers (kept local so this file imports without torch).
_PROT_INT8_FORMAT = "prot_int8_asym_static"
_PROT_BF16_FORMAT = "bf16"

_TENSOR_KEYS = ("packed_k", "packed_v", "k_scale", "k_xmin", "k_protect", "v_scale", "v_xmin")


# --------------------------- pure helpers (CPU-tested) --------------------- #
def plan_restore(n_events: int, n_target_blocks: int) -> List[Tuple[int, int]]:
    """Map saved blocks → target blocks, 1:1 and in order. Refuses a count mismatch
    rather than silently truncating (a partial KV load = silent corruption)."""
    if n_events == 0:
        raise ValueError("empty snapshot: no blocks to restore")
    if n_events != n_target_blocks:
        raise ValueError(
            f"snapshot has {n_events} blocks but {n_target_blocks} target blocks were "
            "given; restore is 1:1 and in order — allocate exactly the prefix's block count")
    return [(i, i) for i in range(n_events)]


def check_meta_compatible(snap_meta: dict, writer_meta_d: dict) -> bool:
    """Geometry must match exactly (D / BS / n_protect); a protect-format difference is
    allowed (the dump is dequanted bf16, so restore re-encodes to the writer's format)."""
    for k in ("D", "BS", "n_protect"):
        if snap_meta.get(k) != writer_meta_d.get(k):
            raise ValueError(
                f"incompatible geometry: snapshot/{k}={snap_meta.get(k)} != "
                f"writer/{k}={writer_meta_d.get(k)} — refusing restore")
    if snap_meta.get("prot_format") != writer_meta_d.get("prot_format"):
        import warnings
        warnings.warn(
            f"protect-format differs (snapshot {snap_meta.get('prot_format')} vs writer "
            f"{writer_meta_d.get('prot_format')}); dump is dequanted bf16, restore re-encodes "
            "to the writer's format (precision = the writer's).")
    return True


def summarize_snapshot(snapshot: dict) -> dict:
    """n_blocks + measured stored bytes (sums tensor nbytes; tensor-agnostic)."""
    events = snapshot.get("events", [])
    nbytes = 0
    for ev in events:
        for v in ev.values():
            if hasattr(v, "numel") and hasattr(v, "element_size"):
                nbytes += v.numel() * v.element_size()
    return {"n_blocks": len(events), "approx_bytes": nbytes,
            "prot_format": snapshot.get("meta", {}).get("prot_format")}


def writer_meta(writer: Any) -> dict:
    prot_int8 = getattr(writer, "_prot_int8_active", False)
    return {"D": int(writer.D), "BS": int(writer.BS), "H": int(writer.H),
            "n_protect": int(writer.n_protect),
            "prot_format": _PROT_INT8_FORMAT if prot_int8 else _PROT_BF16_FORMAT}


# --------------------------- tensor ops (pod-only) ------------------------- #
def snapshot_block(writer: Any, kv_cache: Any, b: int) -> dict:
    """Serialize one block (mirrors `_maybe_dump_block` exactly, no 16-block cap)."""
    half_D = writer.D // 2
    prot_int8 = getattr(writer, "_prot_int8_active", False)
    return {
        "block_id": int(b),
        "packed_k": kv_cache[0, b, :, :, :half_D].detach().cpu().clone(),
        "packed_v": kv_cache[1, b, :, :, :half_D].detach().cpu().clone(),
        "k_scale": writer.k_scale_ext[b].detach().cpu().clone(),
        "k_xmin": writer.k_xmin_ext[b].detach().cpu().clone(),
        "k_protect": writer._protect_view_bf16(writer.k_protect_ext[b]).detach().cpu().clone(),
        "k_protect_format": _PROT_INT8_FORMAT if prot_int8 else _PROT_BF16_FORMAT,
        "v_scale": writer.v_scale_ext[b].detach().cpu().clone(),
        "v_xmin": writer.v_xmin_ext[b].detach().cpu().clone(),
    }


def restore_block(writer: Any, kv_cache: Any, ev: dict, tgt: int) -> None:
    """THE missing half: write a saved block's packed K/V + 5 sidecars into block `tgt`.
    Re-encodes the bf16 protect values to the writer's storage format via _protect_store."""
    half_D = writer.D // 2
    dev = kv_cache.device
    kv_cache[0, tgt, :, :, :half_D] = ev["packed_k"].to(dev, kv_cache.dtype)
    kv_cache[1, tgt, :, :, :half_D] = ev["packed_v"].to(dev, kv_cache.dtype)
    sdt = writer.k_scale_ext.dtype
    writer.k_scale_ext[tgt] = ev["k_scale"].to(dev, sdt)
    writer.k_xmin_ext[tgt] = ev["k_xmin"].to(dev, sdt)
    writer.v_scale_ext[tgt] = ev["v_scale"].to(dev, writer.v_scale_ext.dtype)
    writer.v_xmin_ext[tgt] = ev["v_xmin"].to(dev, writer.v_xmin_ext.dtype)
    encoded = writer._protect_store(ev["k_protect"].to(dev))
    writer.k_protect_ext[tgt] = encoded.to(writer.k_protect_ext.dtype)


def _zero_blocks(writer: Any, kv_cache: Any, block_ids) -> None:
    half_D = writer.D // 2
    for b in block_ids:
        kv_cache[0, b, :, :, :half_D].zero_()
        kv_cache[1, b, :, :, :half_D].zero_()
        writer.k_scale_ext[b].zero_()
        writer.k_xmin_ext[b].zero_()
        writer.v_scale_ext[b].zero_()
        writer.v_xmin_ext[b].zero_()
        writer.k_protect_ext[b].zero_()


def save_prefix_snapshot(writer: Any, kv_cache: Any, block_ids, path: str) -> dict:
    """Dump a whole prefix's blocks + sidecars to `path` (torch.save). Returns the
    measured size for the warm-tier bytes/token metric."""
    import torch
    events = [snapshot_block(writer, kv_cache, b) for b in block_ids]
    payload = {"meta": writer_meta(writer), "events": events}
    torch.save(payload, path)
    return {"path": path, **summarize_snapshot(payload)}


def load_prefix_snapshot(path: str) -> dict:
    import torch
    return torch.load(path, map_location="cpu", weights_only=False)


def restore_prefix(writer: Any, kv_cache: Any, snapshot: dict, target_block_ids) -> dict:
    """Restore a loaded snapshot into a freshly-allocated set of blocks (1:1, in order).
    Validates geometry + count BEFORE touching any tensor (cheap guards on the dangerous op)."""
    check_meta_compatible(snapshot["meta"], writer_meta(writer))
    pairs = plan_restore(len(snapshot["events"]), len(list(target_block_ids)))
    tgt = list(target_block_ids)
    for ev_i, tgt_i in pairs:
        restore_block(writer, kv_cache, snapshot["events"][ev_i], tgt[tgt_i])
    return {"restored_blocks": len(pairs)}


def verify_roundtrip(writer: Any, kv_cache: Any, block_ids) -> dict:
    """Built-in Phase-0 byte-gate: snapshot → zero those blocks → restore in place →
    re-snapshot → byte-compare every tensor. Run this on the pod FIRST; `clean=True`
    proves the serialize/restore primitive is bit-faithful (TIER5A → NVMe extension)."""
    import torch
    ids = list(block_ids)
    before = [snapshot_block(writer, kv_cache, b) for b in ids]
    _zero_blocks(writer, kv_cache, ids)
    for ev, b in zip(before, ids):
        restore_block(writer, kv_cache, ev, b)
    after = [snapshot_block(writer, kv_cache, b) for b in ids]
    report, ok = {}, True
    for k in _TENSOR_KEYS:
        eq = all(torch.equal(a[k], c[k]) for a, c in zip(before, after))
        report[k] = bool(eq)
        ok = ok and eq
    return {"clean": bool(ok), "report": report, "n_blocks": len(ids)}
