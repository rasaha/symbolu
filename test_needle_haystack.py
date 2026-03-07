#!/usr/bin/env python3
"""
Needle in a Haystack Test for Phase Attention
==============================================

Tests long-context retrieval by placing a "needle" (specific fact) at various
positions within a "haystack" (long context) and measuring retrieval accuracy.

This is a key benchmark for validating that Phase Attention maintains
retrieval fidelity across long contexts despite O(n) complexity.

Usage:
------
    # Quick test (4K context, 5 depths)
    python test_needle_haystack.py --max_context 4096 --num_depths 5

    # Full test (32K context, 10 depths)
    python test_needle_haystack.py --max_context 32768 --num_depths 10 --gradient_checkpointing

    # Test specific checkpoint
    python test_needle_haystack.py --checkpoint checkpoints/best.pt --max_context 16384

Author: SymbolU Team
Date: December 2025
"""

import os

# Set CUDA memory and tokenizer environment variables before importing torch
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import argparse
import json
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn.functional as F
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from symbolu.phase_transformer import PhaseTransformer, HybridPhaseTransformer

try:
    from transformers import GPT2Tokenizer
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False
    print("Warning: transformers not installed, using simple tokenizer")


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class NeedleConfig:
    """Configuration for needle in haystack test."""
    # Model
    model_type: str = "hybrid"
    model_size: str = "small"
    checkpoint: Optional[str] = None

    # Test parameters
    min_context: int = 1024
    max_context: int = 16384
    num_context_lengths: int = 6
    num_depths: int = 10  # Number of needle positions to test
    num_samples: int = 5  # Samples per (context, depth) combination

    # Model config
    embed_dim: int = 768
    num_layers: int = 12
    num_heads: int = 12
    ff_dim: int = 3072
    vocab_size: int = 50257

    # Memory
    gradient_checkpointing: bool = False

    # Hardware
    device: str = "auto"
    seed: int = 42


# Match train.py model sizes exactly
MODEL_PRESETS = {
    "tiny": {"embed_dim": 256, "num_layers": 4, "num_heads": 4, "ff_dim": 1024},
    "small": {"embed_dim": 512, "num_layers": 8, "num_heads": 8, "ff_dim": 2048},  # 56M params
    "medium": {"embed_dim": 768, "num_layers": 12, "num_heads": 12, "ff_dim": 3072},  # ~125M params
    "large": {"embed_dim": 1024, "num_layers": 24, "num_heads": 16, "ff_dim": 4096},  # ~350M params
}


# =============================================================================
# HAYSTACK GENERATION
# =============================================================================

# Paul Graham essays excerpts for realistic haystack text
HAYSTACK_TEXTS = [
    "The way to get startup ideas is not to try to think of startup ideas. "
    "It's to look for problems, preferably problems you have yourself. "
    "The very best startup ideas tend to have three things in common: "
    "they're something the founders themselves want, that they themselves can build, "
    "and that few others realize are worth doing.",

    "When you're operating on the margin of what's possible, you need a lot of "
    "drive to keep going. The founders who do best are the ones who are motivated "
    "by the problem rather than the money. They want to solve this problem. "
    "The money is just a way to keep doing it.",

    "The most common mistake startups make is to solve problems no one has. "
    "You'd be surprised how often founders build something first and only then "
    "try to find users for it. The problem is, by then it's too late. "
    "You've already built the wrong thing.",

    "In the best case, you end up with something that users love. "
    "The most important thing to do is to build something a few users love, "
    "not something a lot of users sort of like. If you make something users love, "
    "they'll tell their friends, and it will grow organically.",

    "One of the most valuable things I learned from starting a startup was "
    "how important it is to do things that don't scale. "
    "In the early days, you should do things manually. "
    "Talk to users one at a time. Hand-deliver products.",

    "The best founders are often people who've made mistakes before. "
    "They've learned from those mistakes. They know what to avoid. "
    "Experience is valuable, but not in the way most people think. "
    "It's not about learning what works; it's about learning what doesn't.",

    "Focus is about saying no. You can't do everything. "
    "The companies that win are the ones that focus relentlessly "
    "on doing one thing very well. Everything else is a distraction. "
    "Simplicity is the ultimate sophistication.",

    "The best way to predict the future is to create it. "
    "Don't wait for opportunities; create them. "
    "The people who change the world are the ones who act, "
    "not the ones who wait for permission.",
]

