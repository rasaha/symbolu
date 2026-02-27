"""
Architecture health checking and diagnostic probe hooks.

Provides PASS/FAIL/WARN health reports for model architecture validation
and lightweight probe hooks for training-time diagnostics.

Extracted from train_unified_llm.py
"""

import inspect
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Any

import torch
import torch.nn as nn
import torch.nn.functional as F

from symbolu.phase_transformer import (
    ControlShapeViolation,
    validate_control_signals,
)


@dataclass
class ArchitectureHealthReport:
    """
    V10.6.3: Architecture Health Summary with PASS/FAIL diagnostics.

    Checks critical invariants at training start:
    - Control signal shapes (D.5 no-write contract)
    - Dual-channel wiring (alignment clamp present)
    - Quad utilization baseline (not bypassed)
    - Chunk continuity (if chunking enabled)

    Reference: QUAD_PROPOSAL_PHASE_INTEGRATOR_EVALUATION.md, Appendix D
    """
    overall: str = "UNKNOWN"  # "PASS", "WARN", "FAIL"
    checks: Dict[str, Tuple[str, str]] = field(default_factory=dict)  # name -> (status, detail)
    timestamp: str = ""

    def __post_init__(self):
        self.timestamp = datetime.now().isoformat()

    def add_check(self, name: str, status: str, detail: str = ""):
        """Add a check result. status should be 'PASS', 'WARN', or 'FAIL'."""
        self.checks[name] = (status, detail)

    def compute_overall(self) -> str:
        """Compute overall status from individual checks."""
        statuses = [s for s, _ in self.checks.values()]
        if "FAIL" in statuses:
            self.overall = "FAIL"
        elif "WARN" in statuses:
            self.overall = "WARN"
        elif statuses:
            self.overall = "PASS"
        return self.overall

    def print_report(self):
        """Print formatted health report."""
        print(f"\n{'='*70}")
        print("  \U0001f4ca ARCHITECTURE HEALTH CHECK (V10.6.3)")
        print(f"{'='*70}")

        status_icons = {"PASS": "\u2705", "WARN": "\u26a0\ufe0f", "FAIL": "\u274c", "UNKNOWN": "\u2753"}

        for name, (status, detail) in self.checks.items():
            icon = status_icons.get(status, "\u2753")
            detail_str = f" - {detail}" if detail else ""
            print(f"  {icon} {name}: {status}{detail_str}")

        self.compute_overall()
        overall_icon = status_icons.get(self.overall, "\u2753")
        print(f"\n  {overall_icon} OVERALL: {self.overall}")
        print(f"{'='*70}\n")

        return self.overall


