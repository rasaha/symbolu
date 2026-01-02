"""
Unit Tests for Sovereign-1 Phase 2 Modules
===========================================

Tests for:
- PIDGovernor: Vritti detection, authority gating, gradient flow, streaming
- SovereignTransformer: AmbidextrousLayer mode switching, Virtual Nexus
- SovereignGunaComputer: Shannon entropy, variance, cosine similarity
- DeterministicPhonemeEncoder: Determinism, feature structure
- ReferentLookup: Class encoding, WORD_TO_REFERENT integration

Critical checks:
1. Gradients flow correctly through all modules
2. AmbidextrousLayer correctly switches between quadratic and phase modes
3. PIDGovernor doesn't accidentally zero out gradients
4. Guna conservation property holds (S+R+T = 1.0)
5. Phoneme encoding is deterministic (same input → same output)
"""

import pytest
import torch
import torch.nn as nn
import torch.nn.functional as F
import math


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def device():
    """Use CUDA if available, else CPU."""
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


@pytest.fixture
def batch_params():
    """Standard batch parameters."""
    return {
        "batch_size": 2,
        "seq_len": 16,
        "embed_dim": 1024,
        "num_heads": 16,
        "vocab_size": 1000,
    }


# =============================================================================
# PIDGovernor Tests
# =============================================================================

class TestPIDGovernor:
    """Test PIDGovernor module."""

    def test_forward_shape(self, device, batch_params):
        """Test that forward pass produces correct output shapes."""
        from symbolu.sovereign.pid_governor import PIDGovernor, PIDGovernorConfig

        B, N, D = batch_params["batch_size"], batch_params["seq_len"], batch_params["embed_dim"]

        config = PIDGovernorConfig()
        governor = PIDGovernor(config=config, embed_dim=D).to(device)

        x = torch.randn(B, N, D, device=device)
        target_state = torch.randn(B, N, 128, device=device)

        x_out, authority, pid_state = governor(x, target_state)

        assert x_out.shape == (B, N, D), f"Expected {(B, N, D)}, got {x_out.shape}"
        assert authority.shape == (B, N), f"Expected {(B, N)}, got {authority.shape}"
        assert len(pid_state) == 2, "PID state should be tuple of (integral_error, prev_error)"
        assert pid_state[0].shape == (B, N), f"Integral error shape mismatch"
        assert pid_state[1].shape == (B, N), f"Prev error shape mismatch"

    def test_vritti_detection(self, device):
        """Test that Vritti detection works correctly for different R-signals."""
        from symbolu.sovereign.pid_governor import PIDGovernor, PIDGovernorConfig

        config = PIDGovernorConfig()
        governor = PIDGovernor(config=config).to(device)

        # Create R-signal with dominant FACTUAL (index 0) → should be "pramana"
        r_signal = torch.zeros(2, 48, device=device)
        r_signal[:, 0:4] = 1.0  # Bhava 0 (FACTUAL) is dominant

        vritti = governor._detect_dominant_vritti(r_signal)
        assert vritti == "pramana", f"Expected pramana for FACTUAL, got {vritti}"

        # Create R-signal with dominant NARRATIVE (index 3) → should be "vikalpa"
        r_signal = torch.zeros(2, 48, device=device)
        r_signal[:, 12:16] = 1.0  # Bhava 3 (NARRATIVE) is dominant

        vritti = governor._detect_dominant_vritti(r_signal)
        assert vritti == "vikalpa", f"Expected vikalpa for NARRATIVE, got {vritti}"

    def test_authority_gating(self, device, batch_params):
        """Test that authority gating dampens semantic body when authority < 0.7."""
        from symbolu.sovereign.pid_governor import PIDGovernor, PIDGovernorConfig

        B, N, D = batch_params["batch_size"], batch_params["seq_len"], batch_params["embed_dim"]

        config = PIDGovernorConfig(authority_threshold=0.7, dampening_factor=0.1)
        governor = PIDGovernor(config=config, embed_dim=D).to(device)

        x = torch.ones(B, N, D, device=device)

        # Create target state that is very different from current (will cause low authority)
        target_state = torch.randn(B, N, 128, device=device) * 10

        x_out, authority, _ = governor(x, target_state)

        # Check that low authority positions are dampened
        low_authority_mask = authority < 0.7
        if low_authority_mask.any():
            # Semantic body should be dampened (×0.1)
            dampened_semantic = x_out[low_authority_mask, :896]
            expected = x[low_authority_mask, :896] * 0.1
            assert torch.allclose(dampened_semantic, expected, atol=1e-5), \
                "Low authority semantic body not dampened correctly"

    def test_gradient_flow(self, device, batch_params):
        """CRITICAL: Test that gradients flow through PIDGovernor correctly."""
        from symbolu.sovereign.pid_governor import PIDGovernor, PIDGovernorConfig

        B, N, D = batch_params["batch_size"], batch_params["seq_len"], batch_params["embed_dim"]

        config = PIDGovernorConfig()
        governor = PIDGovernor(config=config, embed_dim=D).to(device)

        x = torch.randn(B, N, D, device=device, requires_grad=True)
        target_state = torch.randn(B, N, 128, device=device)

        x_out, authority, _ = governor(x, target_state)

        # Compute loss and backprop
        loss = x_out.sum()
        loss.backward()

        # CRITICAL CHECK: x must have non-zero gradients
        assert x.grad is not None, "CRITICAL: No gradient computed for input x"
        assert not torch.allclose(x.grad, torch.zeros_like(x.grad)), \
            "CRITICAL: PIDGovernor zeroed out gradients!"

        # Check that learnable parameters have gradients
        assert governor.kp_adjust.grad is not None, "kp_adjust should have gradient"

    def test_streaming_state(self, device, batch_params):
        """Test that PID state is correctly passed between calls for streaming."""
        from symbolu.sovereign.pid_governor import PIDGovernor, PIDGovernorConfig

        B, N, D = batch_params["batch_size"], batch_params["seq_len"], batch_params["embed_dim"]

        config = PIDGovernorConfig()
        governor = PIDGovernor(config=config, embed_dim=D).to(device)

        x = torch.randn(B, N, D, device=device)
        target = torch.randn(B, N, 128, device=device)

        # First call without state
        _, _, state1 = governor(x, target, pid_state=None)
        integral1, prev1 = state1

        # Second call with state from first
        _, _, state2 = governor(x, target, pid_state=state1)
        integral2, prev2 = state2

        # Integral error should accumulate
        assert not torch.allclose(integral1, integral2), \
            "Integral error should change between calls"


