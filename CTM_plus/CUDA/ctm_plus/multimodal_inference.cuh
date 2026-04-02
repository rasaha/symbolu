/**
 * multimodal_inference.cuh — Production CUDA inference pipeline
 *
 * Extends CTM+ / TurboQuant with:
 *   1. Multimodal token types (text / image / video / audio)
 *   2. Fused scoring + eviction-decision kernel
 *   3. CXL demotion pipeline (Tier0 → compress → CXL)
 *   4. Compact per-token metadata for GPU-resident cache
 *
 * Design goals:
 *   - Single kernel launch per decode step (score + decide)
 *   - No intermediate allocations on hot path
 *   - Coalesced reads, warp-uniform branches
 *   - ≤ 5 µs per 4K-token cache at scoring
 *
 * Memory hierarchy:
 *
 *   Tier0 (HBM, FP16)  ──── fast, capacity-limited
 *       │ compress via TurboQuant
 *       ▼
 *   CXL tier (TQ-compressed) ── warm, ~5× more capacity
 *       │ evict
 *       ▼
 *   Tier1 (NVMe / drop)  ── cold, future
 */

#pragma once

#include <cstdint>
#include <cuda_runtime.h>
#include <curand_kernel.h>

#include "turboquant.cuh"
#include "turboquant_ctxl_integration.cuh"

// ============================================================================
// Constants
// ============================================================================

// Max tokens the system tracks (governs hash table + metadata arrays)
#define MM_MAX_TOKENS           65536
// Block size for scoring/eviction kernel
#define MM_SCORE_BLOCK_SIZE     256
// Block size for compression kernel
#define MM_COMPRESS_BLOCK_SIZE  128
// Max victim candidates per eviction pass
#define MM_MAX_VICTIMS          256
// CXL slot allocation granularity
#define MM_CXL_SLOT_INVALID     0xFFFFFFFF

// ============================================================================
// Multimodal Token Types  (extends the 8 text-only TokenType enum)
// ============================================================================

/**
 * Token type IDs — compact uint8, used as index into importance LUT.
 *
 *   0-7:   Text tokens (matching existing TokenType enum)
 *   8-11:  Image tokens
 *   12-15: Video tokens
 *   16-18: Audio tokens
 *   19:    Unknown / default
 *
 * Total: 20 types → fits in a 32-entry constant LUT with room to grow.
 */
enum MultimodalTokenType : uint8_t {
    // ---- Text (same IDs as existing TokenType) ----
    MM_TOKEN_BOS             = 0,
    MM_TOKEN_ENTITY          = 1,
    MM_TOKEN_NUMBER          = 2,
    MM_TOKEN_CODE            = 3,
    MM_TOKEN_INSTRUCTION     = 4,
    MM_TOKEN_EOS             = 5,
    MM_TOKEN_REGULAR         = 6,
    MM_TOKEN_PUNCTUATION     = 7,

    // ---- Image ----
    MM_TOKEN_IMAGE_CLS       = 8,   // CLS anchor for image
    MM_TOKEN_IMAGE_PATCH     = 9,   // Generic ViT patch (redundant)
    MM_TOKEN_IMAGE_ROI       = 10,  // Region-of-interest patch
    MM_TOKEN_IMAGE_BORDER    = 11,  // Border / padding patch

    // ---- Video ----
    MM_TOKEN_VIDEO_KEYFRAME  = 12,  // I-frame (scene anchor)
    MM_TOKEN_VIDEO_PFRAME    = 13,  // P-frame (partially redundant)
    MM_TOKEN_VIDEO_BFRAME    = 14,  // B-frame (most redundant)
    MM_TOKEN_VIDEO_SCENE     = 15,  // Scene-change boundary

    // ---- Audio ----
    MM_TOKEN_AUDIO_ONSET     = 16,  // Speech / sound onset
    MM_TOKEN_AUDIO_SPEECH    = 17,  // Mid-speech token
    MM_TOKEN_AUDIO_SILENCE   = 18,  // Silence (safe to evict)

    // ---- Fallback ----
    MM_TOKEN_UNKNOWN         = 19,

    MM_TOKEN_TYPE_COUNT      = 20,
};

