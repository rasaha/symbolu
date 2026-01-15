#!/usr/bin/env python3
"""
Phase Dynamics Diagnostic - Gemini's "Phase Entropy" Analysis

Diagnoses the health of Phase Attention by measuring:
1. Phase Entropy - Are phases diverse or collapsed?
2. Amplitude Distribution - Is cumsum saturating?
3. Q-K Alignment - Is phase attention being ignored?
4. Learned Decay Diversity - Are heads specializing?

Usage:
    python diagnose_phase_dynamics.py --checkpoint checkpoints_unified/best.pt
"""

import argparse
import torch
import torch.nn as nn
import numpy as np
from pathlib import Path
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from train_unified_llm import UnifiedTrainingConfig, create_model


class PhaseAttentionHook:
    """Hook to capture phase attention internals during forward pass."""

    def __init__(self):
        self.phi_q = None  # Query phases
        self.phi_k = None  # Key phases
        self.a_q = None    # Query amplitudes
        self.a_k = None    # Key amplitudes
        self.gamma = None  # Learned decay values
        self.global_state_norm = None  # State accumulator norm

    def hook_fn(self, module, input, output):
        """Capture internals from PhaseAttention forward pass."""
        # We'll store the captured values in the module for retrieval
        if hasattr(module, '_diag_phi_q'):
            self.phi_q = module._diag_phi_q.detach().cpu()
            self.phi_k = module._diag_phi_k.detach().cpu()
            self.a_q = module._diag_a_q.detach().cpu()
            self.a_k = module._diag_a_k.detach().cpu()
        if hasattr(module, '_diag_gamma'):
            self.gamma = module._diag_gamma.detach().cpu()
        if hasattr(module, '_diag_state_norm'):
            self.global_state_norm = module._diag_state_norm.detach().cpu()


def patch_phase_attention_for_diagnostics(model):
    """
    Monkey-patch PhaseAttentionLayer to capture diagnostic values.

    This adds diagnostic capture to the forward pass without changing behavior.
    """
    from symbolu.phase_transformer import PhaseAttentionLayer

    original_forward = PhaseAttentionLayer.forward

    def diagnostic_forward(self, x, causal_mask=True, phase_context=None, intent_phase=None):
        # Run original forward with all arguments
        result = original_forward(self, x, causal_mask, phase_context, intent_phase)

        # Capture diagnostic values (these are computed in forward)
        # We need to recompute them here since they're not stored
        B, N, C = x.shape

        # Recompute phases and amplitudes for diagnostics
        with torch.no_grad():
            x_norm = self.norm(x)

            # Query phase and amplitude
            phi_q_raw = self.W_q_phase(x_norm)
            a_q_raw = self.W_q_amp(x_norm)

            # Key phase and amplitude
            phi_k_raw = self.W_k_phase(x_norm)
            a_k_raw = self.W_k_amp(x_norm)

            # Reshape to heads
            H = self.num_heads
            D_h = C // H

            phi_q = phi_q_raw.view(B, N, H, D_h)
            phi_k = phi_k_raw.view(B, N, H, D_h)
            a_q = torch.sigmoid(a_q_raw.view(B, N, H, D_h))
            a_k = torch.sigmoid(a_k_raw.view(B, N, H, D_h))

            # Store for hook
            self._diag_phi_q = phi_q
            self._diag_phi_k = phi_k
            self._diag_a_q = a_q
            self._diag_a_k = a_k

            # Capture learned decay if available
            if hasattr(self, 'learned_decay') and self.learned_decay:
                gamma = 0.5 + 0.5 * torch.sigmoid(self.decay_logit)
                self._diag_gamma = gamma

        return result

    PhaseAttentionLayer.forward = diagnostic_forward
    return original_forward  # Return for restoration


def compute_phase_entropy(phi, num_bins=50):
    """
    Compute entropy of phase distribution.

    Higher entropy = more diverse phases (healthy)
    Lower entropy = collapsed phases (sick)

    Args:
        phi: Phase tensor of any shape (will be flattened)
        num_bins: Number of histogram bins

    Returns:
        entropy: Scalar entropy value
    """
    phi_flat = phi.numpy().flatten()

    # Normalize to [0, 2π]
    phi_norm = np.mod(phi_flat, 2 * np.pi)

    # Compute histogram
    hist, _ = np.histogram(phi_norm, bins=num_bins, range=(0, 2 * np.pi), density=True)

    # Compute entropy (avoid log(0))
    hist = hist + 1e-10
    entropy = -np.sum(hist * np.log(hist)) * (2 * np.pi / num_bins)

    return entropy


