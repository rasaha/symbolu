#!/usr/bin/env python3
"""
Passkey Retrieval (Needle-in-a-Haystack) Evaluation
====================================================

Tests the model's ability to retrieve a specific "passkey" hidden in a long context.
This is THE critical test for hybrid O(n²)+O(n) architectures.

The test:
1. Generate a random 5-digit passkey
2. Hide it at a random position in filler text
3. Ask the model to retrieve it
4. Measure accuracy at various context lengths

Success criteria:
- Pure O(n) models: ~60% accuracy (struggle with retrieval)
- O(n²) Transformers: ~95%+ accuracy
- Your Hybrid: Should be 95%+ (proving the architecture works!)

Usage:
    # Quick test (10 samples per length)
    python eval_passkey.py --checkpoint checkpoints_1k_fast/best.pt --samples 10

    # Full test (100 samples per length)
    python eval_passkey.py --checkpoint checkpoints_1k_fast/best.pt --samples 100

    # Test specific context lengths
    python eval_passkey.py --checkpoint checkpoints_1k_fast/best.pt --lengths 512,1024,2048
"""

import argparse
import random
import torch
import torch.nn.functional as F
from tqdm import tqdm
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from transformers import GPT2Tokenizer
from train import TrainingConfig, create_model


# Filler text patterns (boring, repetitive content)
FILLER_SENTENCES = [
    "The grass is green. The sky is blue. The sun is bright.",
    "Water flows downhill. Rivers reach the sea. Clouds form rain.",
    "Trees grow tall. Leaves fall down. Seasons change slowly.",
    "Birds fly south. Fish swim deep. Animals seek shelter.",
    "Days pass by. Time moves forward. Life continues on.",
    "Mountains stand tall. Valleys run deep. Plains stretch wide.",
    "Stars shine bright. Moon glows soft. Night brings peace.",
    "Wind blows gently. Waves crash softly. Nature speaks quietly.",
]


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
    """Generate a random 5-digit passkey."""
    return str(random.randint(10000, 99999))


def create_passkey_prompt(passkey: str, context_length: int, tokenizer, position: str = "random"):
    """
    Create a prompt with a passkey hidden in filler text.

    Args:
        passkey: The 5-digit number to hide
        context_length: Target context length in tokens
        tokenizer: Tokenizer for length estimation
        position: Where to place passkey - "random", "early", "middle", "late"
    """
    # The needle (instruction + passkey)
    needle = f"The secret passkey is: {passkey}. Remember this number."

    # Build filler to reach target length
    filler_tokens_needed = context_length - len(tokenizer.encode(needle)) - 50  # Buffer for query

    filler_parts = []
    current_tokens = 0
    while current_tokens < filler_tokens_needed:
        sentence = random.choice(FILLER_SENTENCES)
        filler_parts.append(sentence)
        current_tokens += len(tokenizer.encode(sentence))

    # Determine needle position
    num_parts = len(filler_parts)
    if position == "early":
        insert_idx = num_parts // 10  # 10% into context
    elif position == "middle":
        insert_idx = num_parts // 2
    elif position == "late":
        insert_idx = int(num_parts * 0.9)  # 90% into context
    else:  # random
        insert_idx = random.randint(0, num_parts)

    # Insert needle
    filler_parts.insert(insert_idx, needle)

    # Build full context
    context = " ".join(filler_parts)

    # Add retrieval query at the end
    query = "\n\nWhat is the secret passkey mentioned above? The passkey is:"

    full_prompt = context + query

    return full_prompt, insert_idx / num_parts if num_parts > 0 else 0


def extract_passkey_from_generation(generated_text: str) -> str:
    """Extract a 5-digit number from generated text."""
    import re
    # Find all 5-digit numbers
    matches = re.findall(r'\b(\d{5})\b', generated_text)
    if matches:
        return matches[0]
    # Try to find any sequence of 5 digits
    matches = re.findall(r'(\d{5})', generated_text)
    if matches:
        return matches[0]
    return ""


def generate_completion(model, tokenizer, prompt: str, device: torch.device, max_new_tokens: int = 20):
    """Generate completion for the prompt."""
    tokens = tokenizer.encode(prompt, return_tensors="pt").to(device)

    # Truncate if needed
    max_len = getattr(model, 'max_seq_len', 131072)
    if tokens.shape[1] > max_len - max_new_tokens:
        tokens = tokens[:, -(max_len - max_new_tokens):]

    with torch.no_grad():
        generated = tokens.clone()

        for _ in range(max_new_tokens):
            outputs = model(generated)
            logits = outputs if isinstance(outputs, torch.Tensor) else outputs[0]
            next_token_logits = logits[:, -1, :]
            next_token = torch.argmax(next_token_logits, dim=-1, keepdim=True)
            generated = torch.cat([generated, next_token], dim=1)

            # Stop on newline or period after getting some tokens
            if next_token.item() in [tokenizer.encode('\n')[0], tokenizer.encode('.')[0]]:
                if generated.shape[1] > tokens.shape[1] + 5:
                    break

    # Decode only the new tokens
    new_tokens = generated[:, tokens.shape[1]:]
    completion = tokenizer.decode(new_tokens[0], skip_special_tokens=True)

    return completion


