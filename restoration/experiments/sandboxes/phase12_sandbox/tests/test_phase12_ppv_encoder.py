"""
Tests for Phase-12 PPV Conditioning Encoder
============================================

Test Categories:
    1. Determinism - Same input → same output (100+ runs)
    2. Strategy Coverage - All 4 strategies produce valid output
    3. Input Validation - Invalid inputs rejected
    4. Frozen Constraint - Encoder config cannot change
    5. Signal Properties - Output signals have correct structure
"""

import pytest
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from phase12_schema import (
    PPV_DIM_COUNT,
    CANONICAL_SUBBANDS,
    PPVEncodingStrategy,
    PPVConditioningSignal,
)
from phase12_ppv_encoder import (
    FrozenPPVEncoder,
    create_embedding_encoder,
    create_soft_prompt_encoder,
    create_adapter_encoder,
    create_text_prefix_encoder,
    get_default_encoder,
    DEFAULT_EMBEDDING_DIM,
    SOFT_PROMPT_VOCAB_BASE,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_ppv() -> tuple:
    """Sample PPV values covering all bands."""
    return (0, 1, 2, 3, 4, 5, 6, 7)


@pytest.fixture
def canonical_signature() -> str:
    """Canonical signature matching sample_ppv after B.3 canonicalization."""
    # L0,L0,L2,M0,M0,M2,H0,H1
    return "L0_L0_L2_M0_M0_M2_H0_H1"


@pytest.fixture
def all_low_ppv() -> tuple:
    """All-low PPV values."""
    return (0, 0, 0, 0, 0, 0, 0, 0)


@pytest.fixture
def all_low_signature() -> str:
    """Canonical signature for all-low."""
    return "L0_L0_L0_L0_L0_L0_L0_L0"


@pytest.fixture
def all_high_ppv() -> tuple:
    """All-high PPV values."""
    return (7, 7, 7, 7, 7, 7, 7, 7)


@pytest.fixture
def all_high_signature() -> str:
    """Canonical signature for all-high."""
    return "H1_H1_H1_H1_H1_H1_H1_H1"


# =============================================================================
# Test: Determinism (100-run consistency)
# =============================================================================

class TestDeterminism:
    """Tests for encoding determinism."""

    def test_embedding_determinism_100_runs(
        self, sample_ppv, canonical_signature
    ):
        """EMBEDDING strategy produces identical output over 100 runs."""
        encoder = create_embedding_encoder()
        first_result = encoder.encode(sample_ppv, canonical_signature)

        for _ in range(100):
            result = encoder.encode(sample_ppv, canonical_signature)
            assert result.conditioning_data == first_result.conditioning_data
            assert result.signal_hash() == first_result.signal_hash()

    def test_soft_prompt_determinism_100_runs(
        self, sample_ppv, canonical_signature
    ):
        """SOFT_PROMPT strategy produces identical output over 100 runs."""
        encoder = create_soft_prompt_encoder()
        first_result = encoder.encode(sample_ppv, canonical_signature)

        for _ in range(100):
            result = encoder.encode(sample_ppv, canonical_signature)
            assert result.conditioning_data == first_result.conditioning_data
            assert result.signal_hash() == first_result.signal_hash()

    def test_adapter_determinism_100_runs(
        self, sample_ppv, canonical_signature
    ):
        """ADAPTER strategy produces identical output over 100 runs."""
        encoder = create_adapter_encoder()
        first_result = encoder.encode(sample_ppv, canonical_signature)

        for _ in range(100):
            result = encoder.encode(sample_ppv, canonical_signature)
            assert result.conditioning_data == first_result.conditioning_data
            assert result.signal_hash() == first_result.signal_hash()

    def test_text_prefix_determinism_100_runs(
        self, sample_ppv, canonical_signature
    ):
        """TEXT_PREFIX strategy produces identical output over 100 runs."""
        encoder = create_text_prefix_encoder()
        first_result = encoder.encode(sample_ppv, canonical_signature)

        for _ in range(100):
            result = encoder.encode(sample_ppv, canonical_signature)
            assert result.conditioning_data == first_result.conditioning_data
            assert result.signal_hash() == first_result.signal_hash()

    def test_different_inputs_different_outputs(
        self,
        sample_ppv,
        canonical_signature,
        all_low_ppv,
        all_low_signature,
        all_high_ppv,
        all_high_signature,
    ):
        """Different PPV inputs produce different conditioning signals."""
        encoder = create_embedding_encoder()

        signal_1 = encoder.encode(sample_ppv, canonical_signature)
        signal_2 = encoder.encode(all_low_ppv, all_low_signature)
        signal_3 = encoder.encode(all_high_ppv, all_high_signature)

        # All should be different
        assert signal_1.signal_hash() != signal_2.signal_hash()
        assert signal_2.signal_hash() != signal_3.signal_hash()
        assert signal_1.signal_hash() != signal_3.signal_hash()


# =============================================================================
# Test: Strategy Coverage
# =============================================================================

class TestStrategyCoverage:
    """Tests that all strategies produce valid output."""

    def test_embedding_produces_float_tuple(
        self, sample_ppv, canonical_signature
    ):
        """EMBEDDING produces tuple of floats."""
        encoder = create_embedding_encoder(embedding_dim=64)
        signal = encoder.encode(sample_ppv, canonical_signature)

        assert signal.strategy == PPVEncodingStrategy.EMBEDDING
        assert isinstance(signal.conditioning_data, tuple)
        assert len(signal.conditioning_data) == 64
        assert all(isinstance(v, float) for v in signal.conditioning_data)
        assert all(-1.0 <= v <= 1.0 for v in signal.conditioning_data)

    def test_embedding_custom_dimension(
        self, sample_ppv, canonical_signature
    ):
        """EMBEDDING respects custom embedding_dim."""
        encoder = create_embedding_encoder(embedding_dim=128)
        signal = encoder.encode(sample_ppv, canonical_signature)

        assert len(signal.conditioning_data) == 128

    def test_soft_prompt_produces_int_tuple(
        self, sample_ppv, canonical_signature
    ):
        """SOFT_PROMPT produces tuple of integers."""
        encoder = create_soft_prompt_encoder(num_tokens=8)
        signal = encoder.encode(sample_ppv, canonical_signature)

        assert signal.strategy == PPVEncodingStrategy.SOFT_PROMPT
        assert isinstance(signal.conditioning_data, tuple)
        assert len(signal.conditioning_data) == 8
        assert all(isinstance(v, int) for v in signal.conditioning_data)
        assert all(v >= SOFT_PROMPT_VOCAB_BASE for v in signal.conditioning_data)

    def test_soft_prompt_custom_tokens(
        self, sample_ppv, canonical_signature
    ):
        """SOFT_PROMPT respects custom num_tokens."""
        encoder = create_soft_prompt_encoder(num_tokens=16)
        signal = encoder.encode(sample_ppv, canonical_signature)

        assert len(signal.conditioning_data) == 16

    def test_adapter_produces_string(
        self, sample_ppv, canonical_signature
    ):
        """ADAPTER produces adapter ID string."""
        encoder = create_adapter_encoder()
        signal = encoder.encode(sample_ppv, canonical_signature)

        assert signal.strategy == PPVEncodingStrategy.ADAPTER
        assert isinstance(signal.conditioning_data, str)
        assert signal.conditioning_data.startswith("ppv_adapter_")
        assert canonical_signature in signal.conditioning_data

    def test_text_prefix_produces_string(
        self, sample_ppv, canonical_signature
    ):
        """TEXT_PREFIX produces human-readable string."""
        encoder = create_text_prefix_encoder()
        signal = encoder.encode(sample_ppv, canonical_signature)

        assert signal.strategy == PPVEncodingStrategy.TEXT_PREFIX
        assert isinstance(signal.conditioning_data, str)
        assert "[PPV:" in signal.conditioning_data
        assert canonical_signature in signal.conditioning_data

    def test_text_prefix_custom_template(
        self, sample_ppv, canonical_signature
    ):
        """TEXT_PREFIX respects custom template."""
        encoder = create_text_prefix_encoder(template="<style={signature}>")
        signal = encoder.encode(sample_ppv, canonical_signature)

        assert f"<style={canonical_signature}>" == signal.conditioning_data


# =============================================================================
# Test: Input Validation
# =============================================================================

class TestInputValidation:
    """Tests for input validation."""

    def test_wrong_ppv_length_rejected(self, canonical_signature):
        """PPV with wrong number of dimensions is rejected."""
        encoder = get_default_encoder()

        with pytest.raises(ValueError, match="must have 8 elements"):
            encoder.encode((0, 1, 2), canonical_signature)

        with pytest.raises(ValueError, match="must have 8 elements"):
            encoder.encode((0, 1, 2, 3, 4, 5, 6, 7, 8, 9), canonical_signature)

    def test_ppv_out_of_range_rejected(self, canonical_signature):
        """PPV values outside [0, 7] are rejected."""
        encoder = get_default_encoder()

        with pytest.raises(ValueError, match="out of range"):
            encoder.encode((-1, 1, 2, 3, 4, 5, 6, 7), canonical_signature)

        with pytest.raises(ValueError, match="out of range"):
            encoder.encode((0, 1, 2, 3, 4, 5, 6, 8), canonical_signature)

    def test_invalid_signature_format_rejected(self, sample_ppv):
        """Invalid canonical signature format is rejected."""
        encoder = get_default_encoder()

        with pytest.raises(ValueError, match="must have 8 parts"):
            encoder.encode(sample_ppv, "L0_M0_H0")

        with pytest.raises(ValueError, match="must have 8 parts"):
            encoder.encode(sample_ppv, "L0_M0_H0_L0_M0_H0_L0_M0_H0")

    def test_invalid_subband_in_signature_rejected(self, sample_ppv):
        """Invalid subband names in signature are rejected."""
        encoder = get_default_encoder()

        with pytest.raises(ValueError, match="Invalid subband"):
            encoder.encode(sample_ppv, "L0_L1_L2_M0_M1_M2_H0_H1")  # L1, M1 not canonical

        with pytest.raises(ValueError, match="Invalid subband"):
            encoder.encode(sample_ppv, "XX_L0_L2_M0_M2_H0_H1_L0")


# =============================================================================
# Test: Frozen Constraint
# =============================================================================

class TestFrozenConstraint:
    """Tests that encoder is truly frozen."""

    def test_encoder_is_frozen_dataclass(self):
        """FrozenPPVEncoder is a frozen dataclass."""
        encoder = get_default_encoder()

        with pytest.raises(AttributeError):
            encoder._config = None  # type: ignore

    def test_config_is_frozen(self):
        """Encoder config is frozen."""
        encoder = get_default_encoder()
        config = encoder.config

        with pytest.raises(AttributeError):
            config.strategy = PPVEncodingStrategy.ADAPTER  # type: ignore

    def test_config_frozen_flag_is_true(self):
        """All encoder configs have frozen=True."""
        encoders = [
            create_embedding_encoder(),
            create_soft_prompt_encoder(),
            create_adapter_encoder(),
            create_text_prefix_encoder(),
            get_default_encoder(),
        ]

        for encoder in encoders:
            assert encoder.config.frozen is True


# =============================================================================
# Test: Signal Properties
# =============================================================================

class TestSignalProperties:
    """Tests for PPVConditioningSignal structure."""

    def test_signal_preserves_raw_ppv(self, sample_ppv, canonical_signature):
        """Signal contains original PPV values."""
        encoder = get_default_encoder()
        signal = encoder.encode(sample_ppv, canonical_signature)

        assert signal.raw_ppv == sample_ppv

    def test_signal_preserves_signature(self, sample_ppv, canonical_signature):
        """Signal contains canonical signature."""
        encoder = get_default_encoder()
        signal = encoder.encode(sample_ppv, canonical_signature)

        assert signal.canonical_signature == canonical_signature

    def test_signal_hash_is_deterministic(self, sample_ppv, canonical_signature):
        """Signal hash is deterministic."""
        encoder = get_default_encoder()

        hashes = set()
        for _ in range(100):
            signal = encoder.encode(sample_ppv, canonical_signature)
            hashes.add(signal.signal_hash())

        assert len(hashes) == 1

    def test_signal_hash_is_16_chars(self, sample_ppv, canonical_signature):
        """Signal hash is 16 hex characters."""
        encoder = get_default_encoder()
        signal = encoder.encode(sample_ppv, canonical_signature)

        hash_val = signal.signal_hash()
        assert len(hash_val) == 16
        assert all(c in "0123456789abcdef" for c in hash_val)


# =============================================================================
# Test: Default Encoder
# =============================================================================

class TestDefaultEncoder:
    """Tests for default encoder selection."""

    def test_default_is_text_prefix(self):
        """Default encoder uses TEXT_PREFIX strategy."""
        encoder = get_default_encoder()
        assert encoder.config.strategy == PPVEncodingStrategy.TEXT_PREFIX

    def test_default_works_correctly(self, sample_ppv, canonical_signature):
        """Default encoder produces valid output."""
        encoder = get_default_encoder()
        signal = encoder.encode(sample_ppv, canonical_signature)

        assert signal.strategy == PPVEncodingStrategy.TEXT_PREFIX
        assert isinstance(signal.conditioning_data, str)
        assert len(signal.conditioning_data) > 0


# =============================================================================
# Test: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_all_zeros_ppv(self):
        """Encoder handles all-zero PPV."""
        encoder = get_default_encoder()
        ppv = (0, 0, 0, 0, 0, 0, 0, 0)
        sig = "L0_L0_L0_L0_L0_L0_L0_L0"

        signal = encoder.encode(ppv, sig)
        assert signal.raw_ppv == ppv
        assert signal.canonical_signature == sig

    def test_all_sevens_ppv(self):
        """Encoder handles all-seven PPV."""
        encoder = get_default_encoder()
        ppv = (7, 7, 7, 7, 7, 7, 7, 7)
        sig = "H1_H1_H1_H1_H1_H1_H1_H1"

        signal = encoder.encode(ppv, sig)
        assert signal.raw_ppv == ppv
        assert signal.canonical_signature == sig

    def test_mixed_bands_ppv(self):
        """Encoder handles PPV with all canonical subbands."""
        encoder = get_default_encoder()
        ppv = (0, 2, 3, 5, 6, 7, 0, 5)
        sig = "L0_L2_M0_M2_H0_H1_L0_M2"

        signal = encoder.encode(ppv, sig)
        assert signal.raw_ppv == ppv

    def test_embedding_values_bounded(self):
        """Embedding values stay within [-1, 1]."""
        encoder = create_embedding_encoder(embedding_dim=256)

        # Test with various PPV values
        test_cases = [
            ((0, 0, 0, 0, 0, 0, 0, 0), "L0_L0_L0_L0_L0_L0_L0_L0"),
            ((7, 7, 7, 7, 7, 7, 7, 7), "H1_H1_H1_H1_H1_H1_H1_H1"),
            ((0, 2, 3, 5, 6, 7, 0, 5), "L0_L2_M0_M2_H0_H1_L0_M2"),
        ]

        for ppv, sig in test_cases:
            signal = encoder.encode(ppv, sig)
            for val in signal.conditioning_data:
                assert -1.0 <= val <= 1.0, f"Value {val} out of bounds"


# =============================================================================
# Test: Injectivity (Collision Testing)
# =============================================================================

class TestInjectivity:
    """Tests that different inputs produce different outputs."""

    def test_different_signatures_different_embeddings(self):
        """Different canonical signatures produce different embeddings."""
        encoder = create_embedding_encoder()

        # Generate multiple different canonical signatures
        signatures = [
            ("L0_L0_L0_L0_L0_L0_L0_L0", (0, 0, 0, 0, 0, 0, 0, 0)),
            ("H1_H1_H1_H1_H1_H1_H1_H1", (7, 7, 7, 7, 7, 7, 7, 7)),
            ("L2_L2_L2_L2_L2_L2_L2_L2", (2, 2, 2, 2, 2, 2, 2, 2)),
            ("M0_M0_M0_M0_M0_M0_M0_M0", (3, 3, 3, 3, 3, 3, 3, 3)),
            ("M2_M2_M2_M2_M2_M2_M2_M2", (5, 5, 5, 5, 5, 5, 5, 5)),
            ("H0_H0_H0_H0_H0_H0_H0_H0", (6, 6, 6, 6, 6, 6, 6, 6)),
        ]

        hashes = set()
        for sig, ppv in signatures:
            signal = encoder.encode(ppv, sig)
            hashes.add(signal.signal_hash())

        # All should be unique
        assert len(hashes) == len(signatures)

    def test_single_dimension_change_produces_different_output(self):
        """Changing one PPV dimension produces different output."""
        encoder = create_embedding_encoder()

        base_ppv = (0, 0, 0, 0, 0, 0, 0, 0)
        base_sig = "L0_L0_L0_L0_L0_L0_L0_L0"
        base_signal = encoder.encode(base_ppv, base_sig)

        # Change each dimension one at a time
        # Only test changes that keep us within the L0 canonical representative
        # (since sig must match PPV)
        modified_ppv = (0, 0, 0, 0, 0, 0, 0, 7)
        modified_sig = "L0_L0_L0_L0_L0_L0_L0_H1"
        modified_signal = encoder.encode(modified_ppv, modified_sig)

        assert base_signal.signal_hash() != modified_signal.signal_hash()


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
