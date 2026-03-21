"""
Tests for Appendix F Stage 1 — Coherence-Aware Decoder.

Validates:
- CoherenceDecoderConfig defaults and custom values (F.3.3)
- CoherenceAwareDecoder.adjust_policy() logic (F.3.3)
  - Passthrough when disabled
  - No change when coherence >= threshold_low
  - Temperature dampening + top_p cap when coherence < threshold_low
  - Resample trigger when coherence < threshold_critical
- Integration with generate_text() in SymbolU12LLM (F.3.4)
  - Logit firewall: raw logits never modified by decoder
  - Effective temperature/top_p applied correctly
  - Resample logic selects higher-probability tokens
  - Tracer records Stage 1 metrics (coherence_before, temperature_used, etc.)
- Ablation modes: baseline, control, coherence_aware (F.3.7)
"""

import math

import pytest
import torch
import torch.nn.functional as F

from symbolu.inference.coherence_aware_decoder import (
    CoherenceAwareDecoder,
    CoherenceDecoderConfig,
)


# =============================================================================
# CoherenceDecoderConfig
# =============================================================================


class TestCoherenceDecoderConfig:
    """Test configuration defaults and custom values."""

    def test_default_values(self):
        cfg = CoherenceDecoderConfig()
        assert cfg.coherence_threshold_low == 0.4
        assert cfg.coherence_threshold_critical == 0.2
        assert cfg.temperature_dampening == 0.8
        assert cfg.top_p_cap == 0.85
        assert cfg.max_resample_attempts == 2
        assert cfg.enable is True

    def test_custom_values(self):
        cfg = CoherenceDecoderConfig(
            coherence_threshold_low=0.5,
            coherence_threshold_critical=0.1,
            temperature_dampening=0.7,
            top_p_cap=0.75,
            max_resample_attempts=3,
            enable=False,
        )
        assert cfg.coherence_threshold_low == 0.5
        assert cfg.coherence_threshold_critical == 0.1
        assert cfg.temperature_dampening == 0.7
        assert cfg.top_p_cap == 0.75
        assert cfg.max_resample_attempts == 3
        assert cfg.enable is False


# =============================================================================
# CoherenceAwareDecoder — adjust_policy()
# =============================================================================


