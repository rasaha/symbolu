/*
 * CTM+ CUDA Implementation
 *
 * GPU-accelerated memory tiering controller.
 *
 * SPDX-License-Identifier: MIT
 */

#include "ctm_plus.cuh"
#include <cuda.h>
#include <curand_kernel.h>
#include <cstdio>
#include <algorithm>

namespace ctm {

/* ========== Device Helper Functions ========== */

__device__ __forceinline__ uint32_t hash_page_id(uint64_t page_id, uint32_t bits) {
    // MurmurHash-like mixing
    uint64_t h = page_id;
    h ^= h >> 33;
    h *= 0xff51afd7ed558ccdULL;
    h ^= h >> 33;
    h *= 0xc4ceb9fe1a85ec53ULL;
    h ^= h >> 33;
    return (uint32_t)(h & ((1 << bits) - 1));
}

__device__ __forceinline__ float compute_victim_score(
    const PageState& page,
    uint64_t min_time,
    uint64_t time_range,
    float adaptive_p,
    float neighbor_hotness
) {
    // Normalize recency to [0, 1]
    float recency = time_range > 0 ?
        (float)(page.last_access_time - min_time) / (float)time_range : 0.5f;

    // Frequency score
    float frequency = fminf(page.access_count * 0.1f, 1.0f);

    // Weighted score (lower = evict first)
    float score = 0.40f * recency +
                  0.30f * frequency +
                  0.15f * page.reuse_score +
                  0.10f * page.coherence -
                  0.10f * neighbor_hotness;

    // Partition penalty based on adaptive p
    if (adaptive_p > 0.5f && frequency < 0.3f) {
        score -= 0.10f * (adaptive_p - 0.5f) * 2.0f;
    } else if (adaptive_p < 0.5f && recency < 0.3f) {
        score -= 0.10f * (0.5f - adaptive_p) * 2.0f;
    }

    return score;
}

/**
 * Quality-aware victim scoring for TurboQuant + CTM+ integration.
 *
 * Extends the base CTM+ scoring with a compression quality signal:
 * tokens that compressed poorly get a small boost (higher score =
 * less likely evicted) because evicting them loses more information.
 *
 * Matches the vLLM turboquant_integration.py scoring model.
 */
__device__ __forceinline__ float compute_victim_score_quality_aware(
    const PageState& page,
    uint64_t min_time,
    uint64_t time_range,
    float adaptive_p,
    float neighbor_hotness,
    float weight_compression_quality
) {
    float base_score = compute_victim_score(
        page, min_time, time_range, adaptive_p, neighbor_hotness);

    // Quality-aware: tokens that compressed poorly are more valuable
    // to keep (eviction = more information loss)
    if (page.flags & CTM_PAGE_TQ_COMPRESSED) {
        float quality_penalty = 1.0f - page.cosine_similarity;
        base_score += weight_compression_quality * quality_penalty;
    }

    return base_score;
}

/* ========== CUDA Kernels ========== */

__global__ void kernel_init_rng(curandState* states, uint64_t seed, uint32_t n) {
    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < n) {
        curand_init(seed, idx, 0, &states[idx]);
    }
}

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
) {
    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= num_accesses) return;

    uint64_t page_id = access_page_ids[idx];
    uint32_t hash_idx = hash_page_id(page_id, CTM_HASH_BITS);
    uint32_t hash_mask = (1u << CTM_HASH_BITS) - 1;

    // Linear probing to find existing slot or empty slot
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
        // Hash table full in local neighborhood, fall back to base slot
        page = &pages[hash_idx];
    }

    // Initialize if new page
    if (page->page_id != page_id) {
        page->page_id = page_id;
        page->flags = 0;
        page->access_count = 0;
        page->coherence = 0.5f;
        page->reuse_score = 0.0f;
    }

    // Update page state
    atomicAdd(&page->access_count, 1);
    page->last_access_time = current_time + idx;

    bool in_tier0 = (page->flags & CTM_PAGE_IN_TIER0) != 0;
    bool in_tier1 = (page->flags & CTM_PAGE_IN_TIER1) != 0;

    promotions[idx] = false;
    demotions[idx] = false;

    bool in_cxl = (page->flags & CTM_PAGE_IN_CXL) != 0;

    if (in_tier0) {
        // Hit in tier0 (HBM, FP16)
        atomicAdd((unsigned long long*)&stats->tier0_hits, 1);
    } else if (in_cxl) {
        // Hit in CXL tier (TQ-compressed) — check for promotion to tier0
        atomicAdd((unsigned long long*)&stats->cxl_hits, 1);

        float reuse = page->reuse_score;
        float neighbor_hot = page->coherence;

        // CXL -> Tier0 promotion: decompress and move to HBM
        bool should_promote = false;
        float combined = 0.5f * reuse + 0.3f * page->coherence + 0.2f * neighbor_hot;
        if (combined > config.promotion_threshold || page->access_count > 3) {
            should_promote = true;
        }

        if (should_promote) {
            page->flags &= ~CTM_PAGE_IN_CXL;
            page->flags |= CTM_PAGE_IN_TIER0;
            atomicAdd((unsigned long long*)&stats->cxl_promotions, 1);
            atomicAdd((unsigned long long*)&stats->tq_decompressions, 1);
            promotions[idx] = true;
        }
    } else if (in_tier1) {
        // Hit in tier1 (NVMe) - check for promotion
        atomicAdd((unsigned long long*)&stats->tier1_hits, 1);

        float reuse = page->reuse_score;
        float neighbor_hot = page->coherence;

        bool should_promote = false;
        if (reuse > config.loop_pin_reuse_thresh &&
            neighbor_hot > config.loop_pin_neighbor_thresh) {
            should_promote = true;
        } else {
            float combined = 0.5f * reuse + 0.3f * page->coherence + 0.2f * neighbor_hot;
            should_promote = combined > config.promotion_threshold;
        }

        if (should_promote) {
            page->flags &= ~CTM_PAGE_IN_TIER1;
            // If CXL tier is enabled, promote to CXL first (compressed)
            if (config.enable_cxl_tier) {
                page->flags |= CTM_PAGE_IN_CXL;
                page->flags |= CTM_PAGE_TQ_COMPRESSED;
                atomicAdd((unsigned long long*)&stats->tq_compressions, 1);
            } else {
                page->flags |= CTM_PAGE_IN_TIER0;
            }
            atomicAdd((unsigned long long*)&stats->promotions, 1);
            promotions[idx] = true;
        }
    } else {
        // Miss - admit to tier0
        atomicAdd((unsigned long long*)&stats->misses, 1);
        page->flags |= CTM_PAGE_IN_TIER0;
        promotions[idx] = true;
    }
}

