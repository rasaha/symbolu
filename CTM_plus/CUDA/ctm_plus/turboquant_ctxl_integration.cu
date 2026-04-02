/*
 * TurboQuant + CTXL Integration for CTM+ — CUDA Implementation
 *
 * Implements the integrated 3-tier KV cache hierarchy:
 *   Tier 0: HBM (FP16)     — Hot tokens, full precision
 *   CXL:    DRAM (TQ-3bit) — Warm tokens, TurboQuant-compressed
 *   Tier 1: NVMe           — Cold tokens, evicted from CXL
 *
 * Port of vLLM turboquant_integration.py TurboQuantCTMSimulator to native
 * CUDA, integrated with the CTM+ memory tiering controller.
 *
 * SPDX-License-Identifier: MIT
 */

#include "turboquant_ctxl_integration.cuh"
#include <cuda.h>
#include <curand_kernel.h>
#include <cstdio>
#include <cstring>

namespace ctm {

/* ========== Device Constants ========== */

// Token importance LUT (matching vLLM TurboQuantCTMSimulator.TOKEN_IMPORTANCE)
__constant__ float c_token_importance[8] = {
    1.00f,  // TOKEN_BOS
    0.90f,  // TOKEN_ENTITY
    0.85f,  // TOKEN_NUMBER
    0.80f,  // TOKEN_CODE
    0.75f,  // TOKEN_INSTRUCTION
    0.50f,  // TOKEN_EOS
    0.40f,  // TOKEN_REGULAR
    0.20f,  // TOKEN_PUNCTUATION
};

/* ========== Device Helper Functions ========== */

/**
 * CTM+ multi-signal scoring — matches vLLM _score() method.
 *
 * 6 signals (+ optional quality-aware):
 *   1. Recency:     exp(-0.693 * age / 100)
 *   2. Frequency:   log1p(freq * 10) / log1p(10)
 *   3. Attention:   sigmoid(strength - 5)
 *   4. Importance:  token type lookup
 *   5. Position:    sinks + recent window bonus
 *   6. Compression: (1 - cosine_similarity) * weight  [quality-aware mode]
 *
 * Higher score = more valuable = less likely evicted.
 */
__device__ float integrated_score(
    const PageState& page,
    uint64_t current_time,
    uint64_t max_position,
    const IntegratedConfig& config
) {
    float score = 0.0f;

    // Signal 1: Recency
    float age = (float)(current_time - page.last_access_time);
    float recency = expf(-0.693f * age / 100.0f);
    score += config.weight_recency * recency;

    // Signal 2: Frequency
    float freq = fminf(1.0f, (float)page.access_count / (float)config.frequency_window);
    float frequency = log1pf(freq * 10.0f) / log1pf(10.0f);
    score += config.weight_frequency * frequency;

    // Signal 3: Attention strength
    // Use reuse_score as proxy for average attention weight
    float avg_attn = page.reuse_score;
    float baseline = 1.0f / 1000.0f;
    float strength = (baseline > 0.0f) ? avg_attn / baseline : 0.0f;
    float attention = 1.0f / (1.0f + expf(-0.5f * (strength - 5.0f)));
    score += config.weight_attention_strength * attention;

    // Signal 4: Token importance
    uint8_t token_type = page.compression_bits < 8 ?
        page.compression_bits : TOKEN_REGULAR;  // Reuse field for token type in this context
    float importance = c_token_importance[token_type < 8 ? token_type : TOKEN_REGULAR];
    score += config.weight_token_importance * importance;

    // Signal 5: Position (sinks + recent window)
    uint64_t position = page.page_id;
    float position_score = 0.3f;
    if (position < config.attention_sink_tokens) {
        position_score = 1.0f;
    } else if (max_position > config.recent_window_size &&
               position > max_position - config.recent_window_size) {
        float recency_bonus = 1.0f - (float)(max_position - position)
                              / (float)config.recent_window_size;
        position_score = fmaxf(position_score, recency_bonus);
    }
    score += config.weight_position * position_score;

    // Signal 6: Compression quality (quality-aware mode)
    if (config.mode == IntegrationMode::QUALITY_AWARE &&
        (page.flags & CTM_PAGE_TQ_COMPRESSED)) {
        float quality_penalty = 1.0f - page.cosine_similarity;
        score += config.weight_compression_quality * quality_penalty;
    }

    return score;
}

/* ========== Kernel Implementations ========== */

__global__ void kernel_integrated_access(
    PageState*          pages,
    const uint64_t*     access_page_ids,
    const uint8_t*      token_types,
    const float*        attention_weights,
    uint32_t            num_accesses,
    uint64_t            current_time,
    IntegratedConfig    config,
    IntegratedStats*    stats,
    uint8_t*            hit_tiers
) {
    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= num_accesses) return;