def compute_phase_std(phi):
    """Compute circular standard deviation of phases."""
    phi_flat = phi.numpy().flatten()

    # Circular statistics
    sin_mean = np.mean(np.sin(phi_flat))
    cos_mean = np.mean(np.cos(phi_flat))
    R = np.sqrt(sin_mean**2 + cos_mean**2)

    # Circular std (in radians)
    if R > 1e-10:
        circ_std = np.sqrt(-2 * np.log(R))
    else:
        circ_std = np.pi  # Maximum dispersion

    return circ_std


def analyze_layer(hook, layer_idx):
    """Analyze captured phase attention data for one layer."""
    results = {}

    if hook.phi_q is not None:
        # Phase Analysis
        phi_q_entropy = compute_phase_entropy(hook.phi_q)
        phi_k_entropy = compute_phase_entropy(hook.phi_k)
        phi_q_std = compute_phase_std(hook.phi_q)
        phi_k_std = compute_phase_std(hook.phi_k)

        results['phi_q_entropy'] = phi_q_entropy
        results['phi_k_entropy'] = phi_k_entropy
        results['phi_q_std'] = phi_q_std
        results['phi_k_std'] = phi_k_std

        # Q-K Alignment (how correlated are query and key phases?)
        phi_diff = hook.phi_q - hook.phi_k
        alignment = torch.cos(phi_diff).mean().item()
        results['qk_alignment'] = alignment

        # Amplitude Analysis
        a_q_mean = hook.a_q.mean().item()
        a_k_mean = hook.a_k.mean().item()
        a_q_std = hook.a_q.std().item()
        a_k_std = hook.a_k.std().item()

        results['a_q_mean'] = a_q_mean
        results['a_k_mean'] = a_k_mean
        results['a_q_std'] = a_q_std
        results['a_k_std'] = a_k_std

    if hook.gamma is not None:
        # Learned Decay Analysis (per-head)
        gamma = hook.gamma.numpy()
        results['gamma_mean'] = gamma.mean()
        results['gamma_std'] = gamma.std()
        results['gamma_min'] = gamma.min()
        results['gamma_max'] = gamma.max()
        results['gamma_per_head'] = gamma.tolist()

    return results


def get_health_status(results):
    """
    Interpret results and return health status.

    Based on Gemini's diagnostic thresholds.
    """
    status = []

    # Phase Entropy Check
    if 'phi_q_entropy' in results:
        entropy = results['phi_q_entropy']
        if entropy > 2.5:
            status.append(("Phase Entropy", "HEALTHY", f"{entropy:.2f} > 2.5"))
        elif entropy > 1.0:
            status.append(("Phase Entropy", "WARNING", f"{entropy:.2f} (1.0-2.5)"))
        else:
            status.append(("Phase Entropy", "SICK", f"{entropy:.2f} < 1.0 - COLLAPSED"))

    # Phase Std Dev Check
    if 'phi_q_std' in results:
        std = results['phi_q_std']
        if std > 1.0:
            status.append(("Phase Std Dev", "HEALTHY", f"{std:.2f} rad > 1.0"))
        elif std > 0.5:
            status.append(("Phase Std Dev", "WARNING", f"{std:.2f} rad (0.5-1.0)"))
        else:
            status.append(("Phase Std Dev", "SICK", f"{std:.2f} rad < 0.5 - HUDDLED"))

    # Amplitude Check
    if 'a_k_mean' in results:
        amp = results['a_k_mean']
        if 0.3 <= amp <= 0.7:
            status.append(("Amplitude", "HEALTHY", f"{amp:.2f} in [0.3, 0.7]"))
        elif amp > 0.9:
            status.append(("Amplitude", "SICK", f"{amp:.2f} > 0.9 - SATURATED"))
        elif amp < 0.1:
            status.append(("Amplitude", "SICK", f"{amp:.2f} < 0.1 - MUTED"))
        else:
            status.append(("Amplitude", "WARNING", f"{amp:.2f}"))

    # Q-K Alignment Check
    if 'qk_alignment' in results:
        align = results['qk_alignment']
        if abs(align) < 0.3:
            status.append(("Q-K Alignment", "HEALTHY", f"{align:.2f} - Variable"))
        elif abs(align) > 0.8:
            status.append(("Q-K Alignment", "WARNING", f"{align:.2f} - Too correlated"))
        else:
            status.append(("Q-K Alignment", "OK", f"{align:.2f}"))

    # Learned Decay Diversity Check
    if 'gamma_std' in results:
        gamma_std = results['gamma_std']
        gamma_range = results['gamma_max'] - results['gamma_min']
        if gamma_std > 0.1 or gamma_range > 0.3:
            status.append(("Decay Diversity", "HEALTHY", f"std={gamma_std:.3f}, range={gamma_range:.3f} - Heads specializing"))
        elif gamma_std > 0.01:
            status.append(("Decay Diversity", "WARNING", f"std={gamma_std:.3f} - Limited specialization"))
        else:
            status.append(("Decay Diversity", "SICK", f"std={gamma_std:.3f} - All heads identical"))

    return status


