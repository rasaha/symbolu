"""
P30 Output Verification Phase Unit Tests
==========================================

Comprehensive tests for P30 Output Verification phase:
- P30Authority enum
- VerificationStatus enum
- ViolationSeverity enum
- P30Violation dataclass
- P30ComplianceResult dataclass
- P30CoherenceResult dataclass
- P30Output dataclass
- Integration functions
- Determinism verification
"""

import pytest
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from symbolu.mechanical.pipeline.p30_verification import (
    VERSION,
    P30Authority,
    VerificationStatus,
    ViolationSeverity,
    P30Violation,
    P30ComplianceResult,
    P30CoherenceResult,
    P30Output,
    maybe_run_p30,
    get_p30_output,
    get_p30_verified_text,
    is_p30_passed,
    run_p30_verification,
)


# =============================================================================
# MOCK CONTEXT FIXTURES
# =============================================================================


@dataclass
class MockP29Output:
    """Mock P29 output for testing."""
    final_text: str = "Test text from P29"


@dataclass
class MockP28Output:
    """Mock P28 output for testing."""
    guarded_text: str = "Test text from P28"


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""
    p29_expression: Optional[MockP29Output] = None
    p28_dha: Optional[MockP28Output] = None
    p30_verification: Optional[Any] = None
    p13_envelope: Optional[Any] = None
    acoustic_regime: Optional[Any] = None
    discourse_act: Optional[Any] = None
    coherence_state: Optional[Any] = None


# =============================================================================
# ENUM TESTS
# =============================================================================


class TestP30AuthorityEnum:
    """Tests for P30Authority enum."""

    def test_all_authorities_exist(self):
        """Test: all authority levels exist."""
        assert P30Authority.HIGH.value == "high"
        assert P30Authority.MEDIUM.value == "medium"
        assert P30Authority.LOW.value == "low"
        assert len(list(P30Authority)) == 3


class TestVerificationStatusEnum:
    """Tests for VerificationStatus enum."""

    def test_passed_value(self):
        """Test: PASSED exists."""
        assert VerificationStatus.PASSED.value == "passed"

    def test_passed_with_warnings_value(self):
        """Test: PASSED_WITH_WARNINGS exists."""
        assert VerificationStatus.PASSED_WITH_WARNINGS.value == "passed_with_warnings"

    def test_failed_value(self):
        """Test: FAILED exists."""
        assert VerificationStatus.FAILED.value == "failed"

    def test_skipped_value(self):
        """Test: SKIPPED exists."""
        assert VerificationStatus.SKIPPED.value == "skipped"

    def test_all_statuses_exist(self):
        """Test: all four statuses exist."""
        assert len(list(VerificationStatus)) == 4


class TestViolationSeverityEnum:
    """Tests for ViolationSeverity enum."""

    def test_all_severities_exist(self):
        """Test: all severity levels exist."""
        assert ViolationSeverity.CRITICAL.value == "critical"
        assert ViolationSeverity.WARNING.value == "warning"
        assert ViolationSeverity.INFO.value == "info"
        assert len(list(ViolationSeverity)) == 3


# =============================================================================
# P30 VIOLATION TESTS
# =============================================================================


class TestP30Violation:
    """Tests for P30Violation dataclass."""

    def test_basic_construction(self):
        """Test: basic construction with required fields."""
        violation = P30Violation(
            code="TEST_001",
            message="Test violation message",
            severity=ViolationSeverity.WARNING,
            source="TestChecker",
        )
        assert violation.code == "TEST_001"
        assert violation.severity == ViolationSeverity.WARNING
        assert violation.source == "TestChecker"

    def test_construction_with_details(self):
        """Test: construction with details."""
        violation = P30Violation(
            code="P13_SAFETY",
            message="Safety violation",
            severity=ViolationSeverity.CRITICAL,
            source="RendererComplianceChecker",
            details={"category": "safety"},
        )
        assert violation.details["category"] == "safety"

    def test_to_dict(self):
        """Test: to_dict serialization."""
        violation = P30Violation(
            code="TEST_002",
            message="Test message",
            severity=ViolationSeverity.CRITICAL,
            source="TestSource",
            details={"key": "value"},
        )
        result = violation.to_dict()

        assert result["code"] == "TEST_002"
        assert result["severity"] == "critical"
        assert result["details"]["key"] == "value"


# =============================================================================
# P30 COMPLIANCE RESULT TESTS
# =============================================================================


