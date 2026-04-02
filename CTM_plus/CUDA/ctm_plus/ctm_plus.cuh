/*
 * CTM+ CUDA Implementation
 *
 * GPU-accelerated memory tiering controller for:
 * - HBM vs GDDR management
 * - Unified Memory page placement
 * - Multi-GPU memory tiering
 *
 * SPDX-License-Identifier: MIT
 */

#ifndef CTM_PLUS_CUH
#define CTM_PLUS_CUH

#include <cuda_runtime.h>
#include <cstdint>

namespace ctm {

/* Configuration constants */
constexpr int CTM_VICTIM_SAMPLE_SIZE = 48;
constexpr int CTM_SHADOW_MAX_SIZE = 1024;
constexpr int CTM_NEIGHBOR_WINDOW = 16;
constexpr int CTM_HASH_BITS = 16;
constexpr float CTM_PROMOTION_THRESHOLD = 0.3f;
constexpr float CTM_LOOP_PIN_REUSE_THRESH = 0.4f;
constexpr float CTM_LOOP_PIN_NEIGHBOR_THRESH = 0.3f;

/* Page state flags */
constexpr uint32_t CTM_PAGE_IN_TIER0 = 1 << 0;   // HBM (FP16)
constexpr uint32_t CTM_PAGE_IN_TIER1 = 1 << 1;   // NVMe / slow tier
constexpr uint32_t CTM_PAGE_HOT = 1 << 2;
constexpr uint32_t CTM_PAGE_PINNED = 1 << 3;
constexpr uint32_t CTM_PAGE_IN_CXL = 1 << 4;     // CXL tier (TQ-compressed)
constexpr uint32_t CTM_PAGE_TQ_COMPRESSED = 1 << 5; // Has TurboQuant compressed data

/**
 * Per-page state (GPU-resident)
 */
struct __align__(64) PageState {
    uint64_t page_id;
    uint32_t flags;
    uint32_t access_count;
    uint64_t last_access_time;
    float phase;
    float amplitude;
    float coherence;
    float reuse_score;

    // TurboQuant compression quality (for quality-aware eviction)
    float compression_mse;        // MSE between original and reconstructed
    float cosine_similarity;      // 1.0 = perfect compression
    float original_norm;          // L2 norm of original KV vector
    uint8_t compression_bits;     // Bit-width used (2/3/4)
};

/**
 * Shadow tier entry for ghost caches
 */
struct ShadowEntry {
    uint64_t page_id;
    uint64_t evict_time;
    bool from_tier0;
};

/**
 * CTM+ Configuration
 */
struct Config {
    uint32_t victim_sample_size = CTM_VICTIM_SAMPLE_SIZE;
    float promotion_threshold = CTM_PROMOTION_THRESHOLD;
    float loop_pin_reuse_thresh = CTM_LOOP_PIN_REUSE_THRESH;
    float loop_pin_neighbor_thresh = CTM_LOOP_PIN_NEIGHBOR_THRESH;
    bool enable_smart_victim = true;

    // TurboQuant + CTXL integration
    bool enable_quality_aware_eviction = false;
    float weight_compression_quality = 0.05f;  // Weight for compression quality in scoring
    bool enable_cxl_tier = false;              // Enable CXL (CTXL) warm tier
    uint32_t cxl_capacity = 0;                 // CXL tier capacity (pages)
};

/**
 * CTM+ Statistics
 */
struct Stats {
    uint64_t tier0_hits;
    uint64_t tier1_hits;
    uint64_t cxl_hits;           // CXL tier hits
    uint64_t misses;
    uint64_t promotions;
    uint64_t demotions;
    uint64_t cxl_promotions;     // CXL -> Tier0 promotions
    uint64_t cxl_demotions;      // Tier0 -> CXL demotions
    uint64_t smart_selections;
    uint64_t tq_compressions;    // TurboQuant compressions performed
    uint64_t tq_decompressions;  // TurboQuant decompressions performed
};

/**
 * CTM+ Controller (Host-side handle)
 */
class Controller {
public:
    /**
     * Initialize controller
     * @param tier0_capacity Max pages in fast tier (HBM)
     * @param tier1_capacity Max pages in slow tier (GDDR/host)
     * @param stream CUDA stream for async operations
     */
    Controller(uint32_t tier0_capacity, uint32_t tier1_capacity,
               cudaStream_t stream = 0);
    ~Controller();

