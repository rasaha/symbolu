/*
 * SymbolU12 CUDA Extension - Python Binding
 * ==========================================
 *
 * Dispatcher pattern for CPU/GPU parity.
 * Auto-routes to CUDA kernel or C++ fallback based on tensor device.
 *
 * Reference: docs/GOOGLE_ARCHITECTURE_PROPOSALS.md Section 30.21
 */

#include <torch/extension.h>
#include <vector>
#include <stdexcept>
#include "symbol_u12_types.h"

// Forward declarations of CUDA and CPU implementations
void launchCudaEvolution(
    torch::Tensor S_t,
    torch::Tensor S_prev,
    torch::Tensor S_0,
    torch::Tensor R_block,
    torch::Tensor delta,
    GunaWeights weights,
    torch::Tensor output_G,
    torch::Tensor integrity_flags
);

void launchCpuFallback(
    torch::Tensor S_t,
    torch::Tensor S_prev,
    torch::Tensor S_0,
    torch::Tensor R_block,
    torch::Tensor delta,
    GunaWeights weights,
    torch::Tensor output_G,
    torch::Tensor integrity_flags
);

// =============================================================================
// INPUT VALIDATION
// =============================================================================

void validateInputs(
    torch::Tensor S_t,
    torch::Tensor S_prev,
    torch::Tensor S_0,
    torch::Tensor R_block,
    torch::Tensor delta
) {
    // Check dimensions
    TORCH_CHECK(S_t.dim() == 2, "S_t must be 2D [batch, dim]");
    TORCH_CHECK(S_prev.dim() == 2, "S_prev must be 2D [batch, dim]");
    TORCH_CHECK(S_0.dim() == 2, "S_0 must be 2D [batch, dim]");
    TORCH_CHECK(R_block.dim() == 2, "R_block must be 2D [batch, 9]");
    TORCH_CHECK(delta.dim() == 2, "delta must be 2D [batch, dim]");

    int batch_size = S_t.size(0);
    int dim = S_t.size(1);

    // Check batch consistency
    TORCH_CHECK(S_prev.size(0) == batch_size, "S_prev batch mismatch");
    TORCH_CHECK(S_0.size(0) == batch_size, "S_0 batch mismatch");
    TORCH_CHECK(R_block.size(0) == batch_size, "R_block batch mismatch");
    TORCH_CHECK(delta.size(0) == batch_size, "delta batch mismatch");

    // Check dimension consistency
    TORCH_CHECK(S_prev.size(1) == dim, "S_prev dim mismatch");
    TORCH_CHECK(S_0.size(1) == dim, "S_0 dim mismatch");
    TORCH_CHECK(delta.size(1) == dim, "delta dim mismatch");
    TORCH_CHECK(R_block.size(1) == R_BLOCK_SIZE, "R_block must have 9 elements");

    // Check dtype
    TORCH_CHECK(S_t.dtype() == torch::kFloat32, "S_t must be float32");
    TORCH_CHECK(S_prev.dtype() == torch::kFloat32, "S_prev must be float32");
    TORCH_CHECK(S_0.dtype() == torch::kFloat32, "S_0 must be float32");
    TORCH_CHECK(R_block.dtype() == torch::kFloat32, "R_block must be float32");
    TORCH_CHECK(delta.dtype() == torch::kFloat32, "delta must be float32");

    // Check contiguity
    TORCH_CHECK(S_t.is_contiguous(), "S_t must be contiguous");
    TORCH_CHECK(S_prev.is_contiguous(), "S_prev must be contiguous");
    TORCH_CHECK(S_0.is_contiguous(), "S_0 must be contiguous");
    TORCH_CHECK(R_block.is_contiguous(), "R_block must be contiguous");
    TORCH_CHECK(delta.is_contiguous(), "delta must be contiguous");

    // Check device consistency
    auto device = S_t.device();
    TORCH_CHECK(S_prev.device() == device, "S_prev device mismatch");
    TORCH_CHECK(S_0.device() == device, "S_0 device mismatch");
    TORCH_CHECK(R_block.device() == device, "R_block device mismatch");
    TORCH_CHECK(delta.device() == device, "delta device mismatch");
}

// =============================================================================
// MAIN DISPATCHER FUNCTION
// =============================================================================

/**
 * step_evolution - Unified entry point for Sattvic State Evolution.
 *
 * Automatically dispatches to CUDA kernel or CPU fallback based on tensor device.
 *
 * Args:
 *   S_t:      [B, 124] Current state tensor (modified in-place)
 *   S_prev:   [B, 124] Ghost buffer for motion tracking (modified in-place)
 *   S_0:      [B, 124] Sattvic seed anchor (read-only)
 *   R_block:  [B, 9] Flattened R-matrix for integrity check (read-only)
 *   delta:    [B, 124] Model's predicted state change (read-only)
 *   w_S:      Sattva weight
 *   w_R:      Rajas weight
 *   w_T:      Tamas weight
 *   lambda:   Persistence pull strength
 *   threshold: Integrity threshold for kill-switch
 *
 * Returns:
 *   tuple of (output_G [B], integrity_flags [B])
 */
