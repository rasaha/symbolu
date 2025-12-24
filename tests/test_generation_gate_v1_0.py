"""
GenerationGate v1.0 Tests
==========================

Comprehensive test suite for GenerationGate v1.0 binary boundary.

Test Coverage:
- One-time seal enforcement
- Mode queries and status
- Generation assertions (enabled/disabled)
- Renderer entry gating
- Deterministic denial (100 runs)
- Forbidden imports detection
- Immutability verification
- Ledger attestation

Author: Symbolu Core Team
Version: 1.0.0
"""

import pytest
import sys
from typing import Any


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def reset_gate():
    """
    Reset the GenerationGate singleton before each test.

    Uses internal _reset() method for testing purposes only.
    """
    from symbolu.core.generation_gate import GenerationGate
    GenerationGate._reset()
    yield
    GenerationGate._reset()


# ============================================================================
# Test: Seal Once (Second Call Fails)
# ============================================================================

def test_seal_once_second_call_fails():
    """
    Test that sealing the gate once works, but a second seal call raises.
    """
    from symbolu.core.generation_gate import (
        GenerationGate,
        GenerationMode,
        GateViolation,
        ErrorCode
    )

    # First seal should succeed
    GenerationGate.seal(GenerationMode.ENABLED)

    # Second seal should fail
    with pytest.raises(GateViolation) as exc_info:
        GenerationGate.seal(GenerationMode.DISABLED)

    assert exc_info.value.code == ErrorCode.GATE_ALREADY_SEALED


def test_seal_with_disabled_mode():
    """
    Test sealing with DISABLED mode.
    """
    from symbolu.core.generation_gate import (
        GenerationGate,
        GenerationMode,
        GateStatus
    )

    GenerationGate.seal(GenerationMode.DISABLED)

    assert GenerationGate.mode() == GenerationMode.DISABLED
    assert GenerationGate.gate_status() == GateStatus.SEALED_DISABLED


def test_seal_with_enabled_mode():
    """
    Test sealing with ENABLED mode.
    """
    from symbolu.core.generation_gate import (
        GenerationGate,
        GenerationMode,
        GateStatus
    )

    GenerationGate.seal(GenerationMode.ENABLED)

    assert GenerationGate.mode() == GenerationMode.ENABLED
    assert GenerationGate.gate_status() == GateStatus.SEALED_ENABLED


def test_seal_with_invalid_mode():
    """
    Test that sealing with invalid mode raises GateViolation.
    """
    from symbolu.core.generation_gate import (
        GenerationGate,
        GateViolation,
        ErrorCode
    )

    with pytest.raises(GateViolation) as exc_info:
        GenerationGate.seal("INVALID")  # type: ignore

    assert exc_info.value.code == ErrorCode.INVALID_MODE


# ============================================================================
# Test: Unsealed State
# ============================================================================

def test_unsealed_mode_query_fails():
    """
    Test that querying mode before sealing raises GateViolation.
    """
    from symbolu.core.generation_gate import (
        GenerationGate,
        GateViolation,
        ErrorCode
    )

    with pytest.raises(GateViolation) as exc_info:
        GenerationGate.mode()

    assert exc_info.value.code == ErrorCode.GATE_UNSEALED


def test_unsealed_gate_status():
    """
    Test that unsealed gate has UNSEALED status.
    """
    from symbolu.core.generation_gate import (
        GenerationGate,
        GateStatus
    )

    assert GenerationGate.gate_status() == GateStatus.UNSEALED


def test_unsealed_assert_generation_fails():
    """
    Test that assert_generation_enabled fails when unsealed.
    """
    from symbolu.core.generation_gate import (
        GenerationGate,
        GateViolation,
        ErrorCode
    )

    with pytest.raises(GateViolation) as exc_info:
        GenerationGate.assert_generation_enabled()

    assert exc_info.value.code == ErrorCode.GATE_UNSEALED


# ============================================================================
# Test: Disabled Mode - Assert Fails
# ============================================================================

def test_disabled_mode_assert_generation_fails():
    """
    Test that assert_generation_enabled fails when mode is DISABLED.
    """
    from symbolu.core.generation_gate import (
        GenerationGate,
        GenerationMode,
        GateViolation,
        ErrorCode
    )

    GenerationGate.seal(GenerationMode.DISABLED)

    with pytest.raises(GateViolation) as exc_info:
        GenerationGate.assert_generation_enabled()

    assert exc_info.value.code == ErrorCode.GENERATION_DISABLED


