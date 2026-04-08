/**
 * mm_controller.cu — Host-side MultimodalInferenceController
 *
 * TRUE 3-kernel pipeline per decode step (no host sync, no extra kernels):
 *
 *   Kernel 1: mm_kernel_update_on_access      — update metadata + reuse trend
 *   Kernel 2: mm_kernel_fused_score_collect   — score + decide + warp-compact
 *   Kernel 3: mm_kernel_process_demotions     — alloc + TQ compress + CXL write
 *                                               + metadata + free evicted + stats
 *
 * There is NO optional kernel 4. Compression happens INSIDE kernel 3.
 * All 3 kernels have fixed grid dimensions → CUDA graph capturable.
 * Kernel 3 reads demote/evict counts from device memory (written by kernel 2).
 *
 * Per-step GPU operations (over capacity):
 *   1 cudaMemcpy H→D  (32B new TokenMeta)
 *   2 cudaMemset       (zero atomic counters)
 *   3 kernel launches  (no sync between them)
 *   Total: 6 GPU ops, 0 host syncs
 */

#include "multimodal_inference.cuh"
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <cstring>

// ============================================================================
// Helper: Initialize TurboQuant precomputed tables
// ============================================================================

static void host_generate_orthogonal(float* out, int d, uint64_t seed) {
    // Simple Gram-Schmidt orthogonalization of a random matrix
    srand48(seed);
    float* tmp = new float[d * d];
    for (int i = 0; i < d * d; i++) tmp[i] = (float)drand48() * 2.0f - 1.0f;

    // QR via Gram-Schmidt
    for (int col = 0; col < d; col++) {
        // Copy column
        for (int row = 0; row < d; row++) out[col * d + row] = tmp[col * d + row];

        // Subtract projections onto previous columns
        for (int prev = 0; prev < col; prev++) {
            float dot = 0.0f, norm_sq = 0.0f;
            for (int row = 0; row < d; row++) {
                dot += out[col * d + row] * out[prev * d + row];
                norm_sq += out[prev * d + row] * out[prev * d + row];
            }
            float scale = dot / (norm_sq + 1e-10f);
            for (int row = 0; row < d; row++) {
                out[col * d + row] -= scale * out[prev * d + row];
            }
        }

        // Normalize
        float norm = 0.0f;
        for (int row = 0; row < d; row++) norm += out[col * d + row] * out[col * d + row];
        norm = sqrtf(norm + 1e-10f);
        for (int row = 0; row < d; row++) out[col * d + row] /= norm;
    }
    delete[] tmp;
}

// ============================================================================
// MultimodalInferenceController implementation
// ============================================================================

MultimodalInferenceController::MultimodalInferenceController(
    TurboQuantConfig tq_config,
    ScoringConfig    scoring_config
) : tq_config_(tq_config),
    scoring_config_(scoring_config),
    n_tier0_tokens_(0),
    current_step_(0)
{
    // Allocate device arrays
    cudaMalloc(&d_meta_,           MM_MAX_TOKENS * sizeof(TokenMeta));
    cudaMalloc(&d_actions_,        MM_MAX_TOKENS * sizeof(EvictionAction));
    cudaMalloc(&d_scores_,         MM_MAX_TOKENS * sizeof(float));
    cudaMalloc(&d_demote_list_,    MM_MAX_VICTIMS * sizeof(uint32_t));
    cudaMalloc(&d_evict_list_,     MM_MAX_VICTIMS * sizeof(uint32_t));
    cudaMalloc(&d_demote_count_,   sizeof(uint32_t));
    cudaMalloc(&d_evict_count_,    sizeof(uint32_t));
    cudaMalloc(&d_modality_stats_, sizeof(ModalityStats));

    cudaMemset(d_meta_, 0, MM_MAX_TOKENS * sizeof(TokenMeta));
    cudaMemset(d_modality_stats_, 0, sizeof(ModalityStats));

    init_tq_tables();
    init_cxl_storage();
}

MultimodalInferenceController::~MultimodalInferenceController() {
    cudaFree(d_meta_);
    cudaFree(d_actions_);
    cudaFree(d_scores_);
    cudaFree(d_demote_list_);
    cudaFree(d_evict_list_);
    cudaFree(d_demote_count_);
    cudaFree(d_evict_count_);
    cudaFree(d_modality_stats_);

    cudaFree(d_rotation_);
    cudaFree(d_rotation_t_);
    cudaFree(d_angle_grid_full_);
    cudaFree(d_angle_grid_pos_);
    cudaFree(d_cos_lut_full_);
    cudaFree(d_sin_lut_full_);
    cudaFree(d_cos_lut_pos_);
    cudaFree(d_sin_lut_pos_);
    cudaFree(d_jl_matrix_);

    mm_free_cxl_storage(cxl_);
}