    uint64_t page_id = access_page_ids[idx];
    uint8_t token_type = token_types ? token_types[idx] : TOKEN_REGULAR;
    float attn_weight = attention_weights ? attention_weights[idx] : 0.01f;

    // Hash-based lookup
    uint32_t hash_mask = (1u << CTM_HASH_BITS) - 1;
    uint32_t hash_idx = hash_page_id(page_id, CTM_HASH_BITS);

    PageState* page = nullptr;
    for (uint32_t probe = 0; probe < 16; probe++) {
        uint32_t slot = (hash_idx + probe) & hash_mask;
        PageState* candidate = &pages[slot];
        if (candidate->page_id == page_id || candidate->page_id == 0) {
            page = candidate;
            break;
        }
    }
    if (!page) {
        page = &pages[hash_idx];
    }

    atomicAdd((unsigned long long*)&stats->total_accesses, 1);

    bool is_new = (page->page_id != page_id);

    if (!is_new) {
        // Existing page — determine which tier
        bool in_tier0 = (page->flags & CTM_PAGE_IN_TIER0) != 0;
        bool in_cxl   = (page->flags & CTM_PAGE_IN_CXL) != 0;
        bool in_tier1 = (page->flags & CTM_PAGE_IN_TIER1) != 0;

        // Update access metadata
        atomicAdd(&page->access_count, 1);
        page->last_access_time = current_time + idx;

        // Update attention weight (exponential moving average via reuse_score)
        float alpha = 0.1f;
        page->reuse_score = (1.0f - alpha) * page->reuse_score + alpha * attn_weight;

        if (in_tier0) {
            // Tier0 hit (HBM, FP16) — best case
            atomicAdd((unsigned long long*)&stats->tier0_hits, 1);
            hit_tiers[idx] = 0;
        } else if (in_cxl) {
            // CXL hit (TQ-compressed) — requires decompression for attention
            atomicAdd((unsigned long long*)&stats->cxl_hits, 1);
            hit_tiers[idx] = 1;

            // Check for promotion to Tier0 (frequently accessed)
            if (page->access_count > 3) {
                page->flags &= ~CTM_PAGE_IN_CXL;
                page->flags |= CTM_PAGE_IN_TIER0;
                atomicAdd((unsigned long long*)&stats->cxl_to_tier0, 1);
                atomicAdd((unsigned long long*)&stats->tq_decompressions, 1);
            }
        } else if (in_tier1) {
            // Tier1 hit (NVMe) — expensive, promote
            atomicAdd((unsigned long long*)&stats->tier1_hits, 1);
            hit_tiers[idx] = 2;

            // Promote to CXL (compress) or Tier0 based on access pattern
            if (config.mode != IntegrationMode::CAPACITY_ONLY) {
                page->flags &= ~CTM_PAGE_IN_TIER1;
                page->flags |= CTM_PAGE_IN_CXL;
                page->flags |= CTM_PAGE_TQ_COMPRESSED;
                atomicAdd((unsigned long long*)&stats->tier1_to_cxl, 1);
                atomicAdd((unsigned long long*)&stats->tq_compressions, 1);
            } else {
                page->flags &= ~CTM_PAGE_IN_TIER1;
                page->flags |= CTM_PAGE_IN_TIER0;
            }
        }
    } else {
        // New page — cache miss, admit to Tier0
        atomicAdd((unsigned long long*)&stats->misses, 1);
        hit_tiers[idx] = 3;

        page->page_id = page_id;
        page->flags = CTM_PAGE_IN_TIER0;
        page->access_count = 1;
        page->last_access_time = current_time + idx;
        page->reuse_score = attn_weight;
        page->coherence = 0.5f;
        page->phase = 0.0f;
        page->amplitude = 0.0f;

        // Initialize compression quality fields
        page->compression_mse = 0.0f;
        page->cosine_similarity = 1.0f;
        page->original_norm = 1.0f;
        page->compression_bits = 0;
    }
}