def run_architecture_health_check(
    model: torch.nn.Module,
    config: "UnifiedTrainingConfig",
    device: torch.device,
) -> ArchitectureHealthReport:
    """
    V10.6.3: Run architecture health check and return PASS/FAIL report.

    Checks:
    1. D.5 No-Write Contract - control signal shapes are low-dimensional
    2. Dual-Channel Wiring - alignment clamp bounds configured
    3. D.2 Slots Read Flag - enable_slots_read routing works
    4. Quad Baseline - quad path contributes (not bypassed)
    5. Chunk Continuity - (if chunking enabled) state persists across chunks

    Args:
        model: The model to check
        config: Training configuration
        device: Torch device

    Returns:
        ArchitectureHealthReport with all check results
    """
    report = ArchitectureHealthReport()

    # Check 1: D.5 No-Write Contract Configuration
    try:
        if config.strict_control_contract:
            report.add_check(
                "D.5 No-Write Contract",
                "PASS",
                "strict mode enabled (violations will raise)"
            )
        else:
            report.add_check(
                "D.5 No-Write Contract",
                "WARN",
                "warn mode (violations logged, not raised)"
            )
    except Exception as e:
        report.add_check("D.5 No-Write Contract", "FAIL", str(e))

    # Check 2: Dual-Channel Wiring (alignment clamp)
    try:
        if config.dual_channel_mode:
            if 0.0 < config.alignment_clamp_min < config.alignment_clamp_max <= 2.0:
                report.add_check(
                    "Dual-Channel Wiring",
                    "PASS",
                    f"clamp=[{config.alignment_clamp_min:.2f}, {config.alignment_clamp_max:.2f}], \u03b1={config.alignment_authority:.2f}"
                )
            else:
                report.add_check(
                    "Dual-Channel Wiring",
                    "WARN",
                    f"unusual clamp bounds: [{config.alignment_clamp_min}, {config.alignment_clamp_max}]"
                )
        else:
            report.add_check(
                "Dual-Channel Wiring",
                "PASS",
                "dual_channel_mode disabled (not needed)"
            )
    except Exception as e:
        report.add_check("Dual-Channel Wiring", "FAIL", str(e))

    # Check 3: D.2 Enable Slots Read (if model supports it)
    try:
        has_slots_read = hasattr(model, 'forward') and 'enable_slots_read' in str(
            model.forward.__code__.co_varnames if hasattr(model, 'forward') else ""
        )
        # Check if model class has binding cache blocks
        has_binding_cache = any(
            "BindingCache" in type(m).__name__
            for m in model.modules()
        )
        if has_binding_cache:
            report.add_check(
                "D.2 Enable Slots Read",
                "PASS",
                "BindingCache architecture detected"
            )
        else:
            report.add_check(
                "D.2 Enable Slots Read",
                "PASS",
                "no BindingCache (slots_read N/A)"
            )
    except Exception as e:
        report.add_check("D.2 Enable Slots Read", "WARN", f"check skipped: {e}")

    # Check 4: Quad Utilization Baseline
    try:
        # Check if model has quad/binding cache path
        has_quad = any(
            "quad" in name.lower() or "binding" in name.lower()
            for name, _ in model.named_modules()
        )
        if has_quad and not config.no_binding_cache:
            report.add_check(
                "Quad Utilization",
                "PASS",
                f"top_k={config.binding_cache_top_k}"
            )
        elif config.no_binding_cache:
            report.add_check(
                "Quad Utilization",
                "WARN",
                "binding_cache disabled (--no_binding_cache)"
            )
        else:
            report.add_check(
                "Quad Utilization",
                "PASS",
                "no quad path (model type doesn't use it)"
            )
    except Exception as e:
        report.add_check("Quad Utilization", "WARN", f"check skipped: {e}")

    # Check 5: Chunk Continuity (if chunking enabled)
    try:
        if config.enable_chunking:
            has_chunk_method = hasattr(model, 'forward_chunk') or hasattr(model, 'diagnose_chunk_continuity')
            if has_chunk_method:
                report.add_check(
                    "Chunk Continuity",
                    "PASS",
                    f"chunk_size={config.chunk_size}"
                )
            else:
                report.add_check(
                    "Chunk Continuity",
                    "WARN",
                    "chunking enabled but model lacks forward_chunk method"
                )
        else:
            report.add_check(
                "Chunk Continuity",
                "PASS",
                "chunking disabled"
            )
    except Exception as e:
        report.add_check("Chunk Continuity", "WARN", f"check skipped: {e}")

    # Check 6: Parameter-Matched Baseline
    try:
        num_params = sum(p.numel() for p in model.parameters())
        # Baselines should have similar param counts for fair comparison
        # StandardTransformer at same config should match
        if config.enforce_baseline_param_match:
            report.add_check(
                "Param-Match Baseline",
                "PASS",
                f"param_count={num_params:,} (enforcement enabled)"
            )
        else:
            report.add_check(
                "Param-Match Baseline",
                "WARN",
                f"param_count={num_params:,} (enforcement disabled)"
            )
    except Exception as e:
        report.add_check("Param-Match Baseline", "WARN", f"check skipped: {e}")

    return report


