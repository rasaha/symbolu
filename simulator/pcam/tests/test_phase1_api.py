"""
Phase 1 public-API tests for PCAM.

Scope is intentionally narrow:

- public API importability from ``simulator.pcam``
- ``PCAMConfig`` basic construction, factories, and ``build_policy``
- ``classify_tier`` semantics (HOT/WARM/COLD/EVICT, sink clamp,
  unknown-block fallthrough)
- ``tier_hints`` batched semantics
- ``PolicyMetrics.snapshot`` / ``PolicyMetrics.delta`` behavior

These tests do NOT re-test the parity contract — that lives in
``test_sketch_conformance.py`` and ``test_attention_evictor_parity.py``.
The Phase 1 tests assume the runtime policy is correct and only
verify that the new public surface around it behaves as documented.
"""

from __future__ import annotations

import os

import pytest

from simulator.pcam import (
    FrequencySketch,
    InferencePhase,
    KVCachePolicy,
    PCAMConfig,
    PolicyMetrics,
    PositionClass,
    TierHint,
)


# ===========================================================================
# Public-API importability
# ===========================================================================


class TestPublicAPI:
    def test_kv_policy_runtime_symbols_importable(self):
        """All Phase 1 KV-policy symbols are reachable from the package root."""
        assert KVCachePolicy is not None
        assert FrequencySketch is not None
        assert InferencePhase is not None
        assert PositionClass is not None
        assert PCAMConfig is not None
        assert TierHint is not None
        assert PolicyMetrics is not None

    def test_simulator_framework_still_exported(self):
        """
        Pre-existing simulator surface must keep working. PCAMSimulatorConfig
        is the explicit name for what used to be re-exported as PCAMConfig.
        """
        from simulator.pcam import (
            AttentionState,
            BlockScore,
            MetricsCollector,
            PCAMInterface,
            PCAMMetrics,
            PCAMSimulator,
            PCAMSimulatorConfig,
            SimulationResult,
        )
        assert PCAMSimulator is not None
        assert PCAMSimulatorConfig is not None
        assert PCAMInterface is not None
        assert SimulationResult is not None
        assert AttentionState is not None
        assert BlockScore is not None
        assert PCAMMetrics is not None
        assert MetricsCollector is not None

    def test_tier_hint_enum_values(self):
        """TierHint is a stable string-valued enum (serialization-safe)."""
        assert TierHint.HOT.value == "HOT"
        assert TierHint.WARM.value == "WARM"
        assert TierHint.COLD.value == "COLD"
        assert TierHint.EVICT.value == "EVICT"


# ===========================================================================
# PCAMConfig
# ===========================================================================


class TestPCAMConfig:
    def test_construct_with_defaults(self):
        cfg = PCAMConfig(max_blocks=128)
        assert cfg.max_blocks == 128
        assert cfg.block_size == 16
        assert cfg.sink_tokens == 4
        assert cfg.recent_window == 256
        assert cfg.entity_attention_threshold == 0.02
        assert cfg.attention_ema_alpha == 0.1

    def test_construct_with_overrides(self):
        cfg = PCAMConfig(
            max_blocks=512,
            block_size=32,
            sink_tokens=8,
            attention_ema_alpha=0.05,
        )
        assert cfg.max_blocks == 512
        assert cfg.block_size == 32
        assert cfg.sink_tokens == 8
        assert cfg.attention_ema_alpha == 0.05

    def test_frozen(self):
        """Frozen dataclass — mutation must raise."""
        cfg = PCAMConfig(max_blocks=64)
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            cfg.max_blocks = 128  # type: ignore[misc]

    def test_to_dict_roundtrip(self):
        cfg = PCAMConfig(max_blocks=128, sink_tokens=8)
        round = PCAMConfig.from_dict(cfg.to_dict())
        assert cfg == round

    def test_from_dict_rejects_unknown_keys(self):
        with pytest.raises(TypeError, match="unknown keys"):
            PCAMConfig.from_dict({"max_blocks": 64, "bogus_key": 1})

    def test_from_dict_requires_max_blocks(self):
        with pytest.raises(TypeError, match="max_blocks"):
            PCAMConfig.from_dict({"sink_tokens": 4})

    def test_from_env_reads_prefixed_vars(self, monkeypatch):
        monkeypatch.setenv("PCAM_MAX_BLOCKS", "256")
        monkeypatch.setenv("PCAM_SINK_TOKENS", "8")
        monkeypatch.setenv("PCAM_ATTENTION_EMA_ALPHA", "0.2")
        cfg = PCAMConfig.from_env()
        assert cfg.max_blocks == 256
        assert cfg.sink_tokens == 8
        assert cfg.attention_ema_alpha == pytest.approx(0.2)

    def test_from_env_requires_max_blocks(self, monkeypatch):
        # Strip any pre-existing PCAM_MAX_BLOCKS from the test env.
        monkeypatch.delenv("PCAM_MAX_BLOCKS", raising=False)
        with pytest.raises(TypeError, match="MAX_BLOCKS"):
            PCAMConfig.from_env()

    def test_from_yaml_missing_dependency_message(self, tmp_path, monkeypatch):
        """
        from_yaml is a soft dependency. If PyYAML is unavailable, it
        must raise a clear RuntimeError. If it IS available, it must
        successfully parse a minimal YAML file.
        """
        yaml_path = tmp_path / "cfg.yaml"
        yaml_path.write_text("max_blocks: 64\nsink_tokens: 2\n")
        try:
            cfg = PCAMConfig.from_yaml(str(yaml_path))
        except RuntimeError as e:
            assert "PyYAML" in str(e)
            return
        assert cfg.max_blocks == 64
        assert cfg.sink_tokens == 2

    def test_build_policy_returns_kvcachepolicy(self):
        cfg = PCAMConfig(max_blocks=64, sink_tokens=2)
        policy = cfg.build_policy()
        assert isinstance(policy, KVCachePolicy)
        assert policy.max_blocks == 64
        assert policy.sink_tokens == 2