__global__ void kernel_integrated_select_victims(
    const PageState*    pages,
    const uint64_t*     tier0_pages,
    uint32_t            tier0_size,
    IntegratedConfig    config,
    uint64_t            current_time,
    uint64_t*           victim_ids,
    uint32_t            num_victims,
    curandState*        rng_states
) {
    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= num_victims) return;

    curandState local_state = rng_states[idx];

    // Find max position for position scoring
    uint64_t max_position = 0;
    uint32_t scan_limit = min(tier0_size, config.victim_sample_size);
    for (uint32_t i = 0; i < scan_limit; i++) {
        uint64_t pid = tier0_pages[i];
        if (pid > max_position) max_position = pid;
    }

    // Sample and score using CTM+ multi-signal scoring
    float best_score = 1e30f;
    uint64_t best_victim = 0;

    uint32_t samples = min(config.victim_sample_size, tier0_size);
    for (uint32_t s = 0; s < samples; s++) {
        uint32_t rand_idx = curand(&local_state) % tier0_size;
        uint64_t pid = tier0_pages[rand_idx];
        uint32_t hash = hash_page_id(pid, CTM_HASH_BITS);
        const PageState& page = pages[hash];

        float score = integrated_score(page, current_time, max_position, config);

        if (score < best_score) {
            best_score = score;
            best_victim = pid;
        }
    }

    victim_ids[idx] = best_victim;
    rng_states[idx] = local_state;
}

__global__ void kernel_update_compression_quality(
    PageState*          pages,
    const uint64_t*     page_ids,
    const float*        mse_values,
    const float*        cosine_values,
    const float*        norm_values,
    uint32_t            num_pages,
    uint8_t             compression_bits
) {
    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= num_pages) return;

    uint64_t page_id = page_ids[idx];
    uint32_t hash = hash_page_id(page_id, CTM_HASH_BITS);
    PageState* page = &pages[hash];

    // Verify this is the correct page
    if (page->page_id == page_id) {
        page->compression_mse = mse_values[idx];
        page->cosine_similarity = cosine_values[idx];
        page->original_norm = norm_values[idx];
        page->compression_bits = compression_bits;
        page->flags |= CTM_PAGE_TQ_COMPRESSED;
    }
}

/* ========== IntegratedController Implementation ========== */

void IntegratedController::init_device_memory() {
    size_t hash_size = 1 << CTM_HASH_BITS;

    // Page state table
    cudaMalloc(&d_pages_, hash_size * sizeof(PageState));
    cudaMemset(d_pages_, 0, hash_size * sizeof(PageState));

    // Statistics
    cudaMalloc(&d_stats_, sizeof(IntegratedStats));
    cudaMemset(d_stats_, 0, sizeof(IntegratedStats));

    // RNG states for victim selection
    uint32_t rng_count = 256;
    cudaMalloc(&d_rng_states_, rng_count * sizeof(curandState));
    // Initialize RNG
    int block_size = 256;
    int num_blocks = (rng_count + block_size - 1) / block_size;
    // Use a simple init kernel via extern linkage from ctm_plus.cu
    // For now, use curand_init inline
    // We'll launch the init kernel defined in ctm_plus.cu
    kernel_init_rng<<<num_blocks, block_size, 0, stream_>>>(
        d_rng_states_, (uint64_t)42, rng_count);

    // Tier tracking arrays
    cudaMalloc(&d_tier0_pages_,
               config_.tier0_capacity_tokens * sizeof(uint64_t));
    uint32_t cxl_cap = config_.effective_cxl_capacity();
    cudaMalloc(&d_cxl_pages_, cxl_cap * sizeof(uint64_t));

    // CXL compressed storage
    int total_angles = config_.tq_config.total_angles();
    cudaMalloc(&d_cxl_indices_,
               (size_t)cxl_cap * total_angles * sizeof(unsigned char));
    cudaMalloc(&d_cxl_radii_, cxl_cap * sizeof(float));

    // QJL storage (optional)
    if (config_.tq_config.enable_qjl) {
        int proj_dim = config_.tq_config.qjl_proj_dim > 0
            ? config_.tq_config.qjl_proj_dim : config_.tq_config.head_dim;
        int words_per_vec = (proj_dim + 31) / 32;
        cudaMalloc(&d_cxl_qjl_bits_,
                   (size_t)cxl_cap * words_per_vec * sizeof(uint32_t));
        cudaMalloc(&d_cxl_qjl_scales_, cxl_cap * sizeof(float));
    } else {
        d_cxl_qjl_bits_ = nullptr;
        d_cxl_qjl_scales_ = nullptr;
    }
}

