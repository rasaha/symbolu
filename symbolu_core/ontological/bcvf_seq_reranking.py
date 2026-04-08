#!/usr/bin/env python3
"""
Sequence-Level BCVF Candidate Reranking
========================================

Implements sequence-level reranking of candidate continuations using BCVF
(Bidirectional Consistency Verification Framework) signals.  This targets
the regime where BCVF should actually help: selecting among diverse
multi-token completions rather than adjusting individual token choices.

Equation Chosen: **(B) BCVF-adjusted logits then sequence logprob**
----------------------------------------------------------------------

For a candidate sequence y = (t_1, ..., t_N) conditioned on prompt x:

    At each generated position i, adjust the top-M logits:

        z'_i(t) = z_i(t) - lambda * beta * L_i(t)

    where L_i(t) is the BCVF consistency Lagrangian:

        L = lambda_f * (1 - sf)^2 + lambda_b * (1 - sb)^2 + lambda_c * (sf - sb)^2

    with sf = sigmoid(5 * cos_sim(h_i, emb(t))) (forward feasibility)
    and  sb = sigmoid(5 * cos_sim(emb(t), goal)) (backward goal alignment).

    Non-top-M logits are set to -inf (consistent with existing token-level
    pipeline in bcvf_decoding.py).

    The sequence score is the sum of log-probs under the adjusted distribution:

        Score(y) = sum_i  log softmax(z'_i)(t_i)

**Why Equation (B)?**

1. Directly extends the existing token-level ``adjusted = base_logit - beta * L``
   to sequence level --- no new math, just accumulation.
2. The lambda parameter maps cleanly: ``effective_beta = lambda * beta``.
   Setting lambda=0 recovers pure base logprob reranking (softmax of
   unmodified logits).  Setting lambda=1 applies the full BCVF penalty.
3. Avoids the scale-mismatch problem of Equation (A), which additively
   mixes log-probs (range ~ [-15, 0]) with raw BCVF penalties (range
   ~ [0, 2]) requiring careful normalization.
4. Avoids the numerical instability of Equation (C), which requires
   normalizing BCVF scores over the full vocabulary to obtain p_bcvf.
5. Reuses all existing BCVF machinery (BCVFScoringModule, DecodingConfig)
   with zero additional learnable parameters.

Usage::

    from symbolu_core.ontological.bcvf_seq_reranking import (
        rerank_candidates,
        generate_and_rerank,
        run_seq_rerank_benchmark,
    )

    best_idx, scores, diagnostics = rerank_candidates(
        prompt_ids, candidate_ids_list, model, goal_embedding,
        bcvf_config, rerank_lambda=0.5,
    )
"""

from __future__ import annotations

import ast
import math
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

from symbolu_core.ontological.bcvf_decoding import BCVFScoringModule, DecodingConfig
from symbolu_core.ontological.bcvf_benchmarks import (
    BootstrapCI,
    bootstrap_ci,
    bootstrap_pass_at_1_delta,
)


# =========================================================================
# Data Structures
# =========================================================================


# Valid reranking modes
RERANK_MODES = ("bcvf", "logprob", "oracle_verifier", "value", "learned_value", "value_feature")


@dataclass
class SeqRerankResult:
    """Result for one prompt's sequence-level reranking."""

    prompt_id: str = ""
    K: int = 0
    rerank_lambda: float = 1.0
    rerank_mode: str = "bcvf"  # bcvf | logprob | oracle_verifier
    # Base (logprob) reranking
    base_best_idx: int = 0
    base_best_score: float = 0.0
    base_scores: Optional[np.ndarray] = None
    # BCVF reranking
    bcvf_best_idx: int = 0
    bcvf_best_score: float = 0.0
    bcvf_scores: Optional[np.ndarray] = None
    # Comparison
    rerank_changed: bool = False
    score_margin: float = 0.0       # bcvf_best - bcvf_second_best
    base_score_margin: float = 0.0  # base_best - base_second_best
    # Per-candidate details
    candidate_lengths: List[int] = field(default_factory=list)
    # Functional evaluation (if available)
    base_passed: Optional[bool] = None
    bcvf_passed: Optional[bool] = None
    any_passed: Optional[bool] = None  # oracle: did ANY of K pass?
    # Generated texts (for debugging)
    base_text: str = ""
    bcvf_text: str = ""
    # --- BCVF signal diagnostics ---
    topM_hit_rate: float = 0.0         # mean across candidates: frac of tokens in top-M
    mean_sf: float = 0.0               # mean forward score (target tokens)
    mean_sb: float = 0.0               # mean backward score (target tokens)
    mean_sf_all: float = 0.0           # mean forward score (all top-M tokens)
    mean_sb_all: float = 0.0           # mean backward score (all top-M tokens)
    std_sf_all: float = 0.0            # std forward score (all top-M tokens)
    std_sb_all: float = 0.0            # std backward score (all top-M tokens)
    mean_L: float = 0.0                # mean Lagrangian on target tokens
    std_L: float = 0.0                 # std Lagrangian on target tokens
    penalty_per_tok: float = 0.0       # mean BCVF penalty per token
    base_lp_per_tok: float = 0.0       # mean base logprob per token
    score_std: float = 0.0             # std of BCVF scores across K candidates
    base_score_std: float = 0.0        # std of base scores across K candidates
    rank_correlation: float = 0.0      # Spearman corr(base_rank, bcvf_rank)


@dataclass
class SeqRerankReport:
    """Aggregated metrics across all prompts."""

    n_prompts: int = 0
    K: int = 0
    rerank_lambda: float = 1.0
    equation: str = "B"
    rerank_mode: str = "bcvf"  # bcvf | logprob | oracle_verifier
    # Reranking behavior
    rerank_rate: float = 0.0           # fraction where BCVF picked different
    mean_score_margin: float = 0.0     # avg (best - second_best) under BCVF
    mean_base_score_margin: float = 0.0
    # HumanEval-style pass@1
    base_pass_at_1: Optional[float] = None
    bcvf_pass_at_1: Optional[float] = None
    oracle_pass_at_k: Optional[float] = None
    pass_at_1_delta: Optional[float] = None
    pass_at_1_delta_ci: Optional[BootstrapCI] = None
    # Win-rate: fraction where BCVF passed AND base failed
    rerank_win_rate: float = 0.0
    rerank_loss_rate: float = 0.0  # BCVF failed AND base passed
    # Score-based metrics (for WikiText where no pass/fail)
    mean_base_logprob_selected: float = 0.0   # avg base logprob of base-best
    mean_bcvf_logprob_selected: float = 0.0   # avg base logprob of bcvf-best
    # Per-prompt results
    per_prompt: List[SeqRerankResult] = field(default_factory=list)
    # Timing
    elapsed_seconds: float = 0.0
    # --- Aggregated BCVF signal diagnostics ---
    agg_topM_hit_rate: float = 0.0       # mean top-M hit rate across prompts
    agg_mean_sf: float = 0.0             # mean forward score (target tokens)
    agg_mean_sb: float = 0.0             # mean backward score (target tokens)
    agg_mean_sf_all: float = 0.0         # mean sf across ALL top-M tokens
    agg_mean_sb_all: float = 0.0         # mean sb across ALL top-M tokens
    agg_std_sf_all: float = 0.0          # mean of per-prompt sf std (saturation?)
    agg_std_sb_all: float = 0.0          # mean of per-prompt sb std (saturation?)
    agg_mean_L: float = 0.0              # mean Lagrangian on target tokens
    agg_penalty_per_tok: float = 0.0     # mean penalty per token
    agg_base_lp_per_tok: float = 0.0     # mean base logprob per token
    agg_score_std: float = 0.0           # mean score std across candidates
    agg_base_score_std: float = 0.0      # mean base score std across candidates
    agg_rank_correlation: float = 0.0    # mean Spearman correlation


# =========================================================================
# Core Reranking Function
# =========================================================================


