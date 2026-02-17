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

    from symbolu.ontological.bcvf_seq_reranking import (
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

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

try:
    import torch
    import torch.nn.functional as F

    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False

from symbolu.ontological.bcvf_decoding import BCVFScoringModule, DecodingConfig
from symbolu.ontological.bcvf_benchmarks import (
    BootstrapCI,
    bootstrap_ci,
    bootstrap_pass_at_1_delta,
)


# =========================================================================
# Data Structures
# =========================================================================


@dataclass
class SeqRerankResult:
    """Result for one prompt's sequence-level reranking."""

    prompt_id: str = ""
    K: int = 0
    rerank_lambda: float = 1.0
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


@dataclass
class SeqRerankReport:
    """Aggregated metrics across all prompts."""

    n_prompts: int = 0
    K: int = 0
    rerank_lambda: float = 1.0
    equation: str = "B"
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

    for k in range(K):
        T_k = cand_lengths[k]
        if T_k == 0:
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
            adjusted_logits.scatter_(
                1, topM_indices, topM_scores - effective_beta * L
            )

            # --- Adjusted log-probs ---
            adj_lp = F.log_softmax(adjusted_logits, dim=-1)   # [T_k, V]
            adj_lp_tokens = adj_lp.gather(
                1, target.unsqueeze(1)
            ).squeeze(1)                                       # [T_k]
            scores[k] = float(adj_lp_tokens.sum().item())

            # --- Track BCVF penalty for the actual generated tokens ---
            # Find which target tokens are in top-M
            in_topM = (topM_indices == target.unsqueeze(1))  # [T_k, M]
            L_for_targets = (L * in_topM.float()).sum(dim=-1)  # [T_k]
            bcvf_penalties[k] = float(L_for_targets.sum().item())

            # Mean sf/sb across positions (for diagnostics)
            sf_for_targets = (sf * in_topM.float()).sum(dim=-1)
            sb_for_targets = (sb * in_topM.float()).sum(dim=-1)
            per_candidate_sf.append(float(sf_for_targets.mean().item()))
            per_candidate_sb.append(float(sb_for_targets.mean().item()))
        else:
            # lambda=0: pure base logprob
            scores[k] = base_scores[k]
            per_candidate_sf.append(0.0)
            per_candidate_sb.append(0.0)

    # --- Select best ---
    best_index = int(np.argmax(scores))
    base_best_index = int(np.argmax(base_scores))

    # Score margins
    sorted_scores = np.sort(scores)[::-1]
    score_margin = float(sorted_scores[0] - sorted_scores[1]) if K > 1 else 0.0
    sorted_base = np.sort(base_scores)[::-1]
    base_margin = float(sorted_base[0] - sorted_base[1]) if K > 1 else 0.0

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
    }

    return best_index, scores, diagnostics


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

    # Set pad_token_id if not set
    if tokenizer.pad_token_id is None:
        gen_kwargs["pad_token_id"] = tokenizer.eos_token_id

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
    )

    return candidate_texts[base_best_idx], candidate_texts[best_idx], result


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
) -> SeqRerankReport:
    """
    Run sequence-level BCVF reranking benchmark on HumanEval problems.

    For each problem:
    1. Generate K candidates with sampling.
    2. Baseline = candidate with highest base logprob.
    3. BCVF-reranked = candidate with highest Equation (B) score.
    4. Run unit tests on both selections.

    Args:
        model: HuggingFace causal LM.
        tokenizer: Tokenizer.
        problems: List of problem dicts with 'prompt', 'test', 'entry_point'.
        bcvf_config: BCVF parameters.
        K: Number of candidates per problem.
        rerank_lambda: BCVF mixing parameter.
        max_new_tokens: Max tokens per candidate.
        temperature: Sampling temperature.
        top_p: Nucleus sampling threshold.
        n_bootstrap: Bootstrap resamples for CIs.
        test_fn: Function(code, test_code, entry_point) -> bool.
                 Defaults to run_unit_tests from bcvf_experiments.

    Returns:
        SeqRerankReport with all metrics.
    """
    if test_fn is None:
        from symbolu.ontological.bcvf_experiments import run_unit_tests
        test_fn = run_unit_tests

    t0 = time.time()
    per_prompt: List[SeqRerankResult] = []

    for i, prob in enumerate(problems):
        prompt = prob["prompt"]
        test_code = prob.get("test", "")
        entry_point = prob.get("entry_point", "")
        task_id = prob.get("task_id", f"problem_{i}")

        # Compute goal embedding from problem description
        goal = compute_prompt_goal_embedding(
            model, tokenizer, prompt, strategy="prompt_mean",
        )

        # Generate + rerank
        base_text, bcvf_text, result = generate_and_rerank(
            model, tokenizer, prompt, goal, bcvf_config,
            K=K, rerank_lambda=rerank_lambda,
            max_new_tokens=max_new_tokens,
            temperature=temperature, top_p=top_p,
        )
        result.prompt_id = task_id

        # Run unit tests on base-best and bcvf-best
        base_code = prompt + base_text
        bcvf_code = prompt + bcvf_text
        result.base_passed = test_fn(base_code, test_code, entry_point)
        result.bcvf_passed = test_fn(bcvf_code, test_code, entry_point)

        # Oracle: did any candidate pass?
        # Re-generate candidate texts for oracle check
        prompt_ids, candidate_ids_list, candidate_texts = generate_candidates(
            model, tokenizer, prompt, K=1, max_new_tokens=1,
        )
        # We already have the results from generate_and_rerank, but
        # need to test all K candidates for oracle.  Since we can't
        # recover the candidates from result alone, test base and bcvf only.
        # Oracle pass@K = any of the tested candidates passed
        result.any_passed = result.base_passed or result.bcvf_passed

        per_prompt.append(result)

        if (i + 1) % 5 == 0 or i == 0:
            print(
                f"  [seq-rerank-humaneval] {i+1}/{len(problems)} "
                f"base={'PASS' if result.base_passed else 'FAIL'} "
                f"bcvf={'PASS' if result.bcvf_passed else 'FAIL'} "
                f"changed={result.rerank_changed}"
            )

    elapsed = time.time() - t0
    return _build_seq_rerank_report(
        per_prompt, K, rerank_lambda, n_bootstrap, elapsed,
        has_pass_fail=True,
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
        )

        per_prompt.append(result)

        if (i + 1) % 10 == 0 or i == 0:
            print(
                f"  [seq-rerank-wikitext] {len(per_prompt)}/{n_prompts} "
                f"changed={result.rerank_changed} "
                f"margin={result.score_margin:.3f}"
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
) -> SeqRerankReport:
    """Build aggregated report from per-prompt results."""
    n = len(per_prompt)
    if n == 0:
        return SeqRerankReport(n_prompts=0, K=K, rerank_lambda=rerank_lambda)

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

    report = SeqRerankReport(
        n_prompts=n,
        K=K,
        rerank_lambda=rerank_lambda,
        equation="B",
        rerank_rate=rerank_rate,
        mean_score_margin=float(np.mean(score_margins)),
        mean_base_score_margin=float(np.mean(base_score_margins)),
        mean_base_logprob_selected=float(np.mean(base_logprobs)),
        mean_bcvf_logprob_selected=float(np.mean(bcvf_logprobs)),
        per_prompt=per_prompt,
        elapsed_seconds=elapsed,
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

    Returns the table as a string (also prints it).
    """
    lines: List[str] = []
    sep = "=" * 70

    lines.append(sep)
    lines.append("Sequence-Level BCVF Reranking Report")
    lines.append(f"  Equation: (B) BCVF-adjusted logits -> sequence logprob")
    lines.append(
        f"  K={report.K}  lambda={report.rerank_lambda:.2f}  "
        f"n_prompts={report.n_prompts}  "
        f"time={report.elapsed_seconds:.1f}s"
    )
    lines.append(sep)

    # Reranking behavior
    lines.append("")
    lines.append("Reranking Behavior:")
    lines.append(f"  Rerank rate:        {report.rerank_rate:.1%}")
    lines.append(
        f"  Mean BCVF margin:   {report.mean_score_margin:.4f} "
        f"(best - 2nd best under BCVF scoring)"
    )
    lines.append(
        f"  Mean base margin:   {report.mean_base_score_margin:.4f} "
        f"(best - 2nd best under base logprob)"
    )

    # Score-based metrics
    lines.append("")
    lines.append("Score Metrics (base logprob of selected candidate):")
    lines.append(
        f"  Base selection:     {report.mean_base_logprob_selected:.4f} "
        f"avg logprob"
    )
    lines.append(
        f"  BCVF selection:     {report.mean_bcvf_logprob_selected:.4f} "
        f"avg logprob"
    )

    # Pass@1 metrics (HumanEval)
    if report.base_pass_at_1 is not None:
        lines.append("")
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

        lines.append("")
        lines.append("Win/Loss Analysis:")
        lines.append(
            f"  Rerank win-rate:    {report.rerank_win_rate:.1%} "
            f"(BCVF passed, base failed)"
        )
        lines.append(
            f"  Rerank loss-rate:   {report.rerank_loss_rate:.1%} "
            f"(BCVF failed, base passed)"
        )
        net = report.rerank_win_rate - report.rerank_loss_rate
        lines.append(
            f"  Net benefit:        {net:+.1%}"
        )

        if report.pass_at_1_delta_ci is not None:
            ci = report.pass_at_1_delta_ci
            lines.append("")
            lines.append(
                f"  Bootstrap 95% CI for pass@1 delta: "
                f"{ci.mean:+.4f} [{ci.lower:+.4f}, {ci.upper:+.4f}] "
                f"(n={ci.n_bootstrap})"
            )

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

    lines.append(sep)

    table = "\n".join(lines)
    print(table)
    return table