class TestP30ComplianceResult:
    """Tests for P30ComplianceResult dataclass."""

    def test_default_construction(self):
        """Test: construction with defaults (passed)."""
        result = P30ComplianceResult()
        assert result.passed is True
        assert result.violations == []
        assert result.p13_compliant is True
        assert result.p12_consistent is True

    def test_failed_construction(self):
        """Test: construction with violations (failed)."""
        violations = [
            P30Violation(
                code="P13_SAFETY",
                message="Safety issue",
                severity=ViolationSeverity.CRITICAL,
                source="Test",
            )
        ]
        result = P30ComplianceResult(
            passed=False,
            violations=violations,
            p13_compliant=False,
        )
        assert result.passed is False
        assert len(result.violations) == 1

    def test_to_dict(self):
        """Test: to_dict serialization."""
        violations = [
            P30Violation(
                code="TEST",
                message="Test",
                severity=ViolationSeverity.WARNING,
                source="Test",
            )
        ]
        result = P30ComplianceResult(
            passed=True,
            violations=violations,
        )
        d = result.to_dict()

        assert d["passed"] is True
        assert d["violation_count"] == 1
        assert len(d["violations"]) == 1


# =============================================================================
# P30 COHERENCE RESULT TESTS
# =============================================================================


class TestP30CoherenceResult:
    """Tests for P30CoherenceResult dataclass."""

    def test_default_construction(self):
        """Test: construction with defaults."""
        result = P30CoherenceResult()
        assert result.coherence_score == 1.0
        assert result.semantic_stability == 1.0
        assert result.persona_consistent is True
        assert result.temporal_arc_score == 1.0

    def test_custom_construction(self):
        """Test: construction with custom values."""
        result = P30CoherenceResult(
            coherence_score=0.85,
            semantic_stability=0.9,
            persona_consistent=True,
            temporal_arc_score=0.8,
        )
        assert result.coherence_score == 0.85
        assert result.temporal_arc_score == 0.8

    def test_to_dict(self):
        """Test: to_dict serialization."""
        result = P30CoherenceResult(
            coherence_score=0.75,
            persona_consistent=False,
        )
        d = result.to_dict()

        assert d["coherence_score"] == 0.75
        assert d["persona_consistent"] is False


# =============================================================================
# P30 OUTPUT TESTS
# =============================================================================


class TestP30Output:
    """Tests for P30Output dataclass."""

    def test_basic_construction(self):
        """Test: basic construction with required fields."""
        output = P30Output(
            verified_text="Verified text",
        )
        assert output.verified_text == "Verified text"
        assert output.verification_status == VerificationStatus.PASSED  # default
        assert output.authority == P30Authority.MEDIUM  # default

    def test_failed_construction(self):
        """Test: construction with FAILED status."""
        output = P30Output(
            verified_text="",
            verification_status=VerificationStatus.FAILED,
            authority=P30Authority.HIGH,
        )
        assert output.verified_text == ""
        assert output.verification_status == VerificationStatus.FAILED
        assert output.authority == P30Authority.HIGH

    def test_full_construction(self):
        """Test: construction with all fields."""
        compliance = P30ComplianceResult(passed=True)
        coherence = P30CoherenceResult(coherence_score=0.9)

        output = P30Output(
            verified_text="Text",
            verification_status=VerificationStatus.PASSED,
            authority=P30Authority.MEDIUM,
            compliance_result=compliance,
            coherence_result=coherence,
            checks_performed=["P13_compliance", "P12_consistency"],
            processing_trace=["Check 1", "Check 2"],
        )
        assert output.compliance_result is not None
        assert output.coherence_result is not None
        assert len(output.checks_performed) == 2

    def test_to_dict(self):
        """Test: to_dict serialization."""
        output = P30Output(
            verified_text="Test output",
            verification_status=VerificationStatus.PASSED_WITH_WARNINGS,
            checks_performed=["test_check"],
        )
        result = output.to_dict()

        assert result["phase"] == "P30"
        assert result["version"] == VERSION
        assert result["verified_text"] == "Test output"
        assert result["verification_status"] == "passed_with_warnings"


# =============================================================================
# INTEGRATION FUNCTION TESTS
# =============================================================================


class TestRunP30Verification:
    """Tests for run_p30_verification function."""

    def test_verification_returns_output(self):
        """Test: verification returns P30Output."""
        ctx = MockPipelineContext()
        output = run_p30_verification("Test text", ctx)

        assert output is not None
        assert isinstance(output, P30Output)
        assert output.verified_text == "Test text"

    def test_processing_trace_populated(self):
        """Test: processing trace is populated."""
        ctx = MockPipelineContext()
        output = run_p30_verification("Test text", ctx)

        assert len(output.processing_trace) > 0
        assert any("compliance" in t.lower() for t in output.processing_trace)

    def test_compliance_result_included(self):
        """Test: compliance result is included."""
        ctx = MockPipelineContext()
        output = run_p30_verification("Test text", ctx)

        assert output.compliance_result is not None
        assert output.compliance_result.passed is True

    def test_coherence_result_included(self):
        """Test: coherence result is included."""
        ctx = MockPipelineContext()
        output = run_p30_verification("Test text", ctx)

        assert output.coherence_result is not None


