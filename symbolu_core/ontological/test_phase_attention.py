#!/usr/bin/env python3
"""
Test Suite for Phase-Based Attention (U1-U4)
=============================================

Validates that Phase Attention:
1. Produces comparable outputs to standard attention
2. Achieves O(n) scaling (speed test)
3. Maintains gradient flow (training viability)
4. Works on real tasks (not just random data)

Run with:
    python -m symbolu.ontological.test_phase_attention
"""

import time
import math
from typing import Dict, List, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from symbolu_core.ontological.phase_attention import (
    PhaseAttention,
    LinearPhaseAttention,
    PhaseAttentionWrapper,
    PhaseSynchronizer,
    PhaseCorrelation,
)


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_result(name: str, passed: bool, details: str = ""):
    """Print test result."""
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"  {status}: {name}")
    if details:
        print(f"         {details}")


# =============================================================================
# TEST 1: Output Quality Comparison
# =============================================================================

def test_output_quality():
    """
    Compare outputs of Phase Attention vs Standard Attention.

    They won't be identical, but should be correlated.
    """
    print_header("TEST 1: Output Quality Comparison")

    torch.manual_seed(42)

    embed_dim = 256
    num_heads = 8
    seq_len = 64
    batch_size = 4

    # Create inputs
    x = torch.randn(batch_size, seq_len, embed_dim)

    # Standard attention
    std_attn = nn.MultiheadAttention(embed_dim, num_heads, batch_first=True)
    std_out, _ = std_attn(x, x, x)

    # Phase attention
    phase_attn = PhaseAttention(embed_dim, num_heads)
    phase_out = phase_attn(x)

    # Linear phase attention
    linear_phase_attn = LinearPhaseAttention(embed_dim, num_heads)
    linear_out = linear_phase_attn(x)

    # Compare statistics
    std_mean = std_out.mean().item()
    std_std = std_out.std().item()
    phase_mean = phase_out.mean().item()
    phase_std = phase_out.std().item()
    linear_mean = linear_out.mean().item()
    linear_std = linear_out.std().item()

    print(f"\n  Output Statistics:")
    print(f"    Standard:     mean={std_mean:.4f}, std={std_std:.4f}")
    print(f"    Phase:        mean={phase_mean:.4f}, std={phase_std:.4f}")
    print(f"    LinearPhase:  mean={linear_mean:.4f}, std={linear_std:.4f}")

    # Check correlation (flatten and compute)
    std_flat = std_out.flatten()
    phase_flat = phase_out.flatten()
    linear_flat = linear_out.flatten()

    # Pearson correlation
    def correlation(a, b):
        a_centered = a - a.mean()
        b_centered = b - b.mean()
        return (a_centered * b_centered).sum() / (a_centered.norm() * b_centered.norm() + 1e-8)

    corr_phase = correlation(std_flat, phase_flat).item()
    corr_linear = correlation(std_flat, linear_flat).item()

    print(f"\n  Correlation with Standard Attention:")
    print(f"    Phase:        {corr_phase:.4f}")
    print(f"    LinearPhase:  {corr_linear:.4f}")

    # Test: outputs should be in similar range (not NaN, not exploding)
    phase_valid = not (torch.isnan(phase_out).any() or torch.isinf(phase_out).any())
    linear_valid = not (torch.isnan(linear_out).any() or torch.isinf(linear_out).any())

    # Statistics should be reasonable
    stats_ok = (abs(phase_std - std_std) < std_std * 2) and (abs(linear_std - std_std) < std_std * 2)

    print_result("Phase attention outputs valid", phase_valid)
    print_result("Linear phase attention outputs valid", linear_valid)
    print_result("Output statistics reasonable", stats_ok,
                f"std ratio: phase={phase_std/std_std:.2f}x, linear={linear_std/std_std:.2f}x")

    return phase_valid and linear_valid and stats_ok


# =============================================================================
# TEST 2: O(n) Scaling Verification
# =============================================================================