# ============================================================================
# Test: Enabled Mode - Assert Succeeds
# ============================================================================

def test_enabled_mode_assert_generation_succeeds():
    """
    Test that assert_generation_enabled succeeds when mode is ENABLED.
    """
    from symbolu.core.generation_gate import (
        GenerationGate,
        GenerationMode
    )

    GenerationGate.seal(GenerationMode.ENABLED)

    # Should not raise
    GenerationGate.assert_generation_enabled()


# ============================================================================
# Test: Renderer Entry - Disabled Mode (Deterministic 100 Runs)
# ============================================================================

def test_renderer_entry_disabled_deterministic_100_runs():
    """
    Test that renderer entry denies deterministically with DISABLED mode.

    Runs 100 iterations to verify determinism (no randomness).
    """
    from symbolu.core.generation_gate import GenerationGate, GenerationMode
    from symbolu.renderer.render_entry import render_phase11, RenderOutcome

    GenerationGate.seal(GenerationMode.DISABLED)

    results = []
    for _ in range(100):
        result = render_phase11()
        results.append(result.outcome)

    # All outcomes should be identical (deterministic)
    assert all(outcome == RenderOutcome.GATE_BLOCKED for outcome in results)
    assert len(set(results)) == 1  # Only one unique outcome


# ============================================================================
# Test: Renderer Entry - Enabled Mode
# ============================================================================

def test_renderer_entry_enabled_gate_passes():
    """
    Test that renderer entry passes gate when ENABLED.

    Note: Placeholder renderer returns RENDER_BLOCKED (not implemented).
    """
    from symbolu.core.generation_gate import GenerationGate, GenerationMode
    from symbolu.renderer.render_entry import render_phase11, RenderOutcome

    GenerationGate.seal(GenerationMode.ENABLED)

    result = render_phase11()

    # Gate passes, but Phase-11 not implemented -> RENDER_BLOCKED
    assert result.outcome == RenderOutcome.RENDER_BLOCKED
    assert result.data is not None
    assert result.data["gate_passed"] is True


def test_renderer_entry_disabled_gate_blocks():
    """
    Test that renderer entry blocks when DISABLED.
    """
    from symbolu.core.generation_gate import (
        GenerationGate,
        GenerationMode,
        ErrorCode
    )
    from symbolu.renderer.render_entry import render_phase11, RenderOutcome

    GenerationGate.seal(GenerationMode.DISABLED)

    result = render_phase11()

    # Gate blocks
    assert result.outcome == RenderOutcome.GATE_BLOCKED
    assert result.data is not None
    assert result.data["error_code"] == ErrorCode.GENERATION_DISABLED


# ============================================================================
# Test: Forbidden Imports
# ============================================================================

def test_forbidden_imports_not_present():
    """
    Test that forbidden imports (random, time, datetime, uuid) are NOT
    imported by generation_gate module.

    This ensures deterministic operation.
    """
    # Import the module
    import symbolu.core.generation_gate

    # Get the module's imported modules
    module_file = symbolu.core.generation_gate.__file__
    assert module_file is not None

    # Read the source code
    with open(module_file, 'r') as f:
        source = f.read()

    # Check that forbidden imports are not present
    forbidden = ['random', 'time', 'datetime', 'uuid']
    for lib in forbidden:
        assert f'import {lib}' not in source, f"Forbidden import: {lib}"
        assert f'from {lib}' not in source, f"Forbidden import: from {lib}"


def test_forbidden_imports_not_in_renderer_entry():
    """
    Test that forbidden imports are not in render_entry module.
    """
    import symbolu.renderer.render_entry

    module_file = symbolu.renderer.render_entry.__file__
    assert module_file is not None

    with open(module_file, 'r') as f:
        source = f.read()

    forbidden = ['random', 'time', 'datetime', 'uuid']
    for lib in forbidden:
        assert f'import {lib}' not in source, f"Forbidden import: {lib}"
        assert f'from {lib}' not in source, f"Forbidden import: from {lib}"


def test_forbidden_imports_not_in_ledger_attest():
    """
    Test that forbidden imports are not in ledger_generation_attest module.
    """
    import symbolu.core.ledger_generation_attest

    module_file = symbolu.core.ledger_generation_attest.__file__
    assert module_file is not None

    with open(module_file, 'r') as f:
        source = f.read()

    forbidden = ['random', 'time', 'datetime', 'uuid']
    for lib in forbidden:
        assert f'import {lib}' not in source, f"Forbidden import: {lib}"
        assert f'from {lib}' not in source, f"Forbidden import: from {lib}"