@torch.no_grad()
def rerank_candidates(
    prompt_ids: "torch.Tensor",
    candidate_ids_list: List["torch.Tensor"],
    model: Any,
    goal_embedding: "torch.Tensor",
    bcvf_config: DecodingConfig,
    rerank_lambda: float = 1.0,
    mode: str = "B",
) -> Tuple[int, np.ndarray, Dict[str, Any]]:
    """
    Score K candidate continuations and return the best index.

    Implements Equation (B): BCVF-adjusted logits -> sequence logprob.

    At each position i in candidate y:
        z'_i(t) = z_i(t) - lambda * beta * L_i(t)   (for top-M)
        z'_i(t) = -inf                                (outside top-M)
        Score(y) = sum_i log softmax(z'_i)(y_i)

    Sanity checks:
        - lambda=1: full BCVF adjustment (standard seq-level BCVF)
        - lambda=0: effective_beta=0, so z'_i = z_i for top-M, Score = base logprob
          (recovers base logprob reranking, restricted to top-M vocabulary)

    Args:
        prompt_ids: Token ids of the prompt, shape [P].
        candidate_ids_list: List of K continuation token tensors, each [T_k].
        model: HuggingFace causal LM with get_input_embeddings().
        goal_embedding: Goal vector, shape [1, D].
        bcvf_config: DecodingConfig with BCVF parameters (top_m, beta,
            lambda_f, lambda_b, lambda_c).
        rerank_lambda: Mixing parameter in [0, 1].
            0 = base logprob reranking (no BCVF).
            1 = full BCVF penalty applied.
        mode: Equation mode. Only "B" is implemented.

    Returns:
        best_index: Index of the best candidate (0-indexed).
        scores: Array of K scores (Equation B sequence logprobs).
        diagnostics: Dict with per-candidate details.
    """
    if not PYTORCH_AVAILABLE:
        raise ImportError("PyTorch is required")

    if mode != "B":
        raise ValueError(
            f"Only mode='B' is implemented (BCVF-adjusted logits -> "
            f"sequence logprob).  Got mode='{mode}'."
        )

    device = prompt_ids.device
    K = len(candidate_ids_list)
    P = prompt_ids.shape[0]

    if K == 0:
        return 0, np.array([]), {}

    # --- Vocab embeddings ---
    vocab_emb = model.get_input_embeddings().weight.detach()  # [V, D]

    # --- Pad candidates and build batched input ---
    cand_lengths = [c.shape[0] for c in candidate_ids_list]
    max_cand_len = max(cand_lengths)

    # Determine pad token
    pad_id = getattr(model, "config", None)
    if pad_id is not None:
        pad_id = getattr(pad_id, "pad_token_id", None)
    if pad_id is None:
        pad_id = 0

    batch_input = torch.full(
        (K, P + max_cand_len), pad_id,
        dtype=torch.long, device=device,
    )
    attention_mask = torch.zeros(
        K, P + max_cand_len, dtype=torch.long, device=device,
    )

    for k, cand in enumerate(candidate_ids_list):
        T_k = cand.shape[0]
        batch_input[k, :P] = prompt_ids
        batch_input[k, P:P + T_k] = cand
        attention_mask[k, :P + T_k] = 1

    # --- Batched forward pass ---
    outputs = model(
        batch_input,
        attention_mask=attention_mask,
        output_hidden_states=True,
        use_cache=False,
    )
    logits_all = outputs.logits              # [K, P+max_T, V]
    hidden_all = outputs.hidden_states[-1]   # [K, P+max_T, D]

    # --- BCVF scorer ---
    scorer = BCVFScoringModule(bcvf_config)
    effective_beta = rerank_lambda * bcvf_config.beta
    top_m = min(bcvf_config.top_m, logits_all.shape[-1])

    # --- Goal embedding: broadcast to [K, D] ---
    if goal_embedding.dim() == 2:
        goal = goal_embedding.expand(K, -1).to(device)  # [K, D]
    else:
        goal = goal_embedding.unsqueeze(0).expand(K, -1).to(device)

    # --- Score each candidate (vectorized over positions) ---
    scores = np.zeros(K, dtype=np.float64)
    base_scores = np.zeros(K, dtype=np.float64)
    bcvf_penalties = np.zeros(K, dtype=np.float64)
    per_candidate_sf = []
    per_candidate_sb = []
    # Signal diagnostics: per-candidate details
    per_candidate_topM_hit_rate = []   # fraction of target tokens in top-M
    per_candidate_L_mean = []          # mean Lagrangian on target tokens
    per_candidate_L_std = []           # std  Lagrangian on target tokens
    per_candidate_sf_std = []          # std  forward score on target tokens
    per_candidate_sb_std = []          # std  backward score on target tokens
    per_candidate_sf_all_mean = []     # mean sf across ALL top-M tokens (not just target)
    per_candidate_sb_all_mean = []     # mean sb across ALL top-M tokens
    per_candidate_sf_all_std = []      # std  sf across ALL top-M tokens
    per_candidate_sb_all_std = []      # std  sb across ALL top-M tokens
    per_candidate_penalty_per_tok = [] # bcvf penalty / T_k
    per_candidate_base_per_tok = []    # base logprob / T_k

    for k in range(K):
        T_k = cand_lengths[k]
        if T_k == 0:
            _zero_diag = 0.0
            per_candidate_topM_hit_rate.append(_zero_diag)
            per_candidate_L_mean.append(_zero_diag)
            per_candidate_L_std.append(_zero_diag)
            per_candidate_sf_std.append(_zero_diag)
            per_candidate_sb_std.append(_zero_diag)
            per_candidate_sf_all_mean.append(_zero_diag)
            per_candidate_sb_all_mean.append(_zero_diag)
            per_candidate_sf_all_std.append(_zero_diag)
            per_candidate_sb_all_std.append(_zero_diag)
            per_candidate_penalty_per_tok.append(_zero_diag)
            per_candidate_base_per_tok.append(_zero_diag)
            continue

        # Positions: logits at (P-1)..(P-1+T_k-1) predict tokens at P..(P+T_k-1)
        # i.e., logits[k, P-1+t, :] predicts candidate_ids_list[k][t]
        h = hidden_all[k, P - 1:P - 1 + T_k, :]   # [T_k, D]
        z = logits_all[k, P - 1:P - 1 + T_k, :]   # [T_k, V]
        target = candidate_ids_list[k].to(device)   # [T_k]
        g = goal[k].unsqueeze(0).expand(T_k, -1)    # [T_k, D]

        # --- Base log-probs ---
        base_lp = F.log_softmax(z, dim=-1)   # [T_k, V]
        base_lp_tokens = base_lp.gather(
            1, target.unsqueeze(1)
        ).squeeze(1)                          # [T_k]
        base_scores[k] = float(base_lp_tokens.sum().item())
        per_candidate_base_per_tok.append(
            float(base_lp_tokens.sum().item()) / T_k
        )

        if effective_beta > 0:
            # --- Top-M selection ---
            topM_scores, topM_indices = torch.topk(z, top_m, dim=-1)  # [T_k, M]
            candidates_emb = vocab_emb[topM_indices]                  # [T_k, M, D]

            # --- BCVF scores (batch dim = T_k positions) ---
            sf = scorer.forward_score(h, candidates_emb)   # [T_k, M]
            sb = scorer.backward_score(candidates_emb, g)  # [T_k, M]
            L = scorer.lagrangian(sf, sb)                   # [T_k, M]

            # --- Adjusted logits ---
            adjusted_logits = torch.full_like(z, float("-inf"))
            src = (topM_scores - effective_beta * L).to(adjusted_logits.dtype)
            adjusted_logits.scatter_(1, topM_indices, src)

            # --- Adjusted log-probs ---
            adj_lp = F.log_softmax(adjusted_logits, dim=-1)   # [T_k, V]
            adj_lp_tokens = adj_lp.gather(
                1, target.unsqueeze(1)
            ).squeeze(1)                                       # [T_k]
            scores[k] = float(adj_lp_tokens.sum().item())

            # --- Track BCVF penalty for the actual generated tokens ---
            # Find which target tokens are in top-M
            in_topM = (topM_indices == target.unsqueeze(1))  # [T_k, M]
            in_topM_f = in_topM.float()
            hit_rate = float(in_topM.any(dim=-1).float().mean().item())
            per_candidate_topM_hit_rate.append(hit_rate)

            L_for_targets = (L * in_topM_f).sum(dim=-1)  # [T_k]
            bcvf_penalties[k] = float(L_for_targets.sum().item())
            per_candidate_penalty_per_tok.append(
                float(L_for_targets.sum().item()) / T_k
            )

            # Per-position L stats for target tokens (only where in top-M)
            hits_mask = in_topM.any(dim=-1)  # [T_k] bool
            if hits_mask.any():
                L_hit = L_for_targets[hits_mask]
                per_candidate_L_mean.append(float(L_hit.mean().item()))
                per_candidate_L_std.append(
                    float(L_hit.std().item()) if L_hit.numel() > 1 else 0.0
                )
            else:
                per_candidate_L_mean.append(0.0)
                per_candidate_L_std.append(0.0)

            # Mean sf/sb across positions for target tokens
            sf_for_targets = (sf * in_topM_f).sum(dim=-1)
            sb_for_targets = (sb * in_topM_f).sum(dim=-1)
            per_candidate_sf.append(float(sf_for_targets.mean().item()))
            per_candidate_sb.append(float(sb_for_targets.mean().item()))
            if hits_mask.any():
                sf_hit = sf_for_targets[hits_mask]
                sb_hit = sb_for_targets[hits_mask]
                per_candidate_sf_std.append(
                    float(sf_hit.std().item()) if sf_hit.numel() > 1 else 0.0
                )
                per_candidate_sb_std.append(
                    float(sb_hit.std().item()) if sb_hit.numel() > 1 else 0.0
                )
            else:
                per_candidate_sf_std.append(0.0)
                per_candidate_sb_std.append(0.0)

            # sf/sb across ALL top-M candidates (saturation check)
            per_candidate_sf_all_mean.append(float(sf.mean().item()))
            per_candidate_sb_all_mean.append(float(sb.mean().item()))
            per_candidate_sf_all_std.append(float(sf.std().item()))
            per_candidate_sb_all_std.append(float(sb.std().item()))
        else:
            # lambda=0: pure base logprob
            scores[k] = base_scores[k]
            per_candidate_sf.append(0.0)
            per_candidate_sb.append(0.0)
            per_candidate_topM_hit_rate.append(1.0)
            per_candidate_L_mean.append(0.0)
            per_candidate_L_std.append(0.0)
            per_candidate_sf_std.append(0.0)
            per_candidate_sb_std.append(0.0)
            per_candidate_sf_all_mean.append(0.0)
            per_candidate_sb_all_mean.append(0.0)
            per_candidate_sf_all_std.append(0.0)
            per_candidate_sb_all_std.append(0.0)
            per_candidate_penalty_per_tok.append(0.0)

    # --- Select best ---
    best_index = int(np.argmax(scores))
    base_best_index = int(np.argmax(base_scores))

    # Score margins
    sorted_scores = np.sort(scores)[::-1]
    score_margin = float(sorted_scores[0] - sorted_scores[1]) if K > 1 else 0.0
    sorted_base = np.sort(base_scores)[::-1]
    base_margin = float(sorted_base[0] - sorted_base[1]) if K > 1 else 0.0

    # --- Score spread across candidates (is BCVF differentiating?) ---
    score_std = float(np.std(scores)) if K > 1 else 0.0
    base_score_std = float(np.std(base_scores)) if K > 1 else 0.0
    # Rank correlation: does BCVF preserve or scramble base ordering?
    if K > 2:
        # Spearman correlation without scipy: correlate ranks
        base_ranks = np.argsort(np.argsort(base_scores)).astype(float)
        bcvf_ranks = np.argsort(np.argsort(scores)).astype(float)
        d = base_ranks - bcvf_ranks
        n_k = float(K)
        rank_corr = 1.0 - 6.0 * float(np.sum(d ** 2)) / (n_k * (n_k ** 2 - 1))
    elif K == 2:
        rank_corr = 1.0 if np.argmax(base_scores) == np.argmax(scores) else -1.0
    else:
        rank_corr = float("nan")

    diagnostics = {
        "best_index": best_index,
        "base_best_index": base_best_index,
        "rerank_changed": best_index != base_best_index,
        "scores": scores,
        "base_scores": base_scores,
        "bcvf_penalties": bcvf_penalties,
        "score_margin": score_margin,
        "base_score_margin": base_margin,
        "candidate_lengths": cand_lengths,
        "per_candidate_sf": per_candidate_sf,
        "per_candidate_sb": per_candidate_sb,
        "effective_beta": effective_beta,
        "rerank_lambda": rerank_lambda,
        "top_m": top_m,
        # --- Signal diagnostics ---
        "score_std": score_std,
        "base_score_std": base_score_std,
        "rank_correlation": float(rank_corr),
        "per_candidate_topM_hit_rate": per_candidate_topM_hit_rate,
        "per_candidate_L_mean": per_candidate_L_mean,
        "per_candidate_L_std": per_candidate_L_std,
        "per_candidate_sf_std": per_candidate_sf_std,
        "per_candidate_sb_std": per_candidate_sb_std,
        "per_candidate_sf_all_mean": per_candidate_sf_all_mean,
        "per_candidate_sb_all_mean": per_candidate_sb_all_mean,
        "per_candidate_sf_all_std": per_candidate_sf_all_std,
        "per_candidate_sb_all_std": per_candidate_sb_all_std,
        "per_candidate_penalty_per_tok": per_candidate_penalty_per_tok,
        "per_candidate_base_per_tok": per_candidate_base_per_tok,
    }

    return best_index, scores, diagnostics


# =========================================================================
# Logprob-Only Reranking (no BCVF)
# =========================================================================


@torch.no_grad()
def logprob_rerank_candidates(
    prompt_ids: "torch.Tensor",
    candidate_ids_list: List["torch.Tensor"],
    model: Any,
    return_hidden_states: bool = False,
) -> Tuple[int, np.ndarray, Dict[str, Any]]:
    """
    Score K candidates by base logprob only.  No BCVF, no goal embedding.

    This is the honest baseline: generate K candidates with sampling,
    pick the one the model assigns highest probability to.

    Args:
        prompt_ids: Token ids of the prompt, shape [P].
        candidate_ids_list: List of K continuation token tensors, each [T_k].
        model: HuggingFace causal LM.
        return_hidden_states: If True, extract and return mean-pooled hidden
            states for each candidate in diagnostics["pooled_hiddens"].

    Returns:
        best_index: Index of the highest-logprob candidate.
        scores: Array of K base logprob scores.
        diagnostics: Dict with per-candidate details.  If return_hidden_states
            is True, includes "pooled_hiddens" as [K, D] tensor (CPU).
    """
    if not PYTORCH_AVAILABLE:
        raise ImportError("PyTorch is required")

    device = prompt_ids.device
    K = len(candidate_ids_list)
    P = prompt_ids.shape[0]

    if K == 0:
        return 0, np.array([]), {}

    # --- Pad candidates and build batched input ---
    cand_lengths = [c.shape[0] for c in candidate_ids_list]
    max_cand_len = max(cand_lengths)

    pad_id = getattr(model, "config", None)
    if pad_id is not None:
        pad_id = getattr(pad_id, "pad_token_id", None)
    if pad_id is None:
        pad_id = 0

    batch_input = torch.full(
        (K, P + max_cand_len), pad_id,
        dtype=torch.long, device=device,
    )
    attention_mask = torch.zeros(
        K, P + max_cand_len, dtype=torch.long, device=device,
    )

    for k, cand in enumerate(candidate_ids_list):
        T_k = cand.shape[0]
        batch_input[k, :P] = prompt_ids
        batch_input[k, P:P + T_k] = cand
        attention_mask[k, :P + T_k] = 1

    # --- Batched forward pass ---
    outputs = model(
        batch_input,
        attention_mask=attention_mask,
        output_hidden_states=return_hidden_states,
        use_cache=False,
    )
    logits_all = outputs.logits  # [K, P+max_T, V]

    # --- Extract pooled hidden states per candidate ---
    pooled_hiddens = None
    if return_hidden_states and hasattr(outputs, "hidden_states"):
        hidden_all = outputs.hidden_states[-1]  # [K, P+max_T, D]
        pooled_list = []
        for k in range(K):
            T_k = cand_lengths[k]
            if T_k == 0:
                D = hidden_all.shape[-1]
                pooled_list.append(torch.zeros(D, device="cpu"))
            else:
                # Mean-pool over candidate token positions
                h_k = hidden_all[k, P:P + T_k, :]  # [T_k, D]
                pooled_list.append(h_k.mean(dim=0).cpu().float())
        pooled_hiddens = torch.stack(pooled_list, dim=0)  # [K, D]

    # --- Score each candidate by base logprob ---
    scores = np.zeros(K, dtype=np.float64)

    for k in range(K):
        T_k = cand_lengths[k]
        if T_k == 0:
            continue

        z = logits_all[k, P - 1:P - 1 + T_k, :]  # [T_k, V]
        target = candidate_ids_list[k].to(device)   # [T_k]

        base_lp = F.log_softmax(z, dim=-1)
        base_lp_tokens = base_lp.gather(
            1, target.unsqueeze(1)
        ).squeeze(1)
        scores[k] = float(base_lp_tokens.sum().item())

    best_index = int(np.argmax(scores))

    # Score margins
    sorted_scores = np.sort(scores)[::-1]
    score_margin = float(sorted_scores[0] - sorted_scores[1]) if K > 1 else 0.0

    diagnostics = {
        "best_index": best_index,
        "base_best_index": best_index,
        "rerank_changed": False,
        "scores": scores,
        "base_scores": scores,
        "score_margin": score_margin,
        "base_score_margin": score_margin,
        "candidate_lengths": cand_lengths,
        "rerank_mode": "logprob",
    }
    if pooled_hiddens is not None:
        diagnostics["pooled_hiddens"] = pooled_hiddens

    return best_index, scores, diagnostics


# =========================================================================
# Indentation normalization for assembled code
# =========================================================================


def _get_prompt_body_indent(prompt: str) -> Optional[int]:
    """Return the expected body indentation level (in spaces) from a prompt.

    Walks backwards through the prompt lines to find the indentation of the
    last non-empty, indented line (typically the closing ``\"\"\"`` of a
    docstring or the last statement in the function header).  Returns *None*
    if no indented content is found.
    """
    for line in reversed(prompt.split("\n")):
        stripped = line.lstrip()
        if stripped and stripped != line:  # non-empty and indented
            return len(line) - len(stripped)
    return None


def _get_first_line_indent(text: str) -> Optional[int]:
    """Return the indentation of the first non-empty line in *text*."""
    for line in text.split("\n"):
        stripped = line.lstrip()
        if stripped:
            return len(line) - len(stripped)
    return None


def fix_completion_indent(prompt: str, completion: str) -> str:
    """Adjust the first line of *completion* so its indentation matches the prompt.

    BPE tokenisers frequently decode the first completion token with one
    fewer (or more) leading space than the prompt body expects.  Subsequent
    lines are almost always correctly indented because the model copies the
    indent pattern from its own earlier output.

    This helper therefore only touches the **first non-empty line**: it
    shifts it to match the expected indent derived from the prompt, leaving
    all other lines untouched.
    """
    if not completion or not completion.strip():
        return completion

    expected = _get_prompt_body_indent(prompt)
    actual = _get_first_line_indent(completion)

    if expected is None or actual is None or expected == actual:
        return completion

    lines = completion.split("\n")
    for idx, line in enumerate(lines):
        if line.strip():
            # Fix only this first non-empty line
            lines[idx] = " " * expected + line.lstrip()
            break
    return "\n".join(lines)


# =========================================================================
# Value Reranker — deterministic proxy verifier
# =========================================================================


