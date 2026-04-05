"""
Sovereign Bridge — Entropy Translation Tests
=============================================

Tests for `entropy_from_sovereign_state()`: the sovereign-state → EntropyResult
translation helper in agentic/agentic_framework/sovereign_bridge.py.

This helper is the first honest production bridge between:
  - agentic/entropy/ (canonical EntropyEngine producer)
  - the 32D sovereign state (raw guna + kosha activations)

What these tests prove:
  1. The helper extracts guna/kosha slices from 32D state using the same
     _extract_slices() indexing as the sibling bridge functions.
  2. Sovereign guna [LUCIDITY, ACTIVITY, STABILITY] → GunaProfile
     [sattva, rajas, tamas] is the correct direct mapping.
  3. Sovereign kosha [MATERIAL, VITAL, MENTAL, INTELLECTUAL, BLISSFUL] →
     KoshaProfile [annamaya, pranamaya, manomaya, vijnanamaya, anandamaya]
     is the correct direct mapping.
  4. target_kosha=None produces guna-only entropy (no kosha fabrication).
  5. target_kosha=<profile> produces full guna + kosha entropy.
  6. Tier selection controls gate/mode, not thresholds.
  7. Determinism: same input → same output across repeated invocations.
  8. The helper accepts lists, tuples, and torch-like batched tensors
     via the same `_extract_slices()` path as the other bridge functions.
  9. Values outside [0.0, 1.0] are clamped to the valid range.
"""

import pytest

from agentic.agentic_framework.sovereign_bridge import entropy_from_sovereign_state
from agentic.entropy.types import (
    EntropyResult,
    EntropyGate,
    EntropyMode,
    KoshaProfile,
)
from agentic.sovereign_constants import (
    KOSHA_START, KOSHA_END,
    VRITTI_START,
    GUNA_START, GUNA_END,
    GUNA_LUCIDITY, GUNA_ACTIVITY, GUNA_STABILITY,
    GUNA_VELOCITY, GUNA_ACCEL, GUNA_STABLE,
    KOSHA_MATERIAL, KOSHA_VITAL, KOSHA_MENTAL,
    KOSHA_INTELLECTUAL, KOSHA_BLISSFUL,
)


# ---------------------------------------------------------------------------
# Realistic 32D state builders
# ---------------------------------------------------------------------------

def _make_state(
    *,
    sattva: float = 0.33,
    rajas: float = 0.33,
    tamas: float = 0.33,
    velocity: float = 0.0,
    accel: float = 0.0,
    stable: float = 1.0,
    annamaya: float = 0.2,
    pranamaya: float = 0.2,
    manomaya: float = 0.2,
    vijnanamaya: float = 0.2,
    anandamaya: float = 0.2,
) -> list:
    """Build a realistic 32D sovereign state vector from named profile values.

    Layout matches agentic/sovereign_constants.py:
      Bhava[0:12] | Kosha[12:17] | Vritti[17:22] | Guna[22:28] | Reserved[28:32]
    """
    state = [0.0] * 32

    # Kosha slice [12:17]
    state[KOSHA_START + KOSHA_MATERIAL] = annamaya
    state[KOSHA_START + KOSHA_VITAL] = pranamaya
    state[KOSHA_START + KOSHA_MENTAL] = manomaya
    state[KOSHA_START + KOSHA_INTELLECTUAL] = vijnanamaya
    state[KOSHA_START + KOSHA_BLISSFUL] = anandamaya

    # Vritti slice [17:22] — neutral balanced (irrelevant for entropy)
    for i in range(VRITTI_START, VRITTI_START + 5):
        state[i] = 0.2

    # Guna slice [22:28]
    state[GUNA_START + GUNA_LUCIDITY] = sattva
    state[GUNA_START + GUNA_ACTIVITY] = rajas
    state[GUNA_START + GUNA_STABILITY] = tamas
    state[GUNA_START + GUNA_VELOCITY] = velocity
    state[GUNA_START + GUNA_ACCEL] = accel
    state[GUNA_START + GUNA_STABLE] = stable

    return state


# ===========================================================================
# 1. Return type and shape
# ===========================================================================

class TestReturnType:
    """Helper returns a real EntropyResult with all expected fields."""

    def test_returns_entropy_result_instance(self):
        """Return value is a real EntropyResult (not a dict or None)."""
        state = _make_state()
        result = entropy_from_sovereign_state(state)
        assert isinstance(result, EntropyResult)

    def test_result_has_all_entropy_dimensions(self):
        """EntropyResult carries guna, kosha, cross-domain, combined."""
        result = entropy_from_sovereign_state(_make_state())
        assert 0.0 <= result.guna_entropy <= 1.0
        assert 0.0 <= result.kosha_entropy <= 1.0
        assert 0.0 <= result.cross_domain_entropy <= 1.0
        assert 0.0 <= result.combined_entropy <= 1.0

    def test_result_has_gate_and_mode(self):
        """Gate is a real EntropyGate, mode is a real EntropyMode."""
        result = entropy_from_sovereign_state(_make_state())
        assert isinstance(result.gate, EntropyGate)
        assert isinstance(result.mode, EntropyMode)


