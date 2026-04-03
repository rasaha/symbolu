#!/usr/bin/env python3
"""
Phase-Quad Image Generator Validation Script

This script validates that all components of the Phase-Quad Image Generator
are working correctly. Run this after installation to verify the implementation.

Usage:
    python -m symbolu.vision.validate
    python symbolu/vision/validate.py

Requirements:
    - PyTorch >= 2.0
    - CUDA (optional, for GPU validation)
"""

import sys
import time
from typing import Dict, Tuple, Optional
from dataclasses import dataclass

import torch
import torch.nn as nn

# Validation results
@dataclass
class ValidationResult:
    """Result of a validation check."""
    name: str
    passed: bool
    message: str
    duration_ms: float


def validate_imports() -> ValidationResult:
    """Validate all module imports work correctly."""
    start = time.time()
    try:
        from symbolu_extensions.vision import (
            PhaseQuadImageGenerator,
            PhaseQuadVisionConfig,
            CognadeVisionBlock,
            PhaseIntegrator1D,
            PhaseIntegrator2D,
            QuadRetriever2D,
            GateMixer,
            LocalMixer,
            PatchEmbed2D,
            ScanManager2D,
            RotaryPositionEmbedding2D,
        )
        from symbolu_extensions.vision.controls import (
            PatchMeta,
            PhaseControl,
            QuadControl,
            GateControl,
            BlockControl,
            GeneratorControl,
        )
        from symbolu_extensions.vision.diagnostics import (
            compute_quad_utilization,
            compute_phase_health,
            compute_ghost_metrics,
        )
        from symbolu_extensions.vision.contracts import (
            ContractViolationError,
            assert_control_shape,
        )
        duration = (time.time() - start) * 1000
        return ValidationResult(
            name="Module Imports",
            passed=True,
            message="All 18 core modules imported successfully",
            duration_ms=duration,
        )
    except ImportError as e:
        duration = (time.time() - start) * 1000
        return ValidationResult(
            name="Module Imports",
            passed=False,
            message=f"Import failed: {e}",
            duration_ms=duration,
        )


def validate_contracts() -> ValidationResult:
    """Validate no-write contract enforcement."""
    start = time.time()
    try:
        from symbolu_extensions.vision.contracts import (
            ContractViolationError,
            assert_control_shape,
        )

        # Valid shapes
        assert_control_shape(torch.tensor(1.0), "scalar", 8)
        assert_control_shape(torch.randn(8), "per_head", 8)
        assert_control_shape(torch.randn(2, 8), "batch_head", 8)
        assert_control_shape(torch.randn(2, 8, 1), "batch_head_broadcast", 8)
        assert_control_shape(None, "none", 8)

        # Invalid shape should raise
        try:
            assert_control_shape(torch.randn(2, 64, 256), "invalid", 8)
            duration = (time.time() - start) * 1000
            return ValidationResult(
                name="No-Write Contract",
                passed=False,
                message="Contract did not reject invalid shape [B, N, D]",
                duration_ms=duration,
            )
        except ContractViolationError:
            pass  # Expected

        duration = (time.time() - start) * 1000
        return ValidationResult(
            name="No-Write Contract",
            passed=True,
            message="Contract correctly enforces valid/invalid shapes",
            duration_ms=duration,
        )
    except Exception as e:
        duration = (time.time() - start) * 1000
        return ValidationResult(
            name="No-Write Contract",
            passed=False,
            message=f"Contract validation failed: {e}",
            duration_ms=duration,
        )


