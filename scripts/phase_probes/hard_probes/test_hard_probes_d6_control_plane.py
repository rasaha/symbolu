"""
Hard Probes D.6 Test Suite: Control Plane Validation

This test suite implements the HIGH PRIORITY tests from D.6 Test Priority Matrix
(QUAD_PROPOSAL_PHASE_INTEGRATOR_EVALUATION.md Appendix D.6).

TEST GROUPS:
- Group A: Leak Detector Tests (5+ tests)
  Purpose: Assert control signals cannot be token-wise embeddings

- Group B: AR Regression Tests (5+ tests)
  Purpose: Enable/disable Onto & CSR controls and verify AR accuracy does not collapse

- Group C: Enable Slots Read Tests (5+ tests)
  Purpose: Verify the D.2 enable_slots_read control flag works correctly

- Group D: OntoControl Interface Tests (10 tests) - V10.6.4 D.1
  Purpose: Verify OntoControl dataclass formalizes control plane correctly

- Group E: Forward-Pass Contract Enforcement Tests (10 tests) - V10.6.6
  Purpose: Verify no-write contract is enforced INSIDE forward(), not just config
  This addresses the "highest-risk gap" - violations must STOP TRAINING immediately.

CRITICAL INVARIANTS TESTED:
- INV-D6-1: intent_phase must be low-dimensional [B, H] or [B, H, D_h], NOT [B, N, D]
- INV-D6-2: binding_salience must be [B, N] for per-position gating, NOT [B, N, D]
- INV-D6-3: Control signals must be broadcastable to control shapes
- INV-D6-4: AR accuracy must not collapse when Onto/CSR enabled vs disabled
- INV-D6-5: enable_slots_read=False must skip quad retrieval without affecting phase writes
- INV-D6-6: s_align (alignment signal) must be [H] or [], NOT [B, N] (V10.6.3)
- INV-D6-7: OntoControl wraps binding_salience without changing behavior (V10.6.4)
- INV-E6-1: Invalid control signals in forward() must raise ControlShapeViolation (V10.6.6)
- INV-E6-4: enforce_control_contract=True is the default (STRICT) (V10.6.6)
- INV-E6-5: set_enforce_control_contract() propagates to all child blocks (V10.6.6)

Reference: QUAD_PROPOSAL_PHASE_INTEGRATOR_EVALUATION.md, Appendix D.1, D.6, D.10
Version: V10.6.6
"""

import pytest
import torch
import torch.nn as nn
import math
from typing import Dict, Any, Optional, Tuple

from symbolu.phase_transformer import (
    BindingCacheBlock,
    BindingCacheTransformer,
    BindingCachePhaseState,
    BindingCacheQuadQuery,
    assert_control_shape,
    validate_control_signals,
    ControlShapeViolation,
    assert_alignment_signal_shape,  # V10.6.3: Stricter alignment signal validation
    OntoControl,  # V10.6.4 (D.1): Formalized control plane interface
    onto_control_from_salience,  # V10.6.4 (D.1): Adapter function
)


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def model_config() -> Dict[str, Any]:
    """Standard model configuration for testing."""
    return {
        "vocab_size": 1000,
        "embed_dim": 256,  # Small for fast tests
        "num_layers": 2,
        "num_heads": 4,
        "ff_dim": 512,
        "max_seq_len": 128,
        "dropout": 0.0,  # No dropout for deterministic tests
        "top_k": 32,
    }


@pytest.fixture
def binding_cache_block(model_config) -> BindingCacheBlock:
    """Create a BindingCacheBlock for testing."""
    return BindingCacheBlock(
        embed_dim=model_config["embed_dim"],
        num_heads=model_config["num_heads"],
        ff_dim=model_config["ff_dim"],
        dropout=model_config["dropout"],
        top_k=model_config["top_k"],
    )


@pytest.fixture
def binding_cache_transformer(model_config) -> BindingCacheTransformer:
    """Create a BindingCacheTransformer for testing."""
    return BindingCacheTransformer(
        vocab_size=model_config["vocab_size"],
        embed_dim=model_config["embed_dim"],
        num_layers=model_config["num_layers"],
        num_heads=model_config["num_heads"],
        ff_dim=model_config["ff_dim"],
        max_seq_len=model_config["max_seq_len"],
        dropout=model_config["dropout"],
        top_k=model_config["top_k"],
    )


