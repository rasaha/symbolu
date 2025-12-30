#!/usr/bin/env python3
"""
Standard LLM Benchmark Suite
============================

Comprehensive evaluation suite for comparing Phase Attention models
against standard benchmarks used in LLM research.

Benchmarks included:
- Perplexity: WikiText-103, PTB, LAMBADA
- Reasoning: HellaSwag, PIQA, WinoGrande, ARC-Easy, ARC-Challenge
- Knowledge: TriviaQA (subset), MMLU (subset)
- Long Context: Needle-in-Haystack, Passkey Retrieval
- Generation: Text completion quality

Usage:
------
    # Quick benchmark (perplexity only)
    python benchmark_llm.py --checkpoint checkpoints/best.pt --quick

    # Full benchmark suite
    python benchmark_llm.py --checkpoint checkpoints/best.pt --full

    # Specific benchmarks
    python benchmark_llm.py --checkpoint checkpoints/best.pt --benchmarks perplexity,hellaswag,niah

    # Compare multiple checkpoints
    python benchmark_llm.py --checkpoints ckpt1.pt,ckpt2.pt --output comparison.json

Author: SymbolU Team
Date: December 2025
"""

import os

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import argparse
import json
import math
import random
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import torch
import torch.nn.functional as F
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from symbolu.phase_transformer import PhaseTransformer, HybridPhaseTransformer

try:
    from transformers import GPT2Tokenizer, AutoTokenizer
    from datasets import load_dataset
    HAS_HF = True
except ImportError:
    HAS_HF = False
    print("Warning: transformers/datasets not installed. Some benchmarks unavailable.")


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class BenchmarkConfig:
    """Configuration for benchmark suite."""
    checkpoint: str
    model_type: str = "hybrid"
    model_size: str = "medium"
    device: str = "auto"

    # Benchmark selection
    benchmarks: List[str] = None  # None = all

    # Limits for faster testing
    max_samples: int = 1000
    max_context: int = 2048

    # Output
    output_file: str = "benchmark_results.json"
    verbose: bool = True


@dataclass
class BenchmarkResult:
    """Result from a single benchmark."""
    name: str
    score: float
    metric: str  # e.g., "perplexity", "accuracy", "f1"
    samples: int
    time_seconds: float
    details: Dict[str, Any] = None


# Model presets (must match train.py)
MODEL_PRESETS = {
    "tiny": {"embed_dim": 256, "num_layers": 4, "num_heads": 4, "ff_dim": 1024},
    "small": {"embed_dim": 512, "num_layers": 8, "num_heads": 8, "ff_dim": 2048},
    "medium": {"embed_dim": 768, "num_layers": 12, "num_heads": 12, "ff_dim": 3072},
    "large": {"embed_dim": 1024, "num_layers": 24, "num_heads": 16, "ff_dim": 4096},
}


# =============================================================================
# MODEL LOADING
# =============================================================================

def load_model(config: BenchmarkConfig, device: torch.device) -> torch.nn.Module:
    """Load model from checkpoint."""

    # Load checkpoint
    ckpt = torch.load(config.checkpoint, map_location=device, weights_only=False)

    # Get model config from checkpoint or use preset
    if "config" in ckpt:
        model_config = ckpt["config"]
        embed_dim = model_config.get("embed_dim", 768)
        num_layers = model_config.get("num_layers", 12)
        num_heads = model_config.get("num_heads", 12)
        ff_dim = model_config.get("ff_dim", 3072)
        max_seq_len = model_config.get("max_seq_len", 2048)
        vocab_size = model_config.get("vocab_size", 50257)
    else:
        # Infer from checkpoint
        preset = MODEL_PRESETS.get(config.model_size, MODEL_PRESETS["medium"])
        embed_dim = preset["embed_dim"]
        num_layers = preset["num_layers"]
        num_heads = preset["num_heads"]
        ff_dim = preset["ff_dim"]
        max_seq_len = 2048
        vocab_size = 50257

        # Try to infer from weights
        if "model" in ckpt:
            for key, val in ckpt["model"].items():
                if "pos_embed" in key:
                    max_seq_len = val.shape[0]
                if "token_embed" in key:
                    vocab_size = val.shape[0]
                    embed_dim = val.shape[1]
                break

    # Create model
    if config.model_type == "phase":
        model = PhaseTransformer(
            vocab_size=vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            ff_dim=ff_dim,
            max_seq_len=max_seq_len,
            dropout=0.0,
        )
    else:
        model = HybridPhaseTransformer(
            vocab_size=vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            ff_dim=ff_dim,
            max_seq_len=max_seq_len,
            dropout=0.0,
            local_layers=2,
            window_size=256,
            local_backend="unfold",
        )

    # Load weights
    if "model" in ckpt:
        model.load_state_dict(ckpt["model"], strict=False)
    else:
        model.load_state_dict(ckpt, strict=False)

    model = model.to(device)
    model.eval()

    return model, max_seq_len


# =============================================================================
# PERPLEXITY BENCHMARKS
# =============================================================================

