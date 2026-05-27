// Phase 6E — fused_decode_write_k
//
// K-side path: update the rolling K stage buffer, gather protected
// dims, and on block-fill commit packed int4 K + scale + xmin
// sidecars. Increments seq_pos_pool for active rows.
//
// Reference contract: phase5b_4c_paged_writer.py
// _phase6e_fused_decode_write_python_ref (K section).
//
// This is the more complex of the two fused kernels. It has a small
// state machine: (1) per-step partial accumulation into k_stage,
// (2) conditional finalize on block-fill. Both happen inside one
// kernel launch.
//
// CUDA dev guidance for the implementer:
//
//   Grid: dim3(B, H)        -- one thread block per (batch, head)
//   Block: threads = D      -- one thread per head dim
//
//   Per thread block (b, h):
//     1. Load key[b, h, 0..D-1] from HBM into registers.
//     2. Compute block_id, position from slot_mapping[b] (handle -1).
//     3. Read prior_block_id = k_stage_block_id_pool[slot_idx_t[b]].
//        is_new_block = (block_id != prior_block_id)
//     4. Read current_k_stage = k_stage_pool[slot_idx_t[b], :, h, :]
//        If is_new_block: zero the whole (BS, D) tile.
//        Place key into cleared_k_stage[position, :] (this thread's row).
//     5. Write back: k_stage_pool[slot_idx_t[b], :, h, :] = cleared_k_stage
//     6. Quantize cleared_k_stage[BS, D] into packed int4:
//          x_max = max over BS rows
//          x_min = min over BS rows
//          scale = max((x_max - x_min) / 15.0f, 1e-8f)
//          q[i,d] = round((cleared_k_stage[i,d] - x_min[d])/scale[d]).clamp(0,15)
//          packed[i, d/2] = q[i, 2*d] | (q[i, 2*d+1] << 4)
//     7. block_full = (position + 1 == BS) AND active(slot_mapping[b] >= 0)
//        If block_full:
//          kv_cache_k[block_id, :, h, :D/2] = packed
//          k_scale_ext[block_id, h, :] = scale (cast to bf16)
//          k_xmin_ext [block_id, h, :] = x_min (cast to bf16)
//
//     Protect side (independent of block_full):
//        For idx in 0..n_protect-1:
//          d = protected_d_per_head[h, idx]
//          k_protect_ext[block_id, position, h, idx] = key[d]   (bf16 copy)
//
//     Bookkeeping (one thread per block writes pool counters):
//        k_stage_block_id_pool[slot_idx_t[b]] = if active then block_id else prior_block_id
//        k_stage_count_pool[slot_idx_t[b]] = if block_full then 0 else (position+1)
//                                           (gated on active for the count case;
//                                            the Python ref's where handles this)
//        seq_pos_pool[slot_idx_t[b]] += active ? 1 : 0   (atomicAdd if multiple
//                                                          batches share a slot —
//                                                          should never happen
//                                                          in practice but
//                                                          atomicAdd is safe)
//
// Critical ordering note:
//   - Read prior_block_id and current_k_stage BEFORE writing back updated
//     k_stage_pool to avoid RAW hazards across thread blocks.
//   - Use __threadfence() after writing k_stage_pool, before reading
//     for the quantization step (if reading via global memory rather
//     than registers).
//   - The seq_pos increment should be last — once it advances, any
//     subsequent read sees the new position.
//
// TODO(phase6e): full implementation. See guidance above.

#include "fused_decode_write.h"
#include <cuda_runtime.h>

namespace int4_protected {

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
) {
    TORCH_CHECK(key.is_cuda(),                   "key must be CUDA");
    TORCH_CHECK(slot_idx_t.is_cuda(),            "slot_idx_t must be CUDA");
    TORCH_CHECK(slot_mapping.is_cuda(),          "slot_mapping must be CUDA");
    TORCH_CHECK(protect_mask.is_cuda(),          "protect_mask must be CUDA");
    TORCH_CHECK(protected_d_per_head.is_cuda(),  "protected_d_per_head must be CUDA");
    TORCH_CHECK(k_stage_pool.is_cuda(),          "k_stage_pool must be CUDA");
    TORCH_CHECK(key.dtype() == torch::kBFloat16, "key must be bf16");
    TORCH_CHECK(slot_idx_t.dtype() == torch::kInt64, "slot_idx_t must be int64");
    TORCH_CHECK(slot_mapping.dtype() == torch::kInt64, "slot_mapping must be int64");
    TORCH_CHECK(seq_pos_pool.dtype() == torch::kInt32, "seq_pos_pool must be int32");
    TORCH_CHECK(k_stage_count_pool.dtype() == torch::kInt32, "k_stage_count_pool must be int32");
    TORCH_CHECK(k_stage_block_id_pool.dtype() == torch::kInt64, "k_stage_block_id_pool must be int64");

    auto B = key.size(0);
    auto H = key.size(1);
    auto D = key.size(2);
    auto BS = k_stage_pool.size(1);
    TORCH_CHECK(slot_idx_t.size(0) == B, "slot_idx_t shape mismatch");
    TORCH_CHECK(slot_mapping.size(0) == B, "slot_mapping shape mismatch");
    TORCH_CHECK(BS == 32, "Phase 6E currently assumes BS=32");

    TORCH_CHECK(false,
        "fused_decode_write_k: CUDA kernel body not yet implemented "
        "(Phase 6E Day 1 scaffold). The Python reference path produces "
        "byte-identical output and is verified by "
        "verify_phase6e_fused_byte_eq.py. To wire up the CUDA kernel, "
        "implement the kernel body following the spec at the top of "
        "this file and replace this TORCH_CHECK with the kernel launch.");
}

} // namespace int4_protected
