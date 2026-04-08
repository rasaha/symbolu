/*
 * SymbolU12 CUDA Kernel - Sattvic State Evolution
 * =================================================
 *
 * Fused kernel for Layer 1 (State Evolution) and Layer 2 (Guna Modulation).
 * Implements the "Functional Spine" approach with batched processing.
 *
 * Features:
 *   - Ghost Buffer (S_prev) for Motion (M) calculation
 *   - Cosine Similarity to S_0 for Coherence (C_s)
 *   - R-Matrix trace for integrity verification
 *   - Bitmask-based failure reporting
 *
 * Reference: docs/GOOGLE_ARCHITECTURE_PROPOSALS.md Section 30.15-30.20
 */

#include <torch/extension.h>
#include <cuda.h>
#include <cuda_runtime.h>
#include <cmath>
#include "symbol_u12_types.h"

// =============================================================================
// CUDA DEVICE HELPERS
// =============================================================================

/**
 * Warp-level sum reduction using shuffle instructions.
 * O(log N) operations for 32 threads.
 */
__device__ __forceinline__ float warpReduceSum(float val) {
    for (int offset = WARP_SIZE / 2; offset > 0; offset /= 2) {
        val += __shfl_down_sync(0xffffffff, val, offset);
    }
    return val;
}

/**
 * Block-level sum reduction.
 * First reduces within warps, then across warps via shared memory.
 */
__device__ float blockReduceSum(float val, float* shared) {
    int lane = threadIdx.x % WARP_SIZE;
    int wid = threadIdx.x / WARP_SIZE;

    // Warp-level reduction
    val = warpReduceSum(val);

    // Write reduced value to shared memory
    if (lane == 0) {
        shared[wid] = val;
    }
    __syncthreads();

    // Final reduction in first warp
    val = (threadIdx.x < blockDim.x / WARP_SIZE) ? shared[lane] : 0.0f;
    if (wid == 0) {
        val = warpReduceSum(val);
    }

    return val;
}

/**
 * Calculate R-Matrix trace for integrity check.
 * R_block is a flattened 3x3 matrix.
 */
__device__ float calculateRTrace(const float* R_block) {
    // Trace = R[0,0] + R[1,1] + R[2,2]
    float trace = R_block[0] + R_block[4] + R_block[8];
    // Normalize: trace of rotation matrix is in [-1, 3]
    // For identity (perfect alignment): trace = 3.0
    return (trace + 1.0f) / 4.0f;
}

// =============================================================================
// MAIN CUDA KERNEL: BATCHED SATTVIC EVOLUTION
// =============================================================================