__global__ void kernel_select_victims(
    const PageState* pages,
    const uint64_t* tier0_lru,
    uint32_t tier0_size,
    uint32_t sample_size,
    float adaptive_p,
    uint64_t* victim_ids,
    uint32_t num_victims,
    curandState* rng_states
) {
    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= num_victims) return;

    curandState local_state = rng_states[idx];

    // Find time range by sampling up to sample_size entries (bounded scan)
    uint64_t min_time = UINT64_MAX, max_time = 0;
    uint32_t scan_limit = min(tier0_size, sample_size);
    for (uint32_t i = 0; i < scan_limit; i++) {
        uint64_t pid = tier0_lru[i];
        uint32_t hash = hash_page_id(pid, CTM_HASH_BITS);
        const PageState& p = pages[hash];
        if (p.last_access_time < min_time) min_time = p.last_access_time;
        if (p.last_access_time > max_time) max_time = p.last_access_time;
    }
    uint64_t time_range = max_time - min_time;

    // Sample and score
    float best_score = 1e30f;
    uint64_t best_victim = 0;

    uint32_t samples = min(sample_size, tier0_size);
    for (uint32_t s = 0; s < samples; s++) {
        uint32_t rand_idx = curand(&local_state) % tier0_size;
        uint64_t pid = tier0_lru[rand_idx];
        uint32_t hash = hash_page_id(pid, CTM_HASH_BITS);
        const PageState& page = pages[hash];

        float score = compute_victim_score(page, min_time, time_range, adaptive_p, page.coherence);

        if (score < best_score) {
            best_score = score;
            best_victim = pid;
        }
    }

    victim_ids[idx] = best_victim;
    rng_states[idx] = local_state;
}

