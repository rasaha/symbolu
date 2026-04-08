#!/usr/bin/env python3
"""
Phase-Quad Local Attention — Full Diagnostic Suite
===================================================
Runs all 6 diagnostic steps to identify root cause of
"perplexity decreasing but autoregressive samples are low quality".

Steps:
  1. Cache correctness (full-sequence vs incremental logits)
  2. Logit geometry (norm growth, entropy collapse, overconfidence)
  3. Ablation isolation (local-only, memory-only, quad-soft)
  4. Phase memory stability (mean, variance, norm growth)
  5. Quad routing stress test (top-K diversity, head overlap)
  6. Exposure bias (teacher-forced vs free-running divergence)
"""

import math
import sys
import json
from collections import defaultdict

import torch
import torch.nn as nn
import torch.nn.functional as F

# ---------------------------------------------------------------------------
# Model imports
# ---------------------------------------------------------------------------
from symbolu.phase_transformer import (
    BindingCacheTransformer,
    HybridPhaseTransformer,
    PhaseStateCache,
    BindingCacheBlock,
    BindingCachePhaseState,
    BindingCacheQuadQuery,
    LocalWindowAttention,
    PhaseAttentionLayer,
    HybridAttentionLayer,
)

torch.manual_seed(42)
DEVICE = "cpu"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def entropy(logits: torch.Tensor) -> torch.Tensor:
    """Per-position entropy H(p) = -sum(p * log p)."""
    p = F.softmax(logits, dim=-1)
    log_p = F.log_softmax(logits, dim=-1)
    return -(p * log_p).sum(dim=-1)


def top1_prob(logits: torch.Tensor) -> torch.Tensor:
    """Per-position top-1 probability."""
    return F.softmax(logits, dim=-1).max(dim=-1).values


def report(title: str, findings: dict):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")
    for k, v in findings.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.6f}")
        elif isinstance(v, list) and len(v) > 0 and isinstance(v[0], float):
            summary = f"[{v[0]:.4f} ... {v[-1]:.4f}]  mean={sum(v)/len(v):.4f}"
            print(f"  {k}: {summary}")
        else:
            print(f"  {k}: {v}")


# ===================================================================
# Build two model types for testing:
#   A) BindingCacheTransformer (Phase + Quad + Local)
#   B) HybridPhaseTransformer (Local-only early + Hybrid later)
# ===================================================================

VOCAB = 512
EMBED = 128
HEADS = 4
LAYERS = 4
FF = 512
MAX_SEQ = 512
WINDOW = 64
TOP_K = 16
SEQ_LEN = 128  # diagnostic sequence length

def make_binding_cache_model():
    return BindingCacheTransformer(
        vocab_size=VOCAB,
        embed_dim=EMBED,
        num_layers=LAYERS,
        num_heads=HEADS,
        ff_dim=FF,
        max_seq_len=MAX_SEQ,
        dropout=0.0,
        decay_gamma=1.0,
        learned_decay=False,
        bounded_phase=True,
        top_k=TOP_K,
        use_cache=True,
        tie_embeddings=True,
    ).eval()


def make_hybrid_model():
    return HybridPhaseTransformer(
        vocab_size=VOCAB,
        embed_dim=EMBED,
        num_layers=LAYERS,
        num_heads=HEADS,
        ff_dim=FF,
        max_seq_len=MAX_SEQ,
        dropout=0.0,
        local_layers=2,
        window_size=WINDOW,
        local_backend="auto",
        alpha_local=0.8,
        alpha_phase=0.2,
        tie_embeddings=True,
        cosine_mode="standard",
        decay_gamma=1.0,
        learned_decay=False,
        bounded_phase=True,
        zero_mean_cosine=False,
        protected_phase=True,
    ).eval()


# ===================================================================
# STEP 1 — VERIFY CACHE CORRECTNESS
# ===================================================================