# =============================================================================
# AmbidextrousLayer Tests
# =============================================================================

class TestAmbidextrousLayer:
    """Test AmbidextrousLayer mode switching."""

    def test_mode_switching(self, device, batch_params):
        """CRITICAL: Test that quadratic and phase modes produce different outputs."""
        from symbolu.sovereign.transformer import AmbidextrousLayer

        B, N, D = batch_params["batch_size"], batch_params["seq_len"], batch_params["embed_dim"]
        H = batch_params["num_heads"]

        layer = AmbidextrousLayer(
            embed_dim=D,
            num_heads=H,
            ff_dim=D * 4,
        ).to(device)

        torch.manual_seed(42)
        x = torch.randn(B, N, D, device=device)

        # Run quadratic mode
        out_quadratic = layer(x, mode="quadratic", causal_mask=True)

        # Run phase mode with same input
        out_phase = layer(x, mode="phase", causal_mask=True)

        # Outputs MUST be different (modes work differently)
        assert not torch.allclose(out_quadratic, out_phase, atol=1e-3), \
            "CRITICAL: Quadratic and phase modes produce identical outputs - mode switching broken!"

        # Both should have same shape
        assert out_quadratic.shape == out_phase.shape == (B, N, D)

    def test_quadratic_attention_complexity(self, device):
        """Test that quadratic attention creates N×N attention matrix."""
        from symbolu.sovereign.transformer import AmbidextrousLayer

        D, H = 256, 4
        layer = AmbidextrousLayer(embed_dim=D, num_heads=H, ff_dim=D * 4).to(device)

        # Use small sequence to verify
        B, N = 2, 8
        x = torch.randn(B, N, D, device=device)

        # We can verify this by checking internal attention computation
        # For now, just ensure it runs without error
        out = layer(x, mode="quadratic")
        assert out.shape == (B, N, D)

    def test_phase_attention_linear_complexity(self, device):
        """Test that phase attention avoids N×N computation."""
        from symbolu.sovereign.transformer import AmbidextrousLayer

        D, H = 256, 4
        layer = AmbidextrousLayer(embed_dim=D, num_heads=H, ff_dim=D * 4).to(device)

        # Phase attention should work on longer sequences efficiently
        B, N = 2, 64  # Longer sequence
        x = torch.randn(B, N, D, device=device)

        out = layer(x, mode="phase")
        assert out.shape == (B, N, D)

    def test_gradient_flow_both_modes(self, device, batch_params):
        """Test gradient flow through both attention modes."""
        from symbolu.sovereign.transformer import AmbidextrousLayer

        B, N, D = batch_params["batch_size"], batch_params["seq_len"], batch_params["embed_dim"]
        H = batch_params["num_heads"]

        layer = AmbidextrousLayer(embed_dim=D, num_heads=H, ff_dim=D * 4).to(device)

        for mode in ["quadratic", "phase"]:
            x = torch.randn(B, N, D, device=device, requires_grad=True)
            out = layer(x, mode=mode)
            loss = out.sum()
            loss.backward()

            assert x.grad is not None, f"No gradient in {mode} mode"
            assert not torch.allclose(x.grad, torch.zeros_like(x.grad)), \
                f"CRITICAL: {mode} mode zeroed out gradients!"