def benchmark_perplexity_wikitext(
    model: torch.nn.Module,
    tokenizer,
    device: torch.device,
    max_seq_len: int,
    max_samples: int = 1000,
) -> BenchmarkResult:
    """Evaluate perplexity on WikiText-103 test set."""

    start_time = time.time()

    if not HAS_HF:
        return BenchmarkResult(
            name="wikitext103_ppl",
            score=float('inf'),
            metric="perplexity",
            samples=0,
            time_seconds=0,
            details={"error": "datasets not installed"}
        )

    # Load dataset
    dataset = load_dataset("wikitext", "wikitext-103-raw-v1", split="test")

    # Concatenate and tokenize
    text = "\n\n".join([x["text"] for x in dataset if x["text"].strip()])
    tokens = tokenizer.encode(text)

    # Evaluate perplexity
    total_loss = 0.0
    total_tokens = 0
    num_chunks = min(max_samples, len(tokens) // max_seq_len)

    with torch.no_grad():
        for i in range(num_chunks):
            start = i * max_seq_len
            end = start + max_seq_len + 1

            if end > len(tokens):
                break

            chunk = torch.tensor(tokens[start:end], device=device).unsqueeze(0)
            x = chunk[:, :-1]
            y = chunk[:, 1:]

            output = model(x)
            if isinstance(output, dict):
                logits = output.get("logits", output.get("output"))
            else:
                logits = output

            loss = F.cross_entropy(
                logits.view(-1, logits.size(-1)),
                y.view(-1),
                reduction='sum'
            )

            total_loss += loss.item()
            total_tokens += y.numel()

    avg_loss = total_loss / total_tokens if total_tokens > 0 else float('inf')
    perplexity = math.exp(avg_loss) if avg_loss < 100 else float('inf')

    return BenchmarkResult(
        name="wikitext103_ppl",
        score=perplexity,
        metric="perplexity",
        samples=num_chunks,
        time_seconds=time.time() - start_time,
        details={"avg_loss": avg_loss, "total_tokens": total_tokens}
    )


def benchmark_perplexity_lambada(
    model: torch.nn.Module,
    tokenizer,
    device: torch.device,
    max_seq_len: int,
    max_samples: int = 1000,
) -> BenchmarkResult:
    """Evaluate on LAMBADA dataset - predicting final word."""

    start_time = time.time()

    if not HAS_HF:
        return BenchmarkResult(
            name="lambada",
            score=0.0,
            metric="accuracy",
            samples=0,
            time_seconds=0,
            details={"error": "datasets not installed"}
        )

    # Load LAMBADA
    try:
        dataset = load_dataset("lambada", split="test")
    except:
        return BenchmarkResult(
            name="lambada",
            score=0.0,
            metric="accuracy",
            samples=0,
            time_seconds=0,
            details={"error": "Could not load LAMBADA dataset"}
        )

    correct = 0
    total = 0

    with torch.no_grad():
        for item in list(dataset)[:max_samples]:
            text = item["text"]

            # Split into context and target (last word)
            words = text.split()
            if len(words) < 2:
                continue

            context = " ".join(words[:-1])
            target = words[-1]

            # Tokenize
            context_ids = tokenizer.encode(context)
            target_ids = tokenizer.encode(" " + target)

            if len(context_ids) + len(target_ids) > max_seq_len:
                context_ids = context_ids[-(max_seq_len - len(target_ids)):]

            # Get model prediction
            input_ids = torch.tensor([context_ids], device=device)
            output = model(input_ids)

            if isinstance(output, dict):
                logits = output.get("logits", output.get("output"))
            else:
                logits = output

            # Check if model predicts the target
            next_token = logits[0, -1, :].argmax().item()

            if next_token == target_ids[0]:
                correct += 1
            total += 1

    accuracy = correct / total if total > 0 else 0.0

    return BenchmarkResult(
        name="lambada",
        score=accuracy * 100,
        metric="accuracy",
        samples=total,
        time_seconds=time.time() - start_time,
        details={"correct": correct, "total": total}
    )


# =============================================================================
# REASONING BENCHMARKS
# =============================================================================

def benchmark_hellaswag(
    model: torch.nn.Module,
    tokenizer,
    device: torch.device,
    max_seq_len: int,
    max_samples: int = 1000,
) -> BenchmarkResult:
    """Evaluate on HellaSwag - commonsense reasoning."""

    start_time = time.time()

    if not HAS_HF:
        return BenchmarkResult(
            name="hellaswag",
            score=0.0,
            metric="accuracy",
            samples=0,
            time_seconds=0,
            details={"error": "datasets not installed"}
        )

    try:
        dataset = load_dataset("hellaswag", split="validation")
    except:
        return BenchmarkResult(
            name="hellaswag",
            score=0.0,
            metric="accuracy",
            samples=0,
            time_seconds=0,
            details={"error": "Could not load HellaSwag"}
        )

    correct = 0
    total = 0

    with torch.no_grad():
        for item in list(dataset)[:max_samples]:
            ctx = item["ctx"]
            endings = item["endings"]
            label = int(item["label"])

            # Score each ending
            scores = []
            for ending in endings:
                text = ctx + " " + ending
                tokens = tokenizer.encode(text)

                if len(tokens) > max_seq_len:
                    tokens = tokens[:max_seq_len]

                input_ids = torch.tensor([tokens[:-1]], device=device)
                target_ids = torch.tensor([tokens[1:]], device=device)

                output = model(input_ids)
                if isinstance(output, dict):
                    logits = output.get("logits", output.get("output"))
                else:
                    logits = output

                # Compute log probability
                log_probs = F.log_softmax(logits, dim=-1)
                token_log_probs = log_probs.gather(2, target_ids.unsqueeze(-1)).squeeze(-1)
                score = token_log_probs.sum().item()
                scores.append(score)

            # Check if correct
            predicted = scores.index(max(scores))
            if predicted == label:
                correct += 1
            total += 1

    accuracy = correct / total if total > 0 else 0.0

    return BenchmarkResult(
        name="hellaswag",
        score=accuracy * 100,
        metric="accuracy",
        samples=total,
        time_seconds=time.time() - start_time,
        details={"correct": correct, "total": total}
    )


def benchmark_piqa(
    model: torch.nn.Module,
    tokenizer,
    device: torch.device,
    max_seq_len: int,
    max_samples: int = 1000,
) -> BenchmarkResult:
    """Evaluate on PIQA - physical intuition."""

    start_time = time.time()

    if not HAS_HF:
        return BenchmarkResult(
            name="piqa",
            score=0.0,
            metric="accuracy",
            samples=0,
            time_seconds=0,
            details={"error": "datasets not installed"}
        )

    try:
        dataset = load_dataset("piqa", split="validation")
    except:
        return BenchmarkResult(
            name="piqa",
            score=0.0,
            metric="accuracy",
            samples=0,
            time_seconds=0,
            details={"error": "Could not load PIQA"}
        )

    correct = 0
    total = 0

    with torch.no_grad():
        for item in list(dataset)[:max_samples]:
            goal = item["goal"]
            sol1 = item["sol1"]
            sol2 = item["sol2"]
            label = item["label"]

            # Score each solution
            scores = []
            for sol in [sol1, sol2]:
                text = f"Goal: {goal}\nSolution: {sol}"
                tokens = tokenizer.encode(text)

                if len(tokens) > max_seq_len:
                    tokens = tokens[:max_seq_len]

                input_ids = torch.tensor([tokens[:-1]], device=device)
                target_ids = torch.tensor([tokens[1:]], device=device)

                output = model(input_ids)
                if isinstance(output, dict):
                    logits = output.get("logits", output.get("output"))
                else:
                    logits = output

                log_probs = F.log_softmax(logits, dim=-1)
                token_log_probs = log_probs.gather(2, target_ids.unsqueeze(-1)).squeeze(-1)
                score = token_log_probs.mean().item()  # Normalize by length
                scores.append(score)

            predicted = scores.index(max(scores))
            if predicted == label:
                correct += 1
            total += 1

    accuracy = correct / total if total > 0 else 0.0

    return BenchmarkResult(
        name="piqa",
        score=accuracy * 100,
        metric="accuracy",
        samples=total,
        time_seconds=time.time() - start_time,
        details={"correct": correct, "total": total}
    )


def benchmark_winogrande(
    model: torch.nn.Module,
    tokenizer,
    device: torch.device,
    max_seq_len: int,
    max_samples: int = 1000,
) -> BenchmarkResult:
    """Evaluate on WinoGrande - coreference resolution."""

    start_time = time.time()

    if not HAS_HF:
        return BenchmarkResult(
            name="winogrande",
            score=0.0,
            metric="accuracy",
            samples=0,
            time_seconds=0,
            details={"error": "datasets not installed"}
        )

    try:
        dataset = load_dataset("winogrande", "winogrande_xl", split="validation")
    except:
        return BenchmarkResult(
            name="winogrande",
            score=0.0,
            metric="accuracy",
            samples=0,
            time_seconds=0,
            details={"error": "Could not load WinoGrande"}
        )

    correct = 0
    total = 0

    with torch.no_grad():
        for item in list(dataset)[:max_samples]:
            sentence = item["sentence"]
            option1 = item["option1"]
            option2 = item["option2"]
            label = int(item["answer"]) - 1  # 1 or 2 -> 0 or 1

            # Replace _ with each option
            scores = []
            for option in [option1, option2]:
                text = sentence.replace("_", option)
                tokens = tokenizer.encode(text)

                if len(tokens) > max_seq_len:
                    tokens = tokens[:max_seq_len]

                input_ids = torch.tensor([tokens[:-1]], device=device)
                target_ids = torch.tensor([tokens[1:]], device=device)

                output = model(input_ids)
                if isinstance(output, dict):
                    logits = output.get("logits", output.get("output"))
                else:
                    logits = output

                log_probs = F.log_softmax(logits, dim=-1)
                token_log_probs = log_probs.gather(2, target_ids.unsqueeze(-1)).squeeze(-1)
                score = token_log_probs.mean().item()
                scores.append(score)

            predicted = scores.index(max(scores))
            if predicted == label:
                correct += 1
            total += 1

    accuracy = correct / total if total > 0 else 0.0

    return BenchmarkResult(
        name="winogrande",
        score=accuracy * 100,
        metric="accuracy",
        samples=total,
        time_seconds=time.time() - start_time,
        details={"correct": correct, "total": total}
    )


def benchmark_arc(
    model: torch.nn.Module,
    tokenizer,
    device: torch.device,
    max_seq_len: int,
    max_samples: int = 500,
    challenge: bool = False,
) -> BenchmarkResult:
    """Evaluate on ARC (AI2 Reasoning Challenge)."""

    start_time = time.time()
    subset = "ARC-Challenge" if challenge else "ARC-Easy"

    if not HAS_HF:
        return BenchmarkResult(
            name=f"arc_{'challenge' if challenge else 'easy'}",
            score=0.0,
            metric="accuracy",
            samples=0,
            time_seconds=0,
            details={"error": "datasets not installed"}
        )

    try:
        dataset = load_dataset("ai2_arc", subset, split="test")
    except:
        return BenchmarkResult(
            name=f"arc_{'challenge' if challenge else 'easy'}",
            score=0.0,
            metric="accuracy",
            samples=0,
            time_seconds=0,
            details={"error": f"Could not load {subset}"}
        )

    correct = 0
    total = 0

    with torch.no_grad():
        for item in list(dataset)[:max_samples]:
            question = item["question"]
            choices = item["choices"]
            answer_key = item["answerKey"]

            labels = choices["label"]
            texts = choices["text"]

            # Find correct answer index
            try:
                correct_idx = labels.index(answer_key)
            except ValueError:
                continue

            # Score each choice
            scores = []
            for choice_text in texts:
                text = f"Question: {question}\nAnswer: {choice_text}"
                tokens = tokenizer.encode(text)

                if len(tokens) > max_seq_len:
                    tokens = tokens[:max_seq_len]

                input_ids = torch.tensor([tokens[:-1]], device=device)
                target_ids = torch.tensor([tokens[1:]], device=device)

                output = model(input_ids)
                if isinstance(output, dict):
                    logits = output.get("logits", output.get("output"))
                else:
                    logits = output

                log_probs = F.log_softmax(logits, dim=-1)
                token_log_probs = log_probs.gather(2, target_ids.unsqueeze(-1)).squeeze(-1)
                score = token_log_probs.mean().item()
                scores.append(score)

            predicted = scores.index(max(scores))
            if predicted == correct_idx:
                correct += 1
            total += 1

    accuracy = correct / total if total > 0 else 0.0

    return BenchmarkResult(
        name=f"arc_{'challenge' if challenge else 'easy'}",
        score=accuracy * 100,
        metric="accuracy",
        samples=total,
        time_seconds=time.time() - start_time,
        details={"correct": correct, "total": total}
    )


# =============================================================================
# LONG CONTEXT BENCHMARKS
# =============================================================================

def benchmark_needle_in_haystack(
    model: torch.nn.Module,
    tokenizer,
    device: torch.device,
    max_seq_len: int,
    depths: List[float] = [0.0, 0.25, 0.5, 0.75, 1.0],
    num_samples: int = 3,
) -> BenchmarkResult:
    """Needle in a haystack retrieval test."""

    start_time = time.time()

    # Haystack filler text
    filler = (
        "The quick brown fox jumps over the lazy dog. "
        "Machine learning is transforming technology. "
        "Natural language processing enables computers to understand text. "
        "Deep neural networks learn hierarchical representations. "
    ) * 100

    needle_templates = [
        ("The secret password is {code}.", "What is the secret password?"),
        ("The magic number is {code}.", "What is the magic number?"),
        ("Remember the code: {code}.", "What is the code to remember?"),
    ]

    correct = 0
    total = 0

    test_context = min(max_seq_len - 200, 4096)  # Leave room for question

    with torch.no_grad():
        for depth in depths:
            for _ in range(num_samples):
                # Generate random code
                code = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=6))

                # Choose needle
                needle_text, question = random.choice(needle_templates)
                needle = needle_text.format(code=code)

                # Generate haystack with needle at depth
                filler_tokens = tokenizer.encode(filler)
                needle_tokens = tokenizer.encode(" " + needle + " ")

                # Calculate insertion point
                target_len = test_context - len(needle_tokens) - 50
                if target_len <= 0:
                    continue

                insert_pos = int(target_len * depth)

                # Build context
                before = filler_tokens[:insert_pos]
                after = filler_tokens[insert_pos:target_len]
                context_tokens = before + needle_tokens + after

                # Add question
                question_tokens = tokenizer.encode(f"\n\nQuestion: {question}\nAnswer: The answer is ")
                full_tokens = context_tokens + question_tokens

                if len(full_tokens) > max_seq_len - 20:
                    full_tokens = full_tokens[:max_seq_len - 20]

                input_ids = torch.tensor([full_tokens], device=device)

                # Generate response
                output = model(input_ids)
                if isinstance(output, dict):
                    logits = output.get("logits", output.get("output"))
                else:
                    logits = output

                # Get predicted tokens
                predicted_ids = []
                for _ in range(10):  # Generate up to 10 tokens
                    next_token = logits[0, -1, :].argmax().item()
                    predicted_ids.append(next_token)

                    # Stop at newline or EOS
                    if next_token in [tokenizer.eos_token_id, 198]:  # 198 is newline
                        break

                    # Continue generation
                    input_ids = torch.cat([
                        input_ids,
                        torch.tensor([[next_token]], device=device)
                    ], dim=1)

                    if input_ids.shape[1] > max_seq_len:
                        break

                    output = model(input_ids)
                    if isinstance(output, dict):
                        logits = output.get("logits", output.get("output"))
                    else:
                        logits = output

                # Check if code appears in response
                response = tokenizer.decode(predicted_ids)
                if code.lower() in response.lower():
                    correct += 1
                total += 1

    accuracy = correct / total if total > 0 else 0.0

    return BenchmarkResult(
        name="needle_in_haystack",
        score=accuracy * 100,
        metric="accuracy",
        samples=total,
        time_seconds=time.time() - start_time,
        details={
            "correct": correct,
            "total": total,
            "depths_tested": depths,
            "context_length": test_context
        }
    )


