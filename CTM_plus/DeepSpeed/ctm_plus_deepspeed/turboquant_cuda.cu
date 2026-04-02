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
 * Constants (head_dim=128 specialisation)
 * ----------------------------------------------------------------------- */

// Maximum head dimension supported by the register-resident path.
// For larger dims, fall back to shared memory (not implemented yet).
#define MAX_HEAD_DIM 256
#define MAX_ANGLES   (MAX_HEAD_DIM - 1)

/* --------------------------------------------------------------------------
 * Device helpers
 * ----------------------------------------------------------------------- */

__device__ __forceinline__ int nearest_grid_idx(
    float theta,
    const float* __restrict__ grid,
    int n_grid
) {
    // Linear scan — n_grid is small (4, 8, or 16 typically)
    int best = 0;
    float best_d = fabsf(theta - grid[0]);
    for (int g = 1; g < n_grid; g++) {
        float d = fabsf(theta - grid[g]);
        if (d < best_d) {
            best_d = d;
            best = g;
        }
    }
    return best;
}

/* ==========================================================================
 * COMPRESS kernel — one thread per vector
 * ========================================================================== */

extern "C" __global__ void turboquant_compress_kernel(
    const float* __restrict__ rotated,      // (batch, head_dim)
    const float* __restrict__ grid_full,    // (n_grid,) — level 0
    const float* __restrict__ grid_pos,     // (n_grid,) — level 1+
    const int*   __restrict__ level_sizes,  // (n_levels,)
    const int*   __restrict__ level_offsets, // (n_levels+1,)
    int   n_levels,
    int   head_dim,
    int   n_grid,
    int   batch,
    float*       __restrict__ out_angles,   // (batch, total_angles)
    int*         __restrict__ out_indices,   // (batch, total_angles)
    float*       __restrict__ out_radii     // (batch,)
) {
    int tid = blockIdx.x * blockDim.x + threadIdx.x;
    if (tid >= batch) return;

    // Load vector into register array
    float radii[MAX_HEAD_DIM];
    const float* vec = rotated + (long long)tid * head_dim;
    for (int i = 0; i < head_dim; i++) {
        radii[i] = vec[i];
    }

    int total_angles_offset = (long long)tid * (head_dim - 1);
    // ^ safe upper bound; actual total_angles <= head_dim - 1

    int cur_len = head_dim;

    for (int lvl = 0; lvl < n_levels; lvl++) {
        int n_pairs = level_sizes[lvl];
        int off = level_offsets[lvl];
        const float* grid = (lvl == 0) ? grid_full : grid_pos;

        float new_radii[MAX_HEAD_DIM / 2 + 1];
        int nr = 0;

        for (int p = 0; p < n_pairs; p++) {
            float x = radii[2 * p];
            float y = radii[2 * p + 1];
            float r = sqrtf(x * x + y * y);
            float theta = atan2f(y, x);

            int idx = nearest_grid_idx(theta, grid, n_grid);

            // Store quantised angle and index
            out_angles[total_angles_offset + off + p] = grid[idx];
            out_indices[total_angles_offset + off + p] = idx;

            new_radii[nr++] = r;
        }

        // Carry-forward odd element
        if (cur_len % 2 == 1) {
            new_radii[nr++] = radii[cur_len - 1];
        }

        // Copy back to radii
        for (int i = 0; i < nr; i++) {
            radii[i] = new_radii[i];
        }
        cur_len = nr;
    }

    out_radii[tid] = radii[0];
}

/* ==========================================================================
 * DECOMPRESS kernel — one thread per vector
 * ========================================================================== */