__global__ void sattvicEvolutionKernel(
    float* __restrict__ S_t,            // [B, 124] Current state (in/out)
    float* __restrict__ S_prev,         // [B, 124] Ghost buffer (in/out)
    const float* __restrict__ S_0,      // [B, 124] Sattvic seed anchor
    const float* __restrict__ R_block,  // [B, 9] R-matrix blocks
    const float* __restrict__ delta,    // [B, 124] Model predictions
    const GunaWeights weights,          // Guna configuration
    float* __restrict__ output_G,       // [B] Scalar Guna output
    int* __restrict__ integrity_flags,  // [B] Integrity bitmask
    int batch_size
) {
    // Shared memory for reductions
    __shared__ float shared_reduce[4];  // For 4 warps
    __shared__ float metrics[5];        // [Cs, M, H, trace, total_p]

    int batch_idx = blockIdx.x;
    int dim_idx = threadIdx.x;

    if (batch_idx >= batch_size) return;

    // Calculate offsets for this batch item
    int offset = batch_idx * MANIFOLD_DIM;
    int r_offset = batch_idx * R_BLOCK_SIZE;

    // Pointers to this batch's data
    float* my_S_t = S_t + offset;
    float* my_S_prev = S_prev + offset;
    const float* my_S_0 = S_0 + offset;
    const float* my_delta = delta + offset;
    const float* my_R = R_block + r_offset;

    // Load values (pad with 0 for threads >= 124)
    float s_old = (dim_idx < MANIFOLD_DIM) ? my_S_t[dim_idx] : 0.0f;
    float s_0 = (dim_idx < MANIFOLD_DIM) ? my_S_0[dim_idx] : 0.0f;
    float d = (dim_idx < MANIFOLD_DIM) ? my_delta[dim_idx] : 0.0f;
    float s_prev_val = (dim_idx < MANIFOLD_DIM) ? my_S_prev[dim_idx] : 0.0f;

    // =========================================================================
    // LAYER 1: STATE EVOLUTION WITH PERSISTENCE PULL
    // S_{t+1} = S_t + delta + lambda * (S_0 - S_t)
    // =========================================================================
    float s_new = s_old + d + weights.lambda * (s_0 - s_old);

    // Write back new state
    if (dim_idx < MANIFOLD_DIM) {
        my_S_t[dim_idx] = s_new;
    }
    __syncthreads();

    // =========================================================================
    // LAYER 2A: MOTION (M) - Euclidean distance to previous state
    // M = ||S_t - S_prev||
    // =========================================================================
    float diff = s_new - s_prev_val;
    float sq_diff = diff * diff;
    float M_squared = blockReduceSum(sq_diff, shared_reduce);

    if (threadIdx.x == 0) {
        metrics[1] = sqrtf(M_squared);
    }
    __syncthreads();

    // Update Ghost Buffer AFTER motion calculation
    if (dim_idx < MANIFOLD_DIM) {
        my_S_prev[dim_idx] = s_new;
    }

    // =========================================================================
    // LAYER 2B: COHERENCE (Cs) - Cosine Similarity to S_0
    // Cs = (S_t · S_0) / (||S_t|| * ||S_0||)
    // =========================================================================
    float dot = s_new * s_0;
    float mag_t = s_new * s_new;
    float mag_0 = s_0 * s_0;

    float total_dot = blockReduceSum(dot, shared_reduce);
    __syncthreads();
    float total_mag_t = blockReduceSum(mag_t, shared_reduce);
    __syncthreads();
    float total_mag_0 = blockReduceSum(mag_0, shared_reduce);
    __syncthreads();

    if (threadIdx.x == 0) {
        float denom = sqrtf(total_mag_t) * sqrtf(total_mag_0) + 1e-9f;
        metrics[0] = total_dot / denom;  // Cs
    }
    __syncthreads();

    // =========================================================================
    // LAYER 2C: ENTROPY (H) - Information disorder
    // H = -sum(p * log(p)) / log(dim)
    // =========================================================================
    float p = fabsf(s_new);
    float sum_p = blockReduceSum(p, shared_reduce);
    __syncthreads();

    if (threadIdx.x == 0) {
        metrics[4] = sum_p;  // Store for normalization
    }
    __syncthreads();

    float total_p = metrics[4];
    float p_norm = p / (total_p + 1e-9f);
    float p_log_p = (p_norm > 1e-9f) ? p_norm * logf(p_norm) : 0.0f;

    float total_entropy = blockReduceSum(p_log_p, shared_reduce);
    __syncthreads();

    if (threadIdx.x == 0) {
        metrics[2] = -total_entropy / logf((float)MANIFOLD_DIM);  // H
    }
    __syncthreads();

    // =========================================================================
    // LAYER 3: R-MATRIX INTEGRITY CHECK
    // =========================================================================
    if (threadIdx.x == 0) {
        float trace = calculateRTrace(my_R);
        metrics[3] = trace;
    }
    __syncthreads();

    // =========================================================================
    // LAYER 4: GUNA MODULATION & INTEGRITY BITMASK
    // =========================================================================
    if (threadIdx.x == 0) {
        float Cs = metrics[0];
        float M = metrics[1];
        float H = metrics[2];
        float trace = metrics[3];

        // Build integrity bitmask
        int flags = INTEGRITY_OK;

        if (Cs < COHERENCE_THRESHOLD) {
            flags |= COHERENCE_FAILURE;
        }
        if (M > MOTION_THRESHOLD) {
            flags |= MOTION_OVERDRIVE;
        }
        if (trace < weights.integrity_threshold) {
            flags |= TRACE_COLLAPSE;
        }
        if (H > ENTROPY_THRESHOLD) {
            flags |= ENTROPY_SPIKE;
        }

        integrity_flags[batch_idx] = flags;

        // Guna raw calculations
        float S_raw = Cs * (1.0f - H);
        float R_raw = M * (1.0f - fabsf(H - 0.5f));
        float T_raw = H * (1.0f - Cs);

        // Normalize
        float total = S_raw + R_raw + T_raw + 1e-9f;
        float S = S_raw / total;
        float R = R_raw / total;
        float T = T_raw / total;

        // Apply weights and write output
        output_G[batch_idx] = (weights.w_S * S) + (weights.w_R * R) + (weights.w_T * T);
    }
}

// =============================================================================
// CUDA LAUNCHER FUNCTION
// =============================================================================