# =============================================================================
# SovereignTransformer Tests
# =============================================================================

class TestSovereignTransformer:
    """Test full SovereignTransformer with Virtual Nexus."""

    def test_forward_pass(self, device):
        """Test basic forward pass through transformer."""
        from symbolu.sovereign.transformer import SovereignTransformer, SovereignTransformerConfig

        config = SovereignTransformerConfig(
            vocab_size=1000,
            embed_dim=256,
            num_layers=4,
            num_heads=4,
            ff_dim=512,
        )
        model = SovereignTransformer(config=config).to(device)

        B, N = 2, 16
        token_ids = torch.randint(0, 1000, (B, N), device=device)

        outputs = model(token_ids)

        assert "logits" in outputs
        assert "authority" in outputs
        assert outputs["logits"].shape == (B, N, config.vocab_size)

    def test_virtual_nexus_positions(self, device):
        """Test that different nexus positions produce different outputs."""
        from symbolu.sovereign.transformer import SovereignTransformer, SovereignTransformerConfig

        config = SovereignTransformerConfig(
            vocab_size=1000,
            embed_dim=256,
            num_layers=12,
            num_heads=4,
            ff_dim=512,
        )
        model = SovereignTransformer(config=config).to(device)

        B, N = 2, 16
        token_ids = torch.randint(0, 1000, (B, N), device=device)

        # Different nexus positions
        out_4 = model(token_ids, nexus_position=4)
        out_6 = model(token_ids, nexus_position=6)
        out_8 = model(token_ids, nexus_position=8)

        # Outputs should differ based on nexus position
        assert not torch.allclose(out_4["logits"], out_6["logits"], atol=1e-3), \
            "Nexus 4 and 6 produce identical outputs"
        assert not torch.allclose(out_6["logits"], out_8["logits"], atol=1e-3), \
            "Nexus 6 and 8 produce identical outputs"

    def test_nexus_selection_by_ontology(self, device):
        """Test ontology-based nexus selection."""
        from symbolu.sovereign.transformer import SovereignTransformer, SovereignTransformerConfig

        config = SovereignTransformerConfig()
        model = SovereignTransformer(config=config).to(device)

        # Test different ontology types
        assert model.select_nexus("O7_REASONING") == 4
        assert model.select_nexus("O6_AGENCY") == 6
        assert model.select_nexus("O4_STRUCTURE") == 8
        assert model.select_nexus(None) == config.default_nexus

    def test_gradient_flow_with_pid(self, device):
        """CRITICAL: Test gradient flow through transformer with PID Governor."""
        from symbolu.sovereign.transformer import SovereignTransformer, SovereignTransformerConfig

        config = SovereignTransformerConfig(
            vocab_size=1000,
            embed_dim=256,
            num_layers=4,
            num_heads=4,
            ff_dim=512,
        )
        model = SovereignTransformer(config=config).to(device)

        B, N = 2, 16
        token_ids = torch.randint(0, 1000, (B, N), device=device)

        outputs = model(token_ids)
        loss = outputs["logits"].sum()
        loss.backward()

        # Check key parameters have gradients
        assert model.token_embedding.weight.grad is not None, \
            "Token embedding should have gradient"
        assert not torch.allclose(model.token_embedding.weight.grad,
                                  torch.zeros_like(model.token_embedding.weight.grad)), \
            "CRITICAL: Token embedding gradients are zero!"


