"""
Tests for Appendix F Stage 2 — Interpretive Conditioner.

Validates:
- InterpretiveConditionerConfig defaults and custom values (F.4.4)
- BhavaVectorCompressor compression + coherence output (F.5 dependency)
- InterpretiveStateBuilder context projections + concatenation
- InterpretiveConditioner gated residual conditioning (F.4.4)
  - Zero-gate cold start: output == input
  - Disabled mode: passthrough
  - Non-zero gate: output != input
  - Synthesis MLP final layer zero-initialized
- Integration with SymbolU12LLM.forward() (F.4.5)
  - forward() without conditioner: unchanged behavior
  - forward() with conditioner: produces conditioned logits
  - Logits differ from unconditioned at non-zero gate
  - Ontological outputs still produced correctly
  - Stage 2 metadata (gate_value, interp_components) in output
- Null integration test: gate=0 → logits match baseline
- Measurement fields (F.4.7): gate_value, conditioning_norm
"""

import pytest
import torch
import torch.nn as nn

from symbolu.inference.interpretive_conditioner import (
    InterpretiveConditioner,
    InterpretiveConditionerConfig,
    InterpretiveStateBuilder,
    BhavaVectorCompressor,
)


# =============================================================================
# BhavaVectorCompressor
# =============================================================================


class TestBhavaVectorCompressor:
    """Test Bhava matrix compression to compact vector."""

    def test_output_shapes(self):
        comp = BhavaVectorCompressor(bhava_dim=12, output_dim=16)
        bhava = torch.randn(2, 12, 12)
        out = comp(bhava)
        assert out["bhava_vector"].shape == (2, 16)
        assert out["coherence"].shape == (2,)

    def test_coherence_bounded(self):
        """Coherence is sigmoid-bounded in [0, 1]."""
        comp = BhavaVectorCompressor()
        bhava = torch.randn(5, 12, 12) * 10  # Large values
        out = comp(bhava)
        assert (out["coherence"] >= 0).all()
        assert (out["coherence"] <= 1).all()

    def test_flattened_input(self):
        """Accepts pre-flattened 144D input."""
        comp = BhavaVectorCompressor()
        flat = torch.randn(3, 144)
        out = comp(flat)
        assert out["bhava_vector"].shape == (3, 16)

    def test_batch_sequence_input(self):
        """Handles [B, T, 12, 12] input."""
        comp = BhavaVectorCompressor()
        bhava = torch.randn(2, 10, 12, 12)
        out = comp(bhava)
        assert out["bhava_vector"].shape == (2, 10, 16)
        assert out["coherence"].shape == (2, 10)

    def test_deterministic(self):
        """Same input produces same output."""
        comp = BhavaVectorCompressor()
        comp.eval()
        bhava = torch.randn(1, 12, 12)
        out1 = comp(bhava)
        out2 = comp(bhava)
        assert torch.allclose(out1["bhava_vector"], out2["bhava_vector"])

    def test_custom_output_dim(self):
        comp = BhavaVectorCompressor(bhava_dim=12, output_dim=32)
        bhava = torch.randn(1, 12, 12)
        out = comp(bhava)
        assert out["bhava_vector"].shape == (1, 32)


# =============================================================================
# InterpretiveConditionerConfig
# =============================================================================


class TestInterpretiveConditionerConfig:

    def test_defaults(self):
        cfg = InterpretiveConditionerConfig()
        assert cfg.d_synthesis == 64
        assert cfg.gate_init == 0.0
        assert cfg.enable is True
        assert cfg.csr_dim == 16
        assert cfg.vritti_classes == 5
        assert cfg.kosha_primitives == 6
        assert cfg.bhava_output_dim == 16
        assert cfg.bhava_input_dim == 144
        assert cfg.onto_dim == 12

    def test_custom(self):
        cfg = InterpretiveConditionerConfig(d_synthesis=128, gate_init=0.5, enable=False)
        assert cfg.d_synthesis == 128
        assert cfg.gate_init == 0.5
        assert cfg.enable is False


# =============================================================================
# InterpretiveStateBuilder
# =============================================================================