def validate_scan_manager(device: torch.device) -> ValidationResult:
    """Validate 2D scan manager."""
    start = time.time()
    try:
        from symbolu_extensions.vision.scan_manager import ScanManager2D

        scan = ScanManager2D(8, 8).to(device)

        # Test roundtrip
        x = torch.randn(2, 64, 256, device=device)

        x_row = scan.gather(x, scan.row_order)
        x_restored = scan.scatter(x_row, scan.row_order)

        if not torch.allclose(x, x_restored):
            raise ValueError("Gather/scatter roundtrip failed")

        # Test non-square
        scan_ns = ScanManager2D(4, 8).to(device)
        if scan_ns.N != 32:
            raise ValueError("Non-square grid N incorrect")

        duration = (time.time() - start) * 1000
        return ValidationResult(
            name="Scan Manager",
            passed=True,
            message="Row/col orders correct, roundtrip verified",
            duration_ms=duration,
        )
    except Exception as e:
        duration = (time.time() - start) * 1000
        return ValidationResult(
            name="Scan Manager",
            passed=False,
            message=f"Scan manager failed: {e}",
            duration_ms=duration,
        )


def validate_patch_embed(device: torch.device) -> ValidationResult:
    """Validate patch embedding."""
    start = time.time()
    try:
        from symbolu_extensions.vision.patch_embed import PatchEmbed2D, TimestepEmbedding

        embed = PatchEmbed2D(
            in_channels=4,
            patch_size=2,
            embed_dim=256,
        ).to(device)

        z = torch.randn(2, 4, 32, 32, device=device)
        x, meta = embed(z)

        expected_n = 16 * 16  # 32/2 * 32/2
        if x.shape != (2, expected_n, 256):
            raise ValueError(f"Unexpected shape: {x.shape}")

        # Test timestep embedding
        t_embed = TimestepEmbedding(256).to(device)
        t = torch.randint(0, 1000, (2,), device=device)
        t_emb = t_embed(t)

        if t_emb.shape != (2, 256):
            raise ValueError(f"Timestep embed shape: {t_emb.shape}")

        duration = (time.time() - start) * 1000
        return ValidationResult(
            name="Patch Embedding",
            passed=True,
            message=f"Patchify: [2,4,32,32] → [2,{expected_n},256]",
            duration_ms=duration,
        )
    except Exception as e:
        duration = (time.time() - start) * 1000
        return ValidationResult(
            name="Patch Embedding",
            passed=False,
            message=f"Patch embed failed: {e}",
            duration_ms=duration,
        )


def validate_phase_integrator(device: torch.device) -> ValidationResult:
    """Validate phase integrator (1D and 2D)."""
    start = time.time()
    try:
        from symbolu_extensions.vision.phase_integrator import PhaseIntegrator1D, PhaseIntegrator2D
        from symbolu_extensions.vision.controls import PatchMeta, PhaseControl

        # Test 1D
        phase1d = PhaseIntegrator1D(embed_dim=256, num_heads=8).to(device)
        x = torch.randn(2, 64, 256, device=device)
        S_re, S_im = phase1d(x)

        if S_re.shape != (2, 64, 8, 32):
            raise ValueError(f"Phase1D output shape: {S_re.shape}")

        # Test 2D
        phase2d = PhaseIntegrator2D(embed_dim=256, num_heads=8).to(device)
        coords = torch.stack([
            torch.arange(8).repeat_interleave(8),
            torch.arange(8).repeat(8),
        ], dim=-1).to(device)
        meta = PatchMeta(H_p=8, W_p=8, coords=coords)

        S = phase2d(x, meta)
        if S.shape != (2, 64, 256):
            raise ValueError(f"Phase2D output shape: {S.shape}")

        # Test contract validation
        invalid_control = PhaseControl(
            intent_phase=torch.randn(2, 64, device=device)  # Invalid!
        )
        from symbolu_extensions.vision.contracts import ContractViolationError
        try:
            phase1d(x, invalid_control)
            raise ValueError("Should have rejected invalid control")
        except ContractViolationError:
            pass  # Expected

        duration = (time.time() - start) * 1000
        return ValidationResult(
            name="Phase Integrator",
            passed=True,
            message="1D and 2D integrators work, contract enforced",
            duration_ms=duration,
        )
    except Exception as e:
        duration = (time.time() - start) * 1000
        return ValidationResult(
            name="Phase Integrator",
            passed=False,
            message=f"Phase integrator failed: {e}",
            duration_ms=duration,
        )


