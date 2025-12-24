"""
Tests for GCC Runtime Guard (symbolu/safety/gcc_runtime_guard.py)

These tests validate the Generative Containment Constraint enforcement:
- Non-expressive value validation
- Violation exception handling
- Decorator functionality
- Edge cases for all allowed/disallowed types
"""

import pytest
from dataclasses import dataclass, FrozenInstanceError
from enum import Enum

from symbolu.safety.gcc_runtime_guard import (
    is_non_expressive,
    assert_non_expressive,
    GCCViolationError,
    gcc_guarded,
    _is_hex_string,
    _is_invariant_key,
    _is_phase_id,
    _is_valid_string,
    MAX_INVARIANT_KEY_LENGTH,
)


# =============================================================================
# Test Fixtures
# =============================================================================


class SampleEnum(Enum):
    """Sample enum for testing."""
    VALUE_A = 1
    VALUE_B = 2
    VALUE_C = 3


class AnotherEnum(Enum):
    """Another enum to test variety."""
    HIGH = "high"
    LOW = "low"


@dataclass(frozen=True)
class FrozenDataclass:
    """Frozen dataclass for testing."""
    count: int
    flag: bool


@dataclass(frozen=True)
class NestedFrozenDataclass:
    """Nested frozen dataclass for testing."""
    inner: FrozenDataclass
    label: str  # Must be valid invariant key or hex


@dataclass(frozen=True)
class ComplexFrozenDataclass:
    """Complex frozen dataclass with tuples."""
    values: tuple
    enum_val: SampleEnum


@dataclass
class MutableDataclass:
    """Mutable dataclass (should fail validation)."""
    count: int
    flag: bool


# =============================================================================
# Tests for _is_hex_string
# =============================================================================


class TestIsHexString:
    """Tests for _is_hex_string helper function."""

    def test_valid_hex_lowercase(self):
        """Lowercase hex strings should pass."""
        assert _is_hex_string("deadbeef") is True
        assert _is_hex_string("0123456789abcdef") is True
        assert _is_hex_string("a" * 64) is True

    def test_valid_hex_uppercase(self):
        """Uppercase hex strings should pass."""
        assert _is_hex_string("DEADBEEF") is True
        assert _is_hex_string("0123456789ABCDEF") is True

    def test_valid_hex_mixed_case(self):
        """Mixed case hex strings should pass."""
        assert _is_hex_string("DeAdBeEf") is True
        assert _is_hex_string("aAbBcCdDeEfF") is True

    def test_empty_string_fails(self):
        """Empty string should fail."""
        assert _is_hex_string("") is False

    def test_non_hex_chars_fail(self):
        """Non-hex characters should fail."""
        assert _is_hex_string("hello") is False
        assert _is_hex_string("ghijk") is False
        assert _is_hex_string("xyz123") is False

    def test_spaces_fail(self):
        """Strings with spaces should fail."""
        assert _is_hex_string("dead beef") is False
        assert _is_hex_string(" abc123") is False

    def test_special_chars_fail(self):
        """Strings with special characters should fail."""
        assert _is_hex_string("abc-def") is False
        assert _is_hex_string("abc_def") is False
        assert _is_hex_string("abc.def") is False


# =============================================================================
# Tests for _is_invariant_key
# =============================================================================


class TestIsInvariantKey:
    """Tests for _is_invariant_key helper function."""

    def test_valid_invariant_keys(self):
        """Valid invariant keys should pass."""
        assert _is_invariant_key("NON_EXPRESSIVE") is True
        assert _is_invariant_key("PHASE_1B") is True
        assert _is_invariant_key("FAIL_CLOSED") is True
        assert _is_invariant_key("A") is True
        assert _is_invariant_key("A1") is True

    def test_uppercase_only(self):
        """Only uppercase letters are allowed."""
        assert _is_invariant_key("lowercase") is False
        assert _is_invariant_key("MixedCase") is False

    def test_max_length(self):
        """Keys exceeding max length should fail."""
        long_key = "A" * (MAX_INVARIANT_KEY_LENGTH + 1)
        assert _is_invariant_key(long_key) is False

        valid_key = "A" * MAX_INVARIANT_KEY_LENGTH
        assert _is_invariant_key(valid_key) is True

    def test_empty_string_fails(self):
        """Empty string should fail."""
        assert _is_invariant_key("") is False

    def test_no_special_chars(self):
        """Special characters (except underscore) should fail."""
        assert _is_invariant_key("HELLO-WORLD") is False
        assert _is_invariant_key("HELLO.WORLD") is False
        assert _is_invariant_key("HELLO WORLD") is False

    def test_underscores_allowed(self):
        """Underscores should be allowed."""
        assert _is_invariant_key("HELLO_WORLD") is True
        assert _is_invariant_key("A_B_C_D") is True


