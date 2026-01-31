/*
 * CTM+ CUDA Benchmark
 *
 * Benchmarks CTM+ performance across different workloads.
 *
 * Build: nvcc -O3 -o benchmark benchmark.cu ctm_plus.cu -lcurand
 * Run: ./benchmark
 */

#include "ctm_plus.cuh"
#include <iostream>
#include <vector>
#include <random>
#include <chrono>
#include <iomanip>

using namespace ctm;

// Workload generators
std::vector<uint64_t> generate_zipf(size_t n, size_t pages, double skew) {
    std::vector<uint64_t> trace(n);
    std::mt19937_64 rng(42);
    std::vector<double> weights(pages);
    double sum = 0.0;
    for (size_t i = 0; i < pages; i++) {
        weights[i] = 1.0 / std::pow(i + 1, skew);
        sum += weights[i];
    }
    for (size_t i = 0; i < pages; i++) {
        weights[i] /= sum;
        if (i > 0) weights[i] += weights[i - 1];
    }
    std::uniform_real_distribution<double> dist(0.0, 1.0);
    for (size_t i = 0; i < n; i++) {
        double r = dist(rng);
        trace[i] = std::lower_bound(weights.begin(), weights.end(), r) - weights.begin();
    }
    return trace;
}

std::vector<uint64_t> generate_temporal(size_t n, size_t pages) {
    std::vector<uint64_t> trace(n);
    std::mt19937_64 rng(42);
    std::uniform_int_distribution<uint64_t> dist(0, pages - 1);
    std::geometric_distribution<int> gap_dist(0.3);

    uint64_t current = dist(rng);
    for (size_t i = 0; i < n; i++) {
        trace[i] = current;
        if (gap_dist(rng) == 0 || rng() % 10 == 0) {
            current = dist(rng);
        }
    }
    return trace;
}

std::vector<uint64_t> generate_hotspot(size_t n, size_t pages) {
    std::vector<uint64_t> trace(n);
    std::mt19937_64 rng(42);
    size_t hot_pages = pages / 5;  // 20% hot

    std::uniform_real_distribution<double> choice(0.0, 1.0);
    std::uniform_int_distribution<uint64_t> hot_dist(0, hot_pages - 1);
    std::uniform_int_distribution<uint64_t> cold_dist(hot_pages, pages - 1);

    for (size_t i = 0; i < n; i++) {
        trace[i] = (choice(rng) < 0.8) ? hot_dist(rng) : cold_dist(rng);
    }
    return trace;
}

std::vector<uint64_t> generate_uniform(size_t n, size_t pages) {
    std::vector<uint64_t> trace(n);
    std::mt19937_64 rng(42);
    std::uniform_int_distribution<uint64_t> dist(0, pages - 1);
    for (size_t i = 0; i < n; i++) {
        trace[i] = dist(rng);
    }
    return trace;
}

struct BenchmarkResult {
    std::string workload;
    double hit_rate;
    double tier0_rate;
    uint64_t promotions;
    uint64_t demotions;
    double throughput_mops;
};

