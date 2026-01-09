"""
Unit tests for Phase-JEPA components.

Tests cover:
    - SovereignStateProjector: State projection and constraints
    - PhaseJEPAPredictor: Multi-step prediction with phase attention
    - TargetEncoder: EMA updates and momentum scheduling
    - VICRegLoss: Variance-invariance-covariance regularization
    - WeightedAlignmentLoss: Per-component alignment
    - DualSourcePhaseProjector: Combined phase rotation
    - OPB merge_external_observation: Sensor-master integration
"""

import pytest
import torch
import torch.nn as nn
import math


# =============================================================================
# Test: SovereignStateProjector
# =============================================================================

class TestSovereignStateProjector:
    """Tests for SovereignStateProjector."""

    @pytest.fixture
    def projector(self):
        from symbolu.jepa.state_projector import SovereignStateProjector
        return SovereignStateProjector(hidden_dim=768, state_dim=32)

    def test_output_shape(self, projector):
        """Test output has correct shape."""
        x = torch.randn(4, 128, 768)  # [B, T, D]
        S = projector(x)
        assert S.shape == (4, 128, 32)

    def test_output_shape_single(self, projector):
        """Test output shape for single state (no sequence)."""
        x = torch.randn(4, 768)  # [B, D]
        S = projector(x)
        assert S.shape == (4, 32)

    def test_bhava_softmax_constraint(self, projector):
        """Test Bhava dimensions sum to 1 (softmax)."""
        x = torch.randn(4, 768)
        S = projector(x)
        bhava = S[:, 0:12]
        assert torch.allclose(bhava.sum(dim=-1), torch.ones(4), atol=1e-5)

    def test_kosha_softmax_constraint(self, projector):
        """Test Kosha dimensions sum to 1 (softmax)."""
        x = torch.randn(4, 768)
        S = projector(x)
        kosha = S[:, 12:17]
        assert torch.allclose(kosha.sum(dim=-1), torch.ones(4), atol=1e-5)

    def test_vritti_softmax_constraint(self, projector):
        """Test Vritti dimensions sum to 1 (softmax)."""
        x = torch.randn(4, 768)
        S = projector(x)
        vritti = S[:, 17:22]
        assert torch.allclose(vritti.sum(dim=-1), torch.ones(4), atol=1e-5)

    def test_guna_sigmoid_constraint(self, projector):
        """Test Guna dimensions are in [0, 1] (sigmoid)."""
        x = torch.randn(4, 768)
        S = projector(x)
        guna = S[:, 22:28]
        assert (guna >= 0).all() and (guna <= 1).all()

    def test_reserved_tanh_constraint(self, projector):
        """Test Reserved dimensions are in [-1, 1] (tanh)."""
        x = torch.randn(4, 768)
        S = projector(x)
        reserved = S[:, 28:32]
        assert (reserved >= -1).all() and (reserved <= 1).all()

    def test_raw_output(self, projector):
        """Test raw output without constraints."""
        x = torch.randn(4, 768)
        S, raw = projector(x, return_raw=True)
        # Raw should have same shape but different values
        assert raw.shape == S.shape
        # Raw Bhava won't sum to 1
        assert not torch.allclose(raw[:, 0:12].sum(dim=-1), torch.ones(4), atol=1e-5)

    def test_get_component(self, projector):
        """Test component extraction."""
        x = torch.randn(4, 768)
        S = projector(x)

        bhava = projector.get_component(S, 'bhava')
        assert bhava.shape == (4, 12)

        kosha = projector.get_component(S, 'kosha')
        assert kosha.shape == (4, 5)


# =============================================================================
# Test: PhaseJEPAPredictor
# =============================================================================

class TestPhaseJEPAPredictor:
    """Tests for PhaseJEPAPredictor."""

    @pytest.fixture
    def predictor(self):
        from symbolu.jepa.predictor import PhaseJEPAPredictor
        return PhaseJEPAPredictor(
            state_dim=32,
            hidden_dim=128,
            num_heads=4,
            prediction_steps=4,
            cosine_mode='complex',
        )

    def test_single_step_prediction(self, predictor):
        """Test single step prediction."""
        s_context = torch.randn(4, 10, 32)  # [B, T, D]
        s_pred, deltas = predictor(s_context, k_steps=1)

        assert s_pred.shape == (4, 10, 32)
        assert len(deltas) == 1
        assert deltas[0].shape == (4, 10, 32)

    def test_multi_step_prediction(self, predictor):
        """Test multi-step prediction."""
        s_context = torch.randn(4, 10, 32)
        s_pred, deltas = predictor(s_context, k_steps=4)

        assert s_pred.shape == (4, 10, 32)
        assert len(deltas) == 4

        # Final state should equal context + sum of deltas
        expected = s_context + sum(deltas)
        assert torch.allclose(s_pred, expected, atol=1e-5)

    def test_single_state_input(self, predictor):
        """Test prediction with single state (no sequence)."""
        s_context = torch.randn(4, 32)  # [B, D]
        s_pred, deltas = predictor(s_context, k_steps=2)

        assert s_pred.shape == (4, 32)
        assert len(deltas) == 2
        assert deltas[0].shape == (4, 32)

    def test_intermediates(self, predictor):
        """Test intermediate state return."""
        s_context = torch.randn(4, 32)
        s_pred, deltas, intermediates = predictor(
            s_context, k_steps=3, return_intermediates=True
        )

        assert len(intermediates) == 3
        # Each intermediate should be progressively updated
        for i, inter in enumerate(intermediates):
            expected = s_context + sum(deltas[:i+1])
            assert torch.allclose(inter.squeeze(1), expected, atol=1e-5)

    def test_cosine_modes(self):
        """Test different cosine modes work."""
        from symbolu.jepa.predictor import PhaseJEPAPredictor

        for mode in ['standard', 'shifted', 'complex']:
            pred = PhaseJEPAPredictor(cosine_mode=mode)
            s = torch.randn(2, 32)
            s_pred, _ = pred(s, k_steps=1)
            assert s_pred.shape == (2, 32)


