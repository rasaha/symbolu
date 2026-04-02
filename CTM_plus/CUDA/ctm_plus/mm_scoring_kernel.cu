/**
 * mm_scoring_kernel.cu — Fused scoring + eviction decision kernel
 *
 * Single kernel launch per decode step. For each Tier0 token, computes
 * a 7-signal importance score and writes an eviction decision.
 *
 * Performance target: ≤ 3 µs for 4096 tokens on A100.
 *
 * Memory access pattern:
 *   READ:  d_meta[]  — 32B per token, coalesced (consecutive TokenMeta structs)
 *   WRITE: d_actions[] — 1B per token
 *   WRITE: d_scores[]  — 4B per token (optional, NULL to skip)
 *   READ:  c_mm_importance[] — constant memory, broadcast to entire warp
 *   READ:  c_mm_anchor_mask  — constant memory, single uint32
 *
 * Branch analysis:
 *   - Position check (sink vs recent vs middle): warp-uniform for sequential tokens
 *   - Token type lookup: no branch, just LUT index
 *   - Anchor mask check: branchless bit test
 *   - Threshold comparison: unavoidable but lightweight
 */

#include "multimodal_inference.cuh"
#include <math_constants.h>

// External LUT declarations (defined in mm_importance_lut.cu)
extern __constant__ float    c_mm_importance[MM_IMPORTANCE_LUT_SIZE];
extern __constant__ uint32_t c_mm_anchor_mask;

// ============================================================================
// Device helper: compute per-token importance score
// ============================================================================

/**
 * 7-signal scoring function. All arithmetic is FP32 in registers.
 *
 * Signals:
 *   1. Recency:              exp(-0.693 * age / 100)
 *   2. Frequency:            log1p(freq_norm * 10) / log1p(10)
 *   3. Attention strength:   sigmoid(attn_ratio - 5)
 *   4. Token importance:     LUT[token_type]
 *   5. Position:             sink=1.0, recent_window=linear, else=0.3
 *   6. Compression quality:  (1 - cosine_sim) * weight  (quality-aware)
 *   7. Modality anchor:      +bonus if token is a cross-modal anchor
 *
 * Returns score in [0, ~1.2].  Higher = more important = keep.
 */
__device__ __forceinline__ float mm_compute_score(
    const TokenMeta& meta,
    const ScoringConfig& cfg
) {
    float score = 0.0f;

    // ---- Signal 1: Recency ----
    // age = current_step - last_access_step
    uint32_t age = cfg.current_step - meta.last_access_step;
    float recency = expf(-0.693f * (float)age / 100.0f);
    score += cfg.w_recency * recency;

    // ---- Signal 2: Frequency ----
    // Normalize access count to [0, 1] via log scale
    float freq_norm = fminf((float)meta.access_count * 0.001f, 1.0f);
    float frequency = log1pf(freq_norm * 10.0f) / log1pf(10.0f);
    score += cfg.w_frequency * frequency;

    // ---- Signal 3: Attention strength ----
    float avg_attn = (meta.attention_count > 0)
        ? (meta.attention_sum / (float)meta.attention_count)
        : 0.0f;
    // Baseline: 1/1000 (uniform attention over 1K tokens)
    float strength = avg_attn / 0.001f;
    // Sigmoid centered at 5× baseline
    float attention = 1.0f / (1.0f + expf(-0.5f * (strength - 5.0f)));
    score += cfg.w_attention * attention;

    // ---- Signal 4: Token importance ----
    uint8_t tt = meta.token_type;
    float importance = (tt < MM_IMPORTANCE_LUT_SIZE) ? c_mm_importance[tt] : 0.4f;
    score += cfg.w_token_importance * importance;

    // ---- Signal 5: Position ----
    float pos_score = 0.3f;
    if (meta.position < cfg.attention_sink_tokens) {
        // Attention sink — always keep
        pos_score = 1.0f;
    } else if (cfg.seq_len > 0 && meta.position > cfg.seq_len - cfg.recent_window_size) {
        // Recent window — linear bonus
        float recency_bonus = 1.0f - (float)(cfg.seq_len - meta.position)
                                   / (float)cfg.recent_window_size;
        pos_score = fmaxf(pos_score, recency_bonus);
    }
    score += cfg.w_position * pos_score;

    // ---- Signal 6: Compression quality (quality-aware mode) ----
    // Tokens that compressed poorly are more valuable to keep in HBM
    // because their CXL representation would be less faithful.
    if (cfg.w_compression_quality > 0.0f && (meta.flags & MM_FLAG_TQ_COMPRESSED)) {
        float quality_penalty = 1.0f - meta.cosine_sim;
        score += cfg.w_compression_quality * quality_penalty;
    }

    // ---- Signal 7: Modality anchor bonus ----
    // Cross-modal anchor tokens (image_cls, video_keyframe, etc.) get
    // a bonus because they bridge modalities — losing them is costly.
    // Branchless: bit test on anchor mask.
    uint32_t is_anchor = (c_mm_anchor_mask >> tt) & 1u;
    score += cfg.w_modality_anchor * (float)is_anchor;

    return score;
}