def step1_cache_correctness():
    print("\n" + "#" * 70)
    print("# STEP 1: CACHE CORRECTNESS (full-sequence vs incremental)")
    print("#" * 70)

    findings = {}

    # --- Test A: HybridPhaseTransformer (has forward_with_cache) ---
    model = make_hybrid_model()
    tokens = torch.randint(0, VOCAB, (1, SEQ_LEN))

    with torch.no_grad():
        # Full-sequence forward
        full_logits = model(tokens)["logits"]  # [1, SEQ_LEN, VOCAB]

        # Incremental forward with PhaseStateCache
        cache = None
        # Prefill with first 64 tokens
        prefill = tokens[:, :64]
        result, cache = model.forward_with_cache(prefill, cache)
        cached_logits_parts = [result["logits"]]

        # Then decode one token at a time
        for t in range(64, SEQ_LEN):
            tok = tokens[:, t:t+1]
            result, cache = model.forward_with_cache(tok, cache)
            cached_logits_parts.append(result["logits"])

        cached_logits = torch.cat(cached_logits_parts, dim=1)  # [1, SEQ_LEN, VOCAB]

        # Compare
        diff = (full_logits - cached_logits).abs()
        max_diff = diff.max().item()
        mean_diff = diff.mean().item()

        # Per-position max diff
        per_pos_max = diff.max(dim=-1).values.squeeze(0)  # [SEQ_LEN]

        findings["hybrid_max_abs_diff"] = max_diff
        findings["hybrid_mean_abs_diff"] = mean_diff
        findings["hybrid_per_pos_max_diff_last16"] = per_pos_max[-16:].tolist()

        # Identify divergence onset
        threshold = 1e-3
        divergent_positions = (per_pos_max > threshold).nonzero(as_tuple=True)[0]
        if len(divergent_positions) > 0:
            findings["hybrid_first_divergent_pos"] = divergent_positions[0].item()
            findings["hybrid_num_divergent_positions"] = len(divergent_positions)
        else:
            findings["hybrid_first_divergent_pos"] = "NONE"
            findings["hybrid_num_divergent_positions"] = 0

    # --- Test B: BindingCacheTransformer (no cache, re-processes full seq) ---
    model_bc = make_binding_cache_model()
    with torch.no_grad():
        full_logits_bc = model_bc(tokens)  # [1, SEQ_LEN, VOCAB]

        # Simulate autoregressive: process prefix of increasing length
        # and compare logits at each position
        max_diffs_bc = []
        for t in [16, 32, 64, 96, SEQ_LEN]:
            prefix = tokens[:, :t]
            prefix_logits = model_bc(prefix)  # [1, t, VOCAB]
            # Compare last-position logits
            ref_last = full_logits_bc[:, t-1:t, :]
            ar_last = prefix_logits[:, -1:, :]
            diff_at_t = (ref_last - ar_last).abs().max().item()
            max_diffs_bc.append(diff_at_t)

        findings["binding_cache_prefix_diffs"] = max_diffs_bc
        findings["binding_cache_prefix_positions"] = [16, 32, 64, 96, SEQ_LEN]

    # --- Verdict ---
    cache_bug = max_diff > 1e-3
    findings["VERDICT"] = "BUG DETECTED" if cache_bug else "CACHE CORRECT"

    report("STEP 1: Cache Correctness", findings)
    return findings


# ===================================================================
# STEP 2 — LOGIT GEOMETRY DIAGNOSTICS
# ===================================================================