class TestInterpretiveStateBuilder:
    """Test interpretive state construction from auxiliary signals."""

    @pytest.fixture
    def builder(self):
        cfg = InterpretiveConditionerConfig()
        return InterpretiveStateBuilder(hidden_dim=64, config=cfg)

    def test_interp_dim(self, builder):
        """Total interp_dim = csr(16) + vritti(5) + kosha(6) + bhava(16) = 43."""
        assert builder.interp_dim == 43

    def test_output_shape(self, builder):
        hidden = torch.randn(2, 10, 64)
        onto = torch.randn(2, 10, 12)
        bhava = torch.randn(2, 12, 12)
        out = builder(hidden, onto, bhava)
        assert out["interpretive_state"].shape == (2, 10, 43)

    def test_components_present(self, builder):
        hidden = torch.randn(1, 5, 64)
        onto = torch.randn(1, 5, 12)
        bhava = torch.randn(1, 12, 12)
        out = builder(hidden, onto, bhava)
        comps = out["components"]
        assert "r_ctx" in comps
        assert "v_ctx" in comps
        assert "alpha_t" in comps
        assert "b_t" in comps
        assert "bhava_coherence" in comps

    def test_component_shapes(self, builder):
        hidden = torch.randn(2, 10, 64)
        onto = torch.randn(2, 10, 12)
        bhava = torch.randn(2, 12, 12)
        out = builder(hidden, onto, bhava)
        comps = out["components"]
        assert comps["r_ctx"].shape == (2, 10, 16)
        assert comps["v_ctx"].shape == (2, 10, 5)
        assert comps["alpha_t"].shape == (2, 10, 6)
        assert comps["b_t"].shape == (2, 10, 16)

    def test_vritti_is_simplex(self, builder):
        """Vritti output sums to 1 (softmax normalized)."""
        hidden = torch.randn(1, 5, 64)
        onto = torch.randn(1, 5, 12)
        bhava = torch.randn(1, 12, 12)
        out = builder(hidden, onto, bhava)
        v_ctx = out["components"]["v_ctx"]
        sums = v_ctx.sum(dim=-1)
        assert torch.allclose(sums, torch.ones_like(sums), atol=1e-5)

    def test_kosha_is_simplex(self, builder):
        """Kosha routing sums to 1 (softmax normalized)."""
        hidden = torch.randn(1, 5, 64)
        onto = torch.randn(1, 5, 12)
        bhava = torch.randn(1, 12, 12)
        out = builder(hidden, onto, bhava)
        alpha = out["components"]["alpha_t"]
        sums = alpha.sum(dim=-1)
        assert torch.allclose(sums, torch.ones_like(sums), atol=1e-5)

    def test_deterministic(self, builder):
        builder.eval()
        hidden = torch.randn(1, 3, 64)
        onto = torch.randn(1, 3, 12)
        bhava = torch.randn(1, 12, 12)
        out1 = builder(hidden, onto, bhava)
        out2 = builder(hidden, onto, bhava)
        assert torch.allclose(
            out1["interpretive_state"], out2["interpretive_state"]
        )


# =============================================================================
# InterpretiveConditioner
# =============================================================================


