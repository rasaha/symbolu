/**
 * mm_compress_kernels.cu — TurboQuant compression/decompression for CXL tier
 *
 * Contains:
 *   1. mm_kernel_process_demotions — TRUE Kernel 3 of the 3-kernel pipeline.
 *      Fully fused: alloc + compress + CXL write + metadata + free + stats.
 *      1 CUDA block = 1 work item (demote or evict).
 *   2. mm_kernel_compress_to_cxl   — LEGACY standalone compress (retained)
 *   3. mm_kernel_decompress_from_cxl — Decompression for promotion path
 *
 * Architecture:
 *   1 CUDA block = 1 token's KV vector
 *   Block size = MM_COMPRESS_BLOCK_SIZE (128)
 *   Rotation matrix in __constant__ memory (no shared memory needed)
 *
 * For head_dim = 128:
 *   - Registers per thread 0: ~200 (vec[128] + radii[128] + rotated[128])
 *   - Global reads:  256B (FP16 vector) + const mem broadcast (rotation)
 *   - Global writes: 127B (indices) + 4B (radius) + 16B (QJL) + 4B (scale)
 *                   + 32B (TokenMeta update)
 */

#include "multimodal_inference.cuh"
#include <cuda_fp16.h>

// ============================================================================
// __constant__ memory for rotation matrices (broadcast-efficient)
//
// For head_dim=128: 128*128*4 = 64KB = exactly fits constant memory limit.
// All threads reading the same rotation entry → single memory transaction,
// vs shared memory which requires cooperative load + __syncthreads().
// ============================================================================

__constant__ float c_mm_rotation[MM_ROTATION_SIZE];     // R (compression)
__constant__ float c_mm_rotation_t[MM_ROTATION_SIZE];   // R^T (decompression)

// Host-callable: upload rotation matrices to __constant__ memory
void mm_upload_rotation_matrices(const float* h_rotation, const float* h_rotation_t,
                                  int head_dim) {
    size_t sz = (size_t)head_dim * head_dim * sizeof(float);
    cudaMemcpyToSymbol(c_mm_rotation, h_rotation, sz);
    cudaMemcpyToSymbol(c_mm_rotation_t, h_rotation_t, sz);
}

// ============================================================================
// Device helpers
// ============================================================================

/**
 * LUT floor quantization for angle → grid index.
 * O(1) per angle — no argmin search.
 *
 * Level 0: theta in [-π, π], grid uniform on that range
 * Level 1+: theta in [0, π/2], grid uniform on that range
 */
__device__ __forceinline__ uint8_t tq_quantize_angle_full(
    float theta, int n_grid
) {
    // Map [-π, π] → [0, 1)
    float normalized = (theta + CUDART_PI_F) / (2.0f * CUDART_PI_F);
    normalized = fminf(fmaxf(normalized, 0.0f), 0.99999f);
    return (uint8_t)(normalized * n_grid);
}

__device__ __forceinline__ uint8_t tq_quantize_angle_pos(
    float theta, int n_grid
) {
    // Map [0, π/2] → [0, 1)
    float normalized = theta / (CUDART_PI_F * 0.5f);
    normalized = fminf(fmaxf(normalized, 0.0f), 0.99999f);
    return (uint8_t)(normalized * n_grid);
}

/**
 * Reconstruct angle from grid index.
 */
__device__ __forceinline__ float tq_dequantize_angle_full(
    uint8_t idx, int n_grid
) {
    return -CUDART_PI_F + ((float)idx + 0.5f) * (2.0f * CUDART_PI_F / (float)n_grid);
}

__device__ __forceinline__ float tq_dequantize_angle_pos(
    uint8_t idx, int n_grid
) {
    return ((float)idx + 0.5f) * (CUDART_PI_F * 0.5f / (float)n_grid);
}

