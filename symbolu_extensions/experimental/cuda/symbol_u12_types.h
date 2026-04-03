/*
 * SymbolU12 CUDA Kernel - Type Definitions
 * =========================================
 *
 * Data contract between Python and GPU for the Sattvic State Evolution.
 * Ensures the memory layout is identical across CPU and CUDA paths.
 *
 * Reference: docs/GOOGLE_ARCHITECTURE_PROPOSALS.md Section 30
 */

#ifndef SYMBOL_U12_TYPES_H
#define SYMBOL_U12_TYPES_H

// =============================================================================
// GUNA WEIGHTS CONFIGURATION
// =============================================================================

struct GunaWeights {
    float w_S;                    // Sattva emphasis (default: 0.9)
    float w_R;                    // Rajas emphasis (default: 1.05)
    float w_T;                    // Tamas emphasis (default: 0.6)
    float lambda;                 // Persistence pull strength (default: 0.05)
    float integrity_threshold;    // Kill-switch tau (default: 0.30)
};

// =============================================================================
// INTEGRITY BITMASK FLAGS
// =============================================================================
// These flags allow the Sattvic Seal to report specific failure modes

#define INTEGRITY_OK            0x00  // All checks passed
#define COHERENCE_FAILURE       0x01  // C_s < 0.3 (Alignment lost)
#define MOTION_OVERDRIVE        0x02  // M > 2.5 (Hallucination/Chaos)
#define TRACE_COLLAPSE          0x04  // Tr(R) < threshold (Logic non-unitary)
#define ENTROPY_SPIKE           0x08  // H > 0.95 (Information disorder)

// =============================================================================
// MANIFOLD DIMENSIONS
// =============================================================================

#define MANIFOLD_DIM            124   // [Phoneme(44), Topic(64), Onto(12), Dyn(4)]
#define R_BLOCK_SIZE            9     // 3x3 rotation matrix flattened

// =============================================================================
// KERNEL CONFIGURATION
// =============================================================================

#define THREADS_PER_BLOCK       128   // 4 warps for 124 dimensions
#define WARP_SIZE               32

// Motion threshold for hallucination detection
#define MOTION_THRESHOLD        2.5f

// Coherence threshold for alignment failure
#define COHERENCE_THRESHOLD     0.3f

// Entropy threshold for information disorder
#define ENTROPY_THRESHOLD       0.95f

#endif // SYMBOL_U12_TYPES_H