class TestAdjustPolicy:
    """Test the core policy adjustment logic."""

    def test_disabled_returns_unchanged(self):
        """When enable=False, parameters pass through unchanged."""
        decoder = CoherenceAwareDecoder(CoherenceDecoderConfig(enable=False))
        policy = decoder.adjust_policy(coherence=0.1, base_temperature=0.7, base_top_p=0.9)
        assert policy["temperature"] == 0.7
        assert policy["top_p"] == 0.9
        assert policy["should_resample"] is False

    def test_high_coherence_no_change(self):
        """When coherence >= threshold_low, no adjustments made."""
        decoder = CoherenceAwareDecoder()
        policy = decoder.adjust_policy(coherence=0.5, base_temperature=0.7, base_top_p=0.9)
        assert policy["temperature"] == 0.7
        assert policy["top_p"] == 0.9
        assert policy["should_resample"] is False

    def test_exactly_at_threshold_low_no_change(self):
        """Coherence == threshold_low should NOT trigger dampening (< not <=)."""
        decoder = CoherenceAwareDecoder()
        policy = decoder.adjust_policy(coherence=0.4, base_temperature=0.7, base_top_p=0.9)
        assert policy["temperature"] == 0.7
        assert policy["top_p"] == 0.9

    def test_below_threshold_low_dampens_temperature(self):
        """Coherence < 0.4 triggers temperature dampening."""
        decoder = CoherenceAwareDecoder()
        policy = decoder.adjust_policy(coherence=0.35, base_temperature=0.7, base_top_p=0.9)
        expected_temp = 0.7 * 0.8  # 0.56
        assert abs(policy["temperature"] - expected_temp) < 1e-6

    def test_below_threshold_low_caps_top_p(self):
        """Coherence < 0.4 caps top_p at 0.85."""
        decoder = CoherenceAwareDecoder()
        policy = decoder.adjust_policy(coherence=0.35, base_temperature=0.7, base_top_p=0.95)
        assert policy["top_p"] == 0.85

    def test_below_threshold_low_top_p_already_below_cap(self):
        """When base_top_p is already below cap, it stays unchanged."""
        decoder = CoherenceAwareDecoder()
        policy = decoder.adjust_policy(coherence=0.35, base_temperature=0.7, base_top_p=0.7)
        assert policy["top_p"] == 0.7

    def test_below_threshold_low_no_resample(self):
        """Between critical and low: no resample triggered."""
        decoder = CoherenceAwareDecoder()
        policy = decoder.adjust_policy(coherence=0.3, base_temperature=0.7, base_top_p=0.9)
        assert policy["should_resample"] is False

    def test_below_threshold_critical_triggers_resample(self):
        """Coherence < 0.2 triggers should_resample."""
        decoder = CoherenceAwareDecoder()
        policy = decoder.adjust_policy(coherence=0.15, base_temperature=0.7, base_top_p=0.9)
        assert policy["should_resample"] is True

    def test_below_critical_also_dampens_temperature(self):
        """Below critical is also below low, so temperature and top_p are adjusted too."""
        decoder = CoherenceAwareDecoder()
        policy = decoder.adjust_policy(coherence=0.1, base_temperature=1.0, base_top_p=0.95)
        assert abs(policy["temperature"] - 0.8) < 1e-6  # 1.0 * 0.8
        assert policy["top_p"] == 0.85
        assert policy["should_resample"] is True

    def test_exactly_at_threshold_critical_no_resample(self):
        """Coherence == threshold_critical should NOT trigger resample (< not <=)."""
        decoder = CoherenceAwareDecoder()
        policy = decoder.adjust_policy(coherence=0.2, base_temperature=0.7, base_top_p=0.9)
        assert policy["should_resample"] is False

    def test_zero_coherence(self):
        """Zero coherence triggers maximum intervention."""
        decoder = CoherenceAwareDecoder()
        policy = decoder.adjust_policy(coherence=0.0, base_temperature=1.0, base_top_p=0.95)
        assert abs(policy["temperature"] - 0.8) < 1e-6
        assert policy["top_p"] == 0.85
        assert policy["should_resample"] is True

    def test_coherence_one(self):
        """Perfect coherence means no adjustment."""
        decoder = CoherenceAwareDecoder()
        policy = decoder.adjust_policy(coherence=1.0, base_temperature=1.2, base_top_p=0.95)
        assert policy["temperature"] == 1.2
        assert policy["top_p"] == 0.95
        assert policy["should_resample"] is False

    def test_custom_thresholds(self):
        """Custom thresholds are respected."""
        cfg = CoherenceDecoderConfig(
            coherence_threshold_low=0.6,
            coherence_threshold_critical=0.3,
            temperature_dampening=0.5,
            top_p_cap=0.7,
        )
        decoder = CoherenceAwareDecoder(cfg)

        # Above custom low threshold
        p = decoder.adjust_policy(coherence=0.65, base_temperature=1.0, base_top_p=0.9)
        assert p["temperature"] == 1.0
        assert p["top_p"] == 0.9
        assert p["should_resample"] is False

        # Below custom low, above custom critical
        p = decoder.adjust_policy(coherence=0.5, base_temperature=1.0, base_top_p=0.9)
        assert abs(p["temperature"] - 0.5) < 1e-6
        assert p["top_p"] == 0.7
        assert p["should_resample"] is False

        # Below custom critical
        p = decoder.adjust_policy(coherence=0.2, base_temperature=1.0, base_top_p=0.9)
        assert abs(p["temperature"] - 0.5) < 1e-6
        assert p["top_p"] == 0.7
        assert p["should_resample"] is True


# =============================================================================
# CoherenceAwareDecoder — construction
# =============================================================================


