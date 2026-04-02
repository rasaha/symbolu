/**
 * mm_importance_lut.cu — Multimodal token importance LUT (device constant)
 *
 * Stored in __constant__ memory for broadcast-efficient reads.
 * All threads in a warp reading the same LUT entry = single memory transaction.
 */

#include "multimodal_inference.cuh"

// ============================================================================
// Device Constant: Multimodal Token Importance LUT
// ============================================================================

/**
 * Importance values [0, 1] indexed by MultimodalTokenType.
 *
 * Higher = more important = harder to evict.
 * Validated against vLLM Python simulator values.
 */
__constant__ float c_mm_importance[MM_IMPORTANCE_LUT_SIZE] = {
    // Text tokens (0-7)
    1.00f,  // MM_TOKEN_BOS
    0.90f,  // MM_TOKEN_ENTITY
    0.85f,  // MM_TOKEN_NUMBER
    0.80f,  // MM_TOKEN_CODE
    0.75f,  // MM_TOKEN_INSTRUCTION
    0.50f,  // MM_TOKEN_EOS
    0.40f,  // MM_TOKEN_REGULAR
    0.20f,  // MM_TOKEN_PUNCTUATION

    // Image tokens (8-11)
    0.95f,  // MM_TOKEN_IMAGE_CLS       — anchors image representation
    0.35f,  // MM_TOKEN_IMAGE_PATCH     — redundant, compresses well
    0.85f,  // MM_TOKEN_IMAGE_ROI       — region of interest
    0.15f,  // MM_TOKEN_IMAGE_BORDER    — border/padding, least important

    // Video tokens (12-15)
    0.80f,  // MM_TOKEN_VIDEO_KEYFRAME  — I-frame, scene information
    0.45f,  // MM_TOKEN_VIDEO_PFRAME    — predicted, partially redundant
    0.25f,  // MM_TOKEN_VIDEO_BFRAME    — bidirectional, most redundant
    0.90f,  // MM_TOKEN_VIDEO_SCENE     — scene change boundary

    // Audio tokens (16-18)
    0.70f,  // MM_TOKEN_AUDIO_ONSET     — speech/sound onset
    0.55f,  // MM_TOKEN_AUDIO_SPEECH    — mid-speech
    0.10f,  // MM_TOKEN_AUDIO_SILENCE   — silence, safe to evict

    // Unknown (19)
    0.40f,  // MM_TOKEN_UNKNOWN         — default = regular

    // Padding (20-31) — reserved for future token types
    0.0f, 0.0f, 0.0f, 0.0f,
    0.0f, 0.0f, 0.0f, 0.0f,
    0.0f, 0.0f, 0.0f, 0.0f,
};

/**
 * Anchor token set: token types that should get a modality-anchor
 * bonus in the scoring function (cross-modal bridge tokens).
 *
 * Stored as a bitmask: bit N = 1 means token type N is an anchor.
 */
__constant__ uint32_t c_mm_anchor_mask =
    (1u << MM_TOKEN_BOS)           |
    (1u << MM_TOKEN_ENTITY)        |
    (1u << MM_TOKEN_IMAGE_CLS)     |
    (1u << MM_TOKEN_IMAGE_ROI)     |
    (1u << MM_TOKEN_VIDEO_KEYFRAME)|
    (1u << MM_TOKEN_VIDEO_SCENE)   |
    (1u << MM_TOKEN_AUDIO_ONSET)   |
    (1u << MM_TOKEN_INSTRUCTION);