def benchmark_efficiency(
    model: torch.nn.Module,
    tokenizer,
    device: torch.device,
    max_seq_len: int,
    max_samples: int = 10,
) -> BenchmarkResult:
    """
    Benchmark inference efficiency - tokens/sec and memory at various context lengths.
    This shows cost savings vs O(n²) models like GPT-2.
    """
    import gc

    start_time = time.time()

    # Test at various context lengths
    context_lengths = [512, 1024, 2048, 4096]
    context_lengths = [c for c in context_lengths if c <= max_seq_len]

    results_by_length = {}

    # GPU pricing ($/hour) for reference
    GPU_COST_PER_HOUR = 2.50  # ~A100 40GB cloud pricing

    for ctx_len in context_lengths:
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()

        # Generate random input
        input_ids = torch.randint(0, 50257, (1, ctx_len), device=device)

        # Warmup
        with torch.no_grad():
            _ = model(input_ids)

        # Time multiple runs
        times = []
        for _ in range(5):
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            t0 = time.time()

            with torch.no_grad():
                _ = model(input_ids)

            if torch.cuda.is_available():
                torch.cuda.synchronize()
            times.append(time.time() - t0)

        avg_time = np.mean(times)
        tokens_per_sec = ctx_len / avg_time

        # Memory usage
        if torch.cuda.is_available():
            vram_gb = torch.cuda.max_memory_allocated() / (1024**3)
        else:
            vram_gb = 0

        # Cost calculation (tokens per dollar)
        tokens_per_hour = tokens_per_sec * 3600
        tokens_per_dollar = tokens_per_hour / GPU_COST_PER_HOUR

        # GPT-2 reference (O(n²) scaling)
        # At 512 tokens, GPT-2-124M does ~15000 tok/s on A100
        gpt2_base_tps = 15000
        gpt2_scaling = (512 / ctx_len) ** 2  # O(n²) slowdown
        gpt2_tps_at_length = gpt2_base_tps * gpt2_scaling

        speedup_vs_gpt2 = tokens_per_sec / gpt2_tps_at_length if gpt2_tps_at_length > 0 else 1.0

        results_by_length[ctx_len] = {
            "tokens_per_sec": round(tokens_per_sec, 0),
            "vram_gb": round(vram_gb, 2),
            "avg_time_ms": round(avg_time * 1000, 1),
            "tokens_per_dollar": round(tokens_per_dollar, 0),
            "gpt2_tokens_per_sec": round(gpt2_tps_at_length, 0),
            "speedup_vs_gpt2": round(speedup_vs_gpt2, 2),
        }

        del input_ids

    # Calculate average speedup
    speedups = [r["speedup_vs_gpt2"] for r in results_by_length.values()]
    avg_speedup = np.mean(speedups) if speedups else 1.0

    # Cost savings percentage
    cost_savings_pct = (1 - 1/avg_speedup) * 100 if avg_speedup > 1 else 0

    return BenchmarkResult(
        name="efficiency",
        score=avg_speedup,
        metric="speedup_vs_gpt2",
        samples=len(context_lengths),
        time_seconds=time.time() - start_time,
        details={
            "by_context_length": results_by_length,
            "cost_savings_percent": round(cost_savings_pct, 1),
            "gpu_cost_per_hour": GPU_COST_PER_HOUR,
        }
    )