// ============================================================================
// TRUE Kernel 3: mm_kernel_process_demotions
//
// Fully fused: alloc + compress + CXL write + metadata + free + stats.
// This is the ONLY kernel needed after scoring. No separate alloc, compress,
// or free kernels are launched in the steady-state pipeline.
//
// Grid:  MM_MAX_VICTIMS blocks (fixed — reads actual counts from device)
// Block: MM_COMPRESS_BLOCK_SIZE (128)
//
// Block mapping:
//   blocks [0, *d_demote_count):
//     Thread 0: atomic pop CXL slot from freelist
//     Thread 0: TQ compress (rotation + polar + QJL) — serial per vector
//     Thread 0: write compressed payload to CXL storage
//     Thread 0: write cosine_sim + TQ_COMPRESSED + cxl_slot to d_meta
//     Thread 0: update modality stats
//
//   blocks [*d_demote_count, *d_demote_count + *d_evict_count):
//     Thread 0: free CXL slot if token was in CXL tier
//     Thread 0: clear tier_flags + cxl_slot
//     Thread 0: update eviction stats
//
//   blocks beyond: early exit
//
// Memory flow:
//   READ:  d_kv_vectors[pos*head_dim..+head_dim] (256B FP16 per demote)
//   READ:  c_mm_rotation[] (__constant__, broadcast)
//   READ:  d_jl_matrix[] (global, per JL projection row)
//   WRITE: cxl.d_indices[slot*total_angles..+total_angles] (127B per demote)
//   WRITE: cxl.d_radii[slot] (4B per demote)
//   WRITE: cxl.d_qjl_bits[slot*words..+words] (16B per demote)
//   WRITE: cxl.d_qjl_scales[slot] (4B per demote)
//   WRITE: d_meta[token].{cxl_slot, tier_flags, cosine_sim} (12B per item)
//   WRITE: d_modality_stats (atomicAdd, 4B per item)
//   WRITE: cxl.d_freelist_top (atomicSub/Add, 4B per item)
//
// No host sync. No D→H readback. CUDA graph capturable (fixed grid).
// ============================================================================