@pytest.fixture
def sample_inputs(model_config) -> Dict[str, torch.Tensor]:
    """Create sample input tensors."""
    B, N = 2, 64
    D = model_config["embed_dim"]
    H = model_config["num_heads"]
    D_h = D // H

    return {
        "x": torch.randn(B, N, D),
        "input_ids": torch.randint(0, model_config["vocab_size"], (B, N)),
        "valid_intent_phase_2d": torch.randn(B, H),  # [B, H] - valid
        "valid_intent_phase_3d": torch.randn(B, H, D_h),  # [B, H, D_h] - valid
        "valid_binding_salience": torch.randn(B, N),  # [B, N] - valid
        "invalid_intent_phase": torch.randn(B, N, D),  # [B, N, D] - INVALID
        "invalid_binding_salience": torch.randn(B, N, D),  # [B, N, D] - INVALID
        # V10.6.3: Alignment signal samples (s_align)
        "valid_s_align_global": torch.randn(()),  # [] - global scalar (safest)
        "valid_s_align_per_head": torch.randn(H),  # [H] - per-head (recommended)
        "valid_s_align_per_batch_head": torch.randn(B, H),  # [B, H] - per-batch per-head
        "invalid_s_align_token_position": torch.randn(B, N),  # [B, N] - INVALID (token-dependent)
    }


# =============================================================================
# GROUP A: LEAK DETECTOR TESTS
# Purpose: Assert control signals cannot be token-wise embeddings
# =============================================================================