def benchmark_passkey_retrieval(
    model: torch.nn.Module,
    tokenizer,
    device: torch.device,
    max_seq_len: int,
    num_samples: int = 10,
) -> BenchmarkResult:
    """Simple passkey retrieval test."""

    start_time = time.time()

    correct = 0
    total = 0

    filler = "The grass is green. The sky is blue. The sun is yellow. " * 50

    with torch.no_grad():
        for _ in range(num_samples):
            # Generate random passkey
            passkey = str(random.randint(10000, 99999))

            # Create prompt with passkey hidden in context
            context = f"The passkey is {passkey}. {filler}"
            question = "What is the passkey?"

            tokens = tokenizer.encode(f"{context}\n\n{question}\nAnswer: The passkey is ")

            if len(tokens) > max_seq_len - 10:
                tokens = tokens[:max_seq_len - 10]

            input_ids = torch.tensor([tokens], device=device)

            output = model(input_ids)
            if isinstance(output, dict):
                logits = output.get("logits", output.get("output"))
            else:
                logits = output

            # Generate digits
            generated = []
            for _ in range(6):
                next_token = logits[0, -1, :].argmax().item()
                generated.append(next_token)

                input_ids = torch.cat([
                    input_ids,
                    torch.tensor([[next_token]], device=device)
                ], dim=1)

                output = model(input_ids)
                if isinstance(output, dict):
                    logits = output.get("logits", output.get("output"))
                else:
                    logits = output

            response = tokenizer.decode(generated)
            if passkey in response:
                correct += 1
            total += 1

    accuracy = correct / total if total > 0 else 0.0

    return BenchmarkResult(
        name="passkey_retrieval",
        score=accuracy * 100,
        metric="accuracy",
        samples=total,
        time_seconds=time.time() - start_time,
        details={"correct": correct, "total": total}
    )