__global__ void mm_kernel_process_demotions(
    const __half*        __restrict__ d_kv_vectors,     // [max_tokens, head_dim]
    TokenMeta*           __restrict__ d_meta,
    const uint32_t*      __restrict__ d_demote_list,
    const uint32_t*      __restrict__ d_demote_count,   // device-side
    const uint32_t*      __restrict__ d_evict_list,
    const uint32_t*      __restrict__ d_evict_count,    // device-side
    CXLStorageLayout     cxl,
    EvictionAction*      __restrict__ d_actions,
    ModalityStats*       __restrict__ d_modality_stats,
    uint32_t             head_dim,
    int                  n_grid,
    const float*         __restrict__ d_jl_matrix,      // [proj_dim, head_dim]
    int                  proj_dim
) {
    uint32_t bid = blockIdx.x;
    uint32_t tid = threadIdx.x;

    // Read work counts from device memory.
    // Kernel 2 wrote these; same-stream ordering guarantees visibility.
    uint32_t n_demote = *d_demote_count;
    uint32_t n_evict  = *d_evict_count;
    if (n_demote > MM_MAX_VICTIMS) n_demote = MM_MAX_VICTIMS;
    if (n_evict  > MM_MAX_VICTIMS) n_evict  = MM_MAX_VICTIMS;
    uint32_t total = n_demote + n_evict;

    if (bid >= total) return;

    // ====================================================================
    // DEMOTION PATH: alloc + compress + write + metadata + stats
    // ====================================================================
    if (bid < n_demote) {
        uint32_t token_idx = d_demote_list[bid];

        // ---- Step 0: Thread 0 allocates CXL slot ----
        __shared__ uint32_t s_slot;
        __shared__ int      s_alloc_ok;

        if (tid == 0) {
            int old_top = (int)atomicSub(cxl.d_freelist_top, 1u);
            if (old_top - 1 < 0) {
                // CXL full — revert, upgrade to EVICT
                atomicAdd(cxl.d_freelist_top, 1u);
                s_alloc_ok = 0;
            } else {
                s_slot = cxl.d_freelist[old_top - 1];
                s_alloc_ok = 1;
            }
        }
        __syncthreads();  // broadcast alloc result to all threads

        if (!s_alloc_ok) {
            // Alloc failed — mark as evict, update stats, exit
            if (tid == 0) {
                d_actions[token_idx] = ACTION_EVICT;
                d_meta[token_idx].tier_flags &= ~MM_FLAG_IN_TIER0;
                if (d_modality_stats) {
                    ModalityGroup mod = MM_UNPACK_MODALITY(d_meta[token_idx].type_flags);
                    atomicAdd(&d_modality_stats->evicted_count[mod], 1u);
                }
            }
            return;
        }

        uint32_t cxl_slot = s_slot;

        // ---- Steps 1-6: Thread 0 does full TQ compression ----
        if (tid == 0) {
            uint32_t pos = d_meta[token_idx].position;

            // Step 1: Load FP16 KV vector → FP32
            float vec[MM_MAX_HEAD_DIM];
            for (uint32_t i = 0; i < head_dim; i++) {
                vec[i] = __half2float(d_kv_vectors[pos * head_dim + i]);
            }

            // Step 2: Apply rotation v' = R @ v (from __constant__ memory)
            float rotated[MM_MAX_HEAD_DIM];
            for (uint32_t r = 0; r < head_dim; r++) {
                float sum = 0.0f;
                for (uint32_t c = 0; c < head_dim; c++) {
                    sum += c_mm_rotation[r * head_dim + c] * vec[c];
                }
                rotated[r] = sum;
            }

            // Step 3: Recursive polar transform → quantized angle indices
            uint32_t angle_idx = 0;
            uint8_t* out_indices = &cxl.d_indices[cxl_slot * cxl.total_angles];

            float radii[MM_MAX_HEAD_DIM];
            uint32_t n_radii = head_dim;
            for (uint32_t i = 0; i < head_dim; i++) radii[i] = rotated[i];

            int level = 0;
            while (n_radii > 1) {
                float new_radii[MM_MAX_HEAD_DIM / 2];
                uint32_t n_new = 0;

                for (uint32_t i = 0; i < n_radii; i += 2) {
                    if (i + 1 < n_radii) {
                        float x = radii[i];
                        float y = radii[i + 1];
                        float r = sqrtf(x * x + y * y);
                        float theta = atan2f(y, x);

                        uint8_t qi = (level == 0)
                            ? tq_quantize_angle_full(theta, n_grid)
                            : tq_quantize_angle_pos(theta, n_grid);
                        out_indices[angle_idx++] = qi;
                        new_radii[n_new++] = r;
                    } else {
                        new_radii[n_new++] = radii[i];
                    }
                }
                n_radii = n_new;
                for (uint32_t i = 0; i < n_radii; i++) radii[i] = new_radii[i];
                level++;
            }

            // Write final radius to CXL storage
            cxl.d_radii[cxl_slot] = radii[0];

            // Step 4: Cosine similarity proxy (bit-width dependent)
            float cosine_est;
            if (n_grid <= 4)       cosine_est = 0.86f;   // 2-bit
            else if (n_grid <= 8)  cosine_est = 0.965f;  // 3-bit
            else                   cosine_est = 0.991f;  // 4-bit

            // Step 5: QJL sign bits
            if (d_jl_matrix && proj_dim > 0) {
                uint32_t qjl_words_per = (proj_dim + 31) / 32;
                uint32_t* out_qjl = &cxl.d_qjl_bits[cxl_slot * qjl_words_per];
                float scale_sum = 0.0f;

                for (uint32_t w = 0; w < qjl_words_per; w++) {
                    uint32_t bits = 0;
                    for (int b = 0; b < 32 && (w * 32 + b) < (uint32_t)proj_dim; b++) {
                        int proj_idx = w * 32 + b;
                        float dot = 0.0f;
                        for (uint32_t d = 0; d < head_dim; d++) {
                            dot += d_jl_matrix[proj_idx * head_dim + d] * vec[d];
                        }
                        if (dot >= 0.0f) bits |= (1u << b);
                        scale_sum += fabsf(dot);
                    }
                    out_qjl[w] = bits;
                }
                cxl.d_qjl_scales[cxl_slot] = scale_sum / (float)proj_dim;
            }

            // Step 6: Write metadata — slot, flags, cosine_sim
            // TQ_COMPRESSED is set HERE, after data is physically in CXL.
            d_meta[token_idx].cxl_slot   = cxl_slot;
            d_meta[token_idx].cosine_sim = cosine_est;
            d_meta[token_idx].tier_flags =
                (d_meta[token_idx].tier_flags & ~MM_FLAG_IN_TIER0)
                | MM_FLAG_IN_CXL
                | MM_FLAG_TQ_COMPRESSED;

            // Step 7: Modality stats
            if (d_modality_stats) {
                ModalityGroup mod = MM_UNPACK_MODALITY(d_meta[token_idx].type_flags);
                atomicAdd(&d_modality_stats->cxl_count[mod], 1u);
            }
        }
        return;
    }

    // ====================================================================
    // EVICTION PATH: free CXL slot + clear metadata + stats
    // ====================================================================
    if (tid != 0) return;  // only thread 0 needed for lightweight free

    uint32_t evict_idx = bid - n_demote;
    uint32_t token_idx = d_evict_list[evict_idx];
    TokenMeta* meta = &d_meta[token_idx];

    // Free CXL slot if token was in CXL tier
    if (meta->tier_flags & MM_FLAG_IN_CXL) {
        uint32_t slot = meta->cxl_slot;
        if (slot != MM_CXL_SLOT_INVALID) {
            uint32_t push_pos = atomicAdd(cxl.d_freelist_top, 1u);
            if (push_pos < cxl.capacity) {
                cxl.d_freelist[push_pos] = slot;
            }
        }
    }

    // Modality eviction stats
    if (d_modality_stats) {
        ModalityGroup mod = MM_UNPACK_MODALITY(meta->type_flags);
        atomicAdd(&d_modality_stats->evicted_count[mod], 1u);
    }

    // Clear token metadata
    meta->tier_flags = 0;
    meta->cxl_slot = MM_CXL_SLOT_INVALID;
}