def run_diagnostic(model, dataloader, device, num_batches=5):
    """
    Run full phase dynamics diagnostic.

    Args:
        model: The model to diagnose
        dataloader: DataLoader with sample data
        device: torch device
        num_batches: Number of batches to average over

    Returns:
        Dictionary of results per layer
    """
    model.eval()

    # Find all PhaseAttentionLayer modules
    phase_modules = []
    for name, module in model.named_modules():
        if module.__class__.__name__ == 'PhaseAttentionLayer':
            phase_modules.append((name, module))

    if not phase_modules:
        print("  No PhaseAttention modules found!")
        return {}

    print(f"  Found {len(phase_modules)} PhaseAttention modules")

    # Patch for diagnostics
    original_forward = patch_phase_attention_for_diagnostics(model)

    # Register hooks
    hooks = {}
    handles = []
    for name, module in phase_modules:
        hook = PhaseAttentionHook()
        handle = module.register_forward_hook(hook.hook_fn)
        hooks[name] = hook
        handles.append(handle)

    # Run forward passes
    all_results = {name: [] for name, _ in phase_modules}

    with torch.no_grad():
        for batch_idx, batch in enumerate(dataloader):
            if batch_idx >= num_batches:
                break

            if isinstance(batch, dict):
                input_ids = batch['input_ids'].to(device)
            else:
                input_ids = batch.to(device)

            # Forward pass
            try:
                _ = model(input_ids)
            except Exception as e:
                print(f"  Warning: Forward pass failed: {e}")
                continue

            # Collect results
            for name, hook in hooks.items():
                layer_results = analyze_layer(hook, name)
                if layer_results:
                    all_results[name].append(layer_results)

    # Clean up hooks
    for handle in handles:
        handle.remove()

    # Restore original forward
    from symbolu.phase_transformer import PhaseAttentionLayer
    PhaseAttentionLayer.forward = original_forward

    # Average results across batches
    averaged_results = {}
    for name, results_list in all_results.items():
        if not results_list:
            continue

        avg = {}
        for key in results_list[0].keys():
            if key == 'gamma_per_head':
                # Keep the last one for per-head display
                avg[key] = results_list[-1][key]
            else:
                values = [r[key] for r in results_list]
                avg[key] = np.mean(values)
        averaged_results[name] = avg

    return averaged_results