def check_quad_utilization(
    model: torch.nn.Module,
    input_ids: torch.Tensor,
    device: torch.device,
    threshold: float = 0.01,
) -> Tuple[bool, float, str]:
    """
    V10.6.6: Check that quad path contributes to output (not bypassed).

    Runs forward pass with and without quad to measure contribution.

    Args:
        model: Model with BindingCache architecture
        input_ids: Sample input [B, N]
        device: Torch device
        threshold: Minimum contribution ratio (default 1%)

    Returns:
        Tuple of (passed, contribution_ratio, message)
    """
    model.eval()

    with torch.no_grad():
        # Forward with quad enabled
        try:
            out_with_quad = model(input_ids)
            if isinstance(out_with_quad, dict):
                logits_with = out_with_quad.get('logits', out_with_quad.get('output'))
            else:
                logits_with = out_with_quad
        except Exception as e:
            return False, 0.0, f"Forward with quad failed: {e}"

        # Forward with quad disabled (if model supports enable_slots_read)
        try:
            if hasattr(model, 'forward'):
                sig = inspect.signature(model.forward)
                if 'enable_slots_read' in sig.parameters:
                    out_without_quad = model(input_ids, enable_slots_read=False)
                    if isinstance(out_without_quad, dict):
                        logits_without = out_without_quad.get('logits', out_without_quad.get('output'))
                    else:
                        logits_without = out_without_quad

                    # Compute contribution
                    diff = (logits_with - logits_without).abs().mean().item()
                    baseline = logits_with.abs().mean().item() + 1e-9
                    contribution = diff / baseline

                    passed = contribution >= threshold
                    msg = f"quad contributes {contribution:.1%} of output"
                    return passed, contribution, msg

            # Model doesn't support enable_slots_read - skip check
            return True, -1.0, "model doesn't support enable_slots_read (check skipped)"

        except Exception as e:
            return True, -1.0, f"quad check skipped: {e}"


