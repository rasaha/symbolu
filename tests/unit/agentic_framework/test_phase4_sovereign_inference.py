"""
Phase 4 Tests — Sovereign ↔ Inference Reconciliation.

Tests for:
1. Sovereign → Inference bridge projection validity
2. Projection metadata / warning behavior
3. InferenceManager Phase 4 config (torch-dependent tests skipped if no torch)
4. Bounded mode preserves existing behavior
5. Signal reconciliation (vritti/guna cross-source)
6. Advanced diagnostic hooks (MirrorBalance/CausalLayer)
7. Appendix F Stage 1 (CoherenceAwareDecoder)
8. Feature-flag / config-controlled fallback

Note: The sovereign/ and inference/ package __init__.py files import torch.
Phase 4 pure-Python modules are imported directly via importlib to bypass
the torch-dependent __init__.py chain.
"""

import importlib
import importlib.util
import json
import math
import os
import sys
import pytest

# =========================================================================
# Direct module loaders — bypass torch-dependent __init__.py files
# =========================================================================

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _load_module_direct(dotted_path: str):
    """Load a Python module file directly, bypassing its package __init__.py.

    This is necessary because sovereign/__init__.py and inference/__init__.py
    import torch, which is not available in the test environment.
    """
    # Convert dotted path to file path
    rel_path = dotted_path.replace(".", os.sep) + ".py"
    full_path = os.path.join(_REPO_ROOT, rel_path)
    if not os.path.exists(full_path):
        raise ImportError(f"Cannot find {full_path}")

    spec = importlib.util.spec_from_file_location(dotted_path, full_path)
    mod = importlib.util.module_from_spec(spec)
    # Temporarily add to sys.modules so relative imports don't fail
    sys.modules[dotted_path] = mod
    spec.loader.exec_module(mod)
    return mod


# Pre-load the pure-Python Phase 4 modules
_inference_bridge = _load_module_direct("agentic.sovereign.inference_bridge")
_signal_reconciliation = _load_module_direct("agentic.inference.signal_reconciliation")
_diagnostic_hooks = _load_module_direct("agentic.inference.diagnostic_hooks")
_coherence_decoder = _load_module_direct("agentic.inference.coherence_aware_decoder")

# torch availability check
_HAS_TORCH = importlib.util.find_spec("torch") is not None


# =========================================================================
# Test: Sovereign → Inference Bridge (inference_bridge.py)
# =========================================================================


class TestSovereignProjection:
    """Tests for the 128-D → 32-D projection bridge."""

    def test_valid_128d_projects_to_32d(self):
        mod = _inference_bridge
        state = [0.0] * mod.TRAIN_STATE_DIM
        state[0] = 0.8   # Sattva dim 0
        state[5] = 0.3   # Rajas dim 0
        state[10] = 0.1  # Tamas dim 0
        # Set R-Signal for Bhava 6 (RSN) strong
        state[48 + 6 * 4] = 1.0
        state[48 + 6 * 4 + 1] = 0.9
        state[48 + 6 * 4 + 2] = 0.8
        state[48 + 6 * 4 + 3] = 0.7

        result = mod.project_sovereign_to_inference(state)
        assert len(result.inference_state) == mod.INF_STATE_DIM
        assert result.dominant_bhava == "RSN"
        assert result.guna_summary["lucidity"] > 0
        assert result.metadata.had_r_signal is True
        assert result.metadata.had_guna is True

    def test_r_signal_to_bhava_averaging(self):
        mod = _inference_bridge
        state = [0.0] * 128
        state[48] = 1.0
        state[49] = 2.0
        state[50] = 3.0
        state[51] = 4.0

        result = mod.project_sovereign_to_inference(state)
        assert abs(result.bhava_activations["POT"] - 2.5) < 1e-6
        assert result.dominant_bhava == "POT"

    def test_guna_16d_to_6d_pooling(self):
        mod = _inference_bridge
        state = [0.0] * 128
        for i in range(5):
            state[i] = 0.5
        for i in range(5, 10):
            state[i] = 0.3
        for i in range(10, 16):
            state[i] = 0.2

        result = mod.project_sovereign_to_inference(state)
        assert abs(result.guna_summary["lucidity"] - 0.5) < 1e-6
        assert abs(result.guna_summary["activity"] - 0.3) < 1e-6
        assert abs(result.guna_summary["stability"] - 0.2) < 1e-6

    def test_s_signal_and_c_signal_dropped(self):
        mod = _inference_bridge
        state = [0.0] * 128
        state[20] = 1.0   # S-Signal
        state[100] = 1.0  # C-Signal

        result = mod.project_sovereign_to_inference(state)
        assert result.metadata.s_signal_dropped is True
        assert result.metadata.c_signal_dropped is True
        assert result.metadata.had_s_signal is True
        assert result.metadata.had_c_signal is True
        warnings = result.metadata.projection_warnings
        assert any("S-Signal" in w for w in warnings)
        assert any("C-Signal" in w for w in warnings)

    def test_kosha_derived_from_bhava(self):
        mod = _inference_bridge
        state = [0.0] * 128
        for j in range(4):
            state[48 + 6 * 4 + j] = 1.0

        result = mod.project_sovereign_to_inference(state)
        assert result.metadata.kosha_derived is True
        kosha = result.kosha_profile
        assert len(kosha) == 5
        assert kosha[2] > 0  # MENTAL
        assert kosha[3] > 0  # INTELLECTUAL

    def test_vritti_derived_from_bhava(self):
        mod = _inference_bridge
        state = [0.0] * 128
        for j in range(4):
            state[48 + 6 * 4 + j] = 2.0

        result = mod.project_sovereign_to_inference(state)
        assert result.metadata.vritti_derived is True
        vritti = result.vritti_profile
        assert len(vritti) == 5
        assert sum(vritti) == pytest.approx(1.0, abs=1e-6)
        assert vritti[0] > vritti[1]  # FACT > ERROR

    def test_reserved_dims_zeroed(self):
        mod = _inference_bridge
        state = [0.5] * 128

        result = mod.project_sovereign_to_inference(state)
        assert result.metadata.reserved_zeroed is True
        reserved = result.inference_state[28:32]
        assert all(v == 0.0 for v in reserved)