# Needle templates - facts that can be verified
NEEDLE_TEMPLATES = [
    ("The secret code is {code}.", "What is the secret code?", "{code}"),
    ("The password to the vault is {code}.", "What is the password to the vault?", "{code}"),
    ("The magic number is {code}.", "What is the magic number?", "{code}"),
    ("Remember this key: {code}.", "What is the key to remember?", "{code}"),
    ("The special identifier is {code}.", "What is the special identifier?", "{code}"),
]


def generate_random_code(length: int = 6) -> str:
    """Generate a random alphanumeric code."""
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(random.choice(chars) for _ in range(length))


def generate_haystack(target_tokens: int, tokenizer) -> str:
    """Generate haystack text of approximately target_tokens length."""
    haystack = []
    current_tokens = 0

    while current_tokens < target_tokens:
        # Add random essay excerpt
        text = random.choice(HAYSTACK_TEXTS)
        haystack.append(text)
        current_tokens = len(tokenizer.encode(" ".join(haystack)))

    return " ".join(haystack)


def insert_needle(
    haystack: str,
    needle: str,
    depth_percent: float,
    tokenizer,
) -> Tuple[str, int]:
    """
    Insert needle at specified depth percentage.

    Args:
        haystack: The context text
        needle: The fact to insert
        depth_percent: 0.0 = beginning, 1.0 = end
        tokenizer: Tokenizer for splitting

    Returns:
        (text_with_needle, needle_position_tokens)
    """
    # Tokenize haystack
    tokens = tokenizer.encode(haystack)

    # Calculate insertion position
    insert_pos = int(len(tokens) * depth_percent)
    insert_pos = max(10, min(insert_pos, len(tokens) - 10))  # Safety margins

    # Split and insert
    before_tokens = tokens[:insert_pos]
    after_tokens = tokens[insert_pos:]
    needle_tokens = tokenizer.encode(" " + needle + " ")

    # Combine
    combined_tokens = before_tokens + needle_tokens + after_tokens
    combined_text = tokenizer.decode(combined_tokens)

    return combined_text, insert_pos


# =============================================================================
# SIMPLE TOKENIZER FALLBACK
# =============================================================================

class SimpleTokenizer:
    """Simple word-based tokenizer fallback."""

    def __init__(self, vocab_size: int = 50257):
        self.vocab_size = vocab_size
        self.word_to_id = {}
        self.id_to_word = {}
        self.next_id = 256  # Reserve 0-255 for bytes

        # Special tokens
        self.pad_token_id = 0
        self.eos_token_id = 1
        self.unk_token_id = 2

    def encode(self, text: str) -> List[int]:
        """Encode text to token ids."""
        words = text.split()
        ids = []
        for word in words:
            if word not in self.word_to_id:
                self.word_to_id[word] = self.next_id
                self.id_to_word[self.next_id] = word
                self.next_id = (self.next_id + 1) % self.vocab_size
            ids.append(self.word_to_id[word])
        return ids

    def decode(self, ids: List[int]) -> str:
        """Decode token ids to text."""
        words = []
        for id in ids:
            if id in self.id_to_word:
                words.append(self.id_to_word[id])
            else:
                words.append(f"[{id}]")
        return " ".join(words)


# =============================================================================
# MODEL LOADING
# =============================================================================