    // Disable copy
    Controller(const Controller&) = delete;
    Controller& operator=(const Controller&) = delete;

    /**
     * Process a batch of page accesses (async)
     * @param page_ids Device pointer to page IDs
     * @param num_pages Number of pages in batch
     * @param promotions Output: device pointer for promotion flags
     * @param demotions Output: device pointer for demotion flags
     */
    void on_access_batch(const uint64_t* page_ids, uint32_t num_pages,
                         bool* promotions, bool* demotions);

    /**
     * Select victims for eviction (async)
     * @param num_victims Number of victims to select
     * @param victim_ids Output: device pointer for victim page IDs
     */
    void select_victims(uint32_t num_victims, uint64_t* victim_ids);

    /**
     * Synchronize and get statistics
     */
    Stats get_stats();

    /**
     * Reset statistics
     */
    void reset_stats();

    /**
     * Update configuration
     */
    void set_config(const Config& config);

    /**
     * Get current configuration
     */
    Config get_config() const;

    /**
     * Check if page is in tier0
     */
    bool is_in_tier0(uint64_t page_id);

    /**
     * Get tier for a page (-1 if not tracked)
     */
    int get_tier(uint64_t page_id);

    /**
     * Force synchronization
     */
    void synchronize();

private:
    struct Impl;
    Impl* impl_;
};

/* ========== CUDA Kernels (for advanced users) ========== */

/**
 * Kernel: Process page accesses
 */
__global__ void kernel_on_access(
    PageState* pages,
    uint32_t* page_hash,
    uint64_t* tier0_lru,
    uint64_t* tier1_lru,
    const uint64_t* access_page_ids,
    uint32_t num_accesses,
    uint64_t current_time,
    Config config,
    Stats* stats,
    bool* promotions,
    bool* demotions
);

/**
 * Kernel: Select victims using smart sampling
 */
__global__ void kernel_select_victims(
    const PageState* pages,
    const uint64_t* tier0_lru,
    uint32_t tier0_size,
    uint32_t sample_size,
    float adaptive_p,
    uint64_t* victim_ids,
    uint32_t num_victims,
    curandState* rng_states
);

/**
 * Kernel: Compute neighbor hotness
 */
__global__ void kernel_compute_neighbor_hotness(
    const PageState* pages,
    const uint64_t* recent_accesses,
    uint32_t window_size,
    float* hotness_out,
    uint32_t num_pages
);

/**
 * Kernel: Update shadow tiers
 */
__global__ void kernel_update_shadow(
    ShadowEntry* shadow_b1,
    ShadowEntry* shadow_b2,
    uint32_t* shadow_sizes,
    uint64_t evicted_page_id,
    bool from_tier0,
    uint64_t current_time
);

/**
 * Kernel: Quality-aware victim selection (TurboQuant + CTM+ integration)
 */
__global__ void kernel_select_victims_quality_aware(
    const PageState* pages,
    const uint64_t* tier0_lru,
    uint32_t tier0_size,
    uint32_t sample_size,
    float adaptive_p,
    float weight_compression_quality,
    uint64_t* victim_ids,
    uint32_t num_victims,
    curandState* rng_states,
    bool* demote_to_cxl
);

/* ========== Utility Functions ========== */

/**
 * Initialize CUDA device for CTM+
 * @param device_id CUDA device ID
 * @return true on success
 */
bool initialize_device(int device_id = 0);

/**
 * Get device memory info
 * @param free_bytes Output: free memory
 * @param total_bytes Output: total memory
 */
void get_memory_info(size_t* free_bytes, size_t* total_bytes);

/**
 * Allocate managed memory with CTM+ hints
 * @param ptr Output pointer
 * @param size Allocation size
 * @param preferred_tier Preferred initial tier (0 or 1)
 */
cudaError_t ctm_malloc_managed(void** ptr, size_t size, int preferred_tier = 0);

/**
 * Free managed memory
 */
cudaError_t ctm_free(void* ptr);

} // namespace ctm

#endif // CTM_PLUS_CUH