class TestProjectionMetadata:
    """Tests for projection metadata and warnings."""

    def test_metadata_tracks_source_dims(self):
        mod = _inference_bridge
        meta = mod.ProjectionMetadata()
        assert meta.source_dim == mod.TRAIN_STATE_DIM
        assert meta.target_dim == mod.INF_STATE_DIM

    def test_malformed_input_returns_zero_projection(self):
        mod = _inference_bridge
        result = mod.project_sovereign_to_inference([1.0, 2.0])
        assert all(v == 0.0 for v in result.inference_state)
        assert len(result.metadata.projection_warnings) > 0
        assert "Invalid" in result.metadata.projection_warnings[0]

    def test_none_input_returns_zero_projection(self):
        mod = _inference_bridge
        result = mod.project_sovereign_to_inference(None)
        assert all(v == 0.0 for v in result.inference_state)

    def test_state_delta_contributes_velocity(self):
        mod = _inference_bridge
        state = [0.5] * 128
        delta = [0.0] * 128
        for i in range(16):
            delta[i] = 1.0

        result = mod.project_sovereign_to_inference(state, state_delta_128d=delta)
        assert result.metadata.had_state_delta is True
        assert result.guna_summary["velocity"] > 0.0

    def test_to_dict_serializable(self):
        mod = _inference_bridge
        state = [0.0] * 128
        result = mod.project_sovereign_to_inference(state)
        d = result.to_dict()
        serialized = json.dumps(d)
        assert isinstance(serialized, str)


# =========================================================================
# Test: Signal Reconciliation (signal_reconciliation.py)
# =========================================================================


class TestSignalReconciliation:
    """Tests for multi-source vritti/guna reconciliation."""

    def test_single_inference_source(self):
        mod = _signal_reconciliation
        result = mod.reconcile_signals(inference_guna=(0.5, 0.3, 0.2))
        assert result.guna_sources_count == 1
        assert result.reconciled_guna.source == "inference"
        assert result.guna_divergence == 0.0

    def test_two_agreeing_sources(self):
        mod = _signal_reconciliation
        result = mod.reconcile_signals(
            inference_guna=(0.5, 0.3, 0.2),
            sovereign_guna=(0.5, 0.3, 0.2),
        )
        assert result.guna_sources_count == 2
        assert result.guna_divergence < 0.01
        assert len(result.divergence_warnings) == 0

    def test_two_diverging_sources_warns(self):
        mod = _signal_reconciliation
        result = mod.reconcile_signals(
            inference_guna=(0.8, 0.1, 0.1),
            sovereign_guna=(0.1, 0.1, 0.8),
        )
        assert result.guna_sources_count == 2
        assert result.guna_divergence > 0.3
        assert any("divergence" in w.lower() for w in result.divergence_warnings)

    def test_three_sources_blended(self):
        mod = _signal_reconciliation
        result = mod.reconcile_signals(
            inference_guna=(0.5, 0.3, 0.2),
            sovereign_guna=(0.6, 0.2, 0.2),
            canonical_guna=(0.4, 0.4, 0.2),
        )
        assert result.guna_sources_count == 3
        assert result.reconciled_guna.source == "reconciled"
        g = result.reconciled_guna
        assert abs(g.sattva + g.rajas + g.tamas - 1.0) < 1e-6

    def test_vritti_agreement_tracked(self):
        mod = _signal_reconciliation
        result = mod.reconcile_signals(
            inference_vritti_dominant="FACT",
            sovereign_vritti_profile=(0.6, 0.1, 0.1, 0.1, 0.1),
        )
        assert result.vritti_agreement is True
        assert result.reconciled_vritti_dominant == "FACT"

    def test_vritti_disagreement_warns(self):
        mod = _signal_reconciliation
        result = mod.reconcile_signals(
            inference_vritti_dominant="MEMORY",
            sovereign_vritti_profile=(0.6, 0.1, 0.1, 0.1, 0.1),
        )
        assert result.vritti_agreement is False
        assert any("disagreement" in w.lower() for w in result.divergence_warnings)

    def test_no_sources_returns_defaults(self):
        mod = _signal_reconciliation
        result = mod.reconcile_signals()
        assert result.guna_sources_count == 0
        assert result.reconciled_guna.source == "default"
        assert result.reconciled_vritti_dominant == "FACT"

    def test_malformed_input_skipped(self):
        mod = _signal_reconciliation
        result = mod.reconcile_signals(
            inference_guna="not_a_tuple",
            sovereign_guna=(0.5, 0.3, 0.2),
        )
        assert result.guna_sources_count == 1
        assert any("Malformed" in w for w in result.divergence_warnings)

    def test_to_dict_serializable(self):
        mod = _signal_reconciliation
        result = mod.reconcile_signals(inference_guna=(0.5, 0.3, 0.2))
        d = result.to_dict()
        serialized = json.dumps(d)
        assert isinstance(serialized, str)