def load_model(config: NeedleConfig, device: torch.device) -> torch.nn.Module:
    """Load or create model."""

    preset = MODEL_PRESETS.get(config.model_size, MODEL_PRESETS["small"])
    embed_dim = preset["embed_dim"]
    num_layers = preset["num_layers"]
    num_heads = preset["num_heads"]
    ff_dim = preset["ff_dim"]

    # If loading checkpoint, extract max_seq_len from it
    max_seq_len = config.max_context + 1024  # Default with safety margin
    ckpt = None
    is_split = False
    if config.checkpoint and os.path.exists(config.checkpoint):
        ckpt_path = Path(config.checkpoint)
        is_split = ckpt_path.stem.endswith("_model")

        if is_split:
            # Split-file format: *_model.pt is a raw state_dict
            ckpt = torch.load(config.checkpoint, map_location=device, weights_only=False)
            # Load config from config.json in same directory
            config_json = ckpt_path.parent / "config.json"
            if config_json.exists():
                with open(config_json) as f:
                    saved_config = json.load(f)
                max_seq_len = saved_config.get("max_seq_len", max_seq_len)
        else:
            ckpt = torch.load(config.checkpoint, map_location=device, weights_only=False)
            if isinstance(ckpt, dict) and "config" in ckpt:
                max_seq_len = ckpt["config"].get("max_seq_len", max_seq_len)
            elif isinstance(ckpt, dict) and "model" in ckpt:
                # Infer from pos_embed shape
                for key, val in ckpt["model"].items():
                    if "pos_embed" in key:
                        max_seq_len = val.shape[0]
                        break

    if config.model_type == "phase":
        model = PhaseTransformer(
            vocab_size=config.vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            ff_dim=ff_dim,
            max_seq_len=max_seq_len,
            dropout=0.0,  # No dropout for eval
        )
    else:  # hybrid
        model = HybridPhaseTransformer(
            vocab_size=config.vocab_size,
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

    # Enable gradient checkpointing if needed
    if config.gradient_checkpointing:
        for module in model.modules():
            if hasattr(module, 'gradient_checkpointing'):
                module.gradient_checkpointing = True

    # Load checkpoint weights (ckpt already loaded above for config extraction)
    if ckpt is not None:
        print(f"Loading checkpoint from {config.checkpoint}")
        if is_split:
            # Split format: ckpt IS the raw state_dict
            model.load_state_dict(ckpt, strict=False)
        elif isinstance(ckpt, dict) and "model" in ckpt:
            model.load_state_dict(ckpt["model"], strict=False)
        else:
            model.load_state_dict(ckpt, strict=False)

    model = model.to(device)
    model.to(torch.bfloat16)
    model.eval()

    return model


# =============================================================================
# NEEDLE TEST
# =============================================================================

def test_needle_retrieval(
    model: torch.nn.Module,
    context_with_needle: str,
    question: str,
    expected_answer: str,
    tokenizer,
    device: torch.device,
    max_gen_tokens: int = 20,
) -> Tuple[bool, str, float]:
    """
    Test if model can retrieve the needle.

    Uses perplexity-based scoring: measures how likely the model
    considers the correct answer vs alternatives.

    Returns:
        (success, generated_text, confidence_score)
    """
    # Prepare prompt
    prompt = context_with_needle + "\n\nQuestion: " + question + "\nAnswer:"

    # Tokenize
    input_ids = tokenizer.encode(prompt)
    if len(input_ids) > model.config.max_seq_len - max_gen_tokens:
        input_ids = input_ids[-(model.config.max_seq_len - max_gen_tokens):]

    input_tensor = torch.tensor([input_ids], dtype=torch.long, device=device)

    # Generate response
    generated = []
    with torch.no_grad():
        for _ in range(max_gen_tokens):
            output = model(input_tensor)
            if isinstance(output, dict):
                logits = output.get('logits', output.get('output'))
            else:
                logits = output

            # Get next token prediction
            next_logits = logits[0, -1, :]
            probs = F.softmax(next_logits, dim=-1)

            # Greedy sampling
            next_token = torch.argmax(probs).item()
            generated.append(next_token)

            # Stop at EOS or newline
            if next_token in [tokenizer.eos_token_id, tokenizer.encode("\n")[0] if hasattr(tokenizer, 'encode') else 198]:
                break

            # Append to input
            input_tensor = torch.cat([
                input_tensor,
                torch.tensor([[next_token]], device=device)
            ], dim=1)

            # Truncate if too long
            if input_tensor.shape[1] > model.config.max_seq_len:
                input_tensor = input_tensor[:, -model.config.max_seq_len:]

    # Decode generated text
    generated_text = tokenizer.decode(generated).strip()

    # Check if answer is correct
    success = expected_answer.lower() in generated_text.lower()

    # Calculate confidence (simplified)
    confidence = 1.0 if success else 0.0

    return success, generated_text, confidence


def run_needle_test(config: NeedleConfig) -> Dict:
    """
    Run full needle in haystack test suite.

    Returns results dictionary with accuracy per (context_length, depth) pair.
    """
    torch.manual_seed(config.seed)
    random.seed(config.seed)
    np.random.seed(config.seed)

    # Device
    if config.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(config.device)

    print(f"\n{'='*70}")
    print("   NEEDLE IN A HAYSTACK TEST")
    print("   Long-Context Retrieval Benchmark")
    print(f"{'='*70}")
    print(f"\n  Model Type: {config.model_type}")
    print(f"  Model Size: {config.model_size}")
    print(f"  Context Range: {config.min_context:,} - {config.max_context:,} tokens")
    print(f"  Depth Positions: {config.num_depths}")
    print(f"  Samples per Test: {config.num_samples}")
    print(f"  Device: {device}")
    print()

    # Load tokenizer
    if HAS_TRANSFORMERS:
        tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
        tokenizer.pad_token = tokenizer.eos_token
    else:
        tokenizer = SimpleTokenizer(config.vocab_size)

    # Load model
    model = load_model(config, device)
    num_params = sum(p.numel() for p in model.parameters())
    print(f"  Model Parameters: {num_params:,} ({num_params/1e6:.1f}M)")

    # Generate context lengths to test (powers of 2 within range)
    context_lengths = [
        2**p for p in range(
            int(np.log2(config.min_context)),
            int(np.log2(config.max_context)) + 1
        )
        if 2**p >= config.min_context and 2**p <= config.max_context
    ]

    # Generate depth percentages to test
    depths = np.linspace(0.0, 1.0, config.num_depths).tolist()

    # Results storage
    results = {
        "config": {
            "model_type": config.model_type,
            "model_size": config.model_size,
            "min_context": config.min_context,
            "max_context": config.max_context,
            "num_samples": config.num_samples,
        },
        "context_lengths": context_lengths,
        "depths": depths,
        "accuracy_matrix": [],  # [context_idx][depth_idx] = accuracy
        "details": [],
    }

    print(f"\n{'='*70}")
    print("   RUNNING TESTS")
    print(f"{'='*70}\n")

    total_tests = len(context_lengths) * len(depths) * config.num_samples
    completed = 0
    start_time = time.time()

    for ctx_idx, context_len in enumerate(context_lengths):
        accuracy_row = []

        for depth_idx, depth in enumerate(depths):
            successes = 0

            for sample_idx in range(config.num_samples):
                # Generate test case
                needle_template, question, answer_template = random.choice(NEEDLE_TEMPLATES)
                code = generate_random_code()
                needle = needle_template.format(code=code)
                expected_answer = answer_template.format(code=code)

                # Generate haystack and insert needle
                haystack = generate_haystack(context_len, tokenizer)
                context_with_needle, needle_pos = insert_needle(
                    haystack, needle, depth, tokenizer
                )

                # Run test
                try:
                    success, generated, confidence = test_needle_retrieval(
                        model=model,
                        context_with_needle=context_with_needle,
                        question=question,
                        expected_answer=expected_answer,
                        tokenizer=tokenizer,
                        device=device,
                    )

                    if sample_idx == 0 and depth_idx == 0:
                        print(f"  [DEBUG] Expected: '{expected_answer}' | Generated: '{generated[:80]}'")

                    if success:
                        successes += 1

                    results["details"].append({
                        "context_len": context_len,
                        "depth": depth,
                        "sample": sample_idx,
                        "success": success,
                        "expected": expected_answer,
                        "generated": generated,
                    })

                except Exception as e:
                    print(f"  Error at ctx={context_len}, depth={depth:.1%}: {e}")
                    results["details"].append({
                        "context_len": context_len,
                        "depth": depth,
                        "sample": sample_idx,
                        "success": False,
                        "error": str(e),
                    })

                completed += 1

            accuracy = successes / config.num_samples
            accuracy_row.append(accuracy)

            # Progress update
            elapsed = time.time() - start_time
            eta = elapsed / completed * (total_tests - completed) if completed > 0 else 0
            print(f"  Context: {context_len:>6} | Depth: {depth:>5.1%} | "
                  f"Accuracy: {accuracy:>5.1%} | Progress: {completed}/{total_tests} | "
                  f"ETA: {eta/60:.1f}min")

        results["accuracy_matrix"].append(accuracy_row)

    # Calculate summary statistics
    accuracy_matrix = np.array(results["accuracy_matrix"])
    results["summary"] = {
        "overall_accuracy": float(accuracy_matrix.mean()),
        "by_context": {
            str(ctx): float(accuracy_matrix[i].mean())
            for i, ctx in enumerate(context_lengths)
        },
        "by_depth": {
            f"{d:.1%}": float(accuracy_matrix[:, i].mean())
            for i, d in enumerate(depths)
        },
    }

    return results


def print_results(results: Dict):
    """Print formatted results."""
    print(f"\n{'='*70}")
    print("   RESULTS SUMMARY")
    print(f"{'='*70}")

    print(f"\n  Overall Accuracy: {results['summary']['overall_accuracy']:.1%}")

    print("\n  Accuracy by Context Length:")
    for ctx, acc in results["summary"]["by_context"].items():
        bar = "█" * int(acc * 20)
        print(f"    {ctx:>6} tokens: {acc:>5.1%} {bar}")

    print("\n  Accuracy by Depth:")
    for depth, acc in results["summary"]["by_depth"].items():
        bar = "█" * int(acc * 20)
        print(f"    {depth:>6}: {acc:>5.1%} {bar}")

    # Print heatmap (ASCII)
    print("\n  Accuracy Heatmap (rows=context, cols=depth):")
    matrix = np.array(results["accuracy_matrix"])

    # Header
    print("         ", end="")
    for d in results["depths"]:
        print(f"{d:>5.0%} ", end="")
    print()

    # Rows
    for i, ctx in enumerate(results["context_lengths"]):
        print(f"  {ctx:>6}: ", end="")
        for j, acc in enumerate(matrix[i]):
            if acc >= 0.8:
                symbol = "██"
            elif acc >= 0.6:
                symbol = "▓▓"
            elif acc >= 0.4:
                symbol = "▒▒"
            elif acc >= 0.2:
                symbol = "░░"
            else:
                symbol = "  "
            print(f" {symbol}  ", end="")
        print(f" {matrix[i].mean():.0%}")

    print("\n  Legend: ██=80%+ ▓▓=60%+ ▒▒=40%+ ░░=20%+ (blank)=<20%")


def save_results(results: Dict, output_path: str):
    """Save results to JSON file."""
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved to: {output_path}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Needle in a Haystack Test for Phase Attention",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Model
    parser.add_argument("--model_type", type=str, default="hybrid",
                       choices=["phase", "hybrid"],
                       help="Model architecture")
    parser.add_argument("--model_size", type=str, default="small",
                       choices=["tiny", "small", "medium", "large"],
                       help="Model size preset")
    parser.add_argument("--checkpoint", type=str, default=None,
                       help="Path to model checkpoint")

    # Test parameters
    parser.add_argument("--min_context", type=int, default=1024,
                       help="Minimum context length")
    parser.add_argument("--max_context", type=int, default=16384,
                       help="Maximum context length")
    parser.add_argument("--num_context_lengths", type=int, default=6,
                       help="Number of context lengths to test")
    parser.add_argument("--num_depths", type=int, default=10,
                       help="Number of needle positions to test")
    parser.add_argument("--num_samples", type=int, default=5,
                       help="Samples per (context, depth) combination")

    # Memory
    parser.add_argument("--gradient_checkpointing", action="store_true",
                       help="Enable gradient checkpointing for long contexts")

    # Output
    parser.add_argument("--output", type=str, default="needle_haystack_results.json",
                       help="Output file for results")

    # Other
    parser.add_argument("--seed", type=int, default=42)

    args = parser.parse_args()

    config = NeedleConfig(
        model_type=args.model_type,
        model_size=args.model_size,
        checkpoint=args.checkpoint,
        min_context=args.min_context,
        max_context=args.max_context,
        num_context_lengths=args.num_context_lengths,
        num_depths=args.num_depths,
        num_samples=args.num_samples,
        gradient_checkpointing=args.gradient_checkpointing,
        seed=args.seed,
    )

    # Run test
    results = run_needle_test(config)

    # Print and save results
    print_results(results)
    save_results(results, args.output)

    print(f"\n{'='*70}")
    print("   TEST COMPLETE")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