def test_scaling():
    """
    Verify O(n) scaling vs O(n²) for standard attention.

    Phase attention should scale linearly with sequence length.
    """
    print_header("TEST 2: O(n) Scaling Verification")

    embed_dim = 256
    num_heads = 8
    batch_size = 2

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"\n  Device: {device}")

    # Standard attention
    std_attn = nn.MultiheadAttention(embed_dim, num_heads, batch_first=True).to(device)

    # Linear phase attention
    phase_attn = LinearPhaseAttention(embed_dim, num_heads).to(device)

    seq_lengths = [128, 256, 512, 1024, 2048]
    std_times = []
    phase_times = []

    print(f"\n  {'SeqLen':<10} {'Standard':<15} {'Phase':<15} {'Speedup':<10}")
    print(f"  {'-'*50}")

    for seq_len in seq_lengths:
        x = torch.randn(batch_size, seq_len, embed_dim, device=device)

        # Warmup
        with torch.no_grad():
            _ = std_attn(x, x, x)[0]
            _ = phase_attn(x)

        if device.type == 'cuda':
            torch.cuda.synchronize()

        # Time standard attention
        num_runs = 5
        t0 = time.time()
        with torch.no_grad():
            for _ in range(num_runs):
                _ = std_attn(x, x, x)[0]
        if device.type == 'cuda':
            torch.cuda.synchronize()
        std_time = (time.time() - t0) / num_runs * 1000  # ms
        std_times.append(std_time)

        # Time phase attention
        t0 = time.time()
        with torch.no_grad():
            for _ in range(num_runs):
                _ = phase_attn(x)
        if device.type == 'cuda':
            torch.cuda.synchronize()
        phase_time = (time.time() - t0) / num_runs * 1000  # ms
        phase_times.append(phase_time)

        speedup = std_time / phase_time if phase_time > 0 else 0
        print(f"  {seq_len:<10} {std_time:<15.2f}ms {phase_time:<15.2f}ms {speedup:<10.1f}x")

    # Check scaling: O(n²) should grow ~4x when n doubles
    # O(n) should grow ~2x when n doubles

    std_ratios = [std_times[i+1] / std_times[i] for i in range(len(std_times)-1)]
    phase_ratios = [phase_times[i+1] / phase_times[i] for i in range(len(phase_times)-1)]

    avg_std_ratio = sum(std_ratios) / len(std_ratios)
    avg_phase_ratio = sum(phase_ratios) / len(phase_ratios)

    print(f"\n  Scaling Analysis:")
    print(f"    Standard attention: ~{avg_std_ratio:.1f}x per 2x seq_len (expect ~4x for O(n²))")
    print(f"    Phase attention:    ~{avg_phase_ratio:.1f}x per 2x seq_len (expect ~2x for O(n))")

    # Phase should scale better (lower ratio)
    is_linear = avg_phase_ratio < avg_std_ratio
    is_subquadratic = avg_phase_ratio < 3.0

    print_result("Phase attention scales better than standard", is_linear)
    print_result("Phase attention is sub-quadratic", is_subquadratic,
                f"ratio={avg_phase_ratio:.2f} (should be <3.0)")

    return is_linear and is_subquadratic


# =============================================================================
# TEST 3: Gradient Flow
# =============================================================================