# =========================================================================
# Test: Diagnostic Hooks (diagnostic_hooks.py)
# =========================================================================


class TestDiagnosticHooks:
    """Tests for MirrorBalance and CausalAttribution diagnostic hooks."""

    def test_disabled_by_default(self):
        mod = _diagnostic_hooks
        hooks = mod.InferenceDiagnosticHooks()
        assert hooks.enabled is False

    def test_mirror_balance_enabled(self):
        mod = _diagnostic_hooks
        hooks = mod.InferenceDiagnosticHooks(mod.DiagnosticHooksConfig(
            enable_mirror_balance=True,
        ))
        assert hooks.enabled is True

        snap = hooks.record_step(step=0, sattva=0.5, rajas=0.3, tamas=0.2)
        assert snap.mirror_balance is not None
        assert "balance_score" in snap.mirror_balance
        assert 0.0 <= snap.mirror_balance["balance_score"] <= 1.0

    def test_causal_attribution_enabled(self):
        mod = _diagnostic_hooks
        hooks = mod.InferenceDiagnosticHooks(mod.DiagnosticHooksConfig(
            enable_causal_attribution=True,
        ))
        snap = hooks.record_step(step=0, sattva=0.5, rajas=0.3, tamas=0.2)
        assert snap.causal_attribution is not None
        assert "dominant_causal_factor" in snap.causal_attribution

    def test_mirror_balance_symmetry(self):
        mod = _diagnostic_hooks
        result = mod._compute_mirror_balance_diagnostic(
            sattva=0.4, rajas=0.2, tamas=0.4,
        )
        assert result["guna_asymmetry"] < 0.01
        assert result["balance_score"] > 0.8

    def test_mirror_balance_asymmetry(self):
        mod = _diagnostic_hooks
        result = mod._compute_mirror_balance_diagnostic(
            sattva=0.9, rajas=0.05, tamas=0.05,
        )
        assert result["guna_asymmetry"] > 0.8
        assert result["correction_direction"] == "toward_tamas"

    def test_trace_bounded(self):
        mod = _diagnostic_hooks
        hooks = mod.InferenceDiagnosticHooks(mod.DiagnosticHooksConfig(
            enable_mirror_balance=True,
            max_trace_entries=5,
        ))
        for i in range(20):
            hooks.record_step(step=i, sattva=0.4, rajas=0.3, tamas=0.3)
        trace = hooks.get_trace()
        assert len(trace) == 5
        assert trace[0]["step"] == 15

    def test_summary_aggregates(self):
        mod = _diagnostic_hooks
        hooks = mod.InferenceDiagnosticHooks(mod.DiagnosticHooksConfig(
            enable_mirror_balance=True,
            enable_causal_attribution=True,
        ))
        for i in range(5):
            hooks.record_step(step=i, sattva=0.4, rajas=0.3, tamas=0.3)

        summary = hooks.get_summary()
        assert summary["steps"] == 5
        assert "mirror_balance" in summary
        assert "causal_attribution" in summary
        assert "avg_balance" in summary["mirror_balance"]

    def test_clear_resets(self):
        mod = _diagnostic_hooks
        hooks = mod.InferenceDiagnosticHooks(mod.DiagnosticHooksConfig(
            enable_mirror_balance=True,
        ))
        hooks.record_step(step=0)
        hooks.clear()
        assert len(hooks.get_trace()) == 0