class ValueReranker:
    """Deterministic proxy verifier for candidate reranking.

    Scores each candidate using cheap structural checks (AST parse,
    function presence, return statement, placeholder detection) and
    combines the utility estimate with the base logprob::

        S(y) = log p_theta(y|x) + alpha * logit(V(x,y))

    No training, no external models, no torch tensors.
    """

    def __init__(self, alpha: float = 1.0, use_ast: bool = True):
        self.alpha = alpha
        self.use_ast = use_ast

    # --- Utility estimation ------------------------------------------------

    def estimate_utility(self, prompt: str, candidate: str) -> float:
        """Return utility score in [0, 1].

        0.5 = neutral baseline.
        >0.5 = signs of correctness.
        <0.5 = obvious structural failure.
        """
        # Extract just the function body from the candidate.  Model output
        # often extends beyond the function (test code, markdown, extra
        # definitions) and 128-token truncation can leave partial statements.
        # Both cause false AST failures.
        body = self._extract_function_body(candidate)
        full_code = prompt + body
        adj = 0.0

        # (A) Syntax validity (AST) — bonus, not a gate.
        # Many valid completions fail full AST due to trailing text or
        # truncation.  A syntax error is a mild penalty; other structural
        # signals still differentiate candidates.
        if self.use_ast:
            try:
                ast.parse(full_code)
                adj += 0.20
            except SyntaxError:
                adj -= 0.15

        # Extract expected function name from prompt
        expected_fn = self._extract_function_name(prompt)

        # (B) Required function presence
        if expected_fn:
            if self._defines_function(body, expected_fn):
                adj += 0.15
            else:
                adj -= 0.25

        # (C) Return statement check
        if expected_fn and self._likely_needs_return(prompt):
            if not self._has_return(body):
                adj -= 0.15

        # (D) Placeholder / incomplete code penalty
        if self._has_placeholder(body):
            adj -= 0.25

        # (E) Structural completeness bonus
        if len(body.strip()) > 20 and adj >= 0.0:
            adj += 0.05

        # (F) Parameter usage — does candidate use the function's arguments?
        param_names = self._extract_param_names(prompt)
        if param_names:
            used = sum(1 for p in param_names if p in body)
            if used == 0:
                adj -= 0.10  # suspicious: ignores all parameters
            elif used == len(param_names):
                adj += 0.05  # uses all parameters

        return float(np.clip(0.5 + adj, 0.0, 1.0))

    # --- Scoring -----------------------------------------------------------

    def score_candidate(
        self, prompt: str, candidate: str, base_logprob: float,
    ) -> float:
        """Compute combined score: logprob + alpha * logit(utility)."""
        utility = self.estimate_utility(prompt, candidate)
        # Clamp to (0.01, 0.99) to avoid log(0) domain errors
        utility = max(0.01, min(0.99, utility))
        utility_logit = math.log(utility / (1.0 - utility))
        return base_logprob + self.alpha * utility_logit

    # --- Internal helpers --------------------------------------------------

    @staticmethod
    def _extract_function_body(candidate: str) -> str:
        """Extract just the function body from a candidate continuation.

        Model-generated candidates often extend beyond the target function
        (test code, markdown explanations, additional definitions) and
        128-token max generation can truncate mid-statement.  Both cause
        false ``ast.parse()`` failures.

        This extracts body lines by stopping at the first non-blank,
        non-indented line that follows at least one body line — which
        marks the start of content outside the function.
        """
        lines = candidate.split("\n")
        body_lines: List[str] = []
        seen_content = False

        for line in lines:
            # Blank lines are always included
            if not line.strip():
                body_lines.append(line)
                continue
            # Once we've seen body content, a line at column 0 that looks
            # like a new definition, comment, or statement means the
            # function body is over.
            if seen_content and line and not line[0].isspace():
                break
            body_lines.append(line)
            seen_content = True

        # Strip trailing blank lines
        while body_lines and not body_lines[-1].strip():
            body_lines.pop()

        return "\n".join(body_lines)

    @staticmethod
    def _extract_function_name(prompt: str) -> Optional[str]:
        """Extract function name from HumanEval-style prompt."""
        match = re.search(r"def\s+(\w+)\s*\(", prompt)
        return match.group(1) if match else None

    @staticmethod
    def _defines_function(candidate: str, name: str) -> bool:
        """Check if candidate re-defines or continues the named function."""
        # The candidate is a continuation — it may not re-define the
        # function.  Accept if it has a return/yield or substantive body
        # lines (meaning it's filling in the function body).
        stripped = candidate.strip()
        if not stripped:
            return False
        # If candidate itself contains `def name(`, it re-defines
        if re.search(rf"def\s+{re.escape(name)}\s*\(", candidate):
            return True
        # Otherwise accept if it looks like function body content
        # (indented code, return statements, assignments, etc.)
        lines = [l for l in candidate.split("\n") if l.strip()]
        if lines:
            return True
        return False

    @staticmethod
    def _likely_needs_return(prompt: str) -> bool:
        """Heuristic: does this problem likely expect a return value?"""
        # Check docstring for "return" / "returns" / "->"
        lower = prompt.lower()
        if "-> none" in lower or "print(" in lower:
            return False
        if "->" in prompt or "return" in lower or "returns" in lower:
            return True
        return True  # default: most HumanEval problems expect a return

    @staticmethod
    def _has_return(candidate: str) -> bool:
        """Check if candidate has a return or yield statement."""
        for line in candidate.split("\n"):
            stripped = line.strip()
            if stripped.startswith("return ") or stripped == "return":
                return True
            if stripped.startswith("yield "):
                return True
        return False

    @staticmethod
    def _extract_param_names(prompt: str) -> List[str]:
        """Extract parameter names from the function signature in prompt."""
        match = re.search(r"def\s+\w+\s*\(([^)]*)\)", prompt)
        if not match:
            return []
        params_str = match.group(1)
        names: List[str] = []
        for part in params_str.split(","):
            part = part.strip()
            if not part or part == "self":
                continue
            # Strip type annotations and defaults
            name = part.split(":")[0].split("=")[0].strip()
            if name:
                names.append(name)
        return names

    @staticmethod
    def _has_placeholder(candidate: str) -> bool:
        """Detect placeholder/incomplete code patterns."""
        stripped = candidate.strip()
        # Check for common placeholder patterns
        if stripped == "pass" or stripped.endswith("\n    pass"):
            return True
        for pattern in ("TODO", "raise NotImplementedError", "..."):
            if pattern in candidate:
                # Don't flag "..." inside strings
                if pattern == "...":
                    # Only flag if it appears as a statement, not in a string
                    for line in candidate.split("\n"):
                        ls = line.strip()
                        if ls == "..." or ls == "Ellipsis":
                            return True
                else:
                    return True
        return False


# =========================================================================
# Learned Value Reranker — MLP on hidden states
# =========================================================================


class PCATransform:
    """Lightweight PCA via torch SVD — no sklearn dependency.

    Fits on training hidden states and transforms to ``n_components``
    dimensions.  All tensors stored on CPU in float32.
    """

    def __init__(self, n_components: int = 32):
        self.n_components = n_components
        self.mean_: Optional["torch.Tensor"] = None       # [D]
        self.components_: Optional["torch.Tensor"] = None  # [n_comp, D]
        self.explained_var_ratio_: Optional[float] = None

    def fit(self, X: "torch.Tensor") -> "PCATransform":
        """Fit PCA on X of shape [N, D] (CPU float32)."""
        X = X.float().cpu()
        self.mean_ = X.mean(dim=0)
        X_c = X - self.mean_
        # Economy SVD — only need first n_components singular vectors
        _U, S, Vt = torch.linalg.svd(X_c, full_matrices=False)
        self.components_ = Vt[:self.n_components]  # [n_comp, D]
        total_var = (S ** 2).sum().item()
        kept_var = (S[:self.n_components] ** 2).sum().item()
        self.explained_var_ratio_ = kept_var / max(total_var, 1e-12)
        return self

    def transform(self, X: "torch.Tensor") -> "torch.Tensor":
        """Project X [N, D] -> [N, n_components]."""
        assert self.mean_ is not None, "PCA not fitted"
        X = X.float().cpu()
        return (X - self.mean_) @ self.components_.T  # [N, n_comp]

    def fit_transform(self, X: "torch.Tensor") -> "torch.Tensor":
        self.fit(X)
        return self.transform(X)


@dataclass
class CandidateSample:
    """One collected sample for learned reranker training.

    Stores the pooled hidden state (on CPU), base logprob, candidate
    length, and pass/fail label.  Prompt/candidate text kept for
    diagnostics only.
    """

    pooled_hidden: "torch.Tensor"  # [D] float32, CPU
    base_logprob: float
    candidate_length: int
    passed: bool
    prompt_text: str = ""
    candidate_text: str = ""


