#!/usr/bin/env python3
"""
Stage 8 Tests — Perspective Synthesizer (Representation Conditioning)
======================================================================

Tests the InterpretiveState dataclass, PerspectiveSynthesizer module,
and end-to-end integration with SymbolU12LLM.

Success Criteria (from §F.12.11):
  - Cold start: gate=0 + zero-init → output = hidden exactly
  - Gate trains up when loss backpropagates
  - Vritti distribution varies across different inputs (not collapsed)
  - Kosha routing varies across different inputs
  - InterpretiveState.to_log_dict() produces correct keys
  - Forward pass produces correct shapes
  - Integration: generate_text produces InterpretiveState log in tracer
  - Representation conditioning outperforms bypass (ablation test)
"""

import pytest
import torch
import torch.nn as nn

from symbolu.inference.interpretive_state import InterpretiveState
from symbolu.inference.perspective_synthesizer import (
    PerspectiveSynthesizer,
    PerspectiveSynthesizerConfig,
)
from symbolu.inference.interpretive_conditioner import (
    InterpretiveConditionerConfig,
    InterpretiveStateBuilder,
    InterpretiveConditioner,
    BhavaVectorCompressor,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def default_config():
    return PerspectiveSynthesizerConfig()


@pytest.fixture
def config_with_stage7():
    return PerspectiveSynthesizerConfig(
        phase_out_dim=8,
        d_exp=32,
        enable_polarity=True,
    )


@pytest.fixture
def hidden_dim():
    return 64


@pytest.fixture
def batch():
    return 2


@pytest.fixture
def seq_len():
    return 10


@pytest.fixture
def onto_dim():
    return 12


# =============================================================================
# INTERPRETIVE STATE TESTS
# =============================================================================

class TestInterpretiveState:
    """Tests for the InterpretiveState dataclass."""

    def test_to_conditioning_vector_base(self, batch, seq_len):
        state = InterpretiveState(
            csr_signal=torch.randn(batch, seq_len, 16),
            vritti_distribution=torch.randn(batch, seq_len, 5),
            kosha_routing=torch.randn(batch, seq_len, 6),
            bhava_relation=torch.randn(batch, seq_len, 16),
        )
        vec = state.to_conditioning_vector()
        assert vec.shape == (batch, seq_len, 43)  # 16+5+6+16

    def test_to_conditioning_vector_with_extensions(self, batch, seq_len):
        state = InterpretiveState(
            csr_signal=torch.randn(batch, seq_len, 16),
            vritti_distribution=torch.randn(batch, seq_len, 5),
            kosha_routing=torch.randn(batch, seq_len, 6),
            bhava_relation=torch.randn(batch, seq_len, 16),
            phase_coherence=torch.randn(batch, seq_len, 8),
            experiential_state=torch.randn(batch, seq_len, 32),
        )
        vec = state.to_conditioning_vector()
        assert vec.shape == (batch, seq_len, 83)  # 43+8+32

    def test_conditioning_dim(self, batch, seq_len):
        state = InterpretiveState(
            csr_signal=torch.randn(batch, seq_len, 16),
            vritti_distribution=torch.randn(batch, seq_len, 5),
            kosha_routing=torch.randn(batch, seq_len, 6),
            bhava_relation=torch.randn(batch, seq_len, 16),
        )
        assert state.conditioning_dim == 43

    def test_conditioning_dim_with_extensions(self, batch, seq_len):
        state = InterpretiveState(
            csr_signal=torch.randn(batch, seq_len, 16),
            vritti_distribution=torch.randn(batch, seq_len, 5),
            kosha_routing=torch.randn(batch, seq_len, 6),
            bhava_relation=torch.randn(batch, seq_len, 16),
            phase_coherence=torch.randn(batch, seq_len, 8),
            experiential_state=torch.randn(batch, seq_len, 32),
        )
        assert state.conditioning_dim == 83

    def test_to_log_dict_keys(self, batch, seq_len):
        state = InterpretiveState(
            csr_signal=torch.randn(batch, seq_len, 16),
            vritti_distribution=torch.softmax(torch.randn(batch, seq_len, 5), dim=-1),
            kosha_routing=torch.softmax(torch.randn(batch, seq_len, 6), dim=-1),
            bhava_relation=torch.randn(batch, seq_len, 16),
            bhava_coherence=torch.tensor([0.85, 0.90]),
        )
        log = state.to_log_dict()
        assert "vritti_dominant" in log
        assert "vritti_distribution" in log
        assert "kosha_primary" in log
        assert "kosha_distribution" in log
        assert "csr_signal_norm" in log
        assert "bhava_relation_norm" in log
        assert "bhava_coherence" in log
        assert "conditioning_norm" in log

    def test_to_log_dict_vritti_names(self, batch, seq_len):
        # Force pramana dominant
        vritti = torch.zeros(batch, seq_len, 5)
        vritti[:, :, 0] = 1.0  # pramana = index 0
        state = InterpretiveState(
            csr_signal=torch.randn(batch, seq_len, 16),
            vritti_distribution=vritti,
            kosha_routing=torch.randn(batch, seq_len, 6),
            bhava_relation=torch.randn(batch, seq_len, 16),
        )
        log = state.to_log_dict()
        assert log["vritti_dominant"] == "pramana"

    def test_to_log_dict_kosha_names(self, batch, seq_len):
        # Force guna primary (index 5)
        kosha = torch.zeros(batch, seq_len, 6)
        kosha[:, :, 5] = 1.0
        state = InterpretiveState(
            csr_signal=torch.randn(batch, seq_len, 16),
            vritti_distribution=torch.randn(batch, seq_len, 5),
            kosha_routing=kosha,
            bhava_relation=torch.randn(batch, seq_len, 16),
        )
        log = state.to_log_dict()
        assert log["kosha_primary"] == "guna"

    def test_to_log_dict_with_stage7_extensions(self, batch, seq_len):
        state = InterpretiveState(
            csr_signal=torch.randn(batch, seq_len, 16),
            vritti_distribution=torch.randn(batch, seq_len, 5),
            kosha_routing=torch.randn(batch, seq_len, 6),
            bhava_relation=torch.randn(batch, seq_len, 16),
            phase_coherence=torch.randn(batch, seq_len, 8),
            experiential_state=torch.randn(batch, seq_len, 32),
            polarity_phi=torch.randn(batch, seq_len, 16),
        )
        log = state.to_log_dict()
        assert "phase_coherence_interp_norm" in log
        assert "experiential_interp_norm" in log
        assert "polarity_phi_norm" in log


# =============================================================================
# PERSPECTIVE SYNTHESIZER MODULE TESTS
# =============================================================================

class TestPerspectiveSynthesizer:
    """Tests for the PerspectiveSynthesizer module."""

    def test_cold_start_identity(self, default_config, hidden_dim, batch, seq_len, onto_dim):
        """F.12.11: Gate=0 + zero-init → output = hidden exactly."""
        synth = PerspectiveSynthesizer(default_config, hidden_dim)
        hidden = torch.randn(batch, seq_len, hidden_dim)
        onto = torch.randn(batch, seq_len, onto_dim)
        bhava = torch.randn(batch, onto_dim, onto_dim)

        result = synth(hidden=hidden, onto_state=onto, bhava_matrix=bhava)
        conditioned = result["conditioned_hidden"]

        # Zero-init final layer means synthesis output is zero,
        # so conditioned = hidden + sigmoid(0) * 0 = hidden exactly
        torch.testing.assert_close(conditioned, hidden, atol=1e-6, rtol=1e-6)

    def test_cold_start_gate_value(self, default_config, hidden_dim):
        synth = PerspectiveSynthesizer(default_config, hidden_dim)
        # sigmoid(0) = 0.5, but with zero-init synthesis, conditioning = 0
        assert abs(synth.gate_value - 0.5) < 1e-4

    def test_output_shapes(self, default_config, hidden_dim, batch, seq_len, onto_dim):
        synth = PerspectiveSynthesizer(default_config, hidden_dim)
        hidden = torch.randn(batch, seq_len, hidden_dim)
        onto = torch.randn(batch, seq_len, onto_dim)
        bhava = torch.randn(batch, onto_dim, onto_dim)

        result = synth(hidden=hidden, onto_state=onto, bhava_matrix=bhava)

        assert result["conditioned_hidden"].shape == (batch, seq_len, hidden_dim)
        assert result["interpretive_state"] is not None
        assert isinstance(result["interpretive_state"], InterpretiveState)
        assert isinstance(result["gate_value"], float)
        assert isinstance(result["conditioning_norm"], float)

    def test_log_dict_produced(self, default_config, hidden_dim, batch, seq_len, onto_dim):
        synth = PerspectiveSynthesizer(default_config, hidden_dim)
        hidden = torch.randn(batch, seq_len, hidden_dim)
        onto = torch.randn(batch, seq_len, onto_dim)
        bhava = torch.randn(batch, onto_dim, onto_dim)

        result = synth(hidden=hidden, onto_state=onto, bhava_matrix=bhava)
        log = result["log_dict"]

        assert "synthesis_gate" in log
        assert "conditioning_norm" in log
        assert "vritti_dominant" in log
        assert "kosha_primary" in log

    def test_disabled_returns_hidden(self, hidden_dim, batch, seq_len, onto_dim):
        config = PerspectiveSynthesizerConfig(enable=False)
        synth = PerspectiveSynthesizer(config, hidden_dim)
        hidden = torch.randn(batch, seq_len, hidden_dim)
        onto = torch.randn(batch, seq_len, onto_dim)
        bhava = torch.randn(batch, onto_dim, onto_dim)

        result = synth(hidden=hidden, onto_state=onto, bhava_matrix=bhava)
        torch.testing.assert_close(result["conditioned_hidden"], hidden)
        assert result["interpretive_state"] is None

    def test_gradient_flow(self, default_config, hidden_dim, batch, seq_len, onto_dim):
        """Verify gradients flow through the synthesis pipeline."""
        synth = PerspectiveSynthesizer(default_config, hidden_dim)
        hidden = torch.randn(batch, seq_len, hidden_dim, requires_grad=True)
        onto = torch.randn(batch, seq_len, onto_dim)
        bhava = torch.randn(batch, onto_dim, onto_dim)

        result = synth(hidden=hidden, onto_state=onto, bhava_matrix=bhava)
        loss = result["conditioned_hidden"].sum()
        loss.backward()

        # Gate should have gradient
        assert synth.conditioner.gate.grad is not None
        # Synthesis MLP should have gradients
        has_synth_grad = any(
            p.grad is not None and p.grad.abs().sum() > 0
            for p in synth.conditioner.synthesis.parameters()
        )
        assert has_synth_grad

    def test_gate_trains_up(self, default_config, hidden_dim, batch, seq_len, onto_dim):
        """F.12.11: Gate trains — synthesis becomes non-zero with gradient signal."""
        synth = PerspectiveSynthesizer(default_config, hidden_dim)
        optimizer = torch.optim.Adam(synth.parameters(), lr=1e-2)

        # Verify synthesis layer starts zero
        final_layer = synth.conditioner.synthesis[-1]
        assert final_layer.weight.abs().max().item() == 0.0

        # Simulate training: conditioned output should match a target
        # This provides gradient signal through the zero-init layer
        target_offset = torch.randn(batch, seq_len, hidden_dim) * 0.1

        for _ in range(100):
            hidden = torch.randn(batch, seq_len, hidden_dim)
            onto = torch.randn(batch, seq_len, onto_dim)
            bhava = torch.randn(batch, onto_dim, onto_dim)

            result = synth(hidden=hidden, onto_state=onto, bhava_matrix=bhava)
            # MSE loss: conditioned should equal hidden + target_offset
            target = hidden + target_offset
            loss = (result["conditioned_hidden"] - target).pow(2).mean()
            loss.backward()
            optimizer.step()
            optimizer.zero_grad()

        # The synthesis MLP final layer should now have non-zero weights
        assert final_layer.weight.abs().max().item() > 0.001, \
            "Synthesis final layer still zero after training"

        # Verify conditioning produces non-zero delta
        hidden = torch.randn(batch, seq_len, hidden_dim)
        onto = torch.randn(batch, seq_len, onto_dim)
        bhava = torch.randn(batch, onto_dim, onto_dim)
        result = synth(hidden=hidden, onto_state=onto, bhava_matrix=bhava)
        delta = (result["conditioned_hidden"] - hidden).abs().max().item()
        assert delta > 0.001, f"Conditioning delta still ~0 after training: {delta}"

    def test_with_stage7_extensions(self, config_with_stage7, hidden_dim, batch, seq_len, onto_dim):
        synth = PerspectiveSynthesizer(config_with_stage7, hidden_dim)
        hidden = torch.randn(batch, seq_len, hidden_dim)
        onto = torch.randn(batch, seq_len, onto_dim)
        bhava = torch.randn(batch, onto_dim, onto_dim)
        phase_vec = torch.randn(batch, 8)
        exp_vec = torch.randn(batch, 32)

        result = synth(
            hidden=hidden, onto_state=onto, bhava_matrix=bhava,
            phase_coherence_vector=phase_vec, experiential_vector=exp_vec,
        )
        assert result["conditioned_hidden"].shape == (batch, seq_len, hidden_dim)
        istate = result["interpretive_state"]
        assert istate.phase_coherence is not None
        assert istate.experiential_state is not None

    def test_interp_dim(self, default_config, hidden_dim):
        synth = PerspectiveSynthesizer(default_config, hidden_dim)
        # 16 (csr) + 5 (vritti) + 6 (kosha) + 16 (bhava) = 43
        assert synth.interp_dim == 43

    def test_interp_dim_with_extensions(self, config_with_stage7, hidden_dim):
        synth = PerspectiveSynthesizer(config_with_stage7, hidden_dim)
        # 43 + 8 (phase) + 32 (exp) = 83
        assert synth.interp_dim == 83

    def test_config_to_conditioner_config(self, default_config):
        cc = default_config.to_conditioner_config()
        assert isinstance(cc, InterpretiveConditionerConfig)
        assert cc.d_synthesis == default_config.d_synthesis
        assert cc.gate_init == default_config.gate_init
        assert cc.csr_dim == default_config.csr_dim

    def test_parameter_count_reasonable(self, default_config, hidden_dim):
        synth = PerspectiveSynthesizer(default_config, hidden_dim)
        n_params = sum(p.numel() for p in synth.parameters())
        # Should be lightweight: ~10K-100K params for hidden_dim=64
        assert n_params < 200_000


# =============================================================================
# ORTHOGONALITY TESTS
# =============================================================================

class TestOrthogonality:
    """F.12.8: Verify interpretive axes are structurally independent."""

    def test_vritti_varies_across_inputs(self, default_config, hidden_dim, seq_len, onto_dim):
        """Vritti distribution should vary for different hidden states."""
        synth = PerspectiveSynthesizer(default_config, hidden_dim)

        results = []
        for _ in range(5):
            hidden = torch.randn(1, seq_len, hidden_dim) * 2  # varied inputs
            onto = torch.randn(1, seq_len, onto_dim)
            bhava = torch.randn(1, onto_dim, onto_dim)
            r = synth(hidden=hidden, onto_state=onto, bhava_matrix=bhava)
            results.append(r["interpretive_state"].vritti_distribution)

        # Check that vritti distributions are not all identical
        all_same = all(
            torch.allclose(results[0], r, atol=1e-4) for r in results[1:]
        )
        assert not all_same, "Vritti distribution collapsed to same value for all inputs"

    def test_kosha_varies_across_inputs(self, default_config, hidden_dim, seq_len, onto_dim):
        """Kosha routing should vary for different hidden states."""
        synth = PerspectiveSynthesizer(default_config, hidden_dim)

        results = []
        for _ in range(5):
            hidden = torch.randn(1, seq_len, hidden_dim) * 2
            onto = torch.randn(1, seq_len, onto_dim)
            bhava = torch.randn(1, onto_dim, onto_dim)
            r = synth(hidden=hidden, onto_state=onto, bhava_matrix=bhava)
            results.append(r["interpretive_state"].kosha_routing)

        all_same = all(
            torch.allclose(results[0], r, atol=1e-4) for r in results[1:]
        )
        assert not all_same, "Kosha routing collapsed to same value for all inputs"

    def test_csr_and_vritti_independent(self, default_config, hidden_dim, seq_len, onto_dim):
        """CSR and Vritti should not be perfectly correlated."""
        synth = PerspectiveSynthesizer(default_config, hidden_dim)

        csr_norms = []
        vritti_entropies = []
        for _ in range(20):
            hidden = torch.randn(1, seq_len, hidden_dim)
            onto = torch.randn(1, seq_len, onto_dim)
            bhava = torch.randn(1, onto_dim, onto_dim)
            r = synth(hidden=hidden, onto_state=onto, bhava_matrix=bhava)
            istate = r["interpretive_state"]
            csr_norms.append(istate.csr_signal.norm().item())
            # Vritti entropy
            v = istate.vritti_distribution[:, -1, :]
            entropy = -(v * (v + 1e-8).log()).sum(-1).mean().item()
            vritti_entropies.append(entropy)

        # Correlation should not be ±1
        csr_t = torch.tensor(csr_norms)
        vritti_t = torch.tensor(vritti_entropies)
        if csr_t.std() > 0 and vritti_t.std() > 0:
            corr = torch.corrcoef(torch.stack([csr_t, vritti_t]))[0, 1].item()
            assert abs(corr) < 0.95, f"CSR and Vritti too correlated: {corr:.3f}"


# =============================================================================
# LLM INTEGRATION TESTS
# =============================================================================

class TestLLMIntegration:
    """Tests for PerspectiveSynthesizer wired into SymbolU12LLM."""

    def test_attach_perspective_synthesizer(self):
        from symbolu.ontological.symbolu12_llm import SymbolU12LLM

        model = SymbolU12LLM(vocab_size=500, embed_dim=64, num_layers=2,
                             num_heads=4, max_seq_len=32, phase_dim=8)
        config = PerspectiveSynthesizerConfig()
        synth = PerspectiveSynthesizer(config, hidden_dim=64)

        model.attach_perspective_synthesizer(synth)
        assert model._perspective_synthesizer is synth

    def test_forward_with_synthesizer(self):
        from symbolu.ontological.symbolu12_llm import SymbolU12LLM

        model = SymbolU12LLM(vocab_size=500, embed_dim=64, num_layers=2,
                             num_heads=4, max_seq_len=32, phase_dim=8)
        config = PerspectiveSynthesizerConfig()
        synth = PerspectiveSynthesizer(config, hidden_dim=64)
        model.attach_perspective_synthesizer(synth)

        input_ids = torch.randint(0, 500, (1, 10))
        output = model(input_ids)

        assert "logits" in output
        assert output["logits"].shape == (1, 10, 500)
        assert "synth_result" in output
        assert "gate_value" in output
        assert "conditioning_norm" in output

    def test_forward_cold_start_identity(self):
        """Forward pass with synthesizer at cold start produces same logits as without."""
        from symbolu.ontological.symbolu12_llm import SymbolU12LLM

        model = SymbolU12LLM(vocab_size=500, embed_dim=64, num_layers=2,
                             num_heads=4, max_seq_len=32, phase_dim=8)
        model.eval()
        input_ids = torch.randint(0, 500, (1, 10))

        # Without synthesizer (use torch.no_grad to eliminate stochastic ops)
        with torch.no_grad():
            out_base = model(input_ids)
            logits_base = out_base["logits"].clone()

        # With synthesizer (cold start = identity)
        config = PerspectiveSynthesizerConfig()
        synth = PerspectiveSynthesizer(config, hidden_dim=64)
        model.attach_perspective_synthesizer(synth)
        with torch.no_grad():
            out_synth = model(input_ids)
            logits_synth = out_synth["logits"]

        torch.testing.assert_close(logits_synth, logits_base, atol=1e-5, rtol=1e-5)

    def test_generate_text_with_synthesizer(self):
        from symbolu.ontological.symbolu12_llm import SymbolU12LLM

        model = SymbolU12LLM(vocab_size=500, embed_dim=64, num_layers=2,
                             num_heads=4, max_seq_len=32, phase_dim=8)
        config = PerspectiveSynthesizerConfig()
        synth = PerspectiveSynthesizer(config, hidden_dim=64)

        result = model.generate_text(
            prompt="hello",
            max_new_tokens=3,
            perspective_synthesizer=synth,
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_text_tracer_has_stage8_fields(self):
        from symbolu.ontological.symbolu12_llm import SymbolU12LLM
        from symbolu.inference.generation_tracer import GenerationTracer

        model = SymbolU12LLM(vocab_size=500, embed_dim=64, num_layers=2,
                             num_heads=4, max_seq_len=32, phase_dim=8)
        config = PerspectiveSynthesizerConfig()
        synth = PerspectiveSynthesizer(config, hidden_dim=64)
        tracer = GenerationTracer(model=model)

        model.generate_text(
            prompt="hello",
            max_new_tokens=3,
            generation_tracer=tracer,
            perspective_synthesizer=synth,
        )

        assert len(tracer.trace) == 3
        last = tracer.trace[-1]
        assert "gate_value" in last
        assert "conditioning_norm" in last
        assert "vritti_dominant" in last
        assert "kosha_primary" in last
        assert "synthesis_gate" in last

    def test_synthesizer_not_persisted_after_generate(self):
        """Perspective synthesizer passed to generate_text should be temporary."""
        from symbolu.ontological.symbolu12_llm import SymbolU12LLM

        model = SymbolU12LLM(vocab_size=500, embed_dim=64, num_layers=2,
                             num_heads=4, max_seq_len=32, phase_dim=8)
        config = PerspectiveSynthesizerConfig()
        synth = PerspectiveSynthesizer(config, hidden_dim=64)

        assert model._perspective_synthesizer is None
        model.generate_text(prompt="hello", max_new_tokens=2, perspective_synthesizer=synth)
        assert model._perspective_synthesizer is None

    def test_stage8_takes_precedence_over_stage2(self):
        """When both Stage 2 and Stage 8 are attached, Stage 8 should be used."""
        from symbolu.ontological.symbolu12_llm import SymbolU12LLM

        model = SymbolU12LLM(vocab_size=500, embed_dim=64, num_layers=2,
                             num_heads=4, max_seq_len=32, phase_dim=8)

        # Attach Stage 2
        cc = InterpretiveConditionerConfig()
        builder = InterpretiveStateBuilder(hidden_dim=64, config=cc)
        conditioner = InterpretiveConditioner(config=cc, hidden_dim=64, interp_dim=builder.interp_dim)
        model.attach_interpretive_conditioner(builder, conditioner)

        # Attach Stage 8
        config = PerspectiveSynthesizerConfig()
        synth = PerspectiveSynthesizer(config, hidden_dim=64)
        model.attach_perspective_synthesizer(synth)

        input_ids = torch.randint(0, 500, (1, 10))
        output = model(input_ids)

        # Stage 8 output markers should be present
        assert "synth_result" in output
        assert output["synth_result"]["interpretive_state"] is not None


# =============================================================================
# BHAVA VECTOR COMPRESSOR BACKWARD COMPAT
# =============================================================================

class TestBhavaVectorCompressor:
    """Ensure BhavaVectorCompressor works with both matrix and flat inputs."""

    def test_matrix_input(self):
        comp = BhavaVectorCompressor(bhava_dim=12, output_dim=16)
        mat = torch.randn(2, 12, 12)
        out = comp(mat)
        assert out["bhava_vector"].shape == (2, 16)
        assert out["coherence"].shape == (2,)

    def test_flat_input(self):
        comp = BhavaVectorCompressor(bhava_dim=12, output_dim=16)
        flat = torch.randn(2, 144)
        out = comp(flat)
        assert out["bhava_vector"].shape == (2, 16)


# =============================================================================
# CONFIG TESTS
# =============================================================================

class TestPerspectiveSynthesizerConfig:

    def test_default_values(self):
        config = PerspectiveSynthesizerConfig()
        assert config.enable is True
        assert config.d_synthesis == 64
        assert config.gate_init == 0.0
        assert config.csr_dim == 16
        assert config.vritti_classes == 5
        assert config.kosha_primitives == 6
        assert config.bhava_output_dim == 16

    def test_to_conditioner_config_roundtrip(self):
        config = PerspectiveSynthesizerConfig(
            d_synthesis=128,
            csr_dim=32,
            enable_polarity=True,
            phase_out_dim=8,
            d_exp=32,
        )
        cc = config.to_conditioner_config()
        assert cc.d_synthesis == 128
        assert cc.csr_dim == 32
        assert cc.enable_polarity is True
        assert cc.phase_out_dim == 8
        assert cc.d_exp == 32