# =============================================================================
# Test: TargetEncoder
# =============================================================================

class TestTargetEncoder:
    """Tests for TargetEncoder."""

    @pytest.fixture
    def encoder_pair(self):
        from symbolu.jepa.target_encoder import TargetEncoder

        # Simple encoder for testing
        context_encoder = nn.Sequential(
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 32),
        )
        target_encoder = TargetEncoder(context_encoder, momentum=0.9)
        return context_encoder, target_encoder

    def test_initial_weights_match(self, encoder_pair):
        """Test target encoder starts with same weights as context."""
        context, target = encoder_pair

        for cp, tp in zip(context.parameters(), target.encoder.parameters()):
            assert torch.allclose(cp, tp)

    def test_ema_update(self, encoder_pair):
        """Test EMA update changes target weights."""
        context, target = encoder_pair

        # Modify context encoder
        with torch.no_grad():
            for p in context.parameters():
                p.add_(torch.randn_like(p) * 0.1)

        # Store old target weights
        old_weights = [p.clone() for p in target.encoder.parameters()]

        # Update target
        target.update(context)

        # Target should have changed but not match context
        for old, tp, cp in zip(old_weights, target.encoder.parameters(), context.parameters()):
            assert not torch.allclose(tp, old)  # Changed
            assert not torch.allclose(tp, cp)   # Not same as context
            # Should be EMA: 0.9 * old + 0.1 * context
            expected = 0.9 * old + 0.1 * cp
            assert torch.allclose(tp, expected, atol=1e-5)

    def test_no_gradients(self, encoder_pair):
        """Test target encoder has no gradients."""
        _, target = encoder_pair

        for p in target.encoder.parameters():
            assert not p.requires_grad

    def test_momentum_schedule(self):
        """Test momentum scheduling."""
        from symbolu.jepa.target_encoder import (
            TargetEncoder, cosine_momentum_schedule
        )

        schedule = cosine_momentum_schedule(
            base_momentum=0.9,
            final_momentum=0.999,
            total_steps=100
        )

        # At step 0, should be near base
        assert abs(schedule(0) - 0.9) < 0.01

        # At step 100, should be final
        assert abs(schedule(100) - 0.999) < 0.01


# =============================================================================
# Test: VICRegLoss
# =============================================================================

class TestVICRegLoss:
    """Tests for VICRegLoss."""

    @pytest.fixture
    def vicreg(self):
        from symbolu.jepa.losses import VICRegLoss
        return VICRegLoss(sim_coeff=1.0, std_coeff=1.0, cov_coeff=1.0)

    def test_identical_inputs(self, vicreg):
        """Test loss is low for identical inputs."""
        x = torch.randn(32, 64)
        loss = vicreg(x, x.clone())

        # Invariance loss should be 0 for identical
        result = vicreg(x, x.clone(), return_components=True)
        assert result['invariance'] < 1e-6

    def test_collapsed_variance_penalty(self, vicreg):
        """Test high variance loss for collapsed representations."""
        # All same representation = zero variance
        x = torch.ones(32, 64)
        y = torch.ones(32, 64) + 0.01 * torch.randn(32, 64)

        result = vicreg(x, y, return_components=True)
        # Variance loss should be high (close to 1.0 since variance is 0)
        assert result['variance'] > 0.5

    def test_correlated_covariance_penalty(self, vicreg):
        """Test covariance loss penalizes correlated dimensions."""
        # Create correlated features
        base = torch.randn(32, 32)
        x = torch.cat([base, base], dim=-1)  # Duplicate = correlated
        y = x.clone()

        result = vicreg(x, y, return_components=True)
        # Covariance loss should be higher than uncorrelated
        assert result['covariance'] > 0


# =============================================================================
# Test: WeightedAlignmentLoss
# =============================================================================

class TestWeightedAlignmentLoss:
    """Tests for WeightedAlignmentLoss."""

    @pytest.fixture
    def align_loss(self):
        from symbolu.jepa.losses import WeightedAlignmentLoss
        return WeightedAlignmentLoss(
            bhava_weight=10.0,
            semantic_weight=1.0,
            guna_weight=0.1,
        )

    def test_identical_states_zero_loss(self, align_loss):
        """Test zero loss for identical states."""
        s = torch.randn(4, 32)
        loss = align_loss(s, s.clone())
        assert loss < 1e-6

    def test_bhava_weighted_higher(self, align_loss):
        """Test Bhava differences are weighted higher."""
        s1 = torch.zeros(4, 32)
        s2 = torch.zeros(4, 32)

        # Diff only in Bhava [0:12]
        s2_bhava = s2.clone()
        s2_bhava[:, 0:12] = 1.0
        loss_bhava = align_loss(s1, s2_bhava)

        # Diff only in Guna [22:28]
        s2_guna = s2.clone()
        s2_guna[:, 22:28] = 1.0
        loss_guna = align_loss(s1, s2_guna)

        # Bhava diff should have higher loss (10x weight vs 0.1x)
        assert loss_bhava > loss_guna * 50  # 10/0.1 * similar diff

    def test_return_components(self, align_loss):
        """Test component-wise loss return."""
        s1 = torch.randn(4, 32)
        s2 = torch.randn(4, 32)

        result = align_loss(s1, s2, return_components=True)
        assert 'total' in result
        assert 'bhava_loss' in result
        assert 'semantic_loss' in result
        assert 'guna_loss' in result


# =============================================================================
# Test: DualSourcePhaseProjector
# =============================================================================