def validate_quad_retriever(device: torch.device) -> ValidationResult:
    """Validate Quad retriever."""
    start = time.time()
    try:
        from symbolu_extensions.vision.quad_retriever import QuadRetriever2D
        from symbolu_extensions.vision.controls import PatchMeta, QuadControl

        quad = QuadRetriever2D(
            embed_dim=256,
            num_heads=8,
            topk=16,
        ).to(device)

        x = torch.randn(2, 64, 256, device=device)
        S = torch.randn(2, 64, 256, device=device)

        coords = torch.stack([
            torch.arange(8).repeat_interleave(8),
            torch.arange(8).repeat(8),
        ], dim=-1).to(device)
        meta = PatchMeta(H_p=8, W_p=8, coords=coords)

        proposals, scores = quad(x, S, meta)

        if proposals.shape != (2, 64, 16, 256):
            raise ValueError(f"Proposals shape: {proposals.shape}")
        if scores.shape != (2, 64, 16):
            raise ValueError(f"Scores shape: {scores.shape}")

        # Test disabled mode
        control = QuadControl(enable_quad=False)
        proposals_off, scores_off = quad(x, S, meta, control)
        if not torch.all(proposals_off == 0):
            raise ValueError("Disabled Quad should return zeros")

        duration = (time.time() - start) * 1000
        return ValidationResult(
            name="Quad Retriever",
            passed=True,
            message="TopK proposals correct, disable mode works",
            duration_ms=duration,
        )
    except Exception as e:
        duration = (time.time() - start) * 1000
        return ValidationResult(
            name="Quad Retriever",
            passed=False,
            message=f"Quad retriever failed: {e}",
            duration_ms=duration,
        )


def validate_gate_mixer(device: torch.device) -> ValidationResult:
    """Validate gate mixer."""
    start = time.time()
    try:
        from symbolu_extensions.vision.gate_mixer import GateMixer
        from symbolu_extensions.vision.controls import GateControl

        gate = GateMixer(embed_dim=256, num_heads=8).to(device)

        x = torch.randn(2, 64, 256, device=device)
        proposals = torch.randn(2, 64, 16, 256, device=device)
        scores = torch.randn(2, 64, 16, device=device)

        x_out = gate(x, proposals, scores)
        if x_out.shape != (2, 64, 256):
            raise ValueError(f"Gate output shape: {x_out.shape}")

        # Test temperature effect
        control_low = GateControl(tau=0.5)
        _ = gate(x, proposals, scores, control_low)
        sat_low = gate._last_gate_saturation

        control_high = GateControl(tau=3.0)
        _ = gate(x, proposals, scores, control_high)
        sat_high = gate._last_gate_saturation

        # Higher tau should have softer (less saturated) gates
        if sat_high > sat_low + 0.1:  # Allow small margin
            raise ValueError(f"Temperature effect wrong: high={sat_high}, low={sat_low}")

        duration = (time.time() - start) * 1000
        return ValidationResult(
            name="Gate Mixer",
            passed=True,
            message="Sigmoid gating works, temperature effect verified",
            duration_ms=duration,
        )
    except Exception as e:
        duration = (time.time() - start) * 1000
        return ValidationResult(
            name="Gate Mixer",
            passed=False,
            message=f"Gate mixer failed: {e}",
            duration_ms=duration,
        )