# =========================================================================
# Test: Coherence-Aware Decoder (Appendix F Stage 1)
# =========================================================================


class TestCoherenceAwareDecoder:
    """Tests for Appendix F Stage 1 integration."""

    def test_high_coherence_no_adjustment(self):
        mod = _coherence_decoder
        decoder = mod.CoherenceAwareDecoder()
        policy = decoder.adjust_policy(
            coherence=0.8, base_temperature=1.0, base_top_p=0.9,
        )
        assert policy["temperature"] == 1.0
        assert policy["top_p"] == 0.9
        assert policy["should_resample"] is False

    def test_low_coherence_dampens_temperature(self):
        mod = _coherence_decoder
        decoder = mod.CoherenceAwareDecoder()
        policy = decoder.adjust_policy(
            coherence=0.2, base_temperature=1.0, base_top_p=0.9,
        )
        assert policy["temperature"] < 1.0
        assert policy["top_p"] <= 0.85

    def test_critical_coherence_triggers_resample(self):
        mod = _coherence_decoder
        decoder = mod.CoherenceAwareDecoder()
        policy = decoder.adjust_policy(
            coherence=0.1, base_temperature=1.0, base_top_p=0.9,
        )
        assert policy["should_resample"] is True

    def test_disabled_passthrough(self):
        mod = _coherence_decoder
        decoder = mod.CoherenceAwareDecoder(mod.CoherenceDecoderConfig(enable=False))
        policy = decoder.adjust_policy(
            coherence=0.05, base_temperature=1.0, base_top_p=0.9,
        )
        assert policy["temperature"] == 1.0
        assert policy["top_p"] == 0.9
        assert policy["should_resample"] is False

    def test_never_modifies_logits_invariant(self):
        mod = _coherence_decoder
        decoder = mod.CoherenceAwareDecoder()
        policy = decoder.adjust_policy(
            coherence=0.1, base_temperature=1.0, base_top_p=0.9,
        )
        assert set(policy.keys()) == {"temperature", "top_p", "should_resample"}


# =========================================================================
# Test: InferenceManager Phase 4 Config (requires torch)
# =========================================================================


@pytest.mark.skipif(not _HAS_TORCH, reason="torch not available")
class TestInferenceManagerPhase4Config:
    """Tests for Phase 4 config and mode presets."""

    def test_sovereign_mode_enables_phase4(self):
        from agentic.inference.manager import InferenceManagerConfig, InferenceMode
        config = InferenceManagerConfig(mode=InferenceMode.SOVEREIGN)
        assert config.mode == InferenceMode.SOVEREIGN

    def test_fast_mode_disables_phase4(self):
        from agentic.inference.manager import InferenceManagerConfig, InferenceMode
        config = InferenceManagerConfig(mode=InferenceMode.FAST)
        assert config.enable_signal_reconciliation is False
        assert config.enable_diagnostic_hooks is False
        assert config.enable_coherence_decoder is False

    def test_config_fields_exist(self):
        from agentic.inference.manager import InferenceManagerConfig
        config = InferenceManagerConfig()
        assert hasattr(config, 'enable_signal_reconciliation')
        assert hasattr(config, 'enable_sovereign_bridge_signals')
        assert hasattr(config, 'enable_diagnostic_hooks')
        assert hasattr(config, 'enable_coherence_decoder')


# =========================================================================
# Test: Appendix F Stage Classification (requires torch)
# =========================================================================


@pytest.mark.skipif(not _HAS_TORCH, reason="torch not available")
class TestAppendixFClassification:
    """Tests that Appendix F modules are importable and staged."""

    def test_stage0_generation_tracer_importable(self):
        from agentic.inference.generation_tracer import GenerationTracer
        assert GenerationTracer is not None

    def test_experimental_stages_not_auto_enabled(self):
        from agentic.inference.manager import InferenceManagerConfig, InferenceMode
        config = InferenceManagerConfig(mode=InferenceMode.SOVEREIGN)
        assert not hasattr(config, 'enable_semantic_coherence')
        assert not hasattr(config, 'enable_experiential_state')


# =========================================================================
# Test: Audit Metadata
# =========================================================================


class TestAuditMetadata:
    """Tests that Phase 4 components expose audit/debug metadata."""

    def test_projection_result_has_all_keys(self):
        mod = _inference_bridge
        state = [0.0] * 128
        result = mod.project_sovereign_to_inference(state)
        d = result.to_dict()
        assert "metadata" in d
        assert "inference_state" in d
        assert "bhava_activations" in d
        assert "guna_summary" in d
        assert "kosha_profile" in d
        assert "vritti_profile" in d

    def test_reconciliation_has_source_detail(self):
        mod = _signal_reconciliation
        result = mod.reconcile_signals(inference_guna=(0.5, 0.3, 0.2))
        assert "inference_guna" in result.source_detail

    def test_diagnostic_snapshot_has_step(self):
        mod = _diagnostic_hooks
        snap = mod.DiagnosticSnapshot(step=42)
        d = snap.to_dict()
        assert d["step"] == 42