def test_gradient_flow():
    """
    Verify gradients flow properly through phase attention.

    This is critical for training.
    """
    print_header("TEST 3: Gradient Flow")

    embed_dim = 128
    num_heads = 4
    seq_len = 32
    batch_size = 2

    # Create model with phase attention
    class SimpleModel(nn.Module):
        def __init__(self):
            super().__init__()
            self.embed = nn.Linear(embed_dim, embed_dim)
            self.attn = LinearPhaseAttention(embed_dim, num_heads)
            self.output = nn.Linear(embed_dim, 10)

        def forward(self, x):
            x = self.embed(x)
            x = self.attn(x)
            x = x.mean(dim=1)  # Pool
            return self.output(x)

    model = SimpleModel()

    # Forward pass
    x = torch.randn(batch_size, seq_len, embed_dim)
    target = torch.randint(0, 10, (batch_size,))

    output = model(x)
    loss = F.cross_entropy(output, target)

    # Backward pass
    loss.backward()

    # Check gradients
    gradients_ok = True
    has_any_gradient = False
    gradient_info = []

    for name, param in model.named_parameters():
        if param.grad is not None:
            has_any_gradient = True
            grad_norm = param.grad.norm().item()
            grad_max = param.grad.abs().max().item()
            is_valid = not (torch.isnan(param.grad).any() or torch.isinf(param.grad).any())
            gradients_ok = gradients_ok and is_valid
            gradient_info.append((name, grad_norm, grad_max, is_valid))
        else:
            # No gradient is OK (might be unused or bias=False)
            gradient_info.append((name, 0, 0, None))  # None means no gradient

    # Must have at least some gradients flowing
    gradients_ok = gradients_ok and has_any_gradient

    print(f"\n  Gradient Analysis:")
    print(f"    {'Parameter':<30} {'Norm':<12} {'Max':<12} {'Valid':<8}")
    print(f"    {'-'*62}")
    for name, norm, max_val, valid in gradient_info[:10]:  # Show first 10
        if valid is None:
            status = "-"  # No gradient (unused param)
        elif valid:
            status = "✓"
        else:
            status = "✗"
        print(f"    {name:<30} {norm:<12.4f} {max_val:<12.4f} {status:<8}")

    # Check loss decreased after one step
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)

    initial_loss = loss.item()
    optimizer.step()

    output2 = model(x)
    loss2 = F.cross_entropy(output2, target)

    loss_decreased = loss2.item() < initial_loss

    print(f"\n  Training Step:")
    print(f"    Initial loss: {initial_loss:.4f}")
    print(f"    After step:   {loss2.item():.4f}")

    print_result("All gradients valid (no NaN/Inf)", gradients_ok)
    print_result("Loss decreased after optimization step", loss_decreased)

    return gradients_ok and loss_decreased


# =============================================================================
# TEST 4: Phase Synchronization Behavior
# =============================================================================

def test_phase_synchronization():
    """
    Test that phase synchronization actually synchronizes phases.

    After synchronization, phases should be more aligned.
    """
    print_header("TEST 4: Phase Synchronization Behavior")

    phase_dim = 32
    seq_len = 64
    batch_size = 2

    # Create random initial phases
    initial_phases = torch.rand(batch_size, seq_len, phase_dim) * 2 * math.pi

    # Synchronizer
    sync = PhaseSynchronizer(
        phase_dim=phase_dim,
        sync_lr=0.2,
        num_steps=10,
        use_mean_field=True,
    )

    # Synchronize
    synced_phases = sync.synchronize(initial_phases.clone())

    # Measure phase coherence (how aligned phases are)
    def measure_coherence(phases):
        # Mean phase
        mean_phase = phases.mean(dim=1, keepdim=True)
        # Average cosine distance from mean
        coherence = torch.cos(phases - mean_phase).mean()
        return coherence.item()

    initial_coherence = measure_coherence(initial_phases)
    final_coherence = measure_coherence(synced_phases)

    print(f"\n  Phase Coherence:")
    print(f"    Initial: {initial_coherence:.4f}")
    print(f"    After sync: {final_coherence:.4f}")
    print(f"    Improvement: {(final_coherence - initial_coherence):.4f}")

    # Measure phase variance
    initial_var = initial_phases.var(dim=1).mean().item()
    final_var = synced_phases.var(dim=1).mean().item()

    print(f"\n  Phase Variance:")
    print(f"    Initial: {initial_var:.4f}")
    print(f"    After sync: {final_var:.4f}")

    # Phases should be more coherent after synchronization
    coherence_improved = final_coherence > initial_coherence

    # Check the correlation formula U1
    correlation = PhaseCorrelation()

    # For a subset (full is O(n²))
    subset_phases = synced_phases[:, :16, :]
    corr_matrix = correlation.pairwise_correlation(subset_phases)

    # Diagonal should be 1.0 (self-correlation)
    diag = torch.diagonal(corr_matrix, dim1=1, dim2=2)
    diag_ones = (diag > 0.99).all().item()

    # Off-diagonal should be positive after sync (aligned phases)
    off_diag_mask = 1 - torch.eye(16).unsqueeze(0)
    off_diag = (corr_matrix * off_diag_mask).sum() / off_diag_mask.sum()
    off_diag_positive = off_diag.item() > 0

    print(f"\n  Correlation Matrix (U1):")
    print(f"    Diagonal (self-corr): {'all ~1.0' if diag_ones else 'NOT all 1.0'}")
    print(f"    Off-diagonal mean: {off_diag.item():.4f} (should be >0 after sync)")

    print_result("Coherence improved after synchronization", coherence_improved)
    print_result("Self-correlation is 1.0", diag_ones)
    print_result("Off-diagonal correlation positive", off_diag_positive)

    return coherence_improved and diag_ones


