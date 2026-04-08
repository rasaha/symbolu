/*
 * TurboQuant + CTXL + CTM+ Integrated Benchmark
 *
 * Benchmarks the 3-tier KV cache hierarchy across configurations:
 *   1. LRU (FP16)                    — Baseline
 *   2. CTM+ (FP16)                   — Smart eviction
 *   3. TQ-4bit + LRU (capacity)      — Compression + basic eviction
 *   4. TQ-3bit + LRU (capacity)      — More compression + basic eviction
 *   5. TQ-4bit + CTM+ (capacity)     — Combined, capacity-only
 *   6. TQ-3bit + CTM+ (quality-aware) — Combined, quality-aware
 *
 * Mirrors the vLLM run_comparison_benchmark() for native CUDA.
 *
 * Build: nvcc -O3 -o turboquant_benchmark turboquant_benchmark.cu \
 *             turboquant.cu turboquant_ctxl_integration.cu ctm_plus.cu -lcurand
 * Run:   ./turboquant_benchmark
 *
 * SPDX-License-Identifier: MIT
 */

#include "turboquant_ctxl_integration.cuh"
#include <iostream>
#include <iomanip>
#include <vector>
#include <random>
#include <chrono>
#include <string>

using namespace ctm;

/* ========== Workload Generators ========== */

struct AccessEvent {
    uint64_t page_id;
    uint8_t  token_type;
    float    attention_weight;
};

/**
 * Sequential autoregressive workload — each new token attends to
 * attention sinks + recent window (matching vLLM sink_and_recent pattern).
 */
std::vector<AccessEvent> generate_sequential_workload(
    size_t seq_len, size_t base_cache_size, uint64_t seed = 42
) {
    std::vector<AccessEvent> events;
    events.reserve(seq_len * 20);  // Rough estimate

    std::mt19937_64 rng(seed);
    std::uniform_real_distribution<float> uniform(0.0f, 1.0f);

    for (size_t t = 0; t < seq_len; t++) {
        // Determine token type
        uint8_t token_type = TOKEN_REGULAR;
        if (t == 0) token_type = TOKEN_BOS;
        else if (uniform(rng) < 0.05) token_type = TOKEN_ENTITY;
        else if (uniform(rng) < 0.05) token_type = TOKEN_NUMBER;
        else if (uniform(rng) < 0.10) token_type = TOKEN_PUNCTUATION;

        // Attention pattern: sinks + recent + sparse middle
        size_t current_len = t + 1;
        uint32_t sink_tokens = 4;
        uint32_t recent_window = 256;

        // Attend to attention sinks
        for (uint32_t s = 0; s < sink_tokens && s < current_len; s++) {
            float attn = 0.15f / sink_tokens;
            events.push_back({s, token_type, attn});
        }

        // Attend to recent window
        size_t recent_start = (current_len > recent_window) ?
                              current_len - recent_window : sink_tokens;
        for (size_t r = recent_start; r < current_len; r++) {
            float recency = (float)(r - recent_start) / (float)recent_window;
            float attn = 0.55f * recency / recent_window;
            events.push_back({(uint64_t)r, token_type, attn});
        }

        // Sparse attention to middle (10% of middle tokens)
        if (current_len > sink_tokens + recent_window) {
            size_t middle_len = current_len - sink_tokens - recent_window;
            size_t n_sparse = std::max((size_t)1, middle_len / 10);
            for (size_t s = 0; s < n_sparse; s++) {
                size_t pos = sink_tokens + (rng() % middle_len);
                float attn = 0.30f / (float)middle_len;
                events.push_back({(uint64_t)pos, token_type, attn});
            }
        }
    }

    return events;
}

/**
 * Zipfian hotspot workload — some tokens much more important.
 */
