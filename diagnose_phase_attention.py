#!/usr/bin/env python3
"""
Phase Attention Diagnostic Script
==================================

Analyzes what the phase attention layers are actually doing:
1. Are phase attention outputs contributing to final output?
2. Is information flowing through the sync steps?
3. What's the attention pattern distribution?

Usage:
    python diagnose_phase_attention.py --checkpoint checkpoints_1k_fast/best.pt
"""

import argparse
import torch
import torch.nn.functional as F
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

    return model, config


def analyze_layer_contributions(model, tokens, device):
    """Analyze how much each layer contributes to the output."""
    print("\n" + "=" * 60)
    print("  Layer Contribution Analysis")
    print("=" * 60)

    with torch.no_grad():
        # Get embeddings
        B, N = tokens.shape
        positions = torch.arange(N, device=device).unsqueeze(0)
        x = model.token_embed(tokens) + model.pos_embed(positions)
        x = model.embed_dropout(x)

        layer_norms = []
        layer_changes = []

        for i, block in enumerate(model.blocks):
            x_before = x.clone()
            x = block(x, causal_mask=True)

            # Measure how much this layer changed the representation
            change = (x - x_before).norm().item()
            layer_changes.append(change)
            layer_norms.append(x.norm().item())

        # Identify layer types
        local_layers = getattr(model, 'local_layers', 4)

        print(f"\n  Layer contributions (change magnitude):")
        print(f"  {'Layer':<8} {'Type':<15} {'Change':<12} {'Output Norm':<12}")
        print("  " + "-" * 50)

        for i, (change, norm) in enumerate(zip(layer_changes, layer_norms)):
            layer_type = "Local" if i < local_layers else "Hybrid (L+P)"
            print(f"  {i+1:<8} {layer_type:<15} {change:<12.2f} {norm:<12.2f}")

        # Summary
        local_total = sum(layer_changes[:local_layers])
        hybrid_total = sum(layer_changes[local_layers:])

        print(f"\n  Summary:")
        print(f"  Local layers (1-{local_layers}) total change: {local_total:.2f}")
        print(f"  Hybrid layers ({local_layers+1}-{len(layer_changes)}) total change: {hybrid_total:.2f}")
        print(f"  Ratio (Hybrid/Local): {hybrid_total/local_total:.2f}x")


def analyze_attention_weights(model, tokens, device):
    """Analyze attention weight distributions in hybrid layers."""
    print("\n" + "=" * 60)
    print("  Attention Weight Analysis (Hybrid Layers)")
    print("=" * 60)

    local_layers = getattr(model, 'local_layers', 4)

    with torch.no_grad():
        # Get embeddings
        B, N = tokens.shape
        positions = torch.arange(N, device=device).unsqueeze(0)
        x = model.token_embed(tokens) + model.pos_embed(positions)
        x = model.embed_dropout(x)

        # Process through layers
        for i, block in enumerate(model.blocks):
            if i >= local_layers:
                # This is a hybrid layer - analyze its attention
                attn = block.attention

                # Check if it has local and phase components
                if hasattr(attn, 'local_attn') and hasattr(attn, 'phase_attn'):
                    alpha_local = getattr(attn, 'alpha_local', 0.8)
                    alpha_phase = getattr(attn, 'alpha_phase', 0.2)

                    print(f"\n  Layer {i+1} (Hybrid):")
                    print(f"    alpha_local: {alpha_local}")
                    print(f"    alpha_phase: {alpha_phase}")

                    # Get local attention output
                    local_out = attn.local_attn(x, causal_mask=True)
                    local_norm = local_out.norm().item()

                    # Get phase attention output
                    phase_out = attn.phase_attn(x, causal_mask=True)
                    phase_norm = phase_out.norm().item()

                    print(f"    Local output norm: {local_norm:.2f}")
                    print(f"    Phase output norm: {phase_norm:.2f}")
                    print(f"    Weighted contribution ratio: {(alpha_local * local_norm) / (alpha_phase * phase_norm + 1e-8):.2f}:1")

            x = block(x, causal_mask=True)


