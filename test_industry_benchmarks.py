#!/usr/bin/env python3
"""
Industry-Standard Long-Context Benchmarks for Phase Attention
==============================================================

These tests go beyond standard benchmarks to demonstrate revolutionary
capabilities that would "shock" the industry:

1. MULTI-NEEDLE REASONING: Hide 3+ facts, ask model to combine them
2. THROUGHPUT DECAY: Measure if tok/s stays constant as context grows
3. ULTRA-LONG MEMORY: Test 128K, 1M, 10M token contexts
4. DEPTH FLATNESS: Prove no "lost in the middle" problem

Target Metrics:
- 128K context: >85% retrieval (matches GPT-4o, Llama 3.1)
- 1M context: Functional retrieval (matches Gemini 1.5 Pro)
- 10M context: Complete forward pass without OOM
- 0% throughput decay: Same tok/s at 1K and 1M context
- Flat depth accuracy: Same accuracy at 5%, 50%, 95% depth

Author: SymbolU Team
Date: December 2025
"""

import argparse
import gc
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn.functional as F
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from symbolu.phase_transformer import PhaseTransformer, HybridPhaseTransformer

try:
    from transformers import GPT2Tokenizer
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False


# =============================================================================
# CONFIGURATION
# =============================================================================

MODEL_PRESETS = {
    "tiny": {"embed_dim": 256, "num_layers": 4, "num_heads": 4, "ff_dim": 1024},
    "small": {"embed_dim": 512, "num_layers": 8, "num_heads": 8, "ff_dim": 2048},
    "medium": {"embed_dim": 768, "num_layers": 12, "num_heads": 12, "ff_dim": 3072},
    "large": {"embed_dim": 1024, "num_layers": 24, "num_heads": 16, "ff_dim": 4096},
}


# =============================================================================
# TEST 1: ULTRA-LONG MEMORY TEST
# =============================================================================

def test_ultra_long_memory(
    model_type: str = "hybrid",
    model_size: str = "small",
    context_lengths: List[int] = None,
    device: str = "cuda",
    gradient_checkpointing: bool = True,
) -> Dict:
    """
    Test if model can process ultra-long contexts without OOM.

    This is the ultimate O(n) proof - if we can process 1M+ tokens
    on a single A100 80GB, we've achieved something revolutionary.
    """
    if context_lengths is None:
        context_lengths = [
            32_768,      # 32K - Baseline
            65_536,      # 64K
            131_072,     # 128K - Enterprise standard
            262_144,     # 256K
            524_288,     # 512K
            1_048_576,   # 1M - Breakthrough tier
            # 10_000_000,  # 10M - Infinite tier (uncomment if you dare!)
        ]

    print(f"\n{'='*70}")
    print("   ULTRA-LONG MEMORY TEST")
    print("   Testing O(n) Memory Scaling")
    print(f"{'='*70}")

    preset = MODEL_PRESETS[model_size]
    results = {
        "test": "ultra_long_memory",
        "model_type": model_type,
        "model_size": model_size,
        "results": [],
    }

    for ctx_len in context_lengths:
        gc.collect()
        torch.cuda.empty_cache()

        print(f"\n  Testing {ctx_len:,} tokens...")

        try:
            # Create model with this context length
            if model_type == "phase":
                model = PhaseTransformer(
                    vocab_size=50257,
                    embed_dim=preset["embed_dim"],
                    num_layers=preset["num_layers"],
                    num_heads=preset["num_heads"],
                    ff_dim=preset["ff_dim"],
                    max_seq_len=ctx_len + 1024,
                    dropout=0.0,
                )
            else:
                model = HybridPhaseTransformer(
                    vocab_size=50257,
                    embed_dim=preset["embed_dim"],
                    num_layers=preset["num_layers"],
                    num_heads=preset["num_heads"],
                    ff_dim=preset["ff_dim"],
                    max_seq_len=ctx_len + 1024,
                    dropout=0.0,
                    local_layers=2,
                    window_size=256,
                )

            # Enable gradient checkpointing
            if gradient_checkpointing:
                for module in model.modules():
                    if hasattr(module, 'gradient_checkpointing'):
                        module.gradient_checkpointing = True

            model = model.to(device).eval()

            # Create random input
            input_ids = torch.randint(0, 50257, (1, ctx_len), device=device)

            # Time the forward pass
            torch.cuda.synchronize()
            start_time = time.time()

            with torch.no_grad():
                output = model(input_ids)

            torch.cuda.synchronize()
            elapsed = time.time() - start_time

            # Get memory usage
            vram_gb = torch.cuda.max_memory_allocated() / (1024**3)
            tok_per_sec = ctx_len / elapsed

            result = {
                "context_length": ctx_len,
                "status": "SUCCESS",
                "vram_gb": round(vram_gb, 2),
                "time_sec": round(elapsed, 2),
                "tokens_per_sec": round(tok_per_sec, 0),
            }

            print(f"    ✓ SUCCESS | VRAM: {vram_gb:.1f}GB | Time: {elapsed:.1f}s | {tok_per_sec:,.0f} tok/s")

            # Cleanup
            del model, input_ids, output

        except torch.cuda.OutOfMemoryError as e:
            result = {
                "context_length": ctx_len,
                "status": "OOM",
                "error": str(e)[:100],
            }
            print(f"    ✗ OOM at {ctx_len:,} tokens")

        except Exception as e:
            result = {
                "context_length": ctx_len,
                "status": "ERROR",
                "error": str(e)[:100],
            }
            print(f"    ✗ ERROR: {str(e)[:50]}")

        results["results"].append(result)
        gc.collect()
        torch.cuda.empty_cache()

        # Stop if we hit OOM
        if result["status"] == "OOM":
            print(f"\n  Stopping - OOM reached at {ctx_len:,} tokens")
            break

    return results