/**
 * Quality-aware victim selection kernel for TurboQuant + CTM+ integration.
 *
 * Uses compression quality metrics in scoring, so tokens that compressed
 * poorly are protected from eviction (evicting them loses more information).
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
    bool* demote_to_cxl  // Output: whether victim should go to CXL instead of evict
) {
    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= num_victims) return;

    curandState local_state = rng_states[idx];

    uint64_t min_time = UINT64_MAX, max_time = 0;
    uint32_t scan_limit = min(tier0_size, sample_size);
    for (uint32_t i = 0; i < scan_limit; i++) {
        uint64_t pid = tier0_lru[i];
        uint32_t hash = hash_page_id(pid, CTM_HASH_BITS);
        const PageState& p = pages[hash];
        if (p.last_access_time < min_time) min_time = p.last_access_time;
        if (p.last_access_time > max_time) max_time = p.last_access_time;
    }
    uint64_t time_range = max_time - min_time;

    float best_score = 1e30f;
    uint64_t best_victim = 0;
    float best_cosine = 1.0f;

    uint32_t samples = min(sample_size, tier0_size);
    for (uint32_t s = 0; s < samples; s++) {
        uint32_t rand_idx = curand(&local_state) % tier0_size;
        uint64_t pid = tier0_lru[rand_idx];
        uint32_t hash = hash_page_id(pid, CTM_HASH_BITS);
        const PageState& page = pages[hash];

        float score = compute_victim_score_quality_aware(
            page, min_time, time_range, adaptive_p,
            page.coherence, weight_compression_quality);

        if (score < best_score) {
            best_score = score;
            best_victim = pid;
            best_cosine = page.cosine_similarity;
        }
    }

    victim_ids[idx] = best_victim;
    // Demote to CXL if the token compresses well (high cosine similarity)
    demote_to_cxl[idx] = (best_cosine > 0.9f);
    rng_states[idx] = local_state;
}

__global__ void kernel_compute_neighbor_hotness(
    const PageState* pages,
    const uint64_t* recent_accesses,
    uint32_t window_size,
    float* hotness_out,
    uint32_t num_pages
) {
    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= num_pages) return;

    uint64_t page_id = recent_accesses[idx % window_size];
    uint32_t in_tier0 = 0, total = 0;

    for (uint32_t i = 0; i < window_size; i++) {
        uint64_t neighbor = recent_accesses[i];
        if (neighbor != page_id && neighbor != 0) {
            uint32_t hash = hash_page_id(neighbor, CTM_HASH_BITS);
            if (pages[hash].flags & CTM_PAGE_IN_TIER0) {
                in_tier0++;
            }
            total++;
        }
    }

    hotness_out[idx] = total > 0 ? (float)in_tier0 / (float)total : 0.0f;
}

__global__ void kernel_update_shadow(
    ShadowEntry* shadow_b1,
    ShadowEntry* shadow_b2,
    uint32_t* shadow_sizes,
    uint64_t evicted_page_id,
    bool from_tier0,
    uint64_t current_time
) {
    // Single thread updates shadow tier — this kernel must be launched
    // with <<<1, 1>>> to avoid concurrent writes to shadow arrays.
    if (threadIdx.x != 0 || blockIdx.x != 0) return;

    ShadowEntry* shadow = from_tier0 ? shadow_b1 : shadow_b2;
    uint32_t* size = from_tier0 ? &shadow_sizes[0] : &shadow_sizes[1];

    if (*size < CTM_SHADOW_MAX_SIZE) {
        uint32_t idx = *size;
        *size = idx + 1;
        shadow[idx].page_id = evicted_page_id;
        shadow[idx].evict_time = current_time;
        shadow[idx].from_tier0 = from_tier0;
    }
}

/* ========== Controller Implementation ========== */

