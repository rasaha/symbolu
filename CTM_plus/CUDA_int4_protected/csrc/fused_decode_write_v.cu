// Phase 6E — fused_decode_write_v
//
// V-side path: quantize bf16 V to int4 groups + write packed bytes to
// kv_cache + sidecars in one kernel launch.
//
// Reference contract: phase5b_4c_paged_writer.py
// _phase6e_fused_decode_write_python_ref (V section).
//
// Layout assumptions:
//   * D == 128, group_size == 32, n_groups == 4 (asserted in the wrapper).
//   * BS == 32 (asserted).
//   * value, kv_cache_v, v_scale_ext, v_xmin_ext all contiguous.
//
// Kernel layout:
//   Grid:  dim3(B, H)              -- one thread block per (batch, head)
//   Block: D threads (==128)       -- one thread per head-dim element
//
// Per thread block (b, h), per thread d:
//   1. Inactive-row safe-clamp: if slot_mapping[b] < 0, use slot 0.
//      Compute block_id, position from safe slot_mapping.
//   2. Load value[b, h, d] -> register float.
//   3. Per-group amax/amin via warp shuffle. group_size==32 aligns with
//      the warp size, so a single warp's lanes ARE one group; one
//      __shfl_xor_sync reduction tree per group.
//   4. scale = max((amax - amin) / 15.0f, 1e-8f).
//   5. q = clamp(round((v - amin) / scale), 0, 15).
//   6. Pack via __shfl_xor_sync(1): even-d threads write a single byte
//      containing q[d] in the low nibble and q[d+1] in the high nibble
//      to kv_cache_v[block_id, position, h, d/2].
//   7. Lane 0 of each warp (= one thread per group) writes scale and
//      v_min to v_scale_ext / v_xmin_ext for that group.

#include "fused_decode_write.h"

#include <ATen/cuda/CUDAContext.h>
#include <c10/cuda/CUDAException.h>
#include <cuda_runtime.h>
#include <cuda_bf16.h>
#include <cstdint>

namespace int4_protected {

namespace {

// Warp-wide max/min using xor butterfly. Assumes a full warp of 32
// threads participates (group_size == 32 → group lanes == warp lanes).
__device__ __forceinline__ float warp_reduce_max(float v) {
    #pragma unroll
    for (int offset = 16; offset > 0; offset >>= 1) {
        float partner = __shfl_xor_sync(0xffffffffu, v, offset, 32);
        v = fmaxf(v, partner);
    }
    return v;
}

__device__ __forceinline__ float warp_reduce_min(float v) {
    #pragma unroll
    for (int offset = 16; offset > 0; offset >>= 1) {
        float partner = __shfl_xor_sync(0xffffffffu, v, offset, 32);
        v = fminf(v, partner);
    }
    return v;
}

template <int BS_FIXED>
__global__ void fused_decode_write_v_kernel(
    const __nv_bfloat16* __restrict__ value,        // (B, H, D)
    const int64_t*       __restrict__ slot_mapping, // (B,)
    uint8_t*             __restrict__ kv_cache_v,   // (NB, BS, H, kv_last)
    __nv_bfloat16*       __restrict__ v_scale_ext,  // (NB, BS, H, n_groups)
    __nv_bfloat16*       __restrict__ v_xmin_ext,   // (NB, BS, H, n_groups)
    int B, int H, int D, int n_groups, int kv_last
) {
    const int b = blockIdx.x;
    const int h = blockIdx.y;
    const int d = threadIdx.x;
    if (d >= D) return;

    constexpr int GROUP_SIZE = 32;

    // Inactive-row safe slot: matches Python's torch.where(active_mask, sm, 0).
    const int64_t sm = slot_mapping[b];
    const int active = (sm >= 0);
    const int64_t safe_sm = active ? sm : (int64_t)0;
    const int block_id = (int)(safe_sm / BS_FIXED);
    const int position = (int)(safe_sm % BS_FIXED);

    // Load value[b, h, d] as float.
    const __nv_bfloat16* val_row = value + ((int64_t)b * H + h) * D;
    const float v_f = __bfloat162float(val_row[d]);

    // group_size == 32 and warp_size == 32, so each warp == one group.
    // The reduction returns the same value to every lane in the warp.
    const float v_max = warp_reduce_max(v_f);
    const float v_min = warp_reduce_min(v_f);

    float v_scale = (v_max - v_min) / 15.0f;
    if (v_scale < 1e-8f) v_scale = 1e-8f;

    // Quantize. PyTorch's .round() is half-to-even (banker's rounding);
    // rintf() matches in the default FP rounding mode (FE_TONEAREST).
    // roundf() is half-away-from-zero and would diverge from the
    // Python ref at exact half-integers — keep rintf for byte parity.
    float q_f = rintf((v_f - v_min) / v_scale);
    q_f = fmaxf(0.0f, fminf(15.0f, q_f));
    unsigned int q = (unsigned int)q_f;

    // Pack: byte = q[d] | (q[d+1] << 4). All pairs (2k, 2k+1) live in
    // the same warp because group_size aligns to warp size.
    // Stride between (h) rows in kv_cache_v is `kv_last` — typically D
    // (full-uint8 cache layout where packed bytes occupy the first D/2)
    // but the kernel also supports a pure-packed cache (kv_last == D/2).
    unsigned int partner_q = __shfl_xor_sync(0xffffffffu, q, 1, 32);
    if ((d & 1) == 0) {
        const uint8_t byte = (uint8_t)((q & 0x0Fu) | ((partner_q & 0x0Fu) << 4));
        const int64_t off = ((((int64_t)block_id * BS_FIXED + position) * H + h) * kv_last)
                            + (d >> 1);
        kv_cache_v[off] = byte;
    }

    // Lane 0 of each warp writes its group's scale + xmin sidecars.
    const int lane = d & 31;          // group_size==32 ⇒ lane == d % group_size
    if (lane == 0) {
        const int g = d / GROUP_SIZE; // group index (0..n_groups-1)
        const int64_t ext_off = ((((int64_t)block_id * BS_FIXED + position) * H + h) * n_groups)
                                + g;
        v_scale_ext[ext_off] = __float2bfloat16_rn(v_scale);
        v_xmin_ext[ext_off]  = __float2bfloat16_rn(v_min);
    }
}

} // anonymous namespace

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
    TORCH_CHECK(v_scale_ext.is_cuda(),  "v_scale_ext must be CUDA");
    TORCH_CHECK(v_xmin_ext.is_cuda(),   "v_xmin_ext must be CUDA");
    TORCH_CHECK(value.dtype() == torch::kBFloat16,       "value must be bf16");
    TORCH_CHECK(slot_mapping.dtype() == torch::kInt64,   "slot_mapping must be int64");
    TORCH_CHECK(kv_cache_v.dtype() == torch::kUInt8,     "kv_cache_v must be uint8");
    TORCH_CHECK(v_scale_ext.dtype() == torch::kBFloat16, "v_scale_ext must be bf16");
    TORCH_CHECK(v_xmin_ext.dtype() == torch::kBFloat16,  "v_xmin_ext must be bf16");