# =============================================================================
# TEST 2: THROUGHPUT DECAY TEST
# =============================================================================

def test_throughput_decay(
    model_type: str = "hybrid",
    model_size: str = "small",
    context_lengths: List[int] = None,
    num_iterations: int = 3,
    device: str = "cuda",
) -> Dict:
    """
    Test if throughput (tok/s) stays constant as context grows.

    The Goal: 0% decay - same speed at 1K and 1M context.
    This proves true O(n) complexity.
    """
    if context_lengths is None:
        context_lengths = [1024, 2048, 4096, 8192, 16384, 32768]

    print(f"\n{'='*70}")
    print("   THROUGHPUT DECAY TEST")
    print("   Measuring Tokens/Sec vs Context Length")
    print(f"{'='*70}")

    preset = MODEL_PRESETS[model_size]
    max_ctx = max(context_lengths)

    # Create model once
    if model_type == "phase":
        model = PhaseTransformer(
            vocab_size=50257,
            embed_dim=preset["embed_dim"],
            num_layers=preset["num_layers"],
            num_heads=preset["num_heads"],
            ff_dim=preset["ff_dim"],
            max_seq_len=max_ctx + 1024,
            dropout=0.0,
        )
    else:
        model = HybridPhaseTransformer(
            vocab_size=50257,
            embed_dim=preset["embed_dim"],
            num_layers=preset["num_layers"],
            num_heads=preset["num_heads"],
            ff_dim=preset["ff_dim"],
            max_seq_len=max_ctx + 1024,
            dropout=0.0,
            local_layers=2,
            window_size=256,
        )

    model = model.to(device).eval()

    results = {
        "test": "throughput_decay",
        "model_type": model_type,
        "model_size": model_size,
        "results": [],
    }

    baseline_tok_per_sec = None

    for ctx_len in context_lengths:
        times = []

        for _ in range(num_iterations):
            gc.collect()
            torch.cuda.empty_cache()

            input_ids = torch.randint(0, 50257, (1, ctx_len), device=device)

            # Warmup
            with torch.no_grad():
                _ = model(input_ids)

            torch.cuda.synchronize()
            start_time = time.time()

            with torch.no_grad():
                _ = model(input_ids)

            torch.cuda.synchronize()
            times.append(time.time() - start_time)

            del input_ids

        avg_time = np.mean(times)
        tok_per_sec = ctx_len / avg_time

        if baseline_tok_per_sec is None:
            baseline_tok_per_sec = tok_per_sec
            decay_pct = 0.0
        else:
            decay_pct = (1 - tok_per_sec / baseline_tok_per_sec) * 100

        result = {
            "context_length": ctx_len,
            "avg_time_sec": round(avg_time, 4),
            "tokens_per_sec": round(tok_per_sec, 0),
            "decay_percent": round(decay_pct, 1),
        }
        results["results"].append(result)

        bar = "█" * int(tok_per_sec / baseline_tok_per_sec * 20) if baseline_tok_per_sec else ""
        print(f"  {ctx_len:>6} tokens | {tok_per_sec:>8,.0f} tok/s | Decay: {decay_pct:>5.1f}% | {bar}")

    # Calculate overall decay
    first = results["results"][0]["tokens_per_sec"]
    last = results["results"][-1]["tokens_per_sec"]
    overall_decay = (1 - last / first) * 100

    results["summary"] = {
        "baseline_tok_per_sec": first,
        "final_tok_per_sec": last,
        "overall_decay_percent": round(overall_decay, 1),
        "is_zero_decay": overall_decay < 5,  # <5% is essentially zero
    }

    print(f"\n  Overall Decay: {overall_decay:.1f}%")
    print(f"  Zero Decay Achieved: {'YES ✓' if overall_decay < 5 else 'NO ✗'}")

    return results