class TestInterpretiveConditioner:
    """Test gated residual conditioning."""

    @pytest.fixture
    def conditioner(self):
        cfg = InterpretiveConditionerConfig()
        return InterpretiveConditioner(cfg, hidden_dim=64, interp_dim=43)

    def test_zero_gate_cold_start(self, conditioner):
        """At initialization, conditioning output equals input exactly.

        Gate is 0.0 → sigmoid(0)=0.5, but final linear layer is zero-init,
        so conditioning vector is all zeros, and output = hidden + 0.5 * 0 = hidden.
        """
        conditioner.eval()
        hidden = torch.randn(2, 10, 64)
        interp = torch.randn(2, 10, 43)
        out = conditioner(hidden, interp)
        assert torch.allclose(out, hidden, atol=1e-6)

    def test_disabled_returns_unchanged(self):
        """When enable=False, output == hidden regardless of gate."""
        cfg = InterpretiveConditionerConfig(enable=False, gate_init=5.0)
        conditioner = InterpretiveConditioner(cfg, hidden_dim=64, interp_dim=43)
        # Manually set weights to non-zero to prove enable disables
        with torch.no_grad():
            conditioner.synthesis[-1].weight.fill_(1.0)
        conditioner.eval()
        hidden = torch.randn(2, 5, 64)
        interp = torch.randn(2, 5, 43)
        out = conditioner(hidden, interp)
        assert torch.allclose(out, hidden)

    def test_nonzero_weights_changes_output(self):
        """After training (non-zero weights), output differs from input."""
        cfg = InterpretiveConditionerConfig(gate_init=2.0)
        conditioner = InterpretiveConditioner(cfg, hidden_dim=64, interp_dim=43)
        # Set non-zero weights to simulate training
        with torch.no_grad():
            conditioner.synthesis[-1].weight.normal_(0, 0.1)
            conditioner.synthesis[-1].bias.normal_(0, 0.1)
        conditioner.eval()
        hidden = torch.randn(2, 5, 64)
        interp = torch.randn(2, 5, 43)
        out = conditioner(hidden, interp)
        assert not torch.allclose(out, hidden, atol=1e-4)

    def test_gate_value_property(self, conditioner):
        """gate_value returns sigmoid of gate parameter."""
        expected = torch.sigmoid(conditioner.gate).item()
        assert abs(conditioner.gate_value - expected) < 1e-6

    def test_synthesis_final_layer_zero_init(self, conditioner):
        """Final linear layer of synthesis MLP is zero-initialized."""
        final = conditioner.synthesis[-1]
        assert torch.allclose(final.weight, torch.zeros_like(final.weight))
        assert torch.allclose(final.bias, torch.zeros_like(final.bias))

    def test_output_shape(self, conditioner):
        hidden = torch.randn(2, 10, 64)
        interp = torch.randn(2, 10, 43)
        out = conditioner(hidden, interp)
        assert out.shape == hidden.shape

    def test_gate_gradient_flows(self):
        """Gate parameter receives gradients during training."""
        cfg = InterpretiveConditionerConfig(gate_init=0.0)
        conditioner = InterpretiveConditioner(cfg, hidden_dim=32, interp_dim=20)
        # Give non-zero weights so conditioning is non-zero
        with torch.no_grad():
            conditioner.synthesis[-1].weight.normal_(0, 0.1)
        hidden = torch.randn(1, 3, 32, requires_grad=True)
        interp = torch.randn(1, 3, 20)
        out = conditioner(hidden, interp)
        loss = out.sum()
        loss.backward()
        assert conditioner.gate.grad is not None
        assert conditioner.gate.grad.abs() > 0


# =============================================================================
# Integration with SymbolU12LLM
# =============================================================================


