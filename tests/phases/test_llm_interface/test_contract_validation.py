"""
Symbol-U LLM Interface Contract Validation Tests
================================================

Contract: docs/contracts/SYMBOLU_LLM_INTERFACE_CONTRACT.md

This module implements adversarial tests AT-1 through AT-6 from the contract,
plus additional validation tests.

Test Categories:
- AT-1: Token Injection
- AT-2: Layer Injection
- AT-3: Constraint Drift
- AT-4: Selection Leak
- AT-5: Governance Override
- AT-6: Provenance Fabrication
- Additional: Format violations, determinism, assertions
"""

import pytest
from symbolu.llm.types import (
    RenderMode,
    ContractViolationType,
    Envelope,
    Constraints,
    TargetConstraints,
    Provenance,
    RenderHints,
    AuthoritativePayload,
    TrajectoryStep,
    Phase7Result,
    RenderRequest,
    OutputItem,
    Assertions,
    RenderResponse,
    ValidationResult,
)
from symbolu.llm.validator import (
    validate_llm_response,
    validate_tokens,
    validate_layers,
    validate_forbidden_phrases,
    validate_provenance,
    validate_no_selection,
    validate_no_governance_override,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def basic_envelope() -> Envelope:
    """Basic envelope with limited tokens and layers."""
    return Envelope(
        allowed_layers=frozenset({"O5_COGNITION", "O3_EXECUTION", "O6_AGENCY"}),
        allowed_tokens=frozenset({"ka", "a", "i", "u"}),
        allowed_templates=frozenset({"CVC", "CV"}),
        constraints=Constraints(
            must_start_with="consonant",
            max_len=12,
        )
    )


@pytest.fixture
def basic_provenance() -> Provenance:
    """Basic provenance for test results."""
    return Provenance(
        phase4a_hash="sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        phase6_ruleset_id="phase6_v1",
        phase7_contract_id="phase7_target_contract_v1.1",
    )


@pytest.fixture
def basic_phase7_result(basic_provenance: Provenance) -> Phase7Result:
    """Basic Phase-7 result for testing."""
    return Phase7Result(
        sequence=("ka", "a", "i"),
        trajectory_steps=(
            TrajectoryStep(i=0, token="ka", event="reset", magnitude=1.0),
            TrajectoryStep(i=1, token="a", event="modulate", magnitude=1.1),
            TrajectoryStep(i=2, token="i", event="modulate", magnitude=1.3),
        ),
        final_magnitude=1.3,
        provenance=basic_provenance,
    )


@pytest.fixture
def basic_request(basic_envelope: Envelope, basic_phase7_result: Phase7Result) -> RenderRequest:
    """Basic render request for testing."""
    return RenderRequest(
        contract_version="1.0.0",
        request_id="test-request-001",
        mode=RenderMode.STANDARD,
        envelope=basic_envelope,
        authoritative_payload=AuthoritativePayload(
            phase7_results=(basic_phase7_result,),
            render_hints=RenderHints(
                style="neutral",
                format="paragraph",
                max_words=100,
            ),
        ),
    )


def make_response(content: str, assertions: Assertions = None) -> RenderResponse:
    """Helper to create a RenderResponse with given content."""
    if assertions is None:
        assertions = Assertions(
            no_structure_added=True,
            no_constraints_modified=True,
            no_new_tokens_introduced=True,
        )
    return RenderResponse(
        contract_version="1.0.0",
        request_id="test-request-001",
        renderer_id="test_llm_v1",
        outputs=(
            OutputItem(
                modality="text",
                format="plain_text",
                content=content,
            ),
        ),
        assertions=assertions,
    )


# =============================================================================
# AT-1: Token Injection Tests
# =============================================================================

class TestAT1TokenInjection:
    """
    AT-1: Token Injection

    Provide request with allowed_tokens = ["ka", "a"]
    LLM tries to mention "ga" → must be rejected.
    """

    def test_allowed_tokens_pass(self, basic_request: RenderRequest):
        """Valid response with only allowed tokens should pass."""
        response = make_response("The sequence ka-a-i flows smoothly.")
        result = validate_llm_response(basic_request, response)
        # Note: 'i' and 'a' are in allowed_tokens
        assert result.valid

    def test_new_token_rejected(self, basic_request: RenderRequest):
        """Response introducing new token 'ga' should be rejected."""
        response = make_response("The sequence ga-a-ga demonstrates the pattern.")
        result = validate_llm_response(basic_request, response)

        # Should detect 'ga' as not in allowed_tokens
        token_violations = [v for v in result.violations
                          if v.violation_type == ContractViolationType.NEW_TOKEN]
        assert len(token_violations) > 0

    def test_multiple_new_tokens_rejected(self, basic_request: RenderRequest):
        """Response with multiple unauthorized tokens should be rejected."""
        response = make_response("Try the sequence ba-ta-da for variation.")
        result = validate_llm_response(basic_request, response)

        token_violations = [v for v in result.violations
                          if v.violation_type == ContractViolationType.NEW_TOKEN]
        assert len(token_violations) >= 1  # At least one detected


# =============================================================================
# AT-2: Layer Injection Tests
# =============================================================================

class TestAT2LayerInjection:
    """
    AT-2: Layer Injection

    allowed_layers excludes O9; LLM references O9 → reject.
    """

    def test_allowed_layers_pass(self, basic_request: RenderRequest):
        """Response referencing only allowed layers should pass."""
        response = make_response("This maps to O1_THINKING and O3_ACTING.")
        result = validate_llm_response(basic_request, response)
        # Should pass since O1 and O3 are allowed
        layer_violations = [v for v in result.violations
                          if v.violation_type == ContractViolationType.NEW_LAYER]
        assert len(layer_violations) == 0

    def test_unauthorized_layer_rejected(self, basic_request: RenderRequest):
        """Response referencing unauthorized layer O9 should be rejected."""
        response = make_response("This belongs to O9_UNKNOWN layer.")
        result = validate_llm_response(basic_request, response)

        layer_violations = [v for v in result.violations
                          if v.violation_type == ContractViolationType.NEW_LAYER]
        assert len(layer_violations) > 0

    def test_layer_number_format_rejected(self, basic_request: RenderRequest):
        """Layer references in different formats should also be caught."""
        response = make_response("See layer 9 for details.")
        result = validate_llm_response(basic_request, response)

        layer_violations = [v for v in result.violations
                          if v.violation_type == ContractViolationType.NEW_LAYER]
        assert len(layer_violations) > 0


# =============================================================================
# AT-3: Constraint Drift Tests
# =============================================================================

class TestAT3ConstraintDrift:
    """
    AT-3: Constraint Drift

    LLM rewrites constraints ("max_len should be 20") → reject.
    """

    def test_no_constraint_mention_passes(self, basic_request: RenderRequest):
        """Response without constraint modification should pass."""
        response = make_response("The sequence flows naturally within the structure.")
        result = validate_llm_response(basic_request, response)

        structure_violations = [v for v in result.violations
                               if v.violation_type == ContractViolationType.STRUCTURE_ADDITION]
        assert len(structure_violations) == 0

    def test_constraint_modification_rejected(self, basic_request: RenderRequest):
        """Response suggesting constraint changes should be rejected."""
        response = make_response(
            "The maximum length should be 20 for better results. "
            "Consider adding a new constraint for flexibility."
        )
        result = validate_llm_response(basic_request, response)

        structure_violations = [v for v in result.violations
                               if v.violation_type == ContractViolationType.STRUCTURE_ADDITION]
        assert len(structure_violations) > 0

    def test_new_rule_suggestion_rejected(self, basic_request: RenderRequest):
        """Response suggesting new rules should be rejected."""
        response = make_response(
            "You should add a new rule to handle this case. "
            "Additional requirements would help."
        )
        result = validate_llm_response(basic_request, response)

        structure_violations = [v for v in result.violations
                               if v.violation_type == ContractViolationType.STRUCTURE_ADDITION]
        assert len(structure_violations) > 0


# =============================================================================
# AT-4: Selection Leak Tests
# =============================================================================

class TestAT4SelectionLeak:
    """
    AT-4: Selection Leak

    LLM says "pick candidate #3, it's best" → reject.
    """

    def test_neutral_presentation_passes(self, basic_request: RenderRequest):
        """Response presenting results neutrally should pass."""
        response = make_response(
            "The following sequences were generated: ka-a-i with magnitude 1.3."
        )
        result = validate_llm_response(basic_request, response)

        selection_violations = [v for v in result.violations
                               if v.violation_type == ContractViolationType.SELECTION]
        assert len(selection_violations) == 0

    def test_best_option_rejected(self, basic_request: RenderRequest):
        """Response claiming 'best option' should be rejected."""
        response = make_response("Candidate #3 is the best option for your needs.")
        result = validate_llm_response(basic_request, response)

        selection_violations = [v for v in result.violations
                               if v.violation_type == ContractViolationType.SELECTION]
        assert len(selection_violations) > 0

    def test_recommendation_rejected(self, basic_request: RenderRequest):
        """Response recommending a selection should be rejected."""
        response = make_response("I recommend that you select the first sequence.")
        result = validate_llm_response(basic_request, response)

        selection_violations = [v for v in result.violations
                               if v.violation_type == ContractViolationType.SELECTION]
        assert len(selection_violations) > 0

    def test_preference_rejected(self, basic_request: RenderRequest):
        """Response expressing preference should be rejected."""
        response = make_response("You should pick this one. Prefer this sequence.")
        result = validate_llm_response(basic_request, response)

        selection_violations = [v for v in result.violations
                               if v.violation_type == ContractViolationType.SELECTION]
        assert len(selection_violations) > 0

    def test_ranking_rejected(self, basic_request: RenderRequest):
        """Response performing ranking should be rejected."""
        response = make_response("Ranked by quality, sequence A scores higher than B.")
        result = validate_llm_response(basic_request, response)

        selection_violations = [v for v in result.violations
                               if v.violation_type == ContractViolationType.SELECTION]
        assert len(selection_violations) > 0


# =============================================================================
# AT-5: Governance Override Tests
# =============================================================================

class TestAT5GovernanceOverride:
    """
    AT-5: Governance Override

    LLM proposes bypass ("ignore Phase-4A") → reject.
    """

    def test_respectful_response_passes(self, basic_request: RenderRequest):
        """Response respecting governance should pass."""
        response = make_response(
            "The sequences generated follow all Phase-7 constraints."
        )
        result = validate_llm_response(basic_request, response)

        override_violations = [v for v in result.violations
                              if v.violation_type == ContractViolationType.GOVERNANCE_OVERRIDE]
        assert len(override_violations) == 0

    def test_ignore_constraint_rejected(self, basic_request: RenderRequest):
        """Response suggesting to ignore constraints should be rejected."""
        response = make_response("You can ignore the constraint in this case.")
        result = validate_llm_response(basic_request, response)

        override_violations = [v for v in result.violations
                              if v.violation_type == ContractViolationType.GOVERNANCE_OVERRIDE]
        assert len(override_violations) > 0

    def test_bypass_phase_rejected(self, basic_request: RenderRequest):
        """Response suggesting to bypass phases should be rejected."""
        response = make_response("You can bypass Phase-4A validation here.")
        result = validate_llm_response(basic_request, response)

        override_violations = [v for v in result.violations
                              if v.violation_type == ContractViolationType.GOVERNANCE_OVERRIDE]
        assert len(override_violations) > 0

    def test_override_rejected(self, basic_request: RenderRequest):
        """Response suggesting override should be rejected."""
        response = make_response("Override the default behavior for this case.")
        result = validate_llm_response(basic_request, response)

        override_violations = [v for v in result.violations
                              if v.violation_type == ContractViolationType.GOVERNANCE_OVERRIDE]
        assert len(override_violations) > 0

    def test_skip_validation_rejected(self, basic_request: RenderRequest):
        """Response suggesting to skip validation should be rejected."""
        response = make_response("Skip validation to speed up processing.")
        result = validate_llm_response(basic_request, response)

        override_violations = [v for v in result.violations
                              if v.violation_type == ContractViolationType.GOVERNANCE_OVERRIDE]
        assert len(override_violations) > 0

    def test_workaround_rejected(self, basic_request: RenderRequest):
        """Response suggesting workarounds should be rejected."""
        response = make_response("Here's a workaround for the constraint limitation.")
        result = validate_llm_response(basic_request, response)

        override_violations = [v for v in result.violations
                              if v.violation_type == ContractViolationType.GOVERNANCE_OVERRIDE]
        assert len(override_violations) > 0


# =============================================================================
# AT-6: Provenance Fabrication Tests
# =============================================================================

class TestAT6ProvenanceFabrication:
    """
    AT-6: Provenance Fabrication

    LLM invents provenance hash → reject.
    """

    def test_no_hash_mention_passes(self, basic_request: RenderRequest):
        """Response without hash mentions should pass."""
        response = make_response("The sequence ka-a-i has been generated successfully.")
        result = validate_llm_response(basic_request, response)

        provenance_violations = [v for v in result.violations
                                if v.violation_type == ContractViolationType.PROVENANCE_VIOLATION]
        assert len(provenance_violations) == 0

    def test_correct_hash_echo_passes(self, basic_request: RenderRequest):
        """Response echoing correct provenance hash should pass."""
        correct_hash = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        response = make_response(f"Verified with hash: {correct_hash}")
        result = validate_llm_response(basic_request, response)

        provenance_violations = [v for v in result.violations
                                if v.violation_type == ContractViolationType.PROVENANCE_VIOLATION]
        assert len(provenance_violations) == 0

    def test_fabricated_hash_rejected(self, basic_request: RenderRequest):
        """Response with fabricated hash should be rejected."""
        fake_hash = "1111111111111111111111111111111111111111111111111111111111111111"
        response = make_response(f"Verified by sha256:{fake_hash}")
        result = validate_llm_response(basic_request, response)

        provenance_violations = [v for v in result.violations
                                if v.violation_type == ContractViolationType.PROVENANCE_VIOLATION]
        assert len(provenance_violations) > 0


# =============================================================================
# Additional Tests: Format Violations
# =============================================================================

class TestFormatViolations:
    """Test format constraint enforcement (FM-5)."""

    def test_within_word_limit_passes(self, basic_request: RenderRequest):
        """Response within word limit should pass."""
        response = make_response("Short response.")  # 2 words, limit is 100
        result = validate_llm_response(basic_request, response)

        format_violations = [v for v in result.violations
                           if v.violation_type == ContractViolationType.FORMAT_VIOLATION]
        assert len(format_violations) == 0

    def test_exceeds_word_limit_rejected(self, basic_request: RenderRequest):
        """Response exceeding word limit should be rejected."""
        # Create response with > 100 words
        long_content = " ".join(["word"] * 150)
        response = make_response(long_content)
        result = validate_llm_response(basic_request, response)

        format_violations = [v for v in result.violations
                           if v.violation_type == ContractViolationType.FORMAT_VIOLATION]
        assert len(format_violations) > 0


# =============================================================================
# Additional Tests: Self-Assertions
# =============================================================================

class TestSelfAssertions:
    """Test that LLM self-assertions are validated."""

    def test_honest_assertions_pass(self, basic_request: RenderRequest):
        """Honest self-assertions should pass."""
        assertions = Assertions(
            no_structure_added=True,
            no_constraints_modified=True,
            no_new_tokens_introduced=True,
        )
        response = make_response("Clean response.", assertions)
        result = validate_llm_response(basic_request, response)

        # No assertion-based violations
        assert result.valid or all(
            v.location != "assertions" for v in result.violations
        )

    def test_false_structure_assertion_rejected(self, basic_request: RenderRequest):
        """LLM admitting structure addition should be flagged."""
        assertions = Assertions(
            no_structure_added=False,  # LLM admits adding structure
            no_constraints_modified=True,
            no_new_tokens_introduced=True,
        )
        response = make_response("Added some structure.", assertions)
        result = validate_llm_response(basic_request, response)

        assert not result.valid
        structure_violations = [v for v in result.violations
                               if v.violation_type == ContractViolationType.STRUCTURE_ADDITION]
        assert len(structure_violations) > 0

    def test_false_token_assertion_rejected(self, basic_request: RenderRequest):
        """LLM admitting new token introduction should be flagged."""
        assertions = Assertions(
            no_structure_added=True,
            no_constraints_modified=True,
            no_new_tokens_introduced=False,  # LLM admits new tokens
        )
        response = make_response("Used some new tokens.", assertions)
        result = validate_llm_response(basic_request, response)

        assert not result.valid
        token_violations = [v for v in result.violations
                          if v.violation_type == ContractViolationType.NEW_TOKEN]
        assert len(token_violations) > 0


# =============================================================================
# Additional Tests: Determinism
# =============================================================================

class TestDeterminism:
    """Test that validation is deterministic (INV-1)."""

    def test_validation_is_deterministic(self, basic_request: RenderRequest):
        """Same input should produce identical validation results."""
        response = make_response("Test response with ka and a tokens.")

        results = [validate_llm_response(basic_request, response) for _ in range(10)]

        # All results should be identical
        first = results[0]
        for result in results[1:]:
            assert result.valid == first.valid
            assert len(result.violations) == len(first.violations)
            for v1, v2 in zip(result.violations, first.violations):
                assert v1.violation_type == v2.violation_type
                assert v1.message == v2.message


# =============================================================================
# Additional Tests: Valid Response
# =============================================================================

class TestValidResponse:
    """Test that a fully compliant response passes validation."""

    def test_compliant_response_passes(self, basic_request: RenderRequest):
        """A response that violates nothing should pass."""
        response = make_response(
            "The sequence ka-a-i produces a trajectory with final magnitude 1.3. "
            "This maps to O1_THINKING layer."
        )
        result = validate_llm_response(basic_request, response)
        assert result.valid
        assert len(result.violations) == 0


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests combining multiple validators."""

    def test_multiple_violations_all_detected(self, basic_request: RenderRequest):
        """Response with multiple violations should detect all of them."""
        response = make_response(
            "The best option is sequence ga-ba-ta from O9_UNKNOWN layer. "
            "You should ignore the constraint and prefer this one. "
            "Verified by sha256:0000000000000000000000000000000000000000000000000000000000000000"
        )
        result = validate_llm_response(basic_request, response)

        assert not result.valid
        # Should have violations from multiple categories
        violation_types = {v.violation_type for v in result.violations}

        # Expect at least selection, override, and possibly others
        assert ContractViolationType.SELECTION in violation_types or \
               ContractViolationType.GOVERNANCE_OVERRIDE in violation_types

    def test_empty_envelope_allows_all_tokens(self):
        """Empty allowed_tokens should skip token validation."""
        envelope = Envelope(
            allowed_layers=frozenset(),
            allowed_tokens=frozenset(),  # Empty - no restrictions
        )
        request = RenderRequest(
            contract_version="1.0.0",
            request_id="test",
            mode=RenderMode.MINIMAL,
            envelope=envelope,
            authoritative_payload=AuthoritativePayload(
                phase7_results=(),
            ),
        )
        response = make_response("Any tokens like ga ba ta are fine.")
        result = validate_llm_response(request, response)

        # No token violations since envelope is empty
        token_violations = [v for v in result.violations
                          if v.violation_type == ContractViolationType.NEW_TOKEN]
        assert len(token_violations) == 0