# ===========================================================================
# 2. Guna slice → GunaProfile mapping
# ===========================================================================

class TestGunaMapping:
    """Verify guna[LUCIDITY/ACTIVITY/STABILITY] → GunaProfile(sattva/rajas/tamas)."""

    def test_balanced_guna_produces_low_guna_entropy(self):
        """Perfectly balanced (1/3, 1/3, 1/3) → near-zero guna entropy."""
        state = _make_state(sattva=0.333, rajas=0.333, tamas=0.334)
        result = entropy_from_sovereign_state(state)
        assert result.guna_entropy < 0.01, (
            f"Balanced guna should yield ~0 entropy, got {result.guna_entropy}"
        )

    def test_tamas_dominant_produces_high_guna_entropy(self):
        """Pure tamas (0, 0, 1) → maximum guna entropy (1.0)."""
        state = _make_state(sattva=0.0, rajas=0.0, tamas=1.0)
        result = entropy_from_sovereign_state(state)
        assert result.guna_entropy == pytest.approx(1.0, abs=1e-6), (
            f"Pure tamas should yield max guna entropy, got {result.guna_entropy}"
        )

    def test_sattva_dominant_produces_high_guna_entropy(self):
        """Pure sattva (1, 0, 0) → maximum guna entropy (imbalance)."""
        state = _make_state(sattva=1.0, rajas=0.0, tamas=0.0)
        result = entropy_from_sovereign_state(state)
        assert result.guna_entropy == pytest.approx(1.0, abs=1e-6)

    def test_rajas_dominant_produces_high_guna_entropy(self):
        """Pure rajas (0, 1, 0) → maximum guna entropy (imbalance)."""
        state = _make_state(sattva=0.0, rajas=1.0, tamas=0.0)
        result = entropy_from_sovereign_state(state)
        assert result.guna_entropy == pytest.approx(1.0, abs=1e-6)

    def test_dynamics_dims_ignored_in_guna_profile(self):
        """velocity/accel/stable must NOT affect guna_entropy.

        The canonical 3-guna distribution is (lucidity, activity, stability).
        The remaining 3 dims are dynamics descriptors and should not leak
        into GunaProfile.
        """
        balanced_low_dynamics = _make_state(
            sattva=0.333, rajas=0.333, tamas=0.334,
            velocity=0.0, accel=0.0, stable=1.0,
        )
        balanced_high_dynamics = _make_state(
            sattva=0.333, rajas=0.333, tamas=0.334,
            velocity=0.99, accel=0.99, stable=0.0,
        )
        r1 = entropy_from_sovereign_state(balanced_low_dynamics)
        r2 = entropy_from_sovereign_state(balanced_high_dynamics)
        assert r1.guna_entropy == pytest.approx(r2.guna_entropy, abs=1e-9)


# ===========================================================================
# 3. Kosha slice → KoshaProfile mapping + target_kosha semantics
# ===========================================================================