# ============================================================================
# Test: Immutability
# ============================================================================

def test_gate_violation_is_frozen():
    """
    Test that GateViolation dataclass is frozen (immutable).
    """
    from symbolu.core.generation_gate import GateViolation, ErrorCode

    violation = GateViolation(code=ErrorCode.GATE_UNSEALED)

    # Attempt to modify should fail
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        violation.code = "MODIFIED"  # type: ignore


def test_render_result_is_frozen():
    """
    Test that RenderResult dataclass is frozen (immutable).
    """
    from symbolu.renderer.render_entry import RenderResult, RenderOutcome

    result = RenderResult(
        outcome=RenderOutcome.GATE_BLOCKED,
        message="test"
    )

    # Attempt to modify should fail
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        result.outcome = "MODIFIED"  # type: ignore


def test_render_result_data_is_immutable():
    """
    Test that RenderResult data dict is treated as immutable.
    """
    from symbolu.renderer.render_entry import RenderResult, RenderOutcome

    result = RenderResult(
        outcome=RenderOutcome.GATE_BLOCKED,
        message="test",
        data={"key": "value"}
    )

    # Data should be a regular dict (frozen in __post_init__)
    assert result.data is not None
    assert isinstance(result.data, dict)

    # The data is sorted for hash stability
    assert list(result.data.keys()) == sorted(result.data.keys())


# ============================================================================
# Test: Ledger Attestation
# ============================================================================

def test_ledger_attestation_disabled():
    """
    Test ledger attestation when gate is DISABLED.
    """
    from symbolu.core.generation_gate import GenerationGate, GenerationMode
    from symbolu.core.ledger_generation_attest import attest_generation_attempt

    GenerationGate.seal(GenerationMode.DISABLED)

    blob = attest_generation_attempt(
        render_attempted=True,
        render_outcome="GATE_BLOCKED"
    )

    assert blob["generation_mode"] == "DISABLED"
    assert blob["gate_status"] == "SEALED_DISABLED"
    assert blob["render_attempted"] is True
    assert blob["render_outcome"] == "GATE_BLOCKED"


def test_ledger_attestation_enabled():
    """
    Test ledger attestation when gate is ENABLED.
    """
    from symbolu.core.generation_gate import GenerationGate, GenerationMode
    from symbolu.core.ledger_generation_attest import attest_generation_attempt

    GenerationGate.seal(GenerationMode.ENABLED)

    blob = attest_generation_attempt(
        render_attempted=True,
        render_outcome="RENDER_SUCCESS"
    )

    assert blob["generation_mode"] == "ENABLED"
    assert blob["gate_status"] == "SEALED_ENABLED"
    assert blob["render_attempted"] is True
    assert blob["render_outcome"] == "RENDER_SUCCESS"


def test_ledger_attestation_unsealed():
    """
    Test ledger attestation when gate is UNSEALED.
    """
    from symbolu.core.ledger_generation_attest import attest_generation_attempt

    blob = attest_generation_attempt(
        render_attempted=False,
        render_outcome=None
    )

    assert blob["generation_mode"] == "UNSEALED"
    assert blob["gate_status"] == "UNSEALED"
    assert blob["render_attempted"] is False
    assert blob["render_outcome"] == "NONE"


def test_ledger_attestation_is_immutable():
    """
    Test that ledger attestation blob is immutable.
    """
    from symbolu.core.generation_gate import GenerationGate, GenerationMode
    from symbolu.core.ledger_generation_attest import attest_generation_attempt
    from types import MappingProxyType

    GenerationGate.seal(GenerationMode.ENABLED)

    blob = attest_generation_attempt(
        render_attempted=True,
        render_outcome="TEST"
    )

    # Should be a MappingProxyType (immutable)
    assert isinstance(blob, MappingProxyType)

    # Attempt to modify should fail
    with pytest.raises(TypeError):
        blob["generation_mode"] = "MODIFIED"  # type: ignore


def test_ledger_attestation_hash_stability():
    """
    Test that ledger attestation has hash-stable key ordering.
    """
    from symbolu.core.generation_gate import GenerationGate, GenerationMode
    from symbolu.core.ledger_generation_attest import attest_generation_attempt

    GenerationGate.seal(GenerationMode.ENABLED)

    blob = attest_generation_attempt(
        render_attempted=True,
        render_outcome="TEST"
    )

    # Keys should be in sorted order
    keys = list(blob.keys())
    assert keys == sorted(keys)