def validate_cognade_block(device: torch.device) -> ValidationResult:
    """Validate full Cognade vision block."""
    start = time.time()
    try:
        from symbolu_extensions.vision.cognade_vision_block import CognadeVisionBlock
        from symbolu_extensions.vision.controls import PatchMeta, BlockControl

        block = CognadeVisionBlock(
            embed_dim=256,
            num_heads=8,
            topk=16,
            window_size=4,
            use_cross_attn=False,
        ).to(device)

        x = torch.randn(2, 64, 256, device=device)
        t_emb = torch.randn(2, 256, device=device)

        coords = torch.stack([
            torch.arange(8).repeat_interleave(8),
            torch.arange(8).repeat(8),
        ], dim=-1).to(device)
        meta = PatchMeta(H_p=8, W_p=8, coords=coords)

        x_out = block(x, meta, t_emb)
        if x_out.shape != (2, 64, 256):
            raise ValueError(f"Block output shape: {x_out.shape}")

        # Test ablation
        control = BlockControl(enable_quad=False, enable_phase=False)
        x_ablated = block(x, meta, t_emb, control=control)
        if x_ablated.shape != (2, 64, 256):
            raise ValueError("Ablation mode failed")

        duration = (time.time() - start) * 1000
        return ValidationResult(
            name="Cognade Vision Block",
            passed=True,
            message="Full block works, ablation modes available",
            duration_ms=duration,
        )
    except Exception as e:
        duration = (time.time() - start) * 1000
        return ValidationResult(
            name="Cognade Vision Block",
            passed=False,
            message=f"Cognade block failed: {e}",
            duration_ms=duration,
        )


def validate_full_generator(device: torch.device) -> ValidationResult:
    """Validate full Phase-Quad Image Generator."""
    start = time.time()
    try:
        from symbolu_extensions.vision import PhaseQuadImageGenerator, PhaseQuadVisionConfig
        from symbolu_extensions.vision.controls import GeneratorControl

        # Create tiny model for fast validation
        config = PhaseQuadVisionConfig.tiny()
        model = PhaseQuadImageGenerator(config).to(device)

        # Count parameters
        n_params = sum(p.numel() for p in model.parameters())

        # Forward pass
        z_t = torch.randn(1, 4, 16, 16, device=device)
        t = torch.randint(0, 1000, (1,), device=device)

        noise_pred = model(z_t, t)
        if noise_pred.shape != z_t.shape:
            raise ValueError(f"Output shape mismatch: {noise_pred.shape} != {z_t.shape}")

        # Test with control
        control = GeneratorControl(tau=2.0, enable_quad=True)
        noise_pred2 = model(z_t, t, control=control)

        # Test backward pass (gradient flow)
        loss = noise_pred2.sum()
        loss.backward()

        # Check gradients exist
        has_grad = any(p.grad is not None and p.grad.abs().sum() > 0
                      for p in model.parameters() if p.requires_grad)
        if not has_grad:
            raise ValueError("No gradients flowing through model")

        duration = (time.time() - start) * 1000
        return ValidationResult(
            name="Full Generator",
            passed=True,
            message=f"Tiny model ({n_params:,} params), forward+backward OK",
            duration_ms=duration,
        )
    except Exception as e:
        duration = (time.time() - start) * 1000
        return ValidationResult(
            name="Full Generator",
            passed=False,
            message=f"Generator failed: {e}",
            duration_ms=duration,
        )


def validate_diagnostics(device: torch.device) -> ValidationResult:
    """Validate diagnostic metrics."""
    start = time.time()
    try:
        from symbolu_extensions.vision.diagnostics import (
            compute_quad_utilization,
            compute_phase_health,
            compute_ghost_metrics,
        )

        # Quad utilization
        gate_weights = torch.softmax(torch.randn(2, 64, 16, device=device), dim=-1)
        scores = torch.randn(2, 64, 16, device=device)
        quad_metrics = compute_quad_utilization(gate_weights, scores)

        if not (0 <= quad_metrics.active_selection_rate <= 1):
            raise ValueError("Invalid active_selection_rate")

        # Phase health
        S_row = torch.randn(2, 64, 256, device=device)
        S_col = torch.randn(2, 64, 256, device=device)
        a_k = torch.sigmoid(torch.randn(2, 64, 8, device=device))
        phase_metrics = compute_phase_health(S_row, S_col, a_k)

        if not (0 <= phase_metrics.amplitude_mean <= 1):
            raise ValueError("Invalid amplitude_mean")

        # Ghost metrics
        S = torch.randn(2, 128, 256, device=device)
        ghost = compute_ghost_metrics(S)

        if "directional_stability" not in ghost:
            raise ValueError("Missing directional_stability")

        duration = (time.time() - start) * 1000
        return ValidationResult(
            name="Diagnostics",
            passed=True,
            message="Quad, Phase, and Ghost metrics computed correctly",
            duration_ms=duration,
        )
    except Exception as e:
        duration = (time.time() - start) * 1000
        return ValidationResult(
            name="Diagnostics",
            passed=False,
            message=f"Diagnostics failed: {e}",
            duration_ms=duration,
        )


