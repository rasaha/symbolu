/*
 * TurboQuant CUDA Implementation — PolarQuant + QJL KV Cache Compression
 *
 * GPU-accelerated TurboQuant compression for KV cache vectors:
 *   Phase 1: PolarQuant — recursive polar coordinate transformation
 *            with fixed-grid angular quantization (no per-block constants)
 *   Phase 2: QJL — 1-bit Quantized Johnson-Lindenstrauss residual correction
 *
 * Reference: Google Research, ICLR 2026
 *   "TurboQuant: Redefining AI efficiency with extreme compression"
 *
 * This header mirrors the vLLM Python implementation (turboquant.py) and
 * the DeepSpeed CUDA kernels (turboquant_cuda.cu) for native GPU integration
 * with the CTM+ memory tiering controller.
 *
 * SPDX-License-Identifier: MIT
 */

#ifndef TURBOQUANT_CUH
#define TURBOQUANT_CUH

#include <cuda_runtime.h>
#include <cstdint>

namespace ctm {

/* ========== Constants ========== */

// Maximum head dimension for register-resident path
constexpr int TQ_MAX_HEAD_DIM = 256;

// Maximum polar tree levels (log2(256) = 8)
constexpr int TQ_MAX_LEVELS = 8;

// Default configuration values
constexpr int TQ_DEFAULT_HEAD_DIM = 128;
constexpr int TQ_DEFAULT_ANGLE_BITS = 3;
constexpr int TQ_DEFAULT_BLOCK_SIZE = 128;

#ifndef M_PI
#define M_PI 3.14159265358979323846f
#endif

/* ========== Configuration ========== */

/**
 * TurboQuant compression configuration.
 *
 * Bit-width modes (matching vLLM turboquant.py):
 *   2-bit: ~8x compression, quality risk on small models
 *   3-bit: ~5.3x compression (matches paper's 6x claim)
 *   4-bit: ~4x compression, near-lossless quality
 */
struct TurboQuantConfig {
    int head_dim        = TQ_DEFAULT_HEAD_DIM;
    int angle_bits      = TQ_DEFAULT_ANGLE_BITS;
    bool enable_qjl     = true;
    int qjl_proj_dim    = 0;  // 0 = same as head_dim
    uint64_t seed       = 42;

    // Computed properties
    __host__ __device__ int n_grid() const { return 1 << angle_bits; }

    __host__ __device__ int n_levels() const {
        int d = head_dim, levels = 0;
        while (d > 1) { d = (d + 1) / 2; levels++; }
        return levels;
    }

    __host__ __device__ int total_angles() const {
        return head_dim - 1;
    }

    __host__ float total_bits_per_element() const {
        float d = (float)head_dim;
        float polar_bits = ((d - 1.0f) * angle_bits + 16.0f) / d;
        if (enable_qjl) {
            int proj = qjl_proj_dim > 0 ? qjl_proj_dim : head_dim;
            polar_bits += (float)proj / d;
        }
        return polar_bits;
    }

