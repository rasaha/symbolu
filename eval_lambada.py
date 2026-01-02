#!/usr/bin/env python3
"""
LAMBADA Evaluation for Base Language Models
============================================

LAMBADA tests long-range context understanding by predicting the LAST word
of a passage. This is THE benchmark for proving O(n²)+O(n) hybrid architecture.

Why it matters:
- Requires understanding context from 50+ tokens back
- No instruction-following needed - pure next-token prediction
- Tests if your O(n²) layers are capturing long-range dependencies

Reference Scores:
    GPT-2 Small (124M):  ~40% accuracy
    GPT-2 Medium (355M): ~50% accuracy
    GPT-2 Large (774M):  ~55% accuracy
    GPT-2 XL (1.5B):     ~60% accuracy

Target: >45% proves your 165M hybrid beats GPT-2 Small

Usage:
    python eval_lambada.py --checkpoint checkpoints_1k_fast/best.pt
    python eval_lambada.py --checkpoint checkpoints_1k_fast/best.pt --samples 500
"""

import argparse
import torch
import torch.nn.functional as F
from tqdm import tqdm
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from datasets import load_dataset
from transformers import GPT2Tokenizer
from train import TrainingConfig, create_model


def load_model(checkpoint_path: str, device: torch.device):
    """Load model from checkpoint."""
    print(f"Loading checkpoint: {checkpoint_path}")
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)

    config_dict = checkpoint.get('config', {})
    config = TrainingConfig(**config_dict)

    model = create_model(config)
    model.load_state_dict(checkpoint['model'], strict=False)
    model.to(device)
    model.eval()

    num_params = sum(p.numel() for p in model.parameters())
    print(f"Model loaded: {num_params/1e6:.1f}M parameters")

    if 'state' in checkpoint:
        state = checkpoint['state']
        print(f"Checkpoint from step {state.get('step', 'unknown')}")
        if 'best_val_loss' in state:
            import math
            print(f"Best Val PPL: {math.exp(state['best_val_loss']):.2f}")

    return model, config


def evaluate_lambada(
    model,
    tokenizer,
    device: torch.device,
    num_samples: int = None,
) -> dict:
    """
    Evaluate on LAMBADA - predict the last word given context.

    LAMBADA format: Each example has 'text' where the last word must be predicted.
    """
    print("\nLoading LAMBADA dataset...")
    dataset = load_dataset("lambada", split="test", trust_remote_code=True)

    if num_samples:
        dataset = dataset.select(range(min(num_samples, len(dataset))))
        print(f"Evaluating on {len(dataset)} samples")
    else:
        print(f"Evaluating on full dataset ({len(dataset)} samples)")

    correct = 0
    total = 0
    correct_top5 = 0

    for example in tqdm(dataset, desc="Evaluating"):
        text = example['text']

        # Split into context and target (last word)
        words = text.strip().split()
        if len(words) < 2:
            continue

        target_word = words[-1]
        context = ' '.join(words[:-1])

        # Tokenize
        context_tokens = tokenizer.encode(context, return_tensors="pt").to(device)
        target_tokens = tokenizer.encode(' ' + target_word)  # Space prefix for proper tokenization

        if len(target_tokens) == 0:
            continue

        # Get the first token of the target word
        target_first_token = target_tokens[0]

        with torch.no_grad():
            output = model(context_tokens)
            logits = output['logits'][:, -1, :]  # Last position

            # Top-1 accuracy
            pred_token = torch.argmax(logits, dim=-1).item()
            if pred_token == target_first_token:
                correct += 1

            # Top-5 accuracy
            top5_tokens = torch.topk(logits, 5, dim=-1).indices[0].tolist()
            if target_first_token in top5_tokens:
                correct_top5 += 1

        total += 1

    accuracy = correct / total if total > 0 else 0
    accuracy_top5 = correct_top5 / total if total > 0 else 0

    return {
        "accuracy": accuracy,
        "accuracy_top5": accuracy_top5,
        "correct": correct,
        "correct_top5": correct_top5,
        "total": total,
    }


def main():
    parser = argparse.ArgumentParser(description="LAMBADA Evaluation")
    parser.add_argument("--checkpoint", type=str, default="checkpoints_1k_fast/best.pt",
                        help="Path to model checkpoint")
    parser.add_argument("--samples", type=int, default=None,
                        help="Number of samples (default: all ~5K)")
    parser.add_argument("--device", type=str, default="cuda",
                        help="Device (cuda/cpu)")
    args = parser.parse_args()

    if args.device == "cuda" and not torch.cuda.is_available():
        print("CUDA not available, using CPU")
        args.device = "cpu"
    device = torch.device(args.device)
    print(f"Using device: {device}")

    print("Loading tokenizer...")
    tokenizer = GPT2Tokenizer.from_pretrained("gpt2")

    model, config = load_model(args.checkpoint, device)

    print("\n" + "=" * 60)
    print("  LAMBADA Evaluation (Long-Range Context Test)")
    print("=" * 60)

    results = evaluate_lambada(
        model=model,
        tokenizer=tokenizer,
        device=device,
        num_samples=args.samples,
    )

    print("\n" + "=" * 60)
    print("  Results")
    print("=" * 60)
    print(f"  Top-1 Accuracy: {results['accuracy']*100:.2f}% ({results['correct']}/{results['total']})")
    print(f"  Top-5 Accuracy: {results['accuracy_top5']*100:.2f}% ({results['correct_top5']}/{results['total']})")
    print()
    print("  Reference Scores:")
    print("  -----------------")
    print("  GPT-2 Small (124M):   ~40%")
    print("  GPT-2 Medium (355M):  ~50%")
    print("  GPT-2 Large (774M):   ~55%")
    print("  GPT-2 XL (1.5B):      ~60%")
    print()

    if results['accuracy'] >= 0.50:
        print("  Status: EXCELLENT - Matches GPT-2 Medium or better!")
    elif results['accuracy'] >= 0.45:
        print("  Status: GREAT - Beats GPT-2 Small!")
    elif results['accuracy'] >= 0.40:
        print("  Status: GOOD - Matches GPT-2 Small")
    else:
        print("  Status: Needs more training")

    return results


if __name__ == "__main__":
    main()
