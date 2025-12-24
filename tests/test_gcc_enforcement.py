"""
GCC Enforcement Test Suite (C-1)
=================================

Comprehensive tests proving:
    1. Violations are rejected (fail-closed)
    2. No mutation occurs
    3. Determinism over >=100 runs
    4. Existing valid paths still pass unchanged

This test suite validates the Generative Containment Constraint
is enforced at both compile-time (static) and runtime levels.

Hard Requirements:
    - ALL tests must pass for CI to succeed
    - NO false negatives (missed violations)
    - NO false positives (valid code rejected)
    - Deterministic over 100+ runs
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any, FrozenSet, Tuple

import pytest

from symbolu.safety.gcc_runtime_guard import (
    GCC_INVARIANTS,
    GCCViolationError,
    MAX_INVARIANT_KEY_LENGTH,
    NonExpressiveValue,
    assert_non_expressive,
    gcc_guarded,
    is_non_expressive,
)
from symbolu.safety.gcc_ledger_invariant import (
    ALLOWED_LEDGER_FIELDS,
    LedgerInvariantViolation,
    assert_ledger_entry_valid,
    validate_ledger_entry_dict,
)
from symbolu.safety.gcc_static_scanner import (
    CONSTRAINED_PATHS,
    EXIT_SUCCESS,
    EXIT_VIOLATIONS,
    FORBIDDEN_IMPORTS,
    Allowlist,
    ViolationType,
    scan_file,
)


# =============================================================================
# Test Fixtures
# =============================================================================

class SampleEnum(Enum):
    """Sample enum for testing."""
    VALUE_A = 1
    VALUE_B = 2
    VALUE_C = 3


@dataclass(frozen=True)
class ValidFrozenDataclass:
    """Valid frozen dataclass for testing."""
    field_int: int
    field_bool: bool
    field_enum: SampleEnum
    field_hash: str  # Must be hex


@dataclass(frozen=True)
class NestedFrozenDataclass:
    """Nested frozen dataclass for testing."""
    inner: ValidFrozenDataclass
    values: Tuple[int, ...]


@dataclass
class MutableDataclass:
    """Mutable dataclass (should be rejected)."""
    field: str


@dataclass(frozen=True)
class LedgerEntryMock:
    """Mock ledger entry for testing."""
    entry_id: str
    prev_entry_id: str | None
    span_id: str
    artifact_id: str
    artifact_hash: str
    phase_id: str
    projected_layers: Tuple[SampleEnum, ...]
    router_version: str
    mapping_version: str
    seq: int


@dataclass(frozen=True)
class InvalidLedgerEntry:
    """Invalid ledger entry with forbidden field."""
    entry_id: str
    explanation: str  # FORBIDDEN


# =============================================================================
# GROUP 1: Runtime Guard - Violations Rejected (Fail-Closed)
# =============================================================================

class TestGCCRuntimeViolationsRejected:
    """Tests proving violations are rejected with hard failure."""

    def test_free_form_string_rejected(self) -> None:
        """Verify free-form strings are rejected."""
        with pytest.raises(GCCViolationError) as exc:
            assert_non_expressive("This is a free-form text string.")
        assert exc.value.reason == GCCViolationError.REASON_FREE_TEXT

    def test_long_string_rejected(self) -> None:
        """Verify non-hex strings exceeding 32 chars are rejected."""
        # Use mixed-case with non-hex chars to ensure it's not detected as hex
        long_string = "This is a long free form text string here!"
        with pytest.raises(GCCViolationError) as exc:
            assert_non_expressive(long_string)
        assert exc.value.reason == GCCViolationError.REASON_STRING_TOO_LONG

    def test_list_rejected(self) -> None:
        """Verify lists (mutable) are rejected."""
        with pytest.raises(GCCViolationError) as exc:
            assert_non_expressive([1, 2, 3])
        assert exc.value.reason == GCCViolationError.REASON_MUTABLE_CONTAINER

    def test_dict_rejected(self) -> None:
        """Verify dicts (mutable) are rejected."""
        with pytest.raises(GCCViolationError) as exc:
            assert_non_expressive({"key": "value"})
        assert exc.value.reason == GCCViolationError.REASON_MUTABLE_CONTAINER

    def test_set_rejected(self) -> None:
        """Verify sets (mutable) are rejected."""
        with pytest.raises(GCCViolationError) as exc:
            assert_non_expressive({1, 2, 3})
        assert exc.value.reason == GCCViolationError.REASON_MUTABLE_CONTAINER

    def test_nested_violation_rejected(self) -> None:
        """Verify nested violations are detected."""
        nested = (1, 2, (3, "free form text here"))
        with pytest.raises(GCCViolationError) as exc:
            assert_non_expressive(nested)
        # Path should be [2][1] (index 2 -> inner tuple, index 1 -> the string)
        assert "[2][1]" in exc.value.path

    def test_tuple_with_list_rejected(self) -> None:
        """Verify tuples containing lists are rejected."""
        with pytest.raises(GCCViolationError) as exc:
            assert_non_expressive((1, [2, 3]))
        assert exc.value.reason == GCCViolationError.REASON_MUTABLE_CONTAINER

    def test_frozenset_with_invalid_rejected(self) -> None:
        """Verify frozensets with invalid content are rejected."""
        # frozensets cannot contain lists, so test with string
        with pytest.raises(GCCViolationError):
            assert_non_expressive(frozenset({"valid hex", "invalid text!"}))

    def test_float_rejected(self) -> None:
        """Verify floats are rejected (not in allowed types)."""
        with pytest.raises(GCCViolationError) as exc:
            assert_non_expressive(3.14159)
        assert exc.value.reason == GCCViolationError.REASON_INVALID_TYPE

    def test_complex_rejected(self) -> None:
        """Verify complex numbers are rejected."""
        with pytest.raises(GCCViolationError) as exc:
            assert_non_expressive(1 + 2j)
        assert exc.value.reason == GCCViolationError.REASON_INVALID_TYPE

    def test_callable_rejected(self) -> None:
        """Verify callables are rejected."""
        with pytest.raises(GCCViolationError) as exc:
            assert_non_expressive(lambda x: x)
        assert exc.value.reason == GCCViolationError.REASON_INVALID_TYPE

    def test_class_rejected(self) -> None:
        """Verify class types are rejected."""
        with pytest.raises(GCCViolationError) as exc:
            assert_non_expressive(SampleEnum)
        assert exc.value.reason == GCCViolationError.REASON_INVALID_TYPE


# =============================================================================
# GROUP 2: Runtime Guard - Valid Values Accepted
# =============================================================================

class TestGCCRuntimeValidAccepted:
    """Tests proving valid values are accepted."""

    def test_none_accepted(self) -> None:
        """Verify None is accepted."""
        assert_non_expressive(None)

    def test_int_accepted(self) -> None:
        """Verify integers are accepted."""
        assert_non_expressive(42)
        assert_non_expressive(0)
        assert_non_expressive(-1)
        assert_non_expressive(10**100)

    def test_bool_accepted(self) -> None:
        """Verify booleans are accepted."""
        assert_non_expressive(True)
        assert_non_expressive(False)

    def test_enum_accepted(self) -> None:
        """Verify enums are accepted."""
        assert_non_expressive(SampleEnum.VALUE_A)
        assert_non_expressive(SampleEnum.VALUE_B)

    def test_hex_string_accepted(self) -> None:
        """Verify hex strings are accepted."""
        assert_non_expressive("abc123")
        assert_non_expressive("DEADBEEF")
        assert_non_expressive("0123456789abcdef")
        # Long hex strings are allowed
        assert_non_expressive("a" * 64)

    def test_invariant_key_accepted(self) -> None:
        """Verify invariant keys are accepted."""
        assert_non_expressive("VALID_KEY")
        assert_non_expressive("INVARIANT_123")
        assert_non_expressive("A")

    def test_phase_id_accepted(self) -> None:
        """Verify phase IDs are accepted."""
        for phase in ["1b", "2", "3", "4", "5", "6", "7", "8", "9"]:
            assert_non_expressive(phase)

    def test_version_string_accepted(self) -> None:
        """Verify version strings are accepted."""
        assert_non_expressive("R1.0")
        assert_non_expressive("M1.0")

    def test_empty_string_accepted(self) -> None:
        """Verify empty string is accepted."""
        assert_non_expressive("")

    def test_tuple_of_valid_accepted(self) -> None:
        """Verify tuples of valid values are accepted."""
        assert_non_expressive((1, 2, 3))
        assert_non_expressive((True, False))
        assert_non_expressive((SampleEnum.VALUE_A, SampleEnum.VALUE_B))
        assert_non_expressive(("abc123", "def456"))

    def test_nested_tuple_accepted(self) -> None:
        """Verify nested tuples are accepted."""
        assert_non_expressive((1, (2, (3, 4))))

    def test_frozenset_of_valid_accepted(self) -> None:
        """Verify frozensets of valid values are accepted."""
        assert_non_expressive(frozenset({1, 2, 3}))
        assert_non_expressive(frozenset({SampleEnum.VALUE_A}))

    def test_frozen_dataclass_accepted(self) -> None:
        """Verify frozen dataclasses are accepted."""
        dc = ValidFrozenDataclass(
            field_int=42,
            field_bool=True,
            field_enum=SampleEnum.VALUE_A,
            field_hash="abc123",
        )
        assert_non_expressive(dc)

    def test_nested_frozen_dataclass_accepted(self) -> None:
        """Verify nested frozen dataclasses are accepted."""
        inner = ValidFrozenDataclass(
            field_int=1,
            field_bool=False,
            field_enum=SampleEnum.VALUE_B,
            field_hash="deadbeef",
        )
        outer = NestedFrozenDataclass(inner=inner, values=(1, 2, 3))
        assert_non_expressive(outer)


# =============================================================================
# GROUP 3: Runtime Guard - No Mutation
# =============================================================================

class TestGCCNoMutation:
    """Tests proving no mutation occurs during validation."""

    def test_tuple_not_mutated(self) -> None:
        """Verify tuples are not mutated."""
        original = (1, 2, 3)
        original_id = id(original)
        assert_non_expressive(original)
        assert id(original) == original_id
        assert original == (1, 2, 3)

    def test_frozenset_not_mutated(self) -> None:
        """Verify frozensets are not mutated."""
        original = frozenset({1, 2, 3})
        original_id = id(original)
        assert_non_expressive(original)
        assert id(original) == original_id
        assert original == frozenset({1, 2, 3})

    def test_frozen_dataclass_not_mutated(self) -> None:
        """Verify frozen dataclasses are not mutated."""
        original = ValidFrozenDataclass(
            field_int=42,
            field_bool=True,
            field_enum=SampleEnum.VALUE_A,
            field_hash="abc123",
        )
        original_hash = hash((
            original.field_int,
            original.field_bool,
            original.field_enum,
            original.field_hash,
        ))
        assert_non_expressive(original)
        new_hash = hash((
            original.field_int,
            original.field_bool,
            original.field_enum,
            original.field_hash,
        ))
        assert original_hash == new_hash

    def test_nested_structure_not_mutated(self) -> None:
        """Verify nested structures are not mutated."""
        original = (1, (2, (3, (4, 5))))
        copy_of_original = (1, (2, (3, (4, 5))))
        assert_non_expressive(original)
        assert original == copy_of_original


# =============================================================================
# GROUP 4: Runtime Guard - Determinism (100 runs)
# =============================================================================

class TestGCCDeterminism:
    """Tests proving determinism over 100+ runs."""

    def test_valid_value_determinism_100_runs(self) -> None:
        """Verify valid values pass consistently over 100 runs."""
        valid_value = (
            1,
            True,
            SampleEnum.VALUE_A,
            "abc123",
            frozenset({2, 3}),
        )
        for _ in range(100):
            # Should never raise
            assert_non_expressive(valid_value)

    def test_invalid_value_determinism_100_runs(self) -> None:
        """Verify invalid values fail consistently over 100 runs."""
        invalid_value = "This is clearly free-form text!"
        for _ in range(100):
            with pytest.raises(GCCViolationError):
                assert_non_expressive(invalid_value)

    def test_is_non_expressive_determinism_100_runs(self) -> None:
        """Verify is_non_expressive is deterministic."""
        test_cases = [
            (42, True),
            (True, True),
            (SampleEnum.VALUE_A, True),
            ("abc123", True),
            ("free form text", False),
            ([1, 2, 3], False),
            ({"key": "value"}, False),
        ]
        for value, expected in test_cases:
            for _ in range(100):
                result = is_non_expressive(value)
                assert result == expected, f"Non-deterministic for {value}"

    def test_error_path_determinism_100_runs(self) -> None:
        """Verify error paths are deterministic."""
        nested = (1, 2, (3, "invalid text"))
        for _ in range(100):
            with pytest.raises(GCCViolationError) as exc:
                assert_non_expressive(nested)
            assert exc.value.path == "[2][1]"

    def test_hash_stability_100_runs(self) -> None:
        """Verify hash-based validation is stable."""
        valid_hash = "deadbeef1234567890"
        for _ in range(100):
            assert is_non_expressive(valid_hash)


# =============================================================================
# GROUP 5: Ledger Invariant - Violations Rejected
# =============================================================================

class TestLedgerInvariantViolationsRejected:
    """Tests proving ledger invariant violations are rejected."""

    def test_forbidden_field_rejected(self) -> None:
        """Verify forbidden field names are rejected."""
        invalid_entry = InvalidLedgerEntry(
            entry_id="abc123def45678ab",
            explanation="This explains something",
        )
        with pytest.raises(LedgerInvariantViolation) as exc:
            assert_ledger_entry_valid(invalid_entry)
        assert exc.value.reason == LedgerInvariantViolation.REASON_FORBIDDEN_FIELD

    def test_free_text_value_rejected(self) -> None:
        """Verify free-form text values are rejected."""
        entry_dict = {
            "entry_id": "abc123def45678ab",
            "span_id": "This is not a valid span ID!",
        }
        with pytest.raises(LedgerInvariantViolation) as exc:
            validate_ledger_entry_dict(entry_dict)
        assert exc.value.reason == LedgerInvariantViolation.REASON_FREE_TEXT_VALUE

    def test_unknown_field_rejected(self) -> None:
        """Verify unknown fields are rejected."""
        entry_dict = {
            "entry_id": "abc123def45678ab",
            "custom_field": 42,
        }
        with pytest.raises(LedgerInvariantViolation) as exc:
            validate_ledger_entry_dict(entry_dict)
        assert exc.value.reason == LedgerInvariantViolation.REASON_INVALID_FIELD

    def test_mutable_value_rejected(self) -> None:
        """Verify mutable values are rejected."""
        entry_dict = {
            "entry_id": "abc123def45678ab",
            "projected_layers": ["layer1", "layer2"],  # list is mutable
        }
        with pytest.raises(LedgerInvariantViolation) as exc:
            validate_ledger_entry_dict(entry_dict)
        assert exc.value.reason == LedgerInvariantViolation.REASON_MUTABLE_VALUE

    def test_description_field_rejected(self) -> None:
        """Verify 'description' field is rejected."""
        entry_dict = {
            "entry_id": "abc123def45678ab",
            "description": "Some description",
        }
        with pytest.raises(LedgerInvariantViolation) as exc:
            validate_ledger_entry_dict(entry_dict)
        assert exc.value.reason == LedgerInvariantViolation.REASON_FORBIDDEN_FIELD

    def test_summary_field_rejected(self) -> None:
        """Verify 'summary' field is rejected."""
        entry_dict = {
            "entry_id": "abc123def45678ab",
            "summary": "Brief summary",
        }
        with pytest.raises(LedgerInvariantViolation) as exc:
            validate_ledger_entry_dict(entry_dict)
        assert exc.value.reason == LedgerInvariantViolation.REASON_FORBIDDEN_FIELD

    def test_reason_field_rejected(self) -> None:
        """Verify 'reason' field is rejected."""
        entry_dict = {
            "entry_id": "abc123def45678ab",
            "reason": "Because of this",
        }
        with pytest.raises(LedgerInvariantViolation) as exc:
            validate_ledger_entry_dict(entry_dict)
        assert exc.value.reason == LedgerInvariantViolation.REASON_FORBIDDEN_FIELD


# =============================================================================
# GROUP 6: Ledger Invariant - Valid Entries Accepted
# =============================================================================

class TestLedgerInvariantValidAccepted:
    """Tests proving valid ledger entries are accepted."""

    def test_valid_ledger_entry_accepted(self) -> None:
        """Verify valid ledger entry is accepted."""
        entry = LedgerEntryMock(
            entry_id="abc123def45678ab",
            prev_entry_id=None,
            span_id="1234567890abcdef",
            artifact_id="fedcba0987654321",
            artifact_hash="deadbeefcafe1234",
            phase_id="3",
            projected_layers=(SampleEnum.VALUE_A,),
            router_version="R1.0",
            mapping_version="M1.0",
            seq=0,
        )
        assert_ledger_entry_valid(entry)

    def test_valid_ledger_dict_accepted(self) -> None:
        """Verify valid ledger dict is accepted."""
        entry_dict = {
            "entry_id": "abc123def45678ab",
            "prev_entry_id": None,
            "span_id": "1234567890abcdef",
            "artifact_id": "fedcba0987654321",
            "artifact_hash": "deadbeefcafe1234",
            "phase_id": "5",
            # Use tuple of enums directly, not string names
            "projected_layers": (SampleEnum.VALUE_A, SampleEnum.VALUE_B),
            "router_version": "R1.0",
            "mapping_version": "M1.0",
            "seq": 42,
        }
        validate_ledger_entry_dict(entry_dict)

    def test_all_allowed_fields_accepted(self) -> None:
        """Verify all allowed fields are accepted."""
        for field in ALLOWED_LEDGER_FIELDS:
            # Create minimal valid entry with this field
            entry_dict = {field: "abc123" if field != "seq" else 0}
            # Should not raise for the field name itself
            # (may raise for missing required fields, but not for field name)
            try:
                validate_ledger_entry_dict(entry_dict)
            except LedgerInvariantViolation as e:
                assert e.reason != LedgerInvariantViolation.REASON_INVALID_FIELD


# =============================================================================
# GROUP 7: Ledger Invariant - Determinism
# =============================================================================

class TestLedgerDeterminism:
    """Tests proving ledger validation is deterministic."""

    def test_valid_entry_determinism_100_runs(self) -> None:
        """Verify valid entries pass consistently."""
        entry = LedgerEntryMock(
            entry_id="abc123def45678ab",
            prev_entry_id="1234567890abcdef",  # Must be valid 16-char hex
            span_id="1234567890abcdef",
            artifact_id="fedcba0987654321",
            artifact_hash="deadbeefcafe1234",
            phase_id="7",
            projected_layers=(SampleEnum.VALUE_B,),
            router_version="R1.0",
            mapping_version="M1.0",
            seq=99,
        )
        for _ in range(100):
            assert_ledger_entry_valid(entry)

    def test_invalid_entry_determinism_100_runs(self) -> None:
        """Verify invalid entries fail consistently."""
        entry = InvalidLedgerEntry(
            entry_id="abc123def45678ab",
            explanation="This is an explanation",
        )
        for _ in range(100):
            with pytest.raises(LedgerInvariantViolation):
                assert_ledger_entry_valid(entry)


# =============================================================================
# GROUP 8: GCC Decorator Tests
# =============================================================================

class TestGCCDecorator:
    """Tests for the @gcc_guarded decorator."""

    def test_decorator_passes_valid(self) -> None:
        """Verify decorator passes valid returns."""
        @gcc_guarded
        def return_valid():
            return (1, True, SampleEnum.VALUE_A)

        result = return_valid()
        assert result == (1, True, SampleEnum.VALUE_A)

    def test_decorator_rejects_invalid(self) -> None:
        """Verify decorator rejects invalid returns."""
        @gcc_guarded
        def return_invalid():
            return "This is free-form text!"

        with pytest.raises(GCCViolationError):
            return_invalid()

    def test_decorator_preserves_function_name(self) -> None:
        """Verify decorator preserves function metadata."""
        @gcc_guarded
        def my_function():
            """Docstring here."""
            return 42

        assert my_function.__name__ == "my_function"


# =============================================================================
# GROUP 9: Static Scanner - Allowlist
# =============================================================================

class TestStaticScannerAllowlist:
    """Tests for static scanner allowlist."""

    def test_default_allowlist_allows_hex(self) -> None:
        """Verify default allowlist allows hex strings."""
        allowlist = Allowlist.default()
        assert allowlist.is_allowed("abc123def")
        assert allowlist.is_allowed("DEADBEEF")
        assert allowlist.is_allowed("0" * 64)

    def test_default_allowlist_allows_invariant_keys(self) -> None:
        """Verify default allowlist allows invariant keys."""
        allowlist = Allowlist.default()
        assert allowlist.is_allowed("INVALID_ARTIFACT_ID")
        assert allowlist.is_allowed("PHASE_NOT_IN_MAPPING")

    def test_default_allowlist_allows_versions(self) -> None:
        """Verify default allowlist allows version strings."""
        allowlist = Allowlist.default()
        assert allowlist.is_allowed("R1.0")
        assert allowlist.is_allowed("M1.0")
        assert allowlist.is_allowed("V2.5")

    def test_default_allowlist_rejects_free_text(self) -> None:
        """Verify default allowlist rejects free-form text."""
        allowlist = Allowlist.default()
        assert not allowlist.is_allowed("This is free text")
        assert not allowlist.is_allowed("Some explanation here")


# =============================================================================
# GROUP 10: Integration - Existing Valid Paths
# =============================================================================

class TestExistingValidPaths:
    """Tests proving existing valid code paths work unchanged."""

    def test_router_response_types_valid(self) -> None:
        """Verify router response types are GCC-compliant."""
        # Simulated router response structure
        from symbolu.ontology.router.ontological_router_r1 import (
            OntologicalLayer,
            ProjectionResponse,
        )

        response = ProjectionResponse(
            artifact_id="abc123def456",
            artifact_hash="deadbeef12345678",
            phase_id="5",
            projected_layers=(OntologicalLayer.COGNITION,),
            router_version="R1.0",
        )
        # All fields should be non-expressive
        assert_non_expressive(response.artifact_id)
        assert_non_expressive(response.artifact_hash)
        assert_non_expressive(response.phase_id)
        assert_non_expressive(response.projected_layers)
        assert_non_expressive(response.router_version)

    def test_ledger_entry_types_valid(self) -> None:
        """Verify ledger entry types are GCC-compliant."""
        from symbolu.ledger.ledger_replay_verifier import (
            LedgerEntry,
            OntologicalLayer,
        )

        entry = LedgerEntry(
            entry_id="abc123def45678ab",
            prev_entry_id=None,
            span_id="1234567890abcdef",
            artifact_id="fedcba0987654321",
            artifact_hash="deadbeefcafe1234",
            phase_id="3",
            projected_layers=(OntologicalLayer.STRUCTURE,),
            router_version="R1.0",
            mapping_version="M1.0",
            seq=0,
        )
        # All fields should be non-expressive
        assert_non_expressive(entry.entry_id)
        assert_non_expressive(entry.prev_entry_id)
        assert_non_expressive(entry.span_id)
        assert_non_expressive(entry.artifact_id)
        assert_non_expressive(entry.artifact_hash)
        assert_non_expressive(entry.phase_id)
        assert_non_expressive(entry.projected_layers)
        assert_non_expressive(entry.router_version)
        assert_non_expressive(entry.mapping_version)
        assert_non_expressive(entry.seq)


# =============================================================================
# GROUP 11: GCC Invariants Verification
# =============================================================================

class TestGCCInvariants:
    """Tests verifying GCC invariants are correctly defined."""

    def test_gcc_invariants_all_true(self) -> None:
        """Verify all GCC invariants are True."""
        for invariant, value in GCC_INVARIANTS.items():
            assert value is True, f"Invariant {invariant} is not True"

    def test_gcc_invariants_complete(self) -> None:
        """Verify all required invariants are present."""
        required = {
            "NON_EXPRESSIVE",
            "FAIL_CLOSED",
            "NO_FREE_TEXT",
            "NO_SEMANTICS",
            "NO_GENERATION",
            "DETERMINISTIC",
            "AUDITABLE",
        }
        actual = set(GCC_INVARIANTS.keys())
        assert required <= actual

    def test_allowed_ledger_fields_complete(self) -> None:
        """Verify all required ledger fields are allowed."""
        required = {
            "entry_id",
            "prev_entry_id",
            "span_id",
            "artifact_id",
            "artifact_hash",
            "phase_id",
            "projected_layers",
            "router_version",
            "mapping_version",
            "seq",
        }
        assert required <= ALLOWED_LEDGER_FIELDS


# =============================================================================
# GROUP 12: Stress Tests
# =============================================================================

class TestGCCStress:
    """Stress tests for GCC enforcement."""

    def test_deep_nesting_valid(self) -> None:
        """Verify deeply nested valid structures pass."""
        # Create deeply nested tuple
        value: Any = 42
        for _ in range(100):
            value = (value,)
        assert_non_expressive(value)

    def test_deep_nesting_invalid_detected(self) -> None:
        """Verify deeply nested invalid values are detected."""
        # Create deeply nested tuple with invalid at bottom
        value: Any = "invalid free text"
        for _ in range(50):
            value = (value,)
        with pytest.raises(GCCViolationError):
            assert_non_expressive(value)

    def test_large_tuple_valid(self) -> None:
        """Verify large valid tuples pass."""
        large_tuple = tuple(range(10000))
        assert_non_expressive(large_tuple)

    def test_large_frozenset_valid(self) -> None:
        """Verify large valid frozensets pass."""
        large_frozenset = frozenset(range(10000))
        assert_non_expressive(large_frozenset)

    def test_many_enum_values(self) -> None:
        """Verify many enum values pass."""
        enums = tuple(SampleEnum.VALUE_A for _ in range(1000))
        assert_non_expressive(enums)