struct Controller::Impl {
    // Device memory
    PageState* d_pages;
    uint64_t* d_tier0_lru;
    uint64_t* d_tier1_lru;
    ShadowEntry* d_shadow_b1;
    ShadowEntry* d_shadow_b2;
    uint32_t* d_shadow_sizes;
    Stats* d_stats;
    curandState* d_rng_states;

    // Host state
    Config config;
    Stats h_stats;
    uint32_t tier0_capacity;
    uint32_t tier1_capacity;
    uint32_t tier0_size;
    uint32_t tier1_size;
    float adaptive_p;
    uint64_t access_counter;
    cudaStream_t stream;

    Impl(uint32_t t0_cap, uint32_t t1_cap, cudaStream_t s)
        : d_pages(nullptr), d_tier0_lru(nullptr), d_tier1_lru(nullptr),
          d_shadow_b1(nullptr), d_shadow_b2(nullptr), d_shadow_sizes(nullptr),
          d_stats(nullptr), d_rng_states(nullptr),
          tier0_capacity(t0_cap), tier1_capacity(t1_cap), stream(s),
          tier0_size(0), tier1_size(0), adaptive_p(0.5f), access_counter(0)
    {
        memset(&h_stats, 0, sizeof(h_stats));

        // Allocate device memory with error checking
        cudaError_t err;
        size_t hash_size = 1 << CTM_HASH_BITS;

        err = cudaMalloc(&d_pages, hash_size * sizeof(PageState));
        if (err != cudaSuccess) {
            fprintf(stderr, "CTM+ CUDA: Failed to allocate pages: %s\n", cudaGetErrorString(err));
            return;
        }
        cudaMemset(d_pages, 0, hash_size * sizeof(PageState));

        err = cudaMalloc(&d_tier0_lru, tier0_capacity * sizeof(uint64_t));
        if (err != cudaSuccess) {
            fprintf(stderr, "CTM+ CUDA: Failed to allocate tier0_lru: %s\n", cudaGetErrorString(err));
            return;
        }

        err = cudaMalloc(&d_tier1_lru, tier1_capacity * sizeof(uint64_t));
        if (err != cudaSuccess) {
            fprintf(stderr, "CTM+ CUDA: Failed to allocate tier1_lru: %s\n", cudaGetErrorString(err));
            return;
        }

        err = cudaMalloc(&d_shadow_b1, CTM_SHADOW_MAX_SIZE * sizeof(ShadowEntry));
        if (err != cudaSuccess) {
            fprintf(stderr, "CTM+ CUDA: Failed to allocate shadow_b1: %s\n", cudaGetErrorString(err));
            return;
        }

        err = cudaMalloc(&d_shadow_b2, CTM_SHADOW_MAX_SIZE * sizeof(ShadowEntry));
        if (err != cudaSuccess) {
            fprintf(stderr, "CTM+ CUDA: Failed to allocate shadow_b2: %s\n", cudaGetErrorString(err));
            return;
        }

        err = cudaMalloc(&d_shadow_sizes, 2 * sizeof(uint32_t));
        if (err != cudaSuccess) {
            fprintf(stderr, "CTM+ CUDA: Failed to allocate shadow_sizes: %s\n", cudaGetErrorString(err));
            return;
        }
        cudaMemset(d_shadow_sizes, 0, 2 * sizeof(uint32_t));

        err = cudaMalloc(&d_stats, sizeof(Stats));
        if (err != cudaSuccess) {
            fprintf(stderr, "CTM+ CUDA: Failed to allocate stats: %s\n", cudaGetErrorString(err));
            return;
        }
        cudaMemset(d_stats, 0, sizeof(Stats));

        // Initialize RNG
        uint32_t rng_count = 256;
        err = cudaMalloc(&d_rng_states, rng_count * sizeof(curandState));
        if (err != cudaSuccess) {
            fprintf(stderr, "CTM+ CUDA: Failed to allocate rng_states: %s\n", cudaGetErrorString(err));
            return;
        }
        kernel_init_rng<<<(rng_count + 255) / 256, 256, 0, stream>>>(
            d_rng_states, time(nullptr), rng_count);
    }