def analyze_phase_attention_internals(model, tokens, device):
    """Deep dive into phase attention mechanism."""
    print("\n" + "=" * 60)
    print("  Phase Attention Internals")
    print("=" * 60)

    local_layers = getattr(model, 'local_layers', 4)

    with torch.no_grad():
        B, N = tokens.shape
        positions = torch.arange(N, device=device).unsqueeze(0)
        x = model.token_embed(tokens) + model.pos_embed(positions)
        x = model.embed_dropout(x)

        # Find first hybrid layer
        for i, block in enumerate(model.blocks):
            if i >= local_layers:
                attn = block.attention
                if hasattr(attn, 'phase_attn'):
                    phase = attn.phase_attn

                    print(f"\n  Phase Attention (Layer {i+1}):")
                    print(f"    embed_dim: {phase.embed_dim}")
                    print(f"    num_heads: {phase.num_heads}")
                    print(f"    sync_steps: {phase.sync_steps}")
                    print(f"    sync_lr: {phase.sync_lr}")

                    # Check phase parameters
                    if hasattr(phase, 'phase_base'):
                        phase_base = phase.phase_base
                        print(f"    phase_base shape: {phase_base.shape}")
                        print(f"    phase_base range: [{phase_base.min().item():.4f}, {phase_base.max().item():.4f}]")

                    if hasattr(phase, 'freq_scale'):
                        print(f"    freq_scale: {phase.freq_scale.item():.4f}")

                    # Analyze Q, K, V projections
                    Q = phase.q_proj(x)
                    K = phase.k_proj(x)
                    V = phase.v_proj(x)

                    print(f"\n    Projection norms:")
                    print(f"      Q: {Q.norm().item():.2f}")
                    print(f"      K: {K.norm().item():.2f}")
                    print(f"      V: {V.norm().item():.2f}")

                    # Check if values are collapsed
                    q_std = Q.std().item()
                    k_std = K.std().item()
                    v_std = V.std().item()

                    print(f"    Projection stds:")
                    print(f"      Q: {q_std:.4f}")
                    print(f"      K: {k_std:.4f}")
                    print(f"      V: {v_std:.4f}")

                    if q_std < 0.01 or k_std < 0.01 or v_std < 0.01:
                        print(f"    WARNING: Very low std - possible collapse!")

                    break  # Analyze just first hybrid layer

            x = block(x, causal_mask=True)


def test_long_range_attention(model, tokenizer, device):
    """Test if phase attention can attend to distant tokens."""
    print("\n" + "=" * 60)
    print("  Long-Range Attention Test")
    print("=" * 60)

    # Create a test with a key fact early and question late
    # Format: "The key is X. [padding] What is the key?"
    key = "42"
    padding = "The sky is blue. " * 50  # ~300 tokens of padding

    prompt = f"The answer is {key}. {padding}The answer is"
    tokens = tokenizer.encode(prompt, return_tensors="pt").to(device)

    print(f"\n  Test prompt structure:")
    print(f"    'The answer is {key}.' + [~300 tokens padding] + 'The answer is'")
    print(f"    Total tokens: {tokens.shape[1]}")

    with torch.no_grad():
        output = model(tokens)
        logits = output['logits'][:, -1, :]

        # Get top predictions
        probs = F.softmax(logits, dim=-1)
        top5 = torch.topk(probs, 5)

        print(f"\n  Top 5 predictions after 'The answer is':")
        for i in range(5):
            token_id = top5.indices[0][i].item()
            prob = top5.values[0][i].item()
            token = tokenizer.decode([token_id])
            marker = " <-- CORRECT!" if token.strip() == key else ""
            print(f"    {i+1}. '{token}' ({prob*100:.1f}%){marker}")

        # Check if "42" is in top predictions
        key_token = tokenizer.encode(" " + key)[0]
        key_prob = probs[0, key_token].item()
        key_rank = (probs[0] > probs[0, key_token]).sum().item() + 1

        print(f"\n  Target '{key}':")
        print(f"    Probability: {key_prob*100:.2f}%")
        print(f"    Rank: {key_rank}")

        if key_rank <= 10:
            print(f"    Status: OK - Long-range attention working")
        else:
            print(f"    Status: FAIL - Cannot retrieve from distance")


def main():
    parser = argparse.ArgumentParser(description="Diagnose Phase Attention")
    parser.add_argument("--checkpoint", type=str, default="checkpoints_1k_fast/best.pt")
    parser.add_argument("--device", type=str, default="cuda")
    args = parser.parse_args()

    if args.device == "cuda" and not torch.cuda.is_available():
        args.device = "cpu"
    device = torch.device(args.device)
    print(f"Using device: {device}")

    tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
    model, config = load_model(args.checkpoint, device)

    # Print model architecture info
    print("\n" + "=" * 60)
    print("  Model Architecture")
    print("=" * 60)
    print(f"  Model type: {type(model).__name__}")
    print(f"  Total layers: {len(model.blocks)}")
    print(f"  Local layers: {getattr(model, 'local_layers', 'N/A')}")
    print(f"  Embed dim: {model.config.embed_dim}")
    print(f"  Num heads: {model.config.num_heads}")

    # Sample text for analysis
    sample_text = "The quick brown fox jumps over the lazy dog. This is a test of the attention mechanism."
    tokens = tokenizer.encode(sample_text, return_tensors="pt").to(device)
    print(f"  Test sequence length: {tokens.shape[1]} tokens")

    # Run diagnostics
    analyze_layer_contributions(model, tokens, device)
    analyze_attention_weights(model, tokens, device)
    analyze_phase_attention_internals(model, tokens, device)
    test_long_range_attention(model, tokenizer, device)

    print("\n" + "=" * 60)
    print("  DIAGNOSIS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