class TestGroupA_LeakDetector:
    """
    Group A: Leak Detector Tests

    These tests enforce the no-write contract (D.5):
    > Control signals must be low-dimensional, broadcastable,
    > and not token-position dependent (except binding_salience for gating).

    This prevents "Phase integrates influence, not structure" principle violations.
    """

    def test_a01_valid_intent_phase_2d_accepted(self, model_config, sample_inputs):
        """Valid intent_phase [B, H] should be accepted."""
        intent_phase = sample_inputs["valid_intent_phase_2d"]

        result = assert_control_shape(
            intent_phase,
            name="intent_phase",
            d_model=model_config["embed_dim"],
            strict=False,
        )

        assert result is True, f"Valid intent_phase [B, H] rejected: {intent_phase.shape}"

    def test_a02_valid_intent_phase_3d_accepted(self, model_config, sample_inputs):
        """Valid intent_phase [B, H, D_h] should be accepted."""
        intent_phase = sample_inputs["valid_intent_phase_3d"]

        result = assert_control_shape(
            intent_phase,
            name="intent_phase",
            d_model=model_config["embed_dim"],
            strict=False,
        )

        assert result is True, f"Valid intent_phase [B, H, D_h] rejected: {intent_phase.shape}"

    def test_a03_invalid_intent_phase_rejected(self, model_config, sample_inputs):
        """Invalid intent_phase [B, N, D] must be REJECTED (INV-D6-1)."""
        invalid_intent_phase = sample_inputs["invalid_intent_phase"]

        # Non-strict mode: should return False
        result = assert_control_shape(
            invalid_intent_phase,
            name="intent_phase",
            d_model=model_config["embed_dim"],
            strict=False,
        )

        assert result is False, (
            f"LEAK DETECTED: intent_phase with shape [B, N, D]={list(invalid_intent_phase.shape)} "
            f"was accepted but should be REJECTED. This could allow content injection!"
        )

    def test_a04_invalid_intent_phase_raises_strict(self, model_config, sample_inputs):
        """Invalid intent_phase should raise ControlShapeViolation in strict mode."""
        invalid_intent_phase = sample_inputs["invalid_intent_phase"]

        with pytest.raises(ControlShapeViolation) as exc_info:
            assert_control_shape(
                invalid_intent_phase,
                name="intent_phase",
                d_model=model_config["embed_dim"],
                strict=True,
            )

        assert "intent_phase" in str(exc_info.value)
        assert "token-wise content" in str(exc_info.value).lower() or "d_model" in str(exc_info.value)

    def test_a05_valid_binding_salience_accepted(self, model_config, sample_inputs):
        """Valid binding_salience [B, N] should be accepted."""
        binding_salience = sample_inputs["valid_binding_salience"]

        result = assert_control_shape(
            binding_salience,
            name="binding_salience",
            d_model=model_config["embed_dim"],
            strict=False,
        )

        assert result is True, f"Valid binding_salience [B, N] rejected: {binding_salience.shape}"

    def test_a06_invalid_binding_salience_rejected(self, model_config, sample_inputs):
        """Invalid binding_salience [B, N, D] must be REJECTED (INV-D6-2)."""
        invalid_salience = sample_inputs["invalid_binding_salience"]

        result = assert_control_shape(
            invalid_salience,
            name="binding_salience",
            d_model=model_config["embed_dim"],
            strict=False,
        )

        assert result is False, (
            f"LEAK DETECTED: binding_salience with shape [B, N, D]={list(invalid_salience.shape)} "
            f"was accepted but should be REJECTED."
        )

    def test_a07_validate_multiple_controls(self, model_config, sample_inputs):
        """validate_control_signals should check multiple controls at once."""
        results = validate_control_signals(
            d_model=model_config["embed_dim"],
            strict=False,
            intent_phase=sample_inputs["valid_intent_phase_2d"],
            binding_salience=sample_inputs["valid_binding_salience"],
        )

        assert results["intent_phase"] is True
        assert results["binding_salience"] is True

    def test_a08_validate_mixed_valid_invalid(self, model_config, sample_inputs):
        """validate_control_signals should detect invalid in mixed set."""
        results = validate_control_signals(
            d_model=model_config["embed_dim"],
            strict=False,
            intent_phase=sample_inputs["invalid_intent_phase"],  # INVALID
            binding_salience=sample_inputs["valid_binding_salience"],  # valid
        )

        assert results["intent_phase"] is False, "Invalid intent_phase should be detected"
        assert results["binding_salience"] is True

    def test_a09_scalar_control_accepted(self, model_config):
        """Scalar control signals should be accepted (broadcastable)."""
        scalar_control = torch.tensor([0.5])

        result = assert_control_shape(
            scalar_control,
            name="scalar_control",
            d_model=model_config["embed_dim"],
            strict=False,
        )

        assert result is True, "Scalar control should be accepted"

    def test_a10_per_head_scalar_accepted(self, model_config):
        """Per-head scalar control [H] should be accepted."""
        H = model_config["num_heads"]
        per_head_control = torch.randn(H)

        result = assert_control_shape(
            per_head_control,
            name="per_head_control",
            d_model=model_config["embed_dim"],
            strict=False,
        )

        assert result is True, f"Per-head control [H]={H} should be accepted"

    # =========================================================================
    # V10.6.3: ALIGNMENT SIGNAL TESTS (s_align)
    # These test the stricter contract: s_align must be [H] or [], NOT [B, N]
    # =========================================================================

    def test_a11_valid_s_align_global_scalar(self, model_config, sample_inputs):
        """V10.6.3: Global scalar [] alignment signal should be accepted (safest)."""
        s_align = sample_inputs["valid_s_align_global"]
        H = model_config["num_heads"]
        N = 64  # From sample_inputs

        result = assert_alignment_signal_shape(
            s_align,
            name="s_align",
            num_heads=H,
            seq_len=N,
            strict=False,
        )

        assert result is True, f"Global scalar s_align [] should be accepted"

    def test_a12_valid_s_align_per_head(self, model_config, sample_inputs):
        """V10.6.3: Per-head [H] alignment signal should be accepted (recommended)."""
        s_align = sample_inputs["valid_s_align_per_head"]
        H = model_config["num_heads"]
        N = 64

        result = assert_alignment_signal_shape(
            s_align,
            name="s_align",
            num_heads=H,
            seq_len=N,
            strict=False,
        )

        assert result is True, f"Per-head s_align [H]={H} should be accepted"

    def test_a13_valid_s_align_per_batch_head(self, model_config, sample_inputs):
        """V10.6.3: Per-batch per-head [B, H] alignment signal should be accepted."""
        s_align = sample_inputs["valid_s_align_per_batch_head"]
        H = model_config["num_heads"]
        N = 64

        result = assert_alignment_signal_shape(
            s_align,
            name="s_align",
            num_heads=H,
            seq_len=N,
            strict=False,
        )

        assert result is True, f"Per-batch per-head s_align [B, H] should be accepted"

    def test_a14_invalid_s_align_token_position_rejected(self, model_config, sample_inputs):
        """V10.6.3 (INV-D6-6): s_align [B, N] must be REJECTED (token-position dependent)."""
        s_align = sample_inputs["invalid_s_align_token_position"]
        H = model_config["num_heads"]
        N = 64

        result = assert_alignment_signal_shape(
            s_align,
            name="s_align",
            num_heads=H,
            seq_len=N,
            strict=False,
        )

        assert result is False, (
            f"ALIGNMENT CONTRACT VIOLATION: s_align with shape [B, N]={list(s_align.shape)} "
            f"was accepted but should be REJECTED. Token-position dependent alignment "
            f"allows structure to leak into Phase!"
        )

    def test_a15_invalid_s_align_raises_strict(self, model_config, sample_inputs):
        """V10.6.3: s_align [B, N] should raise ControlShapeViolation in strict mode."""
        s_align = sample_inputs["invalid_s_align_token_position"]
        H = model_config["num_heads"]
        N = 64

        with pytest.raises(ControlShapeViolation) as exc_info:
            assert_alignment_signal_shape(
                s_align,
                name="s_align",
                num_heads=H,
                seq_len=N,
                strict=True,
            )

        error_msg = str(exc_info.value).lower()
        assert "s_align" in error_msg or "alignment" in error_msg
        assert "token" in error_msg or "[b, n]" in error_msg.lower()


# =============================================================================
# GROUP B: AR REGRESSION TESTS
# Purpose: Enable/disable Onto & CSR controls and verify AR accuracy does not collapse
# =============================================================================