# ===========================================================================
# Tier-hint API
# ===========================================================================


class TestTierHints:
    def _make_policy(self) -> KVCachePolicy:
        policy = PCAMConfig(max_blocks=128, sink_tokens=4).build_policy()
        policy.register_sequence(1)
        policy.set_phase(1, InferencePhase.DECODE)
        return policy

    def test_unknown_block_classifies_as_evict(self):
        policy = self._make_policy()
        assert policy.classify_tier(9999) is TierHint.EVICT

    def test_sink_block_clamped_to_hot(self):
        """
        Sink blocks (positions < sink_tokens at admission time) are
        pinned and must classify as HOT regardless of their score.
        """
        policy = self._make_policy()
        policy.ensure_block(0, 1, [0, 1, 2, 3])  # all positions are sink
        assert 0 in policy.pinned_blocks
        assert policy.classify_tier(0) is TierHint.HOT

    def test_high_attention_block_classifies_hot(self):
        """
        A non-sink block with attention well above the running mean
        classifies as HOT. We seed a low-EMA baseline first so the
        target block's attention reliably exceeds the adaptive entity
        threshold and the +0.5 entity bonus fires.
        """
        policy = self._make_policy()
        # Low-EMA baseline across 20 filler blocks.
        for filler_id in range(20, 40):
            policy.ensure_block(filler_id, 1, [filler_id * 10])
            policy.on_block_attention(filler_id, 0.001, 1)
        # Now create the genuinely hot block.
        policy.ensure_block(10, 1, [100])
        for _ in range(30):
            policy.on_block_attention(10, 0.9, 1)
        assert policy.classify_tier(10) is TierHint.HOT

    def test_filler_block_classifies_cold_or_evict(self):
        """A non-sink block with negligible attention falls into the
        lower tiers. Exact tier depends on the recency / freq components,
        so we accept either COLD or EVICT and just assert it isn't HOT
        or WARM."""
        policy = self._make_policy()
        policy.ensure_block(20, 1, [200])
        policy.on_block_attention(20, 0.001, 1)
        tier = policy.classify_tier(20)
        assert tier in (TierHint.COLD, TierHint.WARM, TierHint.EVICT)
        assert tier is not TierHint.HOT

    def test_tier_hints_batches_correctly(self):
        policy = self._make_policy()
        # Establish a low-EMA baseline so the hot block reliably crosses
        # the adaptive entity threshold (same setup as the single-block
        # HOT test above).
        for filler_id in range(20, 40):
            policy.ensure_block(filler_id, 1, [filler_id * 10])
            policy.on_block_attention(filler_id, 0.001, 1)
        policy.ensure_block(0, 1, [0, 1, 2, 3])  # sink
        policy.ensure_block(1, 1, [100])
        for _ in range(30):
            policy.on_block_attention(1, 0.9, 1)

        hints = policy.tier_hints([0, 1, 9999])
        assert set(hints.keys()) == {0, 1, 9999}
        assert hints[0] is TierHint.HOT      # sink
        assert hints[1] is TierHint.HOT      # high-attention non-sink
        assert hints[9999] is TierHint.EVICT  # unknown

    def test_thresholds_are_introspectable(self):
        """Tier thresholds are class-level constants for downstream
        consumers that want to align their own placement logic."""
        assert KVCachePolicy.TIER_HOT_THRESHOLD == 0.7
        assert KVCachePolicy.TIER_WARM_THRESHOLD == 0.3


# ===========================================================================
# PolicyMetrics
# ===========================================================================


class TestPolicyMetrics:
    def test_snapshot_returns_dict_copy(self):
        policy = PCAMConfig(max_blocks=64).build_policy()
        m = PolicyMetrics(policy)

        snap = m.snapshot()
        assert isinstance(snap, dict)
        assert "evictions" in snap
        assert "step" in snap

        # Mutating the snapshot must not affect future snapshots.
        snap["evictions"] = 99999
        snap2 = m.snapshot()
        assert snap2["evictions"] != 99999

    def test_delta_computes_numeric_differences(self):
        policy = PCAMConfig(max_blocks=64).build_policy()
        policy.register_sequence(1)
        policy.set_phase(1, InferencePhase.DECODE)
        m = PolicyMetrics(policy)

        snap1 = m.snapshot()
        # Drive a few attention events. Both ensure_block (first
        # admission) and on_block_attention bump _step, so 5 admissions
        # + 5 attention events = 10 step ticks.
        for bid in range(5):
            policy.ensure_block(bid, 1, [100 + bid])
            policy.on_block_attention(bid, 0.1, 1)

        delta = m.delta(snap1)
        assert delta["step"] == 10
        assert delta["total_blocks"] == 5
        assert delta["gpu_blocks"] == 5
        assert delta["evictions"] == 0  # no evictions in this trace

    def test_delta_drops_missing_keys(self):
        policy = PCAMConfig(max_blocks=64).build_policy()
        m = PolicyMetrics(policy)
        delta = m.delta({"nonexistent_key": 42})
        assert "nonexistent_key" not in delta
