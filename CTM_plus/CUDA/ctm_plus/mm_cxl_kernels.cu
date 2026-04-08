/**
 * mm_cxl_kernels.cu — CXL tier management kernels
 *
 * Handles:
 *   1. Lock-free CXL slot allocation (stack-based freelist)
 *   2. Slot deallocation for evicted tokens
 *   3. Modality stats tracking
 *
 * All allocators are lock-free using atomicAdd on the freelist stack pointer.
 * No mutexes, no CAS loops — guaranteed forward progress.
 */

#include "multimodal_inference.cuh"

// External LUT declaration
extern __constant__ float c_mm_importance[MM_IMPORTANCE_LUT_SIZE];

// ============================================================================
// Kernel: Allocate CXL slots for demoted tokens
// ============================================================================

/**
 * Each thread handles one demoted token.
 * Atomically pops a slot from the CXL freelist.
 *
 * On success: writes slot ID into meta[token].cxl_slot, updates flags.
 * On failure (CXL full): upgrades ACTION_DEMOTE → ACTION_EVICT.
 *
 * The freelist is a simple stack:
 *   d_freelist[0..capacity-1] = available slot IDs
 *   d_freelist_top = index of next available entry (decrements on pop)
 *
 * Pop operation:
 *   old_top = atomicSub(d_freelist_top, 1) - 1
 *   if old_top < 0: CXL full → revert
 *   slot = d_freelist[old_top]
 */
__global__ void mm_kernel_alloc_cxl_slots(
    TokenMeta*           __restrict__ d_meta,
    const uint32_t*      __restrict__ d_demote_list,
    uint32_t             n_demote,
    CXLStorageLayout     cxl,
    EvictionAction*      __restrict__ d_actions
) {
    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= n_demote) return;

    uint32_t token_idx = d_demote_list[idx];

    // Atomic pop from freelist stack
    // atomicSub returns OLD value, so new top = old - 1
    int old_top = (int)atomicSub(cxl.d_freelist_top, 1u);
    int new_top = old_top - 1;

    if (new_top < 0) {
        // CXL full — revert the decrement and mark as evict
        atomicAdd(cxl.d_freelist_top, 1u);
        d_actions[token_idx] = ACTION_EVICT;
        return;
    }

    // Pop the slot ID
    uint32_t slot = cxl.d_freelist[new_top];

    // Update token metadata
    d_meta[token_idx].cxl_slot = slot;
    d_meta[token_idx].tier_flags = (d_meta[token_idx].tier_flags & ~MM_FLAG_IN_TIER0)
                                  | MM_FLAG_IN_CXL
                                  | MM_FLAG_TQ_COMPRESSED;
}

// ============================================================================
// Kernel: Free CXL slots for evicted tokens
// ============================================================================

/**
 * Push freed slot IDs back onto the freelist stack.
 * Also updates per-modality eviction counters.
 */
__global__ void mm_kernel_free_cxl_slots(
    TokenMeta*           __restrict__ d_meta,
    const uint32_t*      __restrict__ d_evict_list,
    uint32_t             n_evict,
    CXLStorageLayout     cxl,
    ModalityStats*       __restrict__ d_modality_stats
) {
    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= n_evict) return;

    uint32_t token_idx = d_evict_list[idx];
    TokenMeta* meta = &d_meta[token_idx];

    // If this token was in CXL, free its slot
    if (meta->tier_flags & MM_FLAG_IN_CXL) {
        uint32_t slot = meta->cxl_slot;
        if (slot != MM_CXL_SLOT_INVALID) {
            // Push slot back onto freelist
            uint32_t push_pos = atomicAdd(cxl.d_freelist_top, 1u);
            if (push_pos < cxl.capacity) {
                cxl.d_freelist[push_pos] = slot;
            }
        }
    }

    // Update modality stats
    if (d_modality_stats) {
        ModalityGroup mod = MM_UNPACK_MODALITY(meta->type_flags);
        atomicAdd(&d_modality_stats->evicted_count[mod], 1u);
    }

    // Clear token metadata
    meta->tier_flags = 0;
    meta->cxl_slot = MM_CXL_SLOT_INVALID;
}

// ============================================================================
// Kernel: Fused Alloc + Free + Finalize (TRUE Kernel 3)
//
// Replaces separate mm_kernel_alloc_cxl_slots + mm_kernel_free_cxl_slots
// as a single launch. Reads d_demote_count / d_evict_count from device
// memory (written by kernel 2), so NO host-side sync or readback is needed
// between kernel 2 and kernel 3.
//
// Thread mapping:
//   threads [0, n_demote)          → alloc CXL slot + update tier flags + stats
//   threads [n_demote, n_demote+n_evict) → free CXL slot + clear meta + stats
//   threads beyond                  → early exit
//
// Grid: (MM_MAX_VICTIMS * 2 + 127) / 128  (conservative, most blocks exit early)
// Block: 128
//
// CUDA graph safe: no host interaction, fixed grid dims.
// ============================================================================