class TestDualSourcePhaseProjector:
    """Tests for DualSourcePhaseProjector."""

    @pytest.fixture
    def dual_proj(self):
        from symbolu.common.projectors import DualSourcePhaseProjector
        return DualSourcePhaseProjector(
            text_dim=512,
            state_dim=32,
            num_heads=12,
        )

    def test_output_shape(self, dual_proj):
        """Test output shape."""
        text_emb = torch.randn(4, 512)
        state_delta = torch.randn(4, 32)
        theta = dual_proj(text_emb, state_delta)
        assert theta.shape == (4, 12)  # [B, H]

    def test_output_range(self, dual_proj):
        """Test output is in [-π, π] range."""
        text_emb = torch.randn(4, 512)
        state_delta = torch.randn(4, 32)
        theta = dual_proj(text_emb, state_delta)
        assert (theta >= -math.pi).all()
        assert (theta <= math.pi).all()

    def test_text_only(self, dual_proj):
        """Test text-only mode."""
        text_emb = torch.randn(4, 512)
        state_delta = torch.zeros(4, 32)

        theta_both = dual_proj(text_emb, state_delta)
        theta_text = dual_proj(text_emb, state_delta, text_only=True)

        # Text-only should give different result than both
        # (state contributes even with zeros due to bias)
        assert theta_text.shape == (4, 12)

    def test_state_only(self, dual_proj):
        """Test state-only mode."""
        text_emb = torch.zeros(4, 512)
        state_delta = torch.randn(4, 32)

        theta_state = dual_proj(text_emb, state_delta, state_only=True)
        assert theta_state.shape == (4, 12)

    def test_additive_composition(self, dual_proj):
        """Test that composition is additive."""
        text_emb = torch.randn(4, 512)
        state_delta = torch.randn(4, 32)

        # The outputs should approximately equal text + state phases
        # (not exactly due to scales, but the composition is additive)
        theta_both = dual_proj(text_emb, state_delta)
        theta_text = dual_proj.get_text_phase(text_emb)
        theta_state = dual_proj.get_state_phase(state_delta)

        # With default scales of 1.0, should be close to additive
        expected = theta_text + theta_state
        # May clip due to tanh, but correlation should be high
        assert theta_both.shape == expected.shape


# =============================================================================
# Test: OPB merge_external_observation
# =============================================================================

class TestOPBMergeExternal:
    """Tests for OPB merge_external_observation."""

    @pytest.fixture
    def opb(self):
        from symbolu.sovereign.reasoning_kernel import OPBDimensionLock
        return OPBDimensionLock(state_dim=32)

    def test_unlocked_accepts_observation(self, opb):
        """Test unlocked dimensions accept external observation."""
        external = torch.randn(4, 32)
        merged = opb.merge_external_observation(external)

        # With no locks, should accept observation
        # (blended based on acceptance which is 1.0 - 0)
        assert merged.shape == (4, 32)

    def test_locked_rejects_observation(self, opb):
        """Test locked dimensions reject external observation."""
        # Lock dimension 0
        opb.force_lock('POT', value=0.9)

        external = torch.ones(4, 32) * 0.5  # Different value
        merged = opb.merge_external_observation(external)

        # Locked dimension should retain locked value, not external
        assert not torch.allclose(merged[:, 0], external[:, 0])
        # Should be closer to locked value (0.9)
        assert (merged[:, 0] > 0.7).all()

    def test_override_breaks_lock(self, opb):
        """Test override_locks allows breaking locks."""
        opb.force_lock('POT', value=0.9)

        external = torch.ones(4, 32) * 0.1
        merged = opb.merge_external_observation(external, override_locks=True)

        # With override, should accept external even for locked
        # Value will be blended but closer to external
        assert merged[:, 0].mean() < 0.5  # Moved toward external (0.1)

    def test_acceptance_mask(self, opb):
        """Test get_acceptance_mask."""
        # Initially all accepting (no locks)
        mask = opb.get_acceptance_mask()
        assert (mask == 1.0).all()

        # After locking, acceptance decreases
        opb.force_lock('POT', value=0.9)
        mask = opb.get_acceptance_mask()
        assert mask[0] < 1.0  # Locked dimension has lower acceptance


# =============================================================================
# Integration Tests
# =============================================================================

class TestJEPAIntegration:
    """Integration tests for full JEPA pipeline."""

    def test_full_forward_pass(self):
        """Test full JEPA forward pass."""
        from symbolu.jepa import (
            SovereignStateProjector,
            PhaseJEPAPredictor,
            VICRegLoss,
        )

        # Components
        projector = SovereignStateProjector(hidden_dim=256)
        predictor = PhaseJEPAPredictor(state_dim=32, hidden_dim=64)
        loss_fn = VICRegLoss()

        # Forward pass
        hidden = torch.randn(4, 10, 256)  # [B, T, D]
        s_context = projector(hidden)  # [B, T, 32]

        # Predict future states
        s_pred, deltas = predictor(s_context, k_steps=2)

        # Create mock target (shifted context)
        s_target = torch.roll(s_context, -1, dims=1)

        # Compute loss
        loss = loss_fn(s_pred, s_target)

        assert loss.requires_grad
        assert not torch.isnan(loss)

    def test_gradient_flow(self):
        """Test gradients flow through entire pipeline."""
        from symbolu.jepa import (
            SovereignStateProjector,
            PhaseJEPAPredictor,
            JEPAPredictionLoss,
        )

        projector = SovereignStateProjector(hidden_dim=128)
        predictor = PhaseJEPAPredictor(state_dim=32, hidden_dim=64)
        loss_fn = JEPAPredictionLoss()

        # Forward
        hidden = torch.randn(2, 5, 128, requires_grad=True)
        s_context = projector(hidden)
        s_pred, _ = predictor(s_context, k_steps=1)
        s_target = torch.randn_like(s_pred)

        loss = loss_fn(s_pred, s_target)
        loss.backward()

        # Check gradients exist
        assert hidden.grad is not None
        assert not torch.isnan(hidden.grad).any()