IntegratedController::IntegratedController(const IntegratedConfig& config,
                                           cudaStream_t stream)
    : config_(config), stream_(stream),
      d_pages_(nullptr), d_stats_(nullptr), d_rng_states_(nullptr),
      d_tier0_pages_(nullptr), d_cxl_pages_(nullptr),
      d_cxl_indices_(nullptr), d_cxl_radii_(nullptr),
      d_cxl_qjl_bits_(nullptr), d_cxl_qjl_scales_(nullptr),
      tier0_size_(0), cxl_size_(0), access_counter_(0)
{
    memset(&h_stats_, 0, sizeof(h_stats_));

    // Create TurboQuant engine
    tq_engine_ = new TurboQuantEngine(config.tq_config, stream);

    // Initialize device memory
    init_device_memory();

    printf("CTM+ Integrated Controller initialized:\n");
    printf("  Tier0 (HBM):  %u tokens (FP16)\n", config.tier0_capacity_tokens);
    printf("  CXL (CTXL):   %u tokens (TQ-%dbit, %.1fx compression)\n",
           config.effective_cxl_capacity(),
           config.tq_config.angle_bits,
           config.tq_config.compression_ratio());
    printf("  Total:         %u effective tokens\n",
           config.total_effective_tokens());
    printf("  Mode:          %s\n",
           config.mode == IntegrationMode::QUALITY_AWARE
               ? "quality-aware" : "capacity-only");
}

IntegratedController::~IntegratedController() {
    delete tq_engine_;

    if (d_pages_)          cudaFree(d_pages_);
    if (d_stats_)          cudaFree(d_stats_);
    if (d_rng_states_)     cudaFree(d_rng_states_);
    if (d_tier0_pages_)    cudaFree(d_tier0_pages_);
    if (d_cxl_pages_)      cudaFree(d_cxl_pages_);
    if (d_cxl_indices_)    cudaFree(d_cxl_indices_);
    if (d_cxl_radii_)      cudaFree(d_cxl_radii_);
    if (d_cxl_qjl_bits_)   cudaFree(d_cxl_qjl_bits_);
    if (d_cxl_qjl_scales_) cudaFree(d_cxl_qjl_scales_);
}

void IntegratedController::access_batch(
    const uint64_t* d_page_ids,
    const uint8_t* d_token_types,
    const float* d_attn_weights,
    uint32_t num_accesses,
    uint8_t* d_hit_tiers
) {
    uint32_t block_size = 256;
    uint32_t num_blocks = (num_accesses + block_size - 1) / block_size;

    kernel_integrated_access<<<num_blocks, block_size, 0, stream_>>>(
        d_pages_,
        d_page_ids,
        d_token_types,
        d_attn_weights,
        num_accesses,
        access_counter_,
        config_,
        d_stats_,
        d_hit_tiers
    );

    access_counter_ += num_accesses;
}