void launchCudaEvolution(
    torch::Tensor S_t,
    torch::Tensor S_prev,
    torch::Tensor S_0,
    torch::Tensor R_block,
    torch::Tensor delta,
    GunaWeights weights,
    torch::Tensor output_G,
    torch::Tensor integrity_flags
) {
    int batch_size = S_t.size(0);

    dim3 threads(THREADS_PER_BLOCK);
    dim3 blocks(batch_size);

    sattvicEvolutionKernel<<<blocks, threads>>>(
        S_t.data_ptr<float>(),
        S_prev.data_ptr<float>(),
        S_0.data_ptr<float>(),
        R_block.data_ptr<float>(),
        delta.data_ptr<float>(),
        weights,
        output_G.data_ptr<float>(),
        integrity_flags.data_ptr<int>(),
        batch_size
    );

    // Synchronize to catch errors
    cudaError_t err = cudaGetLastError();
    if (err != cudaSuccess) {
        throw std::runtime_error(
            std::string("CUDA kernel error: ") + cudaGetErrorString(err)
        );
    }
}

// =============================================================================
// CPU FALLBACK IMPLEMENTATION (ATen/C++ Vectorized)
// =============================================================================

void launchCpuFallback(
    torch::Tensor S_t,
    torch::Tensor S_prev,
    torch::Tensor S_0,
    torch::Tensor R_block,
    torch::Tensor delta,
    GunaWeights weights,
    torch::Tensor output_G,
    torch::Tensor integrity_flags
) {
    int batch_size = S_t.size(0);
    int dim = S_t.size(1);

    auto S_t_a = S_t.accessor<float, 2>();
    auto S_prev_a = S_prev.accessor<float, 2>();
    auto S_0_a = S_0.accessor<float, 2>();
    auto R_block_a = R_block.accessor<float, 2>();
    auto delta_a = delta.accessor<float, 2>();
    auto output_G_a = output_G.accessor<float, 1>();
    auto flags_a = integrity_flags.accessor<int, 1>();

    for (int b = 0; b < batch_size; b++) {
        // Layer 1: State Evolution with Persistence
        float dot_sum = 0.0f, mag_t_sum = 0.0f, mag_0_sum = 0.0f;
        float motion_sq_sum = 0.0f;
        float abs_sum = 0.0f;

        for (int i = 0; i < dim; i++) {
            float s_old = S_t_a[b][i];
            float s_0 = S_0_a[b][i];
            float d = delta_a[b][i];
            float s_prev_val = S_prev_a[b][i];

            // Evolution with persistence pull
            float s_new = s_old + d + weights.lambda * (s_0 - s_old);
            S_t_a[b][i] = s_new;

            // Motion calculation (before updating S_prev)
            float diff = s_new - s_prev_val;
            motion_sq_sum += diff * diff;

            // Coherence calculation
            dot_sum += s_new * s_0;
            mag_t_sum += s_new * s_new;
            mag_0_sum += s_0 * s_0;

            // For entropy
            abs_sum += fabsf(s_new);
        }

        // Update Ghost Buffer
        for (int i = 0; i < dim; i++) {
            S_prev_a[b][i] = S_t_a[b][i];
        }

        // Metrics
        float M = sqrtf(motion_sq_sum);
        float Cs = dot_sum / (sqrtf(mag_t_sum) * sqrtf(mag_0_sum) + 1e-9f);

        // Entropy
        float entropy_sum = 0.0f;
        for (int i = 0; i < dim; i++) {
            float p = fabsf(S_t_a[b][i]) / (abs_sum + 1e-9f);
            if (p > 1e-9f) {
                entropy_sum += p * logf(p);
            }
        }
        float H = -entropy_sum / logf((float)dim);

        // R-Matrix trace
        float trace = (R_block_a[b][0] + R_block_a[b][4] + R_block_a[b][8] + 1.0f) / 4.0f;

        // Integrity bitmask
        int flags = INTEGRITY_OK;
        if (Cs < COHERENCE_THRESHOLD) flags |= COHERENCE_FAILURE;
        if (M > MOTION_THRESHOLD) flags |= MOTION_OVERDRIVE;
        if (trace < weights.integrity_threshold) flags |= TRACE_COLLAPSE;
        if (H > ENTROPY_THRESHOLD) flags |= ENTROPY_SPIKE;
        flags_a[b] = flags;

        // Guna modulation
        float S_raw = Cs * (1.0f - H);
        float R_raw = M * (1.0f - fabsf(H - 0.5f));
        float T_raw = H * (1.0f - Cs);

        float total = S_raw + R_raw + T_raw + 1e-9f;
        float S = S_raw / total;
        float R = R_raw / total;
        float T = T_raw / total;

        output_G_a[b] = (weights.w_S * S) + (weights.w_R * R) + (weights.w_T * T);
    }
}