class TestMaybeRunP30:
    """Tests for maybe_run_p30 function."""

    def test_maybe_run_from_p29(self):
        """Test: maybe_run_p30 uses P29 text."""
        ctx = MockPipelineContext(
            p29_expression=MockP29Output(final_text="P29 text"),
        )
        output = maybe_run_p30(ctx)

        assert output is not None
        assert output.verified_text == "P29 text"

    def test_maybe_run_fallback_to_p28(self):
        """Test: maybe_run_p30 falls back to P28."""
        ctx = MockPipelineContext(
            p28_dha=MockP28Output(guarded_text="P28 fallback"),
        )
        output = maybe_run_p30(ctx)

        assert output is not None
        assert output.verified_text == "P28 fallback"

    def test_maybe_run_returns_none_without_input(self):
        """Test: maybe_run_p30 returns None without input."""
        ctx = MockPipelineContext()
        output = maybe_run_p30(ctx)

        assert output is None


class TestGetP30Output:
    """Tests for get_p30_output function."""

    def test_get_output_when_present(self):
        """Test: get_p30_output returns output when present."""
        expected = P30Output(verified_text="Verified")
        ctx = MockPipelineContext(p30_verification=expected)

        result = get_p30_output(ctx)
        assert result is expected

    def test_get_output_when_absent(self):
        """Test: get_p30_output returns None when absent."""
        ctx = MockPipelineContext()
        result = get_p30_output(ctx)
        assert result is None


class TestGetP30VerifiedText:
    """Tests for get_p30_verified_text function."""

    def test_get_verified_text_when_present(self):
        """Test: get_p30_verified_text returns text when present."""
        output = P30Output(verified_text="Verified text")
        ctx = MockPipelineContext(p30_verification=output)

        result = get_p30_verified_text(ctx)
        assert result == "Verified text"

    def test_get_verified_text_empty_when_failed(self):
        """Test: get_p30_verified_text returns empty on failure."""
        output = P30Output(
            verified_text="",
            verification_status=VerificationStatus.FAILED,
        )
        ctx = MockPipelineContext(p30_verification=output)

        result = get_p30_verified_text(ctx)
        assert result == ""

    def test_get_verified_text_empty_when_absent(self):
        """Test: get_p30_verified_text returns empty when absent."""
        ctx = MockPipelineContext()
        result = get_p30_verified_text(ctx)
        assert result == ""


class TestIsP30Passed:
    """Tests for is_p30_passed function."""

    def test_passed_returns_true(self):
        """Test: is_p30_passed returns True for PASSED."""
        output = P30Output(
            verified_text="Text",
            verification_status=VerificationStatus.PASSED,
        )
        ctx = MockPipelineContext(p30_verification=output)

        assert is_p30_passed(ctx) is True

    def test_passed_with_warnings_returns_true(self):
        """Test: is_p30_passed returns True for PASSED_WITH_WARNINGS."""
        output = P30Output(
            verified_text="Text",
            verification_status=VerificationStatus.PASSED_WITH_WARNINGS,
        )
        ctx = MockPipelineContext(p30_verification=output)

        assert is_p30_passed(ctx) is True

    def test_failed_returns_false(self):
        """Test: is_p30_passed returns False for FAILED."""
        output = P30Output(
            verified_text="",
            verification_status=VerificationStatus.FAILED,
        )
        ctx = MockPipelineContext(p30_verification=output)

        assert is_p30_passed(ctx) is False

    def test_default_true_when_absent(self):
        """Test: is_p30_passed returns True when not run."""
        ctx = MockPipelineContext()
        assert is_p30_passed(ctx) is True


# =============================================================================
# DETERMINISM TESTS
# =============================================================================


class TestDeterminism:
    """Tests verifying deterministic behavior."""

    def test_same_input_same_output(self):
        """Test: same text produces same output."""
        ctx = MockPipelineContext()

        results = []
        for _ in range(10):
            output = run_p30_verification("Test text", ctx)
            results.append(output.verification_status)

        assert all(r == results[0] for r in results)


# =============================================================================
# ARCHITECTURAL PHASE TESTS
# =============================================================================


class TestArchitecturalPhase:
    """Tests verifying architectural phase identification."""

    def test_output_identifies_as_p30(self):
        """Test: output correctly identifies as P30."""
        output = P30Output(verified_text="Text")

        result = output.to_dict()
        assert result["phase"] == "P30"

    def test_failed_verification_has_high_authority(self):
        """Test: FAILED verification has HIGH authority."""
        # When output is blocked, authority should be HIGH
        output = P30Output(
            verified_text="",
            verification_status=VerificationStatus.FAILED,
            authority=P30Authority.HIGH,
        )
        assert output.authority == P30Authority.HIGH


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