void IntegratedController::compress_to_cxl(
    const float* d_vectors,
    const uint64_t* d_page_ids,
    int batch
) {
    // Compress vectors using TurboQuant engine
    int total_angles = config_.tq_config.total_angles();

    // Allocate temporary buffers for this batch
    unsigned char* d_batch_indices;
    float* d_batch_radii;
    cudaMalloc(&d_batch_indices, (size_t)batch * total_angles * sizeof(unsigned char));
    cudaMalloc(&d_batch_radii, batch * sizeof(float));

    tq_engine_->compress_batch(d_vectors, batch, d_batch_indices, d_batch_radii);

    // Compute quality metrics
    float* d_reconstructed;
    float* d_mse;
    float* d_cosine;
    cudaMalloc(&d_reconstructed, (size_t)batch * config_.tq_config.head_dim * sizeof(float));
    cudaMalloc(&d_mse, batch * sizeof(float));
    cudaMalloc(&d_cosine, batch * sizeof(float));

    // Decompress for quality measurement
    tq_engine_->decompress_batch(d_batch_radii, d_batch_indices,
                                  batch, d_reconstructed);

    // Compute quality
    tq_engine_->compute_quality_batch(d_vectors, d_reconstructed, batch,
                                       d_mse, d_cosine);

    // Compute norms
    float* d_norms;
    cudaMalloc(&d_norms, batch * sizeof(float));
    // Simple norm computation — reuse quality kernel output
    // For now, set norms to 1.0 (we could add a dedicated kernel)
    cudaMemset(d_norms, 0, batch * sizeof(float));

    // Update page compression quality
    uint32_t block_size = 256;
    uint32_t num_blocks = (batch + block_size - 1) / block_size;
    kernel_update_compression_quality<<<num_blocks, block_size, 0, stream_>>>(
        d_pages_, d_page_ids,
        d_mse, d_cosine, d_norms,
        batch, config_.tq_config.angle_bits
    );

    // QJL residual compression (if enabled)
    if (config_.tq_config.enable_qjl) {
        // Compute residuals: original - reconstructed
        // For simplicity, we skip the residual subtraction kernel here
        // and note that the full pipeline would include it
    }

    // Cleanup temporary buffers
    cudaFree(d_batch_indices);
    cudaFree(d_batch_radii);
    cudaFree(d_reconstructed);
    cudaFree(d_mse);
    cudaFree(d_cosine);
    cudaFree(d_norms);
}

void IntegratedController::decompress_from_cxl(
    const uint64_t* d_page_ids,
    int batch,
    float* d_vectors
) {
    int total_angles = config_.tq_config.total_angles();

    // Allocate temporary compressed buffers
    unsigned char* d_indices;
    float* d_radii;
    cudaMalloc(&d_indices, (size_t)batch * total_angles * sizeof(unsigned char));
    cudaMalloc(&d_radii, batch * sizeof(float));

    // Look up CXL storage slot for each page via its hash.
    // For each page_id, find its PageState → read cxl_slot_ index,
    // then gather from d_cxl_indices_ and d_cxl_radii_.
    //
    // This requires a gather kernel that:
    //   1. For each page_id, hash → PageState → slot index
    //   2. Copy d_cxl_indices_[slot * total_angles .. +total_angles] → d_indices[i*ta..]
    //   3. Copy d_cxl_radii_[slot] → d_radii[i]
    //
    // For now we use host-side gathering via cudaMemcpy per page.
    // In production, replace with a single gather kernel.
    {
        uint64_t* h_page_ids = new uint64_t[batch];
        cudaMemcpy(h_page_ids, d_page_ids, batch * sizeof(uint64_t),
                   cudaMemcpyDeviceToHost);

        uint32_t hash_mask = (1u << CTM_HASH_BITS) - 1;
        for (int i = 0; i < batch; i++) {
            uint32_t hash = hash_page_id(h_page_ids[i], CTM_HASH_BITS);

            // Read the page slot.  In the current design the CXL slot is
            // simply the page's hash index (1-to-1 mapping).  A production
            // allocator would use a freelist like MultimodalInferenceController.
            uint32_t cxl_slot = hash & hash_mask;
            if (cxl_slot < config_.effective_cxl_capacity()) {
                cudaMemcpy(d_indices + (size_t)i * total_angles,
                           d_cxl_indices_ + (size_t)cxl_slot * total_angles,
                           total_angles * sizeof(unsigned char),
                           cudaMemcpyDeviceToDevice);
                cudaMemcpy(d_radii + i,
                           d_cxl_radii_ + cxl_slot,
                           sizeof(float),
                           cudaMemcpyDeviceToDevice);
            }
        }
        delete[] h_page_ids;
    }

    tq_engine_->decompress_batch(d_radii, d_indices, batch, d_vectors);

    cudaFree(d_indices);
    cudaFree(d_radii);
}