def evaluate_passkey_retrieval(
    model,
    tokenizer,
    device: torch.device,
    context_lengths: list = [512, 1024, 2048],
    samples_per_length: int = 10,
    positions: list = ["random"],
):
    """
    Evaluate passkey retrieval at various context lengths.

    Returns:
        Dictionary with results per context length
    """
    results = {}

    for ctx_len in context_lengths:
        print(f"\n  Testing context length: {ctx_len} tokens")

        correct = 0
        total = 0
        position_results = []

        for _ in tqdm(range(samples_per_length), desc=f"  {ctx_len} tokens"):
            passkey = generate_passkey()
            position = random.choice(positions)

            prompt, relative_pos = create_passkey_prompt(
                passkey, ctx_len, tokenizer, position
            )

            # Verify actual length
            actual_tokens = len(tokenizer.encode(prompt))

            # Generate completion
            completion = generate_completion(model, tokenizer, prompt, device)

            # Extract predicted passkey
            predicted = extract_passkey_from_generation(completion)

            is_correct = predicted == passkey
            if is_correct:
                correct += 1
            total += 1

            position_results.append({
                'passkey': passkey,
                'predicted': predicted,
                'correct': is_correct,
                'position': relative_pos,
                'actual_tokens': actual_tokens,
            })

        accuracy = correct / total if total > 0 else 0
        results[ctx_len] = {
            'accuracy': accuracy,
            'correct': correct,
            'total': total,
            'details': position_results,
        }

        print(f"  Accuracy: {accuracy*100:.1f}% ({correct}/{total})")

    return results


def main():
    parser = argparse.ArgumentParser(description="Passkey Retrieval Evaluation")
    parser.add_argument("--checkpoint", type=str, default="checkpoints_1k_fast/best.pt",
                        help="Path to model checkpoint")
    parser.add_argument("--samples", type=int, default=10,
                        help="Samples per context length")
    parser.add_argument("--lengths", type=str, default="256,512,768,1024",
                        help="Comma-separated context lengths to test")
    parser.add_argument("--device", type=str, default="cuda",
                        help="Device (cuda/cpu)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility")
    args = parser.parse_args()

    # Parse context lengths
    context_lengths = [int(x.strip()) for x in args.lengths.split(",")]

    # Set seed
    random.seed(args.seed)
    torch.manual_seed(args.seed)

    # Setup device
    if args.device == "cuda" and not torch.cuda.is_available():
        print("CUDA not available, using CPU")
        args.device = "cpu"
    device = torch.device(args.device)
    print(f"Using device: {device}")

    # Load tokenizer and model
    print("Loading tokenizer...")
    tokenizer = GPT2Tokenizer.from_pretrained("gpt2")

    model, config = load_model(args.checkpoint, device)

    # Run evaluation
    print("\n" + "=" * 60)
    print("  Passkey Retrieval (Needle-in-a-Haystack) Test")
    print("=" * 60)
    print(f"  Context lengths: {context_lengths}")
    print(f"  Samples per length: {args.samples}")

    results = evaluate_passkey_retrieval(
        model=model,
        tokenizer=tokenizer,
        device=device,
        context_lengths=context_lengths,
        samples_per_length=args.samples,
    )

    # Print summary
    print("\n" + "=" * 60)
    print("  RESULTS SUMMARY")
    print("=" * 60)
    print()
    print("  Context Length | Accuracy | Correct/Total")
    print("  " + "-" * 45)

    for ctx_len in context_lengths:
        r = results[ctx_len]
        status = "✓" if r['accuracy'] >= 0.95 else "○" if r['accuracy'] >= 0.80 else "✗"
        print(f"  {ctx_len:>6} tokens  | {r['accuracy']*100:>6.1f}%  | {r['correct']:>3}/{r['total']:<3} {status}")

    print()
    print("  Reference (what to expect):")
    print("  " + "-" * 45)
    print("  Pure O(n) linear:     ~50-60% (struggles)")
    print("  Standard Transformer: ~95-100% (full attention)")
    print("  Your Hybrid Target:   >95% (proves architecture)")
    print()

    # Overall assessment
    avg_accuracy = sum(r['accuracy'] for r in results.values()) / len(results)
    print(f"  Average Accuracy: {avg_accuracy*100:.1f}%")

    if avg_accuracy >= 0.95:
        print("  Status: EXCELLENT - Hybrid architecture working! 🎉")
    elif avg_accuracy >= 0.80:
        print("  Status: GOOD - Architecture shows promise")
    elif avg_accuracy >= 0.60:
        print("  Status: MODERATE - Similar to pure O(n) models")
    else:
        print("  Status: NEEDS WORK - Retrieval mechanism not functioning")

    return results


if __name__ == "__main__":
    main()