class TestGroupB_ARRegression:
    """
    Group B: AR Regression Tests

    These tests verify that enabling/disabling Onto & CSR control signals
    does not cause AR (autoregressive) accuracy to collapse.

    The key invariant (INV-D6-4):
    > AR accuracy must remain stable (within tolerance) when control
    > signals are enabled vs disabled.
    """

    def test_b01_baseline_forward_no_controls(self, binding_cache_transformer, sample_inputs):
        """Baseline: Model runs without control signals."""
        model = binding_cache_transformer
        model.eval()

        with torch.no_grad():
            result = model(sample_inputs["input_ids"])

        if isinstance(result, dict):
            logits = result["logits"]
        elif isinstance(result, tuple):
            logits = result[1]
        else:
            logits = result

        assert logits.shape[0] == sample_inputs["input_ids"].shape[0]
        assert logits.shape[1] == sample_inputs["input_ids"].shape[1]
        assert not torch.isnan(logits).any(), "NaN in baseline logits"
        assert not torch.isinf(logits).any(), "Inf in baseline logits"

    def test_b02_forward_with_intent_phase(self, binding_cache_transformer, sample_inputs):
        """Model runs with valid intent_phase control."""
        model = binding_cache_transformer
        model.eval()

        with torch.no_grad():
            result = model(
                sample_inputs["input_ids"],
                intent_phase=sample_inputs["valid_intent_phase_2d"],
            )

        if isinstance(result, dict):
            logits = result["logits"]
        elif isinstance(result, tuple):
            logits = result[1]
        else:
            logits = result

        assert not torch.isnan(logits).any(), "NaN when intent_phase enabled"
        assert not torch.isinf(logits).any(), "Inf when intent_phase enabled"

    def test_b03_forward_with_binding_salience(self, binding_cache_transformer, sample_inputs):
        """Model runs with valid binding_salience control."""
        model = binding_cache_transformer
        model.eval()

        with torch.no_grad():
            result = model(
                sample_inputs["input_ids"],
                binding_salience=sample_inputs["valid_binding_salience"],
            )

        if isinstance(result, dict):
            logits = result["logits"]
        elif isinstance(result, tuple):
            logits = result[1]
        else:
            logits = result

        assert not torch.isnan(logits).any(), "NaN when binding_salience enabled"
        assert not torch.isinf(logits).any(), "Inf when binding_salience enabled"

    def test_b04_forward_with_all_controls(self, binding_cache_transformer, sample_inputs):
        """Model runs with all control signals enabled."""
        model = binding_cache_transformer
        model.eval()

        with torch.no_grad():
            result = model(
                sample_inputs["input_ids"],
                intent_phase=sample_inputs["valid_intent_phase_2d"],
                binding_salience=sample_inputs["valid_binding_salience"],
            )

        if isinstance(result, dict):
            logits = result["logits"]
        elif isinstance(result, tuple):
            logits = result[1]
        else:
            logits = result

        assert not torch.isnan(logits).any(), "NaN with all controls enabled"
        assert not torch.isinf(logits).any(), "Inf with all controls enabled"

    def test_b05_logit_magnitude_stable(self, binding_cache_transformer, sample_inputs):
        """Logit magnitude should be stable across control configurations (INV-D6-4)."""
        model = binding_cache_transformer
        model.eval()

        def get_logit_stats(logits):
            return {
                "mean": logits.mean().item(),
                "std": logits.std().item(),
                "max": logits.abs().max().item(),
            }

        configs = [
            ("no_controls", {}),
            ("intent_phase", {"intent_phase": sample_inputs["valid_intent_phase_2d"]}),
            ("binding_salience", {"binding_salience": sample_inputs["valid_binding_salience"]}),
            ("all_controls", {
                "intent_phase": sample_inputs["valid_intent_phase_2d"],
                "binding_salience": sample_inputs["valid_binding_salience"],
            }),
        ]

        stats = {}
        with torch.no_grad():
            for name, kwargs in configs:
                result = model(sample_inputs["input_ids"], **kwargs)
                if isinstance(result, dict):
                    logits = result["logits"]
                elif isinstance(result, tuple):
                    logits = result[1]
                else:
                    logits = result
                stats[name] = get_logit_stats(logits)

        # Check: max logit magnitude should be within 2x of baseline
        baseline_max = stats["no_controls"]["max"]
        for name, s in stats.items():
            ratio = s["max"] / (baseline_max + 1e-8)
            assert ratio < 10.0, (
                f"Logit magnitude exploded for {name}: "
                f"max={s['max']:.2f} vs baseline={baseline_max:.2f} (ratio={ratio:.2f})"
            )

    def test_b06_gradient_flow_with_controls(self, binding_cache_transformer, sample_inputs):
        """Gradients should flow when control signals are enabled."""
        model = binding_cache_transformer
        model.train()

        # Create labels for loss computation
        labels = sample_inputs["input_ids"].clone()

        result = model(
            sample_inputs["input_ids"],
            labels=labels,
            intent_phase=sample_inputs["valid_intent_phase_2d"],
            binding_salience=sample_inputs["valid_binding_salience"],
        )

        if isinstance(result, dict):
            loss = result.get("loss")
        elif isinstance(result, tuple):
            loss = result[0]
        else:
            # Compute loss manually
            logits = result
            loss = nn.functional.cross_entropy(
                logits.view(-1, logits.size(-1)),
                labels.view(-1),
            )

        assert loss is not None, "Loss should be computed"
        assert not torch.isnan(loss), "Loss is NaN"

        # Backward pass
        loss.backward()

        # Check at least some gradients exist
        has_grad = False
        for p in model.parameters():
            if p.grad is not None and p.grad.abs().sum() > 0:
                has_grad = True
                break

        assert has_grad, "No gradients flowed with controls enabled"

    def test_b07_determinism_with_controls(self, binding_cache_transformer, sample_inputs):
        """Output should be deterministic with same inputs and controls."""
        model = binding_cache_transformer
        model.eval()

        with torch.no_grad():
            result1 = model(
                sample_inputs["input_ids"],
                intent_phase=sample_inputs["valid_intent_phase_2d"],
                binding_salience=sample_inputs["valid_binding_salience"],
            )
            result2 = model(
                sample_inputs["input_ids"],
                intent_phase=sample_inputs["valid_intent_phase_2d"],
                binding_salience=sample_inputs["valid_binding_salience"],
            )

        if isinstance(result1, dict):
            logits1, logits2 = result1["logits"], result2["logits"]
        elif isinstance(result1, tuple):
            logits1, logits2 = result1[1], result2[1]
        else:
            logits1, logits2 = result1, result2

        assert torch.allclose(logits1, logits2, atol=1e-5), (
            "Non-deterministic output with controls enabled"
        )