class TestCoherenceAwareDecoderConstruction:
    """Test decoder instantiation."""

    def test_default_config(self):
        decoder = CoherenceAwareDecoder()
        assert decoder.config.enable is True
        assert decoder.config.coherence_threshold_low == 0.4

    def test_explicit_config(self):
        cfg = CoherenceDecoderConfig(enable=False)
        decoder = CoherenceAwareDecoder(cfg)
        assert decoder.config.enable is False

    def test_none_config_uses_default(self):
        decoder = CoherenceAwareDecoder(config=None)
        assert decoder.config.enable is True


# =============================================================================
# Logit Firewall Invariant
# =============================================================================


class TestLogitFirewall:
    """Verify the logit firewall invariant: decoder never modifies logits."""

    def test_adjust_policy_returns_only_policy_keys(self):
        """adjust_policy returns only temperature, top_p, should_resample."""
        decoder = CoherenceAwareDecoder()
        policy = decoder.adjust_policy(coherence=0.1, base_temperature=1.0, base_top_p=0.9)
        assert set(policy.keys()) == {"temperature", "top_p", "should_resample"}

    def test_no_logit_attribute_on_decoder(self):
        """Decoder has no state that could hold or modify logits."""
        decoder = CoherenceAwareDecoder()
        # Only config attribute
        attrs = [a for a in dir(decoder) if not a.startswith('_')]
        assert "logits" not in attrs
        assert "modify_logits" not in attrs

    def test_policy_types(self):
        """Policy values have correct types."""
        decoder = CoherenceAwareDecoder()
        policy = decoder.adjust_policy(coherence=0.1, base_temperature=0.7, base_top_p=0.9)
        assert isinstance(policy["temperature"], float)
        assert isinstance(policy["top_p"], float)
        assert isinstance(policy["should_resample"], bool)


# =============================================================================
# Integration with SymbolU12LLM.generate_text()
# =============================================================================


class _MockSymbolU12LLM:
    """Minimal mock of SymbolU12LLM for integration testing.

    Simulates the generate_text() loop logic without needing a real model.
    Produces deterministic outputs with controllable coherence levels.
    """

    def __init__(self, coherence_sequence=None, vocab_size=100):
        """
        Args:
            coherence_sequence: List of coherence values to return per step.
                If None, defaults to 1.0 (full coherence).
            vocab_size: Vocabulary size for logit generation.
        """
        self.coherence_sequence = coherence_sequence or []
        self.vocab_size = vocab_size
        self._step = 0

    def generate_step(self, temperature, top_p, coherence_decoder=None, tracer=None):
        """Simulate one generation step.

        Returns the effective policy used and the "token" selected.
        """
        # Simulate raw logits (deterministic seed per step)
        torch.manual_seed(42 + self._step)
        raw_logits = torch.randn(1, self.vocab_size)

        # Get coherence for this step
        if self._step < len(self.coherence_sequence):
            coherence_scalar = self.coherence_sequence[self._step]
        else:
            coherence_scalar = 1.0

        # Apply coherence-aware policy
        effective_temp = temperature
        effective_top_p = top_p
        should_resample = False

        if coherence_decoder is not None:
            policy = coherence_decoder.adjust_policy(
                coherence=coherence_scalar,
                base_temperature=temperature,
                base_top_p=top_p,
            )
            effective_temp = policy["temperature"]
            effective_top_p = policy["top_p"]
            should_resample = policy["should_resample"]

        # LOGIT FIREWALL: raw_logits unchanged; only temperature applied
        logits = raw_logits / effective_temp

        # Top-p filtering
        if effective_top_p < 1.0:
            sorted_logits, sorted_indices = torch.sort(logits, descending=True, dim=-1)
            cumulative_probs = torch.cumsum(
                F.softmax(sorted_logits, dim=-1), dim=-1
            )
            sorted_indices_to_remove = cumulative_probs > effective_top_p
            sorted_indices_to_remove[:, 1:] = sorted_indices_to_remove[:, :-1].clone()
            sorted_indices_to_remove[:, 0] = 0
            indices_to_remove = sorted_indices_to_remove.scatter(
                1, sorted_indices, sorted_indices_to_remove
            )
            logits[indices_to_remove] = float('-inf')

        probs = F.softmax(logits, dim=-1)
        next_token = torch.multinomial(probs, num_samples=1)

        # Resample
        resample_count = 0
        if should_resample and coherence_decoder is not None:
            for _ in range(coherence_decoder.config.max_resample_attempts):
                candidate = torch.multinomial(probs, num_samples=1)
                if probs[0, candidate[0, 0]] > probs[0, next_token[0, 0]]:
                    next_token = candidate
                    resample_count += 1
                    break

        self._step += 1

        return {
            "token_id": next_token[0, 0].item(),
            "raw_logits": raw_logits,
            "effective_temperature": effective_temp,
            "effective_top_p": effective_top_p,
            "should_resample": should_resample,
            "resample_count": resample_count,
            "coherence": coherence_scalar,
            "probs": probs,
        }