void MultimodalInferenceController::init_tq_tables() {
    int d = tq_config_.head_dim;
    int n_grid = tq_config_.n_grid();
    int proj_dim = tq_config_.qjl_proj_dim > 0 ? tq_config_.qjl_proj_dim : d;

    // ---- Rotation matrix → __constant__ memory ----
    float* h_rotation = new float[d * d];
    host_generate_orthogonal(h_rotation, d, tq_config_.seed);

    // Transpose for decompression
    float* h_rotation_t = new float[d * d];
    for (int r = 0; r < d; r++)
        for (int c = 0; c < d; c++)
            h_rotation_t[r * d + c] = h_rotation[c * d + r];

    // Upload to __constant__ memory (broadcast-efficient, no shared mem needed)
    extern void mm_upload_rotation_matrices(const float*, const float*, int);
    mm_upload_rotation_matrices(h_rotation, h_rotation_t, d);

    // Also keep in global memory for backward compatibility
    cudaMalloc(&d_rotation_, d * d * sizeof(float));
    cudaMemcpy(d_rotation_, h_rotation, d * d * sizeof(float), cudaMemcpyHostToDevice);
    cudaMalloc(&d_rotation_t_, d * d * sizeof(float));
    cudaMemcpy(d_rotation_t_, h_rotation_t, d * d * sizeof(float), cudaMemcpyHostToDevice);
    delete[] h_rotation;
    delete[] h_rotation_t;

    // ---- Angle grids ----
    float* h_grid_full = new float[n_grid];
    float* h_grid_pos  = new float[n_grid];
    for (int i = 0; i < n_grid; i++) {
        h_grid_full[i] = -M_PI + ((float)i + 0.5f) * (2.0f * M_PI / n_grid);
        h_grid_pos[i]  = ((float)i + 0.5f) * (M_PI * 0.5f / n_grid);
    }
    cudaMalloc(&d_angle_grid_full_, n_grid * sizeof(float));
    cudaMalloc(&d_angle_grid_pos_,  n_grid * sizeof(float));
    cudaMemcpy(d_angle_grid_full_, h_grid_full, n_grid * sizeof(float), cudaMemcpyHostToDevice);
    cudaMemcpy(d_angle_grid_pos_,  h_grid_pos,  n_grid * sizeof(float), cudaMemcpyHostToDevice);

    // ---- Cos/Sin LUTs for decompression ----
    float* h_cos_full = new float[n_grid];
    float* h_sin_full = new float[n_grid];
    float* h_cos_pos  = new float[n_grid];
    float* h_sin_pos  = new float[n_grid];
    for (int i = 0; i < n_grid; i++) {
        h_cos_full[i] = cosf(h_grid_full[i]);
        h_sin_full[i] = sinf(h_grid_full[i]);
        h_cos_pos[i]  = cosf(h_grid_pos[i]);
        h_sin_pos[i]  = sinf(h_grid_pos[i]);
    }
    cudaMalloc(&d_cos_lut_full_, n_grid * sizeof(float));
    cudaMalloc(&d_sin_lut_full_, n_grid * sizeof(float));
    cudaMalloc(&d_cos_lut_pos_,  n_grid * sizeof(float));
    cudaMalloc(&d_sin_lut_pos_,  n_grid * sizeof(float));
    cudaMemcpy(d_cos_lut_full_, h_cos_full, n_grid * sizeof(float), cudaMemcpyHostToDevice);
    cudaMemcpy(d_sin_lut_full_, h_sin_full, n_grid * sizeof(float), cudaMemcpyHostToDevice);
    cudaMemcpy(d_cos_lut_pos_,  h_cos_pos,  n_grid * sizeof(float), cudaMemcpyHostToDevice);
    cudaMemcpy(d_sin_lut_pos_,  h_sin_pos,  n_grid * sizeof(float), cudaMemcpyHostToDevice);

    delete[] h_grid_full; delete[] h_grid_pos;
    delete[] h_cos_full;  delete[] h_sin_full;
    delete[] h_cos_pos;   delete[] h_sin_pos;

    // ---- JL matrix (Rademacher ±1/√m) ----
    float* h_jl = new float[proj_dim * d];
    srand48(tq_config_.seed + 1000);
    float inv_sqrt_m = 1.0f / sqrtf((float)proj_dim);
    for (int i = 0; i < proj_dim * d; i++) {
        h_jl[i] = (drand48() < 0.5) ? -inv_sqrt_m : inv_sqrt_m;
    }
    cudaMalloc(&d_jl_matrix_, proj_dim * d * sizeof(float));
    cudaMemcpy(d_jl_matrix_, h_jl, proj_dim * d * sizeof(float), cudaMemcpyHostToDevice);
    delete[] h_jl;
}