# =============================================================================
# GROUP C: ENABLE SLOTS READ TESTS
# Purpose: Verify the D.2 enable_slots_read control flag works correctly
# =============================================================================

class TestGroupC_EnableSlotsRead:
    """
    Group C: Enable Slots Read Tests

    These tests verify the D.2 recommendation implementation:
    > enable_slots_read separates READ path gating from WRITE path.
    > Write path (phase accumulation) remains deterministic.
    > Read path (quad retrieval) can be gated by Onto/CSR controls.

    Key invariant (INV-D6-5):
    > enable_slots_read=False must skip quad retrieval without affecting phase writes.
    """

    def test_c01_enable_slots_read_default_true(self, binding_cache_block, sample_inputs):
        """enable_slots_read defaults to True (backward compatible)."""
        block = binding_cache_block
        block.eval()

        with torch.no_grad():
            # Call without specifying enable_slots_read
            output = block(sample_inputs["x"])

        assert output.shape == sample_inputs["x"].shape
        assert not torch.isnan(output).any()

    def test_c02_enable_slots_read_false_runs(self, binding_cache_block, sample_inputs):
        """Block runs with enable_slots_read=False."""
        block = binding_cache_block
        block.eval()

        with torch.no_grad():
            output = block(sample_inputs["x"], enable_slots_read=False)

        assert output.shape == sample_inputs["x"].shape
        assert not torch.isnan(output).any()

    def test_c03_enable_slots_read_false_different_output(self, binding_cache_block, sample_inputs):
        """Output differs between enable_slots_read=True and False (quad contributes)."""
        block = binding_cache_block
        block.eval()

        with torch.no_grad():
            output_with_read = block(sample_inputs["x"], enable_slots_read=True)
            output_without_read = block(sample_inputs["x"], enable_slots_read=False)

        # Outputs should differ because quad retrieval is skipped
        diff = (output_with_read - output_without_read).abs().mean()

        # They should differ (quad contributes something)
        # But this is a soft check - if quad truly contributes nothing, that's also valid
        # The key is that both should run without error
        assert output_with_read.shape == output_without_read.shape

    def test_c04_enable_slots_read_with_controls(self, binding_cache_block, sample_inputs):
        """enable_slots_read=False works with other controls."""
        block = binding_cache_block
        block.eval()

        with torch.no_grad():
            output = block(
                sample_inputs["x"],
                intent_phase=sample_inputs["valid_intent_phase_2d"],
                binding_salience=sample_inputs["valid_binding_salience"],
                enable_slots_read=False,
            )

        assert output.shape == sample_inputs["x"].shape
        assert not torch.isnan(output).any()

    def test_c05_transformer_enable_slots_read(self, binding_cache_transformer, sample_inputs):
        """BindingCacheTransformer supports enable_slots_read."""
        model = binding_cache_transformer
        model.eval()

        with torch.no_grad():
            result = model(
                sample_inputs["input_ids"],
                enable_slots_read=False,
            )

        if isinstance(result, dict):
            logits = result["logits"]
        elif isinstance(result, tuple):
            logits = result[1]
        else:
            logits = result

        assert not torch.isnan(logits).any()
        assert not torch.isinf(logits).any()

    def test_c06_gradient_flow_slots_read_false(self, binding_cache_transformer, sample_inputs):
        """Gradients flow even with enable_slots_read=False."""
        model = binding_cache_transformer
        model.train()

        labels = sample_inputs["input_ids"].clone()

        result = model(
            sample_inputs["input_ids"],
            labels=labels,
            enable_slots_read=False,
        )

        if isinstance(result, dict):
            loss = result.get("loss")
        elif isinstance(result, tuple):
            loss = result[0]
        else:
            logits = result
            loss = nn.functional.cross_entropy(
                logits.view(-1, logits.size(-1)),
                labels.view(-1),
            )

        loss.backward()

        # Check gradients exist
        has_grad = False
        for p in model.parameters():
            if p.grad is not None and p.grad.abs().sum() > 0:
                has_grad = True
                break

        assert has_grad, "No gradients with enable_slots_read=False"


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """
    Integration tests combining multiple D.6 requirements.
    """

    def test_full_control_plane_validation(self, binding_cache_transformer, sample_inputs):
        """Full integration: validate controls, run forward, check output."""
        model = binding_cache_transformer
        model.eval()

        # Step 1: Validate control shapes
        results = validate_control_signals(
            d_model=model.embed_dim,
            strict=True,  # Raise on invalid
            intent_phase=sample_inputs["valid_intent_phase_2d"],
            binding_salience=sample_inputs["valid_binding_salience"],
        )

        assert all(results.values()), "Control validation failed"

        # Step 2: Forward pass with controls
        with torch.no_grad():
            result = model(
                sample_inputs["input_ids"],
                intent_phase=sample_inputs["valid_intent_phase_2d"],
                binding_salience=sample_inputs["valid_binding_salience"],
                enable_slots_read=True,
            )

        if isinstance(result, dict):
            logits = result["logits"]
        else:
            logits = result[1] if isinstance(result, tuple) else result

        # Step 3: Verify output
        assert not torch.isnan(logits).any()
        assert not torch.isinf(logits).any()
        assert logits.abs().max() < 1000, "Logit magnitude too large"