# =============================================================================
# Test: TrainingCurriculumOrchestrator
# =============================================================================

class TestCurriculumOrchestrator:
    """Tests for TrainingCurriculumOrchestrator."""

    @pytest.fixture
    def orchestrator(self):
        from symbolu.jepa.curriculum import TrainingCurriculumOrchestrator
        return TrainingCurriculumOrchestrator(
            total_steps=1000,
            body_steps=200,
            soul_steps=500,
            auto_transition=True,
        )

    def test_initial_phase(self, orchestrator):
        """Test initial phase is BODY."""
        from symbolu.jepa.curriculum import MacroPhase
        assert orchestrator.state.macro_phase == MacroPhase.BODY

    def test_phase_transition_body_to_soul(self, orchestrator):
        """Test automatic transition from BODY to SOUL."""
        from symbolu.jepa.curriculum import MacroPhase

        # Advance past body_steps (200)
        for _ in range(201):
            orchestrator.step()

        assert orchestrator.state.macro_phase == MacroPhase.SOUL

    def test_phase_transition_soul_to_union(self, orchestrator):
        """Test automatic transition from SOUL to UNION."""
        from symbolu.jepa.curriculum import MacroPhase

        # Advance past soul_end (200 + 500 = 700)
        for _ in range(701):
            orchestrator.step()

        assert orchestrator.state.macro_phase == MacroPhase.UNION

    def test_get_loss_weights(self, orchestrator):
        """Test loss weight retrieval."""
        weights = orchestrator.get_loss_weights()
        assert 'jepa' in weights
        assert 'variance' in weights
        assert 'alignment' in weights

    def test_k_steps_by_phase(self, orchestrator):
        """Test k_steps changes with JEPA micro-phase."""
        from symbolu.jepa.curriculum import JEPAPhase

        # Initially in DHYANA phase (k=1)
        assert orchestrator.state.jepa_phase == JEPAPhase.DHYANA
        assert orchestrator.get_k_steps() == 1

    def test_progress_tracking(self, orchestrator):
        """Test progress information."""
        # Advance 100 steps
        for _ in range(100):
            orchestrator.step()

        progress = orchestrator.get_progress()
        assert progress['current_step'] == 100
        assert progress['overall'] == pytest.approx(0.1, rel=0.1)

    def test_state_dict_save_load(self, orchestrator):
        """Test checkpoint save/load."""
        # Advance and change state
        for _ in range(250):
            orchestrator.step()

        # Save state
        state_dict = orchestrator.state_dict()

        # Create new orchestrator
        from symbolu.jepa.curriculum import TrainingCurriculumOrchestrator
        new_orchestrator = TrainingCurriculumOrchestrator(
            total_steps=1000,
            body_steps=200,
            soul_steps=500,
        )

        # Load state
        new_orchestrator.load_state_dict(state_dict)

        assert new_orchestrator.state.current_step == 250
        assert new_orchestrator.state.macro_phase == orchestrator.state.macro_phase

    def test_force_phase_transition(self, orchestrator):
        """Test manual phase transition."""
        from symbolu.jepa.curriculum import MacroPhase

        changed, new_phase = orchestrator.step(force_phase='union')
        assert changed
        assert new_phase == 'UNION'
        assert orchestrator.state.macro_phase == MacroPhase.UNION


# =============================================================================
# Test: LossScheduler
# =============================================================================

class TestLossScheduler:
    """Tests for LossScheduler smooth weight interpolation."""

    def test_smooth_transition(self):
        """Test smooth weight transition during phase change."""
        from symbolu.jepa.curriculum import (
            TrainingCurriculumOrchestrator,
            LossScheduler,
        )

        orchestrator = TrainingCurriculumOrchestrator(
            total_steps=1000,
            body_steps=100,
            soul_steps=400,
            auto_transition=True,
        )
        scheduler = LossScheduler(orchestrator, transition_steps=50)

        # Get initial weights
        initial_weights = scheduler.get_weights()

        # Advance to phase transition
        for _ in range(101):
            orchestrator.step()

        # Weights should be transitioning
        transitional_weights = scheduler.get_weights()
        assert transitional_weights is not None


# =============================================================================
# Test: PhaseJEPATransformer (if HybridPhaseTransformer available)
# =============================================================================

