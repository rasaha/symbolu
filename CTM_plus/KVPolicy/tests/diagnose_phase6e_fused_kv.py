"""Phase 6E diagnostic — pinpoint why fused CUDA kernel q values differ.

Runs ONE write_decode_batched call on CUDA, twice:
  * PHASE6E_FUSED_WRITER=0 — inline PyTorch op chain (the reference).
  * PHASE6E_FUSED_WRITER=1 — our fused CUDA kernels.

For every (block, pos, h, d_pack) byte in kv_cache that differs, prints:
  - the inline byte (= q_low | (q_high << 4))
  - the fused byte
  - which nibble flipped, by how much
  - the source value v[b, h, d] (bf16 as float)
  - the per-group scale and xmin (recomputed from the source bf16 inputs)
  - the EXACT normalized = (v - xmin) / scale (no rounding) as float64
  - what rintf(...) should return, compared to what each path stored

Run with:
  python CTM_plus/KVPolicy/tests/diagnose_phase6e_fused_kv.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_CANDIDATES = [
    Path("/workspace/symbolu/CTM_plus"),
    Path("/home/user/symbolu/CTM_plus"),
    Path(__file__).resolve().parent.parent.parent,
]
for _root in ROOT_CANDIDATES:
    kvp = _root / "KVPolicy"
    if kvp.is_dir() and str(kvp) not in sys.path:
        sys.path.insert(0, str(kvp))
        break

import torch

assert torch.cuda.is_available(), "Diagnostic requires CUDA."
DEVICE = torch.device("cuda")
SEED = 11
B = 1
N_STEPS = 3
NB, BS, H, D = 64, 32, 4, 128
GROUP_SIZE = 32
N_GROUPS = D // GROUP_SIZE
HALF_D = D // 2


def build_fixed_inputs():
    """Generate the SAME tensors as the verifier so the diagnostic
    matches whatever the verifier sees on seed=SEED, B=B."""
    torch.manual_seed(SEED)
    # Match _drive_write_sequence's pattern: it calls torch.manual_seed(seed)
    # once at start, then loops over n_steps calling torch.randn. So we
    # replicate exactly.
    keys, values = [], []
    for _ in range(N_STEPS):
        keys.append(torch.randn((B, H, D), dtype=torch.bfloat16, device=DEVICE))
        values.append(torch.randn((B, H, D), dtype=torch.bfloat16, device=DEVICE))
    return keys, values


def run_one(fused: bool, keys, values):
    os.environ["PHASE6E_FUSED_WRITER"] = "1" if fused else "0"
    # Re-import so the env flag is picked up at module level if needed.
    from kv_policy.phase5b_4c_paged_writer import PagedKVWriter
    w = PagedKVWriter(layer_idx=0)
    kv_cache = torch.zeros((2, NB, BS, H, D), dtype=torch.uint8, device=DEVICE)
    w._protect_mask_cpu = torch.zeros((H, D), dtype=torch.int8)
    w._protect_mask_cpu[:, :5] = 1
    w._lazy_alloc(kv_cache)

    for s in range(B):
        w.ensure_seq_state(seq_id=s, device=DEVICE)
    slot_idx_t = torch.tensor([w._slot_map[s] for s in range(B)], dtype=torch.long, device=DEVICE)
    base = torch.tensor([s * BS for s in range(B)], dtype=torch.long, device=DEVICE)

    for step in range(N_STEPS):
        abs_pos = base + step
        w.write_decode_batched(
            key=keys[step], value=values[step], kv_cache=kv_cache,
            slot_mapping=abs_pos, slot_idx_t=slot_idx_t, pre_synced=True,
        )
    torch.cuda.synchronize()
    return {
        "kv_cache": kv_cache.clone(),
        "v_scale_ext": w.v_scale_ext.clone(),
        "v_xmin_ext":  w.v_xmin_ext.clone(),
        "k_scale_ext": w.k_scale_ext.clone(),
        "k_xmin_ext":  w.k_xmin_ext.clone(),
    }


def quant_reference_byte(v_source_bf16, h, d_pack):
    """Recompute the V byte at byte index d_pack for head h, replicating
    the Python ref's float32 math exactly. Returns (low_q, high_q, byte)."""
    v = v_source_bf16[h].float()  # (D,) float32, byte-identical to .float() on a bf16 tensor
    d_low  = 2 * d_pack
    d_high = 2 * d_pack + 1
    g = d_low // GROUP_SIZE
    grp = v[g * GROUP_SIZE:(g + 1) * GROUP_SIZE]
    v_min = grp.min()
    v_max = grp.max()
    scale = (v_max - v_min) / 15.0
    scale = torch.clamp(scale, min=1e-8)
    q = ((v - v_min) / scale).round().clamp(0, 15).to(torch.uint8)
    return int(q[d_low].item()), int(q[d_high].item()), v_min.item(), scale.item(), v.tolist()