std::vector<AccessEvent> generate_zipf_workload(
    size_t num_accesses, size_t num_pages, double skew = 1.0, uint64_t seed = 42
) {
    std::vector<AccessEvent> events(num_accesses);
    std::mt19937_64 rng(seed);

    // Precompute Zipf CDF
    std::vector<double> cdf(num_pages);
    double sum = 0.0;
    for (size_t i = 0; i < num_pages; i++) {
        cdf[i] = 1.0 / std::pow(i + 1, skew);
        sum += cdf[i];
    }
    for (size_t i = 0; i < num_pages; i++) {
        cdf[i] /= sum;
        if (i > 0) cdf[i] += cdf[i - 1];
    }

    std::uniform_real_distribution<double> dist(0.0, 1.0);
    std::uniform_real_distribution<float> attn_dist(0.001f, 0.1f);

    for (size_t i = 0; i < num_accesses; i++) {
        double r = dist(rng);
        auto it = std::lower_bound(cdf.begin(), cdf.end(), r);
        uint64_t page = (uint64_t)(it - cdf.begin());

        uint8_t token_type = TOKEN_REGULAR;
        if (page == 0) token_type = TOKEN_BOS;
        else if (page < 10 && dist(rng) < 0.3) token_type = TOKEN_ENTITY;
        else if (dist(rng) < 0.05) token_type = TOKEN_NUMBER;

        events[i] = {page, token_type, attn_dist(rng)};
    }

    return events;
}

/* ========== Benchmark Runner ========== */

struct BenchmarkResult {
    std::string name;
    double hit_rate;
    uint64_t tier0_hits;
    uint64_t cxl_hits;
    uint64_t tier1_hits;
    uint64_t misses;
    uint32_t effective_capacity;
    float compression_ratio;
    double throughput_mops;
    double elapsed_ms;
};

BenchmarkResult run_integrated_benchmark(
    const std::string& name,
    const std::vector<AccessEvent>& events,
    const IntegratedConfig& config
) {
    IntegratedController ctrl(config);

    size_t n = events.size();

    // Prepare device buffers
    std::vector<uint64_t> h_page_ids(n);
    std::vector<uint8_t> h_token_types(n);
    std::vector<float> h_attn_weights(n);

    for (size_t i = 0; i < n; i++) {
        h_page_ids[i] = events[i].page_id;
        h_token_types[i] = events[i].token_type;
        h_attn_weights[i] = events[i].attention_weight;
    }

    uint64_t* d_page_ids;
    uint8_t*  d_token_types;
    float*    d_attn_weights;
    uint8_t*  d_hit_tiers;

    cudaMalloc(&d_page_ids, n * sizeof(uint64_t));
    cudaMalloc(&d_token_types, n * sizeof(uint8_t));
    cudaMalloc(&d_attn_weights, n * sizeof(float));
    cudaMalloc(&d_hit_tiers, n * sizeof(uint8_t));

    cudaMemcpy(d_page_ids, h_page_ids.data(), n * sizeof(uint64_t),
               cudaMemcpyHostToDevice);
    cudaMemcpy(d_token_types, h_token_types.data(), n * sizeof(uint8_t),
               cudaMemcpyHostToDevice);
    cudaMemcpy(d_attn_weights, h_attn_weights.data(), n * sizeof(float),
               cudaMemcpyHostToDevice);

    // Warmup
    size_t warmup = std::min(n, (size_t)10000);
    ctrl.access_batch(d_page_ids, d_token_types, d_attn_weights,
                      warmup, d_hit_tiers);
    ctrl.synchronize();
    ctrl.reset_stats();

    // Benchmark
    auto start = std::chrono::high_resolution_clock::now();

    const size_t BATCH_SIZE = 10000;
    for (size_t i = 0; i < n; i += BATCH_SIZE) {
        size_t batch = std::min(BATCH_SIZE, n - i);
        ctrl.access_batch(d_page_ids + i, d_token_types + i,
                          d_attn_weights + i, batch, d_hit_tiers + i);
    }

    ctrl.synchronize();
    auto end = std::chrono::high_resolution_clock::now();

    IntegratedStats stats = ctrl.get_stats();
    double elapsed_ms = std::chrono::duration<double, std::milli>(end - start).count();

    // Cleanup
    cudaFree(d_page_ids);
    cudaFree(d_token_types);
    cudaFree(d_attn_weights);
    cudaFree(d_hit_tiers);

    uint64_t total_hits = stats.tier0_hits + stats.cxl_hits + stats.tier1_hits;
    uint64_t total = total_hits + stats.misses;

    BenchmarkResult result;
    result.name = name;
    result.hit_rate = total > 0 ? (double)total_hits / total * 100.0 : 0.0;
    result.tier0_hits = stats.tier0_hits;
    result.cxl_hits = stats.cxl_hits;
    result.tier1_hits = stats.tier1_hits;
    result.misses = stats.misses;
    result.effective_capacity = config.total_effective_tokens();
    result.compression_ratio = config.tq_config.compression_ratio();
    result.throughput_mops = (double)n / (elapsed_ms / 1000.0) / 1e6;
    result.elapsed_ms = elapsed_ms;

    return result;
}