    __host__ float compression_ratio() const {
        return 16.0f / total_bits_per_element();
    }
};

/**
 * Precomputed level geometry for the polar tree.
 * Stored on GPU as constant data.
 */
struct TurboQuantLevelInfo {
    int level_sizes[TQ_MAX_LEVELS];    // n_pairs per level
    int level_offsets[TQ_MAX_LEVELS + 1]; // cumulative angle offsets
    int n_levels;
};

/**
 * Quality metrics for a compressed vector batch.
 */
struct TurboQuantQualityMetrics {
    float avg_mse;
    float avg_cosine_similarity;
    float avg_snr_db;
    uint64_t vectors_compressed;
};

/**
 * Per-token compression state — stored alongside PageState for
 * quality-aware eviction in the integrated TQ+CTM+ system.
 */
struct __align__(16) TokenCompressionState {
    float compression_mse;        // MSE between original and reconstructed
    float cosine_similarity;      // Cosine similarity (1.0 = perfect)
    float original_norm;          // L2 norm of original vector
    uint8_t angle_bits;           // Bit-width used for this token
    uint8_t is_compressed;        // Whether stored in compressed form
    uint8_t storage_tier;         // 0=HBM(FP16), 1=CXL(TQ-compressed), 2=NVMe
    uint8_t _pad;
};

/* ========== Device Helper Functions ========== */

/**
 * LUT floor quantization — O(1) per angle.
 * Matches DeepSpeed turboquant_cuda.cu and Numba _compress_polar_numba.
 *
 * Level 0 (Gaussian pairs, theta in [-pi, pi]):
 *   k = clamp(floor((theta + pi) * lut_scale_full), 0, n_grid-1)
 *
 * Level 1+ (radius pairs, theta in [0, pi/2]):
 *   k = clamp(floor(theta * lut_scale_pos), 0, n_grid-1)
 */
__device__ __forceinline__ int tq_quantize_angle(
    float theta,
    int   is_level0,
    float lut_scale_full,
    float lut_scale_pos,
    int   n_grid
) {
    int k;
    if (is_level0) {
        k = __float2int_rd((theta + M_PI) * lut_scale_full);
    } else {
        k = __float2int_rd(theta * lut_scale_pos);
    }
    if (k < 0)       k = 0;
    if (k >= n_grid)  k = n_grid - 1;
    return k;
}

/* ========== Kernel Declarations ========== */

/**
 * Fused rotate+compress kernel — one thread per vector.
 *
 * Folds the rotation matrix multiply into the polar-tree walk,
 * avoiding a separate GEMM launch. All 7 polar tree levels for
 * head_dim=128 stay in registers.
 *
 * Shared memory: head_dim * head_dim * sizeof(float)
 *   For head_dim=128: 64KB (requires raised shmem limit on Ampere+)
 *
 * Output: uint8 grid bin indices (matching Numba/DeepSpeed format).
 */
__global__ void turboquant_compress_fused(
    const float*         __restrict__ vectors,       // (batch, head_dim)
    const float*         __restrict__ rotation,      // (head_dim, head_dim) row-major
    const float*         __restrict__ grid_full,     // (n_grid,)
    const float*         __restrict__ grid_pos,      // (n_grid,)
    const int*           __restrict__ level_sizes,   // (n_levels,)
    const int*           __restrict__ level_offsets,  // (n_levels+1,)
    float lut_scale_full,
    float lut_scale_pos,
    int   n_levels,
    int   head_dim,
    int   n_grid,
    int   batch,
    unsigned char*       __restrict__ out_indices,   // (batch, total_angles) uint8
    float*               __restrict__ out_radii      // (batch,)
);

/**
 * Fused decompress+inverse-rotate kernel — one thread per vector.
 *
 * Reconstructs float angles via precomputed cos/sin LUTs (no trig
 * calls in the hot path), then applies inverse rotation.
 *
 * Shared memory: head_dim * head_dim * sizeof(float)
 */
__global__ void turboquant_decompress_fused(
    const float*         __restrict__ in_radii,       // (batch,)
    const unsigned char* __restrict__ in_indices,      // (batch, total_angles) uint8
    const float*         __restrict__ rotation_t,      // (head_dim, head_dim) R^T row-major
    const float*         __restrict__ cos_grid_full,   // (n_grid,)
    const float*         __restrict__ sin_grid_full,   // (n_grid,)
    const float*         __restrict__ cos_grid_pos,    // (n_grid,)
    const float*         __restrict__ sin_grid_pos,    // (n_grid,)
    const int*           __restrict__ level_sizes,
    const int*           __restrict__ level_offsets,
    int   n_levels,
    int   head_dim,
    int   batch,
    float*               __restrict__ out_vectors      // (batch, head_dim)
);

/**
 * QJL sign-bit compression kernel — one thread per vector.
 *
 * Computes residual projection and stores 1-bit sign per dimension.
 * Output is packed into uint32 words (32 signs per word).
 */
__global__ void qjl_compress_residual(
    const float*   __restrict__ residuals,     // (batch, head_dim)
    const float*   __restrict__ jl_matrix,     // (proj_dim, head_dim)
    int   head_dim,
    int   proj_dim,
    int   batch,
    uint32_t*      __restrict__ out_sign_bits, // (batch, ceil(proj_dim/32))
    float*         __restrict__ out_scales     // (batch,)
);

/**
 * Compute quality metrics kernel — one thread per vector.
 *
 * Compares original vectors with reconstructed vectors to produce
 * per-vector MSE, cosine similarity, and SNR.
 */
__global__ void turboquant_compute_quality(
    const float*   __restrict__ originals,      // (batch, head_dim)
    const float*   __restrict__ reconstructed,  // (batch, head_dim)
    int   head_dim,
    int   batch,
    float*         __restrict__ out_mse,        // (batch,)
    float*         __restrict__ out_cosine,     // (batch,)
    float*         __restrict__ out_snr         // (batch,)
);

/* ========== Host-side TurboQuant Engine ========== */

/**
 * TurboQuant GPU compression engine.
 *
 * Manages GPU-resident rotation matrices, angle grids, and LUT tables.
 * Provides batch compress/decompress operations.
 *
 * Usage:
 *   TurboQuantEngine engine(config, stream);
 *   engine.compress_batch(d_vectors, batch, d_indices, d_radii);
 *   engine.decompress_batch(d_radii, d_indices, batch, d_vectors_out);
 */
class TurboQuantEngine {
public:
    TurboQuantEngine(const TurboQuantConfig& config,
                     cudaStream_t stream = 0);
    ~TurboQuantEngine();