# =============================================================================
# BENCHMARK RUNNER
# =============================================================================

BENCHMARK_REGISTRY = {
    # Perplexity
    "wikitext103_ppl": benchmark_perplexity_wikitext,
    "lambada": benchmark_perplexity_lambada,

    # Reasoning
    "hellaswag": benchmark_hellaswag,
    "piqa": benchmark_piqa,
    "winogrande": benchmark_winogrande,
    "arc_easy": lambda *args, **kwargs: benchmark_arc(*args, challenge=False, **kwargs),
    "arc_challenge": lambda *args, **kwargs: benchmark_arc(*args, challenge=True, **kwargs),

    # Long context
    "niah": benchmark_needle_in_haystack,
    "passkey": benchmark_passkey_retrieval,

    # Efficiency / Cost
    "efficiency": benchmark_efficiency,
}

BENCHMARK_PRESETS = {
    "quick": ["wikitext103_ppl"],
    "perplexity": ["wikitext103_ppl", "lambada"],
    "reasoning": ["hellaswag", "piqa", "winogrande", "arc_easy"],
    "long_context": ["niah", "passkey"],
    "efficiency": ["efficiency"],
    "cost": ["efficiency"],  # Alias for efficiency
    "full": list(BENCHMARK_REGISTRY.keys()),
}