extern "C" __global__ void turboquant_decompress_kernel(
    const float* __restrict__ in_radii,     // (batch,)
    const float* __restrict__ in_angles,    // (batch, total_angles)
    const int*   __restrict__ level_sizes,  // (n_levels,)
    const int*   __restrict__ level_offsets, // (n_levels+1,)
    int   n_levels,
    int   head_dim,
    int   batch,
    float*       __restrict__ out_vectors   // (batch, head_dim)
) {
    int tid = blockIdx.x * blockDim.x + threadIdx.x;
    if (tid >= batch) return;

    int total_angles_offset = (long long)tid * (head_dim - 1);

    // Start with final radius
    float radii[MAX_HEAD_DIM];
    radii[0] = in_radii[tid];
    int cur_len = 1;

    // Reverse through levels (root → leaves)
    for (int rev = 0; rev < n_levels; rev++) {
        int lvl = n_levels - 1 - rev;
        int n_angles = level_sizes[lvl];
        int off = level_offsets[lvl];

        float new_coords[MAX_HEAD_DIM];
        int nc = 0;
        int a_idx = 0;

        for (int i = 0; i < cur_len; i++) {
            float r = radii[i];
            if (a_idx < n_angles) {
                float theta = in_angles[total_angles_offset + off + a_idx];
                a_idx++;
                new_coords[nc++] = r * cosf(theta);
                new_coords[nc++] = r * sinf(theta);
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
 * ========================================================================== */

extern "C" __global__ void turboquant_compress_fused_kernel(
    const float* __restrict__ vectors,      // (batch, head_dim) — original vectors
    const float* __restrict__ rotation,     // (head_dim, head_dim) — rotation matrix
    const float* __restrict__ grid_full,    // (n_grid,)
    const float* __restrict__ grid_pos,     // (n_grid,)
    const int*   __restrict__ level_sizes,  // (n_levels,)
    const int*   __restrict__ level_offsets, // (n_levels+1,)
    int   n_levels,
    int   head_dim,
    int   n_grid,
    int   batch,
    float*       __restrict__ out_angles,   // (batch, total_angles)
    int*         __restrict__ out_indices,   // (batch, total_angles)
    float*       __restrict__ out_radii     // (batch,)
) {
    // Shared memory for rotation matrix tile
    extern __shared__ float shmem[];
    float* rot_tile = shmem;  // head_dim * head_dim floats

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

    for (int i = 0; i < head_dim; i++) {
        float sum = 0.0f;
        for (int j = 0; j < head_dim; j++) {
            // rotation is stored row-major; we compute v @ R^T = R @ v
            // rot_tile[j * head_dim + i] = R[j][i], so dot(vec, R[:, i])
            sum += vec[j] * rot_tile[j * head_dim + i];
        }
        radii[i] = sum;
    }

    // Now run all polar levels (same as compress kernel)
    int total_angles_offset = (long long)tid * (head_dim - 1);
    int cur_len = head_dim;

    for (int lvl = 0; lvl < n_levels; lvl++) {
        int n_pairs = level_sizes[lvl];
        int off = level_offsets[lvl];
        const float* grid = (lvl == 0) ? grid_full : grid_pos;

        float new_radii[MAX_HEAD_DIM / 2 + 1];
        int nr = 0;

        for (int p = 0; p < n_pairs; p++) {
            float x = radii[2 * p];
            float y = radii[2 * p + 1];
            float r = sqrtf(x * x + y * y);
            float theta = atan2f(y, x);

            int idx = nearest_grid_idx(theta, grid, n_grid);
            out_angles[total_angles_offset + off + p] = grid[idx];
            out_indices[total_angles_offset + off + p] = idx;

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
 * ========================================================================== */

extern "C" __global__ void turboquant_decompress_fused_kernel(
    const float* __restrict__ in_radii,     // (batch,)
    const float* __restrict__ in_angles,    // (batch, total_angles)
    const float* __restrict__ rotation_t,   // (head_dim, head_dim) — R^T
    const int*   __restrict__ level_sizes,  // (n_levels,)
    const int*   __restrict__ level_offsets, // (n_levels+1,)
    int   n_levels,
    int   head_dim,
    int   batch,
    float*       __restrict__ out_vectors   // (batch, head_dim)
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

    int total_angles_offset = (long long)tid * (head_dim - 1);

    float radii[MAX_HEAD_DIM];
    radii[0] = in_radii[tid];
    int cur_len = 1;

    for (int rev = 0; rev < n_levels; rev++) {
        int lvl = n_levels - 1 - rev;
        int n_angles = level_sizes[lvl];
        int off = level_offsets[lvl];

        float new_coords[MAX_HEAD_DIM];
        int nc = 0;
        int a_idx = 0;

        for (int i = 0; i < cur_len; i++) {
            float r = radii[i];
            if (a_idx < n_angles) {
                float theta = in_angles[total_angles_offset + off + a_idx];
                a_idx++;
                new_coords[nc++] = r * __cosf(theta);
                new_coords[nc++] = r * __sinf(theta);
            } else {
                new_coords[nc++] = r;
            }
        }

        for (int i = 0; i < nc; i++) {
            radii[i] = new_coords[i];
        }
        cur_len = nc;
    }

    // Inverse rotation: out = coords @ R (i.e. R^T @ coords in column form)
    float* out = out_vectors + (long long)tid * head_dim;
    for (int i = 0; i < head_dim; i++) {
        float sum = 0.0f;
        for (int j = 0; j < head_dim; j++) {
            // coords @ R means sum_j coords[j] * R[j][i]
            // R is stored row-major, so R[j][i] = rotation_t[i * head_dim + j]
            // Wait — rotation_t = R^T, so rotation_t[i][j] = R[j][i]
            // rotation_t stored row-major: rotation_t[i * head_dim + j]
            sum += radii[j] * rot_t_tile[i * head_dim + j];
        }
        out[i] = sum;
    }
}