BenchmarkResult run_benchmark(const std::string& name,
                               const std::vector<uint64_t>& trace,
                               uint32_t tier0_size, uint32_t tier1_size) {
    Controller ctrl(tier0_size, tier1_size);

    Config config;
    config.victim_sample_size = 48;
    config.promotion_threshold = 0.3f;
    config.enable_smart_victim = true;
    ctrl.set_config(config);

    size_t n = trace.size();

    // Allocate device memory
    uint64_t* d_trace;
    bool* d_promotions;
    bool* d_demotions;

    cudaMalloc(&d_trace, n * sizeof(uint64_t));
    cudaMalloc(&d_promotions, n * sizeof(bool));
    cudaMalloc(&d_demotions, n * sizeof(bool));

    cudaMemcpy(d_trace, trace.data(), n * sizeof(uint64_t), cudaMemcpyHostToDevice);

    // Warmup
    ctrl.on_access_batch(d_trace, std::min(n, (size_t)10000), d_promotions, d_demotions);
    ctrl.synchronize();
    ctrl.reset_stats();

    // Benchmark
    auto start = std::chrono::high_resolution_clock::now();

    const size_t BATCH_SIZE = 10000;
    for (size_t i = 0; i < n; i += BATCH_SIZE) {
        size_t batch = std::min(BATCH_SIZE, n - i);
        ctrl.on_access_batch(d_trace + i, batch, d_promotions + i, d_demotions + i);
    }

    ctrl.synchronize();
    auto end = std::chrono::high_resolution_clock::now();

    Stats stats = ctrl.get_stats();
    double elapsed = std::chrono::duration<double>(end - start).count();

    cudaFree(d_trace);
    cudaFree(d_promotions);
    cudaFree(d_demotions);

    uint64_t total = stats.tier0_hits + stats.tier1_hits + stats.misses;

    BenchmarkResult result;
    result.workload = name;
    result.hit_rate = (double)(stats.tier0_hits + stats.tier1_hits) / total * 100.0;
    result.tier0_rate = (double)stats.tier0_hits / total * 100.0;
    result.promotions = stats.promotions;
    result.demotions = stats.demotions;
    result.throughput_mops = n / elapsed / 1e6;

    return result;
}

int main() {
    std::cout << "=== CTM+ CUDA Benchmark ===" << std::endl;

    if (!initialize_device(0)) {
        return 1;
    }

    const uint32_t TIER0_SIZE = 1000;
    const uint32_t TIER1_SIZE = 100000;
    const size_t NUM_ACCESSES = 500000;
    const size_t NUM_PAGES = 10000;

    std::cout << "\nConfiguration:" << std::endl;
    std::cout << "  Tier 0: " << TIER0_SIZE << " pages" << std::endl;
    std::cout << "  Tier 1: " << TIER1_SIZE << " pages" << std::endl;
    std::cout << "  Accesses: " << NUM_ACCESSES << std::endl;
    std::cout << "  Pages: " << NUM_PAGES << std::endl;

    std::vector<BenchmarkResult> results;

    std::cout << "\nRunning benchmarks..." << std::endl;

    // Zipfian
    auto trace_zipf = generate_zipf(NUM_ACCESSES, NUM_PAGES, 1.0);
    results.push_back(run_benchmark("Zipfian", trace_zipf, TIER0_SIZE, TIER1_SIZE));

    // Temporal
    auto trace_temporal = generate_temporal(NUM_ACCESSES, NUM_PAGES);
    results.push_back(run_benchmark("Temporal", trace_temporal, TIER0_SIZE, TIER1_SIZE));

    // Hotspot
    auto trace_hotspot = generate_hotspot(NUM_ACCESSES, NUM_PAGES);
    results.push_back(run_benchmark("Hotspot", trace_hotspot, TIER0_SIZE, TIER1_SIZE));

    // Uniform
    auto trace_uniform = generate_uniform(NUM_ACCESSES, NUM_PAGES);
    results.push_back(run_benchmark("Uniform", trace_uniform, TIER0_SIZE, TIER1_SIZE));

    // Print results
    std::cout << "\n" << std::string(80, '=') << std::endl;
    std::cout << "RESULTS" << std::endl;
    std::cout << std::string(80, '=') << std::endl;

    std::cout << std::left << std::setw(12) << "Workload"
              << std::right << std::setw(12) << "Hit Rate"
              << std::setw(12) << "Tier0 Rate"
              << std::setw(12) << "Promotions"
              << std::setw(12) << "Demotions"
              << std::setw(15) << "Throughput"
              << std::endl;
    std::cout << std::string(80, '-') << std::endl;

    for (const auto& r : results) {
        std::cout << std::left << std::setw(12) << r.workload
                  << std::right << std::fixed << std::setprecision(2)
                  << std::setw(11) << r.hit_rate << "%"
                  << std::setw(11) << r.tier0_rate << "%"
                  << std::setw(12) << r.promotions
                  << std::setw(12) << r.demotions
                  << std::setw(12) << r.throughput_mops << " Mops/s"
                  << std::endl;
    }

    std::cout << std::string(80, '=') << std::endl;

    return 0;
}
