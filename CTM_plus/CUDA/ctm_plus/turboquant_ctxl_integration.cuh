/*
 * TurboQuant + CTXL Integration for CTM+ — CUDA Implementation
 *
 * Combines TurboQuant's mathematical compression (PolarQuant + QJL) with
 * CTM+'s intelligent multi-signal eviction and a CXL (CTXL) warm memory
 * tier for a 3-level KV cache hierarchy:
 *
 *   Tier 0: HBM (FP16)     — Fast, limited capacity
 *   CXL:    DRAM (TQ-3bit) — Warm tier, TurboQuant-compressed (~5.3x expansion)
 *   Tier 1: NVMe           — Cold storage, last resort
 *
 * This mirrors the vLLM Python implementation (turboquant_integration.py)
 * as a native CUDA module for production GPU deployments.
 *
 * Integration modes (matching vLLM IntegrationMode):
 *   CAPACITY_ONLY:  TurboQuant expands CXL capacity; eviction unchanged
 *   QUALITY_AWARE:  TurboQuant expands CXL + compression quality informs
 *                   eviction scoring (tokens that compress poorly get
 *                   protection from eviction)
 *
 * SPDX-License-Identifier: MIT
 */

#ifndef TURBOQUANT_CTXL_INTEGRATION_CUH
#define TURBOQUANT_CTXL_INTEGRATION_CUH

#include "ctm_plus.cuh"
#include "turboquant.cuh"
#include <cuda_runtime.h>

namespace ctm {

/* ========== Integration Mode ========== */

enum class IntegrationMode : int {
    CAPACITY_ONLY  = 0,  // TurboQuant expands cache; eviction unchanged
    QUALITY_AWARE  = 1,  // + compression quality informs eviction scoring
};

/* ========== Configuration ========== */

/**
 * Integrated configuration for TurboQuant + CTM+ + CTXL.
 *
 * Combines TurboQuant compression settings, CTM+ eviction weights,
 * and CXL tier sizing into a single config struct.
 */
struct IntegratedConfig {
    // TurboQuant compression
    TurboQuantConfig tq_config;

    // CTM+ eviction weights (matching vLLM CTMKVConfig)
    float weight_recency             = 0.20f;
    float weight_frequency           = 0.25f;
    float weight_attention_strength  = 0.25f;
    float weight_token_importance    = 0.15f;
    float weight_position            = 0.10f;
    float weight_sequence_priority   = 0.05f;

    // Quality-aware eviction weight
    float weight_compression_quality = 0.05f;

    // Integration mode
    IntegrationMode mode = IntegrationMode::QUALITY_AWARE;

    // CXL tier sizing
    uint32_t tier0_capacity_tokens = 4096;  // HBM capacity (FP16 tokens)
    uint32_t cxl_capacity_tokens   = 0;     // 0 = auto (tier0 * compression_ratio)
    uint32_t tier1_capacity_tokens = 0;     // NVMe (0 = unlimited)

    // Attention sink / recent window (CTM+ scoring)
    uint32_t attention_sink_tokens = 4;
    uint32_t recent_window_size    = 256;
    uint32_t frequency_window      = 1000;

    // Victim selection
    uint32_t victim_sample_size = 64;

    // Computed: effective CXL capacity
    uint32_t effective_cxl_capacity() const {
        if (cxl_capacity_tokens > 0) return cxl_capacity_tokens;
        return (uint32_t)(tier0_capacity_tokens * tq_config.compression_ratio());
    }

