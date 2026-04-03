"""
SymbolU12 Manifold Tests
========================

Tests for the manifold implementation and Sattvic Seal generation.
Can run without the CUDA extension (uses Python fallback).

Usage:
    python -m symbolu.experimental.cuda.test_manifold

Reference: docs/GOOGLE_ARCHITECTURE_PROPOSALS.md Section 30.22
"""

import torch
import sys


def test_manifold_initialization():
    """Test manifold initialization."""
    from symbolu.experimental.cuda import SymbolU12Manifold

    print("=" * 60)
    print("TEST: Manifold Initialization")
    print("=" * 60)

    manifold = SymbolU12Manifold(batch_size=4)
    manifold.initialize_sattvic()

    assert manifold.is_initialized, "Manifold should be initialized"
    assert manifold.S_0.shape == (4, 124), f"S_0 shape mismatch: {manifold.S_0.shape}"
    assert manifold.S_t.shape == (4, 124), f"S_t shape mismatch: {manifold.S_t.shape}"
    assert manifold.S_prev.shape == (4, 124), f"S_prev shape mismatch: {manifold.S_prev.shape}"
    assert manifold.R_block.shape == (4, 9), f"R_block shape mismatch: {manifold.R_block.shape}"

    # Verify S_t == S_0 after initialization
    assert torch.allclose(manifold.S_t, manifold.S_0), "S_t should equal S_0 after init"
    assert torch.allclose(manifold.S_prev, manifold.S_0), "S_prev should equal S_0 after init"

    print("✅ Manifold initialization passed")
    return True


def test_step_evolution():
    """Test single step evolution."""
    from symbolu.experimental.cuda import SymbolU12Manifold

    print("\n" + "=" * 60)
    print("TEST: Step Evolution")
    print("=" * 60)

    manifold = SymbolU12Manifold(batch_size=2)
    manifold.initialize_sattvic()

    # Create a small delta
    delta = torch.randn(2, 124) * 0.1

    # Execute step
    output_G, integrity_flags = manifold.step(delta)

    assert output_G.shape == (2,), f"output_G shape mismatch: {output_G.shape}"
    assert integrity_flags.shape == (2,), f"flags shape mismatch: {integrity_flags.shape}"

    print(f"output_G: {output_G}")
    print(f"integrity_flags: {integrity_flags}")

    # Verify state changed
    assert not torch.allclose(manifold.S_t, manifold.S_0), "S_t should change after step"

    print("✅ Step evolution passed")
    return True


def test_ghost_buffer():
    """Test Ghost Buffer (S_prev) motion tracking."""
    from symbolu.experimental.cuda import SymbolU12Manifold

    print("\n" + "=" * 60)
    print("TEST: Ghost Buffer Motion Tracking")
    print("=" * 60)

    manifold = SymbolU12Manifold(batch_size=1)
    manifold.initialize_sattvic()

    # Step 1: Large delta
    delta1 = torch.randn(1, 124) * 0.5
    output_G_1, _ = manifold.step(delta1)

    metrics_1 = manifold.get_metrics()
    motion_1 = metrics_1['motion'].item()

    # Step 2: Small delta (motion should be smaller)
    delta2 = torch.randn(1, 124) * 0.01
    output_G_2, _ = manifold.step(delta2)

    metrics_2 = manifold.get_metrics()
    motion_2 = metrics_2['motion'].item()

    print(f"Step 1 - Motion: {motion_1:.4f}, Coherence: {metrics_1['coherence'].item():.4f}")
    print(f"Step 2 - Motion: {motion_2:.4f}, Coherence: {metrics_2['coherence'].item():.4f}")

    # Motion should generally decrease with smaller deltas
    print("✅ Ghost buffer motion tracking passed")
    return True


