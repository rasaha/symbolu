// Phase 6E — Fused decode-write kernel API.
//
// Two kernels collapse the writer's per-decode-step Python op chain
// (~30 small CUDA kernel launches per layer per step) into 1-2 kernel
// launches. See PHASE_6E_WRITER_FUSION_DESIGN.md for the full
// motivation and PHASE_6D_PROFILE_SUMMARY.md for the measured data
// that justified this work.
//
// Contract: byte-equivalent to the Python reference
// `_phase6e_fused_decode_write_python_ref` in
// `phase5b_4c_paged_writer.py`. CPU verifier
// `verify_phase6e_fused_byte_eq.py` is the dispositive test.
#pragma once

#include <torch/extension.h>

namespace int4_protected {

// fused_decode_write_v
//
// Replaces the V-side path of write_decode_batched's captured region.
// Quantizes V to int4 groups + writes packed bytes into kv_cache[1]
// at (block_id, position, h, :half_D); writes v_scale/v_xmin sidecars
// at (block_id, position, h, group_idx).
//
// Inputs (read-only):
//   value          (B, H, D) bfloat16         New V tokens this step.
//   slot_mapping   (B,)      int64            vLLM cache slot per batch position.
//                                              -1 marks inactive rows; writes
//                                              for those rows go to slot 0 of
//                                              block 0 (harmless under matched
//                                              active_mask gating on read).
// Outputs (in-place, must be CUDA tensors on the same device):
//   kv_cache_v     (NB, BS, H, D/2)  uint8    Packed int4 V cache.
//   v_scale_ext    (NB, BS, H, n_groups) bf16 Per-group scale (bf16).
//   v_xmin_ext     (NB, BS, H, n_groups) bf16 Per-group min (bf16).
//
// Constants:
//   group_size: V quantization group along head_dim. Must divide D.
//
// Performance budget (per call, B=8, H=4, D=128, group_size=32):
//   ~5-10 µs target (vs ~50-100 µs in the current Python op chain).
//   ~10 ops collapsed into 1 launch.
void fused_decode_write_v(
    torch::Tensor value,
    torch::Tensor slot_mapping,
    torch::Tensor kv_cache_v,
    torch::Tensor v_scale_ext,
    torch::Tensor v_xmin_ext,
    int64_t       group_size
);

// fused_decode_write_k
//
// Replaces the K-side path of write_decode_batched's captured region.
// Updates the K staging buffer (per-slot rolling BS-window), gathers
// the protected dims into k_protect_ext, and on block-fill writes
// the packed int4 K + scale + xmin sidecars into kv_cache[0]/sidecars.
// Increments _seq_pos_pool for active rows.
//
// Inputs (read-only):
//   key                       (B, H, D)       bf16   New K tokens.
//   slot_idx_t                (B,)            int64  Writer's per-slot index.
//   slot_mapping              (B,)            int64  vLLM cache slot.
//   protect_mask              (H, D)          int8   Per-model frozen mask.
//   protected_d_per_head      (H, n_protect)  int64  Gather index for protected dims.
//
// Outputs (in-place, all CUDA, same device):
//   k_stage_pool              (n_slots, BS, H, D) bf16  Rolling K stage.
//   k_stage_block_id_pool     (n_slots,) int64   Last block written per slot (-1 sentinel).
//   k_stage_count_pool        (n_slots,) int32   Count of staged tokens per slot.
//   seq_pos_pool              (n_slots,) int32   Per-slot seq position (incremented).
//   kv_cache_k                (NB, BS, H, D/2) uint8  Packed int4 K (rmw under block_full).
//   k_scale_ext               (NB, H, D)  bf16        K scale sidecar (rmw under block_full).
//   k_xmin_ext                (NB, H, D)  bf16        K xmin  sidecar (rmw under block_full).
//   k_protect_ext             (NB, BS, H, n_protect) bf16  Protect-mask K per-token write.
//
// Performance budget (per call, B=8, H=4, D=128, BS=32):
//   ~10-20 µs target (vs ~150-200 µs in the current Python op chain).
//   ~25 ops collapsed into 1 launch.
void fused_decode_write_k(
    torch::Tensor key,
    torch::Tensor slot_idx_t,
    torch::Tensor slot_mapping,
    torch::Tensor protect_mask,
    torch::Tensor protected_d_per_head,
    torch::Tensor k_stage_pool,
    torch::Tensor k_stage_block_id_pool,
    torch::Tensor k_stage_count_pool,
    torch::Tensor seq_pos_pool,
    torch::Tensor kv_cache_k,
    torch::Tensor k_scale_ext,
    torch::Tensor k_xmin_ext,
    torch::Tensor k_protect_ext
);

} // namespace int4_protected