# =============================================================================
# TEST 3: MULTI-NEEDLE REASONING
# =============================================================================

def generate_multi_needle_test(
    num_needles: int = 3,
    context_length: int = 32768,
    tokenizer = None,
) -> Tuple[str, str, str]:
    """
    Generate a multi-needle reasoning test.

    Hide N facts in different parts of the context and ask
    the model to combine them.
    """
    import random

    # Generate random facts
    colors = ["red", "blue", "green", "yellow", "purple", "orange"]
    numbers = list(range(100, 999))
    animals = ["lion", "tiger", "bear", "wolf", "eagle", "shark"]

    facts = []
    for i in range(num_needles):
        color = random.choice(colors)
        number = random.choice(numbers)
        animal = random.choice(animals)
        facts.append({
            "needle": f"FACT{i+1}: The {color} {animal} has code {number}.",
            "color": color,
            "number": number,
            "animal": animal,
        })

    # Generate filler text
    filler_sentences = [
        "The market showed strong performance in the third quarter.",
        "Researchers discovered new applications for machine learning.",
        "The conference attracted participants from over fifty countries.",
        "Climate data indicates significant changes in weather patterns.",
        "New technologies are transforming the healthcare industry.",
        "Education systems are adapting to digital learning platforms.",
        "Urban development continues to reshape major metropolitan areas.",
        "Scientific collaboration has accelerated breakthrough discoveries.",
    ]

    # Build context with needles at different depths
    context_parts = []
    target_tokens = context_length
    current_tokens = 0

    # Place needles at roughly 10%, 50%, 90% depth
    needle_positions = [0.1, 0.5, 0.9]
    needles_placed = 0

    while current_tokens < target_tokens and needles_placed < num_needles:
        # Add filler
        filler = " ".join(random.choices(filler_sentences, k=10))
        context_parts.append(filler)
        current_tokens += len(filler.split()) * 1.3  # Rough token estimate

        # Check if we should place a needle
        progress = current_tokens / target_tokens
        if needles_placed < len(needle_positions) and progress >= needle_positions[needles_placed]:
            context_parts.append(facts[needles_placed]["needle"])
            needles_placed += 1

    context = " ".join(context_parts)

    # Generate question that requires combining facts
    if num_needles >= 2:
        question = f"What is the sum of the codes for the {facts[0]['color']} {facts[0]['animal']} and the {facts[1]['color']} {facts[1]['animal']}?"
        answer = str(facts[0]['number'] + facts[1]['number'])
    else:
        question = f"What is the code for the {facts[0]['color']} {facts[0]['animal']}?"
        answer = str(facts[0]['number'])

    return context, question, answer


