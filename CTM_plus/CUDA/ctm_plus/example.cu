/*
 * CTM+ CUDA Example
 *
 * Demonstrates basic usage of the CTM+ GPU memory tiering controller.
 *
 * Build: nvcc -o example example.cu ctm_plus.cu -lcurand
 * Run: ./example
 */

#include "ctm_plus.cuh"
#include <iostream>
#include <vector>
#include <random>
#include <chrono>

using namespace ctm;

// Generate Zipfian-distributed page accesses
std::vector<uint64_t> generate_zipf_trace(size_t num_accesses, size_t num_pages,
                                           double skew = 1.0) {
    std::vector<uint64_t> trace(num_accesses);
    std::mt19937_64 rng(42);

    // Precompute Zipf weights
    std::vector<double> weights(num_pages);
    double sum = 0.0;
    for (size_t i = 0; i < num_pages; i++) {
        weights[i] = 1.0 / std::pow(i + 1, skew);
        sum += weights[i];
    }

    // Normalize to CDF
    for (size_t i = 0; i < num_pages; i++) {
        weights[i] /= sum;
        if (i > 0) weights[i] += weights[i - 1];
    }

    // Sample
    std::uniform_real_distribution<double> dist(0.0, 1.0);
    for (size_t i = 0; i < num_accesses; i++) {
        double r = dist(rng);
        auto it = std::lower_bound(weights.begin(), weights.end(), r);
        trace[i] = std::distance(weights.begin(), it);
    }

    return trace;
}

int main() {
    std::cout << "=== CTM+ CUDA Example ===" << std::endl;

    // Initialize device
    if (!initialize_device(0)) {
        std::cerr << "Failed to initialize CUDA device" << std::endl;
        return 1;
    }

    // Get memory info
    size_t free_mem, total_mem;
    get_memory_info(&free_mem, &total_mem);
    std::cout << "GPU Memory: " << free_mem / (1024*1024) << " MB free / "
              << total_mem / (1024*1024) << " MB total" << std::endl;

    // Configuration
    const uint32_t TIER0_SIZE = 1000;    // Fast tier (HBM-like)
    const uint32_t TIER1_SIZE = 100000;  // Slow tier (GDDR-like)
    const size_t NUM_ACCESSES = 100000;
    const size_t NUM_PAGES = 10000;

    std::cout << "\nConfiguration:" << std::endl;
    std::cout << "  Tier 0 capacity: " << TIER0_SIZE << " pages" << std::endl;
    std::cout << "  Tier 1 capacity: " << TIER1_SIZE << " pages" << std::endl;
    std::cout << "  Trace length: " << NUM_ACCESSES << " accesses" << std::endl;
    std::cout << "  Page universe: " << NUM_PAGES << " pages" << std::endl;

    // Create controller
    Controller ctrl(TIER0_SIZE, TIER1_SIZE);

    // Configure
    Config config;
    config.victim_sample_size = 48;
    config.promotion_threshold = 0.3f;
    config.enable_smart_victim = true;
    ctrl.set_config(config);

    // Generate trace
    std::cout << "\nGenerating Zipfian trace..." << std::endl;
    auto trace = generate_zipf_trace(NUM_ACCESSES, NUM_PAGES, 1.0);

    // Allocate device memory for trace and outputs
    uint64_t* d_trace;
    bool* d_promotions;
    bool* d_demotions;

    cudaMalloc(&d_trace, NUM_ACCESSES * sizeof(uint64_t));
    cudaMalloc(&d_promotions, NUM_ACCESSES * sizeof(bool));
    cudaMalloc(&d_demotions, NUM_ACCESSES * sizeof(bool));

    cudaMemcpy(d_trace, trace.data(), NUM_ACCESSES * sizeof(uint64_t),
               cudaMemcpyHostToDevice);

    // Run simulation
    std::cout << "Running simulation..." << std::endl;
    auto start = std::chrono::high_resolution_clock::now();

    // Process in batches
    const size_t BATCH_SIZE = 10000;
    for (size_t i = 0; i < NUM_ACCESSES; i += BATCH_SIZE) {
        size_t batch = std::min(BATCH_SIZE, NUM_ACCESSES - i);
        ctrl.on_access_batch(d_trace + i, batch,
                             d_promotions + i, d_demotions + i);
    }

    ctrl.synchronize();
    auto end = std::chrono::high_resolution_clock::now();

    // Get results
    Stats stats = ctrl.get_stats();

    double elapsed = std::chrono::duration<double, std::milli>(end - start).count();
    double throughput = NUM_ACCESSES / (elapsed / 1000.0);

    // Print results
    std::cout << "\n=== Results ===" << std::endl;
    std::cout << "Tier 0 hits:  " << stats.tier0_hits << std::endl;
    std::cout << "Tier 1 hits:  " << stats.tier1_hits << std::endl;
    std::cout << "Misses:       " << stats.misses << std::endl;

    uint64_t total = stats.tier0_hits + stats.tier1_hits + stats.misses;
    double hit_rate = (double)(stats.tier0_hits + stats.tier1_hits) / total * 100.0;
    double tier0_rate = (double)stats.tier0_hits / total * 100.0;

    std::cout << "\nHit rate:     " << hit_rate << "%" << std::endl;
    std::cout << "Tier 0 rate:  " << tier0_rate << "%" << std::endl;
    std::cout << "Promotions:   " << stats.promotions << std::endl;
    std::cout << "Demotions:    " << stats.demotions << std::endl;

    std::cout << "\nPerformance:" << std::endl;
    std::cout << "  Elapsed:    " << elapsed << " ms" << std::endl;
    std::cout << "  Throughput: " << throughput / 1e6 << " M accesses/sec" << std::endl;

    // Cleanup
    cudaFree(d_trace);
    cudaFree(d_promotions);
    cudaFree(d_demotions);

    std::cout << "\nDone!" << std::endl;
    return 0;
}