if PYTORCH_AVAILABLE:

    class LearnedValueReranker(nn.Module):
        """MLP that predicts P(pass | features).

        Supports two feature modes controlled by ``hidden_only``:

        * ``hidden_only=False`` (legacy):
          features = [pooled_hidden (D'), base_logprob (1), length (1)]
        * ``hidden_only=True`` (recommended):
          features = [pooled_hidden (D')]
          This forces the MLP to learn signal orthogonal to logprob.

        When ``pca`` is set, pooled_hidden is projected from the raw
        hidden dimension D to D' = pca.n_components before being fed
        to the network.

        Scoring formula::

            S(y) = base_logprob + alpha * mlp_logit(features)

        Architecture: 2 hidden layers with GELU activation.
        """

        def __init__(self, input_dim: int, hidden_dim: int = 256):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(input_dim, hidden_dim),
                nn.GELU(),
                nn.Linear(hidden_dim, hidden_dim // 2),
                nn.GELU(),
                nn.Linear(hidden_dim // 2, 1),
            )
            self.input_dim = input_dim
            # Set after training via train_learned_reranker()
            self.pca: Optional[PCATransform] = None
            self.hidden_only: bool = False

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            """Return raw logits, shape [B]."""
            return self.net(x).squeeze(-1)

        def predict_proba(self, x: "torch.Tensor") -> "torch.Tensor":
            """Return P(pass) in [0, 1], shape [B]."""
            return torch.sigmoid(self.forward(x))

        def _build_features(
            self,
            pooled_hiddens: "torch.Tensor",
            base_logprobs: np.ndarray,
            candidate_lengths: List[int],
        ) -> "torch.Tensor":
            """Build feature tensor, applying PCA and hidden_only as needed."""
            device = next(self.parameters()).device

            # Apply PCA if configured
            h = pooled_hiddens
            if self.pca is not None:
                h = self.pca.transform(h)  # [K, pca_dim], CPU
            h = h.to(device)

            if self.hidden_only:
                return h  # [K, D']

            lp = torch.tensor(
                base_logprobs, dtype=torch.float32, device=device,
            ).unsqueeze(1)
            lens = torch.tensor(
                candidate_lengths, dtype=torch.float32, device=device,
            ).unsqueeze(1)
            return torch.cat([h, lp, lens], dim=1)  # [K, D'+2]

        def score_candidates(
            self,
            pooled_hiddens: "torch.Tensor",
            base_logprobs: np.ndarray,
            candidate_lengths: List[int],
            alpha: float = 1.0,
        ) -> np.ndarray:
            """Score K candidates: base_logprob + alpha * mlp_logit.

            Applies PCA and hidden_only settings automatically.

            Args:
                pooled_hiddens: [K, D] raw pooled hidden states.
                base_logprobs: [K] base logprob scores.
                candidate_lengths: List of K candidate lengths.
                alpha: Weight for MLP logit.

            Returns:
                scores: [K] combined scores as numpy array.
            """
            features = self._build_features(
                pooled_hiddens, base_logprobs, candidate_lengths,
            )

            with torch.no_grad():
                logits = self.forward(features)  # [K]

            return base_logprobs + alpha * logits.cpu().numpy()

    def _build_feature_tensor(
        samples: List[CandidateSample],
        device: str = "cpu",
        pca: Optional[PCATransform] = None,
        hidden_only: bool = False,
    ) -> Tuple["torch.Tensor", "torch.Tensor", "torch.Tensor"]:
        """Build (features, labels, logprobs) tensors from collected samples.

        Args:
            samples: Collected candidate samples.
            device: Target torch device.
            pca: If set, project hidden states through PCA first.
            hidden_only: If True, exclude logprob/length from features.

        Returns:
            features: [N, F] tensor.
            labels: [N] tensor of 0.0/1.0.
            logprobs: [N] tensor of base logprobs (for diagnostics).
        """
        hiddens = torch.stack([s.pooled_hidden for s in samples])  # [N, D]
        if pca is not None:
            hiddens = pca.transform(hiddens)  # [N, pca_dim]

        lps = torch.tensor(
            [s.base_logprob for s in samples],
            dtype=torch.float32,
        )  # [N]

        labels = torch.tensor(
            [1.0 if s.passed else 0.0 for s in samples],
            dtype=torch.float32,
        ).to(device)

        if hidden_only:
            features = hiddens.to(device)
        else:
            lens = torch.tensor(
                [s.candidate_length for s in samples],
                dtype=torch.float32,
            ).unsqueeze(1)  # [N, 1]
            features = torch.cat(
                [hiddens, lps.unsqueeze(1), lens], dim=1,
            ).to(device)

        return features, labels, lps.to(device)


# =========================================================================
# Candidate Generation
# =========================================================================


@torch.no_grad()
def generate_candidates(
    model: Any,
    tokenizer: Any,
    prompt: str,
    K: int = 8,
    max_new_tokens: int = 128,
    temperature: float = 0.8,
    top_p: float = 0.95,
    do_sample: bool = True,
) -> Tuple["torch.Tensor", List["torch.Tensor"], List[str]]:
    """
    Generate K candidate continuations from a prompt using sampling.

    Args:
        model: HuggingFace causal LM.
        tokenizer: Corresponding tokenizer.
        prompt: Prompt string.
        K: Number of candidate continuations.
        max_new_tokens: Maximum tokens to generate per candidate.
        temperature: Sampling temperature.
        top_p: Nucleus sampling threshold.
        do_sample: Whether to sample (True) or use greedy (False).

    Returns:
        prompt_ids: Prompt token ids, shape [P].
        candidate_ids_list: List of K continuation tensors, each [T_k].
        candidate_texts: List of K decoded strings.
    """
    if not PYTORCH_AVAILABLE:
        raise ImportError("PyTorch is required")

    device = next(model.parameters()).device

    input_ids = tokenizer.encode(prompt, return_tensors="pt").to(device)
    P = input_ids.shape[1]

    # Generate K candidates
    gen_kwargs: Dict[str, Any] = {
        "max_new_tokens": max_new_tokens,
        "num_return_sequences": K,
        "do_sample": do_sample,
        "temperature": temperature,
        "top_p": top_p,
    }

    # Set pad_token_id on model's generation config to suppress warnings
    if tokenizer.pad_token_id is not None:
        gen_kwargs["pad_token_id"] = tokenizer.pad_token_id
    else:
        gen_kwargs["pad_token_id"] = tokenizer.eos_token_id
    if hasattr(model, "generation_config"):
        model.generation_config.pad_token_id = gen_kwargs["pad_token_id"]

    # Create attention mask (all 1s for the prompt tokens)
    attention_mask = torch.ones_like(input_ids)

    outputs = model.generate(
        input_ids, attention_mask=attention_mask, **gen_kwargs
    )  # [K, P+T]

    prompt_ids = input_ids[0]  # [P]
    candidate_ids_list: List[torch.Tensor] = []
    candidate_texts: List[str] = []

    for k in range(K):
        cand_ids = outputs[k, P:]  # [T_k] (may include padding)
        # Trim trailing pad tokens
        if tokenizer.pad_token_id is not None:
            mask = cand_ids != tokenizer.pad_token_id
            if mask.any():
                last_real = mask.nonzero(as_tuple=True)[0][-1].item() + 1
                cand_ids = cand_ids[:last_real]
            else:
                cand_ids = cand_ids[:1]  # keep at least one token
        # Trim at EOS
        if tokenizer.eos_token_id is not None:
            eos_positions = (cand_ids == tokenizer.eos_token_id).nonzero(
                as_tuple=True
            )[0]
            if len(eos_positions) > 0:
                cand_ids = cand_ids[:eos_positions[0].item() + 1]

        candidate_ids_list.append(cand_ids)
        candidate_texts.append(
            tokenizer.decode(cand_ids, skip_special_tokens=True)
        )

    return prompt_ids, candidate_ids_list, candidate_texts


# =========================================================================
# Generate + Rerank Pipeline
# =========================================================================


@torch.no_grad()
def generate_and_rerank(
    model: Any,
    tokenizer: Any,
    prompt: str,
    goal_embedding: "torch.Tensor",
    bcvf_config: DecodingConfig,
    K: int = 8,
    rerank_lambda: float = 1.0,
    max_new_tokens: int = 128,
    temperature: float = 0.8,
    top_p: float = 0.95,
) -> Tuple[str, str, SeqRerankResult]:
    """
    Generate K candidates, rerank with BCVF, return best.

    Args:
        model: HuggingFace causal LM.
        tokenizer: Tokenizer.
        prompt: Prompt string.
        goal_embedding: [1, D] goal vector.
        bcvf_config: BCVF parameters.
        K: Number of candidates.
        rerank_lambda: BCVF mixing (0=base, 1=full).
        max_new_tokens: Max tokens per candidate.
        temperature: Sampling temperature.
        top_p: Nucleus sampling threshold.

    Returns:
        base_best_text: Text of the base-logprob-best candidate.
        bcvf_best_text: Text of the BCVF-reranked-best candidate.
        result: SeqRerankResult with full diagnostics.
    """
    # Generate candidates
    prompt_ids, candidate_ids_list, candidate_texts = generate_candidates(
        model, tokenizer, prompt, K=K,
        max_new_tokens=max_new_tokens,
        temperature=temperature, top_p=top_p,
    )

    # Rerank
    best_idx, scores, diag = rerank_candidates(
        prompt_ids, candidate_ids_list, model, goal_embedding,
        bcvf_config, rerank_lambda=rerank_lambda,
    )

    base_best_idx = diag["base_best_index"]

    # Aggregate per-candidate diagnostics into per-prompt means
    _safe_mean = lambda lst: float(np.mean(lst)) if lst else 0.0

    result = SeqRerankResult(
        K=K,
        rerank_lambda=rerank_lambda,
        base_best_idx=base_best_idx,
        base_best_score=float(diag["base_scores"][base_best_idx]),
        base_scores=diag["base_scores"],
        bcvf_best_idx=best_idx,
        bcvf_best_score=float(scores[best_idx]),
        bcvf_scores=scores,
        rerank_changed=diag["rerank_changed"],
        score_margin=diag["score_margin"],
        base_score_margin=diag["base_score_margin"],
        candidate_lengths=diag["candidate_lengths"],
        base_text=candidate_texts[base_best_idx],
        bcvf_text=candidate_texts[best_idx],
        # Signal diagnostics
        topM_hit_rate=_safe_mean(diag["per_candidate_topM_hit_rate"]),
        mean_sf=_safe_mean(diag["per_candidate_sf"]),
        mean_sb=_safe_mean(diag["per_candidate_sb"]),
        mean_sf_all=_safe_mean(diag["per_candidate_sf_all_mean"]),
        mean_sb_all=_safe_mean(diag["per_candidate_sb_all_mean"]),
        std_sf_all=_safe_mean(diag["per_candidate_sf_all_std"]),
        std_sb_all=_safe_mean(diag["per_candidate_sb_all_std"]),
        mean_L=_safe_mean(diag["per_candidate_L_mean"]),
        std_L=_safe_mean(diag["per_candidate_L_std"]),
        penalty_per_tok=_safe_mean(diag["per_candidate_penalty_per_tok"]),
        base_lp_per_tok=_safe_mean(diag["per_candidate_base_per_tok"]),
        score_std=diag["score_std"],
        base_score_std=diag["base_score_std"],
        rank_correlation=diag["rank_correlation"],
    )

    return candidate_texts[base_best_idx], candidate_texts[best_idx], result


# =========================================================================
# Learned Reranker — Data Collection & Training
# =========================================================================


@torch.no_grad()
def collect_learned_reranker_data(
    model: Any,
    tokenizer: Any,
    problems: Sequence[Dict[str, Any]],
    K: int = 8,
    max_new_tokens: int = 128,
    temperature: float = 0.8,
    top_p: float = 0.95,
    test_fn: Optional[Callable[[str, str, str], bool]] = None,
) -> List["CandidateSample"]:
    """Collect (hidden_state, logprob, length, pass/fail) for training.

    For each problem, generates K candidates, runs a forward pass with
    hidden state extraction, evaluates pass/fail, and stores one
    ``CandidateSample`` per candidate.

    Args:
        model: HuggingFace causal LM.
        tokenizer: Tokenizer.
        problems: HumanEval-style problem dicts.
        K: Candidates per problem.
        max_new_tokens: Max tokens per candidate.
        temperature: Sampling temperature.
        top_p: Nucleus sampling threshold.
        test_fn: Unit-test runner.  Defaults to ``run_unit_tests``.

    Returns:
        List of CandidateSample (one per candidate across all problems).
    """
    if test_fn is None:
        from symbolu_core.ontological.bcvf_experiments import run_unit_tests
        test_fn = run_unit_tests

    samples: List[CandidateSample] = []
    n_pass = 0
    n_total = 0

    for i, prob in enumerate(problems):
        prompt = prob["prompt"]
        test_code = prob.get("test", "")
        entry_point = prob.get("entry_point", "")

        # Generate K candidates
        prompt_ids, candidate_ids_list, candidate_texts = generate_candidates(
            model, tokenizer, prompt, K=K,
            max_new_tokens=max_new_tokens,
            temperature=temperature, top_p=top_p,
        )
        if not candidate_ids_list:
            continue

        # Forward pass WITH hidden states
        _, logprob_scores, diag = logprob_rerank_candidates(
            prompt_ids, candidate_ids_list, model,
            return_hidden_states=True,
        )
        pooled_hiddens = diag["pooled_hiddens"]  # [K, D], CPU
        cand_lengths = diag["candidate_lengths"]

        # Evaluate pass/fail for each candidate
        for k in range(len(candidate_texts)):
            code = prompt + fix_completion_indent(prompt, candidate_texts[k])
            passed = test_fn(code, test_code, entry_point)
            samples.append(CandidateSample(
                pooled_hidden=pooled_hiddens[k],
                base_logprob=float(logprob_scores[k]),
                candidate_length=cand_lengths[k],
                passed=passed,
                prompt_text=prompt,
                candidate_text=candidate_texts[k],
            ))
            n_total += 1
            if passed:
                n_pass += 1

        if (i + 1) % 10 == 0 or i == 0:
            rate = n_pass / n_total if n_total > 0 else 0.0
            print(
                f"  [collect] {i+1}/{len(problems)}  "
                f"samples={n_total}  pass_rate={rate:.3f}"
            )

    print(
        f"  [collect] Done: {n_total} samples, "
        f"{n_pass} passed ({n_pass/n_total:.3f})"
        if n_total > 0 else "  [collect] No samples collected"
    )
    return samples


def _spearman_rho(x: np.ndarray, y: np.ndarray) -> float:
    """Manual Spearman rank correlation (no scipy)."""
    n = len(x)
    if n < 3:
        return 0.0
    rx = np.argsort(np.argsort(x)).astype(float)
    ry = np.argsort(np.argsort(y)).astype(float)
    d = rx - ry
    return 1.0 - 6.0 * float(np.sum(d ** 2)) / (n * (n ** 2 - 1))


def train_learned_reranker(
    samples: List["CandidateSample"],
    hidden_dim: int = 256,
    epochs: int = 10,
    lr: float = 1e-3,
    batch_size: int = 64,
    train_ratio: float = 0.8,
    seed: int = 42,
    device: str = "cpu",
    pca_dim: int = 0,
    hidden_only: bool = False,
) -> Tuple["LearnedValueReranker", Dict[str, Any]]:
    """Train a LearnedValueReranker MLP on collected candidate samples.

    Args:
        samples: List of CandidateSample from ``collect_learned_reranker_data``.
        hidden_dim: MLP hidden dimension.
        epochs: Training epochs.
        lr: Learning rate.
        batch_size: Mini-batch size.
        train_ratio: Fraction for training (rest for eval).
        seed: Random seed.
        device: Torch device.
        pca_dim: If > 0, reduce hidden states from D to pca_dim via PCA
            before training.  This addresses the p >> n problem when
            D (e.g. 3072) vastly exceeds N (e.g. 400).
        hidden_only: If True, exclude logprob and length from MLP input,
            forcing the network to learn signal orthogonal to base logprob.

    Returns:
        (model, metrics) where metrics contains train/eval loss, accuracy,
        and the critical rho-inequality diagnostic.
    """
    if not PYTORCH_AVAILABLE:
        raise ImportError("PyTorch is required")

    torch.manual_seed(seed)
    np.random.seed(seed)

    # ---- PCA: fit on raw hidden states before building features ----
    pca_obj: Optional[PCATransform] = None
    if pca_dim > 0:
        raw_hiddens = torch.stack([s.pooled_hidden for s in samples])
        raw_D = raw_hiddens.shape[1]
        effective_pca_dim = min(pca_dim, raw_D, len(samples))
        pca_obj = PCATransform(n_components=effective_pca_dim)
        pca_obj.fit(raw_hiddens)
        print(
            f"  [train] PCA: {raw_D} -> {effective_pca_dim}  "
            f"explained_var={pca_obj.explained_var_ratio_:.3f}"
        )

    # Build feature/label tensors (with PCA and hidden_only applied)
    features, labels, logprobs = _build_feature_tensor(
        samples, device=device, pca=pca_obj, hidden_only=hidden_only,
    )
    input_dim = features.shape[1]
    N = features.shape[0]

    # Shuffle and split
    perm = torch.randperm(N)
    features = features[perm]
    labels = labels[perm]
    logprobs = logprobs[perm]
    n_train = int(N * train_ratio)
    X_train, X_eval = features[:n_train], features[n_train:]
    y_train, y_eval = labels[:n_train], labels[n_train:]
    lp_train, lp_eval = logprobs[:n_train], logprobs[n_train:]

    n_pos_train = int(y_train.sum().item())
    n_pos_eval = int(y_eval.sum().item())
    mode_label = "hidden_only" if hidden_only else "hidden+lp+len"
    print(
        f"  [train] N={N}  train={n_train} (pos={n_pos_train})  "
        f"eval={N - n_train} (pos={n_pos_eval})  input_dim={input_dim}  "
        f"mode={mode_label}"
    )

    # Initialize model
    mlp = LearnedValueReranker(input_dim=input_dim, hidden_dim=hidden_dim)
    mlp.pca = pca_obj
    mlp.hidden_only = hidden_only
    mlp = mlp.to(device)
    optimizer = torch.optim.Adam(mlp.parameters(), lr=lr, weight_decay=1e-5)
    loss_fn = nn.BCEWithLogitsLoss()

    # Training loop
    best_eval_acc = 0.0
    best_state = None

    for epoch in range(epochs):
        mlp.train()
        epoch_loss = 0.0
        n_batches = 0

        # Shuffle training data each epoch
        perm_epoch = torch.randperm(n_train)
        X_shuf = X_train[perm_epoch]
        y_shuf = y_train[perm_epoch]

        for start in range(0, n_train, batch_size):
            end = min(start + batch_size, n_train)
            xb = X_shuf[start:end]
            yb = y_shuf[start:end]

            logits = mlp(xb)
            loss = loss_fn(logits, yb)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            epoch_loss += loss.item()
            n_batches += 1

        avg_loss = epoch_loss / max(n_batches, 1)

        # Evaluate
        mlp.eval()
        with torch.no_grad():
            eval_logits = mlp(X_eval)
            eval_loss = loss_fn(eval_logits, y_eval).item()
            eval_preds = (eval_logits > 0).float()
            eval_acc = float((eval_preds == y_eval).float().mean().item())

            train_logits = mlp(X_train)
            train_preds = (train_logits > 0).float()
            train_acc = float((train_preds == y_train).float().mean().item())

        if eval_acc >= best_eval_acc:
            best_eval_acc = eval_acc
            best_state = {k: v.cpu().clone() for k, v in mlp.state_dict().items()}

        if (epoch + 1) % max(1, epochs // 5) == 0 or epoch == 0:
            print(
                f"  [train] epoch {epoch+1}/{epochs}  "
                f"train_loss={avg_loss:.4f}  train_acc={train_acc:.3f}  "
                f"eval_loss={eval_loss:.4f}  eval_acc={eval_acc:.3f}"
            )

    # Load best checkpoint
    if best_state is not None:
        mlp.load_state_dict(best_state)
        mlp = mlp.to(device)

    # Final metrics
    mlp.eval()
    with torch.no_grad():
        final_eval_logits = mlp(X_eval)
        final_eval_preds = (final_eval_logits > 0).float()
        final_eval_acc = float(
            (final_eval_preds == y_eval).float().mean().item()
        )
        final_train_logits = mlp(X_train)
        final_train_preds = (final_train_logits > 0).float()
        final_train_acc = float(
            (final_train_preds == y_train).float().mean().item()
        )

    # ================================================================
    # Rho-inequality diagnostic:
    #   ρ(V(x,y), correctness) vs ρ(logprob, correctness)
    #
    # The MLP can only help if its signal is MORE correlated with
    # correctness than logprob already is.  If not, the reranker
    # adds nothing — S(y) = logprob + alpha*V preserves the base
    # ranking.
    # ================================================================
    with torch.no_grad():
        all_logits = mlp(features)  # [N]
    v_np = all_logits.cpu().numpy()
    lp_np = logprobs.cpu().numpy()
    y_np = labels.cpu().numpy()

    rho_v_corr = _spearman_rho(v_np, y_np)
    rho_lp_corr = _spearman_rho(lp_np, y_np)
    rho_gap = rho_v_corr - rho_lp_corr

    # Also compute on eval split only (out-of-sample)
    with torch.no_grad():
        eval_v = mlp(X_eval).cpu().numpy()
    eval_lp = lp_eval.cpu().numpy()
    eval_y = y_eval.cpu().numpy()

    rho_v_eval = _spearman_rho(eval_v, eval_y)
    rho_lp_eval = _spearman_rho(eval_lp, eval_y)
    rho_gap_eval = rho_v_eval - rho_lp_eval

    print(
        f"  [train] Final: train_acc={final_train_acc:.3f}  "
        f"eval_acc={final_eval_acc:.3f}  best_eval_acc={best_eval_acc:.3f}"
    )
    print(f"  [rho-inequality] Critical diagnostic — "
          f"does MLP beat logprob at predicting correctness?")
    print(f"    All data:  ρ(V,corr)={rho_v_corr:+.4f}  "
          f"ρ(logprob,corr)={rho_lp_corr:+.4f}  "
          f"gap={rho_gap:+.4f}"
          f"{'  << MLP WINS' if rho_gap > 0.05 else ''}"
          f"{'  << LOGPROB WINS — MLP not helping' if rho_gap < -0.02 else ''}"
          f"{'  << ~TIED — MLP is redundant' if -0.02 <= rho_gap <= 0.05 else ''}")
    print(f"    Eval only: ρ(V,corr)={rho_v_eval:+.4f}  "
          f"ρ(logprob,corr)={rho_lp_eval:+.4f}  "
          f"gap={rho_gap_eval:+.4f}"
          f"{'  << MLP WINS' if rho_gap_eval > 0.05 else ''}"
          f"{'  << LOGPROB WINS — MLP not helping' if rho_gap_eval < -0.02 else ''}"
          f"{'  << ~TIED — MLP is redundant' if -0.02 <= rho_gap_eval <= 0.05 else ''}")

    metrics = {
        "n_samples": N,
        "n_train": n_train,
        "n_eval": N - n_train,
        "input_dim": input_dim,
        "hidden_dim": hidden_dim,
        "epochs": epochs,
        "train_acc": final_train_acc,
        "eval_acc": final_eval_acc,
        "best_eval_acc": best_eval_acc,
        "train_pos_rate": n_pos_train / max(n_train, 1),
        "eval_pos_rate": n_pos_eval / max(N - n_train, 1),
        "pca_dim": pca_dim,
        "pca_explained_var": (
            pca_obj.explained_var_ratio_ if pca_obj else None
        ),
        "hidden_only": hidden_only,
        "rho_v_correctness": rho_v_corr,
        "rho_logprob_correctness": rho_lp_corr,
        "rho_gap": rho_gap,
        "rho_v_correctness_eval": rho_v_eval,
        "rho_logprob_correctness_eval": rho_lp_eval,
        "rho_gap_eval": rho_gap_eval,
    }
    return mlp, metrics


# =========================================================================
# Goal Embedding Helpers
# =========================================================================


@torch.no_grad()
def compute_prompt_goal_embedding(
    model: Any,
    tokenizer: Any,
    prompt: str,
    strategy: str = "prompt_mean",
    max_seq_len: int = 512,
) -> "torch.Tensor":
    """
    Compute a goal embedding from the prompt for sequence-level reranking.

    Args:
        model: HuggingFace causal LM.
        tokenizer: Tokenizer.
        prompt: Prompt string.
        strategy: "prompt_mean" (mean-pool prompt hidden states) or
                  "last_hidden" (use last hidden state).
        max_seq_len: Max tokens for prompt.

    Returns:
        goal: [1, D] goal embedding tensor.
    """
    device = next(model.parameters()).device
    tokens = tokenizer.encode(
        prompt, return_tensors="pt", truncation=True,
        max_length=max_seq_len,
    ).to(device)

    outputs = model(tokens, output_hidden_states=True, use_cache=False)
    hidden = outputs.hidden_states[-1]  # [1, T, D]

    if strategy == "prompt_mean":
        goal = hidden[0].mean(dim=0, keepdim=True)  # [1, D]
    elif strategy == "last_hidden":
        goal = hidden[0, -1:, :]  # [1, D]
    else:
        goal = hidden[0].mean(dim=0, keepdim=True)

    return goal.float()


# =========================================================================
# HumanEval Benchmark with Sequence Reranking
# =========================================================================


def run_seq_rerank_benchmark_humaneval(
    model: Any,
    tokenizer: Any,
    problems: Sequence[Dict[str, Any]],
    bcvf_config: DecodingConfig,
    K: int = 8,
    rerank_lambda: float = 1.0,
    max_new_tokens: int = 256,
    temperature: float = 0.8,
    top_p: float = 0.95,
    n_bootstrap: int = 1000,
    test_fn: Optional[Callable[[str, str, str], bool]] = None,
    rerank_mode: str = "bcvf",
    value_alpha: float = 1.0,
    value_use_ast: bool = True,
    learned_reranker: Optional[Any] = None,
    learned_alpha: float = 1.0,
) -> SeqRerankReport:
    """
    Run sequence-level reranking benchmark on HumanEval problems.

    Supports five reranking modes:

    ``bcvf``
        Original BCVF-adjusted logits (Equation B).  Selects the candidate
        with the highest BCVF-adjusted sequence logprob.

    ``logprob``
        Pure logprob reranking — no BCVF, no goal embedding.  Generates K
        candidates with sampling, picks the one the model assigns highest
        probability to.  This is the honest baseline that answers: "does
        sampling K and picking by logprob already beat greedy (K=1)?"

    ``oracle_verifier``
        Tests *all* K candidates against unit tests.  Picks the first
        passing candidate (tie-broken by logprob if multiple pass).
        Falls back to best-logprob if none pass.  This gives the ceiling:
        "how good can reranking possibly be with a perfect verifier?"

    ``value``
        Deterministic proxy verifier.  Scores each candidate using
        S(y) = logprob + alpha * logit(V(x,y)) where V is a cheap
        structural utility estimate (AST, function presence, etc.).

    ``learned_value``
        Learned MLP reranker.  Scores each candidate using
        S(y) = logprob + alpha * MLP_logit(pooled_hidden, logprob, length).
        Requires a trained ``LearnedValueReranker`` instance.

    Args:
        model: HuggingFace causal LM.
        tokenizer: Tokenizer.
        problems: List of problem dicts with 'prompt', 'test', 'entry_point'.
        bcvf_config: BCVF parameters.
        K: Number of candidates per problem.
        rerank_lambda: BCVF mixing parameter (only used in bcvf mode).
        max_new_tokens: Max tokens per candidate.
        temperature: Sampling temperature.
        top_p: Nucleus sampling threshold.
        n_bootstrap: Bootstrap resamples for CIs.
        test_fn: Function(code, test_code, entry_point) -> bool.
                 Defaults to run_unit_tests from bcvf_experiments.
        rerank_mode: "bcvf", "logprob", "oracle_verifier", "value",
                     or "learned_value".
        value_alpha: Weight for utility logit (value mode only).
        value_use_ast: Whether to use AST parsing (value mode only).
        learned_reranker: Trained LearnedValueReranker (learned_value only).
        learned_alpha: Weight for MLP logit (learned_value mode only).

    Returns:
        SeqRerankReport with all metrics.
    """
    if rerank_mode not in RERANK_MODES:
        raise ValueError(
            f"Unknown rerank_mode={rerank_mode!r}. "
            f"Valid modes: {RERANK_MODES}"
        )

    if test_fn is None:
        from symbolu_core.ontological.bcvf_experiments import run_unit_tests
        test_fn = run_unit_tests

    t0 = time.time()
    per_prompt: List[SeqRerankResult] = []
    mode_label = f"seq-rerank-humaneval-{rerank_mode}"

    for i, prob in enumerate(problems):
        prompt = prob["prompt"]
        test_code = prob.get("test", "")
        entry_point = prob.get("entry_point", "")
        task_id = prob.get("task_id", f"problem_{i}")

        # Generate K candidates (shared across all modes)
        prompt_ids, candidate_ids_list, candidate_texts = generate_candidates(
            model, tokenizer, prompt, K=K,
            max_new_tokens=max_new_tokens,
            temperature=temperature, top_p=top_p,
        )

        if not candidate_ids_list:
            continue

        # --- Compute base logprob scores (needed by all modes) ---
        logprob_best_idx, logprob_scores, logprob_diag = \
            logprob_rerank_candidates(
                prompt_ids, candidate_ids_list, model,
            )

        if rerank_mode == "logprob":
            # --- Logprob mode: pick best by base logprob ---
            selected_idx = logprob_best_idx
            result = SeqRerankResult(
                prompt_id=task_id,
                K=K,
                rerank_lambda=0.0,
                rerank_mode="logprob",
                base_best_idx=logprob_best_idx,
                base_best_score=float(logprob_scores[logprob_best_idx]),
                base_scores=logprob_scores,
                bcvf_best_idx=logprob_best_idx,
                bcvf_best_score=float(logprob_scores[logprob_best_idx]),
                bcvf_scores=logprob_scores,
                rerank_changed=False,
                score_margin=logprob_diag["score_margin"],
                base_score_margin=logprob_diag["score_margin"],
                candidate_lengths=logprob_diag["candidate_lengths"],
                base_text=candidate_texts[logprob_best_idx],
                bcvf_text=candidate_texts[logprob_best_idx],
            )

        elif rerank_mode == "oracle_verifier":
            # --- Oracle mode: test ALL K candidates, pick first passer ---
            pass_results: List[bool] = []
            for k in range(K):
                code = prompt + fix_completion_indent(prompt, candidate_texts[k])
                passed = test_fn(code, test_code, entry_point)
                pass_results.append(passed)

            # Among passing candidates, pick by highest logprob
            passing_indices = [
                k for k, p in enumerate(pass_results) if p
            ]
            if passing_indices:
                # Tie-break by logprob
                best_passing = max(
                    passing_indices, key=lambda k: logprob_scores[k]
                )
                selected_idx = best_passing
            else:
                # No candidate passed; fall back to best logprob
                selected_idx = logprob_best_idx

            result = SeqRerankResult(
                prompt_id=task_id,
                K=K,
                rerank_lambda=0.0,
                rerank_mode="oracle_verifier",
                base_best_idx=logprob_best_idx,
                base_best_score=float(logprob_scores[logprob_best_idx]),
                base_scores=logprob_scores,
                bcvf_best_idx=selected_idx,
                bcvf_best_score=float(logprob_scores[selected_idx]),
                bcvf_scores=logprob_scores,
                rerank_changed=selected_idx != logprob_best_idx,
                score_margin=logprob_diag["score_margin"],
                base_score_margin=logprob_diag["score_margin"],
                candidate_lengths=logprob_diag["candidate_lengths"],
                base_text=candidate_texts[logprob_best_idx],
                bcvf_text=candidate_texts[selected_idx],
            )
            # Set pass/fail: oracle selected candidate and base
            result.bcvf_passed = bool(pass_results[selected_idx])
            result.base_passed = bool(pass_results[logprob_best_idx])
            result.any_passed = any(pass_results)

            per_prompt.append(result)

            if (i + 1) % 5 == 0 or i == 0:
                n_pass = sum(pass_results)
                print(
                    f"  [{mode_label}] {i+1}/{len(problems)} "
                    f"oracle={'PASS' if result.bcvf_passed else 'FAIL'} "
                    f"logprob={'PASS' if result.base_passed else 'FAIL'} "
                    f"K_passed={n_pass}/{K} "
                    f"changed={result.rerank_changed}"
                )
            continue  # skip the common tail below

        elif rerank_mode == "value":
            # --- Value mode: deterministic proxy verifier ---
            reranker = ValueReranker(
                alpha=value_alpha, use_ast=value_use_ast,
            )
            # Fix indentation before structural analysis (same BPE
            # issue as value_feature mode)
            fixed_texts = [
                fix_completion_indent(prompt, ct)
                for ct in candidate_texts
            ]
            # Score each candidate: logprob + alpha * logit(utility)
            value_scores = np.array([
                reranker.score_candidate(
                    prompt, fixed_texts[k], float(logprob_scores[k]),
                )
                for k in range(len(fixed_texts))
            ])
            utilities = np.array([
                reranker.estimate_utility(prompt, fixed_texts[k])
                for k in range(len(fixed_texts))
            ])
            selected_idx = int(np.argmax(value_scores))

            # Score margin (value-best minus value-second-best)
            sorted_scores = np.sort(value_scores)[::-1]
            value_margin = (
                float(sorted_scores[0] - sorted_scores[1])
                if len(sorted_scores) > 1 else 0.0
            )
            # Rank correlation between base logprob and value scores
            # (manual Spearman, no scipy dependency)
            n_k = len(value_scores)
            if n_k > 2:
                base_ranks = np.argsort(np.argsort(logprob_scores)).astype(float)
                val_ranks = np.argsort(np.argsort(value_scores)).astype(float)
                d = base_ranks - val_ranks
                rank_corr = 1.0 - 6.0 * float(np.sum(d ** 2)) / (
                    float(n_k) * (float(n_k) ** 2 - 1)
                )
            elif n_k == 2:
                rank_corr = (
                    1.0 if np.argmax(logprob_scores) == np.argmax(value_scores)
                    else -1.0
                )
            else:
                rank_corr = 1.0

            # --- Evaluate pass/fail for base, value, and ALL K (oracle) ---
            base_code = prompt + fix_completion_indent(
                prompt, candidate_texts[logprob_best_idx],
            )
            selected_code = prompt + fix_completion_indent(
                prompt, candidate_texts[selected_idx],
            )
            base_passed = test_fn(base_code, test_code, entry_point)
            value_passed = test_fn(selected_code, test_code, entry_point)

            # Test ALL K candidates for true oracle ceiling
            oracle_any = base_passed or value_passed
            if not oracle_any:
                for k in range(len(candidate_texts)):
                    if k == logprob_best_idx or k == selected_idx:
                        continue  # already tested
                    code_k = prompt + fix_completion_indent(
                        prompt, candidate_texts[k],
                    )
                    if test_fn(code_k, test_code, entry_point):
                        oracle_any = True
                        break

            result = SeqRerankResult(
                prompt_id=task_id,
                K=K,
                rerank_lambda=0.0,
                rerank_mode="value",
                base_best_idx=logprob_best_idx,
                base_best_score=float(logprob_scores[logprob_best_idx]),
                base_scores=logprob_scores,
                bcvf_best_idx=selected_idx,
                bcvf_best_score=float(value_scores[selected_idx]),
                bcvf_scores=value_scores,
                rerank_changed=selected_idx != logprob_best_idx,
                score_margin=value_margin,
                base_score_margin=logprob_diag["score_margin"],
                candidate_lengths=logprob_diag["candidate_lengths"],
                base_text=candidate_texts[logprob_best_idx],
                bcvf_text=candidate_texts[selected_idx],
                # Reuse diagnostics fields for value-specific info
                mean_sf=float(np.mean(utilities)),  # repurpose: mean utility
                rank_correlation=rank_corr,
                score_std=float(np.std(value_scores)),
                base_score_std=float(np.std(logprob_scores)),
            )
            result.base_passed = base_passed
            result.bcvf_passed = value_passed
            result.any_passed = oracle_any

            per_prompt.append(result)

            if (i + 1) % 5 == 0 or i == 0:
                print(
                    f"  [{mode_label}] {i+1}/{len(problems)} "
                    f"base={'PASS' if base_passed else 'FAIL'} "
                    f"value={'PASS' if value_passed else 'FAIL'} "
                    f"changed={result.rerank_changed} "
                    f"util={float(np.mean(utilities)):.2f} "
                    f"base_lp={float(logprob_scores[logprob_best_idx]):.2f}"
                )
            continue  # skip common tail below

        elif rerank_mode == "learned_value":
            # --- Learned value mode: MLP on hidden states ---
            if learned_reranker is None:
                raise ValueError(
                    "learned_value mode requires a trained "
                    "LearnedValueReranker (learned_reranker= parameter)"
                )

            # Forward pass WITH hidden states
            _, logprob_scores_h, diag_h = logprob_rerank_candidates(
                prompt_ids, candidate_ids_list, model,
                return_hidden_states=True,
            )
            pooled_hiddens = diag_h["pooled_hiddens"]  # [K, D], CPU
            cand_lengths_h = diag_h["candidate_lengths"]

            # Score with MLP: base_logprob + alpha * mlp_logit
            learned_scores = learned_reranker.score_candidates(
                pooled_hiddens, logprob_scores, cand_lengths_h,
                alpha=learned_alpha,
            )
            selected_idx = int(np.argmax(learned_scores))

            # MLP predicted probabilities for diagnostics
            feat = learned_reranker._build_features(
                pooled_hiddens, logprob_scores, cand_lengths_h,
            )
            with torch.no_grad():
                mlp_probs = learned_reranker.predict_proba(feat).cpu().numpy()

            # Score margin
            sorted_lscores = np.sort(learned_scores)[::-1]
            learned_margin = (
                float(sorted_lscores[0] - sorted_lscores[1])
                if len(sorted_lscores) > 1 else 0.0
            )

            # Rank correlation (manual Spearman)
            n_k = len(learned_scores)
            if n_k > 2:
                base_ranks = np.argsort(np.argsort(logprob_scores)).astype(float)
                lr_ranks = np.argsort(np.argsort(learned_scores)).astype(float)
                d = base_ranks - lr_ranks
                rank_corr = 1.0 - 6.0 * float(np.sum(d ** 2)) / (
                    float(n_k) * (float(n_k) ** 2 - 1)
                )
            elif n_k == 2:
                rank_corr = (
                    1.0 if np.argmax(logprob_scores) == np.argmax(learned_scores)
                    else -1.0
                )
            else:
                rank_corr = 1.0

            # Evaluate pass/fail for base, learned, and ALL K (oracle)
            base_code = prompt + fix_completion_indent(
                prompt, candidate_texts[logprob_best_idx],
            )
            selected_code = prompt + fix_completion_indent(
                prompt, candidate_texts[selected_idx],
            )
            base_passed = test_fn(base_code, test_code, entry_point)
            learned_passed = test_fn(selected_code, test_code, entry_point)

            oracle_any = base_passed or learned_passed
            if not oracle_any:
                for k in range(len(candidate_texts)):
                    if k == logprob_best_idx or k == selected_idx:
                        continue
                    code_k = prompt + fix_completion_indent(
                        prompt, candidate_texts[k],
                    )
                    if test_fn(code_k, test_code, entry_point):
                        oracle_any = True
                        break

            result = SeqRerankResult(
                prompt_id=task_id,
                K=K,
                rerank_lambda=0.0,
                rerank_mode="learned_value",
                base_best_idx=logprob_best_idx,
                base_best_score=float(logprob_scores[logprob_best_idx]),
                base_scores=logprob_scores,
                bcvf_best_idx=selected_idx,
                bcvf_best_score=float(learned_scores[selected_idx]),
                bcvf_scores=learned_scores,
                rerank_changed=selected_idx != logprob_best_idx,
                score_margin=learned_margin,
                base_score_margin=logprob_diag["score_margin"],
                candidate_lengths=logprob_diag["candidate_lengths"],
                base_text=candidate_texts[logprob_best_idx],
                bcvf_text=candidate_texts[selected_idx],
                # Repurpose mean_sf for mean MLP prob
                mean_sf=float(np.mean(mlp_probs)),
                rank_correlation=rank_corr,
                score_std=float(np.std(learned_scores)),
                base_score_std=float(np.std(logprob_scores)),
            )
            result.base_passed = base_passed
            result.bcvf_passed = learned_passed
            result.any_passed = oracle_any

            per_prompt.append(result)

            if (i + 1) % 5 == 0 or i == 0:
                print(
                    f"  [{mode_label}] {i+1}/{len(problems)} "
                    f"base={'PASS' if base_passed else 'FAIL'} "
                    f"learned={'PASS' if learned_passed else 'FAIL'} "
                    f"changed={result.rerank_changed} "
                    f"mlp_prob={float(np.mean(mlp_probs)):.3f} "
                    f"rank_r={rank_corr:.2f}"
                )
            continue  # skip common tail

        elif rerank_mode == "value_feature":
            # --- Value-feature mode: StructureBCVF multi-channel ---
            # Uses AST + unbound-variable + return/param/placeholder
            # checks as constraint energies combined with logprob.
            from symbolu_core.ontological.structure_bcvf import (
                StructureBCVF, StructureConfig,
            )
            struct_config = StructureConfig(
                use_ast=value_use_ast,
                use_unbound=True,
                use_runtime=False,  # too slow for benchmark loop
                alpha=value_alpha,
            )
            struct_bcvf = StructureBCVF(struct_config)

            # Score each candidate
            struct_scores = np.zeros(len(candidate_texts))
            struct_diags = []
            for k in range(len(candidate_texts)):
                # Fix first-line indentation before structural analysis
                # (same fix applied to test evaluation — without this,
                # AST parse fails on ~88% of candidates due to BPE
                # tokenizer dropping/adding a leading space)
                fixed_cand = fix_completion_indent(
                    prompt, candidate_texts[k],
                )
                diag_k = struct_bcvf.compute_energies(
                    prompt, fixed_cand,
                )
                struct_diags.append(diag_k)
                struct_scores[k] = (
                    float(logprob_scores[k])
                    + value_alpha * diag_k.utility_logit
                )

            selected_idx = int(np.argmax(struct_scores))
            utilities = np.array([d.utility for d in struct_diags])

            # Score margin
            sorted_scores = np.sort(struct_scores)[::-1]
            struct_margin = (
                float(sorted_scores[0] - sorted_scores[1])
                if len(sorted_scores) > 1 else 0.0
            )

            # Rank correlation (manual Spearman)
            n_k = len(struct_scores)
            if n_k > 2:
                base_ranks = np.argsort(np.argsort(logprob_scores)).astype(float)
                val_ranks = np.argsort(np.argsort(struct_scores)).astype(float)
                d = base_ranks - val_ranks
                rank_corr = 1.0 - 6.0 * float(np.sum(d ** 2)) / (
                    float(n_k) * (float(n_k) ** 2 - 1)
                )
            elif n_k == 2:
                rank_corr = (
                    1.0 if np.argmax(logprob_scores) == np.argmax(struct_scores)
                    else -1.0
                )
            else:
                rank_corr = 1.0

            # Evaluate pass/fail
            base_code = prompt + fix_completion_indent(
                prompt, candidate_texts[logprob_best_idx],
            )
            selected_code = prompt + fix_completion_indent(
                prompt, candidate_texts[selected_idx],
            )
            base_passed = test_fn(base_code, test_code, entry_point)
            struct_passed = test_fn(selected_code, test_code, entry_point)

            oracle_any = base_passed or struct_passed
            if not oracle_any:
                for k in range(len(candidate_texts)):
                    if k == logprob_best_idx or k == selected_idx:
                        continue
                    code_k = prompt + fix_completion_indent(
                        prompt, candidate_texts[k],
                    )
                    if test_fn(code_k, test_code, entry_point):
                        oracle_any = True
                        break

            result = SeqRerankResult(
                prompt_id=task_id,
                K=K,
                rerank_lambda=0.0,
                rerank_mode="value_feature",
                base_best_idx=logprob_best_idx,
                base_best_score=float(logprob_scores[logprob_best_idx]),
                base_scores=logprob_scores,
                bcvf_best_idx=selected_idx,
                bcvf_best_score=float(struct_scores[selected_idx]),
                bcvf_scores=struct_scores,
                rerank_changed=selected_idx != logprob_best_idx,
                score_margin=struct_margin,
                base_score_margin=logprob_diag["score_margin"],
                candidate_lengths=logprob_diag["candidate_lengths"],
                base_text=candidate_texts[logprob_best_idx],
                bcvf_text=candidate_texts[selected_idx],
                # Repurpose mean_sf for mean utility
                mean_sf=float(np.mean(utilities)),
                rank_correlation=rank_corr,
                score_std=float(np.std(struct_scores)),
                base_score_std=float(np.std(logprob_scores)),
            )
            result.base_passed = base_passed
            result.bcvf_passed = struct_passed
            result.any_passed = oracle_any

            per_prompt.append(result)

            if (i + 1) % 5 == 0 or i == 0:
                ast_rate = sum(1 for d in struct_diags if d.ast_ok) / max(len(struct_diags), 1)
                dt_total = sum(d.doctest_total for d in struct_diags)
                dt_ok = sum(d.doctest_ok for d in struct_diags)
                trunc_n = sum(1 for d in struct_diags if d.is_truncated)
                util_spread = float(np.max(utilities) - np.min(utilities))
                print(
                    f"  [{mode_label}] {i+1}/{len(problems)} "
                    f"base={'PASS' if base_passed else 'FAIL'} "
                    f"struct={'PASS' if struct_passed else 'FAIL'} "
                    f"changed={result.rerank_changed} "
                    f"ast={ast_rate:.0%} "
                    f"dt={dt_ok}/{dt_total} "
                    f"trunc={trunc_n}/{len(struct_diags)} "
                    f"util={float(np.mean(utilities)):.2f} "
                    f"spread={util_spread:.3f} "
                    f"rank_r={rank_corr:.2f}"
                )
            continue  # skip common tail

        else:
            # --- BCVF mode: original Equation (B) ---
            goal = compute_prompt_goal_embedding(
                model, tokenizer, prompt, strategy="prompt_mean",
            )
            best_idx, scores, diag = rerank_candidates(
                prompt_ids, candidate_ids_list, model, goal,
                bcvf_config, rerank_lambda=rerank_lambda,
            )

            base_best_idx = diag["base_best_index"]
            _safe_mean = lambda lst: float(np.mean(lst)) if lst else 0.0

            result = SeqRerankResult(
                prompt_id=task_id,
                K=K,
                rerank_lambda=rerank_lambda,
                rerank_mode="bcvf",
                base_best_idx=base_best_idx,
                base_best_score=float(diag["base_scores"][base_best_idx]),
                base_scores=diag["base_scores"],
                bcvf_best_idx=best_idx,
                bcvf_best_score=float(scores[best_idx]),
                bcvf_scores=scores,
                rerank_changed=diag["rerank_changed"],
                score_margin=diag["score_margin"],
                base_score_margin=diag["base_score_margin"],
                candidate_lengths=diag["candidate_lengths"],
                base_text=candidate_texts[base_best_idx],
                bcvf_text=candidate_texts[best_idx],
                # Signal diagnostics
                topM_hit_rate=_safe_mean(diag["per_candidate_topM_hit_rate"]),
                mean_sf=_safe_mean(diag["per_candidate_sf"]),
                mean_sb=_safe_mean(diag["per_candidate_sb"]),
                mean_sf_all=_safe_mean(diag["per_candidate_sf_all_mean"]),
                mean_sb_all=_safe_mean(diag["per_candidate_sb_all_mean"]),
                std_sf_all=_safe_mean(diag["per_candidate_sf_all_std"]),
                std_sb_all=_safe_mean(diag["per_candidate_sb_all_std"]),
                mean_L=_safe_mean(diag["per_candidate_L_mean"]),
                std_L=_safe_mean(diag["per_candidate_L_std"]),
                penalty_per_tok=_safe_mean(diag["per_candidate_penalty_per_tok"]),
                base_lp_per_tok=_safe_mean(diag["per_candidate_base_per_tok"]),
                score_std=diag["score_std"],
                base_score_std=diag["base_score_std"],
                rank_correlation=diag["rank_correlation"],
            )
            selected_idx = best_idx

        # --- Common pass/fail evaluation (bcvf and logprob modes) ---
        base_code = prompt + fix_completion_indent(prompt, candidate_texts[logprob_best_idx])
        selected_code = prompt + fix_completion_indent(prompt, candidate_texts[selected_idx])
        result.base_passed = test_fn(base_code, test_code, entry_point)
        result.bcvf_passed = test_fn(selected_code, test_code, entry_point)
        result.any_passed = result.base_passed or result.bcvf_passed

        per_prompt.append(result)

        if (i + 1) % 5 == 0 or i == 0:
            if rerank_mode == "bcvf":
                print(
                    f"  [{mode_label}] {i+1}/{len(problems)} "
                    f"base={'PASS' if result.base_passed else 'FAIL'} "
                    f"bcvf={'PASS' if result.bcvf_passed else 'FAIL'} "
                    f"changed={result.rerank_changed} "
                    f"topM_hit={result.topM_hit_rate:.2f} "
                    f"sf={result.mean_sf:.3f} sb={result.mean_sb:.3f} "
                    f"L={result.mean_L:.4f} "
                    f"rank_r={result.rank_correlation:.2f}"
                )
            else:
                print(
                    f"  [{mode_label}] {i+1}/{len(problems)} "
                    f"base={'PASS' if result.base_passed else 'FAIL'} "
                    f"selected={'PASS' if result.bcvf_passed else 'FAIL'} "
                    f"changed={result.rerank_changed}"
                )

    elapsed = time.time() - t0
    return _build_seq_rerank_report(
        per_prompt, K, rerank_lambda, n_bootstrap, elapsed,
        has_pass_fail=True, rerank_mode=rerank_mode,
    )


# =========================================================================
# WikiText Benchmark with Sequence Reranking
# =========================================================================


def run_seq_rerank_benchmark_wikitext(
    model: Any,
    tokenizer: Any,
    texts: Sequence[str],
    bcvf_config: DecodingConfig,
    goal_strategy: str = "prompt_mean",
    K: int = 8,
    rerank_lambda: float = 1.0,
    max_new_tokens: int = 64,
    temperature: float = 1.0,
    top_p: float = 0.95,
    n_prompts: int = 50,
    prompt_length: int = 64,
    n_bootstrap: int = 1000,
) -> SeqRerankReport:
    """
    Run sequence-level BCVF reranking benchmark on WikiText.

    For each text:
    1. Use first prompt_length tokens as prompt.
    2. Generate K continuations with sampling.
    3. Score and rerank.
    4. Report reranking behavior and score statistics.

    For WikiText there is no binary pass/fail, so we report:
    - Rerank rate, score margins, mean selected logprobs.
    - If goal_strategy="lookahead", we also measure overlap with
      the actual continuation (oracle metric).

    Args:
        model: HuggingFace causal LM.
        tokenizer: Tokenizer.
        texts: Text passages to use as evaluation data.
        bcvf_config: BCVF parameters.
        goal_strategy: "prompt_mean" or "lookahead" (oracle).
        K: Number of candidates per prompt.
        rerank_lambda: BCVF mixing parameter.
        max_new_tokens: Max tokens per candidate.
        temperature: Sampling temperature.
        top_p: Nucleus sampling threshold.
        n_prompts: Number of prompts to evaluate.
        prompt_length: Number of tokens for the prompt prefix.
        n_bootstrap: Bootstrap resamples for CIs.

    Returns:
        SeqRerankReport with score-based metrics.
    """
    device = next(model.parameters()).device
    t0 = time.time()
    per_prompt: List[SeqRerankResult] = []

    for i, text in enumerate(texts):
        if len(per_prompt) >= n_prompts:
            break

        # Tokenize full text
        full_ids = tokenizer.encode(
            text, return_tensors="pt", truncation=True,
            max_length=prompt_length + max_new_tokens + 50,
        ).to(device)

        if full_ids.shape[1] < prompt_length + 10:
            continue

        prompt_ids_full = full_ids[0, :prompt_length]  # [P]
        prompt_text = tokenizer.decode(
            prompt_ids_full, skip_special_tokens=True,
        )

        # Compute goal embedding
        if goal_strategy == "lookahead":
            # Oracle: use actual future hidden states
            continuation_ids = full_ids[0, prompt_length:prompt_length + max_new_tokens]
            with torch.no_grad():
                out = model(full_ids, output_hidden_states=True, use_cache=False)
                future_hidden = out.hidden_states[-1][0, prompt_length:]
                goal = future_hidden.mean(dim=0, keepdim=True).float()
        else:
            goal = compute_prompt_goal_embedding(
                model, tokenizer, prompt_text, strategy=goal_strategy,
            )

        # Generate K candidates
        prompt_ids, candidate_ids_list, candidate_texts = generate_candidates(
            model, tokenizer, prompt_text, K=K,
            max_new_tokens=max_new_tokens,
            temperature=temperature, top_p=top_p,
        )

        if not candidate_ids_list:
            continue

        # Rerank
        best_idx, scores, diag = rerank_candidates(
            prompt_ids, candidate_ids_list, model, goal,
            bcvf_config, rerank_lambda=rerank_lambda,
        )

        base_best_idx = diag["base_best_index"]

        _safe_mean = lambda lst: float(np.mean(lst)) if lst else 0.0
        result = SeqRerankResult(
            prompt_id=f"wikitext_{i}",
            K=K,
            rerank_lambda=rerank_lambda,
            base_best_idx=base_best_idx,
            base_best_score=float(diag["base_scores"][base_best_idx]),
            base_scores=diag["base_scores"],
            bcvf_best_idx=best_idx,
            bcvf_best_score=float(scores[best_idx]),
            bcvf_scores=scores,
            rerank_changed=diag["rerank_changed"],
            score_margin=diag["score_margin"],
            base_score_margin=diag["base_score_margin"],
            candidate_lengths=diag["candidate_lengths"],
            base_text=candidate_texts[base_best_idx],
            bcvf_text=candidate_texts[best_idx],
            # Signal diagnostics
            topM_hit_rate=_safe_mean(diag["per_candidate_topM_hit_rate"]),
            mean_sf=_safe_mean(diag["per_candidate_sf"]),
            mean_sb=_safe_mean(diag["per_candidate_sb"]),
            mean_sf_all=_safe_mean(diag["per_candidate_sf_all_mean"]),
            mean_sb_all=_safe_mean(diag["per_candidate_sb_all_mean"]),
            std_sf_all=_safe_mean(diag["per_candidate_sf_all_std"]),
            std_sb_all=_safe_mean(diag["per_candidate_sb_all_std"]),
            mean_L=_safe_mean(diag["per_candidate_L_mean"]),
            std_L=_safe_mean(diag["per_candidate_L_std"]),
            penalty_per_tok=_safe_mean(diag["per_candidate_penalty_per_tok"]),
            base_lp_per_tok=_safe_mean(diag["per_candidate_base_per_tok"]),
            score_std=diag["score_std"],
            base_score_std=diag["base_score_std"],
            rank_correlation=diag["rank_correlation"],
        )

        per_prompt.append(result)

        if (i + 1) % 10 == 0 or i == 0:
            print(
                f"  [seq-rerank-wikitext] {len(per_prompt)}/{n_prompts} "
                f"changed={result.rerank_changed} "
                f"margin={result.score_margin:.3f} "
                f"topM_hit={result.topM_hit_rate:.2f} "
                f"sf={result.mean_sf:.3f} sb={result.mean_sb:.3f} "
                f"L={result.mean_L:.4f}"
            )

    elapsed = time.time() - t0
    return _build_seq_rerank_report(
        per_prompt, K, rerank_lambda, n_bootstrap, elapsed,
        has_pass_fail=False,
    )


# =========================================================================
# Report Builder
# =========================================================================


def _build_seq_rerank_report(
    per_prompt: List[SeqRerankResult],
    K: int,
    rerank_lambda: float,
    n_bootstrap: int,
    elapsed: float,
    has_pass_fail: bool,
    rerank_mode: str = "bcvf",
) -> SeqRerankReport:
    """Build aggregated report from per-prompt results."""
    n = len(per_prompt)
    if n == 0:
        return SeqRerankReport(
            n_prompts=0, K=K, rerank_lambda=rerank_lambda,
            rerank_mode=rerank_mode,
        )

    # Reranking behavior
    rerank_changed = [r.rerank_changed for r in per_prompt]
    rerank_rate = sum(rerank_changed) / n

    score_margins = [r.score_margin for r in per_prompt]
    base_score_margins = [r.base_score_margin for r in per_prompt]

    # Score-based metrics
    base_logprobs = [r.base_best_score for r in per_prompt]
    bcvf_logprobs = [
        float(r.base_scores[r.bcvf_best_idx])
        if r.base_scores is not None else 0.0
        for r in per_prompt
    ]

    # Aggregate signal diagnostics across prompts
    _agg = lambda attr: float(np.mean([getattr(r, attr) for r in per_prompt]))

    report = SeqRerankReport(
        n_prompts=n,
        K=K,
        rerank_lambda=rerank_lambda,
        equation="B",
        rerank_mode=rerank_mode,
        rerank_rate=rerank_rate,
        mean_score_margin=float(np.mean(score_margins)),
        mean_base_score_margin=float(np.mean(base_score_margins)),
        mean_base_logprob_selected=float(np.mean(base_logprobs)),
        mean_bcvf_logprob_selected=float(np.mean(bcvf_logprobs)),
        per_prompt=per_prompt,
        elapsed_seconds=elapsed,
        # Signal diagnostics
        agg_topM_hit_rate=_agg("topM_hit_rate"),
        agg_mean_sf=_agg("mean_sf"),
        agg_mean_sb=_agg("mean_sb"),
        agg_mean_sf_all=_agg("mean_sf_all"),
        agg_mean_sb_all=_agg("mean_sb_all"),
        agg_std_sf_all=_agg("std_sf_all"),
        agg_std_sb_all=_agg("std_sb_all"),
        agg_mean_L=_agg("mean_L"),
        agg_penalty_per_tok=_agg("penalty_per_tok"),
        agg_base_lp_per_tok=_agg("base_lp_per_tok"),
        agg_score_std=_agg("score_std"),
        agg_base_score_std=_agg("base_score_std"),
        agg_rank_correlation=_agg("rank_correlation"),
    )

    if has_pass_fail:
        base_passed = np.array([
            1.0 if r.base_passed else 0.0 for r in per_prompt
        ])
        bcvf_passed = np.array([
            1.0 if r.bcvf_passed else 0.0 for r in per_prompt
        ])
        any_passed = np.array([
            1.0 if r.any_passed else 0.0 for r in per_prompt
        ])

        report.base_pass_at_1 = float(base_passed.mean())
        report.bcvf_pass_at_1 = float(bcvf_passed.mean())
        report.oracle_pass_at_k = float(any_passed.mean())
        report.pass_at_1_delta = float(
            bcvf_passed.mean() - base_passed.mean()
        )

        # Win/loss rates
        wins = sum(
            1 for r in per_prompt
            if r.bcvf_passed and not r.base_passed
        )
        losses = sum(
            1 for r in per_prompt
            if not r.bcvf_passed and r.base_passed
        )
        report.rerank_win_rate = wins / n
        report.rerank_loss_rate = losses / n

        # Bootstrap CI for pass@1 delta
        report.pass_at_1_delta_ci = bootstrap_pass_at_1_delta(
            base_passed, bcvf_passed,
            n_bootstrap=n_bootstrap, seed=42,
        )

    return report


# =========================================================================
# Pretty-Print Report
# =========================================================================


def print_seq_rerank_report(report: SeqRerankReport) -> str:
    """
    Print a formatted sequence-level reranking report.

    Adapts output based on ``report.rerank_mode``:
    - ``bcvf``: Full BCVF diagnostics (original behavior).
    - ``logprob``: Concise logprob-only report.
    - ``oracle_verifier``: Shows oracle ceiling with framing numbers.

    Returns the table as a string (also prints it).
    """
    lines: List[str] = []
    sep = "=" * 70
    mode = report.rerank_mode

    # --- Mode-specific labels ---
    MODE_TITLES = {
        "bcvf": "Sequence-Level BCVF Reranking Report",
        "logprob": "Sequence-Level Logprob Reranking Report",
        "oracle_verifier": "Sequence-Level Oracle Verifier Report",
        "value": "Sequence-Level Value Reranking Report",
        "learned_value": "Sequence-Level Learned Value Reranking Report",
    }
    MODE_DESCS = {
        "bcvf": "Equation (B): BCVF-adjusted logits -> sequence logprob",
        "logprob": (
            "Pure logprob reranking: generate K candidates, pick "
            "highest base logprob.  No BCVF, no goal embedding."
        ),
        "oracle_verifier": (
            "Oracle verifier: test ALL K candidates, pick first passer "
            "(tie-break by logprob).  This is the ceiling."
        ),
        "value": (
            "S(y) = logprob + alpha * logit(V(x,y))  "
            "V = deterministic proxy verifier (AST + structural checks)"
        ),
        "learned_value": (
            "S(y) = logprob + alpha * MLP_logit(features)  "
            "MLP trained on candidate pass/fail data"
        ),
    }

    # --- Header ---
    lines.append(sep)
    lines.append(MODE_TITLES.get(mode, f"Sequence-Level Reranking ({mode})"))
    lines.append(f"  {MODE_DESCS.get(mode, mode)}")
    lines.append(
        f"  K={report.K}  "
        + (f"lambda={report.rerank_lambda:.2f}  " if mode == "bcvf" else "")
        + f"n_prompts={report.n_prompts}  "
        + f"time={report.elapsed_seconds:.1f}s"
    )
    lines.append(sep)

    # --- Reranking behavior ---
    lines.append("")
    lines.append("Reranking Behavior:")
    if mode == "oracle_verifier":
        lines.append(
            f"  Override rate:      {report.rerank_rate:.1%} "
            f"(oracle picked different candidate than logprob)"
        )
    elif mode == "logprob":
        lines.append(f"  (Logprob baseline — no reranking applied)")
    elif mode == "value":
        lines.append(f"  Rerank rate:        {report.rerank_rate:.1%}")
        lines.append(
            f"  Mean value margin:  {report.mean_score_margin:.4f} "
            f"(best - 2nd best under value scoring)"
        )
    elif mode == "learned_value":
        lines.append(f"  Rerank rate:        {report.rerank_rate:.1%}")
        lines.append(
            f"  Mean learned margin: {report.mean_score_margin:.4f} "
            f"(best - 2nd best under learned scoring)"
        )
    else:
        lines.append(f"  Rerank rate:        {report.rerank_rate:.1%}")
        lines.append(
            f"  Mean BCVF margin:   {report.mean_score_margin:.4f} "
            f"(best - 2nd best under BCVF scoring)"
        )
    lines.append(
        f"  Mean logprob margin: {report.mean_base_score_margin:.4f} "
        f"(best - 2nd best under base logprob)"
    )

    # --- Score-based metrics ---
    lines.append("")
    lines.append("Score Metrics (base logprob of selected candidate):")
    lines.append(
        f"  Logprob selection:  {report.mean_base_logprob_selected:.4f} "
        f"avg logprob"
    )
    if mode == "bcvf":
        lines.append(
            f"  BCVF selection:     {report.mean_bcvf_logprob_selected:.4f} "
            f"avg logprob"
        )
    elif mode == "value":
        lines.append(
            f"  Value selection:    {report.mean_bcvf_logprob_selected:.4f} "
            f"avg logprob"
        )
    elif mode == "oracle_verifier":
        lines.append(
            f"  Oracle selection:   {report.mean_bcvf_logprob_selected:.4f} "
            f"avg logprob"
        )
    elif mode == "learned_value":
        lines.append(
            f"  Learned selection:  {report.mean_bcvf_logprob_selected:.4f} "
            f"avg logprob"
        )

    # --- Pass@1 metrics ---
    if report.base_pass_at_1 is not None:
        lines.append("")

        if mode == "oracle_verifier":
            # Framing numbers for oracle verifier
            lines.append("Pass@1 — Oracle Verifier Framing:")
            lines.append(
                f"  Logprob pass@1:     {report.base_pass_at_1:.3f}  "
                f"<- floor (best logprob among K)"
            )
            lines.append(
                f"  Oracle pass@1:      {report.bcvf_pass_at_1:.3f}  "
                f"<- ceiling (any passer among K)"
            )
            if report.oracle_pass_at_k is not None:
                lines.append(
                    f"  Any-pass@{report.K}:        "
                    f"{report.oracle_pass_at_k:.3f}  "
                    f"<- any candidate passed (= oracle)"
                )
            gap = (report.bcvf_pass_at_1 or 0) - (report.base_pass_at_1 or 0)
            lines.append(
                f"  Headroom:           {gap:+.3f}  "
                f"<- max gain a perfect selector could achieve over logprob"
            )
        elif mode == "logprob":
            lines.append("Pass@1 — Logprob Reranking:")
            lines.append(
                f"  Logprob pass@1:     {report.base_pass_at_1:.3f}  "
                f"(= logprob-best among K candidates)"
            )
            if report.oracle_pass_at_k is not None:
                lines.append(
                    f"  Any-pass@{report.K}:        "
                    f"{report.oracle_pass_at_k:.3f}  "
                    f"(upper bound: any candidate passed)"
                )
        elif mode == "value":
            lines.append("Pass@1 — Value Reranking:")
            lines.append(
                f"  Base pass@1:        {report.base_pass_at_1:.3f}"
            )
            lines.append(
                f"  Value pass@1:       {report.bcvf_pass_at_1:.3f}"
            )
            delta = report.pass_at_1_delta or 0.0
            lines.append(
                f"  Delta (value-base): {delta:+.3f}"
            )
            if report.oracle_pass_at_k is not None:
                lines.append(
                    f"  Oracle pass@{report.K}:     "
                    f"{report.oracle_pass_at_k:.3f}"
                )
        elif mode == "learned_value":
            lines.append("Pass@1 — Learned Value Reranking:")
            lines.append(
                f"  Base pass@1:        {report.base_pass_at_1:.3f}"
            )
            lines.append(
                f"  Learned pass@1:     {report.bcvf_pass_at_1:.3f}"
            )
            delta = report.pass_at_1_delta or 0.0
            lines.append(
                f"  Delta (learned-base): {delta:+.3f}"
            )
            if report.oracle_pass_at_k is not None:
                lines.append(
                    f"  Oracle pass@{report.K}:     "
                    f"{report.oracle_pass_at_k:.3f}"
                )
        else:
            # BCVF mode (original)
            lines.append("Pass@1 Metrics (HumanEval):")
            lines.append(
                f"  Base pass@1:        {report.base_pass_at_1:.3f}"
            )
            lines.append(
                f"  BCVF pass@1:        {report.bcvf_pass_at_1:.3f}"
            )
            delta = report.pass_at_1_delta or 0.0
            lines.append(
                f"  Delta (BCVF-base):  {delta:+.3f}"
            )
            if report.oracle_pass_at_k is not None:
                lines.append(
                    f"  Oracle pass@{report.K}:     "
                    f"{report.oracle_pass_at_k:.3f}"
                )

        # Win/loss
        if mode == "oracle_verifier":
            lines.append("")
            lines.append("Oracle Override Analysis:")
            lines.append(
                f"  Win-rate:           {report.rerank_win_rate:.1%} "
                f"(oracle passed, logprob failed)"
            )
            lines.append(
                f"  Loss-rate:          {report.rerank_loss_rate:.1%} "
                f"(should be 0% for oracle)"
            )
        elif mode in ("bcvf", "value", "learned_value"):
            mode_name = {"bcvf": "BCVF", "value": "Value", "learned_value": "Learned"}[mode]
            lines.append("")
            lines.append("Win/Loss Analysis:")
            lines.append(
                f"  Rerank win-rate:    {report.rerank_win_rate:.1%} "
                f"({mode_name} passed, base failed)"
            )
            lines.append(
                f"  Rerank loss-rate:   {report.rerank_loss_rate:.1%} "
                f"({mode_name} failed, base passed)"
            )
            net = report.rerank_win_rate - report.rerank_loss_rate
            lines.append(
                f"  Net benefit:        {net:+.1%}"
            )

        # Bootstrap CI
        if report.pass_at_1_delta_ci is not None:
            ci = report.pass_at_1_delta_ci
            lines.append("")
            delta_label = {
                "bcvf": "BCVF-base",
                "logprob": "logprob-greedy",
                "oracle_verifier": "oracle-logprob",
                "value": "value-base",
                "learned_value": "learned-base",
            }.get(mode, "delta")
            lines.append(
                f"  Bootstrap 95% CI for pass@1 delta ({delta_label}): "
                f"{ci.mean:+.4f} [{ci.lower:+.4f}, {ci.upper:+.4f}] "
                f"(n={ci.n_bootstrap})"
            )

        # --- Headroom Recovery (value / learned_value modes) ---
        if mode in ("value", "learned_value") and report.oracle_pass_at_k is not None:
            label = "Value" if mode == "value" else "Learned"
            lines.append("")
            lines.append("Headroom Recovery:")
            oracle_gain = (
                (report.oracle_pass_at_k or 0)
                - (report.base_pass_at_1 or 0)
            )
            reranker_gain = (
                (report.bcvf_pass_at_1 or 0)
                - (report.base_pass_at_1 or 0)
            )
            if oracle_gain > 0:
                recovery = reranker_gain / oracle_gain
            else:
                recovery = 0.0
            lines.append(f"  Oracle headroom:   {oracle_gain:+.3f}")
            lines.append(f"  {label} recovered: {reranker_gain:+.3f}")
            lines.append(f"  Recovery ratio:    {recovery:.1%}")

    # --- BCVF Signal Diagnostics (only for bcvf mode) ---
    if mode == "bcvf":
        lines.append("")
        lines.append("-" * 70)
        lines.append("BCVF Signal Diagnostics (is BCVF providing useful signal?)")
        lines.append("-" * 70)

        lines.append("")
        lines.append("1. Top-M Coverage (are generated tokens in the BCVF window?):")
        lines.append(f"     Mean top-M hit rate:  {report.agg_topM_hit_rate:.3f}")
        if report.agg_topM_hit_rate < 0.5:
            lines.append(
                "     ** WARNING: <50% of target tokens are in top-M. "
                "BCVF cannot influence most token scores. Increase top_m."
            )

        lines.append("")
        lines.append("2. Forward/Backward Score Distributions (saturation check):")
        lines.append(
            f"     sf (target tokens): mean={report.agg_mean_sf:.4f}"
        )
        lines.append(
            f"     sb (target tokens): mean={report.agg_mean_sb:.4f}"
        )
        lines.append(
            f"     sf (all top-M):     mean={report.agg_mean_sf_all:.4f}  "
            f"std={report.agg_std_sf_all:.4f}"
        )
        lines.append(
            f"     sb (all top-M):     mean={report.agg_mean_sb_all:.4f}  "
            f"std={report.agg_std_sb_all:.4f}"
        )
        if report.agg_std_sf_all < 0.02 or report.agg_std_sb_all < 0.02:
            lines.append(
                "     ** WARNING: Very low std in sf/sb across top-M tokens. "
                "Scores are saturated -> Lagrangian is near-constant -> "
                "BCVF cannot differentiate candidates."
            )

        lines.append("")
        lines.append("3. Lagrangian Penalty Magnitude:")
        lines.append(f"     Mean L (target toks): {report.agg_mean_L:.6f}")
        lines.append(f"     Penalty/token:        {report.agg_penalty_per_tok:.6f}")
        lines.append(f"     Base logprob/token:   {report.agg_base_lp_per_tok:.4f}")
        if report.agg_base_lp_per_tok != 0:
            ratio = abs(report.agg_penalty_per_tok / report.agg_base_lp_per_tok)
            lines.append(f"     |penalty/base_lp|:    {ratio:.4f}")
            if ratio < 0.01:
                lines.append(
                    "     ** WARNING: BCVF penalty is <1% of base logprob magnitude. "
                    "The penalty is too small to meaningfully rerank. "
                    "Increase beta or lambda."
                )

        lines.append("")
        lines.append("4. Score Differentiation Across Candidates:")
        lines.append(
            f"     BCVF score std:       {report.agg_score_std:.4f}  "
            f"(spread of BCVF scores across K)"
        )
        lines.append(
            f"     Base score std:       {report.agg_base_score_std:.4f}  "
            f"(spread of base scores across K)"
        )
        lines.append(
            f"     Rank correlation:     {report.agg_rank_correlation:.3f}  "
            f"(Spearman: base vs BCVF ranking)"
        )
        if abs(report.agg_rank_correlation) > 0.95:
            lines.append(
                "     ** NOTE: Near-perfect rank correlation means BCVF is "
                "not changing the ranking. The penalty is too weak or uniform."
            )

        # Diagnosis summary
        lines.append("")
        problems_found = []
        if report.agg_topM_hit_rate < 0.5:
            problems_found.append("low top-M coverage")
        if report.agg_std_sf_all < 0.02 or report.agg_std_sb_all < 0.02:
            problems_found.append("saturated sf/sb scores")
        if report.agg_base_lp_per_tok != 0 and abs(
            report.agg_penalty_per_tok / report.agg_base_lp_per_tok
        ) < 0.01:
            problems_found.append("penalty magnitude too small")
        if abs(report.agg_rank_correlation) > 0.95:
            problems_found.append("BCVF not changing rankings")
        if problems_found:
            lines.append(
                f"  DIAGNOSIS: {', '.join(problems_found)}"
            )
        else:
            lines.append(
                "  DIAGNOSIS: BCVF signal looks active. Check pass@1 delta "
                "for whether it helps."
            )
        lines.append("")

        # Sanity check notes
        lines.append("")
        lines.append("Sanity Checks:")
        if report.rerank_lambda == 0.0:
            lines.append(
                "  lambda=0: BCVF penalty disabled, scores should equal "
                "base logprobs -> rerank_rate should be ~0%"
            )
        elif report.rerank_lambda == 1.0:
            lines.append(
                "  lambda=1: Full BCVF penalty applied "
                "(effective_beta = beta)"
            )
        else:
            lines.append(
                f"  lambda={report.rerank_lambda}: "
                f"Interpolated BCVF strength"
            )

    # --- Value Signal Diagnostics (only for value mode) ---
    if mode == "value":
        lines.append("")
        lines.append("-" * 70)
        lines.append(
            "Value Signal Diagnostics (is proxy verifier providing useful signal?)"
        )
        lines.append("-" * 70)

        lines.append("")
        lines.append("1. Utility Score Distribution:")
        lines.append(
            f"     Mean utility:     {report.agg_mean_sf:.3f}"
        )
        if report.agg_mean_sf > 0.7:
            lines.append(
                "     NOTE: High mean utility — most candidates look structurally valid."
            )
        elif report.agg_mean_sf < 0.3:
            lines.append(
                "     NOTE: Low mean utility — many candidates have structural issues."
            )

        lines.append("")
        lines.append("2. Score Differentiation Across Candidates:")
        lines.append(
            f"     Value score std:  {report.agg_score_std:.4f}  "
            f"(spread of value scores across K)"
        )
        lines.append(
            f"     Base score std:   {report.agg_base_score_std:.4f}  "
            f"(spread of base scores across K)"
        )
        lines.append(
            f"     Rank correlation: {report.agg_rank_correlation:.3f}  "
            f"(Spearman: base vs value ranking)"
        )
        if abs(report.agg_rank_correlation) > 0.95:
            lines.append(
                "     ** NOTE: Near-perfect rank correlation means value "
                "reranker is not changing the ranking."
            )
        elif abs(report.agg_rank_correlation) < 0.5:
            lines.append(
                "     ** NOTE: Low rank correlation — value reranker is "
                "significantly reshuffling candidates."
            )

    # --- Learned Value Signal Diagnostics ---
    if mode == "learned_value":
        lines.append("")
        lines.append("-" * 70)
        lines.append(
            "Learned Value Diagnostics (is MLP providing useful signal?)"
        )
        lines.append("-" * 70)

        lines.append("")
        lines.append("1. MLP Probability Distribution:")
        lines.append(
            f"     Mean P(pass):     {report.agg_mean_sf:.3f}"
        )
        if report.agg_mean_sf > 0.8:
            lines.append(
                "     NOTE: High mean P(pass) — MLP is very confident."
            )
        elif report.agg_mean_sf < 0.2:
            lines.append(
                "     NOTE: Low mean P(pass) — MLP predicts most will fail."
            )

        lines.append("")
        lines.append("2. Score Differentiation Across Candidates:")
        lines.append(
            f"     Learned score std: {report.agg_score_std:.4f}  "
            f"(spread of learned scores across K)"
        )
        lines.append(
            f"     Base score std:    {report.agg_base_score_std:.4f}  "
            f"(spread of base scores across K)"
        )
        lines.append(
            f"     Rank correlation:  {report.agg_rank_correlation:.3f}  "
            f"(Spearman: base vs learned ranking)"
        )
        if abs(report.agg_rank_correlation) > 0.95:
            lines.append(
                "     ** NOTE: Near-perfect rank correlation — MLP is not "
                "changing the ranking. alpha may be too low or MLP "
                "is not discriminative."
            )
        elif abs(report.agg_rank_correlation) < 0.5:
            lines.append(
                "     ** NOTE: Low rank correlation — MLP is "
                "significantly reshuffling candidates."
            )

    lines.append(sep)

    table = "\n".join(lines)
    print(table)
    return table