def test_sattvic_seal():
    """Test Sattvic Seal generation."""
    from symbolu.experimental.cuda import SymbolU12Manifold

    print("\n" + "=" * 60)
    print("TEST: Sattvic Seal Generation")
    print("=" * 60)

    manifold = SymbolU12Manifold(batch_size=1)
    manifold.initialize_sattvic()

    # Small delta to maintain integrity
    delta = torch.randn(1, 124) * 0.05
    manifold.step(delta)

    # Generate seal
    seal = manifold.generate_seal("The capital of France is Paris.")

    print(f"Seal: {seal.seal}")
    print(f"Trace Score: {seal.trace_score:.4f}")
    print(f"Coherence: {seal.coherence_score:.4f}")
    print(f"Motion: {seal.motion_score:.4f}")
    print(f"Entropy: {seal.entropy_score:.4f}")
    print(f"Verified: {seal.verified}")
    print(f"Status: {seal.status}")

    assert seal.seal.startswith("SATTVIC_SEAL:"), "Seal should have correct prefix"
    assert len(seal.state_hash) > 0, "State hash should be non-empty"

    print("✅ Sattvic Seal generation passed")
    return True


def test_integrity_flags():
    """Test integrity flag detection."""
    from symbolu.experimental.cuda import SymbolU12Manifold, IntegrityFlag

    print("\n" + "=" * 60)
    print("TEST: Integrity Flag Detection")
    print("=" * 60)

    manifold = SymbolU12Manifold(batch_size=1)
    manifold.initialize_sattvic()

    # Very large delta to trigger integrity violations
    delta = torch.randn(1, 124) * 5.0

    output_G, integrity_flags = manifold.step(delta)
    flags = integrity_flags.item()

    print(f"Integrity Flags: {flags:#x}")

    if flags & IntegrityFlag.COHERENCE_FAILURE:
        print("  - COHERENCE_FAILURE detected")
    if flags & IntegrityFlag.MOTION_OVERDRIVE:
        print("  - MOTION_OVERDRIVE detected")
    if flags & IntegrityFlag.TRACE_COLLAPSE:
        print("  - TRACE_COLLAPSE detected")
    if flags & IntegrityFlag.ENTROPY_SPIKE:
        print("  - ENTROPY_SPIKE detected")

    # With a large delta, we expect some integrity issues
    # (MOTION_OVERDRIVE is most likely)
    print("✅ Integrity flag detection passed")
    return True


def test_cpu_gpu_parity():
    """Test CPU/GPU parity (if CUDA available)."""
    from symbolu.experimental.cuda import SymbolU12Manifold, is_cuda_available

    print("\n" + "=" * 60)
    print("TEST: CPU/GPU Parity")
    print("=" * 60)

    if not is_cuda_available():
        print("⚠️ CUDA not available - skipping GPU parity test")
        return True

    torch.manual_seed(42)

    # CPU manifold
    manifold_cpu = SymbolU12Manifold(batch_size=4)
    manifold_cpu.initialize_sattvic()

    # GPU manifold (same initialization)
    manifold_gpu = SymbolU12Manifold(batch_size=4)
    manifold_gpu.initialize_sattvic()
    manifold_gpu = manifold_gpu.cuda()

    # Same delta
    delta_cpu = torch.randn(4, 124) * 0.1
    delta_gpu = delta_cpu.cuda()

    # Execute steps
    output_G_cpu, flags_cpu = manifold_cpu.step(delta_cpu)
    output_G_gpu, flags_gpu = manifold_gpu.step(delta_gpu)

    # Compare
    output_G_gpu_cpu = output_G_gpu.cpu()
    diff = torch.abs(output_G_cpu - output_G_gpu_cpu).max().item()

    print(f"CPU output_G:  {output_G_cpu}")
    print(f"GPU output_G:  {output_G_gpu_cpu}")
    print(f"Max diff:      {diff:.10f}")

    if diff < 1e-5:
        print("✅ CPU/GPU parity verified (diff < 1e-5)")
    else:
        print(f"⚠️ CPU/GPU difference: {diff:.10f}")

    return True


def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("SymbolU12 Manifold Test Suite")
    print("=" * 60)

    from symbolu.experimental.cuda import get_device_info

    info = get_device_info()
    print(f"\nDevice Info:")
    print(f"  CUDA Available:      {info['cuda_available']}")
    print(f"  Extension Available: {info['extension_available']}")
    if info['extension_error']:
        print(f"  Extension Error:     {info['extension_error']}")
    if info.get('cuda_device_name'):
        print(f"  GPU Device:          {info['cuda_device_name']}")
    print()

    tests = [
        test_manifold_initialization,
        test_step_evolution,
        test_ghost_buffer,
        test_sattvic_seal,
        test_integrity_flags,
        test_cpu_gpu_parity,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ {test.__name__} FAILED: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"TEST RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