__global__ void mm_kernel_fused_alloc_free_finalize(
    TokenMeta*           __restrict__ d_meta,
    const uint32_t*      __restrict__ d_demote_list,
    const uint32_t*      __restrict__ d_demote_count,   // device-side (from kernel 2)
    const uint32_t*      __restrict__ d_evict_list,
    const uint32_t*      __restrict__ d_evict_count,    // device-side (from kernel 2)
    CXLStorageLayout     cxl,
    EvictionAction*      __restrict__ d_actions,         // may upgrade DEMOTE→EVICT
    ModalityStats*       __restrict__ d_modality_stats
) {
    // Read counts from device memory (visible because kernel 2 completed
    // on the same stream before this kernel launched — CUDA ordering guarantee)
    uint32_t n_demote = *d_demote_count;
    uint32_t n_evict  = *d_evict_count;
    n_demote = min(n_demote, (uint32_t)MM_MAX_VICTIMS);
    n_evict  = min(n_evict,  (uint32_t)MM_MAX_VICTIMS);
    uint32_t total = n_demote + n_evict;

    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= total) return;

    if (idx < n_demote) {
        // ---- ALLOC PATH: pop CXL slot for demoted token ----
        uint32_t token_idx = d_demote_list[idx];

        int old_top = (int)atomicSub(cxl.d_freelist_top, 1u);
        int new_top = old_top - 1;

        if (new_top < 0) {
            // CXL full — revert decrement, upgrade to EVICT
            atomicAdd(cxl.d_freelist_top, 1u);
            d_actions[token_idx] = ACTION_EVICT;

            // Count as eviction in modality stats
            if (d_modality_stats) {
                ModalityGroup mod = MM_UNPACK_MODALITY(d_meta[token_idx].type_flags);
                atomicAdd(&d_modality_stats->evicted_count[mod], 1u);
            }

            // Clear tier flags (no longer in Tier0, not in CXL either — evicted)
            d_meta[token_idx].tier_flags &= ~MM_FLAG_IN_TIER0;
            return;
        }

        // Pop slot from freelist
        uint32_t slot = cxl.d_freelist[new_top];

        // Update token metadata: Tier0 → CXL
        d_meta[token_idx].cxl_slot = slot;
        d_meta[token_idx].tier_flags = (d_meta[token_idx].tier_flags & ~MM_FLAG_IN_TIER0)
                                      | MM_FLAG_IN_CXL;
        // Note: MM_FLAG_TQ_COMPRESSED is set AFTER the compress kernel actually
        // writes data. Setting it here before compression is a lie. Leave it unset
        // until compress runs. The alloc only reserves the slot.

        // Update CXL modality stats
        if (d_modality_stats) {
            ModalityGroup mod = MM_UNPACK_MODALITY(d_meta[token_idx].type_flags);
            atomicAdd(&d_modality_stats->cxl_count[mod], 1u);
        }
    } else {
        // ---- FREE PATH: release CXL slot for evicted token ----
        uint32_t evict_idx = idx - n_demote;
        uint32_t token_idx = d_evict_list[evict_idx];
        TokenMeta* meta = &d_meta[token_idx];

        // Free CXL slot if token was in CXL tier
        if (meta->tier_flags & MM_FLAG_IN_CXL) {
            uint32_t slot = meta->cxl_slot;
            if (slot != MM_CXL_SLOT_INVALID) {
                uint32_t push_pos = atomicAdd(cxl.d_freelist_top, 1u);
                if (push_pos < cxl.capacity) {
                    cxl.d_freelist[push_pos] = slot;
                }
            }
        }

        // Update modality eviction stats
        if (d_modality_stats) {
            ModalityGroup mod = MM_UNPACK_MODALITY(meta->type_flags);
            atomicAdd(&d_modality_stats->evicted_count[mod], 1u);
        }

        // Clear token metadata
        meta->tier_flags = 0;
        meta->cxl_slot = MM_CXL_SLOT_INVALID;
    }
}

// ============================================================================
// Host helper: Initialize CXL storage layout
// ============================================================================

/**
 * Allocate and initialize CXL storage on device.
 * Called once at controller construction.
 */
void mm_init_cxl_storage(
    CXLStorageLayout& cxl,
    uint32_t capacity,
    uint32_t total_angles,    // head_dim - 1
    uint32_t qjl_words        // ceil(proj_dim / 32)
) {
    cxl.capacity = capacity;
    cxl.total_angles = total_angles;
    cxl.qjl_words = qjl_words;

    // Allocate storage arrays
    cudaMalloc(&cxl.d_indices,    (size_t)capacity * total_angles * sizeof(uint8_t));
    cudaMalloc(&cxl.d_radii,      (size_t)capacity * sizeof(float));
    cudaMalloc(&cxl.d_qjl_bits,   (size_t)capacity * qjl_words * sizeof(uint32_t));
    cudaMalloc(&cxl.d_qjl_scales, (size_t)capacity * sizeof(float));
    cudaMalloc(&cxl.d_freelist,    (size_t)capacity * sizeof(uint32_t));
    cudaMalloc(&cxl.d_freelist_top, sizeof(uint32_t));

    // Initialize freelist: slot[i] = i, top = capacity
    uint32_t* h_freelist = new uint32_t[capacity];
    for (uint32_t i = 0; i < capacity; i++) {
        h_freelist[i] = i;
    }
    cudaMemcpy(cxl.d_freelist, h_freelist, capacity * sizeof(uint32_t),
               cudaMemcpyHostToDevice);
    cudaMemcpy(cxl.d_freelist_top, &capacity, sizeof(uint32_t),
               cudaMemcpyHostToDevice);
    delete[] h_freelist;

    // Zero out storage
    cudaMemset(cxl.d_indices, 0, (size_t)capacity * total_angles);
    cudaMemset(cxl.d_radii, 0, (size_t)capacity * sizeof(float));
    cudaMemset(cxl.d_qjl_bits, 0, (size_t)capacity * qjl_words * sizeof(uint32_t));
    cudaMemset(cxl.d_qjl_scales, 0, (size_t)capacity * sizeof(float));
}

void mm_free_cxl_storage(CXLStorageLayout& cxl) {
    cudaFree(cxl.d_indices);
    cudaFree(cxl.d_radii);
    cudaFree(cxl.d_qjl_bits);
    cudaFree(cxl.d_qjl_scales);
    cudaFree(cxl.d_freelist);
    cudaFree(cxl.d_freelist_top);
    cxl = {};
}