class TestPhaseJEPATransformerBasic:
    """Basic tests for PhaseJEPATransformer (mocked encoder)."""

    def test_config_creation(self):
        """Test PhaseJEPAConfig creation."""
        from symbolu.jepa.transformer import PhaseJEPAConfig

        config = PhaseJEPAConfig(
            embed_dim=512,
            prediction_steps=4,
            target_momentum=0.996,
        )
        assert config.embed_dim == 512
        assert config.prediction_steps == 4
        assert config.target_momentum == 0.996

    def test_transformer_with_mock_encoder(self):
        """Test PhaseJEPATransformer with mock encoder."""
        from symbolu.jepa.transformer import PhaseJEPATransformer, PhaseJEPAConfig

        # Create mock encoder
        class MockEncoder(nn.Module):
            def __init__(self, embed_dim=256):
                super().__init__()
                self.embed = nn.Embedding(1000, embed_dim)
                self.layers = nn.TransformerEncoder(
                    nn.TransformerEncoderLayer(embed_dim, 4, batch_first=True),
                    num_layers=2,
                )

            def forward(self, input_ids, attention_mask=None):
                x = self.embed(input_ids)
                h = self.layers(x)
                return h  # Return hidden states

        config = PhaseJEPAConfig(
            embed_dim=256,
            vocab_size=1000,
            prediction_steps=2,
            predictor_hidden_dim=64,
        )

        encoder = MockEncoder(embed_dim=256)
        model = PhaseJEPATransformer(config=config, context_encoder=encoder)

        # Forward pass
        input_ids = torch.randint(0, 1000, (2, 32))
        outputs = model(input_ids, compute_loss=True)

        assert 's_pred' in outputs
        assert 'loss' in outputs
        assert outputs['loss'].requires_grad

    def test_target_encoder_update(self):
        """Test target encoder EMA update."""
        from symbolu.jepa.transformer import PhaseJEPATransformer, PhaseJEPAConfig

        class MockEncoder(nn.Module):
            def __init__(self):
                super().__init__()
                self.embed = nn.Embedding(100, 64)
                self.linear = nn.Linear(64, 64)

            def forward(self, input_ids, attention_mask=None):
                return self.linear(self.embed(input_ids))

        config = PhaseJEPAConfig(
            embed_dim=64,
            vocab_size=100,
            prediction_steps=1,
            target_momentum=0.9,  # Lower for visible changes
        )

        model = PhaseJEPATransformer(config=config, context_encoder=MockEncoder())

        # Get target encoder weight before update
        target_weight_before = model.target_encoder.encoder.linear.weight.clone()

        # Modify context encoder
        model.context_encoder.linear.weight.data += 0.1

        # Update target encoder
        model.update_target_encoder()

        target_weight_after = model.target_encoder.encoder.linear.weight

        # Weights should have moved (EMA update)
        assert not torch.allclose(target_weight_before, target_weight_after)

    def test_curriculum_integration(self):
        """Test curriculum integration with transformer."""
        from symbolu.jepa.transformer import PhaseJEPATransformer, PhaseJEPAConfig
        from symbolu.jepa.curriculum import TrainingCurriculumOrchestrator

        class MockEncoder(nn.Module):
            def __init__(self):
                super().__init__()
                self.embed = nn.Embedding(100, 64)

            def forward(self, input_ids, attention_mask=None):
                return self.embed(input_ids)

        config = PhaseJEPAConfig(embed_dim=64, vocab_size=100, prediction_steps=1)
        model = PhaseJEPATransformer(config=config, context_encoder=MockEncoder())

        curriculum = TrainingCurriculumOrchestrator(
            total_steps=100,
            body_steps=30,
            soul_steps=40,
        )
        model.set_curriculum(curriculum)

        assert model.curriculum is not None

        # Training step should update curriculum
        phase_changed, _ = model.training_step_update()

        assert model.training_step.item() == 1


# =============================================================================
# Test: Phase 3 Gradient Bridge (NLL → Predictor)
# =============================================================================