# =============================================================================
# Tests for _is_phase_id
# =============================================================================


class TestIsPhaseId:
    """Tests for _is_phase_id helper function."""

    def test_valid_phase_ids(self):
        """Valid phase IDs should pass."""
        assert _is_phase_id("1b") is True
        assert _is_phase_id("2") is True
        assert _is_phase_id("3") is True
        assert _is_phase_id("9") is True

    def test_invalid_phase_ids(self):
        """Invalid phase IDs should fail."""
        assert _is_phase_id("1") is False
        assert _is_phase_id("1a") is False
        assert _is_phase_id("10") is False
        assert _is_phase_id("phase1") is False
        assert _is_phase_id("") is False


# =============================================================================
# Tests for _is_valid_string
# =============================================================================


class TestIsValidString:
    """Tests for _is_valid_string helper function."""

    def test_empty_string_allowed(self):
        """Empty string is explicitly allowed."""
        assert _is_valid_string("") is True

    def test_hex_strings_allowed(self):
        """Hex strings should pass."""
        assert _is_valid_string("deadbeef") is True
        assert _is_valid_string("a" * 64) is True

    def test_invariant_keys_allowed(self):
        """Invariant keys should pass."""
        assert _is_valid_string("NON_EXPRESSIVE") is True
        assert _is_valid_string("PHASE_1B") is True

    def test_phase_ids_allowed(self):
        """Phase IDs should pass."""
        assert _is_valid_string("1b") is True
        assert _is_valid_string("5") is True

    def test_version_strings_allowed(self):
        """Router version strings should pass."""
        assert _is_valid_string("R1.0") is True
        assert _is_valid_string("M1.0") is True
        assert _is_valid_string("R2.5") is True

    def test_free_text_rejected(self):
        """Free-form text should be rejected."""
        assert _is_valid_string("Hello world") is False
        assert _is_valid_string("This is a sentence.") is False
        assert _is_valid_string("I feel happy") is False


# =============================================================================
# Tests for is_non_expressive - Allowed Types
# =============================================================================


class TestIsNonExpressiveAllowedTypes:
    """Tests for is_non_expressive with allowed types."""

    def test_none_allowed(self):
        """None should be allowed."""
        assert is_non_expressive(None) is True

    def test_int_allowed(self):
        """Integers should be allowed."""
        assert is_non_expressive(0) is True
        assert is_non_expressive(42) is True
        assert is_non_expressive(-100) is True
        assert is_non_expressive(999999) is True

    def test_bool_allowed(self):
        """Booleans should be allowed."""
        assert is_non_expressive(True) is True
        assert is_non_expressive(False) is True

    def test_enum_allowed(self):
        """Enum values should be allowed."""
        assert is_non_expressive(SampleEnum.VALUE_A) is True
        assert is_non_expressive(SampleEnum.VALUE_B) is True
        assert is_non_expressive(AnotherEnum.HIGH) is True

    def test_hex_string_allowed(self):
        """Hex strings should be allowed."""
        assert is_non_expressive("deadbeef") is True
        assert is_non_expressive("0123456789abcdef") is True

    def test_invariant_key_allowed(self):
        """Invariant keys should be allowed."""
        assert is_non_expressive("NON_EXPRESSIVE") is True
        assert is_non_expressive("FAIL_CLOSED") is True

    def test_empty_string_allowed(self):
        """Empty string should be allowed."""
        assert is_non_expressive("") is True

    def test_tuple_of_allowed_types(self):
        """Tuples of allowed types should be allowed."""
        assert is_non_expressive((1, 2, 3)) is True
        assert is_non_expressive((True, False, True)) is True
        assert is_non_expressive((SampleEnum.VALUE_A, 42)) is True
        assert is_non_expressive(()) is True  # Empty tuple

    def test_nested_tuples(self):
        """Nested tuples should be allowed."""
        assert is_non_expressive((1, (2, 3), 4)) is True
        assert is_non_expressive(((1, 2), (3, 4))) is True

    def test_frozenset_of_allowed_types(self):
        """Frozensets of allowed types should be allowed."""
        assert is_non_expressive(frozenset([1, 2, 3])) is True
        assert is_non_expressive(frozenset()) is True  # Empty frozenset

    def test_frozen_dataclass_allowed(self):
        """Frozen dataclasses with allowed fields should be allowed."""
        dc = FrozenDataclass(count=5, flag=True)
        assert is_non_expressive(dc) is True

    def test_complex_frozen_dataclass(self):
        """Complex frozen dataclasses should be allowed."""
        dc = ComplexFrozenDataclass(
            values=(1, 2, 3),
            enum_val=SampleEnum.VALUE_A
        )
        assert is_non_expressive(dc) is True