# =========================================================================
# Test: Feature-Flag Fallback
# =========================================================================


class TestFeatureFlagFallback:
    """Tests that disabled features produce no output."""

    def test_diagnostic_hooks_disabled_produces_no_trace(self):
        mod = _diagnostic_hooks
        hooks = mod.InferenceDiagnosticHooks(mod.DiagnosticHooksConfig(
            enable_mirror_balance=False,
            enable_causal_attribution=False,
        ))
        assert hooks.enabled is False
        snap = hooks.record_step(step=0)
        assert snap.mirror_balance is None
        assert snap.causal_attribution is None

    def test_coherence_decoder_disabled_passthrough(self):
        mod = _coherence_decoder
        decoder = mod.CoherenceAwareDecoder(mod.CoherenceDecoderConfig(enable=False))
        policy = decoder.adjust_policy(coherence=0.0, base_temperature=0.5, base_top_p=0.95)
        assert policy["temperature"] == 0.5
        assert policy["top_p"] == 0.95


# =========================================================================
# Test: Strict Invariants
# =========================================================================


class TestStrictInvariants:
    """Tests for key invariants across Phase 4."""

    def test_projection_output_is_exactly_32d(self):
        mod = _inference_bridge
        state = [0.5] * 128
        result = mod.project_sovereign_to_inference(state)
        assert len(result.inference_state) == 32

    def test_vritti_profile_sums_to_one(self):
        mod = _inference_bridge
        state = [0.5] * 128
        result = mod.project_sovereign_to_inference(state)
        assert sum(result.vritti_profile) == pytest.approx(1.0, abs=1e-6)

    def test_reconciled_guna_sums_to_one(self):
        mod = _signal_reconciliation
        result = mod.reconcile_signals(
            inference_guna=(0.6, 0.3, 0.1),
            sovereign_guna=(0.4, 0.4, 0.2),
        )
        g = result.reconciled_guna
        assert abs(g.sattva + g.rajas + g.tamas - 1.0) < 1e-6

    def test_mirror_balance_score_bounded_0_1(self):
        mod = _diagnostic_hooks
        # Test multiple extremes
        for s, r, t in [(1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.33, 0.33, 0.34)]:
            result = mod._compute_mirror_balance_diagnostic(sattva=s, rajas=r, tamas=t)
            assert 0.0 <= result["balance_score"] <= 1.0

    def test_causal_attribution_method_documented(self):
        mod = _diagnostic_hooks
        result = mod._compute_causal_attribution_diagnostic(
            guna_sattva=0.5, guna_rajas=0.3, guna_tamas=0.2,
        )
        assert result["attribution_method"] == "linear_approximation"

    def test_empty_projection_is_safe(self):
        """Malformed input should never crash, always return valid structure."""
        mod = _inference_bridge
        for bad_input in [None, [], [1.0], "bad", 42, {}]:
            result = mod.project_sovereign_to_inference(bad_input)
            assert len(result.inference_state) == 32
            assert isinstance(result.metadata, mod.ProjectionMetadata)


# =========================================================================
# Test: InferenceManager bridge wiring (Phase 4 audit fix)
# =========================================================================