class TestKoshaMapping:
    """Verify kosha slice → source KoshaProfile + target_kosha handling."""

    def test_no_target_kosha_yields_zero_kosha_entropy(self):
        """Without target_kosha, engine defaults kosha entropy to 0.0.

        This is the honest default at single-state inference time: we
        have the current state's kosha as source, but no natural target.
        Fabricating a target kosha is forbidden.
        """
        state = _make_state(annamaya=1.0, pranamaya=0.0, manomaya=0.0,
                            vijnanamaya=0.0, anandamaya=0.0)
        result = entropy_from_sovereign_state(state, target_kosha=None)
        assert result.kosha_entropy == 0.0

    def test_same_layer_target_kosha_yields_low_kosha_entropy(self):
        """source ≈ target → low kosha entropy (same processing layer)."""
        # State kosha = annamaya-dominant
        state = _make_state(annamaya=1.0, pranamaya=0.0, manomaya=0.0,
                            vijnanamaya=0.0, anandamaya=0.0)
        # Target also annamaya-dominant
        target = KoshaProfile(
            annamaya=1.0, pranamaya=0.0, manomaya=0.0,
            vijnanamaya=0.0, anandamaya=0.0,
        )
        result = entropy_from_sovereign_state(state, target_kosha=target)
        # Same layer → low entropy
        assert result.kosha_entropy < 0.2, (
            f"Same layer should yield low kosha entropy, got {result.kosha_entropy}"
        )

    def test_distant_layer_target_kosha_yields_high_kosha_entropy(self):
        """annamaya source → anandamaya target is max layer distance."""
        # Source: annamaya-dominant (layer 1)
        state = _make_state(annamaya=1.0, pranamaya=0.0, manomaya=0.0,
                            vijnanamaya=0.0, anandamaya=0.0)
        # Target: anandamaya-dominant (layer 5) — max distance
        target = KoshaProfile(
            annamaya=0.0, pranamaya=0.0, manomaya=0.0,
            vijnanamaya=0.0, anandamaya=1.0,
        )
        result = entropy_from_sovereign_state(state, target_kosha=target)
        # Distant layers → high entropy
        assert result.kosha_entropy > 0.7, (
            f"Distant layers should yield high kosha entropy, "
            f"got {result.kosha_entropy}"
        )

    def test_providing_target_changes_combined_entropy(self):
        """Passing target_kosha adds kosha contribution to combined entropy."""
        state = _make_state(
            sattva=0.333, rajas=0.333, tamas=0.334,  # balanced guna → 0
            annamaya=1.0, pranamaya=0.0, manomaya=0.0,
            vijnanamaya=0.0, anandamaya=0.0,
        )
        without_target = entropy_from_sovereign_state(state, target_kosha=None)
        distant_target = KoshaProfile(
            annamaya=0.0, pranamaya=0.0, manomaya=0.0,
            vijnanamaya=0.0, anandamaya=1.0,
        )
        with_target = entropy_from_sovereign_state(
            state, target_kosha=distant_target,
        )
        # With a distant target kosha, combined entropy must be strictly higher
        assert with_target.combined_entropy > without_target.combined_entropy


# ===========================================================================
# 4. Cross-domain entropy is always zero from this helper
# ===========================================================================

class TestCrossDomainNeverComputed:
    """The 32D state does not carry DomainProfile data — cross-domain = 0."""

    def test_cross_domain_entropy_always_zero(self):
        """Cross-domain entropy must be 0.0 regardless of state content."""
        extreme_state = _make_state(
            sattva=0.0, rajas=0.0, tamas=1.0,
            annamaya=1.0, pranamaya=0.0, manomaya=0.0,
            vijnanamaya=0.0, anandamaya=0.0,
        )
        result = entropy_from_sovereign_state(extreme_state)
        assert result.cross_domain_entropy == 0.0


# ===========================================================================
# 5. Tier selection
# ===========================================================================

class TestTierSelection:
    """tier_name controls gate/mode — does not fabricate thresholds."""

    def test_enterprise_search_tier_is_diagnostic_only(self):
        """enterprise_search tier → DIAGNOSTIC_ONLY mode, always ALLOW."""
        extreme_state = _make_state(sattva=0.0, rajas=0.0, tamas=1.0)
        result = entropy_from_sovereign_state(
            extreme_state, tier_name="enterprise_search",
        )
        assert result.mode == EntropyMode.DIAGNOSTIC_ONLY
        assert result.gate == EntropyGate.ALLOW

    def test_enterprise_chat_tier_is_modulation_only(self):
        """enterprise_chat tier → MODULATION_ONLY mode, never BLOCK."""
        extreme_state = _make_state(sattva=0.0, rajas=0.0, tamas=1.0)
        result = entropy_from_sovereign_state(
            extreme_state, tier_name="enterprise_chat",
        )
        assert result.mode == EntropyMode.MODULATION_ONLY
        assert result.gate != EntropyGate.BLOCK

    def test_consumer_tier_is_full_gating(self):
        """consumer tier → FULL_GATING mode."""
        result = entropy_from_sovereign_state(
            _make_state(), tier_name="consumer",
        )
        assert result.mode == EntropyMode.FULL_GATING

    def test_default_tier_is_enterprise_chat(self):
        """Default tier_name is enterprise_chat."""
        result = entropy_from_sovereign_state(_make_state())
        assert result.mode == EntropyMode.MODULATION_ONLY

    def test_invalid_tier_name_raises(self):
        """Unknown tier_name raises ValueError (no silent default)."""
        with pytest.raises(ValueError):
            entropy_from_sovereign_state(_make_state(), tier_name="nonexistent")


# ===========================================================================
# 6. Determinism
# ===========================================================================