// LUT size padded to next power-of-2 for cache line alignment
#define MM_IMPORTANCE_LUT_SIZE  32

// ============================================================================
// Modality Groups  (for per-modality aggregate stats)
// ============================================================================

enum ModalityGroup : uint8_t {
    MODALITY_TEXT   = 0,
    MODALITY_IMAGE  = 1,
    MODALITY_VIDEO  = 2,
    MODALITY_AUDIO  = 3,
    MODALITY_COUNT  = 4,
};

/**
 * Map token type → modality group.
 * Compiled into a device constant for O(1) lookup.
 */
__host__ __device__ inline ModalityGroup mm_token_modality(uint8_t token_type) {
    if (token_type <= MM_TOKEN_PUNCTUATION)   return MODALITY_TEXT;
    if (token_type <= MM_TOKEN_IMAGE_BORDER)  return MODALITY_IMAGE;
    if (token_type <= MM_TOKEN_VIDEO_SCENE)   return MODALITY_VIDEO;
    if (token_type <= MM_TOKEN_AUDIO_SILENCE) return MODALITY_AUDIO;
    return MODALITY_TEXT;  // default
}

// ============================================================================
// Per-Token Metadata  (32 bytes, cache-line friendly)
// ============================================================================

/**
 * Compact metadata stored per token in the KV cache.
 * Designed for coalesced GPU reads: 32 B aligned, no padding waste.
 *
 * Layout (32 bytes):
 *   [0:3]   position         — token position in sequence
 *   [4:7]   last_access_step — last decode step that touched this token
 *   [8:9]   access_count     — saturating counter (max 65535)
 *   [10]    token_type       — MultimodalTokenType enum
 *   [11]    flags            — tier/state bits
 *   [12:15] attention_sum    — cumulative attention weight (EMA proxy)
 *   [16:19] attention_count  — number of attention observations
 *   [20:23] cosine_sim       — TQ compression quality (FP32, 1.0 = perfect)
 *   [24:27] original_norm    — L2 norm of original KV vector
 *   [28:31] cxl_slot         — index into CXL compressed storage (or INVALID)
 */
struct __align__(32) TokenMeta {
    uint32_t position;
    uint32_t last_access_step;
    uint16_t access_count;
    uint8_t  token_type;        // MultimodalTokenType
    uint8_t  flags;
    float    attention_sum;
    uint32_t attention_count;
    float    cosine_sim;
    float    original_norm;
    uint32_t cxl_slot;
};

// Flag bits for TokenMeta.flags
#define MM_FLAG_IN_TIER0      (1u << 0)
#define MM_FLAG_IN_CXL        (1u << 1)
#define MM_FLAG_IN_TIER1      (1u << 2)
#define MM_FLAG_PINNED        (1u << 3)
#define MM_FLAG_TQ_COMPRESSED (1u << 4)
#define MM_FLAG_ANCHOR        (1u << 5)  // protected anchor (sink, etc.)

// ============================================================================
// Eviction Decision
// ============================================================================

enum EvictionAction : uint8_t {
    ACTION_KEEP    = 0,   // Stay in Tier0 (HBM)
    ACTION_DEMOTE  = 1,   // Compress + move to CXL
    ACTION_EVICT   = 2,   // Drop entirely (or move to Tier1/NVMe)
};

// ============================================================================
// Scoring Configuration
// ============================================================================

struct ScoringConfig {
    // Signal weights (should sum to ~1.0)
    float w_recency;                // 0.20
    float w_frequency;              // 0.20
    float w_attention;              // 0.25
    float w_token_importance;       // 0.15
    float w_position;               // 0.10
    float w_compression_quality;    // 0.05
    float w_modality_anchor;        // 0.05

    // Thresholds
    uint32_t attention_sink_tokens; // First N positions always kept
    uint32_t recent_window_size;    // Last N positions get bonus
    float    demotion_threshold;    // Score below this → demote to CXL
    float    eviction_threshold;    // Score below this → evict

    // Capacity
    uint32_t tier0_capacity;        // Max tokens in HBM
    uint32_t cxl_capacity;          // Max compressed tokens in CXL

    // Current state
    uint32_t current_step;          // Monotonic decode step counter
    uint32_t seq_len;               // Current sequence length