    TORCH_CHECK(value.is_contiguous(),       "value must be contiguous");
    TORCH_CHECK(kv_cache_v.is_contiguous(),  "kv_cache_v must be contiguous");
    TORCH_CHECK(v_scale_ext.is_contiguous(), "v_scale_ext must be contiguous");
    TORCH_CHECK(v_xmin_ext.is_contiguous(),  "v_xmin_ext must be contiguous");
    TORCH_CHECK(slot_mapping.is_contiguous(),"slot_mapping must be contiguous");

    const auto B  = value.size(0);
    const auto H  = value.size(1);
    const auto D  = value.size(2);
    const auto BS = kv_cache_v.size(1);
    TORCH_CHECK(slot_mapping.size(0) == B,   "slot_mapping shape mismatch");
    TORCH_CHECK(kv_cache_v.size(2) == H,     "kv_cache_v head dim mismatch");
    // kv_cache_v last dim must hold at least D/2 packed bytes per (block, pos, h).
    // Production vLLM allocates the int4_packed cache with last dim == D
    // (the bf16 backing area in the second half is unused after Phase 6C
    // but kept for layout uniformity). Either D/2 or D is accepted.
    TORCH_CHECK(kv_cache_v.size(3) >= D / 2,
                "kv_cache_v packed dim must be >= D/2 (got ",
                kv_cache_v.size(3), ", D/2=", D/2, ")");
    const int kv_last_v = (int)kv_cache_v.size(3);
    TORCH_CHECK(v_scale_ext.size(0) == kv_cache_v.size(0), "v_scale_ext NB mismatch");
    TORCH_CHECK(v_xmin_ext.size(0)  == kv_cache_v.size(0), "v_xmin_ext NB mismatch");

    TORCH_CHECK(BS == 32, "Phase 6E currently assumes BS=32");
    TORCH_CHECK(group_size == 32,
                "Phase 6E V kernel currently assumes group_size=32 "
                "to align with warp-shuffle reductions.");
    TORCH_CHECK(D % group_size == 0, "group_size must divide D");
    TORCH_CHECK(D % 2 == 0,          "D must be even (pack requires pairs)");
    TORCH_CHECK(D <= 1024,           "D must be <= 1024 (thread-block size limit)");
    const int n_groups = (int)(D / group_size);
    TORCH_CHECK(v_scale_ext.size(3) == n_groups,
                "v_scale_ext n_groups mismatch");
    TORCH_CHECK(v_xmin_ext.size(3)  == n_groups,
                "v_xmin_ext n_groups mismatch");

    if (B == 0) return;

    const dim3 grid((unsigned)B, (unsigned)H);
    const dim3 block((unsigned)D);

    auto stream = at::cuda::getCurrentCUDAStream();
    fused_decode_write_v_kernel<32><<<grid, block, 0, stream>>>(
        reinterpret_cast<const __nv_bfloat16*>(value.data_ptr<at::BFloat16>()),
        slot_mapping.data_ptr<int64_t>(),
        kv_cache_v.data_ptr<uint8_t>(),
        reinterpret_cast<__nv_bfloat16*>(v_scale_ext.data_ptr<at::BFloat16>()),
        reinterpret_cast<__nv_bfloat16*>(v_xmin_ext.data_ptr<at::BFloat16>()),
        (int)B, (int)H, (int)D, n_groups, kv_last_v
    );
    C10_CUDA_KERNEL_LAUNCH_CHECK();
}

} // namespace int4_protected
