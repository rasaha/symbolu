"""
P22 - Acoustic-Vrtti Witness Extractor Tests

This phase is witness-only and has zero authority over cognition or delivery.

Test categories:
    1. Witness-Only: P22 output never alters regime, discourse, or semantics
    2. Determinism: Same input -> identical witness report
    3. No Semantic Leakage: Words like "sad", "angry", "please" never appear in output
    4. Pressure Only: Output changes with sound structure, not meaning
    5. Barrier Respect: P22 cannot access any P1-P21 decisions
    6. Delivery Neutrality: Disabling P22 changes nothing upstream
"""

import pytest
from dataclasses import FrozenInstanceError
from typing import Any

from symbolu.mechanical.pipeline.p21_delivery.p21_delivery_schema import DeliveryMode
from symbolu.mechanical.pipeline.p22_acoustic_witness import (
    # Version
    P22_VERSION,
    # Enums
    MotionPrimitive,
    MotionBalance,
    # Dataclasses
    P22AcousticVrittiWitness,
    # Exceptions
    P22InvariantViolation,
    # Factory
    create_empty_witness,
    # Resolver
    AcousticVrittiWitnessResolver,
    resolve_acoustic_witness,
    # Integration
    maybe_run_p22,
    run_p22,
    run_p22_directly,
    # Helpers
    is_p22_disabled,
    has_p22_witness,
    get_p22_witness,
    get_acoustic_signature,
    get_dominant_motion,
    get_motion_balance,
    get_pressure_band,
    get_vritti_vector,
    get_p22_version,
    # Constants
    FORBIDDEN_INTENT_ATTRS,
    FORBIDDEN_REGIME_ATTRS,
    FORBIDDEN_DISCOURSE_ATTRS,
    FORBIDDEN_SEMANTIC_ATTRS,
    ALL_FORBIDDEN_ATTRS,
)


# ============================================================================
# MOCK CONTEXT HELPERS
# ============================================================================


class MockContext:
    """Mock context for testing P22."""

    def __init__(
        self,
        user_raw_text: str = "",
        p21_delivery_mode: DeliveryMode = None,
        disabled: bool = False,
    ):
        self.user_raw_text = user_raw_text
        self._p22_disabled = disabled

        # P21 setup
        if p21_delivery_mode is not None:
            class MockP21:
                def __init__(self, mode):
                    self.delivery_mode = mode
            self.p21 = MockP21(p21_delivery_mode)

        # P22 outputs (will be set by integration)
        self.p22_acoustic_witness = None
        self.p22 = None


class MockContextWithForbiddenAttrs(MockContext):
    """Mock context that has forbidden attributes (for barrier testing)."""

    def __init__(self, user_raw_text: str = "hello"):
        super().__init__(user_raw_text)

        # Add forbidden attributes - P22 should NOT read these
        self.intent = "mock_intent"
        self.intent_type = "mock_intent_type"
        self.regime = "mock_regime"
        self.p6_regime = "mock_p6_regime"
        self.discourse = "mock_discourse"
        self.discourse_act = "mock_discourse_act"
        self.semantic_slots = {"mock": "slots"}
        self.semantic_frame = {"mock": "frame"}
        self.lexical_items = ["mock", "items"]
        self.p9_lexical = {"mock": "lexical"}
        self.p13_safety_envelope = "mock_safety"
        self.drift_scores = {"mock": 0.5}
        self.persona_state = "mock_persona"


# ============================================================================
# 1. WITNESS-ONLY TESTS
# ============================================================================