    static ScoringConfig defaults() {
        ScoringConfig c{};
        c.w_recency              = 0.20f;
        c.w_frequency            = 0.20f;
        c.w_attention            = 0.25f;
        c.w_token_importance     = 0.15f;
        c.w_position             = 0.10f;
        c.w_compression_quality  = 0.05f;
        c.w_modality_anchor      = 0.05f;
        c.attention_sink_tokens  = 4;
        c.recent_window_size     = 256;
        c.demotion_threshold     = 0.25f;
        c.eviction_threshold     = 0.10f;
        c.tier0_capacity         = 4096;
        c.cxl_capacity           = 16384;
        c.current_step           = 0;
        c.seq_len                = 0;
        return c;
    }

    static ScoringConfig for_long_context() {
        ScoringConfig c = defaults();
        c.w_recency              = 0.15f;
        c.w_attention            = 0.30f;
        c.w_token_importance     = 0.20f;
        c.attention_sink_tokens  = 8;
        c.recent_window_size     = 1024;
        c.tier0_capacity         = 8192;
        c.cxl_capacity           = 32768;
        return c;
    }
};

// ============================================================================
// CXL Compressed Storage Layout
// ============================================================================

/**
 * CXL storage is a flat buffer pool indexed by slot ID.
 *
 * For head_dim = 128, 3-bit TQ:
 *   Per slot:
 *     angle_indices: 127 uint8  = 127 bytes
 *     final_radius:  1 float32  =   4 bytes
 *     qjl_bits:      4 uint32   =  16 bytes  (128-dim / 32 bits/word)
 *     qjl_scale:     1 float32  =   4 bytes
 *                              Total: 151 bytes → padded to 160 bytes
 *
 * Layout in device memory:
 *   d_cxl_indices[cxl_capacity * total_angles]  — angle indices (SoA)
 *   d_cxl_radii[cxl_capacity]                   — final radii
 *   d_cxl_qjl_bits[cxl_capacity * qjl_words]    — QJL sign bits
 *   d_cxl_qjl_scales[cxl_capacity]              — QJL scales
 *   d_cxl_freelist[cxl_capacity]                 — free slot stack
 *   d_cxl_freelist_top                           — atomic stack pointer
 */
struct CXLStorageLayout {
    uint8_t*  d_indices;       // [cxl_capacity * total_angles]
    float*    d_radii;         // [cxl_capacity]
    uint32_t* d_qjl_bits;     // [cxl_capacity * qjl_words_per_vec]
    float*    d_qjl_scales;   // [cxl_capacity]

    // Slot allocator (lock-free stack)
    uint32_t* d_freelist;      // [cxl_capacity]
    uint32_t* d_freelist_top;  // Atomic stack top (init to cxl_capacity - 1)

    uint32_t  capacity;
    uint32_t  total_angles;    // head_dim - 1
    uint32_t  qjl_words;       // ceil(qjl_proj_dim / 32)
};

// ============================================================================
// Per-Modality Statistics (atomic, device-side)
// ============================================================================

struct ModalityStats {
    uint32_t tier0_count[MODALITY_COUNT];
    uint32_t cxl_count[MODALITY_COUNT];
    uint32_t evicted_count[MODALITY_COUNT];
    uint32_t total_inserted[MODALITY_COUNT];
};

// ============================================================================
// Kernel Declarations
// ============================================================================

/**
 * Fused scoring + eviction decision kernel.
 *
 * ONE launch per decode step. For each Tier0 token:
 *   1. Compute 7-signal importance score
 *   2. Compare against thresholds
 *   3. Write ACTION_KEEP / ACTION_DEMOTE / ACTION_EVICT
 *
 * Thread layout: 1 thread per Tier0 token.
 * Grid:  ceil(n_tier0_tokens / MM_SCORE_BLOCK_SIZE)
 * Block: MM_SCORE_BLOCK_SIZE (256)
 *
 * Reads: d_meta[] (coalesced 32B per thread)
 * Writes: d_actions[] (1 byte per token), d_scores[] (4 bytes, optional)
 *
 * Expected latency: ~3 µs for 4K tokens on A100.
 */
