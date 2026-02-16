#!/usr/bin/env python3
"""
BCVF Signal Validation — The Definitive Empirical Test
========================================================

Runs the BCVF pipeline on **real** hidden states from a real LLM and
answers the only question that matters:

    Does sb (backward goal-alignment) correlate with correctness
    better than raw logit rank?

Three goal-embedding strategies are tested:
    1. **lookahead** — hidden state from position t+1 (oracle upper bound)
    2. **prompt_mean** — mean of all prompt-position hidden states
    3. **random** — noise baseline (should show ~0 correlation)

If sb doesn't beat logits under the *lookahead* strategy, the goal
embedding concept itself is broken and BCVF cannot help regardless
of engineering improvements.

Usage::

    # Quick sanity (100 tokens, GPT-2 — fits in any GPU or CPU)
    python scripts/validate_bcvf_signal.py --model gpt2 --samples 100

    # 3B-parameter models (the real test)
    python scripts/validate_bcvf_signal.py \\
        --model microsoft/phi-3.5-mini-instruct --samples 500

    # Full evaluation with specific dataset
    python scripts/validate_bcvf_signal.py \\
        --model stabilityai/stablelm-zephyr-3b \\
        --dataset wikitext --samples 1000

    # Custom HuggingFace model, specific device
    python scripts/validate_bcvf_signal.py \\
        --model openlm-research/open_llama_3b_v2 \\
        --device cuda:0 --samples 500 --top-m 500

Recommended 3B–4B models::

    microsoft/phi-3.5-mini-instruct    (3.8B, best quality)
    stabilityai/stablelm-zephyr-3b     (3B, good baseline)
    openlm-research/open_llama_3b_v2   (3B, llama architecture)
    microsoft/phi-2                    (2.7B, fast iteration)
    gpt2                               (124M, sanity check)
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path
# ---------------------------------------------------------------------------
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import torch
import torch.nn.functional as F

from symbolu.ontological.bcvf_decoding import BCVFDecoder, DecodingConfig
from symbolu.ontological.bcvf_calibration import spearman_rank_correlation
from symbolu.ontological.bcvf_experiments import (
    ExperimentResult,
    ExperimentRunner,
    StepLogger,
    StepRecord,
)


# =========================================================================
# Result Dataclass
# =========================================================================


@dataclass
class SignalValidationResult:
    """Outcome of one goal-embedding strategy on real data."""

    strategy: str
    model_name: str
    n_samples: int
    # The critical comparison
    sb_correctness_rho: float = 0.0
    logit_rank_correctness_rho: float = 0.0
    base_logit_correctness_rho: float = 0.0
    confidence_correctness_rho: float = 0.0
    # Supporting metrics
    accuracy: float = 0.0
    mean_sb: float = 0.0
    mean_sf: float = 0.0
    rerank_change_rate: float = 0.0
    rerank_net_benefit: float = 0.0
    # Verdict
    verdict: str = ""
    # Timing
    elapsed_seconds: float = 0.0


@dataclass
class FullValidationReport:
    """Aggregated report across all strategies."""

    model_name: str
    model_params: str
    device: str
    dataset: str
    n_samples: int
    bcvf_config: Dict[str, Any] = field(default_factory=dict)
    strategies: List[SignalValidationResult] = field(default_factory=list)
    overall_verdict: str = ""


# =========================================================================
# Model Loading (HuggingFace)
# =========================================================================


def load_hf_model(
    model_name: str,
    device: str = "auto",
    dtype: str = "auto",
) -> Tuple[Any, Any]:
    """
    Load a HuggingFace model + tokenizer.

    Args:
        model_name: HF model identifier or local path.
        device: Device string ('auto', 'cpu', 'cuda', 'cuda:0', etc.).
        dtype: 'auto', 'float16', 'bfloat16', 'float32'.

    Returns:
        (model, tokenizer)
    """
    from transformers import AutoModelForCausalLM, AutoTokenizer

    print(f"Loading model: {model_name}")
    print(f"  device={device}, dtype={dtype}")

    # Resolve dtype
    torch_dtype = None
    if dtype == "float16":
        torch_dtype = torch.float16
    elif dtype == "bfloat16":
        torch_dtype = torch.bfloat16
    elif dtype == "float32":
        torch_dtype = torch.float32
    # else "auto" — let transformers decide

    tokenizer = AutoTokenizer.from_pretrained(
        model_name, trust_remote_code=True
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch_dtype,
        device_map=device if device == "auto" else None,
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    )

    if device != "auto":
        model = model.to(device)

    model.eval()

    n_params = sum(p.numel() for p in model.parameters())
    print(f"  Loaded: {n_params / 1e9:.2f}B parameters")
    print(f"  Dtype: {next(model.parameters()).dtype}")

    return model, tokenizer


# =========================================================================
# Dataset Loading
# =========================================================================


def load_evaluation_texts(
    dataset_name: str = "wikitext",
    split: str = "test",
    max_texts: int = 50,
) -> List[str]:
    """
    Load text passages for next-token evaluation.

    Returns a list of text strings, each suitable for tokenization
    and per-position next-token prediction.
    """
    from datasets import load_dataset

    if dataset_name == "wikitext":
        ds = load_dataset("wikitext", "wikitext-103-raw-v1", split=split)
        texts = [
            t for t in ds["text"]
            if len(t.strip()) > 200
        ]
    elif dataset_name == "openwebtext":
        ds = load_dataset("stas/openwebtext-10k", split="train")
        texts = [t for t in ds["text"] if len(t.strip()) > 200]
    elif dataset_name == "c4":
        ds = load_dataset("allenai/c4", "en", split="validation", streaming=True)
        texts = []
        for item in ds:
            if len(item["text"].strip()) > 200:
                texts.append(item["text"])
            if len(texts) >= max_texts * 2:
                break
    else:
        raise ValueError(f"Unknown dataset: {dataset_name}")

    # Shuffle and limit
    rng = np.random.RandomState(42)
    rng.shuffle(texts)
    return texts[:max_texts]


# =========================================================================
# Goal Embedding Strategies
# =========================================================================


def compute_goal_embeddings(
    hidden_states: torch.Tensor,
    strategy: str,
    prompt_length: int = 0,
) -> torch.Tensor:
    """
    Compute goal embeddings for each position.

    Args:
        hidden_states: [1, T, D] — hidden states from all positions.
        strategy: One of 'lookahead', 'prompt_mean', 'random'.
        prompt_length: Number of prompt tokens (for prompt_mean).

    Returns:
        goals: [T, D] — one goal embedding per position.
    """
    T, D = hidden_states.shape[1], hidden_states.shape[2]

    if strategy == "lookahead":
        # Use hidden state from position t+1 as goal for position t.
        # This is an oracle: it knows where the model is going.
        # For the last position, use itself (no lookahead available).
        goals = torch.zeros(T, D, device=hidden_states.device, dtype=hidden_states.dtype)
        goals[:-1] = hidden_states[0, 1:]
        goals[-1] = hidden_states[0, -1]
        return goals

    elif strategy == "prompt_mean":
        # Mean of the first `prompt_length` hidden states.
        # Represents the "what the prompt asks for" signal.
        if prompt_length < 1:
            prompt_length = max(1, T // 4)  # Default: first 25%
        prompt_hidden = hidden_states[0, :prompt_length]  # [P, D]
        mean_goal = prompt_hidden.mean(dim=0)  # [D]
        return mean_goal.unsqueeze(0).expand(T, -1)  # [T, D]

    elif strategy == "random":
        # Random noise baseline — no real signal.
        # If sb correlates with correctness here, something is wrong.
        torch.manual_seed(12345)
        return torch.randn(T, D, device=hidden_states.device, dtype=hidden_states.dtype)

    else:
        raise ValueError(f"Unknown strategy: {strategy}")


# =========================================================================
# Core Evaluation Loop
# =========================================================================


def evaluate_signal(
    model: Any,
    tokenizer: Any,
    texts: List[str],
    strategy: str,
    n_samples: int,
    bcvf_config: DecodingConfig,
    device: str = "cpu",
    max_seq_len: int = 512,
) -> SignalValidationResult:
    """
    Run BCVF decode_step on real hidden states and compute
    Spearman correlations.

    For each text passage:
        1. Tokenize and run the model forward to get hidden states + logits
        2. Compute goal embeddings using the specified strategy
        3. At each position t, run decode_step with (h_t, goal_t)
        4. Record: sb, logit_rank, base_logit_score, correctness

    Then compute Spearman correlations across all positions.
    """
    decoder = BCVFDecoder(bcvf_config)
    logger = StepLogger()

    vocab_emb = model.get_input_embeddings().weight.detach()
    # Ensure float32 for BCVF scoring (cosine sim needs precision)
    vocab_emb_f32 = vocab_emb.float()

    total_positions = 0
    t0 = time.time()

    for text_idx, text in enumerate(texts):
        if total_positions >= n_samples:
            break

        # Tokenize
        tokens = tokenizer.encode(
            text, return_tensors="pt", truncation=True,
            max_length=max_seq_len,
        ).to(device)

        if tokens.shape[1] < 10:
            continue

        # Forward pass
        with torch.no_grad():
            outputs = model(tokens, output_hidden_states=True)
            logits = outputs.logits  # [1, T, V]
            # Use the last hidden layer
            hidden_states = outputs.hidden_states[-1]  # [1, T, D]

        T = tokens.shape[1]
        ground_truth = tokens[0, 1:]  # [T-1] — next token at each position

        # Compute goal embeddings
        goals = compute_goal_embeddings(
            hidden_states, strategy, prompt_length=T // 4,
        )

        # Evaluate positions (skip last — no ground truth)
        positions_to_eval = min(T - 1, n_samples - total_positions)
        for t in range(positions_to_eval):
            h_t = hidden_states[:, t, :].float()  # [1, D]
            goal_t = goals[t].unsqueeze(0).float()  # [1, D]
            logits_t = logits[:, t, :].float()  # [1, V]
            gt_token = int(ground_truth[t].item())

            # Run BCVF decode step
            best_idx, probs, log_data = decoder.decode_step(
                h_t, vocab_emb_f32, goal_t, logits_t
            )

            pred_token = int(best_idx[0].item())

            # Build step record (captures logit_rank from base_logits)
            record = StepLogger.from_decode_log(
                step_index=total_positions,
                log_data=log_data,
                predicted_token=pred_token,
                ground_truth_token=gt_token,
            )
            logger.log(record)
            total_positions += 1

        if (text_idx + 1) % 5 == 0 or total_positions >= n_samples:
            elapsed = time.time() - t0
            print(
                f"  [{strategy}] {total_positions}/{n_samples} positions "
                f"({elapsed:.1f}s, "
                f"acc={logger.accuracy():.3f})"
            )

    elapsed = time.time() - t0

    # Compute correlations
    summary = logger.summary()
    sb_rho = summary["sb_correctness_corr"]
    logit_rank_rho = summary["logit_rank_correctness_corr"]
    base_logit_rho = summary["base_logit_correctness_corr"]

    # Also compute confidence-correctness correlation
    scored = [r for r in logger.records if r.correct is not None]
    conf_rho = 0.0
    if len(scored) >= 3:
        confs = np.array([r.confidence for r in scored])
        corrs = np.array([float(r.correct) for r in scored])
        conf_rho = spearman_rank_correlation(confs, corrs)

    # Determine verdict
    if sb_rho > base_logit_rho + 0.05:
        verdict = "sb WINS — goal embedding adds signal beyond logits"
    elif base_logit_rho > sb_rho + 0.05:
        verdict = "logit WINS — model already encodes the goal"
    elif abs(sb_rho) < 0.05 and abs(base_logit_rho) < 0.05:
        verdict = "NEITHER — both weak predictors, embedding bottleneck"
    else:
        verdict = "~TIED — marginal BCVF benefit"

    return SignalValidationResult(
        strategy=strategy,
        model_name="",  # Set by caller
        n_samples=total_positions,
        sb_correctness_rho=sb_rho,
        logit_rank_correctness_rho=logit_rank_rho,
        base_logit_correctness_rho=base_logit_rho,
        confidence_correctness_rho=conf_rho,
        accuracy=summary["accuracy"],
        mean_sb=summary["mean_sb"],
        mean_sf=summary["mean_sf"],
        rerank_change_rate=summary["rerank_change_rate"],
        rerank_net_benefit=summary["rerank_net_benefit"],
        verdict=verdict,
        elapsed_seconds=elapsed,
    )


# =========================================================================
# Report Formatting
# =========================================================================


def format_report(report: FullValidationReport) -> str:
    """Format the full validation report as a readable string."""
    lines = []
    lines.append("=" * 78)
    lines.append("BCVF SIGNAL VALIDATION REPORT")
    lines.append("=" * 78)
    lines.append(f"Model:   {report.model_name} ({report.model_params})")
    lines.append(f"Device:  {report.device}")
    lines.append(f"Dataset: {report.dataset}")
    lines.append(f"Samples: {report.n_samples}")
    lines.append(f"Config:  top_m={report.bcvf_config.get('top_m')}, "
                 f"beta={report.bcvf_config.get('beta')}")
    lines.append("")

    # Strategy comparison table
    lines.append("-" * 78)
    lines.append(
        f"{'Strategy':<14} {'rho(sb)':>9} {'rho(logit)':>11} "
        f"{'rho(rank)':>10} {'rho(conf)':>10} {'acc':>6} {'time':>6}"
    )
    lines.append("-" * 78)

    for s in report.strategies:
        lines.append(
            f"{s.strategy:<14} {s.sb_correctness_rho:>+9.4f} "
            f"{s.base_logit_correctness_rho:>+11.4f} "
            f"{s.logit_rank_correctness_rho:>+10.4f} "
            f"{s.confidence_correctness_rho:>+10.4f} "
            f"{s.accuracy:>5.1%} {s.elapsed_seconds:>5.0f}s"
        )

    lines.append("-" * 78)
    lines.append("")

    # Per-strategy verdicts
    lines.append("Per-strategy verdicts:")
    for s in report.strategies:
        lines.append(f"  {s.strategy:<14} {s.verdict}")
    lines.append("")

    # Detailed interpretation
    lines.append("-" * 78)
    lines.append("INTERPRETATION")
    lines.append("-" * 78)
    lines.append("")

    # Find lookahead result
    lookahead = next(
        (s for s in report.strategies if s.strategy == "lookahead"), None
    )
    random_s = next(
        (s for s in report.strategies if s.strategy == "random"), None
    )
    prompt_s = next(
        (s for s in report.strategies if s.strategy == "prompt_mean"), None
    )

    if lookahead:
        sb = lookahead.sb_correctness_rho
        lo = lookahead.base_logit_correctness_rho
        lines.append(f"Lookahead (oracle upper bound):")
        lines.append(f"  sb rho  = {sb:+.4f}")
        lines.append(f"  logit rho = {lo:+.4f}")
        if sb > lo + 0.05:
            lines.append(
                "  >> Goal embedding provides INDEPENDENT signal.")
            lines.append(
                "  >> BCVF reranking is structurally justified.")
        elif lo > sb + 0.05:
            lines.append(
                "  >> Logits already encode goal alignment better than sb.")
            lines.append(
                "  >> Even with a perfect goal, BCVF cannot beat logits.")
            lines.append(
                "  >> Recommendation: keep calibration, drop reranking.")
        elif abs(sb) < 0.05:
            lines.append(
                "  >> sb shows NO correlation even with oracle goals.")
            lines.append(
                "  >> The cosine-similarity scoring formulation may be")
            lines.append(
                "     fundamentally insufficient for this embedding space.")
        else:
            lines.append(
                "  >> sb and logits are approximately tied.")
            lines.append(
                "  >> BCVF provides marginal benefit at best.")
        lines.append("")

    if random_s:
        lines.append(f"Random baseline (sanity check):")
        lines.append(f"  sb rho = {random_s.sb_correctness_rho:+.4f}")
        if abs(random_s.sb_correctness_rho) > 0.1:
            lines.append("  >> WARNING: Random goals show correlation!")
            lines.append("     This suggests a methodological problem.")
        else:
            lines.append("  >> Clean: random goals show ~0 correlation. Good.")
        lines.append("")

    if prompt_s:
        lines.append(f"Prompt-mean (practical strategy):")
        lines.append(f"  sb rho = {prompt_s.sb_correctness_rho:+.4f}")
        if prompt_s.sb_correctness_rho > 0.05:
            lines.append(
                "  >> Prompt-mean goal provides usable signal.")
            lines.append(
                "  >> This is the deployable strategy for real use.")
        elif prompt_s.sb_correctness_rho > 0.0:
            lines.append(
                "  >> Weak but positive signal from prompt context.")
        else:
            lines.append(
                "  >> Prompt-mean goal provides no useful signal.")
            lines.append(
                "  >> A learned goal embedding is required.")
        lines.append("")

    # Overall verdict
    lines.append("=" * 78)
    lines.append(f"OVERALL VERDICT: {report.overall_verdict}")
    lines.append("=" * 78)

    return "\n".join(lines)


def determine_overall_verdict(
    strategies: List[SignalValidationResult],
) -> str:
    """Determine the overall go/no-go verdict."""
    lookahead = next(
        (s for s in strategies if s.strategy == "lookahead"), None
    )
    random_s = next(
        (s for s in strategies if s.strategy == "random"), None
    )

    if random_s and abs(random_s.sb_correctness_rho) > 0.1:
        return "INVALID — random baseline shows spurious correlation, check methodology"

    if not lookahead:
        return "INCOMPLETE — no lookahead strategy tested"

    sb = lookahead.sb_correctness_rho
    lo = lookahead.base_logit_correctness_rho

    if sb > lo + 0.05 and sb > 0.1:
        return (
            "GO — sb provides independent signal beyond logits. "
            "Proceed to learned goal embeddings and fine-tuning."
        )
    elif lo > sb + 0.05:
        return (
            "STOP RERANKING — logits already encode goal alignment. "
            "Pivot to calibration-only (Option B). "
            "The model's own confidence is the best predictor."
        )
    elif abs(sb) < 0.05:
        return (
            "STOP — sb shows no signal even with oracle goals. "
            "The cosine-similarity scoring formulation needs redesign "
            "or the embedding space is not goal-aligned."
        )
    else:
        return (
            "MARGINAL — sb and logits are tied. "
            "BCVF may help in specific domains but is not a general win. "
            "Consider domain-specific goal embeddings."
        )


# =========================================================================
# CLI
# =========================================================================


# =========================================================================
# Dry-Run Mode (tiny random-weight model, no network needed)
# =========================================================================


def create_dry_run_model(
    device: str = "cpu",
) -> Tuple[Any, Any, List[str]]:
    """
    Create a tiny GPT-2 model with random weights and synthetic texts.

    Returns (model, tokenizer, texts) — all local, no downloads.
    The model has ~600K params (not 124M) so it runs in seconds.
    """
    from transformers import GPT2Config, GPT2LMHeadModel, GPT2TokenizerFast

    print("DRY-RUN: Creating tiny random-weight model (no network)")

    # Small vocab (50) so random chance gives ~2% accuracy,
    # enough correct predictions to exercise the Spearman math.
    config = GPT2Config(
        vocab_size=50,
        n_positions=256,
        n_embd=64,
        n_layer=2,
        n_head=2,
        n_inner=128,
        bos_token_id=0,
        eos_token_id=1,
    )
    model = GPT2LMHeadModel(config)
    model.to(device)
    model.eval()

    n_params = sum(p.numel() for p in model.parameters())
    print(f"  Tiny model: {n_params / 1e3:.1f}K parameters, "
          f"vocab={config.vocab_size}, d_model={config.n_embd}")

    # Build a minimal tokenizer from the model's vocab
    # We only need encode() and decode() to work
    class _MinimalTokenizer:
        """Bare-bones tokenizer for dry-run (wraps random token IDs)."""

        def __init__(self, vocab_size: int, eos_id: int = 1):
            self.vocab_size = vocab_size
            self.eos_token_id = eos_id
            self.pad_token_id = eos_id
            self.pad_token = "<pad>"
            self.eos_token = "<eos>"

        def encode(
            self, text: str, return_tensors: str = "pt",
            truncation: bool = True, max_length: int = 256,
            **kwargs,
        ) -> torch.Tensor:
            # Deterministic pseudo-tokenization: hash characters to token IDs
            ids = []
            for i, ch in enumerate(text):
                tok = (ord(ch) * 31 + i * 7) % (self.vocab_size - 2) + 2
                ids.append(tok)
            ids = ids[:max_length]
            if return_tensors == "pt":
                return torch.tensor([ids], dtype=torch.long)
            return ids

        def decode(self, ids, skip_special_tokens: bool = True) -> str:
            return f"<decoded {len(ids)} tokens>"

    tokenizer = _MinimalTokenizer(config.vocab_size)

    # Synthetic texts — enough variety to produce 500+ token positions
    texts = [
        "The quick brown fox jumps over the lazy dog. " * 10,
        "In functional programming, functions are first-class citizens. " * 8,
        "Machine learning models learn patterns from data through optimization. " * 8,
        "The Spearman rank correlation measures monotonic relationships. " * 10,
        "Hidden states in transformer models encode contextual representations. " * 8,
        "Goal alignment measures whether a token choice moves toward the objective. " * 8,
        "Calibration ensures that model confidence reflects actual accuracy. " * 10,
        "The Lagrangian penalizes deviations from both forward and backward scores. " * 8,
    ]

    return model, tokenizer, texts


RECOMMENDED_MODELS = {
    "gpt2": "gpt2 (124M — sanity check, fast)",
    "phi2": "microsoft/phi-2 (2.7B — fast iteration)",
    "phi3": "microsoft/phi-3.5-mini-instruct (3.8B — best quality)",
    "stablelm": "stabilityai/stablelm-zephyr-3b (3B — good baseline)",
    "openllama3b": "openlm-research/open_llama_3b_v2 (3B — llama arch)",
}

MODEL_ALIASES = {
    "gpt2": "gpt2",
    "phi2": "microsoft/phi-2",
    "phi-2": "microsoft/phi-2",
    "phi3": "microsoft/phi-3.5-mini-instruct",
    "phi-3": "microsoft/phi-3.5-mini-instruct",
    "phi3.5": "microsoft/phi-3.5-mini-instruct",
    "stablelm": "stabilityai/stablelm-zephyr-3b",
    "stablelm3b": "stabilityai/stablelm-zephyr-3b",
    "openllama": "openlm-research/open_llama_3b_v2",
    "openllama3b": "openlm-research/open_llama_3b_v2",
}


def resolve_model_name(name: str) -> str:
    """Resolve aliases to full HuggingFace model identifiers."""
    return MODEL_ALIASES.get(name.lower().replace("-", "").replace("_", ""), name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="BCVF Signal Validation — empirical test on real LLM hidden states",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join([
            "Recommended 3B-4B models:",
            *(f"  {alias:<14} {desc}" for alias, desc in RECOMMENDED_MODELS.items()),
            "",
            "Examples:",
            "  python scripts/validate_bcvf_signal.py --model gpt2 --samples 100",
            "  python scripts/validate_bcvf_signal.py --model phi3 --samples 500",
            "  python scripts/validate_bcvf_signal.py --model stabilityai/stablelm-zephyr-3b",
        ]),
    )

    # Model
    parser.add_argument(
        "--model", type=str, default="gpt2",
        help="HuggingFace model name or alias (default: gpt2)",
    )
    parser.add_argument(
        "--dtype", type=str, default="auto",
        choices=["auto", "float16", "bfloat16", "float32"],
        help="Model dtype (default: auto)",
    )

    # Device
    parser.add_argument(
        "--device", type=str, default="auto",
        help="Device: 'auto', 'cpu', 'cuda', 'cuda:0' (default: auto)",
    )

    # Dataset
    parser.add_argument(
        "--dataset", type=str, default="wikitext",
        choices=["wikitext", "openwebtext", "c4"],
        help="Evaluation dataset (default: wikitext)",
    )

    # Evaluation
    parser.add_argument(
        "--samples", type=int, default=500,
        help="Number of token positions to evaluate (default: 500)",
    )
    parser.add_argument(
        "--max-seq-len", type=int, default=512,
        help="Maximum sequence length per passage (default: 512)",
    )
    parser.add_argument(
        "--max-texts", type=int, default=100,
        help="Maximum text passages to load from dataset (default: 100)",
    )

    # BCVF config
    parser.add_argument(
        "--top-m", type=int, default=500,
        help="Top-M candidates for BCVF (default: 500)",
    )
    parser.add_argument(
        "--beta", type=float, default=0.2,
        help="BCVF beta parameter (default: 0.2)",
    )

    # Strategies
    parser.add_argument(
        "--strategies", type=str, nargs="+",
        default=["lookahead", "prompt_mean", "random"],
        choices=["lookahead", "prompt_mean", "random"],
        help="Goal embedding strategies to test (default: all three)",
    )

    # Output
    parser.add_argument(
        "--output", type=str, default=None,
        help="Path to save JSON results (default: None — print only)",
    )
    parser.add_argument(
        "--list-models", action="store_true",
        help="List recommended models and exit",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help=(
            "Run with a tiny random-weight model and synthetic text. "
            "Verifies the full pipeline end-to-end without network "
            "access.  Correlations will be near-zero (meaningless) "
            "but the plumbing is proven correct."
        ),
    )

    return parser


# =========================================================================
# Main
# =========================================================================


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.list_models:
        print("Recommended models for BCVF validation:")
        print()
        for alias, desc in RECOMMENDED_MODELS.items():
            print(f"  {alias:<14} {desc}")
        print()
        print("Use --model <alias> or --model <full-hf-name>")
        sys.exit(0)

    # Resolve device
    device = args.device
    if device == "auto":
        if torch.cuda.is_available():
            device = "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"
    print(f"Device: {device}")

    # BCVF config — clamp top_m to dry-run vocab size if needed
    top_m = args.top_m
    if args.dry_run and top_m > 500:
        top_m = 500  # dry-run vocab is only 1000
    bcvf_config = DecodingConfig(
        top_m=top_m,
        beta=args.beta,
        use_rerank=True,
        use_calibration=True,
        use_logit_mod=False,
    )

    # Load model + texts
    if args.dry_run:
        model_name = "dry-run-tiny-random"
        model, tokenizer, texts = create_dry_run_model(device=device)
        # Clamp to tiny model's position limit
        args.max_seq_len = min(args.max_seq_len, 256)
        # Override params for tiny model
        if args.samples > 200:
            args.samples = 200
        # Clamp top_m to dry-run vocab size (50)
        top_m = min(top_m, 25)
        bcvf_config = DecodingConfig(
            top_m=top_m,
            beta=args.beta,
            use_rerank=True,
            use_calibration=True,
            use_logit_mod=False,
        )
        print(f"DRY-RUN: max_seq_len={args.max_seq_len}, samples={args.samples}, top_m={top_m}")
    else:
        model_name = resolve_model_name(args.model)
        print(f"Resolved model: {model_name}")
        model, tokenizer = load_hf_model(model_name, device=device, dtype=args.dtype)
        print(f"\nLoading dataset: {args.dataset}")
        texts = load_evaluation_texts(
            args.dataset, max_texts=args.max_texts,
        )
        print(f"  Loaded {len(texts)} text passages")

    # Determine effective device for tensors
    if device == "auto":
        # Model might be on multiple devices with device_map
        effective_device = next(model.parameters()).device
    else:
        effective_device = device

    # Run strategies
    print(f"\n{'='*60}")
    print("Running BCVF signal validation")
    print(f"  Strategies: {args.strategies}")
    print(f"  Samples per strategy: {args.samples}")
    print(f"  top_m={bcvf_config.top_m}, beta={bcvf_config.beta}")
    print(f"{'='*60}\n")

    strategy_results: List[SignalValidationResult] = []

    for strategy in args.strategies:
        print(f"\n--- Strategy: {strategy} ---")
        result = evaluate_signal(
            model=model,
            tokenizer=tokenizer,
            texts=texts,
            strategy=strategy,
            n_samples=args.samples,
            bcvf_config=bcvf_config,
            device=str(effective_device),
            max_seq_len=args.max_seq_len,
        )
        result.model_name = model_name
        strategy_results.append(result)
        print(f"  Done: sb_rho={result.sb_correctness_rho:+.4f}, "
              f"logit_rho={result.base_logit_correctness_rho:+.4f}, "
              f"verdict={result.verdict}")

    # Build report
    n_params = sum(p.numel() for p in model.parameters())
    report = FullValidationReport(
        model_name=model_name,
        model_params=f"{n_params / 1e9:.2f}B",
        device=str(effective_device),
        dataset=args.dataset,
        n_samples=args.samples,
        bcvf_config={
            "top_m": bcvf_config.top_m,
            "beta": bcvf_config.beta,
            "lambda_f": bcvf_config.lambda_f,
            "lambda_b": bcvf_config.lambda_b,
            "lambda_c": bcvf_config.lambda_c,
        },
        strategies=strategy_results,
        overall_verdict=determine_overall_verdict(strategy_results),
    )

    # Print report
    report_str = format_report(report)
    print("\n")
    print(report_str)

    # Save if requested
    if args.output:
        output_path = Path(args.output)
        output_data = {
            "model_name": report.model_name,
            "model_params": report.model_params,
            "device": report.device,
            "dataset": report.dataset,
            "n_samples": report.n_samples,
            "bcvf_config": report.bcvf_config,
            "overall_verdict": report.overall_verdict,
            "strategies": [
                {
                    "strategy": s.strategy,
                    "sb_correctness_rho": s.sb_correctness_rho,
                    "logit_rank_correctness_rho": s.logit_rank_correctness_rho,
                    "base_logit_correctness_rho": s.base_logit_correctness_rho,
                    "confidence_correctness_rho": s.confidence_correctness_rho,
                    "accuracy": s.accuracy,
                    "mean_sb": s.mean_sb,
                    "mean_sf": s.mean_sf,
                    "rerank_change_rate": s.rerank_change_rate,
                    "rerank_net_benefit": s.rerank_net_benefit,
                    "verdict": s.verdict,
                    "elapsed_seconds": s.elapsed_seconds,
                }
                for s in report.strategies
            ],
        }
        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)
        print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