# =============================================================================
# Tests for is_non_expressive - Violation Types
# =============================================================================


class TestIsNonExpressiveViolations:
    """Tests for is_non_expressive with violation types."""

    def test_list_violation(self):
        """Lists should be rejected (mutable)."""
        assert is_non_expressive([1, 2, 3]) is False
        assert is_non_expressive([]) is False

    def test_dict_violation(self):
        """Dicts should be rejected (mutable)."""
        assert is_non_expressive({"key": "value"}) is False
        assert is_non_expressive({}) is False

    def test_set_violation(self):
        """Sets should be rejected (mutable)."""
        assert is_non_expressive({1, 2, 3}) is False
        assert is_non_expressive(set()) is False

    def test_free_text_violation(self):
        """Free-form text should be rejected."""
        assert is_non_expressive("Hello world") is False
        assert is_non_expressive("This is a sentence.") is False
        assert is_non_expressive("I feel happy") is False

    def test_float_violation(self):
        """Floats should be rejected."""
        assert is_non_expressive(3.14) is False
        assert is_non_expressive(0.0) is False

    def test_bytes_violation(self):
        """Bytes should be rejected."""
        assert is_non_expressive(b"hello") is False

    def test_tuple_with_violation(self):
        """Tuples containing violations should fail."""
        assert is_non_expressive((1, "Hello world", 3)) is False
        assert is_non_expressive((1, [2, 3], 4)) is False

    def test_nested_violation(self):
        """Nested violations should be detected."""
        assert is_non_expressive((1, (2, "free text"))) is False


# =============================================================================
# Tests for assert_non_expressive - Success Cases
# =============================================================================


class TestAssertNonExpressiveSuccess:
    """Tests for assert_non_expressive success cases."""

    def test_none_passes(self):
        """None should pass without exception."""
        assert_non_expressive(None)  # Should not raise

    def test_int_passes(self):
        """Integers should pass without exception."""
        assert_non_expressive(42)
        assert_non_expressive(0)
        assert_non_expressive(-100)

    def test_bool_passes(self):
        """Booleans should pass without exception."""
        assert_non_expressive(True)
        assert_non_expressive(False)

    def test_enum_passes(self):
        """Enums should pass without exception."""
        assert_non_expressive(SampleEnum.VALUE_A)

    def test_hex_string_passes(self):
        """Hex strings should pass without exception."""
        assert_non_expressive("deadbeef")

    def test_tuple_passes(self):
        """Tuples should pass without exception."""
        assert_non_expressive((1, 2, 3))

    def test_frozen_dataclass_passes(self):
        """Frozen dataclasses should pass without exception."""
        dc = FrozenDataclass(count=5, flag=True)
        assert_non_expressive(dc)


# =============================================================================
# Tests for assert_non_expressive - Violation Cases
# =============================================================================