# ============================================================================
# Test: Guard Function
# ============================================================================

def test_guard_generation_gate_enabled():
    """
    Test that guard function succeeds when gate is enabled.
    """
    from symbolu.core.generation_gate import GenerationGate, GenerationMode
    from symbolu.renderer.render_entry import guard_generation_gate

    GenerationGate.seal(GenerationMode.ENABLED)

    # Should not raise
    guard_generation_gate()


def test_guard_generation_gate_disabled():
    """
    Test that guard function raises when gate is disabled.
    """
    from symbolu.core.generation_gate import (
        GenerationGate,
        GenerationMode,
        GateViolation
    )
    from symbolu.renderer.render_entry import guard_generation_gate

    GenerationGate.seal(GenerationMode.DISABLED)

    with pytest.raises(GateViolation):
        guard_generation_gate()


def test_guard_generation_gate_unsealed():
    """
    Test that guard function raises when gate is unsealed.
    """
    from symbolu.core.generation_gate import GateViolation
    from symbolu.renderer.render_entry import guard_generation_gate

    with pytest.raises(GateViolation):
        guard_generation_gate()


# ============================================================================
# Test: GateViolation String Representation
# ============================================================================

def test_gate_violation_str_with_context():
    """
    Test GateViolation string representation with context.
    """
    from symbolu.core.generation_gate import GateViolation

    violation = GateViolation(code="TEST_CODE", context="test context")
    assert str(violation) == "GateViolation[TEST_CODE]: test context"


def test_gate_violation_str_without_context():
    """
    Test GateViolation string representation without context.
    """
    from symbolu.core.generation_gate import GateViolation

    violation = GateViolation(code="TEST_CODE")
    assert str(violation) == "GateViolation[TEST_CODE]"


# ============================================================================
# Test: Determinism Verification
# ============================================================================

def test_gate_operations_are_deterministic():
    """
    Test that all gate operations produce deterministic results.

    Run multiple iterations and verify identical outcomes.
    """
    from symbolu.core.generation_gate import GenerationGate, GenerationMode

    results = []
    for i in range(50):
        # Reset gate
        GenerationGate._reset()

        # Seal and query
        GenerationGate.seal(GenerationMode.ENABLED)
        status = GenerationGate.gate_status()
        mode = GenerationGate.mode()

        results.append((status.value, mode.value))

        # Reset for next iteration
        GenerationGate._reset()

    # All results should be identical
    assert len(set(results)) == 1
    assert results[0] == ("SEALED_ENABLED", "ENABLED")


# ============================================================================
# Test: Integration - Full Flow
# ============================================================================

def test_full_integration_disabled_flow():
    """
    Test full integration flow with DISABLED mode.
    """
    from symbolu.core.generation_gate import GenerationGate, GenerationMode
    from symbolu.renderer.render_entry import render_phase11, RenderOutcome
    from symbolu.core.ledger_generation_attest import attest_generation_attempt

    # Seal gate as DISABLED
    GenerationGate.seal(GenerationMode.DISABLED)

    # Attempt render
    result = render_phase11()

    # Create attestation
    attestation = attest_generation_attempt(
        render_attempted=True,
        render_outcome=result.outcome
    )

    # Verify flow
    assert result.outcome == RenderOutcome.GATE_BLOCKED
    assert attestation["generation_mode"] == "DISABLED"
    assert attestation["gate_status"] == "SEALED_DISABLED"
    assert attestation["render_outcome"] == RenderOutcome.GATE_BLOCKED


def test_full_integration_enabled_flow():
    """
    Test full integration flow with ENABLED mode.
    """
    from symbolu.core.generation_gate import GenerationGate, GenerationMode
    from symbolu.renderer.render_entry import render_phase11, RenderOutcome
    from symbolu.core.ledger_generation_attest import attest_generation_attempt

    # Seal gate as ENABLED
    GenerationGate.seal(GenerationMode.ENABLED)

    # Attempt render
    result = render_phase11()

    # Create attestation
    attestation = attest_generation_attempt(
        render_attempted=True,
        render_outcome=result.outcome
    )

    # Verify flow
    assert result.outcome == RenderOutcome.RENDER_BLOCKED  # Not implemented
    assert attestation["generation_mode"] == "ENABLED"
    assert attestation["gate_status"] == "SEALED_ENABLED"
    assert attestation["render_outcome"] == RenderOutcome.RENDER_BLOCKED