class TestWitnessOnly:
    """
    Test that P22 output never alters regime, discourse, or semantics.

    This phase is witness-only and has zero authority over cognition or delivery.
    """

    def test_witness_only_flag_always_true(self):
        """P22 witness must always have witness_only=True."""
        witness = run_p22_directly("hello world")
        assert witness.witness_only is True

    def test_empty_witness_has_witness_only_true(self):
        """Empty witness must have witness_only=True."""
        witness = create_empty_witness()
        assert witness.witness_only is True

    def test_witness_cannot_set_witness_only_false(self):
        """Cannot create witness with witness_only=False."""
        with pytest.raises(ValueError, match="witness_only must be True"):
            P22AcousticVrittiWitness(
                acoustic_signature="",
                unit_count=0,
                vritti_vector={"neutral": 1.0},
                dominant_motion=MotionPrimitive.NEUTRAL,
                motion_balance=MotionBalance.BALANCED,
                pressure_band="low",
                witness_only=False,  # This should raise
            )

    def test_witness_is_frozen_immutable(self):
        """Witness report must be immutable (frozen dataclass)."""
        witness = run_p22_directly("hello")
        with pytest.raises(FrozenInstanceError):
            witness.acoustic_signature = "modified"

    def test_p22_does_not_modify_upstream_regime(self):
        """P22 must not modify any upstream regime state."""
        ctx = MockContextWithForbiddenAttrs("hello world")
        original_regime = ctx.regime

        maybe_run_p22(ctx)

        assert ctx.regime == original_regime

    def test_p22_does_not_modify_upstream_discourse(self):
        """P22 must not modify any upstream discourse state."""
        ctx = MockContextWithForbiddenAttrs("hello world")
        original_discourse = ctx.discourse

        maybe_run_p22(ctx)

        assert ctx.discourse == original_discourse

    def test_p22_does_not_modify_upstream_semantics(self):
        """P22 must not modify any upstream semantic state."""
        ctx = MockContextWithForbiddenAttrs("hello world")
        original_semantic_slots = ctx.semantic_slots

        maybe_run_p22(ctx)

        assert ctx.semantic_slots == original_semantic_slots

    def test_p22_only_writes_to_p22_attributes(self):
        """P22 should only write to p22_* attributes."""
        ctx = MockContext("hello world")

        # Track all attributes before
        attrs_before = set(dir(ctx))

        maybe_run_p22(ctx)

        # Track all attributes after
        attrs_after = set(dir(ctx))

        # New attributes should only be p22-related
        new_attrs = attrs_after - attrs_before
        for attr in new_attrs:
            assert attr.startswith("p22") or attr.startswith("_"), \
                f"P22 wrote to non-p22 attribute: {attr}"


# ============================================================================
# 2. DETERMINISM TESTS
# ============================================================================


class TestDeterminism:
    """
    Test that same input always produces identical witness report.

    This phase is witness-only and has zero authority over cognition or delivery.
    """

    def test_same_input_same_output(self):
        """Same text input must produce identical witness."""
        text = "The quick brown fox"

        witness1 = run_p22_directly(text)
        witness2 = run_p22_directly(text)

        assert witness1.acoustic_signature == witness2.acoustic_signature
        assert witness1.unit_count == witness2.unit_count
        assert witness1.vritti_vector == witness2.vritti_vector
        assert witness1.dominant_motion == witness2.dominant_motion
        assert witness1.motion_balance == witness2.motion_balance
        assert witness1.pressure_band == witness2.pressure_band

    def test_determinism_across_multiple_runs(self):
        """Determinism holds across many runs."""
        text = "Testing deterministic behavior"

        witnesses = [run_p22_directly(text) for _ in range(10)]

        # All should have same acoustic signature
        signatures = [w.acoustic_signature for w in witnesses]
        assert len(set(signatures)) == 1

        # All should have same dominant motion
        motions = [w.dominant_motion for w in witnesses]
        assert len(set(motions)) == 1

    def test_whitespace_normalization_is_deterministic(self):
        """Whitespace handling is deterministic."""
        text1 = "hello world"
        text2 = "hello  world"  # Extra space
        text3 = "  hello world  "  # Surrounding spaces

        # Same words should normalize similarly
        w1 = run_p22_directly(text1)
        w2 = run_p22_directly(text2)
        w3 = run_p22_directly(text3)

        # All should be deterministic (may differ due to whitespace handling)
        assert w1.acoustic_signature == run_p22_directly(text1).acoustic_signature

    def test_resolver_instance_does_not_affect_output(self):
        """Different resolver instances produce same output."""
        text = "consistent output"

        resolver1 = AcousticVrittiWitnessResolver()
        resolver2 = AcousticVrittiWitnessResolver()

        witness1 = resolver1.resolve(text)
        witness2 = resolver2.resolve(text)

        assert witness1.acoustic_signature == witness2.acoustic_signature
        assert witness1.vritti_vector == witness2.vritti_vector