class TestSymbolU12Integration:
    """Test Stage 2 integration into SymbolU12LLM forward()."""

    @pytest.fixture
    def model(self):
        from symbolu.ontological.symbolu12_llm import SymbolU12LLM
        return SymbolU12LLM(
            vocab_size=256,
            embed_dim=64,
            num_layers=2,
            num_heads=4,
            max_seq_len=128,
        )

    def test_forward_without_conditioner(self, model):
        """Without conditioner, forward() behaves as before."""
        model.eval()
        ids = torch.randint(0, 256, (1, 10))
        out = model(ids, return_ontological=True)
        assert "logits" in out
        assert "ontological" in out
        assert "coherence" in out
        assert "gate_value" not in out

    def test_forward_with_conditioner(self, model):
        """With conditioner, forward() produces conditioned logits + metadata."""
        cfg = InterpretiveConditionerConfig(onto_dim=12)
        builder = InterpretiveStateBuilder(hidden_dim=64, config=cfg)
        conditioner = InterpretiveConditioner(cfg, hidden_dim=64, interp_dim=builder.interp_dim)
        model.attach_interpretive_conditioner(builder, conditioner)
        model.eval()
        ids = torch.randint(0, 256, (1, 10))
        out = model(ids, return_ontological=True)
        assert "logits" in out
        assert "ontological" in out
        assert "gate_value" in out
        assert "interp_components" in out

    def test_null_integration_zero_gate(self, model):
        """At gate=0 with zero-init, conditioned logits match unconditioned."""
        model.eval()
        ids = torch.randint(0, 256, (1, 8))

        # Baseline (no conditioner)
        torch.manual_seed(42)
        baseline_out = model(ids, return_ontological=True)
        baseline_logits = baseline_out["logits"].clone()

        # With conditioner at zero-init
        cfg = InterpretiveConditionerConfig(onto_dim=12)
        builder = InterpretiveStateBuilder(hidden_dim=64, config=cfg)
        conditioner = InterpretiveConditioner(cfg, hidden_dim=64, interp_dim=builder.interp_dim)
        model.attach_interpretive_conditioner(builder, conditioner)

        torch.manual_seed(42)
        conditioned_out = model(ids, return_ontological=True)
        conditioned_logits = conditioned_out["logits"]

        assert torch.allclose(baseline_logits, conditioned_logits, atol=1e-5)

    def test_nonzero_gate_changes_logits(self, model):
        """With non-zero conditioning, logits change from baseline."""
        model.eval()
        ids = torch.randint(0, 256, (1, 8))

        # Baseline
        baseline_logits = model(ids, return_ontological=True)["logits"].clone()

        # Attach conditioner with non-zero weights
        cfg = InterpretiveConditionerConfig(onto_dim=12, gate_init=5.0)
        builder = InterpretiveStateBuilder(hidden_dim=64, config=cfg)
        conditioner = InterpretiveConditioner(cfg, hidden_dim=64, interp_dim=builder.interp_dim)
        with torch.no_grad():
            conditioner.synthesis[-1].weight.normal_(0, 0.5)
            conditioner.synthesis[-1].bias.normal_(0, 0.5)
        model.attach_interpretive_conditioner(builder, conditioner)

        conditioned_logits = model(ids, return_ontological=True)["logits"]

        assert not torch.allclose(baseline_logits, conditioned_logits, atol=1e-3)

    def test_ontological_outputs_still_correct(self, model):
        """Ontological outputs are still produced when conditioner is active."""
        cfg = InterpretiveConditionerConfig(onto_dim=12)
        builder = InterpretiveStateBuilder(hidden_dim=64, config=cfg)
        conditioner = InterpretiveConditioner(cfg, hidden_dim=64, interp_dim=builder.interp_dim)
        model.attach_interpretive_conditioner(builder, conditioner)
        model.eval()
        ids = torch.randint(0, 256, (1, 6))
        out = model(ids, return_ontological=True)
        assert out["ontological"].shape == (1, 6, 12)
        assert "bhava" in out
        assert "coherence" in out
        assert "relationship_matrix" in out

    def test_forward_without_ontological_flag(self, model):
        """With conditioner but return_ontological=False, ontological is still
        computed (needed for conditioning) but not returned."""
        cfg = InterpretiveConditionerConfig(onto_dim=12)
        builder = InterpretiveStateBuilder(hidden_dim=64, config=cfg)
        conditioner = InterpretiveConditioner(cfg, hidden_dim=64, interp_dim=builder.interp_dim)
        model.attach_interpretive_conditioner(builder, conditioner)
        model.eval()
        ids = torch.randint(0, 256, (1, 6))
        out = model(ids, return_ontological=False)
        # Ontological NOT in output (flag is False)
        assert "ontological" not in out
        # But conditioner metadata IS in output
        assert "gate_value" in out

    def test_detach_conditioner(self, model):
        """Setting conditioner to None restores original behavior."""
        cfg = InterpretiveConditionerConfig(onto_dim=12, gate_init=5.0)
        builder = InterpretiveStateBuilder(hidden_dim=64, config=cfg)
        conditioner = InterpretiveConditioner(cfg, hidden_dim=64, interp_dim=builder.interp_dim)
        with torch.no_grad():
            conditioner.synthesis[-1].weight.normal_(0, 0.5)
        model.attach_interpretive_conditioner(builder, conditioner)

        model.eval()
        ids = torch.randint(0, 256, (1, 6))

        out_with = model(ids)
        assert "gate_value" in out_with

        model.attach_interpretive_conditioner(None, None)
        out_without = model(ids)
        assert "gate_value" not in out_without