std::vector<torch::Tensor> step_evolution(
    torch::Tensor S_t,
    torch::Tensor S_prev,
    torch::Tensor S_0,
    torch::Tensor R_block,
    torch::Tensor delta,
    float w_S,
    float w_R,
    float w_T,
    float lambda,
    float threshold
) {
    // Validate inputs
    validateInputs(S_t, S_prev, S_0, R_block, delta);

    int batch_size = S_t.size(0);
    auto device = S_t.device();

    // Build weights struct
    GunaWeights weights = {w_S, w_R, w_T, lambda, threshold};

    // Allocate output tensors
    auto output_G = torch::zeros({batch_size}, torch::dtype(torch::kFloat32).device(device));
    auto integrity_flags = torch::zeros({batch_size}, torch::dtype(torch::kInt32).device(device));

    // Dispatch based on device
    if (S_t.is_cuda()) {
        launchCudaEvolution(
            S_t, S_prev, S_0, R_block, delta,
            weights, output_G, integrity_flags
        );
    } else {
        launchCpuFallback(
            S_t, S_prev, S_0, R_block, delta,
            weights, output_G, integrity_flags
        );
    }

    return {output_G, integrity_flags};
}

// =============================================================================
// SINGLE-SAMPLE CONVENIENCE WRAPPER
// =============================================================================

/**
 * step_evolution_single - Convenience wrapper for single-sample processing.
 *
 * Automatically adds batch dimension if tensors are 1D.
 */
std::vector<torch::Tensor> step_evolution_single(
    torch::Tensor S_t,
    torch::Tensor S_prev,
    torch::Tensor S_0,
    torch::Tensor R_block,
    torch::Tensor delta,
    float w_S,
    float w_R,
    float w_T,
    float lambda,
    float threshold
) {
    bool was_1d = (S_t.dim() == 1);

    if (was_1d) {
        S_t = S_t.unsqueeze(0);
        S_prev = S_prev.unsqueeze(0);
        S_0 = S_0.unsqueeze(0);
        R_block = R_block.unsqueeze(0);
        delta = delta.unsqueeze(0);
    }

    auto results = step_evolution(
        S_t, S_prev, S_0, R_block, delta,
        w_S, w_R, w_T, lambda, threshold
    );

    if (was_1d) {
        results[0] = results[0].squeeze(0);
        results[1] = results[1].squeeze(0);
    }

    return results;
}

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

/**
 * decode_integrity_flags - Convert bitmask to human-readable status.
 */
std::string decode_integrity_flags(int flags) {
    if (flags == INTEGRITY_OK) {
        return "OK";
    }

    std::string result;
    if (flags & COHERENCE_FAILURE) {
        result += "COHERENCE_FAILURE ";
    }
    if (flags & MOTION_OVERDRIVE) {
        result += "MOTION_OVERDRIVE ";
    }
    if (flags & TRACE_COLLAPSE) {
        result += "TRACE_COLLAPSE ";
    }
    if (flags & ENTROPY_SPIKE) {
        result += "ENTROPY_SPIKE ";
    }

    return result;
}

/**
 * get_version - Return extension version string.
 */
std::string get_version() {
    return "1.0.0";
}

/**
 * is_cuda_available - Check if CUDA is available.
 */
bool is_cuda_available() {
#ifdef __CUDACC__
    return torch::cuda::is_available();
#else
    return false;
#endif
}

// =============================================================================
// PYBIND11 MODULE DEFINITION
// =============================================================================

PYBIND11_MODULE(TORCH_EXTENSION_NAME, m) {
    m.doc() = "SymbolU12 CUDA Extension - Sattvic State Evolution";

    // Main functions
    m.def("step_evolution", &step_evolution,
          "Batched Sattvic State Evolution (auto-dispatches to CUDA or CPU)",
          py::arg("S_t"),
          py::arg("S_prev"),
          py::arg("S_0"),
          py::arg("R_block"),
          py::arg("delta"),
          py::arg("w_S") = 0.9f,
          py::arg("w_R") = 1.05f,
          py::arg("w_T") = 0.6f,
          py::arg("lambda") = 0.05f,
          py::arg("threshold") = 0.3f);

    m.def("step_evolution_single", &step_evolution_single,
          "Single-sample Sattvic State Evolution with auto-batching",
          py::arg("S_t"),
          py::arg("S_prev"),
          py::arg("S_0"),
          py::arg("R_block"),
          py::arg("delta"),
          py::arg("w_S") = 0.9f,
          py::arg("w_R") = 1.05f,
          py::arg("w_T") = 0.6f,
          py::arg("lambda") = 0.05f,
          py::arg("threshold") = 0.3f);

    // Utility functions
    m.def("decode_integrity_flags", &decode_integrity_flags,
          "Decode integrity bitmask to human-readable string");

    m.def("get_version", &get_version,
          "Get extension version");

    m.def("is_cuda_available", &is_cuda_available,
          "Check if CUDA is available");

    // Export constants
    m.attr("INTEGRITY_OK") = py::int_(INTEGRITY_OK);
    m.attr("COHERENCE_FAILURE") = py::int_(COHERENCE_FAILURE);
    m.attr("MOTION_OVERDRIVE") = py::int_(MOTION_OVERDRIVE);
    m.attr("TRACE_COLLAPSE") = py::int_(TRACE_COLLAPSE);
    m.attr("ENTROPY_SPIKE") = py::int_(ENTROPY_SPIKE);
    m.attr("MANIFOLD_DIM") = py::int_(MANIFOLD_DIM);
}