def print_diagnostic_report(results):
    """Print a formatted diagnostic report."""
    print("\n" + "=" * 70)
    print("   PHASE DYNAMICS DIAGNOSTIC REPORT")
    print("   (Gemini's Phase Entropy Analysis)")
    print("=" * 70)

    if not results:
        print("\n  No results to report!")
        return

    for layer_name, layer_results in results.items():
        # Extract layer number
        print(f"\n  Layer: {layer_name}")
        print("  " + "-" * 50)

        # Get health status
        health = get_health_status(layer_results)

        # Print metrics
        print("\n  Phase Distribution:")
        if 'phi_q_entropy' in layer_results:
            print(f"    Query Entropy:  {layer_results['phi_q_entropy']:.3f}")
            print(f"    Key Entropy:    {layer_results['phi_k_entropy']:.3f}")
            print(f"    Query Std Dev:  {layer_results['phi_q_std']:.3f} rad")
            print(f"    Key Std Dev:    {layer_results['phi_k_std']:.3f} rad")

        print("\n  Amplitude Distribution:")
        if 'a_q_mean' in layer_results:
            print(f"    Query Amp:  mean={layer_results['a_q_mean']:.3f}, std={layer_results['a_q_std']:.3f}")
            print(f"    Key Amp:    mean={layer_results['a_k_mean']:.3f}, std={layer_results['a_k_std']:.3f}")

        print("\n  Q-K Relationship:")
        if 'qk_alignment' in layer_results:
            print(f"    Alignment:  {layer_results['qk_alignment']:.3f} (0=orthogonal, 1=aligned)")

        if 'gamma_per_head' in layer_results:
            print("\n  Learned Decay (per-head γ):")
            gamma = layer_results['gamma_per_head']
            print(f"    Range: [{layer_results['gamma_min']:.4f}, {layer_results['gamma_max']:.4f}]")
            print(f"    Std:   {layer_results['gamma_std']:.4f}")
            print(f"    Heads: {['%.3f' % g for g in gamma]}")

        # Health Summary
        print("\n  Health Status:")
        for metric, status, detail in health:
            icon = "✅" if status == "HEALTHY" else "⚠️" if status in ["WARNING", "OK"] else "🔴"
            print(f"    {icon} {metric}: {status} ({detail})")

    print("\n" + "=" * 70)
    print("   INTERPRETATION GUIDE")
    print("=" * 70)
    print("""
  Phase Entropy > 2.5:  Phases are diverse (model distinguishes concepts)
  Phase Entropy < 1.0:  Phases collapsed (model treats all tokens same)

  Phase Std > 1.0 rad:  Good spread across complex plane
  Phase Std < 0.5 rad:  Phases huddled in one corner

  Amplitude 0.3-0.7:    Healthy signal strength
  Amplitude > 0.9:      Saturation - cumsum smear likely
  Amplitude < 0.1:      Layer effectively muted

  Q-K Alignment ~0:     Variable (healthy selective attention)
  Q-K Alignment ~1:     Always aligned (no selectivity)

  Decay Diversity:      High std = heads specializing
                        (some long-memory, some short-memory)
    """)


def main():
    parser = argparse.ArgumentParser(description="Phase Dynamics Diagnostic")
    parser.add_argument("--checkpoint", type=str, default="checkpoints_unified/best.pt",
                       help="Path to checkpoint")
    parser.add_argument("--num_batches", type=int, default=5,
                       help="Number of batches to average over")
    parser.add_argument("--batch_size", type=int, default=4,
                       help="Batch size for diagnostic")
    parser.add_argument("--seq_len", type=int, default=512,
                       help="Sequence length for diagnostic")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\n  Device: {device}")

    # Load checkpoint
    print(f"  Loading checkpoint: {args.checkpoint}")
    checkpoint = torch.load(args.checkpoint, map_location=device, weights_only=False)

    # Get config
    if 'config' in checkpoint:
        config_dict = checkpoint['config']
        config = UnifiedTrainingConfig(**config_dict)
    else:
        # Try loading config from JSON file in same directory
        config_path = Path(args.checkpoint).parent / "config.json"
        if config_path.exists():
            import json
            with open(config_path) as f:
                config_dict = json.load(f)
            config = UnifiedTrainingConfig(**config_dict)
            print(f"  Loaded config from {config_path}")
        else:
            print("  Warning: No config in checkpoint, using defaults")
            config = UnifiedTrainingConfig(model_type="ontological_hybrid")

    # Create model
    print(f"  Creating model: {config.model_type}")
    model = create_model(config, device)

    # Load weights
    if 'model' in checkpoint:
        model.load_state_dict(checkpoint['model'], strict=False)
    print("  Model loaded")

    model.eval()

    # Create simple dataloader with random data
    print(f"\n  Creating diagnostic dataloader (batch={args.batch_size}, seq={args.seq_len})")

    # Use random token IDs for diagnostic
    class DiagnosticDataset(torch.utils.data.Dataset):
        def __init__(self, num_samples, seq_len, vocab_size=50257):
            self.num_samples = num_samples
            self.seq_len = seq_len
            self.vocab_size = vocab_size

        def __len__(self):
            return self.num_samples

        def __getitem__(self, idx):
            return torch.randint(0, self.vocab_size, (self.seq_len,))

    dataset = DiagnosticDataset(args.num_batches * args.batch_size, args.seq_len)
    dataloader = torch.utils.data.DataLoader(dataset, batch_size=args.batch_size)

    # Run diagnostic
    print("\n  Running phase dynamics diagnostic...")
    results = run_diagnostic(model, dataloader, device, args.num_batches)

    # Print report
    print_diagnostic_report(results)


if __name__ == "__main__":
    main()
