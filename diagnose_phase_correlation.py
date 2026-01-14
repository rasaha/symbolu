#!/usr/bin/env python3
"""
Diagnose why phase attention has zero impact despite correct alpha values.
Checks correlation between phase and local attention outputs.
"""

import torch
import torch.nn.functional as F
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from symbolu.phase_transformer import OntologicalHybridTransformer
from symbolu.config import UnifiedTrainingConfig
import json


def load_model(checkpoint_path: str):
    """Load model from checkpoint."""
    print(f"Loading checkpoint: {checkpoint_path}")

    # Load config
    config_path = Path(checkpoint_path).parent / "config.json"
    with open(config_path, 'r') as f:
        config_dict = json.load(f)

    config = UnifiedTrainingConfig(**config_dict)

    # Create model
    if config.model_type == "ontological_hybrid":
        model = OntologicalHybridTransformer(
            vocab_size=config.vocab_size,
            d_model=config.d_model,
            n_layers=config.n_layers,
            n_heads=config.n_heads,
            d_ff=config.d_ff,
            dropout=config.dropout,
            max_seq_len=config.max_seq_len,
            state_dim=config.state_dim,
            local_layers=config.local_layers,
            window_size=config.window_size,
            local_backend=config.local_backend,
            alpha_local=config.alpha_local,
            alpha_phase=config.alpha_phase,
            tie_embeddings=True,
            cosine_mode=config.cosine_mode,
        )
    else:
        raise ValueError(f"Unsupported model type: {config.model_type}")

    # Load weights
    checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=False)
    model.load_state_dict(checkpoint['model'], strict=False)
    model.eval()

    return model, config


def analyze_phase_local_correlation(model, batch_size=4, seq_len=128):
    """Analyze correlation between phase and local attention outputs."""

    print(f"\n{'='*70}")
    print("PHASE vs LOCAL ATTENTION CORRELATION ANALYSIS")
    print(f"{'='*70}\n")

    # Generate test batch
    x = torch.randint(0, 50257, (batch_size, seq_len))
    print(f"Test batch: shape={x.shape}\n")

    # Storage for outputs
    phase_outputs = {}
    local_outputs = {}
    blended_outputs = {}

    # Hook to capture outputs
    def make_hook(storage, name):
        def hook(module, input, output):
            if isinstance(output, tuple):
                storage[name] = output[0].detach()
            else:
                storage[name] = output.detach()
        return hook

    # Register hooks on hybrid layers
    hooks = []
    for i in range(model.local_layers, model.n_layers):
        layer = model.hybrid.blocks[i].attention

        # Hook phase attention
        if hasattr(layer, 'phase_attn'):
            h = layer.phase_attn.register_forward_hook(
                make_hook(phase_outputs, f'layer_{i}')
            )
            hooks.append(h)

        # Hook local attention
        if hasattr(layer, 'local_attn'):
            h = layer.local_attn.register_forward_hook(
                make_hook(local_outputs, f'layer_{i}')
            )
            hooks.append(h)

        # Hook the blended output (after combining phase + local)
        h = layer.register_forward_hook(
            make_hook(blended_outputs, f'layer_{i}')
        )
        hooks.append(h)

    # Forward pass
    with torch.no_grad():
        output = model(x)

    # Remove hooks
    for h in hooks:
        h.remove()

    # Analyze each layer
    print(f"{'Layer':<8} {'Phase Norm':<12} {'Local Norm':<12} {'Correlation':<12} {'Phase/Local':<12} {'Blend Check':<12}")
    print("-" * 80)

    results = {}

    for i in range(model.local_layers, model.n_layers):
        layer_name = f'layer_{i}'

        if layer_name not in phase_outputs or layer_name not in local_outputs:
            continue

        phase_out = phase_outputs[layer_name]
        local_out = local_outputs[layer_name]
        blended_out = blended_outputs[layer_name]

        # Compute statistics
        phase_norm = phase_out.norm().item()
        local_norm = local_out.norm().item()
        phase_std = phase_out.std().item()
        local_std = local_out.std().item()

        # Correlation
        phase_flat = phase_out.flatten()
        local_flat = local_out.flatten()

        # Cosine similarity (correlation)
        corr = F.cosine_similarity(phase_flat, local_flat, dim=0).item()

        # Ratio of norms
        norm_ratio = phase_norm / (local_norm + 1e-8)

        # Check if blend matches expected (0.4 * phase + 0.6 * local)
        expected_blend = 0.4 * phase_out + 0.6 * local_out
        blend_error = (blended_out - expected_blend).norm().item()

        results[i] = {
            'phase_norm': phase_norm,
            'local_norm': local_norm,
            'phase_std': phase_std,
            'local_std': local_std,
            'correlation': corr,
            'norm_ratio': norm_ratio,
            'blend_error': blend_error,
        }

        print(f"Layer {i:<3} {phase_norm:<12.4f} {local_norm:<12.4f} {corr:<12.4f} {norm_ratio:<12.4f} {blend_error:<12.6f}")

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}\n")

    avg_corr = sum(r['correlation'] for r in results.values()) / len(results)
    avg_norm_ratio = sum(r['norm_ratio'] for r in results.values()) / len(results)

    print(f"Average correlation: {avg_corr:.4f}")
    print(f"Average phase/local norm ratio: {avg_norm_ratio:.4f}")

    # Diagnosis
    print(f"\n{'='*70}")
    print("DIAGNOSIS")
    print(f"{'='*70}\n")

    if avg_corr > 0.9:
        print("❌ HIGH CORRELATION (>0.9)")
        print("   Phase and local attention are computing nearly identical outputs.")
        print("   This explains why ablation shows no effect.")
        print("   Fix: Add decorrelation loss or architectural changes.")
    elif avg_norm_ratio < 0.01:
        print("❌ PHASE OUTPUT TOO SMALL")
        print("   Phase attention outputs have very low magnitude.")
        print("   Despite 40% weight, contribution is negligible.")
        print("   Fix: Check phase attention initialization or add gradient scaling.")
    elif avg_norm_ratio > 10.0:
        print("❌ PHASE OUTPUT TOO LARGE")
        print("   Phase attention outputs dominate despite lower weight.")
        print("   Fix: Add gradient clipping or output normalization.")
    elif avg_corr > 0.5:
        print("⚠️  MODERATE CORRELATION (0.5-0.9)")
        print("   Phase and local share some patterns but aren't identical.")
        print("   Still problematic - phase should learn different features.")
        print("   Fix: Consider architectural changes to force diversity.")
    else:
        print("✅ OUTPUTS ARE DIVERSE")
        print("   Phase and local compute different things (correlation < 0.5).")
        print("   But ablation still shows no effect!")
        print("   This suggests phase output is IRRELEVANT, not redundant.")
        print("   Fix: Phase attention may need fundamental redesign.")

    # Check for numerical issues
    print(f"\n{'='*70}")
    print("NUMERICAL STABILITY CHECK")
    print(f"{'='*70}\n")

    for i, stats in results.items():
        if stats['phase_std'] < 1e-6:
            print(f"⚠️  Layer {i}: Phase std too low ({stats['phase_std']:.2e}) - near constant output")
        if stats['blend_error'] > 0.1:
            print(f"⚠️  Layer {i}: Blend error ({stats['blend_error']:.4f}) - alpha blending may be broken")

    return results


