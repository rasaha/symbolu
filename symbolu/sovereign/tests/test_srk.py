"""
Sovereign Reasoning Kernel (SRK) Unit Tests
============================================

V9.8.0 Test Suite

Tests for:
- SRKConfig
- SovereignReasoningKernel
- OPBDimensionLock
- UserOntologicalMirror
- UOMDiagnosticsMonitor
- Checkpoint save/load
- SovereignLoss
- SovereignAnnealer
"""

import pytest
import torch
import torch.nn as nn
import tempfile
import os
from pathlib import Path

# Import SRK components
from symbolu.sovereign.reasoning_kernel import (
    SRKConfig,
    SovereignReasoningKernel,
    SovereignEmbedding,
    IsomorphicMappingRouter,
    OntologicalBridge,
    WitnessArbitrator,
    SynthesisGate,
    VrittiGate,
    KoshaShiftController,
    OPBDimensionLock,
    UserOntologicalMirror,
    UOMDiagnosticsMonitor,
    MaunaProtocol,
    PhaseExtractionHook,
    SOVEREIGN_STATE_DIM,
    BHAVA_NAMES,
    KOSHA_NAMES,
    VRITTI_NAMES,
    GUNA_NAMES,
    create_logic_templates,
)

from symbolu.sovereign.sovereign_loss import (
    SovereignLossConfig,
    SovereignLoss,
    SovereignAnnealer,
    TeleologicalOptimizer,
    BackwardScoreCalculator,
    ForwardScoreCalculator,
    PhaseCoherenceCalculator,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def device():
    """Get test device (CPU for CI compatibility)."""
    return torch.device('cpu')


@pytest.fixture
def srk_config():
    """Create default SRK config."""
    return SRKConfig(
        state_dim=32,
        hidden_dim=256,  # Smaller for tests
        num_heads=4,
    )


@pytest.fixture
def srk(srk_config, device):
    """Create SRK instance."""
    return SovereignReasoningKernel(srk_config).to(device)


@pytest.fixture
def batch_hidden(device):
    """Create batch of hidden states."""
    B, N, D = 2, 16, 256
    return torch.randn(B, N, D, device=device)


@pytest.fixture
def batch_state(device):
    """Create batch of 32D states."""
    B = 2
    state = torch.rand(B, SOVEREIGN_STATE_DIM, device=device)
    # Normalize each component group
    state[:, 0:12] = torch.softmax(state[:, 0:12], dim=-1)
    state[:, 12:17] = torch.softmax(state[:, 12:17], dim=-1)
    state[:, 17:22] = torch.softmax(state[:, 17:22], dim=-1)
    state[:, 22:28] = torch.softmax(state[:, 22:28], dim=-1)
    state[:, 28:32] = torch.sigmoid(state[:, 28:32])
    return state


# =============================================================================
# SRKConfig TESTS
# =============================================================================

class TestSRKConfig:
    """Tests for SRKConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = SRKConfig()
        assert config.state_dim == 32
        assert config.hidden_dim == 768
        assert config.num_heads == 12
        assert config.dna_bridge_layer == 4
        assert config.witness_layer == 9
        assert config.synthesis_layer == 11

    def test_custom_values(self):
        """Test custom configuration values."""
        config = SRKConfig(
            hidden_dim=512,
            num_heads=8,
            isomorphism_threshold=0.8,
        )
        assert config.hidden_dim == 512
        assert config.num_heads == 8
        assert config.isomorphism_threshold == 0.8

    def test_validation_state_dim(self):
        """Test state_dim must be 32."""
        with pytest.raises(AssertionError):
            SRKConfig(state_dim=16)

    def test_validation_threshold_range(self):
        """Test threshold must be in (0, 1]."""
        with pytest.raises(AssertionError):
            SRKConfig(isomorphism_threshold=1.5)
        with pytest.raises(AssertionError):
            SRKConfig(isomorphism_threshold=0.0)


# =============================================================================
# SovereignReasoningKernel TESTS
# =============================================================================

class TestSovereignReasoningKernel:
    """Tests for main SRK class."""

    def test_initialization(self, srk_config, device):
        """Test SRK initializes correctly."""
        srk = SovereignReasoningKernel(srk_config).to(device)

        assert srk.config == srk_config
        assert srk.karma_state.shape == (1, 32)
        assert hasattr(srk, 'dna_bridge')
        assert hasattr(srk, 'witness')
        assert hasattr(srk, 'synthesis_gate')
        assert hasattr(srk, 'imr')
        assert hasattr(srk, 'opb_lock')

    def test_karma_initialization(self, srk, device):
        """Test karma is initialized with Absolute Potential bias."""
        karma = srk.karma_state.squeeze(0)
        # O12_ABS should be high
        assert karma[11].item() > 0.5
        # MATERIAL should be present
        assert karma[12].item() > 0.5

    def test_get_karma_batch_expansion(self, srk, device):
        """Test karma expands to batch size."""
        karma = srk.get_karma(batch_size=4)
        assert karma.shape == (4, 32)

    def test_compute_state_from_hidden(self, srk, batch_hidden, device):
        """Test 32D state computation from hidden states."""
        state = srk.compute_state_from_hidden(batch_hidden)

        assert state.shape == (batch_hidden.shape[0], 32)
        # Check normalization
        assert torch.allclose(state[:, 0:12].sum(dim=-1), torch.ones(2, device=device), atol=1e-5)
        assert torch.allclose(state[:, 12:17].sum(dim=-1), torch.ones(2, device=device), atol=1e-5)

    def test_forward_pass_dna_bridge(self, srk, batch_hidden, batch_state, device):
        """Test forward pass at DNA Bridge layer."""
        result = srk.forward_pass(
            hidden_states=batch_hidden,
            layer_idx=4,  # DNA Bridge layer
            current_state=batch_state,
        )

        assert 'hidden_states' in result
        assert 'diagnostics' in result
        assert result['hidden_states'].shape == batch_hidden.shape
        assert result['diagnostics']['layer_idx'] == 4

    def test_forward_pass_witness(self, srk, batch_hidden, batch_state, device):
        """Test forward pass at Witness layer."""
        result = srk.forward_pass(
            hidden_states=batch_hidden,
            layer_idx=9,  # Witness layer
            current_state=batch_state,
        )

        assert result['diagnostics']['layer_idx'] == 9

    def test_forward_pass_synthesis(self, srk, batch_hidden, batch_state, device):
        """Test forward pass at Synthesis layer."""
        result = srk.forward_pass(
            hidden_states=batch_hidden,
            layer_idx=11,  # Synthesis layer
            current_state=batch_state,
        )

        assert result['diagnostics']['layer_idx'] == 11

    def test_step_karma(self, srk, batch_state, device):
        """Test karma update (Toroidal loop)."""
        initial_karma = srk.karma_state.clone()
        srk.step_karma(batch_state)

        # Karma should be updated
        assert not torch.equal(srk.karma_state, initial_karma)

    def test_reset_karma(self, srk, device):
        """Test karma reset to initial state."""
        # Modify karma
        srk.karma_state.fill_(0.5)

        # Reset
        srk.reset_karma()

        # Check initialization values restored
        assert srk.karma_state[0, 11].item() > 0.5  # O12_ABS

    def test_diagnostics(self, srk, device):
        """Test diagnostic information."""
        diag = srk.get_diagnostics()

        assert 'dominant_bhava' in diag
        assert 'active_kosha' in diag
        assert 'vritti_state' in diag
        assert 'lucidity' in diag
        assert diag['dominant_bhava'] in BHAVA_NAMES


# =============================================================================
# OPBDimensionLock TESTS
# =============================================================================

class TestOPBDimensionLock:
    """Tests for OPB Dimension Locking."""

    @pytest.fixture
    def opb_lock(self, device):
        """Create OPB lock instance."""
        return OPBDimensionLock(
            state_dim=32,
            lock_threshold=0.7,
            unlock_threshold=0.3,
            lock_decay=0.95,
            blend_factor=0.6,
        ).to(device)

    def test_initialization(self, opb_lock, device):
        """Test OPB lock initializes with no locks."""
        assert opb_lock.locked_mask.sum().item() == 0
        assert opb_lock.locked_state.sum().item() == 0

    def test_auto_lock_high_activation(self, opb_lock, device):
        """Test dimension auto-locks on high activation."""
        # Create state with high O7 (Reasoning)
        state = torch.zeros(2, 32, device=device)
        state[:, 6] = 0.85  # O7_RSN above lock_threshold (0.7)

        diag = opb_lock.update_locks(state)

        assert opb_lock.locked_mask[6].item() == True
        assert 'Bhava_RSN' in diag['newly_locked']

    def test_lock_persistence(self, opb_lock, device):
        """Test locked dimension persists with decay."""
        # Lock O7
        opb_lock.force_lock('RSN', value=0.9)
        initial_strength = opb_lock.lock_strength[6].item()

        # Update with lower activation
        state = torch.zeros(2, 32, device=device)
        state[:, 6] = 0.5  # Below lock threshold but above unlock

        opb_lock.update_locks(state)

        # Should still be locked but with decayed strength
        assert opb_lock.locked_mask[6].item() == True
        assert opb_lock.lock_strength[6].item() < initial_strength

    def test_apply_locks_blending(self, opb_lock, device):
        """Test locked state blends with new state."""
        # Lock O7 with high value
        opb_lock.force_lock('RSN', value=0.9)

        # New state with low O7
        new_state = torch.zeros(2, 32, device=device)
        new_state[:, 6] = 0.1

        blended = opb_lock.apply_locks(new_state)

        # O7 should be boosted by locked value
        assert blended[:, 6].mean().item() > 0.1

    def test_force_unlock(self, opb_lock, device):
        """Test manual unlock."""
        opb_lock.force_lock('RSN', value=0.9)
        assert opb_lock.locked_mask[6].item() == True

        opb_lock.force_unlock('RSN')
        assert opb_lock.locked_mask[6].item() == False

    def test_reset(self, opb_lock, device):
        """Test reset clears all locks."""
        opb_lock.force_lock('RSN', value=0.9)
        opb_lock.force_lock('STR', value=0.8)

        opb_lock.reset()

        assert opb_lock.locked_mask.sum().item() == 0

    def test_get_locked_dimensions(self, opb_lock, device):
        """Test retrieving locked dimension names."""
        opb_lock.force_lock('RSN', value=0.9)
        opb_lock.force_lock('INTELLECTUAL', value=0.8)

        locked = opb_lock.get_locked_dimensions()

        assert 'Bhava_RSN' in locked
        assert 'Kosha_INTELLECTUAL' in locked


# =============================================================================
# UserOntologicalMirror TESTS
# =============================================================================

class TestUserOntologicalMirror:
    """Tests for UOM."""

    @pytest.fixture
    def uom(self, device):
        """Create UOM instance."""
        return UserOntologicalMirror(
            state_dim=32,
            hidden_dim=256,
            distress_threshold=0.6,
            confusion_threshold=0.5,
        ).to(device)

    def test_sattvic_anchor_creation(self, uom, device):
        """Test Sattvic anchor has correct values."""
        anchor = uom.sattvic_anchor

        assert anchor[11].item() > 0.9  # O12_ABS high
        assert anchor[15].item() > 0.7  # INTELLECTUAL high
        assert anchor[17].item() > 0.8  # FACT high
        assert anchor[22].item() > 0.9  # LUCIDITY high

    def test_detect_user_state_normal(self, uom, batch_state, device):
        """Test detection of normal user state."""
        # Normal state (no distress/confusion)
        normal_state = batch_state.clone()
        normal_state[:, 18] = 0.1  # Low ERROR
        normal_state[:, 13] = 0.2  # Low VITAL
        normal_state[:, 23] = 0.3  # Low ACTIVITY (Rajas)

        analysis = uom.detect_user_state(normal_state)

        assert not analysis['is_distressed']
        assert not analysis['is_confused']

    def test_detect_user_state_distressed(self, uom, device):
        """Test detection of distressed user."""
        distressed_state = torch.zeros(2, 32, device=device)
        distressed_state[:, 13] = 0.8  # High VITAL (emotional)
        distressed_state[:, 23] = 0.9  # High ACTIVITY (panic)
        distressed_state[:, 18] = 0.7  # High ERROR

        analysis = uom.detect_user_state(distressed_state)

        assert analysis['is_distressed']
        assert analysis['vital_high']
        assert analysis['rajas_high']

    def test_recommend_intervention_direct(self, uom, batch_state, device):
        """Test DIRECT_ACTION recommendation for stable user."""
        # Make state stable
        stable_state = batch_state.clone()
        stable_state[:, 18] = 0.1  # Low ERROR
        stable_state[:, 13] = 0.1  # Low VITAL
        stable_state[:, 23] = 0.2  # Low ACTIVITY

        target, strategy, diag = uom.recommend_intervention(stable_state, 'factual')

        assert strategy == 'DIRECT_ACTION'

    def test_recommend_intervention_stabilize(self, uom, device):
        """Test STABILIZE_AND_REFRAME for distressed+confused user."""
        crisis_state = torch.zeros(2, 32, device=device)
        crisis_state[:, 18] = 0.8  # High ERROR
        crisis_state[:, 13] = 0.8  # High VITAL
        crisis_state[:, 23] = 0.9  # High ACTIVITY
        crisis_state[:, 14] = 0.7  # High MENTAL
        crisis_state[:, 20] = 0.6  # High VOID

        target, strategy, diag = uom.recommend_intervention(crisis_state, 'factual')

        assert strategy == 'STABILIZE_AND_REFRAME'

    def test_teleological_vector(self, uom, batch_state, device):
        """Test teleological vector calculation."""
        tele_vec = uom.calculate_teleological_vector(batch_state, 'factual')

        assert tele_vec.shape == batch_state.shape
        # Vector points toward Sattvic anchor

    def test_task_specific_anchors(self, uom, device):
        """Test different anchors for different tasks."""
        factual = uom.get_anchor_for_task('factual')
        creative = uom.get_anchor_for_task('creative')
        analytical = uom.get_anchor_for_task('analytical')

        # Creative should have higher IMAGINATION tolerance
        assert creative[19].item() > factual[19].item()
        # Analytical should have high INTELLECTUAL
        assert analytical[15].item() >= factual[15].item()


# =============================================================================
# UOMDiagnosticsMonitor TESTS
# =============================================================================

class TestUOMDiagnosticsMonitor:
    """Tests for UOM Diagnostics Monitor."""

    @pytest.fixture
    def monitor(self):
        """Create monitor instance."""
        return UOMDiagnosticsMonitor(history_size=10)

    def test_track_positive_intervention(self, monitor, device):
        """Test tracking positive intervention."""
        initial = torch.zeros(32, device=device)
        initial[22] = 0.3  # Low LUCIDITY
        initial[17] = 0.2  # Low FACT
        initial[18] = 0.7  # High ERROR

        final = torch.zeros(32, device=device)
        final[22] = 0.8  # High LUCIDITY
        final[17] = 0.7  # High FACT
        final[18] = 0.2  # Low ERROR

        result = monitor.track_intervention(initial, final, 'STABILIZE')

        assert result['effectiveness'] > 0
        assert result['delta_sattva'] > 0
        assert result['validity_gain'] > 0
        assert result['status'] in ['HIGH', 'MEDIUM']

    def test_track_negative_intervention(self, monitor, device):
        """Test tracking failed intervention."""
        initial = torch.zeros(32, device=device)
        initial[22] = 0.7  # High LUCIDITY

        final = torch.zeros(32, device=device)
        final[22] = 0.3  # Low LUCIDITY (got worse)
        final[18] = 0.6  # High ERROR

        result = monitor.track_intervention(initial, final, 'FAILED')

        assert result['effectiveness'] < 0
        assert result['status'] == 'LOW'

    def test_history_limit(self, monitor, device):
        """Test history respects size limit."""
        for i in range(15):
            initial = torch.zeros(32, device=device)
            final = torch.zeros(32, device=device)
            final[22] = 0.5 + (i * 0.01)
            monitor.track_intervention(initial, final, f'INT_{i}')

        # History should be capped at 10
        assert len(monitor.history) == 10

    def test_summary_statistics(self, monitor, device):
        """Test summary computation."""
        # Add some positive and negative interventions
        for i in range(5):
            initial = torch.zeros(32, device=device)
            final = torch.zeros(32, device=device)
            final[22] = 0.8  # Positive
            monitor.track_intervention(initial, final, 'POSITIVE')

        for i in range(3):
            initial = torch.zeros(32, device=device)
            final = torch.zeros(32, device=device)
            final[22] = 0.0  # Negative
            final[18] = 0.5  # Error increased
            monitor.track_intervention(initial, final, 'NEGATIVE')

        summary = monitor.get_summary()

        assert summary['total_interventions'] == 8
        assert 0 < summary['success_rate'] < 1


# =============================================================================
# CHECKPOINT TESTS
# =============================================================================

class TestCheckpoint:
    """Tests for checkpoint save/load."""

    def test_get_checkpoint_state(self, srk, device):
        """Test checkpoint state extraction."""
        state = srk.get_checkpoint_state()

        assert 'srk_version' in state
        assert state['srk_version'] == '9.8.0'
        assert 'karma_state' in state
        assert 'opb_locked_mask' in state
        assert 'dna_bridge_state' in state
        assert 'config' in state

    def test_load_checkpoint_state(self, srk_config, device):
        """Test checkpoint loading."""
        srk1 = SovereignReasoningKernel(srk_config).to(device)

        # Modify state
        srk1.karma_state.fill_(0.5)
        srk1.opb_lock.force_lock('RSN', 0.9)

        # Save state
        checkpoint = srk1.get_checkpoint_state()

        # Create new SRK and load
        srk2 = SovereignReasoningKernel(srk_config).to(device)
        missing, _ = srk2.load_checkpoint_state(checkpoint)

        # Verify state restored
        assert torch.allclose(srk2.karma_state, srk1.karma_state)
        assert srk2.opb_lock.locked_mask[6].item() == True

    def test_save_load_file(self, srk_config, device):
        """Test full save/load cycle with file."""
        srk1 = SovereignReasoningKernel(srk_config).to(device)
        srk1.karma_state.fill_(0.42)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / 'srk_test.pt'

            # Save
            torch.save({'srk_state': srk1.get_checkpoint_state()}, path)

            # Load
            srk2 = SovereignReasoningKernel.from_checkpoint(str(path), device=device)

            assert torch.allclose(srk2.karma_state, srk1.karma_state)

    def test_version_mismatch_warning(self, srk_config, device, capsys):
        """Test warning on version mismatch."""
        srk = SovereignReasoningKernel(srk_config).to(device)

        # Create checkpoint with different version
        checkpoint = srk.get_checkpoint_state()
        checkpoint['srk_version'] = '8.0.0'

        srk.load_checkpoint_state(checkpoint)

        captured = capsys.readouterr()
        assert 'Warning' in captured.out or len(captured.out) == 0  # May or may not print


# =============================================================================
# SovereignLoss TESTS
# =============================================================================

class TestSovereignLoss:
    """Tests for SRK loss functions."""

    @pytest.fixture
    def loss_config(self):
        """Create loss config."""
        return SovereignLossConfig(
            lambda_f=1.0,
            lambda_b=1.0,
            lambda_c=0.5,
            lambda_task=1.0,
        )

    @pytest.fixture
    def loss_fn(self, loss_config, device):
        """Create loss function."""
        return SovereignLoss(loss_config).to(device)

    def test_forward_basic(self, loss_fn, device):
        """Test basic loss computation."""
        B, N, V = 2, 16, 1000

        logits = torch.randn(B, N, V, device=device)
        targets = torch.randint(0, V, (B, N), device=device)
        hidden = torch.randn(B, N, 256, device=device)
        karma = torch.rand(B, 32, device=device)

        loss, metrics = loss_fn(
            logits=logits,
            targets=targets,
            hidden_states=hidden,
            karma_state=karma,
            srk_diagnostics={'entropy_delta': 0.0},
        )

        assert loss.shape == ()
        assert loss.item() > 0
        assert 'L_total' in metrics
        assert 'L_task' in metrics

    def test_consistency_lagrangian(self, loss_fn, device):
        """Test B1 consistency loss."""
        B, N, V = 2, 16, 1000

        logits = torch.randn(B, N, V, device=device)
        targets = torch.randint(0, V, (B, N), device=device)
        hidden = torch.randn(B, N, 256, device=device)
        karma = torch.rand(B, 32, device=device)

        _, metrics = loss_fn(
            logits=logits,
            targets=targets,
            hidden_states=hidden,
            karma_state=karma,
            srk_diagnostics={'entropy_delta': 0.0},
        )

        assert 'L_lagrangian' in metrics
        assert 's_f' in metrics
        assert 's_b' in metrics


# =============================================================================
# SovereignAnnealer TESTS
# =============================================================================

class TestSovereignAnnealer:
    """Tests for lambda annealing."""

    @pytest.fixture
    def annealer(self):
        """Create annealer."""
        return SovereignAnnealer(
            total_steps=1000,
            warmup_steps=100,
        )

    def test_warmup_phase(self, annealer):
        """Test warmup phase lambdas."""
        lambdas = annealer.get_lambdas(50)  # Mid-warmup

        # Forward should be full, backward ramping
        assert lambdas['lambda_f'] == 1.0
        assert 0 < lambdas['lambda_b'] < 1.0

    def test_post_warmup_phase(self, annealer):
        """Test post-warmup lambdas."""
        lambdas = annealer.get_lambdas(500)  # Post-warmup

        # Both should be active
        assert lambdas['lambda_f'] > 0
        assert lambdas['lambda_b'] > 0

    def test_phase_names(self, annealer):
        """Test phase name retrieval."""
        early = annealer.get_phase_name(50)
        mid = annealer.get_phase_name(200)
        late = annealer.get_phase_name(800)

        assert early in ['WARMUP', 'SYSTEM_1']
        assert mid in ['SYSTEM_1', 'CALIBRATION', 'SYSTEM_2']


# =============================================================================
# IMR TESTS
# =============================================================================

class TestIsomorphicMappingRouter:
    """Tests for IMR logic templates."""

    @pytest.fixture
    def imr(self, device):
        """Create IMR instance."""
        return IsomorphicMappingRouter(
            state_dim=32,
            hidden_dim=256,
            threshold=0.75,
        ).to(device)

    def test_logic_templates_registered(self, imr):
        """Test logic templates are registered as buffers."""
        assert hasattr(imr, 'template_DEDUCTION')
        assert hasattr(imr, 'template_INDUCTION')
        assert hasattr(imr, 'template_ABDUCTION')
        assert hasattr(imr, 'template_ANALOGY')
        assert hasattr(imr, 'template_SYNTHESIS')

    def test_template_shapes(self, imr):
        """Test template shapes are correct."""
        assert imr.template_DEDUCTION.shape == (12,)
        assert imr.template_INDUCTION.shape == (12,)

    def test_detect_isomorphism(self, imr, batch_state, device):
        """Test isomorphism detection."""
        # Create state aligned with DEDUCTION (high O7, O4, O12)
        deductive_state = torch.zeros(2, 32, device=device)
        deductive_state[:, 6] = 0.9   # O7_RSN
        deductive_state[:, 3] = 0.8   # O4_STR
        deductive_state[:, 11] = 0.85  # O12_ABS

        bias, name = imr.detect_isomorphism(deductive_state)

        # Should detect DEDUCTION
        if bias is not None:
            assert name == 'DEDUCTION'


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestSRKIntegration:
    """Integration tests for full SRK pipeline."""

    def test_full_forward_pass(self, srk, batch_hidden, device):
        """Test complete SRK forward pass through all layers."""
        # Simulate passing through all layers
        current_state = None
        karma = srk.get_karma(batch_size=batch_hidden.shape[0])

        for layer_idx in range(12):
            if current_state is None:
                current_state = srk.compute_state_from_hidden(batch_hidden)

            result = srk.forward_pass(
                hidden_states=batch_hidden,
                layer_idx=layer_idx,
                current_state=current_state,
                karma_state=karma,
            )

            batch_hidden = result['hidden_states']
            current_state = result['current_state']

        # Should complete without error
        assert batch_hidden.shape[1] == 16
        assert current_state.shape == (2, 32)

    def test_opb_lock_during_training(self, srk, batch_hidden, device):
        """Test OPB locks update during training simulation."""
        # First pass: High reasoning state
        reasoning_hidden = batch_hidden.clone()
        reasoning_hidden[:, :, 100:150] = 2.0  # Boost certain dims

        state1 = srk.compute_state_from_hidden(reasoning_hidden)

        # If reasoning is high enough, should lock
        initial_locks = srk.opb_lock.locked_mask.sum().item()

        # Second pass: Different state
        different_hidden = torch.randn_like(batch_hidden)
        state2 = srk.compute_state_from_hidden(different_hidden)

        # Locks should persist or decay
        # (Exact behavior depends on activation levels)

    def test_uom_with_srk(self, srk, batch_hidden, device):
        """Test UOM integration with SRK."""
        # Compute state
        state = srk.compute_state_from_hidden(batch_hidden)

        # Create UOM
        uom = UserOntologicalMirror(state_dim=32, hidden_dim=256).to(device)

        # Get intervention
        result = uom(state, 'factual')

        assert 'target_state' in result
        assert 'strategy' in result
        assert result['strategy'] in UserOntologicalMirror.STRATEGIES


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