/* ========== TurboQuant Compression Benchmark ========== */

void benchmark_turboquant_kernels(int head_dim = 128) {
    std::cout << "\n" << std::string(80, '=') << std::endl;
    std::cout << "TURBOQUANT KERNEL BENCHMARK (head_dim=" << head_dim << ")" << std::endl;
    std::cout << std::string(80, '=') << std::endl;

    const int batch_sizes[] = {64, 256, 1024, 4096, 16384};
    const int angle_bits[] = {2, 3, 4};

    for (int bits : angle_bits) {
        TurboQuantConfig config;
        config.head_dim = head_dim;
        config.angle_bits = bits;
        config.enable_qjl = true;

        TurboQuantEngine engine(config);

        std::cout << "\n  " << bits << "-bit (compression ratio: "
                  << std::fixed << std::setprecision(1)
                  << config.compression_ratio() << "x, "
                  << std::setprecision(2) << config.total_bits_per_element()
                  << " bits/elem):" << std::endl;

        for (int batch : batch_sizes) {
            // Allocate
            float* d_vectors;
            float* d_vectors_out;
            unsigned char* d_indices;
            float* d_radii;

            cudaMalloc(&d_vectors, (size_t)batch * head_dim * sizeof(float));
            cudaMalloc(&d_vectors_out, (size_t)batch * head_dim * sizeof(float));
            cudaMalloc(&d_indices,
                       (size_t)batch * config.total_angles() * sizeof(unsigned char));
            cudaMalloc(&d_radii, batch * sizeof(float));

            // Fill with random data
            // (In production, these would be actual KV vectors)
            cudaMemset(d_vectors, 0x42, (size_t)batch * head_dim * sizeof(float));

            // Warmup
            engine.compress_batch(d_vectors, batch, d_indices, d_radii);
            engine.synchronize();

            // Benchmark compress
            auto start = std::chrono::high_resolution_clock::now();
            const int iterations = 100;
            for (int i = 0; i < iterations; i++) {
                engine.compress_batch(d_vectors, batch, d_indices, d_radii);
            }
            engine.synchronize();
            auto mid = std::chrono::high_resolution_clock::now();

            // Benchmark decompress
            for (int i = 0; i < iterations; i++) {
                engine.decompress_batch(d_radii, d_indices, batch, d_vectors_out);
            }
            engine.synchronize();
            auto end = std::chrono::high_resolution_clock::now();

            double compress_ms = std::chrono::duration<double, std::milli>(mid - start).count();
            double decompress_ms = std::chrono::duration<double, std::milli>(end - mid).count();

            double compress_gbps = (double)batch * head_dim * sizeof(float) * iterations
                                   / (compress_ms / 1000.0) / 1e9;
            double decompress_gbps = (double)batch * head_dim * sizeof(float) * iterations
                                     / (decompress_ms / 1000.0) / 1e9;

            std::cout << "    batch=" << std::setw(6) << batch
                      << "  compress: " << std::setw(7) << std::setprecision(2)
                      << compress_ms / iterations << " ms"
                      << " (" << std::setw(6) << std::setprecision(1)
                      << compress_gbps << " GB/s)"
                      << "  decompress: " << std::setw(7) << std::setprecision(2)
                      << decompress_ms / iterations << " ms"
                      << " (" << std::setw(6) << std::setprecision(1)
                      << decompress_gbps << " GB/s)"
                      << std::endl;

            cudaFree(d_vectors);
            cudaFree(d_vectors_out);
            cudaFree(d_indices);
            cudaFree(d_radii);
        }
    }
}