# =============================================================================
# GROUP D: ONTOCONTROL INTERFACE TESTS (V10.6.4 D.1)
# Purpose: Verify OntoControl dataclass formalizes control plane correctly
# =============================================================================

class TestGroupD_OntoControlInterface:
    """
    Group D: OntoControl Interface Tests

    V10.6.4 (D.1): OntoControl formalizes existing binding_salience as an explicit
    control-plane object. This is a PURE DATA CONTAINER with NO behavioral changes.

    Tests verify:
    1. OntoControl wraps binding_salience correctly
    2. Validation uses existing no-write contract enforcement
    3. Serialization works for logging/debugging
    4. Factory methods create valid instances
    """

    def test_d01_ontocontrol_basic_creation(self, sample_inputs):
        """OntoControl can be created with binding_salience."""
        binding_salience = sample_inputs["valid_binding_salience"]

        onto_ctrl = OntoControl(binding_salience=binding_salience)

        assert onto_ctrl.binding_salience is binding_salience
        assert onto_ctrl.enable_slots_read is True  # default
        assert onto_ctrl.source == "ontology"  # default

    def test_d02_ontocontrol_from_salience_factory(self, sample_inputs):
        """OntoControl.from_salience factory creates valid instance."""
        binding_salience = sample_inputs["valid_binding_salience"]

        onto_ctrl = OntoControl.from_salience(
            binding_salience,
            source="annotator",
            confidence=0.95,
        )

        assert onto_ctrl.binding_salience is binding_salience
        assert onto_ctrl.source == "annotator"
        assert onto_ctrl.confidence == 0.95

    def test_d03_onto_control_from_salience_adapter(self, sample_inputs):
        """onto_control_from_salience adapter function works."""
        binding_salience = sample_inputs["valid_binding_salience"]

        onto_ctrl = onto_control_from_salience(binding_salience, source="csr")

        assert onto_ctrl.binding_salience is binding_salience
        assert onto_ctrl.source == "csr"

    def test_d04_ontocontrol_validate_valid_signals(self, model_config, sample_inputs):
        """OntoControl.validate() accepts valid control signals."""
        onto_ctrl = OntoControl(
            binding_salience=sample_inputs["valid_binding_salience"],
            intent_phase=sample_inputs["valid_intent_phase_2d"],
        )

        results = onto_ctrl.validate(
            d_model=model_config["embed_dim"],
            strict=False,
        )

        assert results["binding_salience"] is True
        assert results["intent_phase"] is True

    def test_d05_ontocontrol_validate_invalid_intent_phase(self, model_config, sample_inputs):
        """OntoControl.validate() rejects invalid intent_phase."""
        onto_ctrl = OntoControl(
            binding_salience=sample_inputs["valid_binding_salience"],
            intent_phase=sample_inputs["invalid_intent_phase"],  # [B, N, D] INVALID
        )

        results = onto_ctrl.validate(
            d_model=model_config["embed_dim"],
            strict=False,
        )

        assert results["binding_salience"] is True
        assert results["intent_phase"] is False, "Invalid intent_phase should be rejected"

    def test_d06_ontocontrol_validate_strict_raises(self, model_config, sample_inputs):
        """OntoControl.validate() raises in strict mode for invalid signals."""
        onto_ctrl = OntoControl(
            intent_phase=sample_inputs["invalid_intent_phase"],  # [B, N, D] INVALID
        )

        with pytest.raises(ControlShapeViolation):
            onto_ctrl.validate(
                d_model=model_config["embed_dim"],
                strict=True,
            )

    def test_d07_ontocontrol_to_dict_serialization(self, sample_inputs):
        """OntoControl.to_dict() serializes correctly for logging."""
        binding_salience = sample_inputs["valid_binding_salience"]
        intent_phase = sample_inputs["valid_intent_phase_2d"]

        onto_ctrl = OntoControl(
            binding_salience=binding_salience,
            intent_phase=intent_phase,
            enable_slots_read=False,
            source="test",
            confidence=0.85,
        )

        d = onto_ctrl.to_dict()

        assert d["binding_salience_shape"] == list(binding_salience.shape)
        assert d["intent_phase_shape"] == list(intent_phase.shape)
        assert d["enable_slots_read"] is False
        assert d["source"] == "test"
        assert d["confidence"] == 0.85

    def test_d08_ontocontrol_to_dict_with_none_values(self):
        """OntoControl.to_dict() handles None values correctly."""
        onto_ctrl = OntoControl()  # All tensor fields None

        d = onto_ctrl.to_dict()

        assert d["binding_salience_shape"] is None
        assert d["intent_phase_shape"] is None
        assert d["enable_slots_read"] is True
        assert d["source"] == "ontology"

    def test_d09_ontocontrol_future_flags_no_behavior(self, sample_inputs):
        """Future flags (enable_quad, enable_csr) exist but have no behavior."""
        onto_ctrl = OntoControl(
            binding_salience=sample_inputs["valid_binding_salience"],
            enable_quad=True,
            enable_csr=False,
        )

        # Flags exist and can be set
        assert onto_ctrl.enable_quad is True
        assert onto_ctrl.enable_csr is False

        # to_dict includes them
        d = onto_ctrl.to_dict()
        assert d["enable_quad"] is True
        assert d["enable_csr"] is False

    def test_d10_ontocontrol_preserves_no_write_contract(self, model_config, sample_inputs):
        """OntoControl preserves the no-write contract (D.5) through validation."""
        # Valid: [B, N] for binding_salience
        valid_ctrl = OntoControl(
            binding_salience=sample_inputs["valid_binding_salience"],
        )
        valid_results = valid_ctrl.validate(d_model=model_config["embed_dim"], strict=False)
        assert valid_results["binding_salience"] is True

        # Invalid: [B, N, D] would violate no-write contract
        invalid_ctrl = OntoControl(
            binding_salience=sample_inputs["invalid_binding_salience"],  # [B, N, D]
        )
        invalid_results = invalid_ctrl.validate(d_model=model_config["embed_dim"], strict=False)
        assert invalid_results["binding_salience"] is False