def check_phase_parameters(checkpoint_path: str):
    """Check if phase attention parameters are being learned."""

    print(f"\n{'='*70}")
    print("PHASE ATTENTION PARAMETER CHECK")
    print(f"{'='*70}\n")

    ckpt = torch.load(checkpoint_path, map_location='cpu', weights_only=False)

    phase_params = {}
    for k, v in ckpt['model'].items():
        if 'phase_attn' in k and ('weight' in k or 'bias' in k):
            norm = v.norm().item()
            mean_abs = v.abs().mean().item()
            std = v.std().item()
            phase_params[k] = {
                'shape': v.shape,
                'norm': norm,
                'mean_abs': mean_abs,
                'std': std,
            }

    print(f"{'Parameter':<60} {'Norm':<12} {'Mean |x|':<12} {'Std':<12}")
    print("-" * 100)

    for name, stats in list(phase_params.items())[:20]:  # Show first 20
        print(f"{name:<60} {stats['norm']:<12.4f} {stats['mean_abs']:<12.4f} {stats['std']:<12.4f}")

    if len(phase_params) > 20:
        print(f"... and {len(phase_params) - 20} more parameters")

    # Check if parameters are too small (not learning)
    avg_norm = sum(p['norm'] for p in phase_params.values()) / len(phase_params)

    print(f"\nAverage parameter norm: {avg_norm:.4f}")

    if avg_norm < 0.01:
        print("❌ Parameters are very small - may not be learning effectively")
    elif avg_norm > 10.0:
        print("⚠️  Parameters are large - check for instability")
    else:
        print("✅ Parameters appear normal")


if __name__ == "__main__":
    checkpoint_path = "checkpoints_unified/last.pt"

    # First check parameters
    check_phase_parameters(checkpoint_path)

    # Then load model and check correlations
    model, config = load_model(checkpoint_path)

    print(f"\nModel loaded: {config.model_type}")
    print(f"Local layers: {model.local_layers}")
    print(f"Hybrid layers: {model.local_layers} to {model.n_layers-1}")

    # Run correlation analysis
    results = analyze_phase_local_correlation(model, batch_size=4, seq_len=256)

    print(f"\n{'='*70}")
    print("Analysis complete.")
    print(f"{'='*70}")
