#!/usr/bin/env python3
"""
HellaSwag 0-shot Evaluation for SymbolU Phase Transformer
==========================================================

Evaluates the model on HellaSwag commonsense reasoning benchmark.

Usage:
    # Quick test (100 samples)
    python eval_hellaswag.py --checkpoint checkpoints_1k_fast/best.pt --samples 100

    # Full evaluation (~10K samples)
    python eval_hellaswag.py --checkpoint checkpoints_1k_fast/best.pt

Reference Scores (0-shot):
    GPT-2 Small (124M):  ~29%
    GPT-2 Medium (355M): ~32%
    GPT-2 Large (774M):  ~36%
    GPT-2 XL (1.5B):     ~40%
    Random baseline:      25%
"""

import argparse
import torch
import torch.nn.functional as F
from tqdm import tqdm
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from datasets import load_dataset
from transformers import GPT2Tokenizer

from train import TrainingConfig, create_model


def load_model(checkpoint_path: str, device: torch.device):
    """Load model from checkpoint."""
    print(f"Loading checkpoint: {checkpoint_path}")
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)

    # Reconstruct config
    config_dict = checkpoint.get('config', {})
    config = TrainingConfig(**config_dict)

    # Create and load model
    model = create_model(config)
    model.load_state_dict(checkpoint['model'], strict=False)
    model.to(device)
    model.eval()

    # Print info
    num_params = sum(p.numel() for p in model.parameters())
    print(f"Model loaded: {num_params/1e6:.1f}M parameters")

    if 'state' in checkpoint:
        state = checkpoint['state']
        print(f"Checkpoint from step {state.get('step', 'unknown')}")
        if 'best_val_loss' in state:
            import math
            print(f"Best Val PPL: {math.exp(state['best_val_loss']):.2f}")

    return model, config


def score_completion(model, tokenizer, context: str, completion: str, device: torch.device) -> float:
    """
    Score a completion given a context.
    Returns the average log probability of the completion tokens.
    """
    # Encode full sequence
    full_text = context + completion
    tokens = tokenizer.encode(full_text, return_tensors="pt").to(device)

    # Get context length to know where completion starts
    context_tokens = tokenizer.encode(context, return_tensors="pt")
    context_len = context_tokens.shape[1]

    if tokens.shape[1] <= context_len:
        return float('-inf')

    with torch.no_grad():
        # Get model output
        outputs = model(tokens)
        logits = outputs if isinstance(outputs, torch.Tensor) else outputs[0]

        # Get log probabilities for completion tokens only
        # Shift: predict token[i+1] from logits[i]
        completion_logits = logits[:, context_len-1:-1, :]  # Logits that predict completion
        completion_targets = tokens[:, context_len:]  # Actual completion tokens

        # Compute log probabilities
        log_probs = F.log_softmax(completion_logits, dim=-1)

        # Gather the log probs for actual tokens
        token_log_probs = log_probs.gather(2, completion_targets.unsqueeze(-1)).squeeze(-1)

        # Average log probability (higher is better)
        avg_log_prob = token_log_probs.mean().item()

    return avg_log_prob


def evaluate_hellaswag(
    model,
    tokenizer,
    device: torch.device,
    num_samples: int = None,
    batch_size: int = 1,
) -> dict:
    """
    Evaluate model on HellaSwag benchmark.

    Returns:
        Dictionary with accuracy and details
    """
    print("\nLoading HellaSwag dataset...")
    dataset = load_dataset("Rowan/hellaswag", split="validation", trust_remote_code=True)

    if num_samples:
        dataset = dataset.select(range(min(num_samples, len(dataset))))
        print(f"Evaluating on {len(dataset)} samples")
    else:
        print(f"Evaluating on full dataset ({len(dataset)} samples)")

    correct = 0
    total = 0

    for example in tqdm(dataset, desc="Evaluating"):
        # HellaSwag format
        ctx = example["ctx"]
        endings = example["endings"]
        label = int(example["label"])

        # Score each ending
        scores = []
        for ending in endings:
            score = score_completion(model, tokenizer, ctx, " " + ending, device)
            scores.append(score)

        # Prediction is the highest scoring completion
        pred = scores.index(max(scores))

        if pred == label:
            correct += 1
        total += 1

    accuracy = correct / total

    return {
        "accuracy": accuracy,
        "correct": correct,
        "total": total,
        "accuracy_pct": f"{accuracy * 100:.2f}%",
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate on HellaSwag")
    parser.add_argument("--checkpoint", type=str, default="checkpoints_1k_fast/best.pt",
                        help="Path to model checkpoint")
    parser.add_argument("--samples", type=int, default=None,
                        help="Number of samples to evaluate (default: all)")
    parser.add_argument("--device", type=str, default="cuda",
                        help="Device to use (cuda/cpu)")
    args = parser.parse_args()

    # Setup device
    if args.device == "cuda" and not torch.cuda.is_available():
        print("CUDA not available, using CPU")
        args.device = "cpu"
    device = torch.device(args.device)
    print(f"Using device: {device}")

    # Load tokenizer
    print("Loading tokenizer...")
    tokenizer = GPT2Tokenizer.from_pretrained("gpt2")

    # Load model
    model, config = load_model(args.checkpoint, device)

    # Evaluate
    print("\n" + "=" * 60)
    print("  HellaSwag 0-shot Evaluation")
    print("=" * 60)

    results = evaluate_hellaswag(
        model=model,
        tokenizer=tokenizer,
        device=device,
        num_samples=args.samples,
    )

    # Print results
    print("\n" + "=" * 60)
    print("  Results")
    print("=" * 60)
    print(f"  Accuracy: {results['accuracy_pct']} ({results['correct']}/{results['total']})")
    print()

    # Reference comparison
    print("  Reference Scores (0-shot):")
    print("  -------------------------")
    print("  GPT-2 Small (124M):   ~29%")
    print("  GPT-2 Medium (355M):  ~32%")
    print("  GPT-2 Large (774M):   ~36%")
    print("  GPT-2 XL (1.5B):      ~40%")
    print("  Random baseline:       25%")
    print()

    return results


if __name__ == "__main__":
    main()