__global__ void mm_kernel_score_and_decide(
    const TokenMeta*     __restrict__ d_meta,
    const ScoringConfig  config,
    uint32_t             n_tokens,
    EvictionAction*      __restrict__ d_actions,   // [n_tokens]
    float*               __restrict__ d_scores     // [n_tokens] (NULL = skip)
);

/**
 * Collect demotion candidates: compact tokens with ACTION_DEMOTE
 * into a contiguous list using warp-level prefix sum.
 *
 * Grid:  ceil(n_tokens / MM_SCORE_BLOCK_SIZE)
 * Block: MM_SCORE_BLOCK_SIZE
 *
 * Output: d_demote_list[*d_demote_count] — positions of tokens to demote
 */
__global__ void mm_kernel_collect_demotions(
    const EvictionAction* __restrict__ d_actions,
    uint32_t              n_tokens,
    uint32_t*             __restrict__ d_demote_list,   // [MM_MAX_VICTIMS]
    uint32_t*             __restrict__ d_demote_count   // atomic counter
);

/**
 * Allocate CXL slots for demoted tokens (lock-free stack pop).
 *
 * Grid:  ceil(n_demote / 128)
 * Block: 128
 *
 * Each thread atomically decrements freelist_top and reads a slot.
 * On success, writes slot ID into d_meta[token].cxl_slot and updates flags.
 * On failure (CXL full), marks token as ACTION_EVICT instead.
 */
__global__ void mm_kernel_alloc_cxl_slots(
    TokenMeta*           __restrict__ d_meta,
    const uint32_t*      __restrict__ d_demote_list,
    uint32_t             n_demote,
    CXLStorageLayout     cxl,
    EvictionAction*      __restrict__ d_actions  // may upgrade DEMOTE→EVICT
);

/**
 * Compress demoted tokens' KV vectors into CXL storage.
 *
 * Uses TurboQuant fused compression (PolarQuant + QJL).
 * 1 block = 1 token (needs shared memory for rotation matrix).
 *
 * Grid:  n_demote
 * Block: MM_COMPRESS_BLOCK_SIZE (128 — matches head_dim)
 *
 * Input:  d_kv_fp16[token_pos * head_dim] — FP16 KV vectors in HBM
 * Output: CXL storage arrays indexed by cxl_slot
 */
__global__ void mm_kernel_compress_to_cxl(
    const __half*        __restrict__ d_kv_vectors,   // [max_tokens, head_dim]
    const TokenMeta*     __restrict__ d_meta,
    const uint32_t*      __restrict__ d_demote_list,
    uint32_t             n_demote,
    uint32_t             head_dim,
    CXLStorageLayout     cxl,
    // TurboQuant precomputed tables
    const float*         __restrict__ d_rotation_matrix,  // [head_dim, head_dim]
    const float*         __restrict__ d_angle_grid_full,  // [n_grid]
    const float*         __restrict__ d_angle_grid_pos,   // [n_grid]
    int                  n_grid,
    // QJL
    const float*         __restrict__ d_jl_matrix,        // [proj_dim, head_dim]
    int                  proj_dim
);

/**
 * Decompress tokens from CXL back to HBM (promotion path).
 *
 * Inverse of compress: read CXL slot, apply inverse polar + rotation.
 * 1 block = 1 token.
 *
 * Grid:  n_promote
 * Block: MM_COMPRESS_BLOCK_SIZE
 */
__global__ void mm_kernel_decompress_from_cxl(
    __half*              __restrict__ d_kv_vectors,    // output: [max_tokens, head_dim]
    const TokenMeta*     __restrict__ d_meta,
    const uint32_t*      __restrict__ d_promote_list,
    uint32_t             n_promote,
    uint32_t             head_dim,
    CXLStorageLayout     cxl,
    // TurboQuant precomputed tables (inverse rotation = R^T)
    const float*         __restrict__ d_rotation_t,    // [head_dim, head_dim]
    const float*         __restrict__ d_cos_lut_full,  // [n_grid]
    const float*         __restrict__ d_sin_lut_full,  // [n_grid]
    const float*         __restrict__ d_cos_lut_pos,   // [n_grid]
    const float*         __restrict__ d_sin_lut_pos,   // [n_grid]
    int                  n_grid
);