    // Disable copy
    TurboQuantEngine(const TurboQuantEngine&) = delete;
    TurboQuantEngine& operator=(const TurboQuantEngine&) = delete;

    /**
     * Compress a batch of vectors (async).
     *
     * @param d_vectors   Device ptr: (batch, head_dim) float32 input
     * @param batch       Number of vectors
     * @param d_indices   Device ptr: (batch, total_angles) uint8 output
     * @param d_radii     Device ptr: (batch,) float32 output
     */
    void compress_batch(const float* d_vectors, int batch,
                        unsigned char* d_indices, float* d_radii);

    /**
     * Decompress a batch of vectors (async).
     *
     * @param d_radii     Device ptr: (batch,) float32 input
     * @param d_indices   Device ptr: (batch, total_angles) uint8 input
     * @param batch       Number of vectors
     * @param d_vectors   Device ptr: (batch, head_dim) float32 output
     */
    void decompress_batch(const float* d_radii,
                          const unsigned char* d_indices,
                          int batch, float* d_vectors);

    /**
     * Compress QJL residuals (async).
     *
     * @param d_residuals  Device ptr: (batch, head_dim) float32
     * @param batch        Number of vectors
     * @param d_sign_bits  Device ptr: (batch, ceil(proj_dim/32)) uint32 output
     * @param d_scales     Device ptr: (batch,) float32 output
     */
    void compress_qjl_batch(const float* d_residuals, int batch,
                            uint32_t* d_sign_bits, float* d_scales);

    /**
     * Compute quality metrics for a batch (async).
     *
     * @param d_originals     Device ptr: (batch, head_dim) float32
     * @param d_reconstructed Device ptr: (batch, head_dim) float32
     * @param batch           Number of vectors
     * @param d_mse           Device ptr: (batch,) float32 output
     * @param d_cosine        Device ptr: (batch,) float32 output
     */
    void compute_quality_batch(const float* d_originals,
                               const float* d_reconstructed,
                               int batch,
                               float* d_mse, float* d_cosine);

    /** Get configuration */
    const TurboQuantConfig& get_config() const { return config_; }

    /** Get level info */
    const TurboQuantLevelInfo& get_level_info() const { return level_info_; }

    /** Synchronize stream */
    void synchronize();

private:
    TurboQuantConfig config_;
    TurboQuantLevelInfo level_info_;
    cudaStream_t stream_;

    // GPU-resident data
    float* d_rotation_;       // (head_dim, head_dim)
    float* d_rotation_t_;     // (head_dim, head_dim) transposed
    float* d_grid_full_;      // (n_grid,)
    float* d_grid_pos_;       // (n_grid,)
    float* d_cos_grid_full_;  // (n_grid,)
    float* d_sin_grid_full_;  // (n_grid,)
    float* d_cos_grid_pos_;   // (n_grid,)
    float* d_sin_grid_pos_;   // (n_grid,)
    int*   d_level_sizes_;    // (n_levels,)
    int*   d_level_offsets_;  // (n_levels+1,)
    float* d_jl_matrix_;     // (proj_dim, head_dim) — QJL projection

    // LUT scales
    float lut_scale_full_;
    float lut_scale_pos_;

    void init_rotation_matrix();
    void init_angle_grids();
    void init_level_geometry();
    void init_jl_matrix();
};

/* ========== Preset Configurations ========== */

/** 2-bit aggressive: ~8x compression */
inline TurboQuantConfig tq_config_2bit(int head_dim = 128) {
    TurboQuantConfig cfg;
    cfg.head_dim = head_dim;
    cfg.angle_bits = 2;
    cfg.enable_qjl = true;
    return cfg;
}

/** 3-bit standard: ~5.3x compression (recommended) */
inline TurboQuantConfig tq_config_3bit(int head_dim = 128) {
    TurboQuantConfig cfg;
    cfg.head_dim = head_dim;
    cfg.angle_bits = 3;
    cfg.enable_qjl = true;
    return cfg;
}

/** 4-bit high-quality: ~4x compression, near-lossless */
inline TurboQuantConfig tq_config_4bit(int head_dim = 128) {
    TurboQuantConfig cfg;
    cfg.head_dim = head_dim;
    cfg.angle_bits = 4;
    cfg.enable_qjl = true;
    return cfg;
}

} // namespace ctm

#endif // TURBOQUANT_CUH
