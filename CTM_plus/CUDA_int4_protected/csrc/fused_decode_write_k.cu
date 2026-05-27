// Phase 6E — fused_decode_write_k
//
// K-side path: update the rolling K stage buffer, gather protected
// dims, and on block-fill commit packed int4 K + scale + xmin
// sidecars. Increments seq_pos_pool for active rows.
//
// Reference contract: phase5b_4c_paged_writer.py
// _phase6e_fused_decode_write_python_ref (K section).
//
// Layout assumptions:
//   * D == 128, BS == 32 (asserted in the wrapper).
//   * All tensors contiguous in their natural row-major layout.
//   * key:                  (B, H, D)              bf16
//   * slot_idx_t:           (B,)                   int64
//   * slot_mapping:         (B,)                   int64
//   * protected_d_per_head: (H, n_protect)         int64
//   * k_stage_pool:         (n_slots, BS, H, D)    bf16
//   * k_stage_block_id_pool:(n_slots,)             int64 (-1 sentinel)
//   * k_stage_count_pool:   (n_slots,)             int32
//   * seq_pos_pool:         (n_slots,)             int32
//   * kv_cache_k:           (NB, BS, H, D/2)       uint8
//   * k_scale_ext:          (NB, H, D)             bf16
//   * k_xmin_ext:           (NB, H, D)             bf16
//   * k_protect_ext:        (NB, BS, H, n_protect) bf16
//
// Kernel layout:
//   Grid:  dim3(B, H)              -- one thread block per (batch, head)
//   Block: D threads (==128)       -- one thread per head-dim element
//
// Per thread block (b, h), per thread d:
//   1. Resolve active / safe slot / block_id / position from slot_mapping.
//   2. slot_idx = slot_idx_t[b]; prior_block_id = k_stage_block_id_pool[slot_idx];
//      is_new_block = (block_id != prior_block_id).
//   3. col[BS] register array: for each row r in 0..BS,
//        v = is_new_block ? 0 : k_stage_pool[slot_idx, r, h, d]
//        if (r == position): v = key[b, h, d]
//        k_stage_pool[slot_idx, r, h, d] = v   (write back)
//        col[r] = v
//   4. Per-column (across BS rows) amax/amin -> x_max[d], x_min[d].
//   5. scale = max((x_max - x_min) / 15.0f, 1e-8f).
//   6. block_full = (position+1 == BS) && active.
//   7. If block_full:
//        For each row r:
//          q   = clamp(round((col[r] - x_min) / scale), 0, 15)
//          partner_q = __shfl_xor_sync(.., q, 1, 32)   (pair lane d ↔ d^1)
//          if (d even): kv_cache_k[block_id, r, h, d/2] = q | (partner_q << 4)
//        k_scale_ext[block_id, h, d] = scale (bf16)
//        k_xmin_ext [block_id, h, d] = x_min (bf16)
//   8. Protect side (per step, regardless of block_full): threads d in
//      [0, n_protect) gather key at protected_d_per_head[h, d] and
//      write to k_protect_ext[block_id, position, h, d].
//   9. Bookkeeping (only blockIdx.y == 0, threadIdx.x == 0):
//        if active: k_stage_block_id_pool[slot_idx] = block_id
//        k_stage_count_pool[slot_idx] =
//            active ? (block_full ? 0 : position+1) : prior count
//        if active: atomicAdd(&seq_pos_pool[slot_idx], 1)
//
// Race considerations:
//   * In production, slot_idx_t values are distinct across the batch
//     (each active seq has its own pool slot), so cross-(b) writes to
//     pool tensors don't alias.
//   * Across the H thread blocks for one (b), only blockIdx.y == 0
//     writes scalar bookkeeping (block_id, count). seq_pos uses
//     atomicAdd so an aliased slot_idx would still produce the correct
//     count (matching Python's index_add_).
//   * Within one (b, h) block, each thread d writes its own column of
//     k_stage_pool[slot, :, h, d] and kv_cache_k[block, :, h, d/2] — no
//     intra-block aliasing.