/**
 * Free CXL slots for evicted tokens (lock-free stack push).
 * Also updates ModalityStats counters.
 *
 * Grid:  ceil(n_evict / 128)
 * Block: 128
 */
__global__ void mm_kernel_free_cxl_slots(
    TokenMeta*           __restrict__ d_meta,
    const uint32_t*      __restrict__ d_evict_list,
    uint32_t             n_evict,
    CXLStorageLayout     cxl,
    ModalityStats*       __restrict__ d_modality_stats
);

/**
 * Update token metadata after a new token is appended
 * (called once per decode step for all attending tokens).
 *
 * Updates: last_access_step, access_count, attention_sum.
 * Lightweight: 1 thread per token in the attention window.
 *
 * Grid:  ceil(n_attending / 256)
 * Block: 256
 */
__global__ void mm_kernel_update_on_access(
    TokenMeta*           __restrict__ d_meta,
    const uint32_t*      __restrict__ d_attending_positions,  // which tokens were attended
    const float*         __restrict__ d_attention_weights,    // softmax weights for each
    uint32_t             n_attending,
    uint32_t             current_step
);

// ============================================================================
// Host-Side Controller
// ============================================================================

class MultimodalInferenceController {
public:
    MultimodalInferenceController(
        TurboQuantConfig tq_config,
        ScoringConfig    scoring_config
    );
    ~MultimodalInferenceController();

    // ---- Per-step API (called from vLLM decode loop) ----

    /**
     * Called when a new token is generated.
     * 1. Append token metadata
     * 2. Update attention stats for attended positions
     * 3. Score all Tier0 tokens
     * 4. Execute demotions / evictions
     *
     * Returns number of tokens demoted to CXL.
     */
    int on_decode_step(
        uint32_t new_position,
        uint8_t  token_type,
        // Attention info from this step
        const uint32_t* d_attended_positions,
        const float*    d_attention_weights,
        uint32_t        n_attended
    );

    /**
     * Promote a token from CXL back to Tier0 (e.g., on cache miss).
     * Decompresses via TurboQuant and restores FP16 KV vector.
     */
    bool promote_from_cxl(uint32_t position);

    // ---- Lifecycle ----
    void reset();

    // ---- Stats ----
    struct Stats {
        uint32_t tier0_occupancy;
        uint32_t cxl_occupancy;
        uint32_t total_demotions;
        uint32_t total_evictions;
        uint32_t total_promotions;
        float    avg_score;
        ModalityStats modality;
    };
    Stats get_stats() const;

private:
    TurboQuantConfig  tq_config_;
    ScoringConfig     scoring_config_;

    // Device arrays
    TokenMeta*        d_meta_;              // [MM_MAX_TOKENS]
    EvictionAction*   d_actions_;           // [MM_MAX_TOKENS]
    float*            d_scores_;            // [MM_MAX_TOKENS]
    uint32_t*         d_demote_list_;       // [MM_MAX_VICTIMS]
    uint32_t*         d_evict_list_;        // [MM_MAX_VICTIMS]
    uint32_t*         d_demote_count_;      // atomic counter
    uint32_t*         d_evict_count_;       // atomic counter
    ModalityStats*    d_modality_stats_;

    // CXL storage
    CXLStorageLayout  cxl_;

    // TurboQuant precomputed tables (device)
    float*            d_rotation_;          // [head_dim, head_dim]
    float*            d_rotation_t_;        // [head_dim, head_dim] (transpose)
    float*            d_angle_grid_full_;   // [n_grid]
    float*            d_angle_grid_pos_;    // [n_grid]
    float*            d_cos_lut_full_;      // [n_grid]
    float*            d_sin_lut_full_;      // [n_grid]
    float*            d_cos_lut_pos_;       // [n_grid]
    float*            d_sin_lut_pos_;       // [n_grid]
    float*            d_jl_matrix_;         // [proj_dim, head_dim]

    // State
    uint32_t          n_tier0_tokens_;
    uint32_t          current_step_;

    void init_tq_tables();
    void init_cxl_storage();
};

#endif  // Included via pragma once