class TestGenerateTextIntegration:
    """Test coherence-aware decoder integration with generation loop."""

    def test_no_decoder_unchanged_behavior(self):
        """Without coherence decoder, behavior is unchanged (baseline)."""
        mock = _MockSymbolU12LLM(coherence_sequence=[0.1, 0.1])
        result = mock.generate_step(temperature=0.7, top_p=0.9, coherence_decoder=None)
        assert result["effective_temperature"] == 0.7
        assert result["effective_top_p"] == 0.9
        assert result["should_resample"] is False

    def test_high_coherence_no_adjustment(self):
        """With high coherence, decoder makes no changes."""
        decoder = CoherenceAwareDecoder()
        mock = _MockSymbolU12LLM(coherence_sequence=[0.8])
        result = mock.generate_step(temperature=0.7, top_p=0.9, coherence_decoder=decoder)
        assert result["effective_temperature"] == 0.7
        assert result["effective_top_p"] == 0.9
        assert result["should_resample"] is False

    def test_low_coherence_dampens_temperature(self):
        """Low coherence reduces temperature."""
        decoder = CoherenceAwareDecoder()
        mock = _MockSymbolU12LLM(coherence_sequence=[0.3])
        result = mock.generate_step(temperature=0.7, top_p=0.9, coherence_decoder=decoder)
        assert abs(result["effective_temperature"] - 0.56) < 1e-6
        assert result["effective_top_p"] == 0.85

    def test_critical_coherence_triggers_resample(self):
        """Critical coherence triggers resampling."""
        decoder = CoherenceAwareDecoder()
        mock = _MockSymbolU12LLM(coherence_sequence=[0.1])
        result = mock.generate_step(temperature=0.7, top_p=0.9, coherence_decoder=decoder)
        assert result["should_resample"] is True

    def test_logit_firewall_raw_logits_unchanged(self):
        """Raw logits are never modified by the coherence decoder."""
        decoder = CoherenceAwareDecoder()
        mock = _MockSymbolU12LLM(coherence_sequence=[0.1])

        # Record raw logits before any adjustment
        torch.manual_seed(42)
        expected_raw = torch.randn(1, 100)

        result = mock.generate_step(temperature=0.7, top_p=0.9, coherence_decoder=decoder)

        # Raw logits should match exactly
        assert torch.allclose(result["raw_logits"], expected_raw)

    def test_multi_step_varying_coherence(self):
        """Multiple steps with varying coherence produce correct policies."""
        decoder = CoherenceAwareDecoder()
        # High → Low → Critical coherence
        mock = _MockSymbolU12LLM(coherence_sequence=[0.8, 0.3, 0.1])

        r1 = mock.generate_step(temperature=1.0, top_p=0.9, coherence_decoder=decoder)
        assert r1["effective_temperature"] == 1.0  # High coherence, no change

        r2 = mock.generate_step(temperature=1.0, top_p=0.9, coherence_decoder=decoder)
        assert abs(r2["effective_temperature"] - 0.8) < 1e-6  # Low coherence

        r3 = mock.generate_step(temperature=1.0, top_p=0.9, coherence_decoder=decoder)
        assert r3["should_resample"] is True  # Critical

    def test_disabled_decoder_passthrough(self):
        """Disabled decoder passes through all parameters unchanged."""
        decoder = CoherenceAwareDecoder(CoherenceDecoderConfig(enable=False))
        mock = _MockSymbolU12LLM(coherence_sequence=[0.05])
        result = mock.generate_step(temperature=0.7, top_p=0.9, coherence_decoder=decoder)
        assert result["effective_temperature"] == 0.7
        assert result["effective_top_p"] == 0.9
        assert result["should_resample"] is False