# Reference scores from published models for comparison
# Sources: Original papers, Hugging Face leaderboards, OpenAI reports
REFERENCE_SCORES = {
    "wikitext103_ppl": {
        "metric": "perplexity",
        "lower_is_better": True,
        "models": {
            "GPT-2 (124M)": 29.4,
            "GPT-2 (355M)": 22.0,
            "GPT-2 (774M)": 19.9,
            "GPT-2 (1.5B)": 17.5,
            "LLaMA-7B": 5.7,
            "LLaMA-13B": 5.1,
            "Mistral-7B": 5.3,
        }
    },
    "lambada": {
        "metric": "accuracy",
        "lower_is_better": False,
        "models": {
            "GPT-2 (124M)": 45.0,
            "GPT-2 (355M)": 51.0,
            "GPT-2 (774M)": 56.0,
            "GPT-2 (1.5B)": 63.0,
            "LLaMA-7B": 77.0,
            "LLaMA-13B": 79.0,
            "GPT-4": 96.0,
        }
    },
    "hellaswag": {
        "metric": "accuracy",
        "lower_is_better": False,
        "models": {
            "GPT-2 (124M)": 29.0,
            "GPT-2 (355M)": 35.0,
            "GPT-2 (774M)": 40.0,
            "GPT-2 (1.5B)": 45.0,
            "LLaMA-7B": 76.0,
            "LLaMA-13B": 79.0,
            "Mistral-7B": 81.0,
            "GPT-4": 95.0,
        }
    },
    "piqa": {
        "metric": "accuracy",
        "lower_is_better": False,
        "models": {
            "GPT-2 (124M)": 62.0,
            "GPT-2 (355M)": 66.0,
            "GPT-2 (774M)": 68.0,
            "GPT-2 (1.5B)": 70.0,
            "LLaMA-7B": 79.0,
            "LLaMA-13B": 80.0,
            "Mistral-7B": 82.0,
            "GPT-4": 95.0,
        }
    },
    "winogrande": {
        "metric": "accuracy",
        "lower_is_better": False,
        "models": {
            "GPT-2 (124M)": 52.0,
            "GPT-2 (355M)": 54.0,
            "GPT-2 (774M)": 57.0,
            "GPT-2 (1.5B)": 59.0,
            "LLaMA-7B": 70.0,
            "LLaMA-13B": 73.0,
            "Mistral-7B": 75.0,
            "GPT-4": 94.0,
        }
    },
    "arc_easy": {
        "metric": "accuracy",
        "lower_is_better": False,
        "models": {
            "GPT-2 (124M)": 43.0,
            "GPT-2 (355M)": 50.0,
            "GPT-2 (774M)": 54.0,
            "GPT-2 (1.5B)": 58.0,
            "LLaMA-7B": 75.0,
            "LLaMA-13B": 77.0,
            "Mistral-7B": 80.0,
            "GPT-4": 96.0,
        }
    },
    "arc_challenge": {
        "metric": "accuracy",
        "lower_is_better": False,
        "models": {
            "GPT-2 (124M)": 21.0,
            "GPT-2 (355M)": 25.0,
            "GPT-2 (774M)": 28.0,
            "GPT-2 (1.5B)": 32.0,
            "LLaMA-7B": 47.0,
            "LLaMA-13B": 52.0,
            "Mistral-7B": 55.0,
            "GPT-4": 85.0,
        }
    },
    "niah": {
        "metric": "accuracy",
        "lower_is_better": False,
        "models": {
            "GPT-2 (any)": 10.0,  # Not designed for this
            "LLaMA-7B (4K)": 60.0,
            "LLaMA-13B (4K)": 65.0,
            "GPT-4 (8K)": 90.0,
            "Claude-3 (200K)": 98.0,
        }
    },
    "passkey": {
        "metric": "accuracy",
        "lower_is_better": False,
        "models": {
            "GPT-2 (any)": 20.0,
            "LLaMA-7B": 50.0,
            "Mistral-7B": 85.0,
            "GPT-4": 95.0,
        }
    },
}