def test_multi_needle_reasoning(
    model_type: str = "hybrid",
    model_size: str = "small",
    context_lengths: List[int] = None,
    num_needles: int = 3,
    num_samples: int = 5,
    device: str = "cuda",
    checkpoint_path: str = None,
) -> Dict:
    """
    Test multi-needle reasoning capability using perplexity scoring.

    For each test:
    1. Generate context with N hidden facts
    2. Score the correct answer vs random wrong answers
    3. Success = correct answer has lowest perplexity

    This works even without a fully trained model by measuring
    if the model attends to the right parts of the context.
    """
    if context_lengths is None:
        context_lengths = [4096, 8192, 16384, 32768]

    if not HAS_TRANSFORMERS:
        print("  ✗ Requires transformers library")
        return {"test": "multi_needle_reasoning", "error": "no transformers"}

    print(f"\n{'='*70}")
    print("   MULTI-NEEDLE REASONING TEST")
    print(f"   {num_needles} Needles, Perplexity Scoring")
    print(f"{'='*70}")

    tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
    tokenizer.pad_token = tokenizer.eos_token

    preset = MODEL_PRESETS[model_size]
    max_ctx = max(context_lengths)

    # Create model
    if model_type == "phase":
        model = PhaseTransformer(
            vocab_size=50257,
            embed_dim=preset["embed_dim"],
            num_layers=preset["num_layers"],
            num_heads=preset["num_heads"],
            ff_dim=preset["ff_dim"],
            max_seq_len=max_ctx + 2048,
            dropout=0.0,
        )
    else:
        model = HybridPhaseTransformer(
            vocab_size=50257,
            embed_dim=preset["embed_dim"],
            num_layers=preset["num_layers"],
            num_heads=preset["num_heads"],
            ff_dim=preset["ff_dim"],
            max_seq_len=max_ctx + 2048,
            dropout=0.0,
            local_layers=2,
            window_size=256,
        )

    # Load checkpoint if available
    if checkpoint_path and os.path.exists(checkpoint_path):
        print(f"  Loading checkpoint: {checkpoint_path}")
        checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=True)
        model.load_state_dict(checkpoint["model_state_dict"])

    model = model.to(device).eval()

    results = {
        "test": "multi_needle_reasoning",
        "num_needles": num_needles,
        "model_type": model_type,
        "checkpoint": checkpoint_path,
        "results": [],
    }

    for ctx_len in context_lengths:
        successes = 0

        for sample_idx in range(num_samples):
            context, question, correct_answer = generate_multi_needle_test(
                num_needles=num_needles,
                context_length=ctx_len,
                tokenizer=tokenizer,
            )

            # Build prompt
            prompt = context + f"\n\nQuestion: {question}\nAnswer: "

            # Generate wrong answers
            import random
            wrong_answers = [str(random.randint(100, 999)) for _ in range(3)]

            # Score each answer using perplexity
            def score_answer(answer_text):
                full_text = prompt + answer_text
                tokens = tokenizer.encode(full_text, return_tensors="pt", truncation=True, max_length=ctx_len + 100)
                tokens = tokens.to(device)

                if tokens.shape[1] > model.max_seq_len:
                    tokens = tokens[:, -model.max_seq_len:]

                with torch.no_grad():
                    outputs = model(tokens)
                    # Get loss on answer tokens
                    answer_tokens = tokenizer.encode(answer_text)
                    answer_len = len(answer_tokens)

                    if answer_len > 0:
                        logits = outputs[:, -(answer_len+1):-1, :]
                        targets = tokens[:, -answer_len:]
                        loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), targets.reshape(-1))
                        return loss.item()
                return float('inf')

            # Score correct and wrong answers
            try:
                correct_score = score_answer(correct_answer)
                wrong_scores = [score_answer(w) for w in wrong_answers]

                # Success if correct answer has lowest loss (perplexity)
                if correct_score < min(wrong_scores):
                    successes += 1

            except Exception as e:
                print(f"    Sample {sample_idx} error: {str(e)[:50]}")

        accuracy = successes / num_samples
        results["results"].append({
            "context_length": ctx_len,
            "accuracy": accuracy,
            "num_samples": num_samples,
        })

        status = "✓" if accuracy >= 0.5 else "✗"
        print(f"  {ctx_len:>6} tokens | Accuracy: {accuracy:.1%} {status}")

    # Cleanup
    del model
    gc.collect()
    torch.cuda.empty_cache()

    return results


# =============================================================================
# TEST 4: DEPTH FLATNESS TEST
# =============================================================================

