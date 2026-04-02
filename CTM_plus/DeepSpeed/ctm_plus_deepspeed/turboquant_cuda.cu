/*
 * TurboQuant CUDA kernels — fused PolarQuant compress / decompress.
 *
 * Architecture
 * ------------
 * One thread processes one KV vector (head_dim=128).  All 7 polar tree
 * levels are fused into a single kernel launch so intermediate radii
 * stay in registers — no global-memory round-trips between levels.
 *
 * For head_dim=128:
 *   Level 0: 64 angles   Level 1: 32   Level 2: 16   Level 3: 8
 *   Level 4:  4          Level 5:  2   Level 6:  1
 *   Total: 127 quantised angles + 1 final radius per vector.
 *
 * Quantization scheme: LUT floor quantization (matches Numba kernels).
 *   Level 0: k = clamp(floor((theta + pi) * lut_scale_full), 0, n_grid-1)
 *   Level 1+: k = clamp(floor(theta * lut_scale_pos), 0, n_grid-1)
 * This is O(1) per angle vs O(n_grid) for argmin, and produces identical
 * results on uniform grids.
 *
 * Compressed representation: uint8 grid bin indices (not float angles).
 * This matches the Numba path and enables cross-backend interop.
 * Decompress reconstructs float angles from indices via grid LUT.
 *
 * Throughput target: 10–50 GB/s on modern GPUs (memory-bound).
 *
 * Build
 * -----
 * Compiled as a PyTorch C++ extension via torch.utils.cpp_extension or
 * as a standalone .so via:
 *   nvcc -O3 -arch=sm_80 --use_fast_math -shared -Xcompiler -fPIC \
 *        -o turboquant_cuda.so turboquant_cuda.cu
 *
 * The Python bindings are in turboquant_cuda_ext.py.
 */

#include <cmath>
#include <cstdio>
#include <cstdint>

/* --------------------------------------------------------------------------
 * Constants
 * ----------------------------------------------------------------------- */

// Maximum head dimension supported by the register-resident path.
#define MAX_HEAD_DIM 256

// M_PI may not be defined in all CUDA toolchains
#ifndef M_PI
#define M_PI 3.14159265358979323846f
#endif

/* --------------------------------------------------------------------------
 * Device helpers
 * ----------------------------------------------------------------------- */

/**
 * LUT floor quantization — O(1) per angle, matches Numba _compress_polar_numba.
 *
 * Level 0 (Gaussian pairs, theta in [-pi, pi]):
 *   k = clamp(floor((theta + pi) * lut_scale_full), 0, n_grid - 1)
 *
 * Level 1+ (radius pairs, theta in [0, pi/2]):
 *   k = clamp(floor(theta * lut_scale_pos), 0, n_grid - 1)
 */
__device__ __forceinline__ int quantize_angle(
    float theta,
    int   is_level0,
    float lut_scale_full,
    float lut_scale_pos,
    int   n_grid
) {
    int k;
    if (is_level0) {
        k = __float2int_rd((theta + M_PI) * lut_scale_full);  // floor
    } else {
        k = __float2int_rd(theta * lut_scale_pos);
    }
    // Clamp to [0, n_grid - 1]
    if (k < 0)       k = 0;
    if (k >= n_grid)  k = n_grid - 1;
    return k;
}

/* ==========================================================================
 * COMPRESS kernel — one thread per vector
 *
 * Output: uint8 grid bin indices (not float angles), matching Numba.
 * ========================================================================== */

extern "C" __global__ void turboquant_compress_kernel(
    const float* __restrict__ rotated,       // (batch, head_dim)
    const float* __restrict__ grid_full,     // (n_grid,) — level 0 midpoints
    const float* __restrict__ grid_pos,      // (n_grid,) — level 1+ midpoints
    const int*   __restrict__ level_sizes,   // (n_levels,)  — n_pairs per polar tree level
    const int*   __restrict__ level_offsets,  // (n_levels+1,) — cumulative angle offsets
    float lut_scale_full,                    // n_grid / (2*pi)
    float lut_scale_pos,                     // 2*n_grid / pi
    int   n_levels,                          // number of polar tree levels (7 for d=128)
    int   head_dim,
    int   n_grid,                            // 2**angle_bits
    int   batch,
    unsigned char* __restrict__ out_indices,  // (batch, total_angles) uint8 — grid bin indices
    float*         __restrict__ out_radii     // (batch,)
) {
    int tid = blockIdx.x * blockDim.x + threadIdx.x;
    if (tid >= batch) return;

    // Load vector into register array
    float radii[MAX_HEAD_DIM];
    float new_radii[MAX_HEAD_DIM / 2 + 1];
    const float* vec = rotated + (long long)tid * head_dim;
    for (int i = 0; i < head_dim; i++) {
        radii[i] = vec[i];
    }

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

            int idx = quantize_angle(theta, is_level0, lut_scale_full, lut_scale_pos, n_grid);
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
 * DECOMPRESS kernel — one thread per vector
 *
 * Input: uint8 grid bin indices.  Reconstructs float angles via grid LUT.
 * ========================================================================== */

extern "C" __global__ void turboquant_decompress_kernel(
    const float*         __restrict__ in_radii,       // (batch,)
    const unsigned char* __restrict__ in_indices,      // (batch, total_angles) uint8
    const float*         __restrict__ cos_grid_full,   // (n_grid,) precomputed cos for level 0
    const float*         __restrict__ sin_grid_full,   // (n_grid,) precomputed sin for level 0
    const float*         __restrict__ cos_grid_pos,    // (n_grid,) precomputed cos for level 1+
    const float*         __restrict__ sin_grid_pos,    // (n_grid,) precomputed sin for level 1+
    const int*           __restrict__ level_sizes,     // (n_levels,)
    const int*           __restrict__ level_offsets,    // (n_levels+1,)
    int   n_levels,
    int   head_dim,
    int   batch,
    float*               __restrict__ out_vectors      // (batch, head_dim)
) {
    int tid = blockIdx.x * blockDim.x + threadIdx.x;
    if (tid >= batch) return;

    long long total_angles_offset = (long long)tid * (head_dim - 1);

    // Start with final radius
    float radii[MAX_HEAD_DIM];
    float new_coords[MAX_HEAD_DIM];
    radii[0] = in_radii[tid];
    int cur_len = 1;

    // Reverse through levels (root → leaves)
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
                // Odd carry-forward
                new_coords[nc++] = r;
            }
        }

        for (int i = 0; i < nc; i++) {
            radii[i] = new_coords[i];
        }
        cur_len = nc;
    }

    // Write output (rotated-domain coords — inverse rotation done on host)
    float* out = out_vectors + (long long)tid * head_dim;
    for (int i = 0; i < head_dim; i++) {
        out[i] = radii[i];
    }
}