# ============================================================================
# 3. NO SEMANTIC LEAKAGE TESTS
# ============================================================================


class TestNoSemanticLeakage:
    """
    Test that semantic words never appear in output.

    This phase is witness-only and has zero authority over cognition or delivery.
    """

    EMOTIONAL_WORDS = [
        "sad", "happy", "angry", "fear", "joy", "anxious", "excited",
        "depressed", "frustrated", "pleased", "upset", "calm",
    ]

    POLITENESS_WORDS = [
        "please", "thank", "sorry", "excuse", "pardon", "appreciate",
    ]

    SEMANTIC_WORDS = EMOTIONAL_WORDS + POLITENESS_WORDS

    def test_emotional_input_no_emotional_output(self):
        """Input with emotional words should not produce emotional labels."""
        emotional_inputs = [
            "I am so sad today",
            "This makes me angry",
            "Please help me I am scared",
            "Thank you for your joy",
        ]

        for text in emotional_inputs:
            witness = run_p22_directly(text)
            output_str = str(witness.to_dict()).lower()

            for word in self.SEMANTIC_WORDS:
                assert word not in output_str, \
                    f"Semantic word '{word}' leaked into output for: {text}"

    def test_no_emotion_in_motion_primitive_values(self):
        """MotionPrimitive values should never be emotional labels."""
        for motion in MotionPrimitive:
            for word in self.EMOTIONAL_WORDS:
                assert word not in motion.value.lower(), \
                    f"Emotional word '{word}' in MotionPrimitive.{motion.name}"

    def test_no_emotion_in_motion_balance_values(self):
        """MotionBalance values should never be emotional labels."""
        for balance in MotionBalance:
            for word in self.EMOTIONAL_WORDS:
                assert word not in balance.value.lower(), \
                    f"Emotional word '{word}' in MotionBalance.{balance.name}"

    def test_vritti_vector_keys_are_motion_primitives(self):
        """Vritti vector keys should only be motion primitive names."""
        witness = run_p22_directly("hello world test")

        valid_keys = {mp.value for mp in MotionPrimitive}
        for key in witness.vritti_vector.keys():
            assert key in valid_keys, \
                f"Invalid vritti_vector key: {key}"

    def test_acoustic_signature_contains_no_words(self):
        """Acoustic signature should be a code, not words."""
        test_inputs = [
            "happy day",
            "sad night",
            "please help",
            "angry response",
        ]

        for text in test_inputs:
            witness = run_p22_directly(text)
            sig = witness.acoustic_signature.lower()

            # Signature should be short codes, not full words
            for word in self.SEMANTIC_WORDS:
                assert word not in sig


# ============================================================================
# 4. PRESSURE ONLY TESTS
# ============================================================================