def test_depth_flatness(
    model_type: str = "hybrid",
    model_size: str = "small",
    context_length: int = 16384,
    num_depths: int = 10,
    num_samples: int = 5,
    device: str = "cuda",
    checkpoint_path: str = None,
) -> Dict:
    """
    Test if accuracy is flat across all depths (no "lost in the middle").

    The Goal: Same accuracy at 5%, 50%, 95% depth.
    A flat heatmap proves the architecture has no depth bias.

    Method: Place a unique code at different depths, measure retrieval
    accuracy using perplexity scoring (correct code vs random codes).
    """
    import random

    if not HAS_TRANSFORMERS:
        print("  ✗ Requires transformers library")
        return {"test": "depth_flatness", "error": "no transformers"}

    print(f"\n{'='*70}")
    print("   DEPTH FLATNESS TEST")
    print(f"   Testing 'Lost in the Middle' Problem")
    print(f"{'='*70}")

    tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
    tokenizer.pad_token = tokenizer.eos_token

    preset = MODEL_PRESETS[model_size]

    # Create model
    if model_type == "phase":
        model = PhaseTransformer(
            vocab_size=50257,
            embed_dim=preset["embed_dim"],
            num_layers=preset["num_layers"],
            num_heads=preset["num_heads"],
            ff_dim=preset["ff_dim"],
            max_seq_len=context_length + 2048,
            dropout=0.0,
        )
    else:
        model = HybridPhaseTransformer(
            vocab_size=50257,
            embed_dim=preset["embed_dim"],
            num_layers=preset["num_layers"],
            num_heads=preset["num_heads"],
            ff_dim=preset["ff_dim"],
            max_seq_len=context_length + 2048,
            dropout=0.0,
            local_layers=2,
            window_size=256,
        )

    # Load checkpoint if available
    if checkpoint_path and os.path.exists(checkpoint_path):
        print(f"  Loading checkpoint: {checkpoint_path}")
        checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=True)
        model.load_state_dict(checkpoint["model_state_dict"])

    model = model.to(device).eval()

    depths = np.linspace(0.05, 0.95, num_depths)

    # Filler sentences for padding
    filler_sentences = [
        "The market showed strong performance in the third quarter.",
        "Researchers discovered new applications for machine learning.",
        "The conference attracted participants from over fifty countries.",
        "Climate data indicates significant changes in weather patterns.",
        "New technologies are transforming the healthcare industry.",
        "Education systems are adapting to digital learning platforms.",
        "Urban development continues to reshape major metropolitan areas.",
        "Scientific collaboration has accelerated breakthrough discoveries.",
    ]

    results = {
        "test": "depth_flatness",
        "context_length": context_length,
        "model_type": model_type,
        "checkpoint": checkpoint_path,
        "results": [],
    }

    for depth in depths:
        successes = 0

        for _ in range(num_samples):
            # Generate unique code
            secret_code = str(random.randint(1000, 9999))
            needle = f"SECRET: The magic number is {secret_code}."

            # Build context with needle at specific depth
            target_needle_pos = int(context_length * depth)
            context_parts = []
            current_tokens = 0

            needle_placed = False
            while current_tokens < context_length:
                filler = " ".join(random.choices(filler_sentences, k=5))
                filler_tokens = len(tokenizer.encode(filler))

                if not needle_placed and current_tokens >= target_needle_pos:
                    context_parts.append(needle)
                    needle_placed = True
                    current_tokens += len(tokenizer.encode(needle))
                else:
                    context_parts.append(filler)
                    current_tokens += filler_tokens

            context = " ".join(context_parts)
            prompt = context + "\n\nQuestion: What is the magic number?\nAnswer: "

            # Score correct vs wrong answers
            def score_answer(answer_text):
                full_text = prompt + answer_text
                tokens = tokenizer.encode(full_text, return_tensors="pt", truncation=True, max_length=context_length + 100)
                tokens = tokens.to(device)

                if tokens.shape[1] > model.max_seq_len:
                    tokens = tokens[:, -model.max_seq_len:]

                with torch.no_grad():
                    outputs = model(tokens)
                    answer_tokens = tokenizer.encode(answer_text)
                    answer_len = len(answer_tokens)

                    if answer_len > 0:
                        logits = outputs[:, -(answer_len+1):-1, :]
                        targets = tokens[:, -answer_len:]
                        loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), targets.reshape(-1))
                        return loss.item()
                return float('inf')

            try:
                correct_score = score_answer(secret_code)
                wrong_codes = [str(random.randint(1000, 9999)) for _ in range(3)]
                wrong_scores = [score_answer(w) for w in wrong_codes]

                if correct_score < min(wrong_scores):
                    successes += 1

            except Exception as e:
                pass  # Skip failed samples

        accuracy = successes / num_samples
        results["results"].append({
            "depth_percent": round(depth * 100, 1),
            "accuracy": accuracy,
        })

        bar = "█" * int(accuracy * 20)
        print(f"  Depth {depth*100:>5.1f}% | Accuracy: {accuracy:.1%} | {bar}")

    # Calculate flatness score (std dev of accuracies)
    accuracies = [r["accuracy"] for r in results["results"]]
    flatness_std = np.std(accuracies)
    mean_acc = np.mean(accuracies)

    results["summary"] = {
        "mean_accuracy": round(mean_acc, 3),
        "std_accuracy": round(flatness_std, 3),
        "is_flat": flatness_std < 0.15,  # <15% std dev is considered flat
        "min_accuracy": round(min(accuracies), 3),
        "max_accuracy": round(max(accuracies), 3),
    }

    print(f"\n  Mean Accuracy: {mean_acc:.1%}")
    print(f"  Flatness Score (StdDev): {flatness_std:.3f}")
    print(f"  Range: {min(accuracies):.1%} - {max(accuracies):.1%}")
    print(f"  Is Flat: {'YES ✓' if flatness_std < 0.15 else 'NO ✗'}")

    # Cleanup
    del model
    gc.collect()
    torch.cuda.empty_cache()

    return results


