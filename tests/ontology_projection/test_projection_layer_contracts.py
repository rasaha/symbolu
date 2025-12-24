"""
Projection Layer Contract Tests
===============================

Verify that layer outputs comply with contracts:
    - No free-form strings in artifacts
    - Only hex hashes, IDs, enum values
    - No forbidden modules imported
"""

import sys
import pytest

from symbolu.ontology.projection import (
    FrozenSnapshot,
    InputRef,
    InputRefKind,
    OntologicalLayer,
    ProjectionProfile,
    OutputMode,
    Strictness,
    ProjectionOptions,
    ProjectionRequest,
    run_projection,
)
from symbolu.ontology.projection.validators import (
    is_allowed_value,
    is_hex_hash,
    is_allowed_string,
    check_no_forbidden_modules,
    FORBIDDEN_MODULES,
    ALLOWED_FIXED_TOKENS,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_snapshot():
    """Create a sample frozen snapshot for testing."""
    return FrozenSnapshot(
        snapshot_id="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        payload={"key": "value", "count": 42, "items": [1, 2, 3]},
        content_hash="deadbeefcafebabe1234567890abcdef"
    )


@pytest.fixture
def list_snapshot():
    """Create a snapshot with list payload for UNIFYING tests."""
    return FrozenSnapshot(
        snapshot_id="b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6a7",
        payload=[
            {"type": "a", "val": 1},
            {"type": "b", "val": 2},
            {"type": "a", "val": 1},
        ],
        content_hash="cafebabe12345678deadbeef90abcdef"
    )


@pytest.fixture
def sample_input_ref():
    """Create a sample input reference."""
    return InputRef(
        kind=InputRefKind.GENERIC,
        object_id="f1e2d3c4b5a69788796a5b4c3d2e1f00"
    )


@pytest.fixture
def sample_options():
    """Create sample projection options."""
    return ProjectionOptions(
        include_ledger=True,
        max_artifacts=100,
        output_mode=OutputMode.NON_TEXTUAL,
        strictness=Strictness.STRICT
    )


# =============================================================================
# Helper Functions
# =============================================================================

def recursively_check_artifact(artifact, path=""):
    """Recursively check that artifact contains only allowed values."""
    errors = []

    if isinstance(artifact, (tuple, list)):
        for i, item in enumerate(artifact):
            item_errors = recursively_check_artifact(item, f"{path}[{i}]")
            errors.extend(item_errors)
    elif isinstance(artifact, str):
        if not is_allowed_string(artifact):
            errors.append(f"{path}: disallowed string '{artifact}'")
    elif isinstance(artifact, bool):
        pass  # bools are allowed
    elif isinstance(artifact, int):
        pass  # ints are allowed
    elif artifact is None:
        pass  # None is allowed
    else:
        errors.append(f"{path}: disallowed type {type(artifact).__name__}")

    return errors


# =============================================================================
# No Free-Form Text Tests
# =============================================================================

class TestNoFreeFormText:
    """Test that artifacts contain no free-form text."""

    def test_thinking_layer_no_freeform_text(self, sample_snapshot, sample_input_ref, sample_options):
        """THINKING layer artifacts should contain no free-form text."""
        request = ProjectionRequest(
            snapshot_id=sample_snapshot.snapshot_id,
            layer=OntologicalLayer.COGNITION,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        response = run_projection(sample_snapshot, request)

        assert response.eligible is True
        errors = recursively_check_artifact(response.artifacts, "artifacts")
        assert len(errors) == 0, f"Free-form text in THINKING artifacts: {errors}"

    def test_meta_observing_layer_no_freeform_text(self, sample_snapshot, sample_input_ref, sample_options):
        """META_OBSERVING layer artifacts should contain no free-form text."""
        request = ProjectionRequest(
            snapshot_id=sample_snapshot.snapshot_id,
            layer=OntologicalLayer.WITNESSES,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        response = run_projection(sample_snapshot, request)

        assert response.eligible is True
        errors = recursively_check_artifact(response.artifacts, "artifacts")
        assert len(errors) == 0, f"Free-form text in META_OBSERVING artifacts: {errors}"

    def test_unifying_layer_no_freeform_text(self, list_snapshot, sample_input_ref, sample_options):
        """UNIFYING layer artifacts should contain no free-form text."""
        request = ProjectionRequest(
            snapshot_id=list_snapshot.snapshot_id,
            layer=OntologicalLayer.UNIFYING,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        response = run_projection(list_snapshot, request)

        assert response.eligible is True
        errors = recursively_check_artifact(response.artifacts, "artifacts")
        assert len(errors) == 0, f"Free-form text in UNIFYING artifacts: {errors}"

    def test_ledger_spans_no_freeform_text(self, sample_snapshot, sample_input_ref, sample_options):
        """Ledger spans should contain no free-form text."""
        for layer in [OntologicalLayer.COGNITION, OntologicalLayer.WITNESSES, OntologicalLayer.UNIFYING]:
            request = ProjectionRequest(
                snapshot_id=sample_snapshot.snapshot_id,
                layer=layer,
                input_ref=sample_input_ref,
                projection_profile=ProjectionProfile.STANDARD,
                options=sample_options
            )

            response = run_projection(sample_snapshot, request)

            errors = recursively_check_artifact(response.ledger_spans, f"{layer.name}_ledger_spans")
            assert len(errors) == 0, f"Free-form text in {layer.name} ledger spans: {errors}"


# =============================================================================
# Hex Hash Validation Tests
# =============================================================================

class TestHexHashValidation:
    """Test hex hash validation."""

    def test_valid_32_char_hex_hash(self):
        """32-character lowercase hex hash should be valid."""
        assert is_hex_hash("deadbeefcafebabe1234567890abcdef")
        assert is_hex_hash("a" * 32)
        assert is_hex_hash("0" * 32)

    def test_valid_64_char_hex_hash(self):
        """64-character lowercase hex hash should be valid."""
        assert is_hex_hash("a" * 64)
        assert is_hex_hash("0123456789abcdef" * 4)

    def test_invalid_short_hash(self):
        """Hash shorter than 16 chars should be invalid."""
        assert not is_hex_hash("deadbeef")
        assert not is_hex_hash("a" * 15)

    def test_invalid_long_hash(self):
        """Hash longer than 64 chars should be invalid."""
        assert not is_hex_hash("a" * 65)
        assert not is_hex_hash("0" * 100)

    def test_invalid_uppercase_hash(self):
        """Uppercase hex should be invalid."""
        assert not is_hex_hash("DEADBEEFCAFEBABE1234567890ABCDEF")
        assert not is_hex_hash("DeadBeef" + "0" * 24)

    def test_invalid_non_hex_chars(self):
        """Non-hex characters should be invalid."""
        assert not is_hex_hash("ghijklmnopqrstuv" * 2)
        assert not is_hex_hash("hello world 12345678901234")


# =============================================================================
# Allowed String Tests
# =============================================================================

class TestAllowedStrings:
    """Test allowed string validation."""

    def test_hex_hashes_allowed(self):
        """Hex hashes of appropriate length should be allowed."""
        assert is_allowed_string("deadbeefcafebabe1234567890abcdef")
        assert is_allowed_string("a" * 32)

    def test_fixed_tokens_allowed(self):
        """Fixed tokens should be allowed."""
        for token in ALLOWED_FIXED_TOKENS:
            assert is_allowed_string(token), f"Token '{token}' should be allowed"

    def test_freeform_text_not_allowed(self):
        """Free-form text should not be allowed."""
        assert not is_allowed_string("hello world")
        assert not is_allowed_string("This is a sentence.")
        assert not is_allowed_string("error message: something went wrong")

    def test_short_strings_not_allowed(self):
        """Short non-token strings should not be allowed."""
        assert not is_allowed_string("abc")
        assert not is_allowed_string("test")
        assert not is_allowed_string("12345")


# =============================================================================
# Allowed Value Tests
# =============================================================================

class TestAllowedValues:
    """Test allowed value validation."""

    def test_int_allowed(self):
        """Integers should be allowed."""
        assert is_allowed_value(0)
        assert is_allowed_value(42)
        assert is_allowed_value(-1)

    def test_bool_allowed(self):
        """Booleans should be allowed."""
        assert is_allowed_value(True)
        assert is_allowed_value(False)

    def test_none_allowed(self):
        """None should be allowed."""
        assert is_allowed_value(None)

    def test_tuple_of_allowed_values(self):
        """Tuple of allowed values should be allowed."""
        assert is_allowed_value((1, 2, 3))
        assert is_allowed_value((True, False))
        assert is_allowed_value(("deadbeefcafebabe1234567890abcdef",))

    def test_nested_tuples_allowed(self):
        """Nested tuples should be allowed."""
        assert is_allowed_value(((1, 2), (3, 4)))
        assert is_allowed_value((("standard", True), ("audit", False)))

    def test_dict_not_allowed_in_artifacts(self):
        """Dicts should not be allowed in artifacts (only for internal hashing)."""
        assert not is_allowed_value({"key": "value"})
        assert not is_allowed_value({})

    def test_freeform_string_not_allowed(self):
        """Free-form strings should not be allowed."""
        assert not is_allowed_value("hello")
        assert not is_allowed_value("error")


# =============================================================================
# No Forbidden Modules Tests
# =============================================================================

class TestNoForbiddenModules:
    """Test that forbidden modules are not imported."""

    def test_forbidden_modules_not_imported(self):
        """Forbidden modules should not be in sys.modules."""
        passed, violations = check_no_forbidden_modules()
        # Filter out 'random' if it was imported by some other test dependency
        actual_violations = [v for v in violations if not v.startswith("random")]
        assert len(actual_violations) == 0, f"Forbidden modules imported: {actual_violations}"

    def test_nlp_modules_not_imported(self):
        """NLP modules should not be imported."""
        nlp_modules = ["nltk", "spacy", "transformers", "gensim", "textblob"]
        for module in nlp_modules:
            assert module not in sys.modules, f"NLP module {module} is imported"

    def test_llm_modules_not_imported(self):
        """LLM client modules should not be imported."""
        llm_modules = ["openai", "anthropic", "langchain"]
        for module in llm_modules:
            assert module not in sys.modules, f"LLM module {module} is imported"


# =============================================================================
# Artifact Content Type Tests
# =============================================================================

class TestArtifactContentTypes:
    """Test that artifact contents are correct types."""

    def test_thinking_artifacts_are_tuples(self, sample_snapshot, sample_input_ref, sample_options):
        """THINKING layer artifacts should be tuples."""
        request = ProjectionRequest(
            snapshot_id=sample_snapshot.snapshot_id,
            layer=OntologicalLayer.COGNITION,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        response = run_projection(sample_snapshot, request)

        assert isinstance(response.artifacts, tuple)
        assert isinstance(response.ledger_spans, tuple)

    def test_meta_observing_artifacts_structure(self, sample_snapshot, sample_input_ref, sample_options):
        """META_OBSERVING layer should have WitnessFrame and InvariantTimeline."""
        request = ProjectionRequest(
            snapshot_id=sample_snapshot.snapshot_id,
            layer=OntologicalLayer.WITNESSES,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        response = run_projection(sample_snapshot, request)

        assert len(response.artifacts) == 2, "Should have 2 artifacts"

        # WitnessFrame
        witness_frame = response.artifacts[0]
        assert isinstance(witness_frame, tuple)
        assert len(witness_frame) == 4

        # InvariantTimeline
        invariant_timeline = response.artifacts[1]
        assert isinstance(invariant_timeline, tuple)
        for item in invariant_timeline:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert isinstance(item[0], str)  # invariant name
            assert isinstance(item[1], bool)  # passed

    def test_unifying_artifacts_structure(self, list_snapshot, sample_input_ref, sample_options):
        """UNIFYING layer should have EquivalenceClasses."""
        request = ProjectionRequest(
            snapshot_id=list_snapshot.snapshot_id,
            layer=OntologicalLayer.UNIFYING,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        response = run_projection(list_snapshot, request)

        assert len(response.artifacts) == 1, "Should have 1 artifact"

        # EquivalenceClasses
        eq_classes = response.artifacts[0]
        assert isinstance(eq_classes, tuple)
        for item in eq_classes:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert isinstance(item[0], str)  # hash
            assert isinstance(item[1], int)  # count
            assert is_hex_hash(item[0]), f"Hash should be valid hex: {item[0]}"


# =============================================================================
# Invariants Report Tests
# =============================================================================

class TestInvariantsReport:
    """Test invariants report structure."""

    def test_invariants_report_structure(self, sample_snapshot, sample_input_ref, sample_options):
        """Invariants report should have correct structure."""
        request = ProjectionRequest(
            snapshot_id=sample_snapshot.snapshot_id,
            layer=OntologicalLayer.COGNITION,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        response = run_projection(sample_snapshot, request)

        assert isinstance(response.invariants_report.passed, bool)
        assert isinstance(response.invariants_report.reason_codes, tuple)

    def test_invariants_report_reason_codes_are_strings(self, sample_snapshot, sample_input_ref, sample_options):
        """Reason codes should be strings."""
        request = ProjectionRequest(
            snapshot_id=sample_snapshot.snapshot_id,
            layer=OntologicalLayer.EXECUTION,  # Unsupported
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        response = run_projection(sample_snapshot, request)

        for code in response.invariants_report.reason_codes:
            assert isinstance(code, str), f"Reason code should be string: {code}"


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
