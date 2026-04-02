/*
 * TurboQuant CUDA Implementation — Fused PolarQuant + QJL Kernels
 *
 * Ported from DeepSpeed turboquant_cuda.cu and vLLM turboquant.py for
 * native integration with the CTM+ memory tiering controller.
 *
 * Architecture:
 *   One thread processes one KV vector (head_dim=128). All 7 polar tree
 *   levels are fused into a single kernel so intermediate radii stay in
 *   registers — no global-memory round-trips between levels.
 *
 * For head_dim=128:
 *   Level 0: 64 angles   Level 1: 32   Level 2: 16   Level 3: 8
 *   Level 4:  4          Level 5:  2   Level 6:  1
 *   Total: 127 quantised angles + 1 final radius per vector.
 *
 * Throughput target: 10-50 GB/s on modern GPUs (memory-bound).
 *
 * SPDX-License-Identifier: MIT
 */

#include "turboquant.cuh"
#include <cmath>
#include <cstdio>
#include <cstdlib>

namespace ctm {

/* ==========================================================================
 * COMPRESS kernel — fused rotate + polar quantization
 *
 * Shared memory for rotation matrix tile. One thread per vector.
 * Output: uint8 grid bin indices (matching Numba/DeepSpeed format).
 * ========================================================================== */

__global__ void turboquant_compress_fused(
    const float*         __restrict__ vectors,
    const float*         __restrict__ rotation,
    const float*         __restrict__ grid_full,
    const float*         __restrict__ grid_pos,
    const int*           __restrict__ level_sizes,
    const int*           __restrict__ level_offsets,
    float lut_scale_full,
    float lut_scale_pos,
    int   n_levels,
    int   head_dim,
    int   n_grid,
    int   batch,
    unsigned char*       __restrict__ out_indices,
    float*               __restrict__ out_radii
) {
    // Load rotation matrix into shared memory
    extern __shared__ float shmem[];
    float* rot_tile = shmem;

    int total_rot = head_dim * head_dim;
    for (int i = threadIdx.x; i < total_rot; i += blockDim.x) {
        rot_tile[i] = rotation[i];
    }
    __syncthreads();

    int tid = blockIdx.x * blockDim.x + threadIdx.x;
    if (tid >= batch) return;

    // Load and rotate vector in registers
    const float* vec = vectors + (long long)tid * head_dim;
    float radii[TQ_MAX_HEAD_DIM];
    float new_radii[TQ_MAX_HEAD_DIM / 2 + 1];

    // v' = v @ R^T: dot(vec, R[:, i]) = sum_j vec[j] * R[j][i]
    for (int i = 0; i < head_dim; i++) {
        float sum = 0.0f;
        for (int j = 0; j < head_dim; j++) {
            sum += vec[j] * rot_tile[j * head_dim + i];
        }
        radii[i] = sum;
    }

    // Recursive polar transformation — all levels in registers
    long long total_angles_offset = (long long)tid * (head_dim - 1);
    int cur_len = head_dim;

    for (int lvl = 0; lvl < n_levels; lvl++) {
        int n_pairs = level_sizes[lvl];
        int off = level_offsets[lvl];
        int is_level0 = (lvl == 0);
        int nr = 0;

        for (int p = 0; p < n_pairs; p++) {
            float x = radii[2 * p];
            float y = radii[2 * p + 1];
            float r = sqrtf(x * x + y * y);
            float theta = atan2f(y, x);

            int idx = tq_quantize_angle(theta, is_level0,
                                        lut_scale_full, lut_scale_pos, n_grid);
            out_indices[total_angles_offset + off + p] = (unsigned char)idx;
            new_radii[nr++] = r;
        }

        // Carry-forward odd element
        if (cur_len % 2 == 1) {
            new_radii[nr++] = radii[cur_len - 1];
        }

        for (int i = 0; i < nr; i++) {
            radii[i] = new_radii[i];
        }
        cur_len = nr;
    }

    out_radii[tid] = radii[0];
}

/* ==========================================================================
 * DECOMPRESS kernel — fused inverse-polar + inverse-rotate
 *
 * Uses precomputed cos/sin LUTs — no trig calls in the hot path.
 * ========================================================================== */

__global__ void turboquant_decompress_fused(
    const float*         __restrict__ in_radii,
    const unsigned char* __restrict__ in_indices,
    const float*         __restrict__ rotation_t,
    const float*         __restrict__ cos_grid_full,
    const float*         __restrict__ sin_grid_full,
    const float*         __restrict__ cos_grid_pos,
    const float*         __restrict__ sin_grid_pos,
    const int*           __restrict__ level_sizes,
    const int*           __restrict__ level_offsets,
    int   n_levels,
    int   head_dim,
    int   batch,
    float*               __restrict__ out_vectors
) {
    extern __shared__ float shmem[];
    float* rot_t_tile = shmem;

    int total_rot = head_dim * head_dim;
    for (int i = threadIdx.x; i < total_rot; i += blockDim.x) {
        rot_t_tile[i] = rotation_t[i];
    }
    __syncthreads();

    int tid = blockIdx.x * blockDim.x + threadIdx.x;
    if (tid >= batch) return;

    long long total_angles_offset = (long long)tid * (head_dim - 1);

    // Start from final radius
    float radii[TQ_MAX_HEAD_DIM];
    float new_coords[TQ_MAX_HEAD_DIM];
    radii[0] = in_radii[tid];
    int cur_len = 1;

    // Reverse through levels (root -> leaves)
    for (int rev = 0; rev < n_levels; rev++) {
        int lvl = n_levels - 1 - rev;
        int n_angles = level_sizes[lvl];
        int off = level_offsets[lvl];
        int is_level0 = (lvl == 0);

        int nc = 0;
        int a_idx = 0;

        for (int i = 0; i < cur_len; i++) {
            float r = radii[i];
            if (a_idx < n_angles) {
                int grid_idx = (int)in_indices[total_angles_offset + off + a_idx];
                a_idx++;
                float cos_v, sin_v;
                if (is_level0) {
                    cos_v = cos_grid_full[grid_idx];
                    sin_v = sin_grid_full[grid_idx];
                } else {
                    cos_v = cos_grid_pos[grid_idx];
                    sin_v = sin_grid_pos[grid_idx];
                }
                new_coords[nc++] = r * cos_v;
                new_coords[nc++] = r * sin_v;
            } else {
                new_coords[nc++] = r;
            }
        }

        for (int i = 0; i < nc; i++) {
            radii[i] = new_coords[i];
        }
        cur_len = nc;
    }

    // Inverse rotation: out = coords @ R
    float* out = out_vectors + (long long)tid * head_dim;
    for (int i = 0; i < head_dim; i++) {
        float sum = 0.0f;
        for (int j = 0; j < head_dim; j++) {
            sum += radii[j] * rot_t_tile[i * head_dim + j];
        }
        out[i] = sum;
    }
}

/* ==========================================================================
 * QJL sign-bit compression kernel
 *
 * Projects residual with JL matrix, stores sign bits packed into uint32.
 * Scale = mean(|projected|) for unbiased estimation.
 * ========================================================================== */

__global__ void qjl_compress_residual(
    const float*   __restrict__ residuals,
    const float*   __restrict__ jl_matrix,
    int   head_dim,
    int   proj_dim,
    int   batch,
    uint32_t*      __restrict__ out_sign_bits,
    float*         __restrict__ out_scales
) {
    int tid = blockIdx.x * blockDim.x + threadIdx.x;
    if (tid >= batch) return;

    const float* residual = residuals + (long long)tid * head_dim;
    int words_per_vector = (proj_dim + 31) / 32;
    uint32_t* signs = out_sign_bits + (long long)tid * words_per_vector;

    float abs_sum = 0.0f;

    for (int w = 0; w < words_per_vector; w++) {
        uint32_t bits = 0;
        int base = w * 32;

        for (int b = 0; b < 32 && (base + b) < proj_dim; b++) {
            int proj_idx = base + b;
            const float* jl_row = jl_matrix + (long long)proj_idx * head_dim;

            // Dot product: JL[proj_idx, :] . residual
            float dot = 0.0f;
            for (int j = 0; j < head_dim; j++) {
                dot += jl_row[j] * residual[j];
            }

            abs_sum += fabsf(dot);

            // Store sign bit (1 = positive, 0 = negative)
            if (dot >= 0.0f) {
                bits |= (1u << b);
            }
        }

        signs[w] = bits;
    }

    // Scale = mean(|projected|) for unbiased estimation
    out_scales[tid] = abs_sum / (float)proj_dim;
}

/* ==========================================================================
 * Quality metrics kernel
 *
 * Computes per-vector MSE, cosine similarity, and SNR.
 * ========================================================================== */

__global__ void turboquant_compute_quality(
    const float*   __restrict__ originals,
    const float*   __restrict__ reconstructed,
    int   head_dim,
    int   batch,
    float*         __restrict__ out_mse,
    float*         __restrict__ out_cosine,
    float*         __restrict__ out_snr
) {
    int tid = blockIdx.x * blockDim.x + threadIdx.x;
    if (tid >= batch) return;

    const float* orig = originals + (long long)tid * head_dim;
    const float* recon = reconstructed + (long long)tid * head_dim;

    float sum_sq_err = 0.0f;
    float sum_orig_sq = 0.0f;
    float sum_recon_sq = 0.0f;
    float dot_product = 0.0f;

    for (int i = 0; i < head_dim; i++) {
        float o = orig[i];
        float r = recon[i];
        float err = o - r;

        sum_sq_err += err * err;
        sum_orig_sq += o * o;
        sum_recon_sq += r * r;
        dot_product += o * r;
    }

    float mse = sum_sq_err / (float)head_dim;
    float denom = sqrtf(sum_orig_sq) * sqrtf(sum_recon_sq) + 1e-10f;
    float cosine = dot_product / denom;
    float snr = (mse > 0.0f && sum_orig_sq > 0.0f)
        ? 10.0f * log10f(sum_orig_sq / (mse * (float)head_dim + 1e-10f))
        : 100.0f;

    out_mse[tid] = mse;
    out_cosine[tid] = cosine;
    out_snr[tid] = snr;
}

/* ==========================================================================
 * TurboQuantEngine implementation
 * ========================================================================== */

// Helper: simple host-side RNG for rotation matrix generation
static void host_randn(float* out, int n, uint64_t seed) {
    // Box-Muller transform with LCG
    uint64_t state = seed;
    for (int i = 0; i < n; i += 2) {
        state = state * 6364136223846793005ULL + 1442695040888963407ULL;
        float u1 = (float)((state >> 33) & 0x7FFFFFFF) / (float)0x7FFFFFFF;
        state = state * 6364136223846793005ULL + 1442695040888963407ULL;
        float u2 = (float)((state >> 33) & 0x7FFFFFFF) / (float)0x7FFFFFFF;

        u1 = fmaxf(u1, 1e-10f);
        float z0 = sqrtf(-2.0f * logf(u1)) * cosf(2.0f * M_PI * u2);
        float z1 = sqrtf(-2.0f * logf(u1)) * sinf(2.0f * M_PI * u2);

        out[i] = z0;
        if (i + 1 < n) out[i + 1] = z1;
    }
}

// Helper: Gram-Schmidt QR decomposition for orthogonal rotation matrix
static void host_qr_orthogonal(float* Q, const float* A, int d) {
    // Copy A to Q
    for (int i = 0; i < d * d; i++) Q[i] = A[i];

    // Modified Gram-Schmidt
    for (int j = 0; j < d; j++) {
        // Normalize column j
        float norm = 0.0f;
        for (int i = 0; i < d; i++) {
            norm += Q[i * d + j] * Q[i * d + j];
        }
        norm = sqrtf(norm);
        if (norm > 1e-10f) {
            for (int i = 0; i < d; i++) Q[i * d + j] /= norm;
        }

        // Orthogonalize remaining columns against column j
        for (int k = j + 1; k < d; k++) {
            float dot = 0.0f;
            for (int i = 0; i < d; i++) {
                dot += Q[i * d + j] * Q[i * d + k];
            }
            for (int i = 0; i < d; i++) {
                Q[i * d + k] -= dot * Q[i * d + j];
            }
        }
    }
}

void TurboQuantEngine::init_rotation_matrix() {
    int d = config_.head_dim;
    int n = d * d;

    float* h_random = new float[n];
    float* h_rotation = new float[n];
    float* h_rotation_t = new float[n];

    host_randn(h_random, n, config_.seed);
    host_qr_orthogonal(h_rotation, h_random, d);

    // Transpose
    for (int i = 0; i < d; i++) {
        for (int j = 0; j < d; j++) {
            h_rotation_t[i * d + j] = h_rotation[j * d + i];
        }
    }

    cudaMalloc(&d_rotation_, n * sizeof(float));
    cudaMalloc(&d_rotation_t_, n * sizeof(float));
    cudaMemcpyAsync(d_rotation_, h_rotation, n * sizeof(float),
                    cudaMemcpyHostToDevice, stream_);
    cudaMemcpyAsync(d_rotation_t_, h_rotation_t, n * sizeof(float),
                    cudaMemcpyHostToDevice, stream_);

    delete[] h_random;
    delete[] h_rotation;
    delete[] h_rotation_t;
}

void TurboQuantEngine::init_angle_grids() {
    int n_grid = config_.n_grid();

    float* h_grid_full = new float[n_grid];
    float* h_grid_pos = new float[n_grid];
    float* h_cos_full = new float[n_grid];
    float* h_sin_full = new float[n_grid];
    float* h_cos_pos = new float[n_grid];
    float* h_sin_pos = new float[n_grid];

    // Full-range grid for level 0: [-pi, pi]
    float step_full = 2.0f * M_PI / n_grid;
    for (int i = 0; i < n_grid; i++) {
        h_grid_full[i] = -M_PI + step_full * i + step_full * 0.5f;
        h_cos_full[i] = cosf(h_grid_full[i]);
        h_sin_full[i] = sinf(h_grid_full[i]);
    }

    // Positive-quadrant grid for level 1+: [0, pi/2]
    float step_pos = (M_PI * 0.5f) / n_grid;
    for (int i = 0; i < n_grid; i++) {
        h_grid_pos[i] = step_pos * i + step_pos * 0.5f;
        h_cos_pos[i] = cosf(h_grid_pos[i]);
        h_sin_pos[i] = sinf(h_grid_pos[i]);
    }

    // LUT scales
    lut_scale_full_ = (float)n_grid / (2.0f * M_PI);
    lut_scale_pos_  = (float)n_grid / (M_PI * 0.5f);

    // Allocate and copy to GPU
    cudaMalloc(&d_grid_full_, n_grid * sizeof(float));
    cudaMalloc(&d_grid_pos_, n_grid * sizeof(float));
    cudaMalloc(&d_cos_grid_full_, n_grid * sizeof(float));
    cudaMalloc(&d_sin_grid_full_, n_grid * sizeof(float));
    cudaMalloc(&d_cos_grid_pos_, n_grid * sizeof(float));
    cudaMalloc(&d_sin_grid_pos_, n_grid * sizeof(float));

    cudaMemcpyAsync(d_grid_full_, h_grid_full, n_grid * sizeof(float),
                    cudaMemcpyHostToDevice, stream_);
    cudaMemcpyAsync(d_grid_pos_, h_grid_pos, n_grid * sizeof(float),
                    cudaMemcpyHostToDevice, stream_);
    cudaMemcpyAsync(d_cos_grid_full_, h_cos_full, n_grid * sizeof(float),
                    cudaMemcpyHostToDevice, stream_);
    cudaMemcpyAsync(d_sin_grid_full_, h_sin_full, n_grid * sizeof(float),
                    cudaMemcpyHostToDevice, stream_);
    cudaMemcpyAsync(d_cos_grid_pos_, h_cos_pos, n_grid * sizeof(float),
                    cudaMemcpyHostToDevice, stream_);
    cudaMemcpyAsync(d_sin_grid_pos_, h_sin_pos, n_grid * sizeof(float),
                    cudaMemcpyHostToDevice, stream_);

    delete[] h_grid_full;
    delete[] h_grid_pos;
    delete[] h_cos_full;
    delete[] h_sin_full;
    delete[] h_cos_pos;
    delete[] h_sin_pos;
}

void TurboQuantEngine::init_level_geometry() {
    int d = config_.head_dim;
    level_info_.n_levels = 0;
    int cur = d;
    int offset = 0;

    while (cur > 1) {
        int n_pairs = cur / 2;
        int lvl = level_info_.n_levels;
        level_info_.level_sizes[lvl] = n_pairs;
        level_info_.level_offsets[lvl] = offset;
        offset += n_pairs;
        cur = (cur + 1) / 2;
        level_info_.n_levels++;
    }
    level_info_.level_offsets[level_info_.n_levels] = offset;

    cudaMalloc(&d_level_sizes_, level_info_.n_levels * sizeof(int));
    cudaMalloc(&d_level_offsets_, (level_info_.n_levels + 1) * sizeof(int));
    cudaMemcpyAsync(d_level_sizes_, level_info_.level_sizes,
                    level_info_.n_levels * sizeof(int),
                    cudaMemcpyHostToDevice, stream_);
    cudaMemcpyAsync(d_level_offsets_, level_info_.level_offsets,
                    (level_info_.n_levels + 1) * sizeof(int),
                    cudaMemcpyHostToDevice, stream_);
}

void TurboQuantEngine::init_jl_matrix() {
    if (!config_.enable_qjl) {
        d_jl_matrix_ = nullptr;
        return;
    }

    int proj_dim = config_.qjl_proj_dim > 0 ? config_.qjl_proj_dim
                                              : config_.head_dim;
    int n = proj_dim * config_.head_dim;

    // Random +/-1/sqrt(m) Rademacher matrix
    float* h_jl = new float[n];
    uint64_t state = config_.seed + 1000;
    float scale = 1.0f / sqrtf((float)proj_dim);

    for (int i = 0; i < n; i++) {
        state = state * 6364136223846793005ULL + 1442695040888963407ULL;
        h_jl[i] = ((state >> 63) & 1) ? scale : -scale;
    }

    cudaMalloc(&d_jl_matrix_, n * sizeof(float));
    cudaMemcpyAsync(d_jl_matrix_, h_jl, n * sizeof(float),
                    cudaMemcpyHostToDevice, stream_);

    delete[] h_jl;
}

TurboQuantEngine::TurboQuantEngine(const TurboQuantConfig& config,
                                   cudaStream_t stream)
    : config_(config), stream_(stream),
      d_rotation_(nullptr), d_rotation_t_(nullptr),
      d_grid_full_(nullptr), d_grid_pos_(nullptr),
      d_cos_grid_full_(nullptr), d_sin_grid_full_(nullptr),
      d_cos_grid_pos_(nullptr), d_sin_grid_pos_(nullptr),
      d_level_sizes_(nullptr), d_level_offsets_(nullptr),
      d_jl_matrix_(nullptr),
      lut_scale_full_(0.0f), lut_scale_pos_(0.0f)
{
    init_level_geometry();
    init_rotation_matrix();
    init_angle_grids();
    init_jl_matrix();
}

TurboQuantEngine::~TurboQuantEngine() {
    if (d_rotation_)       cudaFree(d_rotation_);
    if (d_rotation_t_)     cudaFree(d_rotation_t_);
    if (d_grid_full_)      cudaFree(d_grid_full_);
    if (d_grid_pos_)       cudaFree(d_grid_pos_);
    if (d_cos_grid_full_)  cudaFree(d_cos_grid_full_);
    if (d_sin_grid_full_)  cudaFree(d_sin_grid_full_);
    if (d_cos_grid_pos_)   cudaFree(d_cos_grid_pos_);
    if (d_sin_grid_pos_)   cudaFree(d_sin_grid_pos_);
    if (d_level_sizes_)    cudaFree(d_level_sizes_);
    if (d_level_offsets_)  cudaFree(d_level_offsets_);
    if (d_jl_matrix_)      cudaFree(d_jl_matrix_);
}

void TurboQuantEngine::compress_batch(const float* d_vectors, int batch,
                                       unsigned char* d_indices,
                                       float* d_radii) {
    int block_size = TQ_DEFAULT_BLOCK_SIZE;
    int num_blocks = (batch + block_size - 1) / block_size;
    size_t shmem_size = config_.head_dim * config_.head_dim * sizeof(float);

    turboquant_compress_fused<<<num_blocks, block_size, shmem_size, stream_>>>(
        d_vectors, d_rotation_, d_grid_full_, d_grid_pos_,
        d_level_sizes_, d_level_offsets_,
        lut_scale_full_, lut_scale_pos_,
        level_info_.n_levels, config_.head_dim,
        config_.n_grid(), batch,
        d_indices, d_radii
    );
}

void TurboQuantEngine::decompress_batch(const float* d_radii,
                                         const unsigned char* d_indices,
                                         int batch, float* d_vectors) {
    int block_size = TQ_DEFAULT_BLOCK_SIZE;
    int num_blocks = (batch + block_size - 1) / block_size;
    size_t shmem_size = config_.head_dim * config_.head_dim * sizeof(float);

    turboquant_decompress_fused<<<num_blocks, block_size, shmem_size, stream_>>>(
        d_radii, d_indices, d_rotation_t_,
        d_cos_grid_full_, d_sin_grid_full_,
        d_cos_grid_pos_, d_sin_grid_pos_,
        d_level_sizes_, d_level_offsets_,
        level_info_.n_levels, config_.head_dim,
        batch, d_vectors
    );
}

void TurboQuantEngine::compress_qjl_batch(const float* d_residuals, int batch,
                                           uint32_t* d_sign_bits,
                                           float* d_scales) {
    if (!d_jl_matrix_) return;

    int proj_dim = config_.qjl_proj_dim > 0 ? config_.qjl_proj_dim
                                              : config_.head_dim;
    int block_size = TQ_DEFAULT_BLOCK_SIZE;
    int num_blocks = (batch + block_size - 1) / block_size;

    qjl_compress_residual<<<num_blocks, block_size, 0, stream_>>>(
        d_residuals, d_jl_matrix_,
        config_.head_dim, proj_dim, batch,
        d_sign_bits, d_scales
    );
}

void TurboQuantEngine::compute_quality_batch(const float* d_originals,
                                              const float* d_reconstructed,
                                              int batch,
                                              float* d_mse, float* d_cosine) {
    int block_size = TQ_DEFAULT_BLOCK_SIZE;
    int num_blocks = (batch + block_size - 1) / block_size;

    // Allocate temporary SNR buffer
    float* d_snr;
    cudaMalloc(&d_snr, batch * sizeof(float));

    turboquant_compute_quality<<<num_blocks, block_size, 0, stream_>>>(
        d_originals, d_reconstructed,
        config_.head_dim, batch,
        d_mse, d_cosine, d_snr
    );

    cudaFree(d_snr);
}

void TurboQuantEngine::synchronize() {
    cudaStreamSynchronize(stream_);
}

} // namespace ctm