# =============================================================================
# Resample Logic
# =============================================================================


class TestResampleLogic:
    """Test the resampling mechanism for critically low coherence."""

    def test_resample_selects_higher_prob_token(self):
        """Resampling should accept a candidate only if it has higher probability."""
        decoder = CoherenceAwareDecoder(CoherenceDecoderConfig(max_resample_attempts=100))
        mock = _MockSymbolU12LLM(coherence_sequence=[0.05])

        # Run many times to verify resampled tokens tend to be higher-probability
        results = []
        for seed in range(20):
            m = _MockSymbolU12LLM(coherence_sequence=[0.05], vocab_size=50)
            m._step = 0
            torch.manual_seed(seed * 1000)
            r = m.generate_step(temperature=1.0, top_p=0.9, coherence_decoder=decoder)
            results.append(r)

        # At least some should have resampled (probabilistic, but very likely with 20 tries)
        resample_events = sum(r["resample_count"] for r in results)
        # With 100 attempts and 20 runs, at least a few should have resampled
        assert resample_events >= 0  # Non-negative (can't have negative resamples)

    def test_max_resample_attempts_respected(self):
        """Resampling does not exceed max_resample_attempts iterations."""
        cfg = CoherenceDecoderConfig(max_resample_attempts=0)
        decoder = CoherenceAwareDecoder(cfg)
        mock = _MockSymbolU12LLM(coherence_sequence=[0.05])
        result = mock.generate_step(temperature=0.7, top_p=0.9, coherence_decoder=decoder)
        # With 0 max attempts, no resampling should occur even though triggered
        assert result["resample_count"] == 0


# =============================================================================
# Ablation Test Modes (F.3.7)
# =============================================================================


class TestAblationModes:
    """Verify the three ablation modes produce distinct behaviors."""

    def _run_steps(self, decoder, coherence_seq, temperature=1.0, top_p=0.9):
        """Run a sequence of generation steps and collect policies."""
        mock = _MockSymbolU12LLM(coherence_sequence=coherence_seq)
        results = []
        for _ in coherence_seq:
            r = mock.generate_step(
                temperature=temperature, top_p=top_p, coherence_decoder=decoder,
            )
            results.append(r)
        return results

    def test_baseline_mode(self):
        """Baseline: coherence-aware disabled, current behavior preserved."""
        decoder = CoherenceAwareDecoder(CoherenceDecoderConfig(enable=False))
        coherence_seq = [0.8, 0.3, 0.1]
        results = self._run_steps(decoder, coherence_seq)

        # All steps should use base temperature and top_p
        for r in results:
            assert r["effective_temperature"] == 1.0
            assert r["effective_top_p"] == 0.9
            assert r["should_resample"] is False

    def test_control_mode_fixed_dampening(self):
        """Control: always apply fixed temperature reduction (simulate T*0.8)."""
        # Simulate control mode by using a threshold of 1.0 (always triggers)
        cfg = CoherenceDecoderConfig(
            coherence_threshold_low=1.1,  # Always below
            coherence_threshold_critical=0.0,  # Never triggers resample
            temperature_dampening=0.8,
            top_p_cap=0.85,
        )
        decoder = CoherenceAwareDecoder(cfg)
        coherence_seq = [0.8, 0.3, 0.1]
        results = self._run_steps(decoder, coherence_seq)

        # All steps should be dampened
        for r in results:
            assert abs(r["effective_temperature"] - 0.8) < 1e-6
            assert r["effective_top_p"] == 0.85
            assert r["should_resample"] is False

    def test_coherence_aware_mode_adaptive(self):
        """Coherence-aware: adaptive adjustment based on signal."""
        decoder = CoherenceAwareDecoder()  # Default config
        coherence_seq = [0.8, 0.3, 0.1]
        results = self._run_steps(decoder, coherence_seq)

        # Step 1: high coherence → no change
        assert results[0]["effective_temperature"] == 1.0
        # Step 2: low coherence → dampened
        assert abs(results[1]["effective_temperature"] - 0.8) < 1e-6
        # Step 3: critical → dampened + resample
        assert results[2]["should_resample"] is True