    ~Impl() {
        if (d_pages) cudaFree(d_pages);
        if (d_tier0_lru) cudaFree(d_tier0_lru);
        if (d_tier1_lru) cudaFree(d_tier1_lru);
        if (d_shadow_b1) cudaFree(d_shadow_b1);
        if (d_shadow_b2) cudaFree(d_shadow_b2);
        if (d_shadow_sizes) cudaFree(d_shadow_sizes);
        if (d_stats) cudaFree(d_stats);
        if (d_rng_states) cudaFree(d_rng_states);
    }
};

Controller::Controller(uint32_t tier0_capacity, uint32_t tier1_capacity,
                       cudaStream_t stream) {
    impl_ = new Impl(tier0_capacity, tier1_capacity, stream);
}

Controller::~Controller() {
    delete impl_;
}

void Controller::on_access_batch(const uint64_t* page_ids, uint32_t num_pages,
                                  bool* promotions, bool* demotions) {
    uint32_t block_size = 256;
    uint32_t num_blocks = (num_pages + block_size - 1) / block_size;

    kernel_on_access<<<num_blocks, block_size, 0, impl_->stream>>>(
        impl_->d_pages,
        nullptr,  // page_hash not used in simplified version
        impl_->d_tier0_lru,
        impl_->d_tier1_lru,
        page_ids,
        num_pages,
        impl_->access_counter,
        impl_->config,
        impl_->d_stats,
        promotions,
        demotions
    );

    impl_->access_counter += num_pages;
}

void Controller::select_victims(uint32_t num_victims, uint64_t* victim_ids) {
    if (impl_->tier0_size == 0) return;

    uint32_t block_size = 256;
    uint32_t num_blocks = (num_victims + block_size - 1) / block_size;

    kernel_select_victims<<<num_blocks, block_size, 0, impl_->stream>>>(
        impl_->d_pages,
        impl_->d_tier0_lru,
        impl_->tier0_size,
        impl_->config.victim_sample_size,
        impl_->adaptive_p,
        victim_ids,
        num_victims,
        impl_->d_rng_states
    );
}

Stats Controller::get_stats() {
    cudaMemcpyAsync(&impl_->h_stats, impl_->d_stats, sizeof(Stats),
                    cudaMemcpyDeviceToHost, impl_->stream);
    cudaStreamSynchronize(impl_->stream);
    return impl_->h_stats;
}

void Controller::reset_stats() {
    cudaMemsetAsync(impl_->d_stats, 0, sizeof(Stats), impl_->stream);
}

void Controller::set_config(const Config& config) {
    impl_->config = config;
}

Config Controller::get_config() const {
    return impl_->config;
}

void Controller::synchronize() {
    cudaStreamSynchronize(impl_->stream);
}

/* ========== Utility Functions ========== */

bool initialize_device(int device_id) {
    cudaError_t err = cudaSetDevice(device_id);
    if (err != cudaSuccess) {
        fprintf(stderr, "CTM+ CUDA: Failed to set device %d: %s\n",
                device_id, cudaGetErrorString(err));
        return false;
    }

    cudaDeviceProp prop;
    cudaGetDeviceProperties(&prop, device_id);
    printf("CTM+ CUDA: Using %s (SM %d.%d, %zu MB)\n",
           prop.name, prop.major, prop.minor,
           prop.totalGlobalMem / (1024 * 1024));

    return true;
}

void get_memory_info(size_t* free_bytes, size_t* total_bytes) {
    cudaMemGetInfo(free_bytes, total_bytes);
}

cudaError_t ctm_malloc_managed(void** ptr, size_t size, int preferred_tier) {
    cudaError_t err = cudaMallocManaged(ptr, size);
    if (err != cudaSuccess) return err;

    // Set memory advice based on preferred tier
    if (preferred_tier == 0) {
        cudaMemAdvise(*ptr, size, cudaMemAdviseSetPreferredLocation, 0);
    } else {
        cudaMemAdvise(*ptr, size, cudaMemAdviseSetPreferredLocation, cudaCpuDeviceId);
    }

    return cudaSuccess;
}

cudaError_t ctm_free(void* ptr) {
    return cudaFree(ptr);
}

} // namespace ctm