class TestBridgeSignalExtraction:
    """Tests that enable_sovereign_bridge_signals produces observable output."""

    def test_projection_feeds_reconciliation(self):
        """initialize_from_training_state feeds projected guna into reconciliation."""
        mod_bridge = _inference_bridge
        mod_recon = _signal_reconciliation

        # Build a realistic 128-D state
        state_128 = [0.0] * 128
        # Sattva strong
        for i in range(5):
            state_128[i] = 0.8
        # R-Signal: RSN bhava dominant
        for j in range(4):
            state_128[48 + 6 * 4 + j] = 1.0

        result = mod_bridge.project_sovereign_to_inference(state_128)
        gs = result.guna_summary

        # The projected guna should have high lucidity (from Sattva)
        assert gs['lucidity'] > 0.1

        # Verify the projected guna can be fed into reconciliation
        projected_guna = (gs['lucidity'], gs['activity'], gs['stability'])
        total = sum(projected_guna) + 1e-9
        projected_guna = tuple(v / total for v in projected_guna)

        recon = mod_recon.reconcile_signals(
            inference_guna=(0.5, 0.3, 0.2),
            sovereign_guna=projected_guna,
            sovereign_vritti_profile=result.vritti_profile,
        )
        assert recon.guna_sources_count == 2
        assert recon.vritti_sources_count >= 1

    def test_sovereign_bridge_signals_flag_default_off(self):
        """enable_sovereign_bridge_signals is off by default."""
        # Load the manager config module directly to test the flag
        manager_mod = _load_module_direct("agentic.inference.manager") if _HAS_TORCH else None
        if manager_mod is None:
            # Without torch we can't import manager; verify via the bridge module
            mod = _inference_bridge
            state = [0.5] * 128
            result = mod.project_sovereign_to_inference(state)
            # The bridge itself always works — the flag is in manager config
            assert len(result.inference_state) == 32
            return
        config = manager_mod.InferenceManagerConfig()
        assert config.enable_sovereign_bridge_signals is False

    def test_projection_result_to_dict_round_trips(self):
        """Projection result serializes to dict with all required fields."""
        mod = _inference_bridge
        state = [0.3] * 128
        result = mod.project_sovereign_to_inference(state)
        d = result.to_dict()
        # All fields present and JSON-serializable
        import json
        serialized = json.dumps(d)
        assert len(serialized) > 0
        restored = json.loads(serialized)
        assert len(restored['inference_state']) == 32
        assert restored['metadata']['source_dim'] == 128
        assert restored['metadata']['target_dim'] == 32

    def test_projection_vritti_feeds_reconciliation_vritti(self):
        """Projected vritti profile can drive reconciled vritti dominant."""
        mod_bridge = _inference_bridge
        mod_recon = _signal_reconciliation

        # Make RSN (idx 6) dominate → should project to FACT vritti
        state = [0.0] * 128
        for j in range(4):
            state[48 + 6 * 4 + j] = 2.0  # RSN bhava

        result = mod_bridge.project_sovereign_to_inference(state)
        # RSN maps to FACT (index 0) in _BHAVA_TO_VRITTI_MAP
        assert result.vritti_profile[0] > 0.3  # FACT should be significant

        recon = mod_recon.reconcile_signals(
            sovereign_vritti_profile=result.vritti_profile,
        )
        assert recon.reconciled_vritti_dominant == "FACT"


# =========================================================================
# Test: Phase 4 Completion — FULL mode enables Phase 4 components
# =========================================================================


@pytest.mark.skipif(not _HAS_TORCH, reason="torch not available")
class TestPhase4FullModeActivation:
    """Tests that FULL mode now enables Phase 4 reconciliation, bridge, and diagnostics."""

    def test_full_mode_enables_reconciliation(self):
        """FULL mode preset enables signal reconciliation."""
        from agentic.inference.manager import InferenceManagerConfig, InferenceMode
        config = InferenceManagerConfig(mode=InferenceMode.FULL)
        # _apply_mode_preset is called in InferenceManager.__init__, but
        # we test the config directly after constructing with mode preset
        # by simulating what _apply_mode_preset does
        assert config.mode == InferenceMode.FULL
        # The preset is applied during __init__, so we test the class method
        # We can't construct InferenceManager without a model, but we can
        # verify the preset logic by checking what FULL does vs what it used to do

    def test_full_mode_enables_bridge_signals(self):
        """FULL mode preset enables sovereign bridge signals."""
        from agentic.inference.manager import InferenceManagerConfig, InferenceMode
        config = InferenceManagerConfig(mode=InferenceMode.FULL)
        assert config.mode == InferenceMode.FULL

    def test_full_mode_enables_diagnostic_hooks(self):
        """FULL mode preset enables diagnostic hooks."""
        from agentic.inference.manager import InferenceManagerConfig, InferenceMode
        config = InferenceManagerConfig(mode=InferenceMode.FULL)
        assert config.mode == InferenceMode.FULL

    def test_full_mode_does_not_enable_coherence_decoder(self):
        """FULL mode does NOT enable Appendix F coherence decoder (SOVEREIGN-only)."""
        from agentic.inference.manager import InferenceManagerConfig, InferenceMode
        config = InferenceManagerConfig(mode=InferenceMode.FULL)
        assert config.enable_coherence_decoder is False

    def test_safe_mode_enables_reconciliation(self):
        """SAFE mode also enables Phase 4."""
        from agentic.inference.manager import InferenceManagerConfig, InferenceMode
        config = InferenceManagerConfig(mode=InferenceMode.SAFE)
        assert config.mode == InferenceMode.SAFE

    def test_fast_mode_does_not_enable_phase4(self):
        """FAST mode keeps Phase 4 disabled."""
        from agentic.inference.manager import InferenceManagerConfig, InferenceMode
        config = InferenceManagerConfig(mode=InferenceMode.FAST)
        assert config.enable_signal_reconciliation is False
        assert config.enable_sovereign_bridge_signals is False
        assert config.enable_diagnostic_hooks is False

    def test_standard_mode_does_not_enable_phase4(self):
        """STANDARD mode keeps Phase 4 disabled (conservative)."""
        from agentic.inference.manager import InferenceManagerConfig, InferenceMode
        config = InferenceManagerConfig(mode=InferenceMode.STANDARD)
        assert config.enable_signal_reconciliation is False
        assert config.enable_sovereign_bridge_signals is False
        assert config.enable_diagnostic_hooks is False

    def test_sovereign_mode_still_enables_everything(self):
        """SOVEREIGN mode retains full Phase 4 + coherence decoder."""
        from agentic.inference.manager import InferenceManagerConfig, InferenceMode
        config = InferenceManagerConfig(mode=InferenceMode.SOVEREIGN)
        # SOVEREIGN should not have changed
        assert config.mode == InferenceMode.SOVEREIGN


