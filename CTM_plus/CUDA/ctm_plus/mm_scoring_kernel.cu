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
 * 8-signal scoring function. All arithmetic is FP32 in registers.
 *
 * Uses __expf / __logf fast-math intrinsics (~2 ULP error, ~30% faster
 * than IEEE-compliant expf/log1pf). Score differences at eviction
 * thresholds are O(0.01), so 1e-7 error is negligible.
 *
 * Signals (weights sum to 1.0):
 *   1. Recency      (0.20): exp(-0.693 * age / 100)
 *   2. Frequency    (0.15): log(1 + freq_norm * 10) / ln(11)
 *   3. Attention    (0.25): sigmoid(attn_ratio - 5)
 *   4. Token imp.   (0.12): LUT[token_type]
 *   5. Position     (0.08): sink=1.0, recent_window=linear, else=0.3
 *   6. Comp quality (0.05): (1 - cosine_sim) * weight  (quality-aware)
 *   7. Mod anchor   (0.10): +bonus if token is a cross-modal anchor
 *   8. Reuse trend  (0.05): sigmoid(trend) — predictive: rising attention → keep
 *
 * Returns score in [0, ~1.2].  Higher = more important = keep.
 */
__device__ __forceinline__ float mm_compute_score(
    const TokenMeta& meta,
    const ScoringConfig& cfg
) {
    float score = 0.0f;

    // Unpack token type from bitfield
    uint8_t tt = MM_UNPACK_TOKEN_TYPE(meta.type_flags);

    // ---- Signal 1: Recency ----
    uint32_t age = cfg.current_step - meta.last_access_step;
    float recency = __expf(-0.693f * (float)age / 100.0f);
    score += cfg.w_recency * recency;

    // ---- Signal 2: Frequency (weight reduced 0.20→0.15) ----
    // 0.41787344f = 1/ln(11), precomputed to avoid runtime log1pf(10)
    float freq_norm = fminf((float)meta.access_count * 0.001f, 1.0f);
    float frequency = __logf(1.0f + freq_norm * 10.0f) * 0.41787344f;
    score += cfg.w_frequency * frequency;

    // ---- Signal 3: Attention strength ----
    float avg_attn = (meta.attention_count > 0)
        ? (meta.attention_sum / (float)meta.attention_count)
        : 0.0f;
    float strength = avg_attn / 0.001f;
    float attention = 1.0f / (1.0f + __expf(-0.5f * (strength - 5.0f)));
    score += cfg.w_attention * attention;

    // ---- Signal 4: Token importance ----
    float importance = (tt < MM_IMPORTANCE_LUT_SIZE) ? c_mm_importance[tt] : 0.4f;
    score += cfg.w_token_importance * importance;

    // ---- Signal 5: Position ----
    float pos_score = 0.3f;
    if (meta.position < cfg.attention_sink_tokens) {
        pos_score = 1.0f;
    } else if (cfg.seq_len > 0 && meta.position > cfg.seq_len - cfg.recent_window_size) {
        float recency_bonus = 1.0f - (float)(cfg.seq_len - meta.position)
                                   / (float)cfg.recent_window_size;
        pos_score = fmaxf(pos_score, recency_bonus);
    }
    score += cfg.w_position * pos_score;

    // ---- Signal 6: Compression quality (quality-aware mode) ----
    if (cfg.w_compression_quality > 0.0f && (meta.tier_flags & MM_FLAG_TQ_COMPRESSED)) {
        float quality_penalty = 1.0f - meta.cosine_sim;
        score += cfg.w_compression_quality * quality_penalty;
    }

    // ---- Signal 7: Modality anchor bonus (weight raised 0.05→0.10) ----
    // Branchless bit test on anchor mask
    uint32_t is_anchor = (c_mm_anchor_mask >> tt) & 1u;
    score += cfg.w_modality_anchor * (float)is_anchor;

    // ---- Signal 8: Reuse trend (predictive, NEW) ----
    // Stored as int16_t scaled by 1000 (range: -32.0 to +32.0).
    // Positive trend = attention is increasing → token will be needed → keep.
    // sigmoid maps to [0, 1]; centered at 0 (no trend).
    if (cfg.w_reuse_trend > 0.0f) {
        float trend_val = (float)meta.reuse_trend / 1000.0f;
        float trend_sig = 1.0f / (1.0f + __expf(-2.0f * trend_val));
        score += cfg.w_reuse_trend * trend_sig;
    }

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
    if (!(meta.tier_flags & MM_FLAG_IN_TIER0)) {
        d_actions[idx] = ACTION_KEEP;  // Not in Tier0, no action
        if (d_scores) d_scores[idx] = 0.0f;
        return;
    }

    // Pinned tokens are always kept (pinned bit in type_flags)
    if (MM_UNPACK_PINNED(meta.type_flags)) {
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
// Kernel: Collect demotions (stream compaction via atomic) — LEGACY
// Kept for non-fused path. Prefer mm_kernel_fused_score_collect.
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
// Kernel: FUSED Score + Decide + Collect (single launch, CUDA graph ready)
//
// Replaces: mm_kernel_score_and_decide + mm_kernel_collect_demotions
//
// Warp-level ballot compaction:
//   1. Each thread scores its token and decides action
//   2. Warp ballot identifies DEMOTE/EVICT threads
//   3. Warp-level prefix sum assigns contiguous output positions
//   4. First thread in each warp does a single atomicAdd on global counter
//   5. Warp members write to d_demote_list / d_evict_list at computed offsets
//
// This eliminates the intermediate d_actions read in a second kernel and
// reduces global atomic pressure from O(demotions) to O(demotions/32).
// ============================================================================

__global__ void mm_kernel_fused_score_collect(
    const TokenMeta*     __restrict__ d_meta,
    const ScoringConfig  config,
    uint32_t             n_tokens,
    EvictionAction*      __restrict__ d_actions,
    float*               __restrict__ d_scores,
    uint32_t*            __restrict__ d_demote_list,
    uint32_t*            __restrict__ d_demote_count,
    uint32_t*            __restrict__ d_evict_list,
    uint32_t*            __restrict__ d_evict_count
) {
    uint32_t idx = blockIdx.x * blockDim.x + threadIdx.x;

    // ---- Phase 1: Score + Decide (same as mm_kernel_score_and_decide) ----
    EvictionAction action = ACTION_KEEP;
    float score = 0.0f;

    if (idx < n_tokens) {
        TokenMeta meta = d_meta[idx];  // 32B coalesced read

        if (!(meta.tier_flags & MM_FLAG_IN_TIER0)) {
            action = ACTION_KEEP;
        } else if (MM_UNPACK_PINNED(meta.type_flags)) {
            action = ACTION_KEEP;
            score = 999.0f;
        } else {
            score = mm_compute_score(meta, config);
            if (score < config.eviction_threshold) {
                action = ACTION_EVICT;
            } else if (score < config.demotion_threshold) {
                action = ACTION_DEMOTE;
            }
        }

        d_actions[idx] = action;
        if (d_scores) d_scores[idx] = score;
    }

    // ---- Phase 2: Warp-level ballot compaction ----
    uint32_t lane = threadIdx.x & 31;
    uint32_t demote_ballot = __ballot_sync(0xFFFFFFFF, action == ACTION_DEMOTE);
    uint32_t evict_ballot  = __ballot_sync(0xFFFFFFFF, action == ACTION_EVICT);

    // Count demotions/evictions in this warp
    uint32_t warp_demote_count = __popc(demote_ballot);
    uint32_t warp_evict_count  = __popc(evict_ballot);

    // Lane 0 reserves global output slots for the whole warp
    __shared__ uint32_t s_demote_base[MM_SCORE_BLOCK_SIZE / 32];
    __shared__ uint32_t s_evict_base[MM_SCORE_BLOCK_SIZE / 32];
    uint32_t warp_id = threadIdx.x >> 5;

    if (lane == 0) {
        s_demote_base[warp_id] = (warp_demote_count > 0)
            ? atomicAdd(d_demote_count, warp_demote_count) : 0;
        s_evict_base[warp_id]  = (warp_evict_count > 0)
            ? atomicAdd(d_evict_count, warp_evict_count) : 0;
    }
    __syncwarp();

    // Each DEMOTE thread computes its position via prefix popcount
    if (action == ACTION_DEMOTE) {
        uint32_t prefix = __popc(demote_ballot & ((1u << lane) - 1));
        uint32_t global_pos = s_demote_base[warp_id] + prefix;
        if (global_pos < MM_MAX_VICTIMS) {
            d_demote_list[global_pos] = idx;
        }
    }

    // Each EVICT thread computes its position
    if (action == ACTION_EVICT) {
        uint32_t prefix = __popc(evict_ballot & ((1u << lane) - 1));
        uint32_t global_pos = s_evict_base[warp_id] + prefix;
        if (global_pos < MM_MAX_VICTIMS) {
            d_evict_list[global_pos] = idx;
        }
    }
}

// ============================================================================
// Kernel: Update token metadata on access + reuse trend
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
    float old_avg = (meta->attention_count > 0)
        ? (meta->attention_sum / (float)meta->attention_count)
        : 0.0f;

    meta->attention_sum += w;
    meta->attention_count++;

    // ---- Reuse trend update (predictive signal) ----
    // Compute new average and store delta as int16 * 1000
    float new_avg = meta->attention_sum / (float)meta->attention_count;
    float delta = new_avg - old_avg;
    // Clamp to int16 range (scaled by 1000)
    int trend = (int)(delta * 1000.0f);
    trend = max(-32000, min(32000, trend));
    meta->reuse_trend = (int16_t)trend;
}