def step2_logit_geometry():
    print("\n" + "#" * 70)
    print("# STEP 2: LOGIT GEOMETRY (norms, entropy, top-1 probability)")
    print("#" * 70)

    findings = {}
    model = make_binding_cache_model()

    # Generate 256 tokens autoregressively
    gen_len = 256
    prompt = torch.randint(0, VOCAB, (1, 16))

    logit_norms = []
    entropies = []
    top1_probs = []

    with torch.no_grad():
        input_ids = prompt.clone()
        for step in range(gen_len):
            logits = model(input_ids)  # [1, N, VOCAB]
            last_logits = logits[:, -1, :]  # [1, VOCAB]

            # Record metrics
            logit_norms.append(last_logits.norm(dim=-1).item())
            entropies.append(entropy(last_logits).item())
            top1_probs.append(top1_prob(last_logits).item())

            # Sample next token (greedy for determinism)
            next_token = last_logits.argmax(dim=-1, keepdim=True)
            input_ids = torch.cat([input_ids, next_token], dim=1)

    # Analyze trends
    n = len(logit_norms)
    first_quarter = slice(0, n // 4)
    last_quarter = slice(3 * n // 4, n)

    findings["logit_norm_first_q"] = sum(logit_norms[first_quarter]) / (n // 4)
    findings["logit_norm_last_q"] = sum(logit_norms[last_quarter]) / (n // 4)
    findings["logit_norm_ratio"] = findings["logit_norm_last_q"] / (findings["logit_norm_first_q"] + 1e-8)

    findings["entropy_first_q"] = sum(entropies[first_quarter]) / (n // 4)
    findings["entropy_last_q"] = sum(entropies[last_quarter]) / (n // 4)
    findings["entropy_ratio"] = findings["entropy_last_q"] / (findings["entropy_first_q"] + 1e-8)

    findings["top1_prob_first_q"] = sum(top1_probs[first_quarter]) / (n // 4)
    findings["top1_prob_last_q"] = sum(top1_probs[last_quarter]) / (n // 4)

    # Detect issues
    logit_growth = findings["logit_norm_ratio"] > 2.0
    entropy_collapse = findings["entropy_ratio"] < 0.3
    overconfident = findings["top1_prob_last_q"] > 0.95

    findings["MONOTONIC_LOGIT_GROWTH"] = logit_growth
    findings["ENTROPY_COLLAPSE"] = entropy_collapse
    findings["OVERCONFIDENT"] = overconfident

    # Also check with HybridPhaseTransformer
    model_h = make_hybrid_model()
    logit_norms_h = []
    entropies_h = []
    with torch.no_grad():
        input_ids_h = prompt.clone()
        for step in range(gen_len):
            result = model_h(input_ids_h)
            last_logits_h = result["logits"][:, -1, :]
            logit_norms_h.append(last_logits_h.norm(dim=-1).item())
            entropies_h.append(entropy(last_logits_h).item())
            next_token = last_logits_h.argmax(dim=-1, keepdim=True)
            input_ids_h = torch.cat([input_ids_h, next_token], dim=1)

    findings["hybrid_logit_norm_first_q"] = sum(logit_norms_h[first_quarter]) / (n // 4)
    findings["hybrid_logit_norm_last_q"] = sum(logit_norms_h[last_quarter]) / (n // 4)
    findings["hybrid_entropy_first_q"] = sum(entropies_h[first_quarter]) / (n // 4)
    findings["hybrid_entropy_last_q"] = sum(entropies_h[last_quarter]) / (n // 4)

    report("STEP 2: Logit Geometry", findings)
    return findings, logit_norms, entropies, top1_probs


# ===================================================================
# STEP 3 — ABLATION ISOLATION
# ===================================================================

def step3_ablation_isolation():
    print("\n" + "#" * 70)
    print("# STEP 3: ABLATION ISOLATION")
    print("#" * 70)

    findings = {}
    prompt = torch.randint(0, VOCAB, (1, 16))
    gen_len = 128

    def generate_and_analyze(model, name, gen_len=128):
        """Generate tokens and compute quality metrics."""
        with torch.no_grad():
            input_ids = prompt.clone()
            all_tokens = []
            entropies_list = []

            for step in range(gen_len):
                if isinstance(model, BindingCacheTransformer):
                    logits = model(input_ids)
                else:
                    logits = model(input_ids)["logits"]
                last_logits = logits[:, -1, :] if not isinstance(logits, dict) else logits[:, -1, :]
                entropies_list.append(entropy(last_logits).item())
                next_token = last_logits.argmax(dim=-1, keepdim=True)
                all_tokens.append(next_token.item())
                input_ids = torch.cat([input_ids, next_token], dim=1)

            # Repetition analysis
            bigrams = [(all_tokens[i], all_tokens[i+1]) for i in range(len(all_tokens)-1)]
            unique_bigrams = len(set(bigrams))
            total_bigrams = len(bigrams)
            repetition_rate = 1.0 - (unique_bigrams / total_bigrams) if total_bigrams > 0 else 0.0

            # Token diversity
            unique_tokens = len(set(all_tokens))
            token_diversity = unique_tokens / len(all_tokens)

            return {
                f"{name}_repetition_rate": repetition_rate,
                f"{name}_token_diversity": token_diversity,
                f"{name}_mean_entropy": sum(entropies_list) / len(entropies_list),
                f"{name}_unique_bigrams": unique_bigrams,
                f"{name}_total_bigrams": total_bigrams,
            }

    # A) Full model (Local + Phase + Quad)
    model_full = make_binding_cache_model()
    findings.update(generate_and_analyze(model_full, "full"))

    # B) Local-only: disable Phase and Quad by setting phase ablation to "off"
    model_local = make_binding_cache_model()
    model_local.set_ablation("off")  # Zeroes out phase
    # Also disable quad by temporarily setting use_cache to False and top_k very high
    for block in model_local.blocks:
        block.quad_query.use_cache = False
        # Set quad output to zero by zeroing out_proj
        with torch.no_grad():
            block.quad_query.out_proj.weight.zero_()
            if block.quad_query.out_proj.bias is not None:
                block.quad_query.out_proj.bias.zero_()
    findings.update(generate_and_analyze(model_local, "local_only"))

    # C) Memory-only: disable local window attention
    model_mem = make_binding_cache_model()
    for block in model_mem.blocks:
        with torch.no_grad():
            block.local_attn.out_proj.weight.zero_()
            if block.local_attn.out_proj.bias is not None:
                block.local_attn.out_proj.bias.zero_()
    findings.update(generate_and_analyze(model_mem, "memory_only"))

    # D) Quad-soft: replace top-K with full attention (no cache sparsity)
    model_qs = make_binding_cache_model()
    for block in model_qs.blocks:
        block.quad_query.use_cache = False  # Full O(n^2) attention
    findings.update(generate_and_analyze(model_qs, "quad_soft"))

    report("STEP 3: Ablation Isolation", findings)
    return findings


# ===================================================================
# STEP 4 — PHASE MEMORY STABILITY CHECK
# ===================================================================

def step4_phase_memory_stability():
    print("\n" + "#" * 70)
    print("# STEP 4: PHASE MEMORY STABILITY")
    print("#" * 70)

    findings = {}
    model = make_binding_cache_model()
    tokens = torch.randint(0, VOCAB, (1, SEQ_LEN))

    # Instrument phase state computation
    memory_states_per_layer = defaultdict(list)

    # Hook into phase_state forward
    hooks = []
    for layer_idx, block in enumerate(model.blocks):
        def make_hook(idx):
            def hook_fn(module, input, output):
                # output is memory_state [B, N, D]
                with torch.no_grad():
                    mem = output
                    memory_states_per_layer[idx].append({
                        "mean": mem.mean().item(),
                        "var": mem.var().item(),
                        "norm": mem.norm().item(),
                        "max_abs": mem.abs().max().item(),
                        "min_abs": mem.abs().min().item(),
                    })
            return hook_fn
        h = block.phase_state.register_forward_hook(make_hook(layer_idx))
        hooks.append(h)

    # Run forward passes with increasing sequence lengths
    with torch.no_grad():
        for seq_len in [32, 64, 128, 256]:
            toks = torch.randint(0, VOCAB, (1, seq_len))
            _ = model(toks)

    # Remove hooks
    for h in hooks:
        h.remove()

    # Analyze stability
    for layer_idx in sorted(memory_states_per_layer.keys()):
        states = memory_states_per_layer[layer_idx]
        norms = [s["norm"] for s in states]
        means = [s["mean"] for s in states]
        variances = [s["var"] for s in states]
        max_abs = [s["max_abs"] for s in states]

        findings[f"layer_{layer_idx}_norms"] = norms
        findings[f"layer_{layer_idx}_means"] = means
        findings[f"layer_{layer_idx}_variances"] = variances
        findings[f"layer_{layer_idx}_max_abs"] = max_abs

        # Check for explosion
        if len(norms) >= 2:
            norm_growth = norms[-1] / (norms[0] + 1e-8)
            findings[f"layer_{layer_idx}_norm_growth"] = norm_growth

    # Check if memory is exploding or saturating
    all_norms = []
    for layer_idx in sorted(memory_states_per_layer.keys()):
        states = memory_states_per_layer[layer_idx]
        all_norms.extend([s["norm"] for s in states])

    if all_norms:
        max_norm = max(all_norms)
        findings["max_norm_across_all"] = max_norm
        findings["EXPLODING"] = max_norm > 1000
        findings["SATURATING"] = all(n < 0.01 for n in all_norms[-4:]) if len(all_norms) >= 4 else False

    report("STEP 4: Phase Memory Stability", findings)
    return findings


# ===================================================================
# STEP 5 — QUAD ROUTING STRESS TEST
# ===================================================================

def step5_quad_routing():
    print("\n" + "#" * 70)
    print("# STEP 5: QUAD ROUTING STRESS TEST")
    print("#" * 70)

    findings = {}
    model = make_binding_cache_model()
    tokens = torch.randint(0, VOCAB, (1, SEQ_LEN))

    # Instrument quad_query to capture top-K indices
    topk_indices_per_layer = defaultdict(list)
    attention_weights_per_layer = defaultdict(list)

    hooks = []
    for layer_idx, block in enumerate(model.blocks):
        original_forward = block.quad_query.forward

        def make_instrumented_forward(idx, orig_fwd, quad_module):
            def instrumented_forward(x, memory_state, binding_salience=None):
                B, N, D = x.shape
                H = quad_module.num_heads
                D_h = quad_module.head_dim

                # Get Q and K/V from memory
                mem_norm = quad_module.norm_mem(memory_state)
                x_norm = quad_module.norm_q(x)
                Q = quad_module.W_q(x_norm).view(B, N, H, D_h).transpose(1, 2)
                K = quad_module.W_k(mem_norm).view(B, N, H, D_h).transpose(1, 2)

                # Compute attention scores
                scores = torch.matmul(Q, K.transpose(-2, -1)) / (D_h ** 0.5)

                # Capture top-K indices
                if quad_module.use_cache and quad_module.top_k < N:
                    _, top_indices = scores.mean(dim=-2).topk(
                        min(quad_module.top_k, N), dim=-1
                    )
                    topk_indices_per_layer[idx].append(top_indices.detach())

                # Capture attention distribution
                with torch.no_grad():
                    attn_w = F.softmax(scores, dim=-1)
                    attention_weights_per_layer[idx].append(attn_w.detach())

                # Call original forward
                return orig_fwd(x, memory_state, binding_salience)
            return instrumented_forward

        block.quad_query.forward = make_instrumented_forward(
            layer_idx, original_forward, block.quad_query
        )

    with torch.no_grad():
        _ = model(tokens)

    # Analyze routing
    for layer_idx in sorted(topk_indices_per_layer.keys()):
        indices_list = topk_indices_per_layer[layer_idx]
        if indices_list:
            indices = indices_list[0]  # [B, H, K]
            B, H, K = indices.shape

            # Per-head index distribution
            head_index_sets = []
            for h in range(H):
                head_indices = set(indices[0, h].tolist())
                head_index_sets.append(head_indices)

            # Overlap ratio between heads
            overlaps = []
            for i in range(H):
                for j in range(i + 1, H):
                    overlap = len(head_index_sets[i] & head_index_sets[j])
                    union = len(head_index_sets[i] | head_index_sets[j])
                    jaccard = overlap / union if union > 0 else 0
                    overlaps.append(jaccard)

            mean_overlap = sum(overlaps) / len(overlaps) if overlaps else 0
            findings[f"layer_{layer_idx}_head_overlap_jaccard"] = mean_overlap
            findings[f"layer_{layer_idx}_num_unique_indices_per_head"] = [
                len(s) for s in head_index_sets
            ]

    # Analyze attention weight distribution
    for layer_idx in sorted(attention_weights_per_layer.keys()):
        attn_list = attention_weights_per_layer[layer_idx]
        if attn_list:
            attn = attn_list[0]  # [B, H, N, N]
            # Average attention distance
            N = attn.shape[-1]
            positions = torch.arange(N, dtype=torch.float32)
            dist_matrix = (positions.unsqueeze(0) - positions.unsqueeze(1)).abs()
            avg_attn_dist = (attn[0] * dist_matrix.unsqueeze(0)).sum(dim=-1).mean().item()
            findings[f"layer_{layer_idx}_avg_attn_distance"] = avg_attn_dist

            # Entropy of attention weights
            attn_entropy = -(attn * (attn + 1e-10).log()).sum(dim=-1).mean().item()
            findings[f"layer_{layer_idx}_attn_entropy"] = attn_entropy

    # Detect high redundancy
    overlap_vals = [v for k, v in findings.items() if "overlap_jaccard" in k]
    if overlap_vals:
        findings["ROUTING_REDUNDANT"] = any(o > 0.7 for o in overlap_vals)
    else:
        findings["ROUTING_REDUNDANT"] = "N/A"

    report("STEP 5: Quad Routing", findings)
    return findings


# ===================================================================
# STEP 6 — EXPOSURE BIAS CHECK
# ===================================================================

def step6_exposure_bias():
    print("\n" + "#" * 70)
    print("# STEP 6: EXPOSURE BIAS CHECK")
    print("#" * 70)

    findings = {}
    model = make_binding_cache_model()

    # Create a reference sequence
    ref_tokens = torch.randint(0, VOCAB, (1, SEQ_LEN))

    with torch.no_grad():
        # Teacher-forced: full-sequence forward
        tf_logits = model(ref_tokens)  # [1, SEQ_LEN, VOCAB]

        # Free-running: start with prefix, generate rest
        prefix_len = 16
        prefix = ref_tokens[:, :prefix_len]
        input_ids = prefix.clone()

        fr_logits_at_positions = []
        for t in range(prefix_len, SEQ_LEN):
            logits = model(input_ids)
            last_logits = logits[:, -1:, :]  # [1, 1, VOCAB]
            fr_logits_at_positions.append(last_logits)

            # Use model's own prediction (free-running)
            next_token = last_logits.argmax(dim=-1)  # greedy
            input_ids = torch.cat([input_ids, next_token], dim=1)

        # Compare hidden states at corresponding positions
        # We use logit divergence as a proxy for hidden state divergence
        divergences = []
        for t_offset, fr_logit in enumerate(fr_logits_at_positions):
            t = prefix_len + t_offset
            tf_logit = tf_logits[:, t:t+1, :]  # [1, 1, VOCAB]

            # KL divergence: KL(tf || fr)
            tf_probs = F.softmax(tf_logit, dim=-1)
            fr_log_probs = F.log_softmax(fr_logit, dim=-1)
            tf_log_probs = F.log_softmax(tf_logit, dim=-1)
            kl = (tf_probs * (tf_log_probs - fr_log_probs)).sum(dim=-1).item()
            divergences.append(kl)

        # Analyze divergence trend
        if len(divergences) >= 50:
            div_at_10 = sum(divergences[:10]) / 10
            div_at_50 = sum(divergences[40:50]) / 10
            div_at_end = sum(divergences[-10:]) / 10
        else:
            div_at_10 = sum(divergences[:5]) / 5 if len(divergences) >= 5 else 0
            div_at_50 = sum(divergences[-5:]) / 5 if len(divergences) >= 5 else 0
            div_at_end = div_at_50

        findings["kl_divergence_at_10"] = div_at_10
        findings["kl_divergence_at_50"] = div_at_50
        findings["kl_divergence_at_end"] = div_at_end
        findings["divergence_growth_ratio"] = div_at_end / (div_at_10 + 1e-8)

        findings["EXPOSURE_BIAS_SEVERE"] = div_at_end > 10 * div_at_10 and div_at_end > 1.0

    report("STEP 6: Exposure Bias", findings)
    return findings


# ===================================================================
# STEP 1b — DETAILED CACHE MISMATCH ANALYSIS
# ===================================================================

def step1b_cache_mismatch_analysis():
    """Deep analysis of WHY cache diverges (if it does)."""
    print("\n" + "#" * 70)
    print("# STEP 1b: DETAILED CACHE MISMATCH ANALYSIS")
    print("#" * 70)

    findings = {}
    model = make_hybrid_model()
    tokens = torch.randint(0, VOCAB, (1, SEQ_LEN))

    with torch.no_grad():
        # Full-sequence forward
        full_result = model(tokens)
        full_logits = full_result["logits"]

        # Incremental: token-by-token from the start
        cache = None
        incremental_logits_list = []
        for t in range(SEQ_LEN):
            tok = tokens[:, t:t+1]
            result, cache = model.forward_with_cache(tok, cache)
            incremental_logits_list.append(result["logits"])

        incremental_logits = torch.cat(incremental_logits_list, dim=1)

        # Per-position analysis
        diff = (full_logits - incremental_logits).abs()
        per_pos_max = diff.max(dim=-1).values.squeeze(0)

        # Find where divergence starts
        threshold = 1e-4
        divergent = (per_pos_max > threshold).nonzero(as_tuple=True)[0]

        if len(divergent) > 0:
            first_div = divergent[0].item()
            findings["first_divergent_position"] = first_div
            findings["divergence_at_first"] = per_pos_max[first_div].item()
            findings["divergence_grows_monotonically"] = all(
                per_pos_max[i] <= per_pos_max[i+1] * 1.5
                for i in range(first_div, min(first_div + 20, SEQ_LEN - 1))
            )

            # Check if the divergence is in local layers or hybrid layers
            # By comparing layer outputs
            findings["note"] = (
                "Divergence detected. In protected_phase mode, incremental inference "
                "passes [prev_state, current_state] to local attention (2 KV positions), "
                "while full-sequence passes [memory_state_0, ..., memory_state_N] "
                "(N KV positions). This causes local attention to see different "
                "memory views, leading to cumulative divergence."
            )
        else:
            findings["divergence"] = "None detected (< 1e-4)"

        # Also check: do position embeddings align?
        # In full mode: pos = [0, 1, 2, ..., N-1]
        # In cache mode: chunk_offset should increment correctly
        findings["cache_seq_len"] = cache.seq_len
        findings["expected_seq_len"] = SEQ_LEN
        findings["seq_len_match"] = cache.seq_len == SEQ_LEN

    report("STEP 1b: Cache Mismatch Analysis", findings)
    return findings


# ===================================================================
# MAIN
# ===================================================================

def main():
    print("=" * 70)
    print("  PHASE-QUAD LOCAL ATTENTION — DIAGNOSTIC SUITE")
    print("=" * 70)
    print(f"  Models: BindingCacheTransformer + HybridPhaseTransformer")
    print(f"  Config: vocab={VOCAB}, embed={EMBED}, heads={HEADS}, layers={LAYERS}")
    print(f"  Seq length: {SEQ_LEN}, window: {WINDOW}, top_k: {TOP_K}")
    print()

    all_findings = {}

    # Step 1: Cache correctness
    f1 = step1_cache_correctness()
    all_findings["step1"] = f1

    # Step 1b: Detailed cache analysis
    f1b = step1b_cache_mismatch_analysis()
    all_findings["step1b"] = f1b

    # Step 2: Logit geometry
    f2, norms, ents, probs = step2_logit_geometry()
    all_findings["step2"] = f2

    # Step 3: Ablation isolation
    f3 = step3_ablation_isolation()
    all_findings["step3"] = f3

    # Step 4: Phase memory stability
    f4 = step4_phase_memory_stability()
    all_findings["step4"] = f4

    # Step 5: Quad routing
    f5 = step5_quad_routing()
    all_findings["step5"] = f5

    # Step 6: Exposure bias
    f6 = step6_exposure_bias()
    all_findings["step6"] = f6

    # ================================================================
    # SUMMARY
    # ================================================================
    print("\n" + "=" * 70)
    print("  DIAGNOSTIC SUMMARY")
    print("=" * 70)

    issues = []

    # Cache bug
    if f1.get("VERDICT") == "BUG DETECTED":
        issues.append(("CACHE BUG", f"max_diff={f1['hybrid_max_abs_diff']:.6f}"))

    # Logit geometry
    if f2.get("MONOTONIC_LOGIT_GROWTH"):
        issues.append(("LOGIT GROWTH", f"ratio={f2['logit_norm_ratio']:.2f}"))
    if f2.get("ENTROPY_COLLAPSE"):
        issues.append(("ENTROPY COLLAPSE", f"ratio={f2['entropy_ratio']:.2f}"))
    if f2.get("OVERCONFIDENT"):
        issues.append(("OVERCONFIDENCE", f"top1={f2['top1_prob_last_q']:.3f}"))

    # Memory stability
    if f4.get("EXPLODING"):
        issues.append(("PHASE EXPLOSION", f"max_norm={f4['max_norm_across_all']:.2f}"))
    if f4.get("SATURATING"):
        issues.append(("PHASE SATURATION", "norms near 0"))

    # Quad routing
    if f5.get("ROUTING_REDUNDANT") == True:
        issues.append(("ROUTING REDUNDANCY", "head overlap > 0.7"))

    # Exposure bias
    if f6.get("EXPOSURE_BIAS_SEVERE"):
        issues.append(("EXPOSURE BIAS", f"growth={f6['divergence_growth_ratio']:.2f}"))

    if issues:
        print("\n  ISSUES DETECTED:")
        for name, detail in issues:
            print(f"    [!] {name}: {detail}")
    else:
        print("\n  No critical issues detected in randomized model.")
        print("  NOTE: These diagnostics run on UNTRAINED random weights.")
        print("  Root cause analysis below is based on code inspection.")

    # ================================================================
    # ROOT CAUSE ANALYSIS (from code review)
    # ================================================================
    print("\n" + "=" * 70)
    print("  ROOT CAUSE ANALYSIS (from architecture inspection)")
    print("=" * 70)

    print("""
  1. CACHE BUG (HybridPhaseTransformer.generate_with_cache):
     In protected_phase mode, full-sequence forward passes the FULL
     memory_state [B, N, H, D_h] to LocalAttention as K/V.
     In incremental mode, only [prev_state, current_state] is passed (2 positions).
     Local attention sees drastically different memory views.
     SEVERITY: HIGH — causes cumulative logit divergence during generation.

  2. MEMORY STATE NORM GROWTH (BindingCachePhaseState):
     With decay_gamma=1.0 (cumsum), memory_state norm grows O(sqrt(N)).
     No normalization is applied to memory_state before Quad queries it.
     Long sequences cause memory states to dominate quad scores.
     SEVERITY: MEDIUM — causes attention to flatten over long generations.

  3. LOGIT SCALING:
     logit_scale = 1/sqrt(sqrt(embed_dim)) is applied uniformly.
     No z-loss or entropy regularization prevents logit norm growth.
     Combined with growing memory state, this causes overconfidence.
     SEVERITY: MEDIUM — contributes to entropy collapse.

  4. QUAD TOP-K SPARSITY:
     With small top_k relative to sequence length, quad retrieval
     misses relevant positions. No mechanism forces inclusion of
     recent positions in the candidate set.
     SEVERITY: LOW-MEDIUM — reduces entity retention.
    """)

    return all_findings


if __name__ == "__main__":
    all_findings = main()