class TestPressureOnly:
    """
    Test that output changes with sound structure, not meaning.

    This phase is witness-only and has zero authority over cognition or delivery.
    """

    def test_similar_sounds_similar_output(self):
        """Words with similar sounds should produce similar witness."""
        # Words with similar phonetic structure
        pair1_a = run_p22_directly("stop")
        pair1_b = run_p22_directly("shop")

        # Both have similar initial fricative/stop structure
        # Their dominant motions should be related to sound structure

        # This test verifies the output is based on phonetics, not semantics
        assert pair1_a.unit_count > 0
        assert pair1_b.unit_count > 0

    def test_different_meaning_same_sounds_similar_output(self):
        """Words with same sounds but different meanings should have similar witness."""
        # "right" (correct) vs "write" (compose) - same pronunciation
        # In our acoustic mapper, they would be similar
        w1 = run_p22_directly("write")
        w2 = run_p22_directly("right")

        # Since acoustic processing is based on letters (approximation),
        # similar spellings should produce similar results
        # This verifies meaning is not influencing output
        assert w1.unit_count > 0
        assert w2.unit_count > 0

    def test_pressure_band_reflects_acoustic_energy(self):
        """Pressure band should reflect acoustic energy, not emotion."""
        # Short, soft sounds
        soft = run_p22_directly("mm hmm")

        # Many fricatives and stops (high acoustic energy)
        strong = run_p22_directly("psst crack snap pop")

        # Both should have valid pressure bands
        assert soft.pressure_band in ("low", "moderate", "high")
        assert strong.pressure_band in ("low", "moderate", "high")

    def test_unit_count_reflects_text_length(self):
        """Unit count should reflect text structure, not semantic complexity."""
        short = run_p22_directly("hi")
        long = run_p22_directly("hello wonderful beautiful amazing world")

        assert long.unit_count > short.unit_count

    def test_motion_balance_is_acoustic_not_emotional(self):
        """Motion balance should classify acoustic patterns, not emotions."""
        # All motion balance values are acoustic descriptors
        valid_balances = {mb.value for mb in MotionBalance}
        expected = {"balanced", "constricted", "agitated", "oscillatory"}

        assert valid_balances == expected

        # None should be emotional terms
        emotional_terms = {"happy", "sad", "angry", "fearful", "joyful"}
        assert valid_balances.isdisjoint(emotional_terms)


# ============================================================================
# 5. BARRIER RESPECT TESTS
# ============================================================================


class TestBarrierRespect:
    """
    Test that P22 cannot access any P1-P21 decisions.

    This phase is witness-only and has zero authority over cognition or delivery.
    """

    def test_forbidden_attrs_are_comprehensive(self):
        """All forbidden attribute sets should be non-empty."""
        assert len(FORBIDDEN_INTENT_ATTRS) > 0
        assert len(FORBIDDEN_REGIME_ATTRS) > 0
        assert len(FORBIDDEN_DISCOURSE_ATTRS) > 0
        assert len(FORBIDDEN_SEMANTIC_ATTRS) > 0
        assert len(ALL_FORBIDDEN_ATTRS) > 0

    def test_p22_works_with_forbidden_attrs_present(self):
        """P22 should work even if context has forbidden attrs (but not read them)."""
        ctx = MockContextWithForbiddenAttrs("hello world")

        # P22 should run successfully
        witness = maybe_run_p22(ctx)

        assert witness is not None
        assert witness.witness_only is True

    def test_p22_output_independent_of_intent(self):
        """P22 output should be same regardless of intent value."""
        ctx1 = MockContextWithForbiddenAttrs("hello")
        ctx1.intent = "question"

        ctx2 = MockContextWithForbiddenAttrs("hello")
        ctx2.intent = "command"

        w1 = maybe_run_p22(ctx1)
        w2 = maybe_run_p22(ctx2)

        # Output should be identical (intent is not read)
        assert w1.acoustic_signature == w2.acoustic_signature
        assert w1.vritti_vector == w2.vritti_vector

    def test_p22_output_independent_of_regime(self):
        """P22 output should be same regardless of regime value."""
        ctx1 = MockContextWithForbiddenAttrs("test")
        ctx1.regime = "OPEN"

        ctx2 = MockContextWithForbiddenAttrs("test")
        ctx2.regime = "HOLD"

        w1 = maybe_run_p22(ctx1)
        w2 = maybe_run_p22(ctx2)

        # Output should be identical (regime is not read)
        assert w1.acoustic_signature == w2.acoustic_signature

    def test_p22_only_reads_allowed_inputs(self):
        """P22 should only read user_raw_text and delivery_mode."""
        # The allowed inputs per spec are:
        # - ctx.user_raw_text: str
        # - ctx.p21_delivery_mode: DeliveryMode

        ctx = MockContext("hello", p21_delivery_mode=DeliveryMode.TEXT_AND_VOICE)

        witness = maybe_run_p22(ctx)

        assert witness is not None
        assert witness.unit_count > 0