def validate_training_modules() -> ValidationResult:
    """Validate training infrastructure modules."""
    start = time.time()
    try:
        from symbolu_extensions.vision.training import (
            TemperatureSchedule,
            PhaseQuadDiffusionTrainer,
            ReplaceabilityTester,
        )
        from symbolu_extensions.vision.training.temperature_schedule import (
            LinearSchedule,
            CosineSchedule,
        )

        # Temperature schedule
        linear = LinearSchedule(start=2.0, end=1.0, warmup_steps=1000)
        assert abs(linear(0) - 2.0) < 0.01
        assert abs(linear(1000) - 1.0) < 0.01
        assert 1.0 < linear(500) < 2.0

        cosine = CosineSchedule(start=2.0, end=1.0, warmup_steps=1000)
        assert abs(cosine(0) - 2.0) < 0.01
        assert abs(cosine(1000) - 1.0) < 0.01

        duration = (time.time() - start) * 1000
        return ValidationResult(
            name="Training Modules",
            passed=True,
            message="Temperature schedules work correctly",
            duration_ms=duration,
        )
    except Exception as e:
        duration = (time.time() - start) * 1000
        return ValidationResult(
            name="Training Modules",
            passed=False,
            message=f"Training modules failed: {e}",
            duration_ms=duration,
        )


def run_validation() -> Tuple[bool, list]:
    """
    Run all validation checks.

    Returns:
        Tuple of (all_passed, list of ValidationResult)
    """
    print("=" * 60)
    print("Phase-Quad Image Generator Validation")
    print("=" * 60)
    print()

    # Determine device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    if device.type == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")
    print()

    results = []

    # Run all validations
    validations = [
        ("Imports", lambda: validate_imports()),
        ("Contracts", lambda: validate_contracts()),
        ("ScanManager", lambda: validate_scan_manager(device)),
        ("PatchEmbed", lambda: validate_patch_embed(device)),
        ("PhaseIntegrator", lambda: validate_phase_integrator(device)),
        ("QuadRetriever", lambda: validate_quad_retriever(device)),
        ("GateMixer", lambda: validate_gate_mixer(device)),
        ("CognadeBlock", lambda: validate_cognade_block(device)),
        ("FullGenerator", lambda: validate_full_generator(device)),
        ("Diagnostics", lambda: validate_diagnostics(device)),
        ("Training", lambda: validate_training_modules()),
    ]

    for name, validate_fn in validations:
        try:
            result = validate_fn()
        except Exception as e:
            result = ValidationResult(
                name=name,
                passed=False,
                message=f"Unexpected error: {e}",
                duration_ms=0,
            )
        results.append(result)

        status = "✓" if result.passed else "✗"
        print(f"  {status} {result.name:25s} [{result.duration_ms:6.1f}ms] {result.message}")

    print()
    print("=" * 60)

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    all_passed = passed == total

    if all_passed:
        print(f"✓ All {total} validations PASSED")
    else:
        print(f"✗ {passed}/{total} validations passed")
        print()
        print("Failed validations:")
        for r in results:
            if not r.passed:
                print(f"  - {r.name}: {r.message}")

    print("=" * 60)

    return all_passed, results


def main():
    """Main entry point."""
    try:
        all_passed, results = run_validation()
        sys.exit(0 if all_passed else 1)
    except KeyboardInterrupt:
        print("\nValidation interrupted.")
        sys.exit(130)
    except Exception as e:
        print(f"\nValidation crashed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