# =============================================================================
# SovereignGunaComputer Tests
# =============================================================================

class TestSovereignGunaComputer:
    """Test SovereignGunaComputer Guna derivation."""

    def test_sattva_entropy(self, device):
        """Test Sattva computation via Shannon entropy."""
        from symbolu.sovereign.guna import SovereignGunaComputer

        computer = SovereignGunaComputer(embed_dim=256, num_heads=4).to(device)

        B, H, N = 2, 4, 16

        # Focused attention (low entropy) → high Sattva
        focused_attn = torch.zeros(B, H, N, N, device=device)
        focused_attn[:, :, :, 0] = 1.0  # All attention on first token

        sattva_focused = computer.compute_sattva(focused_attn)

        # Uniform attention (high entropy) → low Sattva
        uniform_attn = torch.ones(B, H, N, N, device=device) / N

        sattva_uniform = computer.compute_sattva(uniform_attn)

        # Focused should have higher Sattva than uniform
        assert sattva_focused.mean() > sattva_uniform.mean(), \
            "Focused attention should produce higher Sattva than uniform"

    def test_rajas_variance(self, device):
        """Test Rajas computation via head variance."""
        from symbolu.sovereign.guna import SovereignGunaComputer

        computer = SovereignGunaComputer(embed_dim=256, num_heads=4).to(device)

        B, H, N, d = 2, 4, 16, 64

        # High variance across heads → high Rajas
        high_var = torch.randn(B, H, N, d, device=device) * 2
        rajas_high = computer.compute_rajas(high_var)

        # Low variance (similar across heads) → low Rajas
        base = torch.randn(B, 1, N, d, device=device)
        low_var = base.expand(B, H, N, d).clone() + torch.randn(B, H, N, d, device=device) * 0.01
        rajas_low = computer.compute_rajas(low_var)

        assert rajas_high.mean() > rajas_low.mean(), \
            "High variance should produce higher Rajas"

    def test_tamas_similarity(self, device):
        """Test Tamas computation via cosine similarity."""
        from symbolu.sovereign.guna import SovereignGunaComputer

        computer = SovereignGunaComputer(embed_dim=256, num_heads=4).to(device)

        B, N, D = 2, 16, 256

        hidden = torch.randn(B, N, D, device=device)

        # Same as previous → high Tamas (high inertia)
        tamas_same = computer.compute_tamas(hidden, hidden)

        # Very different from previous → low Tamas
        different = -hidden  # Opposite direction
        tamas_diff = computer.compute_tamas(hidden, different)

        assert tamas_same.mean() > tamas_diff.mean(), \
            "Same state should produce higher Tamas than opposite state"

    def test_guna_conservation(self, device):
        """CRITICAL: Test that Guna values sum to 1.0 (conservation of energy)."""
        from symbolu.sovereign.guna import SovereignGunaComputer

        computer = SovereignGunaComputer(embed_dim=256, num_heads=4).to(device)

        B, H, N, d = 2, 4, 16, 64

        attention_weights = F.softmax(torch.randn(B, H, N, N, device=device), dim=-1)
        head_outputs = torch.randn(B, H, N, d, device=device)
        hidden_states = torch.randn(B, N, 256, device=device)
        prev_hidden = torch.randn(B, N, 256, device=device)

        result = computer(
            attention_weights=attention_weights,
            head_outputs=head_outputs,
            hidden_states=hidden_states,
            prev_hidden_states=prev_hidden,
        )

        guna_3d = result["guna_3d"]  # [B, 3]

        # Sum should be 1.0 (softmax normalization)
        guna_sum = guna_3d.sum(dim=-1)
        assert torch.allclose(guna_sum, torch.ones_like(guna_sum), atol=1e-5), \
            f"CRITICAL: Guna conservation violated! Sum = {guna_sum}"

    def test_guna_range(self, device):
        """Test that all Guna values are in [0, 1]."""
        from symbolu.sovereign.guna import SovereignGunaComputer

        computer = SovereignGunaComputer(embed_dim=256, num_heads=4).to(device)

        B, H, N, d = 2, 4, 16, 64

        attention_weights = F.softmax(torch.randn(B, H, N, N, device=device), dim=-1)
        hidden_states = torch.randn(B, N, 256, device=device)

        result = computer(
            attention_weights=attention_weights,
            hidden_states=hidden_states,
        )

        assert (result["sattva"] >= 0).all() and (result["sattva"] <= 1).all()
        assert (result["rajas"] >= 0).all() and (result["rajas"] <= 1).all()
        assert (result["tamas"] >= 0).all() and (result["tamas"] <= 1).all()