// ============================================================================
// Kernel: Fused score + decide
// ============================================================================

__global__ void mm_kernel_score_and_decide(
    const TokenMeta*     __restrict__ d_meta,
    const ScoringConfig  config,
    uint32_t             n_tokens,
    EvictionAction*      __restrict__ d_actions,
    float*               __restrict__ d_scores
) {
    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= n_tokens) return;

    TokenMeta meta = d_meta[idx];  // 32B coalesced read

    // Only score Tier0 tokens
    if (!(meta.flags & MM_FLAG_IN_TIER0)) {
        d_actions[idx] = ACTION_KEEP;  // Not in Tier0, no action
        if (d_scores) d_scores[idx] = 0.0f;
        return;
    }

    // Pinned tokens are always kept
    if (meta.flags & MM_FLAG_PINNED) {
        d_actions[idx] = ACTION_KEEP;
        if (d_scores) d_scores[idx] = 999.0f;
        return;
    }

    float score = mm_compute_score(meta, config);

    // Decision based on thresholds
    EvictionAction action;
    if (score < config.eviction_threshold) {
        action = ACTION_EVICT;
    } else if (score < config.demotion_threshold) {
        action = ACTION_DEMOTE;
    } else {
        action = ACTION_KEEP;
    }

    d_actions[idx] = action;
    if (d_scores) d_scores[idx] = score;
}

// ============================================================================
// Kernel: Collect demotions (stream compaction via atomic)
// ============================================================================

__global__ void mm_kernel_collect_demotions(
    const EvictionAction* __restrict__ d_actions,
    uint32_t              n_tokens,
    uint32_t*             __restrict__ d_demote_list,
    uint32_t*             __restrict__ d_demote_count
) {
    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= n_tokens) return;

    if (d_actions[idx] == ACTION_DEMOTE) {
        uint32_t slot = atomicAdd(d_demote_count, 1u);
        if (slot < MM_MAX_VICTIMS) {
            d_demote_list[slot] = idx;
        }
    }
}

// ============================================================================
// Kernel: Update token metadata on access
// ============================================================================

__global__ void mm_kernel_update_on_access(
    TokenMeta*           __restrict__ d_meta,
    const uint32_t*      __restrict__ d_attending_positions,
    const float*         __restrict__ d_attention_weights,
    uint32_t             n_attending,
    uint32_t             current_step
) {
    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= n_attending) return;

    uint32_t pos = d_attending_positions[idx];
    if (pos >= MM_MAX_TOKENS) return;

    TokenMeta* meta = &d_meta[pos];

    // Update access time
    meta->last_access_step = current_step;

    // Saturating increment
    if (meta->access_count < 65535) {
        meta->access_count++;
    }

    // Exponential moving average of attention weight
    float w = d_attention_weights[idx];
    meta->attention_sum += w;
    meta->attention_count++;
}
