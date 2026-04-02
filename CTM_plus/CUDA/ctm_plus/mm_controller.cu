/**
 * mm_controller.cu — Host-side MultimodalInferenceController
 *
 * Orchestrates the per-step pipeline:
 *   1. Append new token metadata
 *   2. Update attention stats for attended positions
 *   3. Score all Tier0 tokens (fused kernel)
 *   4. Collect demotions
 *   5. Allocate CXL slots
 *   6. Compress demoted tokens to CXL
 *   7. Free slots for evicted tokens
 *
 * Total kernel launches per decode step: 5-7
 * (can be reduced to 3 with CUDA graphs in production)
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

    // ---- Rotation matrix ----
    float* h_rotation = new float[d * d];
    host_generate_orthogonal(h_rotation, d, tq_config_.seed);

    cudaMalloc(&d_rotation_, d * d * sizeof(float));
    cudaMemcpy(d_rotation_, h_rotation, d * d * sizeof(float), cudaMemcpyHostToDevice);

    // Transpose for decompression
    float* h_rotation_t = new float[d * d];
    for (int r = 0; r < d; r++)
        for (int c = 0; c < d; c++)
            h_rotation_t[r * d + c] = h_rotation[c * d + r];

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
    uint32_t new_position,
    uint8_t  token_type,
    const uint32_t* d_attended_positions,
    const float*    d_attention_weights,
    uint32_t        n_attended
) {
    current_step_++;
    scoring_config_.current_step = current_step_;
    scoring_config_.seq_len = new_position + 1;

    // ---- 1. Append new token metadata (host-side init, single cudaMemcpy) ----
    TokenMeta new_meta{};
    new_meta.position          = new_position;
    new_meta.last_access_step  = current_step_;
    new_meta.access_count      = 1;
    new_meta.token_type        = token_type;
    new_meta.flags             = MM_FLAG_IN_TIER0;
    new_meta.attention_sum     = 0.0f;
    new_meta.attention_count   = 0;
    new_meta.cosine_sim        = 1.0f;  // not compressed yet
    new_meta.original_norm     = 0.0f;
    new_meta.cxl_slot          = MM_CXL_SLOT_INVALID;

    // Pin attention sink tokens
    if (new_position < scoring_config_.attention_sink_tokens) {
        new_meta.flags |= MM_FLAG_PINNED | MM_FLAG_ANCHOR;
    }

    cudaMemcpy(&d_meta_[new_position], &new_meta, sizeof(TokenMeta),
               cudaMemcpyHostToDevice);
    n_tier0_tokens_ = new_position + 1;

    // ---- 2. Update attention stats ----
    if (n_attended > 0 && d_attended_positions && d_attention_weights) {
        uint32_t grid = (n_attended + 255) / 256;
        mm_kernel_update_on_access<<<grid, 256>>>(
            d_meta_, d_attended_positions, d_attention_weights,
            n_attended, current_step_
        );
    }

    // ---- 3. Score all tokens ----
    uint32_t n_tokens = n_tier0_tokens_;
    {
        uint32_t grid = (n_tokens + MM_SCORE_BLOCK_SIZE - 1) / MM_SCORE_BLOCK_SIZE;
        mm_kernel_score_and_decide<<<grid, MM_SCORE_BLOCK_SIZE>>>(
            d_meta_, scoring_config_, n_tokens, d_actions_, d_scores_
        );
    }

    // ---- 4. Check if we need to evict (capacity exceeded) ----
    // Skip eviction if under capacity
    if (n_tier0_tokens_ <= scoring_config_.tier0_capacity) {
        return 0;
    }

    // ---- 5. Collect demotions ----
    cudaMemset(d_demote_count_, 0, sizeof(uint32_t));
    {
        uint32_t grid = (n_tokens + MM_SCORE_BLOCK_SIZE - 1) / MM_SCORE_BLOCK_SIZE;
        mm_kernel_collect_demotions<<<grid, MM_SCORE_BLOCK_SIZE>>>(
            d_actions_, n_tokens, d_demote_list_, d_demote_count_
        );
    }
    cudaDeviceSynchronize();

    uint32_t n_demote = 0;
    cudaMemcpy(&n_demote, d_demote_count_, sizeof(uint32_t), cudaMemcpyDeviceToHost);
    n_demote = (n_demote > MM_MAX_VICTIMS) ? MM_MAX_VICTIMS : n_demote;

    if (n_demote == 0) return 0;

    // ---- 6. Allocate CXL slots ----
    {
        uint32_t grid = (n_demote + 127) / 128;
        mm_kernel_alloc_cxl_slots<<<grid, 128>>>(
            d_meta_, d_demote_list_, n_demote, cxl_, d_actions_
        );
    }

    // ---- 7. Compress demoted tokens to CXL ----
    // Note: In a real system, d_kv_vectors would be the actual KV cache.
    // Here we pass nullptr since we don't have the real KV data in this controller.
    // The kernel is designed to be called by the vLLM integration layer which
    // provides the actual KV cache pointer.

    // mm_kernel_compress_to_cxl<<<n_demote, MM_COMPRESS_BLOCK_SIZE,
    //     tq_config_.head_dim * tq_config_.head_dim * sizeof(float)>>>(
    //     d_kv_vectors, d_meta_, d_demote_list_, n_demote,
    //     tq_config_.head_dim, cxl_,
    //     d_rotation_, d_angle_grid_full_, d_angle_grid_pos_,
    //     tq_config_.n_grid(), d_jl_matrix_,
    //     tq_config_.qjl_proj_dim > 0 ? tq_config_.qjl_proj_dim : tq_config_.head_dim
    // );

    return (int)n_demote;
}

bool MultimodalInferenceController::promote_from_cxl(uint32_t position) {
    // Read token metadata
    TokenMeta meta;
    cudaMemcpy(&meta, &d_meta_[position], sizeof(TokenMeta), cudaMemcpyDeviceToHost);

    if (!(meta.flags & MM_FLAG_IN_CXL)) return false;
    if (meta.cxl_slot == MM_CXL_SLOT_INVALID) return false;

    // In production: launch mm_kernel_decompress_from_cxl for this token
    // Then update flags: clear IN_CXL, set IN_TIER0, free CXL slot.

    meta.flags = (meta.flags & ~(MM_FLAG_IN_CXL | MM_FLAG_TQ_COMPRESSED)) | MM_FLAG_IN_TIER0;
    uint32_t old_slot = meta.cxl_slot;
    meta.cxl_slot = MM_CXL_SLOT_INVALID;
    meta.last_access_step = current_step_;

    cudaMemcpy(&d_meta_[position], &meta, sizeof(TokenMeta), cudaMemcpyHostToDevice);

    // Free the CXL slot
    uint32_t one = 1;
    // Push old_slot back onto freelist (simplified host-side)
    // In production, use a single-element kernel or batch these.
    return true;
}

void MultimodalInferenceController::reset() {
    cudaMemset(d_meta_, 0, MM_MAX_TOKENS * sizeof(TokenMeta));
    cudaMemset(d_modality_stats_, 0, sizeof(ModalityStats));
    n_tier0_tokens_ = 0;
    current_step_ = 0;
}

MultimodalInferenceController::Stats MultimodalInferenceController::get_stats() const {
    Stats s{};
    s.tier0_occupancy = n_tier0_tokens_;
    s.total_demotions = 0;
    s.total_evictions = 0;
    s.total_promotions = 0;
    s.avg_score = 0.0f;

    // Copy modality stats from device
    cudaMemcpy(&s.modality, d_modality_stats_, sizeof(ModalityStats),
               cudaMemcpyDeviceToHost);

    // Count CXL occupancy from freelist top
    uint32_t freelist_top = 0;
    cudaMemcpy(&freelist_top, cxl_.d_freelist_top, sizeof(uint32_t),
               cudaMemcpyDeviceToHost);
    s.cxl_occupancy = cxl_.capacity - freelist_top;

    return s;
}