    // Total effective tokens across all tiers
    uint32_t total_effective_tokens() const {
        return tier0_capacity_tokens + effective_cxl_capacity();
    }
};

/**
 * Preset: 3-bit chatbot (low-latency)
 */
inline IntegratedConfig integrated_config_3bit_chatbot(int head_dim = 128) {
    IntegratedConfig cfg;
    cfg.tq_config = tq_config_3bit(head_dim);
    cfg.weight_recency = 0.30f;
    cfg.weight_frequency = 0.25f;
    cfg.weight_attention_strength = 0.25f;
    cfg.weight_token_importance = 0.10f;
    cfg.weight_position = 0.10f;
    cfg.mode = IntegrationMode::QUALITY_AWARE;
    cfg.recent_window_size = 256;
    return cfg;
}

/**
 * Preset: 3-bit long context (32K+)
 */
inline IntegratedConfig integrated_config_3bit_long_context(int head_dim = 128) {
    IntegratedConfig cfg;
    cfg.tq_config = tq_config_3bit(head_dim);
    cfg.weight_recency = 0.10f;
    cfg.weight_frequency = 0.25f;
    cfg.weight_attention_strength = 0.35f;
    cfg.weight_token_importance = 0.20f;
    cfg.weight_position = 0.10f;
    cfg.mode = IntegrationMode::QUALITY_AWARE;
    cfg.attention_sink_tokens = 8;
    cfg.recent_window_size = 1024;
    return cfg;
}

/**
 * Preset: 4-bit long context (near-lossless)
 */
inline IntegratedConfig integrated_config_4bit_long_context(int head_dim = 128) {
    IntegratedConfig cfg;
    cfg.tq_config = tq_config_4bit(head_dim);
    cfg.weight_recency = 0.10f;
    cfg.weight_frequency = 0.25f;
    cfg.weight_attention_strength = 0.35f;
    cfg.weight_token_importance = 0.20f;
    cfg.weight_position = 0.10f;
    cfg.mode = IntegrationMode::CAPACITY_ONLY;
    cfg.attention_sink_tokens = 8;
    cfg.recent_window_size = 1024;
    return cfg;
}

/* ========== Token Importance (matching vLLM) ========== */

/**
 * Token type IDs for importance scoring.
 * Matches vLLM TurboQuantCTMSimulator.TOKEN_IMPORTANCE.
 */
enum TokenType : uint8_t {
    TOKEN_BOS         = 0,  // importance = 1.0
    TOKEN_ENTITY      = 1,  // importance = 0.9
    TOKEN_NUMBER      = 2,  // importance = 0.85
    TOKEN_CODE        = 3,  // importance = 0.8
    TOKEN_INSTRUCTION = 4,  // importance = 0.75
    TOKEN_EOS         = 5,  // importance = 0.5
    TOKEN_REGULAR     = 6,  // importance = 0.4
    TOKEN_PUNCTUATION = 7,  // importance = 0.2
};

/* ========== Integrated Statistics ========== */

/**
 * Extended statistics for the integrated system.
 */
struct IntegratedStats {
    // Access statistics
    uint64_t total_accesses;
    uint64_t tier0_hits;         // HBM hits
    uint64_t cxl_hits;           // CXL tier hits (TQ-compressed)
    uint64_t tier1_hits;         // NVMe hits
    uint64_t misses;

    // Movement statistics
    uint64_t tier0_to_cxl;       // Demotion: HBM -> CXL (compress)
    uint64_t cxl_to_tier0;       // Promotion: CXL -> HBM (decompress)
    uint64_t cxl_to_tier1;       // Demotion: CXL -> NVMe
    uint64_t tier1_to_cxl;       // Promotion: NVMe -> CXL (compress)
    uint64_t evictions;          // Total evictions from all tiers

    // TurboQuant statistics
    uint64_t tq_compressions;
    uint64_t tq_decompressions;
    float    tq_avg_cosine;      // Running average cosine similarity
    float    tq_avg_mse;         // Running average MSE

    // Capacity
    uint32_t tier0_occupancy;
    uint32_t cxl_occupancy;
    uint32_t tier1_occupancy;
};

/* ========== Kernel Declarations ========== */

/**
 * Integrated access kernel — handles 3-tier lookup with CXL.
 *
 * For each access:
 *   1. Check Tier0 (HBM) — direct hit
 *   2. Check CXL — hit requires decompression for attention
 *   3. Check Tier1 (NVMe) — hit requires full fetch + optional compress to CXL
 *   4. Miss — admit to Tier0
 *
 * On Tier0 overflow: demote victims to CXL (compress with TurboQuant)
 * On CXL overflow: demote victims to Tier1
 */
__global__ void kernel_integrated_access(
    PageState*          pages,
    const uint64_t*     access_page_ids,
    const uint8_t*      token_types,          // TokenType per access
    const float*        attention_weights,     // Attention weight per access
    uint32_t            num_accesses,
    uint64_t            current_time,
    IntegratedConfig    config,
    IntegratedStats*    stats,
    uint8_t*            hit_tiers             // Output: tier where hit occurred (0/1/2/3=miss)
);

/**
 * Integrated victim selection with quality-aware scoring.
 *
 * Selects victims from Tier0 for demotion to CXL, considering:
 *   - Standard CTM+ signals (recency, frequency, attention, importance, position)
 *   - Compression quality (quality-aware mode): tokens that compress well
 *     are preferred for demotion since they lose less information
 */
__global__ void kernel_integrated_select_victims(
    const PageState*    pages,
    const uint64_t*     tier0_pages,
    uint32_t            tier0_size,
    IntegratedConfig    config,
    uint64_t            current_time,
    uint64_t*           victim_ids,
    uint32_t            num_victims,
    curandState*        rng_states
);

/**
 * Batch update compression quality for pages in CXL tier.
 *
 * After TurboQuant compression, updates each page's quality metrics
 * (MSE, cosine similarity) for use in quality-aware eviction scoring.
 */
__global__ void kernel_update_compression_quality(
    PageState*          pages,
    const uint64_t*     page_ids,
    const float*        mse_values,
    const float*        cosine_values,
    const float*        norm_values,
    uint32_t            num_pages,
    uint8_t             compression_bits
);

/* ========== Host-side Integrated Controller ========== */

/**
 * Integrated TurboQuant + CTXL + CTM+ Controller.
 *
 * Manages the 3-tier KV cache hierarchy:
 *   Tier0 (HBM, FP16) -> CXL (DRAM, TQ-compressed) -> Tier1 (NVMe)
 *
 * Usage:
 *   IntegratedConfig config = integrated_config_3bit_long_context();
 *   config.tier0_capacity_tokens = 4096;
 *
 *   IntegratedController ctrl(config, stream);
 *   ctrl.access_batch(d_page_ids, d_token_types, d_attn_weights, n, d_hit_tiers);
 *
 *   IntegratedStats stats = ctrl.get_stats();
 */
class IntegratedController {
public:
    IntegratedController(const IntegratedConfig& config,
                         cudaStream_t stream = 0);
    ~IntegratedController();