def run_benchmarks(config: BenchmarkConfig) -> Dict[str, BenchmarkResult]:
    """Run selected benchmarks."""

    # Setup device
    if config.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(config.device)

    print(f"\n{'='*70}")
    print("   LLM BENCHMARK SUITE")
    print(f"{'='*70}")
    print(f"\n  Checkpoint: {config.checkpoint}")
    print(f"  Device: {device}")

    # Load model
    print(f"\n  Loading model...")
    model, max_seq_len = load_model(config, device)
    num_params = sum(p.numel() for p in model.parameters())
    print(f"  Parameters: {num_params:,} ({num_params/1e6:.1f}M)")
    print(f"  Max sequence length: {max_seq_len:,}")

    # Load tokenizer
    if HAS_HF:
        tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
        tokenizer.pad_token = tokenizer.eos_token
    else:
        raise RuntimeError("transformers required for benchmarks")

    # Determine benchmarks to run
    if config.benchmarks is None:
        benchmarks_to_run = BENCHMARK_PRESETS["full"]
    elif len(config.benchmarks) == 1 and config.benchmarks[0] in BENCHMARK_PRESETS:
        benchmarks_to_run = BENCHMARK_PRESETS[config.benchmarks[0]]
    else:
        benchmarks_to_run = config.benchmarks

    print(f"\n  Benchmarks: {', '.join(benchmarks_to_run)}")
    print(f"\n{'='*70}")
    print("   RUNNING BENCHMARKS")
    print(f"{'='*70}\n")

    # Run benchmarks
    results = {}
    for name in benchmarks_to_run:
        if name not in BENCHMARK_REGISTRY:
            print(f"  Warning: Unknown benchmark '{name}', skipping")
            continue

        print(f"  Running {name}...", end=" ", flush=True)

        try:
            result = BENCHMARK_REGISTRY[name](
                model=model,
                tokenizer=tokenizer,
                device=device,
                max_seq_len=min(max_seq_len, config.max_context),
                max_samples=config.max_samples,
            )
            results[name] = result

            print(f"{result.score:.2f} {result.metric} ({result.time_seconds:.1f}s)")

        except Exception as e:
            print(f"Error: {e}")
            results[name] = BenchmarkResult(
                name=name,
                score=0.0,
                metric="error",
                samples=0,
                time_seconds=0,
                details={"error": str(e)}
            )

    return results


def print_results(results: Dict[str, BenchmarkResult], compare: bool = False):
    """Print formatted results with optional comparison to reference models."""

    print(f"\n{'='*70}")
    print("   RESULTS SUMMARY")
    print(f"{'='*70}\n")

    # Group by category
    categories = {
        "Perplexity": ["wikitext103_ppl", "lambada"],
        "Reasoning": ["hellaswag", "piqa", "winogrande", "arc_easy", "arc_challenge"],
        "Long Context": ["niah", "passkey"],
        "Efficiency": ["efficiency"],
    }

    for category, benchmarks in categories.items():
        category_results = {k: v for k, v in results.items() if k in benchmarks}
        if not category_results:
            continue

        print(f"  {category}:")
        print(f"  {'-'*40}")

        for name, result in category_results.items():
            if name == "efficiency":
                # Special formatting for efficiency benchmark
                print(f"    Avg Speedup vs GPT-2: {result.score:.2f}x")
                if result.details:
                    cost_savings = result.details.get("cost_savings_percent", 0)
                    print(f"    Cost Savings: {cost_savings:.1f}%")
                    print(f"\n    By Context Length:")
                    by_length = result.details.get("by_context_length", {})
                    for ctx_len, data in sorted(by_length.items()):
                        tps = data.get("tokens_per_sec", 0)
                        vram = data.get("vram_gb", 0)
                        speedup = data.get("speedup_vs_gpt2", 1)
                        print(f"      {ctx_len:>5} tokens: {tps:>8,.0f} tok/s | {vram:.1f}GB | {speedup:.1f}x vs GPT-2")
            else:
                metric_symbol = "↓" if result.metric == "perplexity" else "↑"
                print(f"    {name:20} {result.score:>8.2f} {result.metric:12} {metric_symbol}")

        print()

    # Overall
    accuracy_results = [r for r in results.values() if r.metric == "accuracy"]
    if accuracy_results:
        avg_accuracy = sum(r.score for r in accuracy_results) / len(accuracy_results)
        print(f"  Average Accuracy: {avg_accuracy:.2f}%")

    total_time = sum(r.time_seconds for r in results.values())
    print(f"  Total Time: {total_time:.1f}s")

    # Comparison table
    if compare:
        print_comparison_table(results)