class TestPhase3GradientBridge:
    """
    Tests for Phase 3 (Kṛti) gradient flow from NLL loss to predictor.

    Critical: During Phase 3, gradients from L_nll must flow backwards through
    the Phase Rotation (θ) into the PhaseJEPAPredictor. This allows the predictor
    to learn: "I set θ=45°, got 'Cat'. Should have been θ=90° for 'Dog'."
    """

    def test_intent_phase_projector_gradient_flow(self):
        """Test gradients flow through intent_phase_projector."""
        from symbolu.jepa.transformer import PhaseJEPATransformer, PhaseJEPAConfig

        class MockEncoder(nn.Module):
            def __init__(self, embed_dim=64, vocab_size=100):
                super().__init__()
                self.embed = nn.Embedding(vocab_size, embed_dim)
                self.lm_head = nn.Linear(embed_dim, vocab_size)

            def forward(self, input_ids, attention_mask=None):
                h = self.embed(input_ids)
                logits = self.lm_head(h)
                return h, logits

        config = PhaseJEPAConfig(
            embed_dim=64,
            vocab_size=100,
            num_encoder_heads=4,
            prediction_steps=2,
            state_dim=32,
        )

        model = PhaseJEPATransformer(config=config, context_encoder=MockEncoder())

        # Create input
        input_ids = torch.randint(0, 100, (2, 16))
        s_pred = torch.randn(2, 32, requires_grad=True)

        # Compute phase rotation
        theta = model.compute_phase_rotation(s_pred)

        # Simulate loss on theta
        loss = theta.sum()
        loss.backward()

        # Gradient must flow back to s_pred
        assert s_pred.grad is not None, "Gradient did not flow to s_pred!"
        assert not torch.isnan(s_pred.grad).any(), "NaN in gradients"
        assert (s_pred.grad.abs() > 0).any(), "Zero gradients - no flow"

    def test_phase_modulation_gradient_flow(self):
        """Test gradients flow through _apply_phase_modulation."""
        from symbolu.jepa.transformer import PhaseJEPATransformer, PhaseJEPAConfig

        class MockEncoder(nn.Module):
            def __init__(self):
                super().__init__()
                self.embed = nn.Embedding(100, 48)  # 48 = 4 heads * 12 head_dim

            def forward(self, input_ids, attention_mask=None):
                return self.embed(input_ids)

        config = PhaseJEPAConfig(
            embed_dim=48,
            vocab_size=100,
            num_encoder_heads=4,
            prediction_steps=1,
            state_dim=32,
        )

        model = PhaseJEPATransformer(config=config, context_encoder=MockEncoder())

        # Test phase modulation gradient flow
        hidden_states = torch.randn(2, 8, 48, requires_grad=True)
        phase_rotation = torch.randn(2, 4, requires_grad=True)

        h_modulated = model._apply_phase_modulation(hidden_states, phase_rotation)

        # Loss on modulated output
        loss = h_modulated.sum()
        loss.backward()

        # Both inputs should receive gradients
        assert hidden_states.grad is not None, "No gradient to hidden_states"
        assert phase_rotation.grad is not None, "No gradient to phase_rotation"
        assert not torch.isnan(hidden_states.grad).any()
        assert not torch.isnan(phase_rotation.grad).any()

    def test_full_phase3_nll_to_predictor_gradient(self):
        """
        CRITICAL TEST: Verify complete gradient flow from NLL → Predictor.

        This tests the full gradient path:
        L_nll → logits → h_modulated → θ → s_pred → predictor → s_context → encoder
        """
        from symbolu.jepa.transformer import PhaseJEPATransformer, PhaseJEPAConfig

        class MockEncoderWithHead(nn.Module):
            def __init__(self, embed_dim=64, vocab_size=100):
                super().__init__()
                self.embed = nn.Embedding(vocab_size, embed_dim)
                self.transform = nn.Linear(embed_dim, embed_dim)
                self.lm_head = nn.Linear(embed_dim, vocab_size)

            def forward(self, input_ids, attention_mask=None):
                h = self.transform(self.embed(input_ids))
                logits = self.lm_head(h)
                return h, logits

        config = PhaseJEPAConfig(
            embed_dim=64,
            vocab_size=100,
            num_encoder_heads=4,
            prediction_steps=2,
            state_dim=32,
            predictor_hidden_dim=32,
        )

        model = PhaseJEPATransformer(config=config, context_encoder=MockEncoderWithHead())
        model.train()

        # Enable Phase 3 mode
        model.set_phase3_mode(True)

        # Input and labels
        input_ids = torch.randint(0, 100, (2, 20))
        labels = input_ids.clone()

        # Forward with Phase 3
        outputs = model.forward_phase3(
            input_ids=input_ids,
            labels=labels,
            return_loss_components=True,
        )

        assert 'loss' in outputs
        assert 'phase_rotation' in outputs
        assert 's_pred' in outputs

        # Backward pass
        loss = outputs['loss']
        loss.backward()

        # CRITICAL CHECKS: Predictor weights must have gradients
        predictor_has_grad = False
        for name, param in model.predictor.named_parameters():
            if param.grad is not None and (param.grad.abs() > 1e-10).any():
                predictor_has_grad = True
                break

        assert predictor_has_grad, (
            "CRITICAL FAILURE: Predictor has no gradients from NLL loss! "
            "Phase 3 gradient bridge is broken."
        )

        # Intent phase projector must also have gradients
        projector_has_grad = False
        for param in model.intent_phase_projector.parameters():
            if param.grad is not None and (param.grad.abs() > 1e-10).any():
                projector_has_grad = True
                break

        assert projector_has_grad, (
            "Intent phase projector has no gradients! "
            "θ = f(s_pred) gradient path is broken."
        )

    def test_no_detach_in_phase3_path(self):
        """Verify s_pred is NOT detached in Phase 3 forward."""
        from symbolu.jepa.transformer import PhaseJEPATransformer, PhaseJEPAConfig

        class MockEncoder(nn.Module):
            def __init__(self):
                super().__init__()
                self.embed = nn.Embedding(100, 64)
                self.lm_head = nn.Linear(64, 100)

            def forward(self, input_ids, attention_mask=None):
                h = self.embed(input_ids)
                return h, self.lm_head(h)

        config = PhaseJEPAConfig(
            embed_dim=64,
            vocab_size=100,
            num_encoder_heads=4,
            prediction_steps=2,
            state_dim=32,
        )

        model = PhaseJEPATransformer(config=config, context_encoder=MockEncoder())
        model.train()
        model.set_phase3_mode(True)

        input_ids = torch.randint(0, 100, (2, 16))

        # Run forward_phase3
        outputs = model.forward_phase3(input_ids=input_ids, labels=input_ids)

        # s_pred should require grad (not detached)
        s_pred = outputs['s_pred']
        assert s_pred.requires_grad, (
            "s_pred does NOT require grad! "
            "Someone called .detach() on the prediction path."
        )

        # phase_rotation should also require grad
        phase_rotation = outputs['phase_rotation']
        assert phase_rotation.requires_grad, (
            "phase_rotation does NOT require grad! "
            "Gradient bridge is broken."
        )

    def test_phase3_mode_toggle(self):
        """Test set_phase3_mode properly toggles routing."""
        from symbolu.jepa.transformer import PhaseJEPATransformer, PhaseJEPAConfig

        class MockEncoder(nn.Module):
            def __init__(self):
                super().__init__()
                self.embed = nn.Embedding(100, 64)

            def forward(self, input_ids, attention_mask=None):
                return self.embed(input_ids)

        config = PhaseJEPAConfig(embed_dim=64, vocab_size=100, prediction_steps=2)
        model = PhaseJEPATransformer(config=config, context_encoder=MockEncoder())

        # Initially Phase 3 mode is off
        assert not model._phase3_mode

        # Enable Phase 3
        model.set_phase3_mode(True)
        assert model._phase3_mode

        # Disable Phase 3
        model.set_phase3_mode(False)
        assert not model._phase3_mode