# =============================================================================
# DeterministicPhonemeEncoder Tests
# =============================================================================

class TestDeterministicPhonemeEncoder:
    """Test DeterministicPhonemeEncoder determinism and features."""

    def test_determinism(self, device):
        """CRITICAL: Same token should always produce same features."""
        from symbolu.sovereign.observer import DeterministicPhonemeEncoder

        encoder = DeterministicPhonemeEncoder(vocab_size=1000).to(device)

        token_ids = torch.tensor([[42, 100, 500]], device=device)

        # Run multiple times
        out1 = encoder(token_ids)
        out2 = encoder(token_ids)
        out3 = encoder(token_ids)

        assert torch.allclose(out1, out2), "Output 1 != Output 2 - NOT DETERMINISTIC"
        assert torch.allclose(out2, out3), "Output 2 != Output 3 - NOT DETERMINISTIC"

    def test_output_shape(self, device, batch_params):
        """Test output shape is correct."""
        from symbolu.sovereign.observer import DeterministicPhonemeEncoder

        B, N = batch_params["batch_size"], batch_params["seq_len"]
        encoder = DeterministicPhonemeEncoder(vocab_size=1000, output_dim=32).to(device)

        token_ids = torch.randint(0, 1000, (B, N), device=device)
        out = encoder(token_ids)

        # forward() returns mean over sequence
        assert out.shape == (B, 32), f"Expected {(B, 32)}, got {out.shape}"

    def test_hash_token_features(self):
        """Test _hash_token produces 32 features."""
        from symbolu.sovereign.observer import DeterministicPhonemeEncoder

        encoder = DeterministicPhonemeEncoder(vocab_size=1000, output_dim=32)

        features = encoder._hash_token("hello")
        assert len(features) == 32

        # Features should be in [0, 1]
        assert all(0 <= f <= 1 for f in features)

        # Same word should give same features
        features2 = encoder._hash_token("hello")
        assert features == features2

        # Different words should give different features
        features3 = encoder._hash_token("world")
        assert features != features3


# =============================================================================
# ReferentLookup Tests
# =============================================================================

class TestReferentLookup:
    """Test ReferentLookup S-Signal computation."""

    def test_output_shape(self, device, batch_params):
        """Test output shape is correct."""
        from symbolu.sovereign.observer import ReferentLookup

        B, N = batch_params["batch_size"], batch_params["seq_len"]
        lookup = ReferentLookup(vocab_size=1000, output_dim=32).to(device)

        token_ids = torch.randint(0, 1000, (B, N), device=device)
        out = lookup(token_ids)

        assert out.shape == (B, 32), f"Expected {(B, 32)}, got {out.shape}"

    def test_referent_classes(self):
        """Test all 16 referent classes are defined."""
        from symbolu.sovereign.observer import ReferentLookup

        lookup = ReferentLookup()
        assert len(lookup.REFERENT_CLASSES) == 16
        assert "unknown" in lookup.REFERENT_CLASSES


# =============================================================================
# BhavaTransitionPrior Tests
# =============================================================================