class TestAssertNonExpressiveViolations:
    """Tests for assert_non_expressive violation cases."""

    def test_list_raises_violation(self):
        """Lists should raise GCCViolationError."""
        with pytest.raises(GCCViolationError) as exc_info:
            assert_non_expressive([1, 2, 3])
        assert exc_info.value.reason == GCCViolationError.REASON_MUTABLE_CONTAINER

    def test_dict_raises_violation(self):
        """Dicts should raise GCCViolationError."""
        with pytest.raises(GCCViolationError) as exc_info:
            assert_non_expressive({"key": "value"})
        assert exc_info.value.reason == GCCViolationError.REASON_MUTABLE_CONTAINER

    def test_set_raises_violation(self):
        """Sets should raise GCCViolationError."""
        with pytest.raises(GCCViolationError) as exc_info:
            assert_non_expressive({1, 2, 3})
        assert exc_info.value.reason == GCCViolationError.REASON_MUTABLE_CONTAINER

    def test_free_text_raises_violation(self):
        """Free text should raise GCCViolationError."""
        with pytest.raises(GCCViolationError) as exc_info:
            assert_non_expressive("Hello world")
        assert exc_info.value.reason == GCCViolationError.REASON_FREE_TEXT

    def test_long_string_raises_violation(self):
        """Long non-hex strings should raise with STRING_TOO_LONG."""
        long_text = "x" * (MAX_INVARIANT_KEY_LENGTH + 10)
        with pytest.raises(GCCViolationError) as exc_info:
            assert_non_expressive(long_text)
        assert exc_info.value.reason == GCCViolationError.REASON_STRING_TOO_LONG

    def test_invalid_type_raises_violation(self):
        """Invalid types should raise GCCViolationError."""
        with pytest.raises(GCCViolationError) as exc_info:
            assert_non_expressive(3.14)
        assert exc_info.value.reason == GCCViolationError.REASON_INVALID_TYPE

    def test_nested_violation_detected(self):
        """Nested violations should be detected."""
        with pytest.raises(GCCViolationError):
            assert_non_expressive((1, "Hello world", 3))

    def test_path_in_violation_error(self):
        """Violation error should include path information."""
        with pytest.raises(GCCViolationError) as exc_info:
            assert_non_expressive((1, 2, "bad text"))
        assert "[2]" in exc_info.value.path


# =============================================================================
# Tests for GCCViolationError
# =============================================================================


class TestGCCViolationError:
    """Tests for GCCViolationError exception class."""

    def test_error_has_value(self):
        """Error should store the violating value."""
        error = GCCViolationError([1, 2, 3], reason=GCCViolationError.REASON_MUTABLE_CONTAINER)
        assert error.value == [1, 2, 3]

    def test_error_has_reason(self):
        """Error should have reason code."""
        error = GCCViolationError("test", reason=GCCViolationError.REASON_FREE_TEXT)
        assert error.reason == GCCViolationError.REASON_FREE_TEXT

    def test_error_has_path(self):
        """Error should have path for nested violations."""
        error = GCCViolationError("test", path="foo.bar[0]", reason=GCCViolationError.REASON_FREE_TEXT)
        assert error.path == "foo.bar[0]"

    def test_error_message_format(self):
        """Error message should be structured."""
        error = GCCViolationError("test", path="field", reason=GCCViolationError.REASON_FREE_TEXT)
        assert "GCC_VIOLATION" in str(error)
        assert "FREE_TEXT" in str(error)
        assert "PATH=field" in str(error)

    def test_all_reason_codes(self):
        """All reason codes should be valid."""
        reasons = [
            GCCViolationError.REASON_FREE_TEXT,
            GCCViolationError.REASON_INVALID_TYPE,
            GCCViolationError.REASON_NON_HEX_STRING,
            GCCViolationError.REASON_STRING_TOO_LONG,
            GCCViolationError.REASON_MUTABLE_CONTAINER,
            GCCViolationError.REASON_MUTABLE_DATACLASS,
            GCCViolationError.REASON_NESTED_VIOLATION,
        ]
        for reason in reasons:
            error = GCCViolationError("test", reason=reason)
            assert error.reason == reason


# =============================================================================
# Tests for gcc_guarded Decorator
# =============================================================================