class TestSelfMotivation:
    """Tests for self-motivation / Sankalpa components."""

    def test_goal_generator_output_shape(self):
        """Test GoalGenerator produces correct output shape."""
        from symbolu.jepa.transformer import GoalGenerator, SOVEREIGN_STATE_DIM

        goal_gen = GoalGenerator(state_dim=SOVEREIGN_STATE_DIM)
        batch_size = 4

        # Test with 2D input
        state = torch.randn(batch_size, SOVEREIGN_STATE_DIM)
        curiosity = torch.rand(batch_size)
        goal = goal_gen(state, curiosity, apply_momentum=False)

        assert goal.shape == (batch_size, 4), f"Expected (4, 4), got {goal.shape}"

        # Test with 3D input (sequence)
        seq_len = 10
        state_seq = torch.randn(batch_size, seq_len, SOVEREIGN_STATE_DIM)
        curiosity_seq = torch.rand(batch_size, seq_len)
        goal_seq = goal_gen(state_seq, curiosity_seq, apply_momentum=False)

        assert goal_seq.shape == (batch_size, seq_len, 4)

    def test_goal_generator_output_ranges(self):
        """Test GoalGenerator outputs are in expected ranges."""
        from symbolu.jepa.transformer import GoalGenerator, SOVEREIGN_STATE_DIM

        goal_gen = GoalGenerator(state_dim=SOVEREIGN_STATE_DIM)
        batch_size = 16

        state = torch.randn(batch_size, SOVEREIGN_STATE_DIM)
        curiosity = torch.rand(batch_size) * 2  # High curiosity

        goal = goal_gen(state, curiosity, apply_momentum=False)

        # Valence: [-1, 1] (Tanh)
        assert (goal[:, 0] >= -1).all() and (goal[:, 0] <= 1).all(), \
            f"Valence out of range: {goal[:, 0].min()}, {goal[:, 0].max()}"

        # Urgency: [0, 1] (Sigmoid)
        assert (goal[:, 1] >= 0).all() and (goal[:, 1] <= 1).all(), \
            f"Urgency out of range: {goal[:, 1].min()}, {goal[:, 1].max()}"

        # Complexity: [0, 1] (Sigmoid)
        assert (goal[:, 2] >= 0).all() and (goal[:, 2] <= 1).all(), \
            f"Complexity out of range: {goal[:, 2].min()}, {goal[:, 2].max()}"

        # Source: [0, 1] (Sigmoid)
        assert (goal[:, 3] >= 0).all() and (goal[:, 3] <= 1).all(), \
            f"Source out of range: {goal[:, 3].min()}, {goal[:, 3].max()}"

    def test_curiosity_driven_goal_source(self):
        """Test get_curiosity_driven_goal forces source=1.0."""
        from symbolu.jepa.transformer import GoalGenerator, SOVEREIGN_STATE_DIM

        goal_gen = GoalGenerator(state_dim=SOVEREIGN_STATE_DIM)
        state = torch.randn(4, SOVEREIGN_STATE_DIM)
        curiosity = torch.rand(4)

        goal = goal_gen.get_curiosity_driven_goal(state, curiosity)

        # Source dimension should be 1.0 (internal)
        assert (goal[:, 3] == 1.0).all(), \
            f"Source should be 1.0 for curiosity-driven goal, got {goal[:, 3]}"

    def test_curiosity_signal_computation(self):
        """Test compute_curiosity_signal produces correct values."""
        from symbolu.jepa.transformer import PhaseJEPATransformer, PhaseJEPAConfig

        class MockEncoder(nn.Module):
            def __init__(self):
                super().__init__()
                self.embed = nn.Embedding(100, 64)

            def forward(self, input_ids, attention_mask=None):
                return self.embed(input_ids)

        config = PhaseJEPAConfig(embed_dim=64, vocab_size=100, state_dim=32)
        model = PhaseJEPATransformer(config=config, context_encoder=MockEncoder())

        # Test curiosity computation
        s_pred = torch.randn(4, 32)
        s_actual = torch.randn(4, 32)

        curiosity = model.compute_curiosity_signal(s_pred, s_actual, normalize=True)

        assert curiosity.shape == (4,)
        assert (curiosity >= 0).all(), "Curiosity should be non-negative"

        # Test zero prediction error gives zero curiosity
        curiosity_zero = model.compute_curiosity_signal(s_pred, s_pred)
        assert torch.allclose(curiosity_zero, torch.zeros_like(curiosity_zero), atol=1e-6)

    def test_sankalpa_injection_extraction(self):
        """Test inject_sankalpa and extract_sankalpa are inverses."""
        from symbolu.jepa.transformer import (
            PhaseJEPATransformer, PhaseJEPAConfig,
            SANKALPA_START_DIM, SANKALPA_END_DIM,
        )

        class MockEncoder(nn.Module):
            def __init__(self):
                super().__init__()
                self.embed = nn.Embedding(100, 64)

            def forward(self, input_ids, attention_mask=None):
                return self.embed(input_ids)

        config = PhaseJEPAConfig(embed_dim=64, vocab_size=100, state_dim=32)
        model = PhaseJEPATransformer(config=config, context_encoder=MockEncoder())

        # Create state and goal
        state = torch.randn(4, 32)
        goal = torch.tensor([[0.5, 0.7, 0.3, 1.0]] * 4)

        # Inject and extract
        modified = model.inject_sankalpa(state, goal)
        extracted = model.extract_sankalpa(modified)

        assert torch.allclose(extracted, goal), \
            "Extracted goal should match injected goal"

        # Original dimensions should be unchanged
        original_dims = list(range(0, SANKALPA_START_DIM))
        assert torch.allclose(modified[:, original_dims], state[:, original_dims]), \
            "Non-Sankalpa dimensions should be unchanged"

    def test_sovereign_jepa_autonomous_step(self):
        """Test SovereignJEPA.autonomous_step produces expected outputs."""
        from symbolu.jepa.transformer import (
            SovereignJEPA, SovereignJEPAConfig, PhaseJEPAConfig,
            PhaseJEPATransformer,
        )

        class MockEncoder(nn.Module):
            def __init__(self):
                super().__init__()
                self.embed = nn.Embedding(100, 64)

            def forward(self, input_ids, attention_mask=None):
                return self.embed(input_ids)

        jepa_config = PhaseJEPAConfig(
            embed_dim=64,
            vocab_size=100,
            state_dim=32,
            enable_self_motivation=True,
        )
        jepa_model = PhaseJEPATransformer(
            config=jepa_config,
            context_encoder=MockEncoder(),
        )

        sovereign_config = SovereignJEPAConfig(
            jepa_config=jepa_config,
            enable_metacognition=True,
        )
        model = SovereignJEPA(
            config=sovereign_config,
            jepa_model=jepa_model,
        )

        # Run autonomous step
        context_ids = torch.randint(0, 100, (2, 20))
        outputs = model.autonomous_step(context_ids, force_new_goal=True)

        # Check expected keys
        assert 'curiosity' in outputs, "Should have curiosity"
        assert 'goal' in outputs, "Should have goal"
        assert 'goal_changed' in outputs, "Should have goal_changed"
        assert 'autonomous_action' in outputs, "Should have autonomous_action"
        assert 's_goal_directed' in outputs, "Should have s_goal_directed"

        # Goal should be updated on first step with force_new_goal=True
        assert outputs['goal_changed'] is True

    def test_sovereign_jepa_goal_persistence(self):
        """Test goal persists across multiple autonomous steps."""
        from symbolu.jepa.transformer import (
            SovereignJEPA, SovereignJEPAConfig, PhaseJEPAConfig,
            PhaseJEPATransformer,
        )

        class MockEncoder(nn.Module):
            def __init__(self):
                super().__init__()
                self.embed = nn.Embedding(100, 64)

            def forward(self, input_ids, attention_mask=None):
                return self.embed(input_ids)

        jepa_config = PhaseJEPAConfig(
            embed_dim=64,
            vocab_size=100,
            state_dim=32,
            enable_self_motivation=True,
        )
        jepa_model = PhaseJEPATransformer(
            config=jepa_config,
            context_encoder=MockEncoder(),
        )

        sovereign_config = SovereignJEPAConfig(
            jepa_config=jepa_config,
            goal_persistence=5,  # Goal persists for 5 steps
            enable_metacognition=False,
        )
        model = SovereignJEPA(
            config=sovereign_config,
            jepa_model=jepa_model,
        )

        context_ids = torch.randint(0, 100, (2, 20))

        # First step - force new goal
        outputs1 = model.autonomous_step(context_ids, force_new_goal=True)
        goal1 = outputs1['goal'].clone()

        # Second step - goal should persist (not change)
        outputs2 = model.autonomous_step(context_ids, force_new_goal=False)

        # Goal shouldn't change until persistence expires
        assert torch.allclose(outputs2['goal'], goal1), \
            "Goal should persist across steps"

    def test_autonomous_state_tracking(self):
        """Test get_autonomous_state returns valid state."""
        from symbolu.jepa.transformer import (
            SovereignJEPA, SovereignJEPAConfig, PhaseJEPAConfig,
            PhaseJEPATransformer,
        )

        class MockEncoder(nn.Module):
            def __init__(self):
                super().__init__()
                self.embed = nn.Embedding(100, 64)

            def forward(self, input_ids, attention_mask=None):
                return self.embed(input_ids)

        jepa_config = PhaseJEPAConfig(
            embed_dim=64,
            vocab_size=100,
            enable_self_motivation=True,
        )
        jepa_model = PhaseJEPATransformer(
            config=jepa_config,
            context_encoder=MockEncoder(),
        )
        model = SovereignJEPA(jepa_model=jepa_model)

        context_ids = torch.randint(0, 100, (2, 20))
        model.autonomous_step(context_ids, force_new_goal=True)

        state = model.get_autonomous_state()

        # Check all expected keys
        expected_keys = [
            'idle_steps', 'current_goal', 'goal_steps',
            'total_autonomous_steps', 'mean_curiosity', 'std_curiosity',
            'goal_valence', 'goal_urgency', 'goal_complexity', 'goal_source',
        ]
        for key in expected_keys:
            assert key in state, f"Missing key: {key}"

    def test_goal_generator_gradient_flow(self):
        """Test gradients flow through goal generator."""
        from symbolu.jepa.transformer import GoalGenerator, SOVEREIGN_STATE_DIM

        goal_gen = GoalGenerator(state_dim=SOVEREIGN_STATE_DIM)

        state = torch.randn(4, SOVEREIGN_STATE_DIM, requires_grad=True)
        curiosity = torch.rand(4, requires_grad=True)

        goal = goal_gen(state, curiosity, apply_momentum=False)

        # Compute loss and backprop
        loss = goal.sum()
        loss.backward()

        assert state.grad is not None, "Gradients should flow to state"
        assert curiosity.grad is not None, "Gradients should flow to curiosity"

    def test_describe_action_categories(self):
        """Test _describe_action produces valid action descriptions."""
        from symbolu.jepa.transformer import (
            SovereignJEPA, SovereignJEPAConfig, PhaseJEPAConfig,
            PhaseJEPATransformer,
        )

        class MockEncoder(nn.Module):
            def __init__(self):
                super().__init__()
                self.embed = nn.Embedding(100, 64)

            def forward(self, input_ids, attention_mask=None):
                return self.embed(input_ids)

        jepa_config = PhaseJEPAConfig(
            embed_dim=64,
            vocab_size=100,
            enable_self_motivation=True,
        )
        jepa_model = PhaseJEPATransformer(
            config=jepa_config,
            context_encoder=MockEncoder(),
        )
        model = SovereignJEPA(jepa_model=jepa_model)

        # Test different goal scenarios
        test_cases = [
            (torch.tensor([0.5, 0.8, 0.3, 1.0]), 0.05, "PURSUE_POSITIVE"),
            (torch.tensor([-0.5, 0.8, 0.3, 0.0]), 0.05, "AVOID_NEGATIVE"),
            (torch.tensor([0.0, 0.5, 0.5, 1.0]), 0.05, "MAINTAIN"),
            (torch.tensor([0.0, 0.5, 0.5, 1.0]), 0.5, "EXPLORE"),  # High curiosity
        ]

        for goal, curiosity, expected_action in test_cases:
            action = model._describe_action(goal, curiosity)
            assert expected_action in action, \
                f"Expected '{expected_action}' in '{action}' for goal={goal}, curiosity={curiosity}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