    // Disable copy
    IntegratedController(const IntegratedController&) = delete;
    IntegratedController& operator=(const IntegratedController&) = delete;

    /**
     * Process a batch of token accesses through the 3-tier hierarchy.
     *
     * @param d_page_ids       Device ptr: page/token IDs
     * @param d_token_types    Device ptr: TokenType per access
     * @param d_attn_weights   Device ptr: attention weight per access
     * @param num_accesses     Number of accesses in batch
     * @param d_hit_tiers      Device ptr output: tier where each hit occurred
     */
    void access_batch(const uint64_t* d_page_ids,
                      const uint8_t* d_token_types,
                      const float* d_attn_weights,
                      uint32_t num_accesses,
                      uint8_t* d_hit_tiers);

    /**
     * Compress KV vectors and store in CXL tier.
     *
     * Compresses a batch of FP16 KV vectors using TurboQuant and updates
     * the page state with compression quality metrics.
     *
     * @param d_vectors    Device ptr: (batch, head_dim) float32 KV vectors
     * @param d_page_ids   Device ptr: page IDs for these vectors
     * @param batch        Number of vectors
     */
    void compress_to_cxl(const float* d_vectors,
                         const uint64_t* d_page_ids,
                         int batch);

    /**
     * Decompress KV vectors from CXL tier back to FP16.
     *
     * @param d_page_ids   Device ptr: page IDs to decompress
     * @param batch        Number of vectors
     * @param d_vectors    Device ptr output: (batch, head_dim) float32
     */
    void decompress_from_cxl(const uint64_t* d_page_ids,
                             int batch,
                             float* d_vectors);

    /** Get statistics (synchronous) */
    IntegratedStats get_stats();

    /** Reset statistics */
    void reset_stats();

    /** Get configuration */
    const IntegratedConfig& get_config() const { return config_; }

    /** Get the TurboQuant engine */
    TurboQuantEngine& get_tq_engine() { return *tq_engine_; }

    /** Synchronize */
    void synchronize();

private:
    IntegratedConfig config_;
    cudaStream_t stream_;

    // Sub-components
    TurboQuantEngine* tq_engine_;

    // Device memory
    PageState* d_pages_;
    IntegratedStats* d_stats_;
    curandState* d_rng_states_;

    // Tier tracking arrays
    uint64_t* d_tier0_pages_;
    uint64_t* d_cxl_pages_;

    // Compressed KV storage (CXL tier)
    unsigned char* d_cxl_indices_;  // (cxl_capacity, total_angles) uint8
    float* d_cxl_radii_;           // (cxl_capacity,) float32
    uint32_t* d_cxl_qjl_bits_;    // QJL sign bits (optional)
    float* d_cxl_qjl_scales_;     // QJL scales (optional)

    // Host-side state
    IntegratedStats h_stats_;
    uint32_t tier0_size_;
    uint32_t cxl_size_;
    uint64_t access_counter_;

    void init_device_memory();
    void select_and_demote_victims();
};

} // namespace ctm

#endif // TURBOQUANT_CTXL_INTEGRATION_CUH