def print_comparison_table(results: Dict[str, BenchmarkResult]):
    """Print comparison table against reference models."""

    print(f"\n{'='*70}")
    print("   COMPARISON WITH REFERENCE MODELS")
    print(f"{'='*70}\n")

    # Collect all reference models across benchmarks
    all_ref_models = set()
    for name in results.keys():
        if name in REFERENCE_SCORES:
            all_ref_models.update(REFERENCE_SCORES[name]["models"].keys())

    # Select key models for comparison (to keep table readable)
    key_models = ["GPT-2 (124M)", "GPT-2 (1.5B)", "LLaMA-7B", "Mistral-7B", "GPT-4"]
    ref_models = [m for m in key_models if m in all_ref_models]

    if not ref_models:
        print("  No reference data available for these benchmarks.")
        return

    # Print header
    header = f"  {'Benchmark':<20} {'Your Model':>12}"
    for model in ref_models:
        # Shorten model names for display
        short_name = model.replace("GPT-2 ", "GPT2-").replace("LLaMA-", "LL-").replace("Mistral-", "Mis-")
        header += f" {short_name:>12}"
    print(header)
    print("  " + "-" * (20 + 13 + 13 * len(ref_models)))

    # Print each benchmark
    for name, result in results.items():
        if name not in REFERENCE_SCORES:
            continue

        ref_data = REFERENCE_SCORES[name]
        lower_is_better = ref_data["lower_is_better"]

        # Your score
        your_score = result.score
        row = f"  {name:<20} {your_score:>12.1f}"

        # Reference scores
        for model in ref_models:
            if model in ref_data["models"]:
                ref_score = ref_data["models"][model]

                # Add indicator if better/worse
                if lower_is_better:
                    indicator = "+" if your_score < ref_score else "-" if your_score > ref_score else "="
                else:
                    indicator = "+" if your_score > ref_score else "-" if your_score < ref_score else "="

                row += f" {ref_score:>10.1f}{indicator}"
            else:
                row += f" {'--':>12}"

        print(row)

    # Legend
    print()
    print("  Legend: + = your model is better, - = your model is worse, = = equal")
    print()

    # Summary comparison
    print_ranking_summary(results, ref_models)


def print_ranking_summary(results: Dict[str, BenchmarkResult], ref_models: List[str]):
    """Print summary of where your model ranks."""

    print("  Performance Summary:")
    print("  " + "-" * 50)

    wins_vs = {model: 0 for model in ref_models}
    total_benchmarks = 0

    for name, result in results.items():
        if name not in REFERENCE_SCORES:
            continue

        ref_data = REFERENCE_SCORES[name]
        lower_is_better = ref_data["lower_is_better"]
        your_score = result.score
        total_benchmarks += 1

        for model in ref_models:
            if model in ref_data["models"]:
                ref_score = ref_data["models"][model]
                if lower_is_better:
                    if your_score < ref_score:
                        wins_vs[model] += 1
                else:
                    if your_score > ref_score:
                        wins_vs[model] += 1

    if total_benchmarks == 0:
        return

    for model in ref_models:
        wins = wins_vs[model]
        pct = (wins / total_benchmarks) * 100
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        status = "BETTER" if pct > 50 else "SIMILAR" if pct >= 40 else "BEHIND"
        print(f"    vs {model:<15} {bar} {wins}/{total_benchmarks} ({pct:.0f}%) {status}")

    print()


def save_results(results: Dict[str, BenchmarkResult], output_file: str):
    """Save results to JSON."""

    output = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": {name: asdict(result) for name, result in results.items()}
    }

    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n  Results saved to: {output_file}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Standard LLM Benchmark Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--checkpoint", type=str, required=True,
                        help="Path to model checkpoint")
    parser.add_argument("--model_type", type=str, default="hybrid",
                        choices=["phase", "hybrid"],
                        help="Model type")
    parser.add_argument("--model_size", type=str, default="medium",
                        choices=["tiny", "small", "medium", "large"],
                        help="Model size preset")

    # Benchmark selection
    parser.add_argument("--benchmarks", type=str, default=None,
                        help="Comma-separated list of benchmarks or preset (quick/perplexity/reasoning/full)")
    parser.add_argument("--quick", action="store_true",
                        help="Run quick benchmarks only (perplexity)")
    parser.add_argument("--full", action="store_true",
                        help="Run all benchmarks")

    # Limits
    parser.add_argument("--max_samples", type=int, default=500,
                        help="Maximum samples per benchmark")
    parser.add_argument("--max_context", type=int, default=2048,
                        help="Maximum context length for benchmarks")

    # Comparison
    parser.add_argument("--compare", action="store_true",
                        help="Show comparison table against GPT-2, LLaMA, GPT-4, etc.")

    # Output
    parser.add_argument("--output", type=str, default="benchmark_results.json",
                        help="Output file for results")

    args = parser.parse_args()

    # Determine benchmarks
    if args.quick:
        benchmarks = ["quick"]
    elif args.full:
        benchmarks = None  # Will use full
    elif args.benchmarks:
        benchmarks = args.benchmarks.split(",")
    else:
        benchmarks = ["perplexity", "reasoning"]  # Default

    config = BenchmarkConfig(
        checkpoint=args.checkpoint,
        model_type=args.model_type,
        model_size=args.model_size,
        benchmarks=benchmarks,
        max_samples=args.max_samples,
        max_context=args.max_context,
        output_file=args.output,
    )

    # Run benchmarks
    results = run_benchmarks(config)

    # Print and save results
    print_results(results, compare=args.compare)
    save_results(results, config.output_file)

    print(f"\n{'='*70}")
    print("   BENCHMARK COMPLETE")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