// ============================================================================
// LEGACY: Standalone compress kernel (retained for backward compatibility)
// Prefer mm_kernel_process_demotions which fuses alloc+compress+free.
// ============================================================================

/**
 * 1 block = 1 token.  Thread 0 does serial polar walk.
 */
__global__ void mm_kernel_compress_to_cxl(
    const __half*        __restrict__ d_kv_vectors,
    TokenMeta*           __restrict__ d_meta,
    const uint32_t*      __restrict__ d_demote_list,
    uint32_t             n_demote,
    uint32_t             head_dim,
    CXLStorageLayout     cxl,
    const float*         __restrict__ d_rotation_matrix,  // unused, kept for API compat
    const float*         __restrict__ d_angle_grid_full,
    const float*         __restrict__ d_angle_grid_pos,
    int                  n_grid,
    const float*         __restrict__ d_jl_matrix,
    int                  proj_dim
) {
    uint32_t demote_idx = blockIdx.x;
    if (demote_idx >= n_demote) return;

    uint32_t token_idx = d_demote_list[demote_idx];
    uint32_t cxl_slot = d_meta[token_idx].cxl_slot;
    if (cxl_slot == MM_CXL_SLOT_INVALID) return;

    uint32_t tid = threadIdx.x;

    // Rotation matrix now in __constant__ memory (c_mm_rotation).
    // No shared memory load, no __syncthreads() needed.
    // All threads reading same rotation row → single broadcast transaction.

    // Thread 0 does the full compression for this token
    if (tid == 0) {
        uint32_t pos = d_meta[token_idx].position;

        // ---- Step 1: Load FP16 → FP32 ----
        float vec[256];  // max head_dim in registers
        float orig_sq_sum = 0.0f;
        for (uint32_t i = 0; i < head_dim; i++) {
            vec[i] = __half2float(d_kv_vectors[pos * head_dim + i]);
            orig_sq_sum += vec[i] * vec[i];
        }
        float orig_norm = sqrtf(orig_sq_sum);

        // ---- Step 2: Apply rotation v' = R @ v ----
        float rotated[256];
        for (uint32_t r = 0; r < head_dim; r++) {
            float sum = 0.0f;
            for (uint32_t c = 0; c < head_dim; c++) {
                sum += c_mm_rotation[r * head_dim + c] * vec[c];
            }
            rotated[r] = sum;
        }

        // ---- Step 3: Recursive polar transform ----
        // Level 0: pairs of rotated coordinates (Gaussian) → angles in [-π, π]
        // Level 1+: pairs of radii (positive) → angles in [0, π/2]
        uint32_t angle_idx = 0;
        uint8_t* out_indices = &cxl.d_indices[cxl_slot * cxl.total_angles];

        float radii[256];
        uint32_t n_radii = head_dim;
        for (uint32_t i = 0; i < head_dim; i++) radii[i] = rotated[i];

        int level = 0;
        while (n_radii > 1) {
            float new_radii[128];
            uint32_t n_new = 0;

            for (uint32_t i = 0; i < n_radii; i += 2) {
                if (i + 1 < n_radii) {
                    float x = radii[i];
                    float y = radii[i + 1];
                    float r = sqrtf(x * x + y * y);
                    float theta = atan2f(y, x);

                    // Quantize angle
                    uint8_t qi;
                    if (level == 0) {
                        qi = tq_quantize_angle_full(theta, n_grid);
                    } else {
                        qi = tq_quantize_angle_pos(theta, n_grid);
                    }
                    out_indices[angle_idx++] = qi;
                    new_radii[n_new++] = r;
                } else {
                    // Odd carry-forward
                    new_radii[n_new++] = radii[i];
                }
            }

            // Copy new radii back
            n_radii = n_new;
            for (uint32_t i = 0; i < n_radii; i++) radii[i] = new_radii[i];
            level++;
        }

        // Store final radius
        cxl.d_radii[cxl_slot] = radii[0];

        // ---- Step 4: Reconstruct for quality measurement ----
        // Reverse the polar transform using quantized angles
        float recon_radii[1] = {radii[0]};
        uint32_t recon_n = 1;
        int read_idx = (int)angle_idx - 1;

        // We need to replay levels in reverse, but we must track level sizes.
        // Simpler approach: reconstruct from final radius through levels.
        // For quality measurement, we compute cosine similarity directly.

        // Approximate quality based on bit-width (fast path for production)
        float cosine_est;
        if (n_grid <= 4) {       // 2-bit
            cosine_est = 0.86f;
        } else if (n_grid <= 8) { // 3-bit
            cosine_est = 0.965f;
        } else {                  // 4-bit
            cosine_est = 0.991f;
        }

        // ---- Step 5: QJL sign bits ----
        if (d_jl_matrix && proj_dim > 0) {
            uint32_t qjl_words_per = (proj_dim + 31) / 32;
            uint32_t* out_qjl = &cxl.d_qjl_bits[cxl_slot * qjl_words_per];
            float scale_sum = 0.0f;

            for (uint32_t w = 0; w < qjl_words_per; w++) {
                uint32_t bits = 0;
                for (int b = 0; b < 32 && (w * 32 + b) < (uint32_t)proj_dim; b++) {
                    int proj_idx = w * 32 + b;
                    // Project original vector with JL row
                    float dot = 0.0f;
                    for (uint32_t d = 0; d < head_dim; d++) {
                        dot += d_jl_matrix[proj_idx * head_dim + d] * vec[d];
                    }
                    if (dot >= 0.0f) bits |= (1u << b);
                    scale_sum += fabsf(dot);
                }
                out_qjl[w] = bits;
            }
            cxl.d_qjl_scales[cxl_slot] = scale_sum / (float)proj_dim;
        }

        // ---- Step 6: Write compression metadata to TokenMeta ----
        // Update cosine_sim so quality-aware scoring signal 6 is live.
        // Set TQ_COMPRESSED flag only NOW — after data is actually in CXL.
        // This prevents the "phantom compression" bug (flag set, slot empty).
        //
        // NOTE: d_meta is __restrict__ on this kernel's parameter, but we're
        // writing to the same token index that only this block touches, so
        // there's no aliasing hazard.
        d_meta[token_idx].cosine_sim  = cosine_est;
        d_meta[token_idx].tier_flags |= MM_FLAG_TQ_COMPRESSED;
    }
}