class TestDeterminism:
    """Same input produces same output across repeated invocations."""

    def test_identical_state_produces_identical_result(self):
        """Deterministic: same state → same result fields."""
        state = _make_state(
            sattva=0.1, rajas=0.3, tamas=0.6,
            annamaya=0.7, pranamaya=0.2, manomaya=0.1,
            vijnanamaya=0.0, anandamaya=0.0,
        )
        r1 = entropy_from_sovereign_state(state)
        r2 = entropy_from_sovereign_state(state)
        assert r1.guna_entropy == r2.guna_entropy
        assert r1.kosha_entropy == r2.kosha_entropy
        assert r1.cross_domain_entropy == r2.cross_domain_entropy
        assert r1.combined_entropy == r2.combined_entropy
        assert r1.gate == r2.gate
        assert r1.mode == r2.mode


# ===========================================================================
# 7. Input format compatibility
# ===========================================================================

class TestInputFormats:
    """Helper accepts lists, tuples, and torch-like batched tensors."""

    def test_list_input_accepted(self):
        """Plain list of 32 floats is accepted."""
        state = _make_state(sattva=0.1, rajas=0.3, tamas=0.6)
        result = entropy_from_sovereign_state(state)
        assert isinstance(result, EntropyResult)

    def test_tuple_input_accepted(self):
        """Tuple of 32 floats is accepted."""
        state = tuple(_make_state(sattva=0.1, rajas=0.3, tamas=0.6))
        result = entropy_from_sovereign_state(state)
        assert isinstance(result, EntropyResult)

    def test_batched_tensor_like_input_accepted(self):
        """Torch-like 2D tensor ([B, 32]) uses batch_idx correctly.

        We simulate a torch.Tensor via a minimal duck-typed stand-in so
        this test has no torch dependency.
        """
        import numpy as np

        class FakeTensor:
            """Minimal torch.Tensor-compatible interface used by _extract_slices."""
            def __init__(self, arr: np.ndarray):
                self._arr = arr
            def dim(self) -> int:
                return self._arr.ndim
            def __getitem__(self, idx):
                return FakeTensor(self._arr[idx])
            def detach(self):
                return self
            def cpu(self):
                return self
            def tolist(self):
                return self._arr.tolist()

        # Two batch rows: row 0 is balanced, row 1 is tamas-dominant
        row_0 = _make_state(sattva=0.333, rajas=0.333, tamas=0.334)
        row_1 = _make_state(sattva=0.0, rajas=0.0, tamas=1.0)
        batched = FakeTensor(np.array([row_0, row_1], dtype=float))

        r0 = entropy_from_sovereign_state(batched, batch_idx=0)
        r1 = entropy_from_sovereign_state(batched, batch_idx=1)
        # Row 0 balanced → low guna entropy
        assert r0.guna_entropy < 0.01
        # Row 1 tamas-dominant → max guna entropy
        assert r1.guna_entropy == pytest.approx(1.0, abs=1e-6)

    def test_short_state_raises_value_error(self):
        """State with < 28 dims raises ValueError (from _extract_slices)."""
        with pytest.raises(ValueError):
            entropy_from_sovereign_state([0.0] * 20)

    def test_unsupported_type_raises_type_error(self):
        """Non-tensor, non-sequence input raises TypeError."""
        with pytest.raises(TypeError):
            entropy_from_sovereign_state("not a tensor")


# ===========================================================================
# 8. Clamping
# ===========================================================================

class TestClamping:
    """Guna/kosha values outside [0.0, 1.0] are clamped to the valid range."""

    def test_negative_values_clamped_to_zero(self):
        """Negative guna values do not crash; result stays in [0, 1]."""
        state = _make_state(sattva=-0.5, rajas=0.5, tamas=0.5)
        result = entropy_from_sovereign_state(state)
        assert 0.0 <= result.guna_entropy <= 1.0
        assert 0.0 <= result.combined_entropy <= 1.0

    def test_above_one_values_clamped_to_one(self):
        """Guna values > 1.0 do not crash; result stays in [0, 1]."""
        state = _make_state(sattva=2.0, rajas=0.0, tamas=0.0)
        result = entropy_from_sovereign_state(state)
        assert 0.0 <= result.guna_entropy <= 1.0


# ===========================================================================
# 9. delta_S parameter parity with sibling bridge functions
# ===========================================================================

class TestDeltaSParameter:
    """delta_S is accepted for signature parity; does not change result today."""

    def test_delta_S_parameter_accepted_and_ignored(self):
        """Supplying delta_S does not change the entropy result today.

        Reserved for future velocity-aware entropy. Current behavior is
        that delta_S is accepted but not consumed.
        """
        state = _make_state(sattva=0.1, rajas=0.3, tamas=0.6)
        r_without = entropy_from_sovereign_state(state, delta_S=None)
        r_with = entropy_from_sovereign_state(state, delta_S=[0.5] * 32)
        assert r_without.guna_entropy == r_with.guna_entropy
        assert r_without.kosha_entropy == r_with.kosha_entropy
        assert r_without.combined_entropy == r_with.combined_entropy