void IntegratedController::select_and_demote_victims(uint32_t num_victims) {
    if (tier0_size_ == 0 || num_victims == 0) return;

    num_victims = min(num_victims, tier0_size_);

    // Allocate victim IDs on device
    uint64_t* d_victim_ids;
    cudaMalloc(&d_victim_ids, num_victims * sizeof(uint64_t));

    // Launch victim selection kernel
    uint32_t block_size = 256;
    uint32_t num_blocks = (num_victims + block_size - 1) / block_size;

    kernel_integrated_select_victims<<<num_blocks, block_size, 0, stream_>>>(
        d_pages_,
        d_tier0_pages_,
        tier0_size_,
        config_,
        access_counter_,
        d_victim_ids,
        num_victims,
        d_rng_states_
    );

    // For each victim: compress to CXL, update tier tracking
    // Read victim page IDs to host for orchestration
    uint64_t* h_victims = new uint64_t[num_victims];
    cudaMemcpyAsync(h_victims, d_victim_ids, num_victims * sizeof(uint64_t),
                    cudaMemcpyDeviceToHost, stream_);
    cudaStreamSynchronize(stream_);

    // Batch compress victims to CXL
    // In production: allocate CXL slots, compress vectors, update flags.
    // Here we update the page flags to mark as CXL-resident.
    uint32_t hash_mask = (1u << CTM_HASH_BITS) - 1;
    for (uint32_t i = 0; i < num_victims; i++) {
        uint32_t hash = hash_page_id(h_victims[i], CTM_HASH_BITS);
        uint32_t slot = hash & hash_mask;

        // Update page flags: clear TIER0, set CXL
        PageState h_page;
        cudaMemcpy(&h_page, &d_pages_[slot], sizeof(PageState),
                   cudaMemcpyDeviceToHost);

        if (h_page.page_id == h_victims[i] &&
            (h_page.flags & CTM_PAGE_IN_TIER0)) {
            h_page.flags &= ~CTM_PAGE_IN_TIER0;
            h_page.flags |= CTM_PAGE_IN_CXL | CTM_PAGE_TQ_COMPRESSED;
            cudaMemcpy(&d_pages_[slot], &h_page, sizeof(PageState),
                       cudaMemcpyHostToDevice);
            cxl_size_++;
            if (tier0_size_ > 0) tier0_size_--;
        }
    }

    delete[] h_victims;
    cudaFree(d_victim_ids);
}

IntegratedStats IntegratedController::get_stats() {
    cudaMemcpyAsync(&h_stats_, d_stats_, sizeof(IntegratedStats),
                    cudaMemcpyDeviceToHost, stream_);
    cudaStreamSynchronize(stream_);

    // Compute averages
    uint64_t n = h_stats_.tq_compressions;
    if (n > 0) {
        // These would be accumulated by the quality kernel
        // For now, report the raw stats
    }

    h_stats_.tier0_occupancy = tier0_size_;
    h_stats_.cxl_occupancy = cxl_size_;

    return h_stats_;
}

void IntegratedController::reset_stats() {
    cudaMemsetAsync(d_stats_, 0, sizeof(IntegratedStats), stream_);
    memset(&h_stats_, 0, sizeof(h_stats_));
}

void IntegratedController::synchronize() {
    cudaStreamSynchronize(stream_);
}

} // namespace ctm