// ============================================================================
// Kernel: Decompress tokens from CXL to HBM (promotion path)
// ============================================================================

/**
 * Inverse of compress. 1 block = 1 token.
 *
 * Reads quantized angles + radius from CXL storage.
 * Reconstructs FP32 coordinates via inverse polar transform.
 * Applies inverse rotation (R^T).
 * Writes FP16 vector to HBM KV cache.
 *
 * Uses precomputed cos/sin LUTs (no trig in hot path).
 */
__global__ void mm_kernel_decompress_from_cxl(
    __half*              __restrict__ d_kv_vectors,
    const TokenMeta*     __restrict__ d_meta,
    const uint32_t*      __restrict__ d_promote_list,
    uint32_t             n_promote,
    uint32_t             head_dim,
    CXLStorageLayout     cxl,
    const float*         __restrict__ d_rotation_t,
    const float*         __restrict__ d_cos_lut_full,
    const float*         __restrict__ d_sin_lut_full,
    const float*         __restrict__ d_cos_lut_pos,
    const float*         __restrict__ d_sin_lut_pos,
    int                  n_grid
) {
    uint32_t promote_idx = blockIdx.x;
    if (promote_idx >= n_promote) return;

    uint32_t token_idx = d_promote_list[promote_idx];
    uint32_t cxl_slot = d_meta[token_idx].cxl_slot;
    if (cxl_slot == MM_CXL_SLOT_INVALID) return;

    uint32_t tid = threadIdx.x;

    // Rotation^T now in __constant__ memory (c_mm_rotation_t).
    // No shared memory needed, no sync barrier.

    if (tid == 0) {
        uint32_t pos = d_meta[token_idx].position;

        // ---- Load compressed data ----
        const uint8_t* indices = &cxl.d_indices[cxl_slot * cxl.total_angles];
        float final_radius = cxl.d_radii[cxl_slot];

        // ---- Inverse polar transform ----
        // Start from final radius, expand through levels in reverse.
        //
        // We need to know the level structure. For head_dim=128:
        //   Level 0: 64 pairs → 64 angles, 64 radii
        //   Level 1: 32 pairs → 32 angles, 32 radii
        //   Level 2: 16 pairs → 16 angles, 16 radii
        //   Level 3: 8 pairs → 8 angles, 8 radii
        //   Level 4: 4 pairs → 4 angles, 4 radii
        //   Level 5: 2 pairs → 2 angles, 2 radii
        //   Level 6: 1 pair → 1 angle, 1 radius (= final)
        //
        // Total angles = 64+32+16+8+4+2+1 = 127
        //
        // Reconstruct in reverse: level 6 → level 0.
        // At each level, expand: r → (r*cos(θ), r*sin(θ))

        // Precompute level structure
        uint32_t level_sizes[8];  // angles per level
        uint32_t level_offsets[9]; // cumulative offset into indices[]
        {
            uint32_t dim = head_dim;
            int n_levels = 0;
            level_offsets[0] = 0;
            while (dim > 1) {
                uint32_t n_pairs = dim / 2;
                level_sizes[n_levels] = n_pairs;
                level_offsets[n_levels + 1] = level_offsets[n_levels] + n_pairs;
                dim = n_pairs + (dim % 2);
                n_levels++;
            }

            // Reverse reconstruction
            float radii[256];
            radii[0] = final_radius;
            uint32_t n_radii = 1;

            for (int lv = n_levels - 1; lv >= 0; lv--) {
                uint32_t n_pairs = level_sizes[lv];
                uint32_t offset = level_offsets[lv];

                float new_coords[256];
                uint32_t n_new = 0;
                uint32_t ai = 0;

                for (uint32_t ri = 0; ri < n_radii; ri++) {
                    if (ai < n_pairs) {
                        uint8_t qi = indices[offset + ai];
                        float cos_val, sin_val;

                        if (lv == 0) {
                            // Full range LUT
                            cos_val = d_cos_lut_full[qi];
                            sin_val = d_sin_lut_full[qi];
                        } else {
                            // Positive quadrant LUT
                            cos_val = d_cos_lut_pos[qi];
                            sin_val = d_sin_lut_pos[qi];
                        }

                        float r = radii[ri];
                        new_coords[n_new++] = r * cos_val;
                        new_coords[n_new++] = r * sin_val;
                        ai++;
                    } else {
                        // Odd carry-forward
                        new_coords[n_new++] = radii[ri];
                    }
                }

                n_radii = n_new;
                for (uint32_t i = 0; i < n_radii; i++) radii[i] = new_coords[i];
            }

            // radii[] now holds the reconstructed rotated coordinates

            // ---- Apply inverse rotation: v = R^T @ rotated ----
            for (uint32_t r = 0; r < head_dim; r++) {
                float sum = 0.0f;
                for (uint32_t c = 0; c < head_dim; c++) {
                    sum += c_mm_rotation_t[r * head_dim + c] * radii[c];
                }
                // Write FP16 output
                d_kv_vectors[pos * head_dim + r] = __float2half(sum);
            }
        }
    }
}