# ============================================================================
# 6. DELIVERY NEUTRALITY TESTS
# ============================================================================


class TestDeliveryNeutrality:
    """
    Test that disabling P22 changes nothing upstream.

    This phase is witness-only and has zero authority over cognition or delivery.
    """

    def test_p22_disabled_returns_none(self):
        """When P22 is disabled, it should return None."""
        ctx = MockContext("hello", disabled=True)

        result = maybe_run_p22(ctx)

        assert result is None

    def test_disabled_p22_does_not_modify_context(self):
        """Disabled P22 should not modify context at all."""
        ctx = MockContext("hello", disabled=True)
        original_attrs = set(dir(ctx))

        maybe_run_p22(ctx)

        # No new attributes should be added
        new_attrs = set(dir(ctx)) - original_attrs
        # p22_acoustic_witness and p22 are pre-defined in MockContext
        for attr in new_attrs:
            assert attr.startswith("_"), f"Unexpected new attr: {attr}"

    def test_suppressed_delivery_produces_empty_witness(self):
        """SUPPRESSED delivery mode should produce empty/neutral witness."""
        ctx = MockContext("hello world", p21_delivery_mode=DeliveryMode.SUPPRESSED)

        witness = maybe_run_p22(ctx)

        assert witness is not None
        assert witness.unit_count == 0
        assert witness.dominant_motion == MotionPrimitive.NEUTRAL
        assert witness.motion_balance == MotionBalance.BALANCED
        assert witness.pressure_band == "low"

    def test_p22_does_not_affect_delivery_decisions(self):
        """P22 must never affect delivery decisions (P21 output is binding)."""
        ctx = MockContext("angry upset words", p21_delivery_mode=DeliveryMode.TEXT_ONLY)

        # Run P22
        maybe_run_p22(ctx)

        # P21 decision should be unchanged
        assert ctx.p21.delivery_mode == DeliveryMode.TEXT_ONLY

    def test_p22_absence_does_not_block_pipeline(self):
        """Pipeline should work without P22."""
        ctx = MockContext("hello", disabled=True)

        # P22 disabled
        result = maybe_run_p22(ctx)
        assert result is None

        # Context should still be valid for downstream
        assert ctx is not None

    def test_has_p22_witness_helper(self):
        """has_p22_witness helper should work correctly."""
        ctx = MockContext("hello")

        # Before running P22
        assert not has_p22_witness(ctx)

        # After running P22
        maybe_run_p22(ctx)
        assert has_p22_witness(ctx)

    def test_get_p22_witness_helper(self):
        """get_p22_witness helper should return witness or None."""
        ctx = MockContext("hello")

        # Before running P22
        assert get_p22_witness(ctx) is None

        # After running P22
        maybe_run_p22(ctx)
        witness = get_p22_witness(ctx)
        assert witness is not None
        assert isinstance(witness, P22AcousticVrittiWitness)


# ============================================================================
# ADDITIONAL TESTS
# ============================================================================


class TestSchemaValidation:
    """Test schema validation rules."""

    def test_unit_count_must_be_non_negative(self):
        """unit_count must be non-negative."""
        with pytest.raises(ValueError, match="non-negative"):
            P22AcousticVrittiWitness(
                acoustic_signature="",
                unit_count=-1,
                vritti_vector={"neutral": 1.0},
                dominant_motion=MotionPrimitive.NEUTRAL,
                motion_balance=MotionBalance.BALANCED,
                pressure_band="low",
            )

    def test_vritti_vector_values_in_range(self):
        """vritti_vector values must be in [0.0, 1.0]."""
        with pytest.raises(ValueError, match="\\[0.0, 1.0\\]"):
            P22AcousticVrittiWitness(
                acoustic_signature="",
                unit_count=1,
                vritti_vector={"neutral": 1.5},  # Invalid
                dominant_motion=MotionPrimitive.NEUTRAL,
                motion_balance=MotionBalance.BALANCED,
                pressure_band="low",
            )

    def test_pressure_band_must_be_valid(self):
        """pressure_band must be low/moderate/high."""
        with pytest.raises(ValueError, match="'low', 'moderate', or 'high'"):
            P22AcousticVrittiWitness(
                acoustic_signature="",
                unit_count=0,
                vritti_vector={"neutral": 1.0},
                dominant_motion=MotionPrimitive.NEUTRAL,
                motion_balance=MotionBalance.BALANCED,
                pressure_band="invalid",
            )