/* ========== Main ========== */

int main() {
    std::cout << "=== TurboQuant + CTXL + CTM+ Integrated Benchmark ===" << std::endl;

    if (!initialize_device(0)) {
        std::cerr << "Failed to initialize CUDA device" << std::endl;
        return 1;
    }

    size_t free_mem, total_mem;
    get_memory_info(&free_mem, &total_mem);
    std::cout << "GPU Memory: " << free_mem / (1024*1024) << " MB free / "
              << total_mem / (1024*1024) << " MB total" << std::endl;

    // ---- Phase 1: TurboQuant kernel throughput ----
    benchmark_turboquant_kernels(128);

    // ---- Phase 2: Integrated 3-tier benchmark ----
    std::cout << "\n" << std::string(80, '=') << std::endl;
    std::cout << "INTEGRATED 3-TIER KV CACHE BENCHMARK" << std::endl;
    std::cout << std::string(80, '=') << std::endl;

    const uint32_t BASE_CAPACITY = 4096;
    const size_t SEQ_LEN = 16384;

    std::cout << "\n  Base cache capacity (FP16): " << BASE_CAPACITY << " tokens" << std::endl;
    std::cout << "  Sequence length: " << SEQ_LEN << " tokens" << std::endl;

    // Generate workloads
    auto workload_seq = generate_sequential_workload(SEQ_LEN, BASE_CAPACITY);
    auto workload_zipf = generate_zipf_workload(200000, 20000, 1.0);

    std::cout << "\n  Workload 1 (Sequential): " << workload_seq.size() << " accesses" << std::endl;
    std::cout << "  Workload 2 (Zipfian):    " << workload_zipf.size() << " accesses" << std::endl;

    // Configuration matrix (matching vLLM run_comparison_benchmark)
    struct BenchConfig {
        std::string name;
        IntegratedConfig config;
    };

    std::vector<BenchConfig> configs;

    // 1. LRU (FP16) — baseline (high recency weight, no compression)
    {
        IntegratedConfig cfg;
        cfg.tq_config.angle_bits = 3;
        cfg.tier0_capacity_tokens = BASE_CAPACITY;
        cfg.cxl_capacity_tokens = 0;
        cfg.weight_recency = 0.90f;
        cfg.weight_frequency = 0.05f;
        cfg.weight_attention_strength = 0.025f;
        cfg.weight_token_importance = 0.025f;
        cfg.weight_position = 0.0f;
        cfg.mode = IntegrationMode::CAPACITY_ONLY;
        cfg.cxl_capacity_tokens = 1;  // Minimal CXL (effectively LRU)
        configs.push_back({"LRU (FP16)", cfg});
    }

    // 2. CTM+ (FP16) — smart eviction, no compression
    {
        IntegratedConfig cfg;
        cfg.tier0_capacity_tokens = BASE_CAPACITY;
        cfg.cxl_capacity_tokens = 1;
        cfg.mode = IntegrationMode::CAPACITY_ONLY;
        configs.push_back({"CTM+ (FP16)", cfg});
    }

    // 3. TQ-4bit + LRU (capacity only)
    {
        IntegratedConfig cfg;
        cfg.tq_config = tq_config_4bit();
        cfg.tier0_capacity_tokens = BASE_CAPACITY;
        cfg.weight_recency = 0.90f;
        cfg.weight_frequency = 0.05f;
        cfg.weight_attention_strength = 0.025f;
        cfg.weight_token_importance = 0.025f;
        cfg.weight_position = 0.0f;
        cfg.mode = IntegrationMode::CAPACITY_ONLY;
        configs.push_back({"TQ-4bit + LRU", cfg});
    }

    // 4. TQ-3bit + LRU (capacity only)
    {
        IntegratedConfig cfg;
        cfg.tq_config = tq_config_3bit();
        cfg.tier0_capacity_tokens = BASE_CAPACITY;
        cfg.weight_recency = 0.90f;
        cfg.weight_frequency = 0.05f;
        cfg.weight_attention_strength = 0.025f;
        cfg.weight_token_importance = 0.025f;
        cfg.weight_position = 0.0f;
        cfg.mode = IntegrationMode::CAPACITY_ONLY;
        configs.push_back({"TQ-3bit + LRU", cfg});
    }

    // 5. TQ-4bit + CTM+ (capacity only)
    {
        IntegratedConfig cfg = integrated_config_4bit_long_context();
        cfg.tier0_capacity_tokens = BASE_CAPACITY;
        configs.push_back({"TQ-4bit + CTM+ (cap)", cfg});
    }

    // 6. TQ-3bit + CTM+ (quality-aware) — best combined
    {
        IntegratedConfig cfg = integrated_config_3bit_long_context();
        cfg.tier0_capacity_tokens = BASE_CAPACITY;
        configs.push_back({"TQ-3bit + CTM+ (qual)", cfg});
    }

    // Run benchmarks for each workload
    for (int wl = 0; wl < 2; wl++) {
        const auto& workload = (wl == 0) ? workload_seq : workload_zipf;
        const char* wl_name = (wl == 0) ? "Sequential (Autoregressive)"
                                        : "Zipfian (Hotspot)";

        std::cout << "\n  --- Workload: " << wl_name << " ---\n" << std::endl;

        // Header
        std::cout << "  " << std::left << std::setw(28) << "Configuration"
                  << std::right
                  << std::setw(10) << "Hit Rate"
                  << std::setw(10) << "Eff.Size"
                  << std::setw(8) << "Ratio"
                  << std::setw(10) << "CXL Hits"
                  << std::setw(12) << "Throughput"
                  << std::setw(10) << "Time"
                  << std::endl;
        std::cout << "  " << std::string(88, '-') << std::endl;

        double baseline_hr = 0.0;

        for (auto& bc : configs) {
            auto result = run_integrated_benchmark(bc.name, workload, bc.config);

            if (bc.name.find("LRU (FP16)") != std::string::npos) {
                baseline_hr = result.hit_rate;
            }

            std::cout << "  " << std::left << std::setw(28) << result.name
                      << std::right << std::fixed
                      << std::setw(9) << std::setprecision(2) << result.hit_rate << "%"
                      << std::setw(10) << result.effective_capacity
                      << std::setw(7) << std::setprecision(1) << result.compression_ratio << "x"
                      << std::setw(10) << result.cxl_hits
                      << std::setw(9) << std::setprecision(1)
                      << result.throughput_mops << " Mops"
                      << std::setw(8) << std::setprecision(1) << result.elapsed_ms << "ms"
                      << std::endl;
        }

        std::cout << "  " << std::string(88, '-') << std::endl;
    }

    std::cout << "\n" << std::string(80, '=') << std::endl;
    std::cout << "  3-Tier Memory Hierarchy:" << std::endl;
    std::cout << "    Tier0 (HBM, FP16)     -> hot tokens, full precision" << std::endl;
    std::cout << "    CXL   (DRAM, TQ-3bit) -> warm tokens, ~5.3x compressed" << std::endl;
    std::cout << "    Tier1 (NVMe)          -> cold tokens, last resort" << std::endl;
    std::cout << std::string(80, '=') << std::endl;

    std::cout << "\nDone!" << std::endl;
    return 0;
}