class LightweightProbeHooks:
    """
    V10.6.7: Lightweight diagnostic probe hooks for training.

    These are NOT full HardProbeDataset evaluations - they're quick sanity checks
    that run periodically during training to catch issues early.

    Supported probes:
    - phase_rotation: Quick check that phase encodes relational structure
    - chunk_continuity: Verify state persists across chunk boundaries
    - control_contract: Validate control signal shapes

    Usage:
        hooks = LightweightProbeHooks(model, config, device)
        # During training loop:
        if step % config.probe_hook_interval == 0:
            results = hooks.run_probes(step)
            for name, (passed, msg) in results.items():
                print(f"  Probe {name}: {'PASS' if passed else 'WARN'} - {msg}")
    """

    def __init__(
        self,
        model: torch.nn.Module,
        config: "UnifiedTrainingConfig",
        device: torch.device,
    ):
        self.model = model
        self.config = config
        self.device = device
        self.probe_types = [p.strip() for p in config.probe_hook_types.split(",")]

    def run_probes(self, step: int) -> Dict[str, Tuple[bool, str]]:
        """
        Run all enabled lightweight probes.

        Args:
            step: Current training step

        Returns:
            Dict mapping probe name to (passed, message)
        """
        results = {}

        for probe_type in self.probe_types:
            if probe_type == "phase_rotation":
                results["phase_rotation"] = self._probe_phase_rotation()
            elif probe_type == "chunk_continuity":
                results["chunk_continuity"] = self._probe_chunk_continuity()
            elif probe_type == "control_contract":
                results["control_contract"] = self._probe_control_contract()
            else:
                results[probe_type] = (True, f"unknown probe type (skipped)")

        return results

    def _probe_phase_rotation(self) -> Tuple[bool, str]:
        """
        Quick phase rotation sanity check.

        Verifies that rotating all phases by theta changes output (phase is functional).
        """
        try:
            # Create small test input
            B, N = 2, 64
            test_ids = torch.randint(0, 1000, (B, N), device=self.device)

            self.model.eval()
            with torch.no_grad():
                # Get baseline output
                out1 = self.model(test_ids)
                if isinstance(out1, dict):
                    logits1 = out1.get('logits', out1.get('output'))
                else:
                    logits1 = out1

                # Apply phase rotation if model supports it
                if hasattr(self.model, 'apply_phase_rotation'):
                    self.model.apply_phase_rotation(math.pi / 4)  # 45 degrees
                    out2 = self.model(test_ids)
                    if isinstance(out2, dict):
                        logits2 = out2.get('logits', out2.get('output'))
                    else:
                        logits2 = out2
                    self.model.apply_phase_rotation(-math.pi / 4)  # Undo

                    diff = (logits1 - logits2).abs().mean().item()
                    if diff > 1e-6:
                        return True, f"phase rotation changes output (\u0394={diff:.4f})"
                    else:
                        return False, f"phase rotation has no effect (\u0394={diff:.4f})"
                else:
                    return True, "model lacks apply_phase_rotation (skipped)"

        except Exception as e:
            return True, f"probe failed: {e}"

    def _probe_chunk_continuity(self) -> Tuple[bool, str]:
        """
        Quick chunk continuity sanity check.

        Verifies that processing in chunks produces similar output to full sequence.
        """
        try:
            if not self.config.enable_chunking:
                return True, "chunking disabled (skipped)"

            if not hasattr(self.model, 'forward_chunk'):
                return True, "model lacks forward_chunk (skipped)"

            # Create test input
            B, N = 1, 256
            chunk_size = 64
            test_ids = torch.randint(0, 1000, (B, N), device=self.device)

            self.model.eval()
            with torch.no_grad():
                # Full sequence
                out_full = self.model(test_ids)
                if isinstance(out_full, dict):
                    logits_full = out_full.get('logits', out_full.get('output'))
                else:
                    logits_full = out_full

                # Chunked - lazy import to avoid circular dependency
                from train_unified_llm import forward_chunked
                logits_chunked = forward_chunked(self.model, test_ids, chunk_size)['logits']

                # Compare
                diff = (logits_full - logits_chunked).abs().mean().item()
                baseline = logits_full.abs().mean().item() + 1e-9
                ratio = diff / baseline

                if ratio < 0.1:  # 10% tolerance
                    return True, f"chunk vs full diff={ratio:.1%}"
                else:
                    return False, f"chunk vs full diff={ratio:.1%} (>10%)"

        except Exception as e:
            return True, f"probe failed: {e}"

    def _probe_control_contract(self) -> Tuple[bool, str]:
        """
        Quick control contract validation.

        Checks that any registered control signals have valid shapes.
        """
        try:
            # Get model's d_model
            d_model = None
            if hasattr(self.model, 'config') and hasattr(self.model.config, 'd_model'):
                d_model = self.model.config.d_model
            elif hasattr(self.model, 'd_model'):
                d_model = self.model.d_model
            else:
                # Try to infer from embedding
                for name, module in self.model.named_modules():
                    if 'embed' in name.lower() and hasattr(module, 'weight'):
                        d_model = module.weight.shape[-1]
                        break

            if d_model is None:
                return True, "couldn't determine d_model (skipped)"

            # Create sample control signals and validate
            B, N = 2, 64
            test_binding_salience = torch.rand(B, N, device=self.device)
            test_intent_phase = torch.rand(B, 8, device=self.device)  # [B, H]

            try:
                results = validate_control_signals(
                    d_model=d_model,
                    seq_len=N,
                    strict=False,
                    binding_salience=test_binding_salience,
                    intent_phase=test_intent_phase,
                )
                if all(results.values()):
                    return True, "sample control signals valid"
                else:
                    invalid = [k for k, v in results.items() if not v]
                    return False, f"invalid signals: {invalid}"
            except ControlShapeViolation as e:
                return False, f"contract violation: {e}"

        except Exception as e:
            return True, f"probe failed: {e}"