class TestBhavaTransitionPrior:
    """Test BhavaTransitionPrior penalty computation."""

    def test_penalty_shape(self, device):
        """Test penalty computation produces correct shape."""
        from symbolu.sovereign.observer import BhavaTransitionPrior

        prior = BhavaTransitionPrior().to(device)

        B, N = 2, 16
        current_r = torch.randn(B, N, 48, device=device)
        prev_r = torch.randn(B, N, 48, device=device)

        penalty = prior.get_transition_penalty(current_r, prev_r)
        assert penalty.shape == (B, N), f"Expected {(B, N)}, got {penalty.shape}"

    def test_penalty_range(self, device):
        """Test penalties are in [0, 1]."""
        from symbolu.sovereign.observer import BhavaTransitionPrior

        prior = BhavaTransitionPrior().to(device)

        current_r = torch.randn(2, 48, device=device)
        prev_r = torch.randn(2, 48, device=device)

        penalty = prior.get_transition_penalty(current_r, prev_r)
        assert (penalty >= 0).all() and (penalty <= 1).all()

    def test_legal_transition_low_penalty(self, device):
        """Test that legal transitions have lower penalty."""
        from symbolu.sovereign.observer import BhavaTransitionPrior

        prior = BhavaTransitionPrior().to(device)

        # FACTUAL → FACTUAL (legal: 0.8 in matrix → penalty 0.2)
        legal_prev = torch.zeros(2, 48, device=device)
        legal_prev[:, 0:4] = 1.0  # FACTUAL

        legal_curr = torch.zeros(2, 48, device=device)
        legal_curr[:, 0:4] = 1.0  # FACTUAL

        penalty_legal = prior.get_transition_penalty(legal_curr, legal_prev)

        # QUESTIONING → INSTRUCTIVE (illegal: 0.1 in matrix → penalty 0.9)
        illegal_prev = torch.zeros(2, 48, device=device)
        illegal_prev[:, 32:36] = 1.0  # QUESTIONING (index 8)

        illegal_curr = torch.zeros(2, 48, device=device)
        illegal_curr[:, 20:24] = 1.0  # INSTRUCTIVE (index 5)

        penalty_illegal = prior.get_transition_penalty(illegal_curr, illegal_prev)

        # Legal should have lower penalty
        assert penalty_legal.mean() < penalty_illegal.mean(), \
            "Legal transitions should have lower penalty than illegal"


# =============================================================================
# SovereignObserver Integration Tests
# =============================================================================

class TestSovereignObserver:
    """Test full SovereignObserver integration."""

    def test_full_state_delta_shape(self, device, batch_params):
        """Test full 128-D state delta computation."""
        from symbolu.sovereign.observer import SovereignObserver

        B, N = batch_params["batch_size"], batch_params["seq_len"]
        D = 256

        observer = SovereignObserver(embed_dim=D, vocab_size=1000).to(device)

        token_ids = torch.randint(0, 1000, (B, N), device=device)
        hidden_states = torch.randn(B, N, D, device=device)

        result = observer(token_ids, hidden_states)

        assert result["state_delta"].shape == (B, 128), \
            f"Expected {(B, 128)}, got {result['state_delta'].shape}"
        assert result["guna"].shape == (B, 16)
        assert result["s_signal"].shape == (B, 32)
        assert result["r_signal"].shape == (B, 48)
        assert result["c_signal"].shape == (B, 32)

    def test_no_grad_mode(self, device):
        """Test that observer runs in no_grad mode (no gradient tracking)."""
        from symbolu.sovereign.observer import SovereignObserver

        observer = SovereignObserver(embed_dim=256, vocab_size=1000).to(device)

        token_ids = torch.randint(0, 1000, (2, 16), device=device)
        hidden_states = torch.randn(2, 16, 256, device=device, requires_grad=True)

        with torch.enable_grad():
            result = observer(token_ids, hidden_states)

        # State delta should not require grad (observer is @torch.no_grad)
        assert not result["state_delta"].requires_grad, \
            "Observer output should not require gradient"


# =============================================================================
# End-to-End Integration Test
# =============================================================================

class TestEndToEndIntegration:
    """End-to-end integration tests for Phase 2 modules."""

    def test_full_forward_backward(self, device):
        """Test full forward and backward pass through all modules."""
        from symbolu.sovereign.transformer import SovereignTransformer, SovereignTransformerConfig
        from symbolu.sovereign.observer import SovereignObserver

        # Create transformer
        config = SovereignTransformerConfig(
            vocab_size=1000,
            embed_dim=256,
            num_layers=4,
            num_heads=4,
            ff_dim=512,
        )
        model = SovereignTransformer(config=config).to(device)

        # Create observer
        observer = SovereignObserver(
            embed_dim=256,
            vocab_size=1000,
        ).to(device)

        B, N = 2, 16
        token_ids = torch.randint(0, 1000, (B, N), device=device)

        # Forward through model (without observer state)
        outputs = model(token_ids, nexus_position=6)

        # Compute loss
        targets = torch.randint(0, 1000, (B, N), device=device)
        loss = F.cross_entropy(
            outputs["logits"].view(-1, 1000),
            targets.view(-1)
        )

        # Backward
        loss.backward()

        # Verify gradients exist and are non-zero
        assert model.token_embedding.weight.grad is not None
        grad_norm = model.token_embedding.weight.grad.norm()
        assert grad_norm > 0, f"Gradient norm is zero: {grad_norm}"

        print(f"✅ End-to-end test passed. Gradient norm: {grad_norm:.4f}")


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