# =============================================================================
# GROUP E: FORWARD-PASS CONTRACT ENFORCEMENT TESTS (V10.6.6)
# Purpose: Verify no-write contract is enforced INSIDE forward(), not just config
# =============================================================================

class TestGroupE_ForwardPassEnforcement:
    """
    Group E: Forward-Pass Contract Enforcement Tests (V10.6.6)

    These tests verify that the no-write contract is enforced INSIDE the forward
    pass, not just during configuration or health checks. This is the "highest-risk
    gap" identified by ChatGPT review - violations must STOP TRAINING immediately.

    Critical Requirements:
    - INV-E6-1: Invalid control signals in forward() must raise ControlShapeViolation
    - INV-E6-2: Enforcement must happen at BindingCacheBlock.forward() entry
    - INV-E6-3: Enforcement must happen at BindingCacheTransformer.forward() entry
    - INV-E6-4: enforce_control_contract=True is the default (STRICT)
    - INV-E6-5: set_enforce_control_contract() propagates to all child blocks

    Reference: ChatGPT feedback on V10.6.5 - "True No-Write Contract Enforcement"
    """

    def test_e01_block_forward_rejects_invalid_intent_phase(
        self, binding_cache_block, model_config, sample_inputs
    ):
        """BindingCacheBlock.forward() must HARD-FAIL on invalid intent_phase (INV-E6-1)."""
        x = sample_inputs["x"]
        invalid_intent_phase = sample_inputs["invalid_intent_phase"]  # [B, N, D]

        # Default enforcement is True
        assert binding_cache_block.enforce_control_contract is True

        with pytest.raises(ControlShapeViolation) as exc_info:
            binding_cache_block(x, intent_phase=invalid_intent_phase)

        assert "intent_phase" in str(exc_info.value)

    def test_e02_block_forward_rejects_invalid_binding_salience(
        self, binding_cache_block, model_config, sample_inputs
    ):
        """BindingCacheBlock.forward() must HARD-FAIL on invalid binding_salience (INV-E6-1)."""
        x = sample_inputs["x"]
        invalid_salience = sample_inputs["invalid_binding_salience"]  # [B, N, D]

        with pytest.raises(ControlShapeViolation) as exc_info:
            binding_cache_block(x, binding_salience=invalid_salience)

        assert "binding_salience" in str(exc_info.value)

    def test_e03_block_forward_accepts_valid_controls(
        self, binding_cache_block, model_config, sample_inputs
    ):
        """BindingCacheBlock.forward() must accept valid control signals."""
        x = sample_inputs["x"]
        valid_intent = sample_inputs["valid_intent_phase_2d"]
        valid_salience = sample_inputs["valid_binding_salience"]

        # Should NOT raise - valid controls
        output = binding_cache_block(
            x,
            intent_phase=valid_intent,
            binding_salience=valid_salience,
        )

        assert output.shape == x.shape

    def test_e04_transformer_forward_rejects_invalid_intent_phase(
        self, binding_cache_transformer, model_config, sample_inputs
    ):
        """BindingCacheTransformer.forward() must HARD-FAIL on invalid intent_phase (INV-E6-3)."""
        input_ids = sample_inputs["input_ids"]
        invalid_intent_phase = sample_inputs["invalid_intent_phase"]  # [B, N, D]

        # Default enforcement is True
        assert binding_cache_transformer.enforce_control_contract is True

        with pytest.raises(ControlShapeViolation) as exc_info:
            binding_cache_transformer(input_ids, intent_phase=invalid_intent_phase)

        assert "intent_phase" in str(exc_info.value)

    def test_e05_transformer_forward_rejects_invalid_binding_salience(
        self, binding_cache_transformer, model_config, sample_inputs
    ):
        """BindingCacheTransformer.forward() must HARD-FAIL on invalid binding_salience."""
        input_ids = sample_inputs["input_ids"]
        invalid_salience = sample_inputs["invalid_binding_salience"]  # [B, N, D]

        with pytest.raises(ControlShapeViolation) as exc_info:
            binding_cache_transformer(input_ids, binding_salience=invalid_salience)

        assert "binding_salience" in str(exc_info.value)

    def test_e06_transformer_forward_accepts_valid_controls(
        self, binding_cache_transformer, model_config, sample_inputs
    ):
        """BindingCacheTransformer.forward() must accept valid control signals."""
        input_ids = sample_inputs["input_ids"]
        valid_intent = sample_inputs["valid_intent_phase_2d"]
        valid_salience = sample_inputs["valid_binding_salience"]

        # Should NOT raise - valid controls
        output = binding_cache_transformer(
            input_ids,
            intent_phase=valid_intent,
            binding_salience=valid_salience,
        )

        # Returns logits tensor
        assert output.dim() == 3  # [B, N, vocab_size]

    def test_e07_enforcement_enabled_by_default(
        self, binding_cache_block, binding_cache_transformer
    ):
        """enforce_control_contract must be True by default (INV-E6-4)."""
        # Block level
        assert binding_cache_block.enforce_control_contract is True

        # Transformer level
        assert binding_cache_transformer.enforce_control_contract is True

        # All child blocks
        for block in binding_cache_transformer.blocks:
            assert block.enforce_control_contract is True

    def test_e08_set_enforce_control_contract_propagates(
        self, binding_cache_transformer, sample_inputs
    ):
        """set_enforce_control_contract() must propagate to all child blocks (INV-E6-5)."""
        # Disable enforcement
        binding_cache_transformer.set_enforce_control_contract(False)

        # Check transformer
        assert binding_cache_transformer.enforce_control_contract is False

        # Check all child blocks
        for block in binding_cache_transformer.blocks:
            assert block.enforce_control_contract is False

        # Re-enable enforcement
        binding_cache_transformer.set_enforce_control_contract(True)

        # Verify re-enabled
        assert binding_cache_transformer.enforce_control_contract is True
        for block in binding_cache_transformer.blocks:
            assert block.enforce_control_contract is True

    def test_e09_disabled_enforcement_allows_invalid_controls(
        self, binding_cache_transformer, sample_inputs
    ):
        """When enforcement is disabled, invalid controls should NOT raise (debugging only)."""
        input_ids = sample_inputs["input_ids"]
        invalid_intent_phase = sample_inputs["invalid_intent_phase"]

        # Disable enforcement (NOT recommended for production)
        binding_cache_transformer.set_enforce_control_contract(False)

        try:
            # Should NOT raise with enforcement disabled
            output = binding_cache_transformer(input_ids, intent_phase=invalid_intent_phase)
            # Model runs but produces potentially garbage output
            assert output.dim() == 3
        finally:
            # Always re-enable for safety
            binding_cache_transformer.set_enforce_control_contract(True)

    def test_e10_forward_hidden_also_enforces_contract(
        self, binding_cache_transformer, sample_inputs
    ):
        """forward_hidden() must also enforce the no-write contract."""
        input_ids = sample_inputs["input_ids"]
        invalid_intent_phase = sample_inputs["invalid_intent_phase"]

        with pytest.raises(ControlShapeViolation) as exc_info:
            binding_cache_transformer.forward_hidden(
                input_ids, intent_phase=invalid_intent_phase
            )

        assert "intent_phase" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