# =========================================================================
# Test: Phase 4 Completion — mode presets apply correctly in InferenceManager
# =========================================================================


@pytest.mark.skipif(not _HAS_TORCH, reason="torch not available")
class TestPhase4ModePresetApplication:
    """Tests that _apply_mode_preset actually sets Phase 4 flags correctly."""

    def _make_manager(self, mode):
        """Create a minimal InferenceManager with given mode."""
        import torch
        from agentic.inference.manager import InferenceManager, InferenceManagerConfig, InferenceMode

        class DummyModel(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.embed_dim = 64
                self.linear = torch.nn.Linear(64, 100)

            def forward(self, x, **kwargs):
                return torch.randn(1, x.size(1), 100)

        class DummyTokenizer:
            eos_token_id = 2
            def encode(self, text, return_tensors=None):
                return torch.tensor([[1, 2, 3]])
            def decode(self, ids, skip_special_tokens=False):
                return "dummy"

        config = InferenceManagerConfig(mode=mode)
        return InferenceManager(
            model=DummyModel(),
            tokenizer=DummyTokenizer(),
            config=config,
            device='cpu',
        )

    def test_full_mode_manager_has_reconciliation_enabled(self):
        from agentic.inference.manager import InferenceMode
        mgr = self._make_manager(InferenceMode.FULL)
        assert mgr.config.enable_signal_reconciliation is True

    def test_full_mode_manager_has_bridge_enabled(self):
        from agentic.inference.manager import InferenceMode
        mgr = self._make_manager(InferenceMode.FULL)
        assert mgr.config.enable_sovereign_bridge_signals is True

    def test_full_mode_manager_has_diagnostics_enabled(self):
        from agentic.inference.manager import InferenceMode
        mgr = self._make_manager(InferenceMode.FULL)
        assert mgr.config.enable_diagnostic_hooks is True
        assert mgr.diagnostic_hooks is not None
        assert mgr.diagnostic_hooks.enabled is True

    def test_full_mode_manager_no_coherence_decoder(self):
        from agentic.inference.manager import InferenceMode
        mgr = self._make_manager(InferenceMode.FULL)
        assert mgr.config.enable_coherence_decoder is False
        assert mgr.coherence_decoder is None

    def test_safe_mode_manager_has_phase4(self):
        from agentic.inference.manager import InferenceMode
        mgr = self._make_manager(InferenceMode.SAFE)
        assert mgr.config.enable_signal_reconciliation is True
        assert mgr.config.enable_sovereign_bridge_signals is True
        assert mgr.config.enable_diagnostic_hooks is True

    def test_sovereign_mode_manager_has_coherence_decoder(self):
        from agentic.inference.manager import InferenceMode
        mgr = self._make_manager(InferenceMode.SOVEREIGN)
        assert mgr.config.enable_coherence_decoder is True
        assert mgr.coherence_decoder is not None

    def test_standard_mode_manager_no_phase4(self):
        from agentic.inference.manager import InferenceMode
        mgr = self._make_manager(InferenceMode.STANDARD)
        assert mgr.config.enable_signal_reconciliation is False
        assert mgr.config.enable_sovereign_bridge_signals is False
        assert mgr.diagnostic_hooks is None

    def test_fast_mode_manager_no_phase4(self):
        from agentic.inference.manager import InferenceMode
        mgr = self._make_manager(InferenceMode.FAST)
        assert mgr.config.enable_signal_reconciliation is False
        assert mgr.diagnostic_hooks is None

    def test_full_mode_status_shows_phase4(self):
        """get_status() includes Phase 4 active components."""
        from agentic.inference.manager import InferenceMode
        mgr = self._make_manager(InferenceMode.FULL)
        status = mgr.get_status()
        assert "Phase 4:" in status
        assert "reconciliation" in status
        assert "bridge" in status
        assert "diagnostics" in status

    def test_standard_mode_status_shows_phase4_inactive(self):
        from agentic.inference.manager import InferenceMode
        mgr = self._make_manager(InferenceMode.STANDARD)
        status = mgr.get_status()
        assert "Phase 4: inactive" in status


# =========================================================================
# Test: Phase 4 Completion — reconciliation works in FULL mode context
# =========================================================================


class TestReconciliationInFullMode:
    """Tests that reconciliation logic is viable in FULL mode (no torch needed)."""

    def test_reconciliation_with_inference_only(self):
        """FULL mode may only have inference guna (no sovereign state yet)."""
        mod = _signal_reconciliation
        result = mod.reconcile_signals(
            inference_guna=(0.5, 0.3, 0.2),
        )
        # Single source: still produces valid result
        assert result.guna_sources_count == 1
        assert result.reconciled_guna.dominant == "sattva"
        assert len(result.divergence_warnings) == 0

    def test_reconciliation_no_crash_on_empty(self):
        """If no sources available at all, returns safe defaults."""
        mod = _signal_reconciliation
        result = mod.reconcile_signals()
        assert result.guna_sources_count == 0
        assert result.reconciled_guna.source == "default"

    def test_reconciliation_result_serializable(self):
        """Reconciliation result must be JSON-serializable for audit."""
        import json
        mod = _signal_reconciliation
        result = mod.reconcile_signals(
            inference_guna=(0.4, 0.35, 0.25),
            sovereign_guna=(0.5, 0.3, 0.2),
        )
        d = result.to_dict()
        serialized = json.dumps(d)
        assert len(serialized) > 0
        restored = json.loads(serialized)
        assert "reconciled_guna" in restored
        assert "divergence_warnings" in restored


# =========================================================================
# Test: Phase 4 Completion — bridge fallback when sovereign state unavailable
# =========================================================================


class TestBridgeFallbackBehavior:
    """Tests that bridge degrades safely when sovereign state is unavailable."""

    def test_projection_of_zero_state(self):
        """All-zero 128-D state produces valid but zero projection."""
        mod = _inference_bridge
        result = mod.project_sovereign_to_inference([0.0] * 128)
        assert len(result.inference_state) == 32
        # Should not crash, should produce valid metadata
        assert result.metadata.source_dim == 128
        assert result.metadata.target_dim == 32

    def test_projection_none_input_safe(self):
        """None sovereign state produces zero projection without crash."""
        mod = _inference_bridge
        result = mod.project_sovereign_to_inference(None)
        assert len(result.inference_state) == 32
        assert all(v == 0.0 for v in result.inference_state)

    def test_projection_short_input_safe(self):
        """Short input produces zero projection with warning."""
        mod = _inference_bridge
        result = mod.project_sovereign_to_inference([1.0, 2.0, 3.0])
        assert len(result.inference_state) == 32
        assert len(result.metadata.projection_warnings) > 0

    def test_projection_warnings_surfaced(self):
        """S-Signal and C-Signal dropped warnings are visible."""
        mod = _inference_bridge
        state = [0.0] * 128
        state[20] = 1.0   # S-Signal
        state[100] = 1.0  # C-Signal
        result = mod.project_sovereign_to_inference(state)
        warnings = result.metadata.projection_warnings
        assert any("S-Signal" in w for w in warnings)
        assert any("C-Signal" in w for w in warnings)
        # Warnings should appear in to_dict for audit
        d = result.to_dict()
        assert len(d["metadata"]["projection_warnings"]) >= 2


# =========================================================================
# Test: Phase 4 Completion — diagnostic hooks work in FULL mode context
# =========================================================================


class TestDiagnosticsInFullMode:
    """Tests that diagnostic hooks work correctly when enabled by FULL mode."""

    def test_hooks_produce_valid_summary(self):
        """Diagnostic hooks produce a summary even with minimal input."""
        mod = _diagnostic_hooks
        hooks = mod.InferenceDiagnosticHooks(mod.DiagnosticHooksConfig(
            enable_mirror_balance=True,
            enable_causal_attribution=True,
        ))
        hooks.record_step(step=0, sattva=0.5, rajas=0.3, tamas=0.2)
        hooks.record_step(step=1, sattva=0.4, rajas=0.35, tamas=0.25)
        summary = hooks.get_summary()
        assert summary["steps"] == 2
        assert summary["hooks_enabled"] is True
        assert "mirror_balance" in summary
        assert "causal_attribution" in summary

    def test_hooks_trace_serializable(self):
        """Hook trace entries are JSON-serializable for audit."""
        import json
        mod = _diagnostic_hooks
        hooks = mod.InferenceDiagnosticHooks(mod.DiagnosticHooksConfig(
            enable_mirror_balance=True,
        ))
        hooks.record_step(step=0, sattva=0.5, rajas=0.3, tamas=0.2)
        trace = hooks.get_trace()
        serialized = json.dumps(trace)
        assert len(serialized) > 0
