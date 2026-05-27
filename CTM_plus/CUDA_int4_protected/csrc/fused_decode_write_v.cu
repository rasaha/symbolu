// Phase 6E — fused_decode_write_v
//
// V-side path: quantize bf16 V to int4 groups + write packed bytes to
// kv_cache + sidecars in one kernel launch.
//
// Reference contract: phase5b_4c_paged_writer.py
// _phase6e_fused_decode_write_python_ref (V section).
//
// CUDA dev guidance for the implementer:
//
//   Grid: dim3(B, H)        -- one thread block per (batch, head)
//   Block: threads = D      -- one thread per head dim (typically 128)
//                              n_groups = D / group_size (typically 4)
//
//   Per thread block (b, h):
//     1. Load value[b, h, 0..D-1] from HBM into registers (bf16).
//        Note slot_mapping[b] = absolute slot in kv_cache; if -1 use 0.
//     2. For each group g in [0, n_groups):
//          v_max[g] = max over d in [g*gs, (g+1)*gs) of value[b,h,d]
//          v_min[g] = min over d in same range
//          v_scale[g] = max((v_max[g] - v_min[g]) / 15.0f, 1e-8f)
//        (Warp shuffle reductions; n_groups * 2 reductions, cheap.)
//     3. Quantize: q[d] = round((value[b,h,d] - v_min[d/gs])/v_scale[d/gs])
//        Clamp to [0, 15].
//     4. Pack: for d in [0, D/2): packed[d] = q[2d] | (q[2d+1] << 4)
//     5. Write packed to kv_cache_v[block_id, position, h, 0..D/2-1]
//        Write v_scale_ext[block_id, position, h, 0..n_groups-1]
//        Write v_xmin_ext [block_id, position, h, 0..n_groups-1]
//     6. block_id = slot_mapping[b] / BS   (BS=32 always for our config)
//        position = slot_mapping[b] % BS
//        If slot_mapping[b] < 0, use block_id = 0, position = 0
//        (inactive rows still write to slot 0; harmless under cache_seqlens
//         masking on the read side).
//
// Special cases:
//   - bf16_v_mode is handled by the writer; skip if active. The kernel
//     should NOT be called in bf16_v_mode (Python dispatch skips).
//   - group_size must divide D. We assume D=128, group_size=32 → 4 groups.
//
// TODO(phase6e): full implementation. The skeleton below returns an
// error so the integration point can be exercised without correctness
// risk before the kernel is written.

#include "fused_decode_write.h"
#include <cuda_runtime.h>

namespace int4_protected {

void fused_decode_write_v(
    torch::Tensor value,
    torch::Tensor slot_mapping,
    torch::Tensor kv_cache_v,
    torch::Tensor v_scale_ext,
    torch::Tensor v_xmin_ext,
    int64_t       group_size
) {
    TORCH_CHECK(value.is_cuda(),        "value must be CUDA");
    TORCH_CHECK(slot_mapping.is_cuda(), "slot_mapping must be CUDA");
    TORCH_CHECK(kv_cache_v.is_cuda(),   "kv_cache_v must be CUDA");
    TORCH_CHECK(value.dtype() == torch::kBFloat16, "value must be bf16");
    TORCH_CHECK(slot_mapping.dtype() == torch::kInt64, "slot_mapping must be int64");
    TORCH_CHECK(kv_cache_v.dtype() == torch::kUInt8, "kv_cache_v must be uint8");

    auto B = value.size(0);
    auto H = value.size(1);
    auto D = value.size(2);
    auto NB = kv_cache_v.size(0);
    auto BS = kv_cache_v.size(1);
    TORCH_CHECK(slot_mapping.size(0) == B, "slot_mapping shape mismatch");
    TORCH_CHECK(D % group_size == 0, "group_size must divide D");
    TORCH_CHECK(BS == 32, "Phase 6E currently assumes BS=32");

    TORCH_CHECK(false,
        "fused_decode_write_v: CUDA kernel body not yet implemented "
        "(Phase 6E Day 1 scaffold). The Python reference path produces "
        "byte-identical output and is verified by "
        "verify_phase6e_fused_byte_eq.py. To wire up the CUDA kernel, "
        "implement the kernel body following the spec at the top of "
        "this file and replace this TORCH_CHECK with the kernel launch.");
}

} // namespace int4_protected
