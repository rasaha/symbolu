#!/usr/bin/env python3
"""
Few-Shot Passkey Retrieval Test
================================

Tests if O(n) layers can carry state by using in-context learning.
Instead of asking "retrieve the passkey" (requires instruction-following),
we provide examples that trigger pattern matching.

Prompt format:
    Input: The key is 111. Output: 111.
    Input: The key is 222. Output: 222.
    Input: The key is 333. Output: 333.
    Input: The key is [TARGET]. Output:

If the model outputs [TARGET], the O(n) layers are working!

Usage:
    python eval_passkey_fewshot.py --checkpoint checkpoints_1k_fast/best.pt
    python eval_passkey_fewshot.py --checkpoint checkpoints_1k_fast/best.pt --shots 5
"""

import argparse
import random
import torch
import re
from tqdm import tqdm
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

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

    return model, config


def generate_passkey():
    """Generate a random 3-digit passkey (shorter for easier matching)."""
    return str(random.randint(100, 999))


def create_fewshot_prompt(target_key: str, num_shots: int = 3):
    """
    Create a few-shot prompt for passkey retrieval.

    Format:
        Input: The key is 123. Output: 123.
        Input: The key is 456. Output: 456.
        Input: The key is [TARGET]. Output:
    """
    examples = []

    # Generate example shots
    used_keys = set()
    for _ in range(num_shots):
        key = generate_passkey()
        while key in used_keys or key == target_key:
            key = generate_passkey()
        used_keys.add(key)
        examples.append(f"Input: The key is {key}. Output: {key}.")

    # Add the target
    examples.append(f"Input: The key is {target_key}. Output:")

    return "\n".join(examples)


def extract_number(text: str) -> str:
    """Extract first 3-digit number from text."""
    matches = re.findall(r'\b(\d{3})\b', text)
    if matches:
        return matches[0]
    matches = re.findall(r'(\d{3})', text)
    if matches:
        return matches[0]
    return ""


def generate_completion(model, tokenizer, prompt: str, device: torch.device, max_tokens: int = 10):
    """Generate completion using greedy decoding."""
    tokens = tokenizer.encode(prompt, return_tensors="pt").to(device)

    with torch.no_grad():
        for _ in range(max_tokens):
            output = model(tokens)
            logits = output['logits'][:, -1, :]
            next_token = torch.argmax(logits, dim=-1, keepdim=True)
            tokens = torch.cat([tokens, next_token], dim=1)

            # Stop on newline
            if next_token.item() == tokenizer.encode('\n')[0]:
                break

    # Decode only new tokens
    new_tokens = tokens[:, -max_tokens:]
    completion = tokenizer.decode(new_tokens[0], skip_special_tokens=True)
    return completion.strip()


def evaluate_fewshot_passkey(
    model,
    tokenizer,
    device: torch.device,
    num_samples: int = 50,
    num_shots: int = 3,
):
    """
    Evaluate few-shot passkey retrieval.
    """
    correct = 0
    total = 0
    results = []

    for _ in tqdm(range(num_samples), desc=f"Testing {num_shots}-shot"):
        target_key = generate_passkey()
        prompt = create_fewshot_prompt(target_key, num_shots)

        completion = generate_completion(model, tokenizer, prompt, device)
        predicted = extract_number(completion)

        is_correct = predicted == target_key
        if is_correct:
            correct += 1
        total += 1

        results.append({
            'target': target_key,
            'predicted': predicted,
            'completion': completion[:50],
            'correct': is_correct,
        })

    accuracy = correct / total if total > 0 else 0
    return {
        'accuracy': accuracy,
        'correct': correct,
        'total': total,
        'details': results,
    }


def main():
    parser = argparse.ArgumentParser(description="Few-Shot Passkey Retrieval")
    parser.add_argument("--checkpoint", type=str, default="checkpoints_1k_fast/best.pt")
    parser.add_argument("--samples", type=int, default=50, help="Number of test samples")
    parser.add_argument("--shots", type=int, default=3, help="Number of few-shot examples")
    parser.add_argument("--device", type=str, default="cuda")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    torch.manual_seed(args.seed)

    if args.device == "cuda" and not torch.cuda.is_available():
        print("CUDA not available, using CPU")
        args.device = "cpu"
    device = torch.device(args.device)
    print(f"Using device: {device}")

    print("Loading tokenizer...")
    tokenizer = GPT2Tokenizer.from_pretrained("gpt2")

    model, config = load_model(args.checkpoint, device)

    # Show example prompt
    print("\n" + "=" * 60)
    print("  Few-Shot Passkey Retrieval Test")
    print("=" * 60)
    print(f"\nExample {args.shots}-shot prompt:")
    print("-" * 40)
    example_prompt = create_fewshot_prompt("789", args.shots)
    print(example_prompt)
    print("-" * 40)

    # Test different shot counts
    shot_counts = [1, 3, 5] if args.shots == 3 else [args.shots]

    all_results = {}
    for shots in shot_counts:
        print(f"\n  Testing {shots}-shot prompts...")
        results = evaluate_fewshot_passkey(
            model=model,
            tokenizer=tokenizer,
            device=device,
            num_samples=args.samples,
            num_shots=shots,
        )
        all_results[shots] = results
        print(f"  {shots}-shot Accuracy: {results['accuracy']*100:.1f}% ({results['correct']}/{results['total']})")

    # Print summary
    print("\n" + "=" * 60)
    print("  RESULTS SUMMARY")
    print("=" * 60)
    print()
    print("  Shots | Accuracy | Correct/Total")
    print("  " + "-" * 35)
    for shots, results in all_results.items():
        status = "OK" if results['accuracy'] >= 0.80 else "PARTIAL" if results['accuracy'] >= 0.50 else "LOW"
        print(f"  {shots:>5} | {results['accuracy']*100:>6.1f}%  | {results['correct']:>3}/{results['total']:<3} {status}")

    print()
    print("  Interpretation:")
    print("  ---------------")
    print("  >80%: O(n) layers successfully carry state")
    print("  50-80%: Partial state propagation")
    print("  <50%: O(n) layers may need tuning")

    # Show some examples
    best_shots = max(all_results.keys(), key=lambda k: all_results[k]['accuracy'])
    print(f"\n  Sample outputs ({best_shots}-shot):")
    for i, ex in enumerate(all_results[best_shots]['details'][:5]):
        status = "OK" if ex['correct'] else "MISS"
        print(f"    {i+1}. Target: {ex['target']}, Got: '{ex['completion'][:20]}' [{status}]")

    return all_results


if __name__ == "__main__":
    main()