# =============================================================================
# TEST 5: MEMORY SCALING ANALYSIS
# =============================================================================

def test_memory_scaling(
    model_type: str = "hybrid",
    model_size: str = "small",
    context_lengths: List[int] = None,
    device: str = "cuda",
) -> Dict:
    """
    Analyze memory scaling to prove O(n) vs O(n²).

    O(n²) memory: Doubling context = 4x memory
    O(n) memory: Doubling context = 2x memory
    """
    if context_lengths is None:
        context_lengths = [1024, 2048, 4096, 8192, 16384, 32768]

    print(f"\n{'='*70}")
    print("   MEMORY SCALING ANALYSIS")
    print("   Proving O(n) vs O(n²)")
    print(f"{'='*70}")

    preset = MODEL_PRESETS[model_size]
    results = {
        "test": "memory_scaling",
        "model_type": model_type,
        "results": [],
    }

    for ctx_len in context_lengths:
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()

        if model_type == "phase":
            model = PhaseTransformer(
                vocab_size=50257,
                embed_dim=preset["embed_dim"],
                num_layers=preset["num_layers"],
                num_heads=preset["num_heads"],
                ff_dim=preset["ff_dim"],
                max_seq_len=ctx_len + 1024,
                dropout=0.0,
            )
        else:
            model = HybridPhaseTransformer(
                vocab_size=50257,
                embed_dim=preset["embed_dim"],
                num_layers=preset["num_layers"],
                num_heads=preset["num_heads"],
                ff_dim=preset["ff_dim"],
                max_seq_len=ctx_len + 1024,
                dropout=0.0,
                local_layers=2,
                window_size=256,
            )

        model = model.to(device).eval()
        input_ids = torch.randint(0, 50257, (1, ctx_len), device=device)

        torch.cuda.reset_peak_memory_stats()

        with torch.no_grad():
            _ = model(input_ids)

        vram_gb = torch.cuda.max_memory_allocated() / (1024**3)

        results["results"].append({
            "context_length": ctx_len,
            "vram_gb": round(vram_gb, 2),
        })

        del model, input_ids

    # Calculate scaling factor
    scaling_factors = []
    for i in range(1, len(results["results"])):
        ctx_ratio = results["results"][i]["context_length"] / results["results"][i-1]["context_length"]
        mem_ratio = results["results"][i]["vram_gb"] / results["results"][i-1]["vram_gb"]
        scaling_factors.append(mem_ratio / ctx_ratio)

    avg_scaling = np.mean(scaling_factors) if scaling_factors else 1.0

    # Print results
    print("\n  Context    | VRAM    | Expected O(n²) | Actual Ratio")
    print("  " + "-" * 55)

    baseline = results["results"][0]["vram_gb"]
    baseline_ctx = results["results"][0]["context_length"]

    for r in results["results"]:
        ctx = r["context_length"]
        vram = r["vram_gb"]

        # O(n²) expected (relative to baseline)
        on2_expected = baseline * (ctx / baseline_ctx) ** 2

        # Actual ratio
        actual_ratio = vram / baseline
        expected_ratio = (ctx / baseline_ctx)  # O(n) expected

        print(f"  {ctx:>7,} | {vram:>5.1f}GB | {on2_expected:>7.1f}GB      | {actual_ratio:.2f}x (O(n)={expected_ratio:.1f}x)")

    is_linear = avg_scaling < 1.5  # Should be ~1.0 for O(n)

    results["summary"] = {
        "avg_scaling_factor": round(avg_scaling, 2),
        "is_linear": is_linear,
        "complexity": "O(n)" if is_linear else "O(n²)",
    }

    print(f"\n  Average Scaling Factor: {avg_scaling:.2f}x (1.0 = perfect O(n))")
    print(f"  Complexity: {results['summary']['complexity']}")

    return results


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Industry-Standard Long-Context Benchmarks",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--test", type=str, default="all",
                       choices=["all", "scaling", "throughput", "ultra_long", "multi_needle", "depth"],
                       help="Which test to run")
    parser.add_argument("--model_type", type=str, default="hybrid",
                       choices=["phase", "hybrid"])
    parser.add_argument("--model_size", type=str, default="small",
                       choices=["tiny", "small", "medium", "large"])
    parser.add_argument("--checkpoint", type=str, default=None,
                       help="Path to model checkpoint (for multi_needle and depth tests)")
    parser.add_argument("--context_length", type=int, default=16384,
                       help="Context length for depth flatness test")
    parser.add_argument("--num_needles", type=int, default=3,
                       help="Number of needles for multi-needle test")
    parser.add_argument("--output", type=str, default="industry_benchmark_results.json")

    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"\n  Device: {device}")
    if device == "cuda":
        print(f"  GPU: {torch.cuda.get_device_name()}")
        print(f"  VRAM: {torch.cuda.get_device_properties(0).total_memory / (1024**3):.1f}GB")

    all_results = {}

    if args.test in ["all", "scaling"]:
        all_results["memory_scaling"] = test_memory_scaling(
            model_type=args.model_type,
            model_size=args.model_size,
            device=device,
        )

    if args.test in ["all", "throughput"]:
        all_results["throughput_decay"] = test_throughput_decay(
            model_type=args.model_type,
            model_size=args.model_size,
            device=device,
        )

    if args.test in ["all", "ultra_long"]:
        all_results["ultra_long"] = test_ultra_long_memory(
            model_type=args.model_type,
            model_size=args.model_size,
            device=device,
        )

    if args.test in ["all", "multi_needle"]:
        all_results["multi_needle"] = test_multi_needle_reasoning(
            model_type=args.model_type,
            model_size=args.model_size,
            num_needles=args.num_needles,
            device=device,
            checkpoint_path=args.checkpoint,
        )

    if args.test in ["all", "depth"]:
        all_results["depth_flatness"] = test_depth_flatness(
            model_type=args.model_type,
            model_size=args.model_size,
            context_length=args.context_length,
            device=device,
            checkpoint_path=args.checkpoint,
        )

    # Save results
    with open(args.output, "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\n{'='*70}")
    print("   BENCHMARK COMPLETE")
    print(f"{'='*70}")
    print(f"  Results saved to: {args.output}")

    # Print summary
    if all_results:
        print("\n  Summary:")
        for test_name, result in all_results.items():
            if "summary" in result:
                summary = result["summary"]
                print(f"    {test_name}:")
                for k, v in summary.items():
                    print(f"      {k}: {v}")


if __name__ == "__main__":
    main()