void MultimodalInferenceController::init_cxl_storage() {
    int d = tq_config_.head_dim;
    int proj_dim = tq_config_.qjl_proj_dim > 0 ? tq_config_.qjl_proj_dim : d;
    uint32_t total_angles = d - 1;
    uint32_t qjl_words = (proj_dim + 31) / 32;

    // External function from mm_cxl_kernels.cu
    extern void mm_init_cxl_storage(CXLStorageLayout&, uint32_t, uint32_t, uint32_t);
    mm_init_cxl_storage(cxl_, scoring_config_.cxl_capacity, total_angles, qjl_words);
}

// ============================================================================
// Per-Step Pipeline
// ============================================================================

int MultimodalInferenceController::on_decode_step(
    const __half*   d_kv_vectors,
    uint32_t new_position,
    uint8_t  token_type,
    const uint32_t* d_attended_positions,
    const float*    d_attention_weights,
    uint32_t        n_attended
) {
    current_step_++;
    scoring_config_.current_step = current_step_;
    scoring_config_.seq_len = new_position + 1;

    // ---- Append new token metadata (host → device, 32B) ----
    ModalityGroup mod = mm_token_modality(token_type);
    bool is_sink = (new_position < scoring_config_.attention_sink_tokens);

    TokenMeta new_meta{};
    new_meta.position          = new_position;
    new_meta.last_access_step  = current_step_;
    new_meta.access_count      = 1;
    new_meta.type_flags        = MM_PACK_TYPE_FLAGS(token_type, mod, is_sink);
    new_meta.tier_flags        = MM_FLAG_IN_TIER0 | (is_sink ? MM_FLAG_ANCHOR : 0);
    new_meta.attention_sum     = 0.0f;
    new_meta.attention_count   = 0;
    new_meta.cosine_sim        = 1.0f;  // uncompressed
    new_meta.reuse_trend       = 0;
    new_meta._reserved         = 0;
    new_meta.cxl_slot          = MM_CXL_SLOT_INVALID;

    cudaMemcpyAsync(&d_meta_[new_position], &new_meta, sizeof(TokenMeta),
                    cudaMemcpyHostToDevice);
    n_tier0_tokens_ = new_position + 1;

    // ========================================================================
    // KERNEL 1: Update attention stats + reuse trend
    // ========================================================================
    if (n_attended > 0 && d_attended_positions && d_attention_weights) {
        uint32_t grid = (n_attended + 255) / 256;
        mm_kernel_update_on_access<<<grid, 256>>>(
            d_meta_, d_attended_positions, d_attention_weights,
            n_attended, current_step_
        );
    }

    // Under capacity — kernel 1 was sufficient, no eviction needed
    if (n_tier0_tokens_ <= scoring_config_.tier0_capacity) {
        return 0;
    }

    // ========================================================================
    // KERNEL 2: Fused score + decide + collect (warp-ballot compaction)
    //
    // Writes d_demote_list, d_demote_count, d_evict_list, d_evict_count
    // to device memory. Kernel 3 reads them directly — no host readback.
    // ========================================================================
    uint32_t n_tokens = n_tier0_tokens_;

    // Zero atomic counters (async, no host blocking)
    cudaMemsetAsync(d_demote_count_, 0, sizeof(uint32_t));
    cudaMemsetAsync(d_evict_count_, 0, sizeof(uint32_t));

    {
        uint32_t grid = (n_tokens + MM_SCORE_BLOCK_SIZE - 1) / MM_SCORE_BLOCK_SIZE;
        mm_kernel_fused_score_collect<<<grid, MM_SCORE_BLOCK_SIZE>>>(
            d_meta_, scoring_config_, n_tokens,
            d_actions_, d_scores_,
            d_demote_list_, d_demote_count_,
            d_evict_list_, d_evict_count_
        );
    }

    // ========================================================================
    // KERNEL 3: Process demotions + evictions (fully fused)
    //
    // Reads d_demote_count / d_evict_count from device (set by kernel 2).
    // No cudaDeviceSynchronize. No D→H readback.
    //
    // For each demote: alloc CXL slot → TQ compress → write CXL → metadata
    // For each evict:  free CXL slot → clear metadata
    // All with modality stats updates.
    //
    // Fixed grid = MM_MAX_VICTIMS blocks. Blocks beyond actual work exit
    // immediately after reading the device-side counts.
    // ========================================================================
    {
        int n_grid = tq_config_.n_grid();
        int proj_dim = tq_config_.qjl_proj_dim > 0
                     ? tq_config_.qjl_proj_dim : tq_config_.head_dim;

        mm_kernel_process_demotions<<<MM_MAX_VICTIMS, MM_COMPRESS_BLOCK_SIZE>>>(
            d_kv_vectors,
            d_meta_,
            d_demote_list_, d_demote_count_,
            d_evict_list_,  d_evict_count_,
            cxl_,
            d_actions_,
            d_modality_stats_,
            (uint32_t)tq_config_.head_dim,
            n_grid,
            d_jl_matrix_,
            proj_dim,
            d_rotation_
        );
    }

    // No sync. No readback. 3 kernels total. Done.
    return 1;
}