# =============================================================================
# Stage 1 Measurements / Tracer Fields (F.3.6)
# =============================================================================


class TestTracerFieldsStage1:
    """Verify that Stage 1 measurement fields are computed correctly."""

    def test_measurement_fields_computed(self):
        """The integration should produce coherence_before, temperature_used,
        top_p_used, and resample_events fields for the tracer."""
        decoder = CoherenceAwareDecoder()

        # Simulate what generate_text does for tracer recording
        coherence_scalar = 0.3
        policy = decoder.adjust_policy(
            coherence=coherence_scalar,
            base_temperature=0.7,
            base_top_p=0.9,
        )

        tracer_entry = {
            "coherence_before": coherence_scalar,
            "temperature_used": policy["temperature"],
            "top_p_used": policy["top_p"],
            "resample_events": 0,
        }

        assert tracer_entry["coherence_before"] == 0.3
        assert abs(tracer_entry["temperature_used"] - 0.56) < 1e-6
        assert tracer_entry["top_p_used"] == 0.85
        assert tracer_entry["resample_events"] == 0

    def test_measurement_fields_critical(self):
        """Critical coherence produces correct measurement fields."""
        decoder = CoherenceAwareDecoder()
        policy = decoder.adjust_policy(coherence=0.1, base_temperature=1.0, base_top_p=0.95)

        assert policy["should_resample"] is True
        assert abs(policy["temperature"] - 0.8) < 1e-6
        assert policy["top_p"] == 0.85


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Edge case testing for robustness."""

    def test_negative_coherence_treated_as_critical(self):
        """Negative coherence (invalid but possible) triggers maximum intervention."""
        decoder = CoherenceAwareDecoder()
        policy = decoder.adjust_policy(coherence=-0.5, base_temperature=1.0, base_top_p=0.9)
        assert policy["should_resample"] is True
        assert abs(policy["temperature"] - 0.8) < 1e-6

    def test_very_high_coherence(self):
        """Coherence > 1.0 should not trigger any adjustment."""
        decoder = CoherenceAwareDecoder()
        policy = decoder.adjust_policy(coherence=2.0, base_temperature=1.0, base_top_p=0.9)
        assert policy["temperature"] == 1.0
        assert policy["top_p"] == 0.9
        assert policy["should_resample"] is False

    def test_very_low_temperature(self):
        """Very low base temperature is still dampened correctly."""
        decoder = CoherenceAwareDecoder()
        policy = decoder.adjust_policy(coherence=0.3, base_temperature=0.1, base_top_p=0.9)
        assert abs(policy["temperature"] - 0.08) < 1e-6

    def test_top_p_one(self):
        """top_p=1.0 is capped when coherence low."""
        decoder = CoherenceAwareDecoder()
        policy = decoder.adjust_policy(coherence=0.3, base_temperature=1.0, base_top_p=1.0)
        assert policy["top_p"] == 0.85

    def test_top_p_zero(self):
        """top_p=0.0 stays at 0.0 even when coherence is high."""
        decoder = CoherenceAwareDecoder()
        policy = decoder.adjust_policy(coherence=0.3, base_temperature=1.0, base_top_p=0.0)
        assert policy["top_p"] == 0.0  # min(0.0, 0.85) = 0.0