def report_first_diffs(name, t_inline, t_fused, sources_per_step, n=10):
    diff = (t_inline.int() - t_fused.int()).abs()
    n_mismatch = int((diff > 0).sum().item())
    print(f"\n=== {name} ===")
    print(f"max_abs_diff = {diff.max().item()}, total mismatches = {n_mismatch}")
    if n_mismatch == 0:
        return
    nz = (diff > 0).nonzero()  # (N, ndim)
    print(f"First {min(n, n_mismatch)} mismatches:")
    for i in range(min(n, n_mismatch)):
        idx = nz[i].tolist()
        if t_inline.ndim == 4:  # kv_cache[k] shape (NB, BS, H, D)
            block, pos, h, d_pack = idx
            inline_b = int(t_inline[block, pos, h, d_pack].item())
            fused_b  = int(t_fused [block, pos, h, d_pack].item())
            inline_low, inline_high = inline_b & 0x0F, (inline_b >> 4) & 0x0F
            fused_low,  fused_high  = fused_b  & 0x0F, (fused_b  >> 4) & 0x0F
            # For B=1, step == pos (since base_positions[0] == 0). Source value:
            step = pos
            if step < len(sources_per_step):
                v_src = sources_per_step[step][0]  # (H, D) bf16 (b=0)
                ref_low, ref_high, ref_xmin, ref_scale, _ = quant_reference_byte(v_src, h, d_pack)
                print(f"  [{i}] (block={block}, pos={pos}, h={h}, d_pack={d_pack})")
                print(f"      inline byte = 0x{inline_b:02x}  q_low={inline_low}  q_high={inline_high}")
                print(f"      fused  byte = 0x{fused_b:02x}  q_low={fused_low}   q_high={fused_high}")
                print(f"      python-ref recompute (float32): q_low={ref_low} q_high={ref_high}")
                print(f"      scale={ref_scale:.10g}  xmin={ref_xmin:.10g}")
                d_low, d_high = 2 * d_pack, 2 * d_pack + 1
                v_low  = v_src[h, d_low ].float().item()
                v_high = v_src[h, d_high].float().item()
                norm_low  = (v_low  - ref_xmin) / ref_scale
                norm_high = (v_high - ref_xmin) / ref_scale
                print(f"      v[d_low={d_low}]  = {v_low:.8f}   norm = {norm_low:.10f}")
                print(f"      v[d_high={d_high}] = {v_high:.8f}   norm = {norm_high:.10f}")
            else:
                print(f"  [{i}] {tuple(idx)}: inline=0x{inline_b:02x} fused=0x{fused_b:02x}")
        else:
            # Generic
            inline_v = t_inline[tuple(idx)].item()
            fused_v  = t_fused [tuple(idx)].item()
            print(f"  [{i}] {tuple(idx)}: inline={inline_v}  fused={fused_v}")


def main():
    keys, values = build_fixed_inputs()
    inline = run_one(fused=False, keys=keys, values=values)
    fused  = run_one(fused=True,  keys=keys, values=values)

    print(f"Diagnostic config: device=cuda B={B} n_steps={N_STEPS} seed={SEED}")
    print(f"  H={H} D={D} group_size={GROUP_SIZE} n_groups={N_GROUPS}")

    # Compare V cache + sidecars.
    report_first_diffs(
        "kv_cache_v", inline["kv_cache"][1], fused["kv_cache"][1],
        sources_per_step=values, n=10,
    )
    report_first_diffs(
        "v_scale_ext", inline["v_scale_ext"], fused["v_scale_ext"],
        sources_per_step=values, n=5,
    )
    report_first_diffs(
        "v_xmin_ext", inline["v_xmin_ext"], fused["v_xmin_ext"],
        sources_per_step=values, n=5,
    )

    # K side — only block_full triggers writes, so for n_steps < BS=32 there
    # should be no diff in kv_cache_k. Still report for completeness.
    report_first_diffs(
        "kv_cache_k", inline["kv_cache"][0], fused["kv_cache"][0],
        sources_per_step=keys, n=10,
    )


if __name__ == "__main__":
    main()