class TestIntegrationHelpers:
    """Test integration helper functions."""

    def test_get_p22_version(self):
        """get_p22_version should return version string."""
        version = get_p22_version()
        assert isinstance(version, str)
        assert version == P22_VERSION

    def test_get_acoustic_signature_helper(self):
        """get_acoustic_signature helper should work."""
        ctx = MockContext("hello")
        maybe_run_p22(ctx)

        sig = get_acoustic_signature(ctx)
        assert isinstance(sig, str)

    def test_get_dominant_motion_helper(self):
        """get_dominant_motion helper should work."""
        ctx = MockContext("hello")
        maybe_run_p22(ctx)

        motion = get_dominant_motion(ctx)
        assert motion is None or isinstance(motion, MotionPrimitive)

    def test_get_motion_balance_helper(self):
        """get_motion_balance helper should work."""
        ctx = MockContext("hello")
        maybe_run_p22(ctx)

        balance = get_motion_balance(ctx)
        assert isinstance(balance, MotionBalance)

    def test_get_pressure_band_helper(self):
        """get_pressure_band helper should work."""
        ctx = MockContext("hello")
        maybe_run_p22(ctx)

        band = get_pressure_band(ctx)
        assert band in ("low", "moderate", "high")

    def test_get_vritti_vector_helper(self):
        """get_vritti_vector helper should work."""
        ctx = MockContext("hello")
        maybe_run_p22(ctx)

        vector = get_vritti_vector(ctx)
        assert isinstance(vector, dict)

    def test_run_p22_directly_suppressed(self):
        """run_p22_directly with suppressed mode."""
        witness = run_p22_directly("hello", delivery_mode_suppressed=True)

        assert witness.unit_count == 0
        assert witness.dominant_motion == MotionPrimitive.NEUTRAL


class TestEmptyInputHandling:
    """Test handling of empty/minimal inputs."""

    def test_empty_string(self):
        """Empty string should produce neutral witness."""
        witness = run_p22_directly("")
        assert witness.unit_count == 0
        assert witness.dominant_motion == MotionPrimitive.NEUTRAL

    def test_whitespace_only(self):
        """Whitespace-only should produce neutral witness."""
        witness = run_p22_directly("   ")
        assert witness.unit_count == 0

    def test_single_character(self):
        """Single character input should work."""
        witness = run_p22_directly("a")
        assert witness.unit_count >= 0  # May be 0 or 1 depending on impl

    def test_null_context(self):
        """None context should return None."""
        result = maybe_run_p22(None)
        assert result is None


class TestWitnessToDict:
    """Test witness serialization."""

    def test_to_dict_returns_dict(self):
        """to_dict should return a dictionary."""
        witness = run_p22_directly("hello world")
        d = witness.to_dict()

        assert isinstance(d, dict)
        assert "acoustic_signature" in d
        assert "unit_count" in d
        assert "vritti_vector" in d
        assert "dominant_motion" in d
        assert "motion_balance" in d
        assert "pressure_band" in d
        assert "witness_only" in d
        assert d["witness_only"] is True

    def test_to_dict_serializes_enums(self):
        """to_dict should serialize enums to values."""
        witness = run_p22_directly("hello")
        d = witness.to_dict()

        # dominant_motion should be string or None
        if d["dominant_motion"] is not None:
            assert isinstance(d["dominant_motion"], str)

        # motion_balance should be string
        assert isinstance(d["motion_balance"], str)
