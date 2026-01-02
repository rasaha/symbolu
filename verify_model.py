#!/usr/bin/env python3
"""
Verify model checkpoint works correctly.

This script:
1. Loads the model checkpoint
2. Computes PPL on validation data (exactly like train.py does)
3. Tests the built-in generate method
4. Diagnoses any issues
"""

import torch
import torch.nn.functional as F
import math
from transformers import GPT2Tokenizer
from datasets import load_dataset
from train import TrainingConfig, create_model

def main():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # Load checkpoint
    checkpoint_path = "checkpoints_1k_fast/best.pt"
    print(f"\n1. Loading checkpoint: {checkpoint_path}")
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)

    # Print checkpoint info
    state = checkpoint.get('state', {})
    print(f"   Step: {state.get('step', 'unknown')}")
    print(f"   Best val loss: {state.get('best_val_loss', 'unknown')}")
    if 'best_val_loss' in state:
        print(f"   Best val PPL: {math.exp(state['best_val_loss']):.2f}")

    # Recreate model
    config_dict = checkpoint.get('config', {})
    config = TrainingConfig(**config_dict)
    print(f"\n2. Creating model...")
    model = create_model(config)

    # Load weights
    missing, unexpected = model.load_state_dict(checkpoint['model'], strict=False)
    print(f"   Missing keys: {len(missing)}")
    print(f"   Unexpected keys: {len(unexpected)}")
    if missing:
        print(f"   Missing: {missing}")

    model.to(device)
    model.eval()

    num_params = sum(p.numel() for p in model.parameters())
    print(f"   Parameters: {num_params/1e6:.1f}M")

    # Load tokenizer
    print(f"\n3. Loading tokenizer...")
    tokenizer = GPT2Tokenizer.from_pretrained("gpt2")

    # Load validation data
    print(f"\n4. Loading WikiText-103 validation data...")
    val_ds = load_dataset("Salesforce/wikitext", "wikitext-103-raw-v1", split="validation")

    # Tokenize some validation text
    val_text = " ".join([ex['text'] for ex in val_ds.select(range(100)) if ex['text'].strip()])
    val_tokens = tokenizer.encode(val_text)
    print(f"   Tokenized {len(val_tokens)} tokens")

    # Create batches exactly like train.py
    seq_len = min(1024, config.max_seq_len)  # Use reasonable length
    print(f"   Sequence length: {seq_len}")

    # Test 1: Compute PPL on validation data
    print(f"\n5. Computing validation PPL...")
    total_loss = 0.0
    num_batches = 0

    with torch.no_grad():
        for i in range(0, len(val_tokens) - seq_len - 1, seq_len):
            x = torch.tensor([val_tokens[i:i+seq_len]], device=device)
            y = torch.tensor([val_tokens[i+1:i+seq_len+1]], device=device)

            output = model(x)
            logits = output['logits']

            loss = F.cross_entropy(
                logits.view(-1, logits.size(-1)),
                y.view(-1),
            )
            total_loss += loss.item()
            num_batches += 1

            if num_batches >= 20:  # Check first 20 batches
                break

    avg_loss = total_loss / num_batches
    ppl = math.exp(avg_loss)
    print(f"   Average loss: {avg_loss:.4f}")
    print(f"   PPL: {ppl:.2f}")

    # Compare with reported PPL
    reported_ppl = math.exp(state.get('best_val_loss', 0))
    print(f"   Reported PPL: {reported_ppl:.2f}")
    if abs(ppl - reported_ppl) > 10:
        print(f"   WARNING: Significant PPL mismatch!")
    else:
        print(f"   OK: PPL matches (within tolerance)")

    # Test 2: Check logits distribution
    print(f"\n6. Checking logits distribution...")
    with torch.no_grad():
        x = torch.tensor([val_tokens[:100]], device=device)
        output = model(x)
        logits = output['logits']

        print(f"   Logits shape: {logits.shape}")
        print(f"   Logits min: {logits.min().item():.2f}")
        print(f"   Logits max: {logits.max().item():.2f}")
        print(f"   Logits mean: {logits.mean().item():.2f}")
        print(f"   Logits std: {logits.std().item():.2f}")

        # Check if logits are all zeros or constant
        if logits.std().item() < 0.1:
            print(f"   WARNING: Logits have very low variance!")
        else:
            print(f"   OK: Logits have reasonable variance")

    # Test 3: Test generation using built-in method
    print(f"\n7. Testing built-in generation...")
    test_prompts = [
        "The meaning of life is",
        "In the year 2050,",
        "The quick brown fox",
    ]

    for prompt in test_prompts:
        tokens = tokenizer.encode(prompt, return_tensors="pt").to(device)
        print(f"\n   Prompt: '{prompt}'")

        with torch.no_grad():
            # Use model's built-in generate
            output_ids = model.generate(
                tokens,
                max_new_tokens=20,
                temperature=0.8,
                top_k=50,
            )

            generated = tokenizer.decode(output_ids[0], skip_special_tokens=True)
            print(f"   Generated: '{generated}'")

    # Test 4: Greedy decoding (simpler)
    print(f"\n8. Testing greedy decoding...")
    prompt = "Hello world"
    tokens = tokenizer.encode(prompt, return_tensors="pt").to(device)
    print(f"   Prompt: '{prompt}'")

    with torch.no_grad():
        for i in range(20):
            output = model(tokens)
            logits = output['logits'][:, -1, :]
            next_token = torch.argmax(logits, dim=-1, keepdim=True)
            tokens = torch.cat([tokens, next_token], dim=1)

        generated = tokenizer.decode(tokens[0], skip_special_tokens=True)
        print(f"   Greedy: '{generated}'")

    # Test 5: Top-5 predictions at each position
    print(f"\n9. Checking top-5 predictions...")
    prompt = "The capital of France is"
    tokens = tokenizer.encode(prompt, return_tensors="pt").to(device)

    with torch.no_grad():
        output = model(tokens)
        logits = output['logits'][:, -1, :]
        probs = F.softmax(logits, dim=-1)
        top5 = torch.topk(probs, 5)

        print(f"   Prompt: '{prompt}'")
        print(f"   Top 5 predictions:")
        for i in range(5):
            token_id = top5.indices[0][i].item()
            prob = top5.values[0][i].item()
            token = tokenizer.decode([token_id])
            print(f"     {i+1}. '{token}' ({prob*100:.1f}%)")

    print("\n" + "="*60)
    print("DIAGNOSIS COMPLETE")
    print("="*60)


if __name__ == "__main__":
    main()