/* ==========================================================================
 * FUSED compress+rotate kernel (rotation fused into compress)
 *
 * Each thread loads one row of the input, multiplies by rotation matrix
 * in shared memory, then runs all 7 polar levels.  This avoids a
 * separate GEMM launch for the rotation.
 *
 * NOTE: Shared memory usage = head_dim * head_dim * sizeof(float).
 * For head_dim=128: 64KB.  Requires cudaFuncSetAttribute to raise the
 * shared memory limit above the default 48KB on Ampere+ GPUs.
 * The Python bindings handle this automatically.
 * ========================================================================== */

extern "C" __global__ void turboquant_compress_fused_kernel(
    const float* __restrict__ vectors,       // (batch, head_dim)
    const float* __restrict__ rotation,      // (head_dim, head_dim) row-major
    const float* __restrict__ grid_full,     // (n_grid,)
    const float* __restrict__ grid_pos,      // (n_grid,)
    const int*   __restrict__ level_sizes,
    const int*   __restrict__ level_offsets,
    float lut_scale_full,
    float lut_scale_pos,
    int   n_levels,
    int   head_dim,
    int   n_grid,
    int   batch,
    unsigned char* __restrict__ out_indices,  // (batch, total_angles) uint8
    float*         __restrict__ out_radii
) {
    // Shared memory for rotation matrix tile
    extern __shared__ float shmem[];
    float* rot_tile = shmem;

    // Cooperative load of rotation matrix into shared memory
    int total_rot = head_dim * head_dim;
    for (int i = threadIdx.x; i < total_rot; i += blockDim.x) {
        rot_tile[i] = rotation[i];
    }
    __syncthreads();

    int tid = blockIdx.x * blockDim.x + threadIdx.x;
    if (tid >= batch) return;

    // Load and rotate vector in registers
    const float* vec = vectors + (long long)tid * head_dim;
    float radii[MAX_HEAD_DIM];
    float new_radii[MAX_HEAD_DIM / 2 + 1];

    for (int i = 0; i < head_dim; i++) {
        float sum = 0.0f;
        for (int j = 0; j < head_dim; j++) {
            // v @ R^T: dot(vec, R[:, i]) = sum_j vec[j] * R[j][i]
            // R stored row-major: R[j][i] = rot_tile[j * head_dim + i]
            sum += vec[j] * rot_tile[j * head_dim + i];
        }
        radii[i] = sum;
    }

    // Polar levels (same as compress kernel)
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

            int idx = quantize_angle(theta, is_level0, lut_scale_full, lut_scale_pos, n_grid);
            out_indices[total_angles_offset + off + p] = (unsigned char)idx;
            new_radii[nr++] = r;
        }

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
 * FUSED decompress+inverse-rotate kernel
 *
 * Same shared memory note as compress_fused_kernel.
 * Uses cosf/sinf (not __cosf/__sinf intrinsics) for consistent precision
 * with the non-fused decompress kernel.  The grid LUT avoids trig calls
 * in the inner loop anyway — cos/sin are only used if we fall through to
 * the carry-forward path (which never calls trig).
 * ========================================================================== */

extern "C" __global__ void turboquant_decompress_fused_kernel(
    const float*         __restrict__ in_radii,
    const unsigned char* __restrict__ in_indices,     // (batch, total_angles) uint8
    const float*         __restrict__ rotation_t,     // (head_dim, head_dim) — R^T row-major
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

    float radii[MAX_HEAD_DIM];
    float new_coords[MAX_HEAD_DIM];
    radii[0] = in_radii[tid];
    int cur_len = 1;

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
    // R^T stored row-major: R^T[i][j] = R[j][i]
    // coords @ R = sum_j coords[j] * R[j][i] = sum_j coords[j] * R^T[i][j]
    float* out = out_vectors + (long long)tid * head_dim;
    for (int i = 0; i < head_dim; i++) {
        float sum = 0.0f;
        for (int j = 0; j < head_dim; j++) {
            sum += radii[j] * rot_t_tile[i * head_dim + j];
        }
        out[i] = sum;
    }
}