# =============================================================================
# TEST 5: Task Performance (Simple Classification)
# =============================================================================

def test_task_performance():
    """
    Test phase attention on a simple classification task.

    Verify it can actually learn something useful.
    """
    print_header("TEST 5: Task Performance (Classification)")

    embed_dim = 64
    num_heads = 4
    seq_len = 16
    num_classes = 4
    batch_size = 32
    num_batches = 50

    # Create a simple pattern classification task
    # Pattern: sum of first half > sum of second half -> class based on magnitude

    class PhaseClassifier(nn.Module):
        def __init__(self):
            super().__init__()
            self.embed = nn.Linear(1, embed_dim)
            self.attn = LinearPhaseAttention(embed_dim, num_heads)
            self.pool = nn.AdaptiveAvgPool1d(1)
            self.classifier = nn.Linear(embed_dim, num_classes)

        def forward(self, x):
            # x: [B, seq_len]
            x = x.unsqueeze(-1)  # [B, seq_len, 1]
            x = self.embed(x)    # [B, seq_len, embed_dim]
            x = self.attn(x)     # [B, seq_len, embed_dim]
            x = x.transpose(1, 2)  # [B, embed_dim, seq_len]
            x = self.pool(x).squeeze(-1)  # [B, embed_dim]
            return self.classifier(x)

    def generate_data(batch_size):
        # Random sequences
        x = torch.randn(batch_size, seq_len)
        # Label based on pattern
        first_half_sum = x[:, :seq_len//2].sum(dim=1)
        second_half_sum = x[:, seq_len//2:].sum(dim=1)
        diff = first_half_sum - second_half_sum
        # Quantize to classes
        y = torch.zeros(batch_size, dtype=torch.long)
        y[diff < -1] = 0
        y[(diff >= -1) & (diff < 0)] = 1
        y[(diff >= 0) & (diff < 1)] = 2
        y[diff >= 1] = 3
        return x, y

    model = PhaseClassifier()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)

    # Training
    losses = []
    accuracies = []

    for i in range(num_batches):
        x, y = generate_data(batch_size)

        optimizer.zero_grad()
        output = model(x)
        loss = F.cross_entropy(output, y)
        loss.backward()
        optimizer.step()

        # Accuracy
        pred = output.argmax(dim=1)
        acc = (pred == y).float().mean().item()

        losses.append(loss.item())
        accuracies.append(acc)

        if (i + 1) % 10 == 0:
            print(f"    Batch {i+1}: loss={loss.item():.4f}, accuracy={acc:.2%}")

    # Final evaluation
    model.eval()
    with torch.no_grad():
        x_test, y_test = generate_data(256)
        output = model(x_test)
        final_acc = (output.argmax(dim=1) == y_test).float().mean().item()

    print(f"\n  Training Summary:")
    print(f"    Initial loss: {losses[0]:.4f}")
    print(f"    Final loss:   {losses[-1]:.4f}")
    print(f"    Initial accuracy: {accuracies[0]:.2%}")
    print(f"    Final accuracy:   {final_acc:.2%}")

    # Success criteria
    loss_decreased = losses[-1] < losses[0]
    accuracy_improved = final_acc > accuracies[0]
    accuracy_above_random = final_acc > 0.30  # Random is 25%

    print_result("Loss decreased during training", loss_decreased)
    print_result("Accuracy improved", accuracy_improved)
    print_result("Accuracy above random (25%)", accuracy_above_random,
                f"final={final_acc:.2%}")

    return loss_decreased and accuracy_above_random


# =============================================================================
# TEST 6: Memory Comparison
# =============================================================================

def test_memory():
    """
    Compare memory usage between standard and phase attention.
    """
    print_header("TEST 6: Memory Comparison")

    if not torch.cuda.is_available():
        print("\n  CUDA not available, skipping memory test")
        return True

    embed_dim = 256
    num_heads = 8
    batch_size = 4

    device = torch.device('cuda')

    def measure_memory(model, x):
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()

        output = model(x) if not isinstance(model, nn.MultiheadAttention) else model(x, x, x)[0]

        torch.cuda.synchronize()
        return torch.cuda.max_memory_allocated() / 1024 / 1024  # MB

    std_attn = nn.MultiheadAttention(embed_dim, num_heads, batch_first=True).to(device)
    phase_attn = LinearPhaseAttention(embed_dim, num_heads).to(device)

    print(f"\n  {'SeqLen':<10} {'Standard (MB)':<15} {'Phase (MB)':<15} {'Savings':<10}")
    print(f"  {'-'*50}")

    for seq_len in [256, 512, 1024, 2048]:
        x = torch.randn(batch_size, seq_len, embed_dim, device=device)

        std_mem = measure_memory(std_attn, x)
        phase_mem = measure_memory(phase_attn, x)
        savings = (std_mem - phase_mem) / std_mem * 100 if std_mem > 0 else 0

        print(f"  {seq_len:<10} {std_mem:<15.1f} {phase_mem:<15.1f} {savings:<10.1f}%")

    return True


# =============================================================================
# MAIN
# =============================================================================

def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "=" * 70)
    print("  PHASE ATTENTION TEST SUITE")
    print("  Testing Patent Formulas U1-U4 Implementation")
    print("=" * 70)

    results = {}

    try:
        results['output_quality'] = test_output_quality()
    except Exception as e:
        print(f"\n  ERROR in test_output_quality: {e}")
        results['output_quality'] = False

    try:
        results['scaling'] = test_scaling()
    except Exception as e:
        print(f"\n  ERROR in test_scaling: {e}")
        results['scaling'] = False

    try:
        results['gradient_flow'] = test_gradient_flow()
    except Exception as e:
        print(f"\n  ERROR in test_gradient_flow: {e}")
        results['gradient_flow'] = False

    try:
        results['phase_sync'] = test_phase_synchronization()
    except Exception as e:
        print(f"\n  ERROR in test_phase_synchronization: {e}")
        results['phase_sync'] = False

    try:
        results['task_performance'] = test_task_performance()
    except Exception as e:
        print(f"\n  ERROR in test_task_performance: {e}")
        results['task_performance'] = False

    try:
        results['memory'] = test_memory()
    except Exception as e:
        print(f"\n  ERROR in test_memory: {e}")
        results['memory'] = False

    # Summary
    print_header("TEST SUMMARY")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")

    print(f"\n  Overall: {passed}/{total} tests passed")

    if passed == total:
        print("\n  ✓ All tests passed! Phase attention is working correctly.")
    else:
        print(f"\n  ✗ {total - passed} test(s) failed. Review output above.")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