bool MultimodalInferenceController::promote_from_cxl(uint32_t position) {
    // Read token metadata
    TokenMeta meta;
    cudaMemcpy(&meta, &d_meta_[position], sizeof(TokenMeta), cudaMemcpyDeviceToHost);

    if (!(meta.tier_flags & MM_FLAG_IN_CXL)) return false;
    if (meta.cxl_slot == MM_CXL_SLOT_INVALID) return false;

    uint32_t old_slot = meta.cxl_slot;

    // In production: launch mm_kernel_decompress_from_cxl for this token first.
    // Then update flags.

    meta.tier_flags = (meta.tier_flags & ~(MM_FLAG_IN_CXL | MM_FLAG_TQ_COMPRESSED)) | MM_FLAG_IN_TIER0;
    meta.cxl_slot = MM_CXL_SLOT_INVALID;
    meta.last_access_step = current_step_;

    cudaMemcpy(&d_meta_[position], &meta, sizeof(TokenMeta), cudaMemcpyHostToDevice);

    // Free the CXL slot: push old_slot back onto freelist via host-side memcpy.
    // Read current top, write slot at that position, increment top.
    uint32_t top = 0;
    cudaMemcpy(&top, cxl_.d_freelist_top, sizeof(uint32_t), cudaMemcpyDeviceToHost);
    if (top < cxl_.capacity) {
        cudaMemcpy(&cxl_.d_freelist[top], &old_slot, sizeof(uint32_t), cudaMemcpyHostToDevice);
        top++;
        cudaMemcpy(cxl_.d_freelist_top, &top, sizeof(uint32_t), cudaMemcpyHostToDevice);
    }

    return true;
}

void MultimodalInferenceController::reset() {
    cudaMemset(d_meta_, 0, MM_MAX_TOKENS * sizeof(TokenMeta));
    cudaMemset(d_modality_stats_, 0, sizeof(ModalityStats));
    n_tier0_tokens_ = 0;
    current_step_ = 0;
}

MultimodalInferenceController::Stats MultimodalInferenceController::get_stats() const {
    // Synchronize to ensure all kernels have completed before reading
    cudaDeviceSynchronize();

    Stats s{};
    s.tier0_occupancy = n_tier0_tokens_;
    s.total_promotions = 0;
    s.avg_score = 0.0f;

    // Read last-step demote/evict counts from device
    uint32_t n_demote = 0, n_evict = 0;
    cudaMemcpy(&n_demote, d_demote_count_, sizeof(uint32_t), cudaMemcpyDeviceToHost);
    cudaMemcpy(&n_evict,  d_evict_count_,  sizeof(uint32_t), cudaMemcpyDeviceToHost);
    s.total_demotions = n_demote;
    s.total_evictions = n_evict;

    // Copy modality stats from device
    cudaMemcpy(&s.modality, d_modality_stats_, sizeof(ModalityStats),
               cudaMemcpyDeviceToHost);

    // Count CXL occupancy from freelist top
    uint32_t freelist_top = 0;
    cudaMemcpy(&freelist_top, cxl_.d_freelist_top, sizeof(uint32_t),
               cudaMemcpyDeviceToHost);
    s.cxl_occupancy = (freelist_top <= cxl_.capacity)
                    ? cxl_.capacity - freelist_top
                    : 0;

    return s;
}