# =============================================================================
# Measurement Fields (F.4.7)
# =============================================================================


class TestMeasurementFields:
    """Verify Stage 2 measurement fields are computed correctly."""

    def test_gate_value_in_output(self):
        from symbolu.ontological.symbolu12_llm import SymbolU12LLM
        model = SymbolU12LLM(vocab_size=256, embed_dim=64, num_layers=2, num_heads=4)
        cfg = InterpretiveConditionerConfig(onto_dim=12)
        builder = InterpretiveStateBuilder(hidden_dim=64, config=cfg)
        conditioner = InterpretiveConditioner(cfg, hidden_dim=64, interp_dim=builder.interp_dim)
        model.attach_interpretive_conditioner(builder, conditioner)
        model.eval()
        out = model(torch.randint(0, 256, (1, 5)))
        assert isinstance(out["gate_value"], float)
        # Default gate=0 → sigmoid(0) = 0.5
        assert abs(out["gate_value"] - 0.5) < 1e-4

    def test_interp_components_structure(self):
        from symbolu.ontological.symbolu12_llm import SymbolU12LLM
        model = SymbolU12LLM(vocab_size=256, embed_dim=64, num_layers=2, num_heads=4)
        cfg = InterpretiveConditionerConfig(onto_dim=12)
        builder = InterpretiveStateBuilder(hidden_dim=64, config=cfg)
        conditioner = InterpretiveConditioner(cfg, hidden_dim=64, interp_dim=builder.interp_dim)
        model.attach_interpretive_conditioner(builder, conditioner)
        model.eval()
        out = model(torch.randint(0, 256, (1, 5)))
        comps = out["interp_components"]
        assert "r_ctx" in comps
        assert "v_ctx" in comps
        assert "alpha_t" in comps
        assert "b_t" in comps
        assert "bhava_coherence" in comps


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:

    def test_single_token_input(self):
        """Works with single-token sequences."""
        cfg = InterpretiveConditionerConfig()
        builder = InterpretiveStateBuilder(hidden_dim=64, config=cfg)
        hidden = torch.randn(1, 1, 64)
        onto = torch.randn(1, 1, 12)
        bhava = torch.randn(1, 12, 12)
        out = builder(hidden, onto, bhava)
        assert out["interpretive_state"].shape == (1, 1, 43)

    def test_large_batch(self):
        """Works with larger batch sizes."""
        cfg = InterpretiveConditionerConfig()
        builder = InterpretiveStateBuilder(hidden_dim=64, config=cfg)
        conditioner = InterpretiveConditioner(cfg, hidden_dim=64, interp_dim=builder.interp_dim)
        hidden = torch.randn(8, 20, 64)
        onto = torch.randn(8, 20, 12)
        bhava = torch.randn(8, 12, 12)
        builder_out = builder(hidden, onto, bhava)
        result = conditioner(hidden, builder_out["interpretive_state"])
        assert result.shape == (8, 20, 64)

    def test_gradient_flow_through_full_pipeline(self):
        """Gradients flow through builder → conditioner → loss."""
        cfg = InterpretiveConditionerConfig()
        builder = InterpretiveStateBuilder(hidden_dim=32, config=cfg)
        conditioner = InterpretiveConditioner(cfg, hidden_dim=32, interp_dim=builder.interp_dim)

        hidden = torch.randn(1, 3, 32, requires_grad=True)
        onto = torch.randn(1, 3, 12, requires_grad=True)
        bhava = torch.randn(1, 12, 12, requires_grad=True)

        builder_out = builder(hidden, onto, bhava)
        result = conditioner(hidden, builder_out["interpretive_state"])
        loss = result.sum()
        loss.backward()

        assert hidden.grad is not None
        assert onto.grad is not None
        assert bhava.grad is not None