#include "fused_decode_write.h"

#include <ATen/cuda/CUDAContext.h>
#include <c10/cuda/CUDAException.h>
#include <cuda_runtime.h>
#include <cuda_bf16.h>
#include <cstdint>

namespace int4_protected {

namespace {

template <int BS_FIXED>
__global__ void fused_decode_write_k_kernel(
    const __nv_bfloat16* __restrict__ key,                       // (B, H, D)
    const int64_t*       __restrict__ slot_idx_t,                // (B,)
    const int64_t*       __restrict__ slot_mapping,              // (B,)
    const int64_t*       __restrict__ protected_d_per_head,      // (H, n_protect)
    __nv_bfloat16*       __restrict__ k_stage_pool,              // (n_slots, BS, H, D)
    int64_t*             __restrict__ k_stage_block_id_pool,     // (n_slots,)
    int32_t*             __restrict__ k_stage_count_pool,        // (n_slots,)
    int32_t*             __restrict__ seq_pos_pool,              // (n_slots,)
    uint8_t*             __restrict__ kv_cache_k,                // (NB, BS, H, D/2)
    __nv_bfloat16*       __restrict__ k_scale_ext,               // (NB, H, D)
    __nv_bfloat16*       __restrict__ k_xmin_ext,                // (NB, H, D)
    __nv_bfloat16*       __restrict__ k_protect_ext,             // (NB, BS, H, n_protect)
    int B, int H, int D, int n_protect
) {
    const int b = blockIdx.x;
    const int h = blockIdx.y;
    const int d = threadIdx.x;
    if (d >= D) return;

    const int half_D = D >> 1;

    // -------- 1. Resolve active / safe slot / block_id / position --------
    const int64_t sm = slot_mapping[b];
    const int active = (sm >= 0);
    const int64_t safe_sm = active ? sm : (int64_t)0;
    const int block_id = (int)(safe_sm / BS_FIXED);
    const int position = (int)(safe_sm % BS_FIXED);

    const int64_t slot_idx = slot_idx_t[b];

    // -------- 2. prior block id + is_new_block -----------------------------
    const int64_t prior_block_id = k_stage_block_id_pool[slot_idx];
    const int is_new_block = (block_id != (int)prior_block_id);

    // -------- 3. Update k_stage_pool, capture col[] in registers ---------
    // k_stage_pool layout: (n_slots, BS, H, D), row-major.
    // base index for (slot_idx, 0, h, d):
    const int64_t stage_base   = ((int64_t)slot_idx * BS_FIXED * H * D)
                               + ((int64_t)h * D)
                               + d;
    const int64_t stage_stride = (int64_t)H * D;   // step from row r to r+1

    const __nv_bfloat16* key_row = key + ((int64_t)b * H + h) * D;
    const float key_val = __bfloat162float(key_row[d]);

    float col[BS_FIXED];

    #pragma unroll
    for (int r = 0; r < BS_FIXED; ++r) {
        float v;
        if (is_new_block) {
            v = 0.0f;
        } else {
            v = __bfloat162float(k_stage_pool[stage_base + (int64_t)r * stage_stride]);
        }
        if (r == position) {
            v = key_val;
        }
        col[r] = v;
        k_stage_pool[stage_base + (int64_t)r * stage_stride] = __float2bfloat16_rn(v);
    }

    // -------- 4. Per-column amax/amin across BS rows --------------------
    float x_max = col[0];
    float x_min = col[0];
    #pragma unroll
    for (int r = 1; r < BS_FIXED; ++r) {
        x_max = fmaxf(x_max, col[r]);
        x_min = fminf(x_min, col[r]);
    }

    // -------- 5. scale --------------------------------------------------
    float scale = (x_max - x_min) / 15.0f;
    if (scale < 1e-8f) scale = 1e-8f;

    // -------- 6. block_full detection ----------------------------------
    const int block_full = (((position + 1) == BS_FIXED) && active);

    // -------- 7. Quantize + pack + write packed K (only on block_full) ---
    // block_full is a (b, h)-scalar (depends only on per-batch state),
    // so every thread in the block takes the same branch — the
    // __shfl_xor_sync calls inside are warp-uniform.
    if (block_full) {
        #pragma unroll
        for (int r = 0; r < BS_FIXED; ++r) {
            // rintf = half-to-even (banker's), matching PyTorch's .round().
            float q_f = rintf((col[r] - x_min) / scale);
            q_f = fmaxf(0.0f, fminf(15.0f, q_f));
            const unsigned int q = (unsigned int)q_f;
            const unsigned int partner_q = __shfl_xor_sync(0xffffffffu, q, 1, 32);
            if ((d & 1) == 0) {
                const uint8_t byte = (uint8_t)((q & 0x0Fu) | ((partner_q & 0x0Fu) << 4));
                const int64_t off = ((((int64_t)block_id * BS_FIXED + r) * H + h) * half_D)
                                    + (d >> 1);
                kv_cache_k[off] = byte;
            }
        }

        // -------- 7b. Scale / xmin sidecars on block_full ---------------
        const int64_t ext_off = (((int64_t)block_id * H) + h) * D + d;
        k_scale_ext[ext_off] = __float2bfloat16_rn(scale);
        k_xmin_ext [ext_off] = __float2bfloat16_rn(x_min);
    }

    // -------- 8. K protect gather + scatter (per step) -------------------
    // Threads d in [0, n_protect) read protected_d_per_head[h, d] and
    // write k_protect_ext[block_id, position, h, d] = key[b, h, d_idx].
    if (d < n_protect) {
        const int64_t pd_off = (int64_t)h * n_protect + d;
        const int64_t d_protect = protected_d_per_head[pd_off];
        // d_protect ∈ [0, D); from _build_protect_tables. Defensive bounds.
        if (d_protect >= 0 && d_protect < D) {
            const float kp = __bfloat162float(key_row[d_protect]);
            const int64_t kp_off =
                ((((int64_t)block_id * BS_FIXED + position) * H + h) * n_protect) + d;
            k_protect_ext[kp_off] = __float2bfloat16_rn(kp);
        }
    }

    // -------- 9. Bookkeeping — once per (b) on the (h=0, d=0) thread ----
    if (h == 0 && d == 0) {
        // k_stage_block_id_pool[slot_idx] = active ? block_id : prior
        if (active) {
            k_stage_block_id_pool[slot_idx] = (int64_t)block_id;
        }

        // k_stage_count_pool[slot_idx]:
        //   - active && block_full: 0
        //   - active && !block_full: position + 1
        //   - !active: keep current
        if (active) {
            k_stage_count_pool[slot_idx] = block_full ? 0 : (int32_t)(position + 1);
        }

        // seq_pos_pool.index_add_(0, slot_idx_t, active_mask.to(int32))
        // — atomic increment so aliased slots accumulate correctly.
        if (active) {
            atomicAdd(&seq_pos_pool[slot_idx], 1);
        }
    }
}

} // anonymous namespace

void fused_decode_write_k(
    torch::Tensor key,
    torch::Tensor slot_idx_t,
    torch::Tensor slot_mapping,
    torch::Tensor protect_mask,            // unused — gather uses protected_d_per_head
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
    (void)protect_mask;  // present for API symmetry; gather only needs protected_d_per_head.

    TORCH_CHECK(key.is_cuda(),                          "key must be CUDA");
    TORCH_CHECK(slot_idx_t.is_cuda(),                   "slot_idx_t must be CUDA");
    TORCH_CHECK(slot_mapping.is_cuda(),                 "slot_mapping must be CUDA");
    TORCH_CHECK(protected_d_per_head.is_cuda(),         "protected_d_per_head must be CUDA");
    TORCH_CHECK(k_stage_pool.is_cuda(),                 "k_stage_pool must be CUDA");
    TORCH_CHECK(k_stage_block_id_pool.is_cuda(),        "k_stage_block_id_pool must be CUDA");
    TORCH_CHECK(k_stage_count_pool.is_cuda(),           "k_stage_count_pool must be CUDA");
    TORCH_CHECK(seq_pos_pool.is_cuda(),                 "seq_pos_pool must be CUDA");
    TORCH_CHECK(kv_cache_k.is_cuda(),                   "kv_cache_k must be CUDA");
    TORCH_CHECK(k_scale_ext.is_cuda(),                  "k_scale_ext must be CUDA");
    TORCH_CHECK(k_xmin_ext.is_cuda(),                   "k_xmin_ext must be CUDA");
    TORCH_CHECK(k_protect_ext.is_cuda(),                "k_protect_ext must be CUDA");

    TORCH_CHECK(key.dtype()                  == torch::kBFloat16, "key must be bf16");
    TORCH_CHECK(slot_idx_t.dtype()           == torch::kInt64,    "slot_idx_t must be int64");
    TORCH_CHECK(slot_mapping.dtype()         == torch::kInt64,    "slot_mapping must be int64");
    TORCH_CHECK(protected_d_per_head.dtype() == torch::kInt64,    "protected_d_per_head must be int64");
    TORCH_CHECK(k_stage_pool.dtype()         == torch::kBFloat16, "k_stage_pool must be bf16");
    TORCH_CHECK(k_stage_block_id_pool.dtype()== torch::kInt64,    "k_stage_block_id_pool must be int64");
    TORCH_CHECK(k_stage_count_pool.dtype()   == torch::kInt32,    "k_stage_count_pool must be int32");
    TORCH_CHECK(seq_pos_pool.dtype()         == torch::kInt32,    "seq_pos_pool must be int32");
    TORCH_CHECK(kv_cache_k.dtype()           == torch::kUInt8,    "kv_cache_k must be uint8");
    TORCH_CHECK(k_scale_ext.dtype()          == torch::kBFloat16, "k_scale_ext must be bf16");
    TORCH_CHECK(k_xmin_ext.dtype()           == torch::kBFloat16, "k_xmin_ext must be bf16");
    TORCH_CHECK(k_protect_ext.dtype()        == torch::kBFloat16, "k_protect_ext must be bf16");

    TORCH_CHECK(key.is_contiguous(),                    "key must be contiguous");
    TORCH_CHECK(slot_idx_t.is_contiguous(),             "slot_idx_t must be contiguous");
    TORCH_CHECK(slot_mapping.is_contiguous(),           "slot_mapping must be contiguous");
    TORCH_CHECK(protected_d_per_head.is_contiguous(),   "protected_d_per_head must be contiguous");
    TORCH_CHECK(k_stage_pool.is_contiguous(),           "k_stage_pool must be contiguous");
    TORCH_CHECK(k_stage_block_id_pool.is_contiguous(),  "k_stage_block_id_pool must be contiguous");
    TORCH_CHECK(k_stage_count_pool.is_contiguous(),     "k_stage_count_pool must be contiguous");
    TORCH_CHECK(seq_pos_pool.is_contiguous(),           "seq_pos_pool must be contiguous");
    TORCH_CHECK(kv_cache_k.is_contiguous(),             "kv_cache_k must be contiguous");
    TORCH_CHECK(k_scale_ext.is_contiguous(),            "k_scale_ext must be contiguous");
    TORCH_CHECK(k_xmin_ext.is_contiguous(),             "k_xmin_ext must be contiguous");
    TORCH_CHECK(k_protect_ext.is_contiguous(),          "k_protect_ext must be contiguous");

    const auto B  = key.size(0);
    const auto H  = key.size(1);
    const auto D  = key.size(2);
    const auto BS = k_stage_pool.size(1);
    const auto n_protect = protected_d_per_head.size(1);
    const auto n_slots   = k_stage_pool.size(0);
    const auto NB        = kv_cache_k.size(0);

    TORCH_CHECK(slot_idx_t.size(0)             == B,        "slot_idx_t shape mismatch");
    TORCH_CHECK(slot_mapping.size(0)           == B,        "slot_mapping shape mismatch");
    TORCH_CHECK(k_stage_pool.size(0)           == n_slots,  "k_stage_pool n_slots mismatch");
    TORCH_CHECK(k_stage_pool.size(2)           == H,        "k_stage_pool head mismatch");
    TORCH_CHECK(k_stage_pool.size(3)           == D,        "k_stage_pool D mismatch");
    TORCH_CHECK(k_stage_block_id_pool.size(0)  == n_slots,  "k_stage_block_id_pool size mismatch");
    TORCH_CHECK(k_stage_count_pool.size(0)     == n_slots,  "k_stage_count_pool size mismatch");
    TORCH_CHECK(seq_pos_pool.size(0)           == n_slots,  "seq_pos_pool size mismatch");
    TORCH_CHECK(protected_d_per_head.size(0)   == H,        "protected_d_per_head H mismatch");
    TORCH_CHECK(kv_cache_k.size(1)             == BS,       "kv_cache_k BS mismatch");
    TORCH_CHECK(kv_cache_k.size(2)             == H,        "kv_cache_k head mismatch");
    TORCH_CHECK(kv_cache_k.size(3)             == D / 2,    "kv_cache_k packed dim mismatch");
    TORCH_CHECK(k_scale_ext.size(0)            == NB,       "k_scale_ext NB mismatch");
    TORCH_CHECK(k_scale_ext.size(1)            == H,        "k_scale_ext H mismatch");
    TORCH_CHECK(k_scale_ext.size(2)            == D,        "k_scale_ext D mismatch");
    TORCH_CHECK(k_xmin_ext.size(0)             == NB,       "k_xmin_ext NB mismatch");
    TORCH_CHECK(k_xmin_ext.size(1)             == H,        "k_xmin_ext H mismatch");
    TORCH_CHECK(k_xmin_ext.size(2)             == D,        "k_xmin_ext D mismatch");
    TORCH_CHECK(k_protect_ext.size(0)          == NB,       "k_protect_ext NB mismatch");
    TORCH_CHECK(k_protect_ext.size(1)          == BS,       "k_protect_ext BS mismatch");
    TORCH_CHECK(k_protect_ext.size(2)          == H,        "k_protect_ext H mismatch");
    TORCH_CHECK(k_protect_ext.size(3)          == n_protect,"k_protect_ext n_protect mismatch");

    TORCH_CHECK(BS == 32, "Phase 6E currently assumes BS=32");
    TORCH_CHECK(D % 2 == 0, "D must be even (pack requires pairs)");
    TORCH_CHECK(D <= 1024,  "D must be <= 1024 (thread-block size limit)");

    if (B == 0) return;

    const dim3 grid((unsigned)B, (unsigned)H);
    const dim3 block((unsigned)D);

    auto stream = at::cuda::getCurrentCUDAStream();
    fused_decode_write_k_kernel<32><<<grid, block, 0, stream>>>(
        reinterpret_cast<const __nv_bfloat16*>(key.data_ptr<at::BFloat16>()),
        slot_idx_t.data_ptr<int64_t>(),
        slot_mapping.data_ptr<int64_t>(),
        protected_d_per_head.data_ptr<int64_t>(),
        reinterpret_cast<__nv_bfloat16*>(k_stage_pool.data_ptr<at::BFloat16>()),
        k_stage_block_id_pool.data_ptr<int64_t>(),
        k_stage_count_pool.data_ptr<int32_t>(),
        seq_pos_pool.data_ptr<int32_t>(),
        kv_cache_k.data_ptr<uint8_t>(),
        reinterpret_cast<__nv_bfloat16*>(k_scale_ext.data_ptr<at::BFloat16>()),
        reinterpret_cast<__nv_bfloat16*>(k_xmin_ext.data_ptr<at::BFloat16>()),
        reinterpret_cast<__nv_bfloat16*>(k_protect_ext.data_ptr<at::BFloat16>()),
        (int)B, (int)H, (int)D, (int)n_protect
    );
    C10_CUDA_KERNEL_LAUNCH_CHECK();
}

} // namespace int4_protected