class TestGccGuardedDecorator:
    """Tests for gcc_guarded decorator."""

    def test_decorator_allows_valid_return(self):
        """Decorator should allow valid return values."""
        @gcc_guarded
        def valid_function():
            return (1, 2, 3)

        result = valid_function()
        assert result == (1, 2, 3)

    def test_decorator_allows_none_return(self):
        """Decorator should allow None return."""
        @gcc_guarded
        def none_function():
            return None

        result = none_function()
        assert result is None

    def test_decorator_allows_int_return(self):
        """Decorator should allow int return."""
        @gcc_guarded
        def int_function():
            return 42

        result = int_function()
        assert result == 42

    def test_decorator_rejects_list_return(self):
        """Decorator should reject list return."""
        @gcc_guarded
        def list_function():
            return [1, 2, 3]

        with pytest.raises(GCCViolationError):
            list_function()

    def test_decorator_rejects_free_text_return(self):
        """Decorator should reject free text return."""
        @gcc_guarded
        def text_function():
            return "Hello world"

        with pytest.raises(GCCViolationError):
            text_function()

    def test_decorator_preserves_function_name(self):
        """Decorator should preserve function name."""
        @gcc_guarded
        def my_function():
            return 42

        assert my_function.__name__ == "my_function"

    def test_decorator_preserves_docstring(self):
        """Decorator should preserve docstring."""
        @gcc_guarded
        def documented_function():
            """This is a docstring."""
            return 42

        assert documented_function.__doc__ == "This is a docstring."

    def test_decorator_with_arguments(self):
        """Decorator should work with function arguments."""
        @gcc_guarded
        def add_function(a, b):
            return a + b

        result = add_function(1, 2)
        assert result == 3

    def test_decorator_path_includes_function_name(self):
        """Violation path should include function name."""
        @gcc_guarded
        def problematic_function():
            return "bad text"

        with pytest.raises(GCCViolationError) as exc_info:
            problematic_function()
        assert "problematic_function" in exc_info.value.path


# =============================================================================
# Edge Cases and Boundary Tests
# =============================================================================


class TestEdgeCases:
    """Edge cases and boundary tests."""

    def test_deeply_nested_valid_structure(self):
        """Deeply nested valid structures should pass."""
        deep = (1, (2, (3, (4, (5,)))))
        assert is_non_expressive(deep) is True
        assert_non_expressive(deep)  # Should not raise

    def test_deeply_nested_violation(self):
        """Deeply nested violations should be detected."""
        deep = (1, (2, (3, (4, ("bad text",)))))
        assert is_non_expressive(deep) is False
        with pytest.raises(GCCViolationError):
            assert_non_expressive(deep)

    def test_mixed_valid_tuple(self):
        """Mixed tuple with all valid types should pass."""
        mixed = (
            42,
            True,
            SampleEnum.VALUE_A,
            "deadbeef",
            "NON_EXPRESSIVE",
            (1, 2),
            frozenset([1, 2]),
        )
        assert is_non_expressive(mixed) is True

    def test_empty_containers(self):
        """Empty containers: tuple/frozenset allowed, list/dict/set not."""
        assert is_non_expressive(()) is True
        assert is_non_expressive(frozenset()) is True
        assert is_non_expressive([]) is False
        assert is_non_expressive({}) is False
        assert is_non_expressive(set()) is False

    def test_single_element_containers(self):
        """Single element containers should behave correctly."""
        assert is_non_expressive((42,)) is True
        assert is_non_expressive(frozenset([42])) is True
        assert is_non_expressive([42]) is False

    def test_version_string_formats(self):
        """Various version string formats should be tested."""
        assert is_non_expressive("R1.0") is True
        assert is_non_expressive("M1.0") is True
        assert is_non_expressive("R99.99") is True
        assert is_non_expressive("V1.0") is False  # Only R and M allowed


# =============================================================================
# Integration-style Tests
# =============================================================================


class TestIntegration:
    """Integration-style tests simulating real usage."""

    def test_phase_exit_scenario(self):
        """Simulate a Phase exit with valid return."""
        @gcc_guarded
        def phase_3_exit(artifact_id, result_count):
            return (
                artifact_id,  # int
                result_count,  # int
                True,  # success flag
                "abcdef123456",  # hex hash
            )

        result = phase_3_exit(42, 5)
        assert result == (42, 5, True, "abcdef123456")

    def test_ontological_router_scenario(self):
        """Simulate Ontological Router R1 output."""
        @gcc_guarded
        def ontological_router_r1(layer_id):
            return (
                layer_id,  # int
                SampleEnum.VALUE_A,  # routing decision
                (1, 2, 3),  # score tuple
            )

        result = ontological_router_r1(5)
        assert result[0] == 5

    def test_ledger_replay_scenario(self):
        """Simulate Ledger replay verification."""
        @gcc_guarded
        def ledger_verify(entry_hash):
            return (
                True,  # valid
                entry_hash,  # hex hash
                42,  # entry count
            )

        result = ledger_verify("deadbeef")
        assert result[0] is True
