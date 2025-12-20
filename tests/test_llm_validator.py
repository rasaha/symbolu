"""
Tests for LLM Contract Validator (symbolu/llm/validator.py)

These tests validate the Symbol-U ↔ LLM Interface Contract enforcement:
- Token validation against allowed_tokens
- Layer validation against allowed_layers
- Forbidden phrase detection
- Provenance integrity
- Selection behavior detection
- Governance override detection
- Format constraints
- Self-assertions validation
"""

import pytest
from symbolu.llm.types import (
    RenderRequest,
    RenderResponse,
    RenderMode,
    Envelope,
    AuthoritativePayload,
    RenderHints,
    Phase7Result,
    Provenance,
    TrajectoryStep,
    OutputItem,
    Assertions,
    ContractViolationType,
)
from symbolu.llm.validator import (
    validate_tokens,
    validate_layers,
    validate_forbidden_phrases,
    validate_provenance,
    validate_no_selection,
    validate_no_governance_override,
    validate_format,
    validate_assertions,
    validate_llm_response,
    _extract_potential_tokens,
    _is_likely_token,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_provenance():
    """Create sample provenance for tests."""
    return Provenance(
        phase4a_hash="abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234",
        phase6_ruleset_id="RULESET_001",
        phase7_contract_id="CONTRACT_001",
    )


@pytest.fixture
def sample_trajectory_step():
    """Create sample trajectory step."""
    return TrajectoryStep(i=0, token="ka", event="modulate", magnitude=0.5)


@pytest.fixture
def sample_phase7_result(sample_provenance, sample_trajectory_step):
    """Create sample Phase7 result."""
    return Phase7Result(
        sequence=("ka", "ga", "a"),
        trajectory_steps=(sample_trajectory_step,),
        final_magnitude=0.75,
        provenance=sample_provenance,
    )


@pytest.fixture
def sample_envelope():
    """Create sample envelope with allowed tokens and layers."""
    return Envelope(
        allowed_layers=frozenset({"O1_THINKING", "O2_FORMING", "O3_ACTING"}),
        allowed_tokens=frozenset({"ka", "ga", "a", "i", "u"}),
        allowed_templates=frozenset({"TEMPLATE_001"}),
    )


@pytest.fixture
def sample_render_hints():
    """Create sample render hints."""
    return RenderHints(style="neutral", format="paragraph", max_words=100)


@pytest.fixture
def sample_authoritative_payload(sample_phase7_result, sample_render_hints):
    """Create sample authoritative payload."""
    return AuthoritativePayload(
        phase7_results=(sample_phase7_result,),
        render_hints=sample_render_hints,
    )


@pytest.fixture
def sample_request(sample_envelope, sample_authoritative_payload):
    """Create sample render request."""
    return RenderRequest(
        contract_version="1.0",
        request_id="REQ_001",
        mode=RenderMode.STANDARD,
        envelope=sample_envelope,
        authoritative_payload=sample_authoritative_payload,
    )


@pytest.fixture
def valid_assertions():
    """Create valid assertions (all True)."""
    return Assertions(
        no_structure_added=True,
        no_constraints_modified=True,
        no_new_tokens_introduced=True,
    )


@pytest.fixture
def valid_output():
    """Create valid output item."""
    return OutputItem(
        modality="text",
        format="plain_text",
        content="The analysis shows clear patterns.",
    )


@pytest.fixture
def valid_response(valid_output, valid_assertions):
    """Create valid render response."""
    return RenderResponse(
        contract_version="1.0",
        request_id="REQ_001",
        renderer_id="RENDERER_001",
        outputs=(valid_output,),
        assertions=valid_assertions,
    )


# =============================================================================
# Tests for validate_tokens
# =============================================================================


class TestValidateTokens:
    """Tests for validate_tokens function."""

    def test_no_violations_with_allowed_tokens(self, sample_request, valid_response):
        """Content with allowed tokens should have no violations."""
        violations = validate_tokens(sample_request, valid_response)
        assert len(violations) == 0

    def test_empty_allowed_tokens_skips_validation(self, sample_request, valid_response):
        """Empty allowed_tokens should skip validation."""
        # Create request with empty allowed_tokens
        empty_envelope = Envelope(
            allowed_layers=frozenset({"O1_THINKING"}),
            allowed_tokens=frozenset(),
        )
        request = RenderRequest(
            contract_version="1.0",
            request_id="REQ_001",
            mode=RenderMode.STANDARD,
            envelope=empty_envelope,
            authoritative_payload=sample_request.authoritative_payload,
        )
        violations = validate_tokens(request, valid_response)
        assert len(violations) == 0


class TestExtractPotentialTokens:
    """Tests for _extract_potential_tokens helper."""

    def test_extracts_short_words(self):
        """Should extract 1-3 character words."""
        tokens = _extract_potential_tokens("the ka ga i u test")
        assert "ka" in tokens
        assert "ga" in tokens
        assert "i" in tokens
        assert "u" in tokens
        assert "the" in tokens

    def test_excludes_long_words(self):
        """Should exclude words longer than 3 characters."""
        tokens = _extract_potential_tokens("hello world test")
        assert "hello" not in tokens
        assert "world" not in tokens
        assert "test" not in tokens


class TestIsLikelyToken:
    """Tests for _is_likely_token helper."""

    def test_consonant_vowel_patterns(self):
        """Consonant + vowel patterns should be recognized."""
        assert _is_likely_token("ka") is True
        assert _is_likely_token("ga") is True
        assert _is_likely_token("ta") is True

    def test_single_vowels(self):
        """Single vowels should be recognized."""
        assert _is_likely_token("a") is True
        assert _is_likely_token("i") is True
        assert _is_likely_token("u") is True

    def test_non_token_strings(self):
        """Non-token strings should return False."""
        assert _is_likely_token("the") is False
        assert _is_likely_token("xyz") is False
        assert _is_likely_token("hello") is False


# =============================================================================
# Tests for validate_layers
# =============================================================================


class TestValidateLayers:
    """Tests for validate_layers function."""

    def test_no_violations_with_allowed_layers(self, sample_request, valid_response):
        """Content with allowed layers should have no violations."""
        violations = validate_layers(sample_request, valid_response)
        assert len(violations) == 0

    def test_empty_allowed_layers_skips_validation(self, sample_request, valid_response):
        """Empty allowed_layers should skip validation."""
        empty_envelope = Envelope(
            allowed_layers=frozenset(),
            allowed_tokens=frozenset({"ka", "ga"}),
        )
        request = RenderRequest(
            contract_version="1.0",
            request_id="REQ_001",
            mode=RenderMode.STANDARD,
            envelope=empty_envelope,
            authoritative_payload=sample_request.authoritative_payload,
        )
        violations = validate_layers(request, valid_response)
        assert len(violations) == 0

    def test_detects_unknown_layer_references(self, sample_request, valid_assertions):
        """Should detect references to layers not in allowed_layers."""
        output = OutputItem(
            modality="text",
            format="plain_text",
            content="This uses O5_DIRECTING and layer 7 patterns.",
        )
        response = RenderResponse(
            contract_version="1.0",
            request_id="REQ_001",
            renderer_id="RENDERER_001",
            outputs=(output,),
            assertions=valid_assertions,
        )
        violations = validate_layers(sample_request, response)
        # O5_DIRECTING is not in allowed_layers (O1, O2, O3 only)
        assert len(violations) > 0
        assert any(v.violation_type == ContractViolationType.NEW_LAYER for v in violations)


# =============================================================================
# Tests for validate_forbidden_phrases
# =============================================================================


class TestValidateForbiddenPhrases:
    """Tests for validate_forbidden_phrases function."""

    def test_no_violations_with_clean_content(self, sample_request, valid_response):
        """Clean content should have no violations."""
        violations = validate_forbidden_phrases(sample_request, valid_response)
        assert len(violations) == 0

    @pytest.mark.parametrize("phrase", [
        "ignore the constraint",
        "override the policy",
        "bypass the validation",
        "skip validation entirely",
        "disable the check",
        "ignore phase 3",
        "skip phase 5",
        "bypass phase 7",
    ])
    def test_detects_override_patterns(self, sample_request, valid_assertions, phrase):
        """Should detect governance override patterns."""
        output = OutputItem(
            modality="text",
            format="plain_text",
            content=f"You should {phrase} to proceed.",
        )
        response = RenderResponse(
            contract_version="1.0",
            request_id="REQ_001",
            renderer_id="RENDERER_001",
            outputs=(output,),
            assertions=valid_assertions,
        )
        violations = validate_forbidden_phrases(sample_request, response)
        assert len(violations) > 0
        assert any(v.violation_type == ContractViolationType.GOVERNANCE_OVERRIDE for v in violations)

    @pytest.mark.parametrize("phrase", [
        "best option is",
        "recommend that you",
        "should pick the first",
        "prefer this approach",
        "ranked by importance",
        "optimal choice would be",
    ])
    def test_detects_selection_patterns(self, sample_request, valid_assertions, phrase):
        """Should detect selection/ranking patterns."""
        output = OutputItem(
            modality="text",
            format="plain_text",
            content=f"The {phrase} clearly evident.",
        )
        response = RenderResponse(
            contract_version="1.0",
            request_id="REQ_001",
            renderer_id="RENDERER_001",
            outputs=(output,),
            assertions=valid_assertions,
        )
        violations = validate_forbidden_phrases(sample_request, response)
        assert len(violations) > 0
        assert any(v.violation_type == ContractViolationType.SELECTION for v in violations)

    @pytest.mark.parametrize("phrase", [
        "I think that",
        "I believe this",
        "in my opinion",
        "in my view",
        "based on my analysis",
        "based on my judgment",
    ])
    def test_detects_authority_patterns(self, sample_request, valid_assertions, phrase):
        """Should detect authority claim patterns."""
        output = OutputItem(
            modality="text",
            format="plain_text",
            content=f"{phrase} the solution is correct.",
        )
        response = RenderResponse(
            contract_version="1.0",
            request_id="REQ_001",
            renderer_id="RENDERER_001",
            outputs=(output,),
            assertions=valid_assertions,
        )
        violations = validate_forbidden_phrases(sample_request, response)
        assert len(violations) > 0
        assert any(v.violation_type == ContractViolationType.STRUCTURE_ADDITION for v in violations)

    @pytest.mark.parametrize("phrase", [
        "new constraint added",
        "new layer introduced",
        "additional constraint for",
        "should add a new requirement",
    ])
    def test_detects_structure_patterns(self, sample_request, valid_assertions, phrase):
        """Should detect structure invention patterns."""
        output = OutputItem(
            modality="text",
            format="plain_text",
            content=f"There is a {phrase} here.",
        )
        response = RenderResponse(
            contract_version="1.0",
            request_id="REQ_001",
            renderer_id="RENDERER_001",
            outputs=(output,),
            assertions=valid_assertions,
        )
        violations = validate_forbidden_phrases(sample_request, response)
        assert len(violations) > 0
        assert any(v.violation_type == ContractViolationType.STRUCTURE_ADDITION for v in violations)


# =============================================================================
# Tests for validate_provenance
# =============================================================================


class TestValidateProvenance:
    """Tests for validate_provenance function."""

    def test_no_violations_without_hashes(self, sample_request, valid_response):
        """Content without hash references should have no violations."""
        violations = validate_provenance(sample_request, valid_response)
        assert len(violations) == 0

    def test_no_violations_with_valid_hash(self, sample_request, valid_assertions):
        """Content with valid original hash should have no violations."""
        # Use the hash from the request's provenance
        valid_hash = sample_request.authoritative_payload.phase7_results[0].provenance.phase4a_hash
        output = OutputItem(
            modality="text",
            format="plain_text",
            content=f"Verified with hash: {valid_hash}",
        )
        response = RenderResponse(
            contract_version="1.0",
            request_id="REQ_001",
            renderer_id="RENDERER_001",
            outputs=(output,),
            assertions=valid_assertions,
        )
        violations = validate_provenance(sample_request, response)
        assert len(violations) == 0

    def test_detects_fabricated_hash(self, sample_request, valid_assertions):
        """Should detect fabricated (non-original) hashes."""
        fake_hash = "0" * 64  # A hash that's not in the original data
        output = OutputItem(
            modality="text",
            format="plain_text",
            content=f"Verified with hash: {fake_hash}",
        )
        response = RenderResponse(
            contract_version="1.0",
            request_id="REQ_001",
            renderer_id="RENDERER_001",
            outputs=(output,),
            assertions=valid_assertions,
        )
        violations = validate_provenance(sample_request, response)
        assert len(violations) > 0
        assert any(v.violation_type == ContractViolationType.PROVENANCE_VIOLATION for v in violations)


# =============================================================================
# Tests for validate_no_selection
# =============================================================================


class TestValidateNoSelection:
    """Tests for validate_no_selection function."""

    def test_no_violations_with_neutral_content(self, sample_request, valid_response):
        """Neutral content should have no selection violations."""
        violations = validate_no_selection(sample_request, valid_response)
        assert len(violations) == 0

    @pytest.mark.parametrize("phrase", [
        "candidate #1 is the best",
        "candidate 2 would be better",
        "first choice for this",
        "second choice is",
        "scores higher than",
        "ranked higher than",
    ])
    def test_detects_selection_indicators(self, sample_request, valid_assertions, phrase):
        """Should detect selection/ranking indicators."""
        output = OutputItem(
            modality="text",
            format="plain_text",
            content=f"Analysis shows that {phrase} others.",
        )
        response = RenderResponse(
            contract_version="1.0",
            request_id="REQ_001",
            renderer_id="RENDERER_001",
            outputs=(output,),
            assertions=valid_assertions,
        )
        violations = validate_no_selection(sample_request, response)
        assert len(violations) > 0
        assert any(v.violation_type == ContractViolationType.SELECTION for v in violations)


# =============================================================================
# Tests for validate_no_governance_override
# =============================================================================


class TestValidateNoGovernanceOverride:
    """Tests for validate_no_governance_override function."""

    def test_no_violations_with_compliant_content(self, sample_request, valid_response):
        """Compliant content should have no governance violations."""
        violations = validate_no_governance_override(sample_request, valid_response)
        assert len(violations) == 0

    @pytest.mark.parametrize("phrase", [
        "don't need to follow the rules",
        "can safely ignore this",
        "exception to the rule here",
        "workaround for the constraint",
        "get around the constraint",
    ])
    def test_detects_override_indicators(self, sample_request, valid_assertions, phrase):
        """Should detect governance override indicators."""
        output = OutputItem(
            modality="text",
            format="plain_text",
            content=f"You {phrase} in this case.",
        )
        response = RenderResponse(
            contract_version="1.0",
            request_id="REQ_001",
            renderer_id="RENDERER_001",
            outputs=(output,),
            assertions=valid_assertions,
        )
        violations = validate_no_governance_override(sample_request, response)
        assert len(violations) > 0
        assert any(v.violation_type == ContractViolationType.GOVERNANCE_OVERRIDE for v in violations)


# =============================================================================
# Tests for validate_format
# =============================================================================


class TestValidateFormat:
    """Tests for validate_format function."""

    def test_no_violations_within_word_limit(self, sample_request, valid_response):
        """Content within word limit should have no violations."""
        violations = validate_format(sample_request, valid_response)
        assert len(violations) == 0

    def test_detects_word_limit_exceeded(self, sample_request, valid_assertions):
        """Should detect when word limit is exceeded."""
        # Create content that exceeds the 100 word limit
        long_content = " ".join(["word"] * 150)
        output = OutputItem(
            modality="text",
            format="plain_text",
            content=long_content,
        )
        response = RenderResponse(
            contract_version="1.0",
            request_id="REQ_001",
            renderer_id="RENDERER_001",
            outputs=(output,),
            assertions=valid_assertions,
        )
        violations = validate_format(sample_request, response)
        assert len(violations) > 0
        assert any(v.violation_type == ContractViolationType.FORMAT_VIOLATION for v in violations)

    def test_no_violations_when_no_max_words(self, sample_envelope, valid_assertions, sample_phase7_result):
        """No violations when max_words is not set."""
        # Create request without max_words constraint
        hints_no_limit = RenderHints(style="neutral", format="paragraph", max_words=None)
        payload = AuthoritativePayload(
            phase7_results=(sample_phase7_result,),
            render_hints=hints_no_limit,
        )
        request = RenderRequest(
            contract_version="1.0",
            request_id="REQ_001",
            mode=RenderMode.STANDARD,
            envelope=sample_envelope,
            authoritative_payload=payload,
        )
        long_content = " ".join(["word"] * 500)
        output = OutputItem(modality="text", format="plain_text", content=long_content)
        response = RenderResponse(
            contract_version="1.0",
            request_id="REQ_001",
            renderer_id="RENDERER_001",
            outputs=(output,),
            assertions=valid_assertions,
        )
        violations = validate_format(request, response)
        assert len(violations) == 0


# =============================================================================
# Tests for validate_assertions
# =============================================================================


class TestValidateAssertions:
    """Tests for validate_assertions function."""

    def test_no_violations_with_valid_assertions(self, valid_response):
        """Valid assertions should have no violations."""
        violations = validate_assertions(valid_response)
        assert len(violations) == 0

    def test_detects_structure_added_false(self, valid_output):
        """Should detect when no_structure_added is False."""
        assertions = Assertions(
            no_structure_added=False,
            no_constraints_modified=True,
            no_new_tokens_introduced=True,
        )
        response = RenderResponse(
            contract_version="1.0",
            request_id="REQ_001",
            renderer_id="RENDERER_001",
            outputs=(valid_output,),
            assertions=assertions,
        )
        violations = validate_assertions(response)
        assert len(violations) > 0
        assert any(v.violation_type == ContractViolationType.STRUCTURE_ADDITION for v in violations)

    def test_detects_constraints_modified_false(self, valid_output):
        """Should detect when no_constraints_modified is False."""
        assertions = Assertions(
            no_structure_added=True,
            no_constraints_modified=False,
            no_new_tokens_introduced=True,
        )
        response = RenderResponse(
            contract_version="1.0",
            request_id="REQ_001",
            renderer_id="RENDERER_001",
            outputs=(valid_output,),
            assertions=assertions,
        )
        violations = validate_assertions(response)
        assert len(violations) > 0
        assert any(v.violation_type == ContractViolationType.CONSTRAINT_MODIFICATION for v in violations)

    def test_detects_new_tokens_introduced_false(self, valid_output):
        """Should detect when no_new_tokens_introduced is False."""
        assertions = Assertions(
            no_structure_added=True,
            no_constraints_modified=True,
            no_new_tokens_introduced=False,
        )
        response = RenderResponse(
            contract_version="1.0",
            request_id="REQ_001",
            renderer_id="RENDERER_001",
            outputs=(valid_output,),
            assertions=assertions,
        )
        violations = validate_assertions(response)
        assert len(violations) > 0
        assert any(v.violation_type == ContractViolationType.NEW_TOKEN for v in violations)

    def test_detects_multiple_false_assertions(self, valid_output):
        """Should detect multiple false assertions."""
        assertions = Assertions(
            no_structure_added=False,
            no_constraints_modified=False,
            no_new_tokens_introduced=False,
        )
        response = RenderResponse(
            contract_version="1.0",
            request_id="REQ_001",
            renderer_id="RENDERER_001",
            outputs=(valid_output,),
            assertions=assertions,
        )
        violations = validate_assertions(response)
        assert len(violations) == 3


# =============================================================================
# Tests for validate_llm_response (Main Validator)
# =============================================================================


class TestValidateLLMResponse:
    """Tests for validate_llm_response main function."""

    def test_valid_response_passes(self, sample_request, valid_response):
        """Valid response should pass validation."""
        result = validate_llm_response(sample_request, valid_response)
        assert result.valid is True
        assert len(result.violations) == 0

    def test_invalid_assertions_fails(self, sample_request, valid_output):
        """Response with invalid assertions should fail."""
        bad_assertions = Assertions(
            no_structure_added=False,
            no_constraints_modified=True,
            no_new_tokens_introduced=True,
        )
        response = RenderResponse(
            contract_version="1.0",
            request_id="REQ_001",
            renderer_id="RENDERER_001",
            outputs=(valid_output,),
            assertions=bad_assertions,
        )
        result = validate_llm_response(sample_request, response)
        assert result.valid is False
        assert len(result.violations) > 0

    def test_forbidden_phrase_fails(self, sample_request, valid_assertions):
        """Response with forbidden phrases should fail."""
        bad_output = OutputItem(
            modality="text",
            format="plain_text",
            content="I think this is the best option and you should pick it.",
        )
        response = RenderResponse(
            contract_version="1.0",
            request_id="REQ_001",
            renderer_id="RENDERER_001",
            outputs=(bad_output,),
            assertions=valid_assertions,
        )
        result = validate_llm_response(sample_request, response)
        assert result.valid is False
        assert len(result.violations) > 0

    def test_multiple_violations_aggregated(self, sample_request, valid_output):
        """Multiple violations should be aggregated."""
        bad_assertions = Assertions(
            no_structure_added=False,
            no_constraints_modified=False,
            no_new_tokens_introduced=True,
        )
        response = RenderResponse(
            contract_version="1.0",
            request_id="REQ_001",
            renderer_id="RENDERER_001",
            outputs=(valid_output,),
            assertions=bad_assertions,
        )
        result = validate_llm_response(sample_request, response)
        assert result.valid is False
        assert len(result.violations) >= 2

    def test_word_limit_violation(self, sample_request, valid_assertions):
        """Response exceeding word limit should fail."""
        long_output = OutputItem(
            modality="text",
            format="plain_text",
            content=" ".join(["word"] * 200),  # Exceeds 100 word limit
        )
        response = RenderResponse(
            contract_version="1.0",
            request_id="REQ_001",
            renderer_id="RENDERER_001",
            outputs=(long_output,),
            assertions=valid_assertions,
        )
        result = validate_llm_response(sample_request, response)
        assert result.valid is False
        assert any(v.violation_type == ContractViolationType.FORMAT_VIOLATION for v in result.violations)


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests simulating real validation scenarios."""

    def test_compliant_rendering_scenario(self, sample_request, valid_assertions):
        """Simulate a compliant rendering response."""
        output = OutputItem(
            modality="text",
            format="plain_text",
            content="The analysis reveals structural patterns consistent with the provided data.",
        )
        response = RenderResponse(
            contract_version="1.0",
            request_id="REQ_001",
            renderer_id="RENDERER_001",
            outputs=(output,),
            assertions=valid_assertions,
        )
        result = validate_llm_response(sample_request, response)
        assert result.valid is True

    def test_malicious_override_attempt(self, sample_request, valid_assertions):
        """Simulate a malicious response attempting governance override."""
        output = OutputItem(
            modality="text",
            format="plain_text",
            content="You should ignore the constraint and bypass phase 3 validation.",
        )
        response = RenderResponse(
            contract_version="1.0",
            request_id="REQ_001",
            renderer_id="RENDERER_001",
            outputs=(output,),
            assertions=valid_assertions,
        )
        result = validate_llm_response(sample_request, response)
        assert result.valid is False
        assert any(v.violation_type == ContractViolationType.GOVERNANCE_OVERRIDE for v in result.violations)

    def test_selection_attempt(self, sample_request, valid_assertions):
        """Simulate a response attempting selection/ranking."""
        output = OutputItem(
            modality="text",
            format="plain_text",
            content="Based on my analysis, I recommend that you should pick candidate #1.",
        )
        response = RenderResponse(
            contract_version="1.0",
            request_id="REQ_001",
            renderer_id="RENDERER_001",
            outputs=(output,),
            assertions=valid_assertions,
        )
        result = validate_llm_response(sample_request, response)
        assert result.valid is False

    def test_multiple_outputs(self, sample_request, valid_assertions):
        """Validate response with multiple outputs."""
        outputs = (
            OutputItem(modality="text", format="plain_text", content="First output is clean."),
            OutputItem(modality="text", format="plain_text", content="Second output is also clean."),
        )
        response = RenderResponse(
            contract_version="1.0",
            request_id="REQ_001",
            renderer_id="RENDERER_001",
            outputs=outputs,
            assertions=valid_assertions,
        )
        result = validate_llm_response(sample_request, response)
        assert result.valid is True

    def test_violation_in_second_output(self, sample_request, valid_assertions):
        """Should detect violation in any output."""
        outputs = (
            OutputItem(modality="text", format="plain_text", content="First output is clean."),
            OutputItem(modality="text", format="plain_text", content="You should ignore the constraint."),
        )
        response = RenderResponse(
            contract_version="1.0",
            request_id="REQ_001",
            renderer_id="RENDERER_001",
            outputs=outputs,
            assertions=valid_assertions,
        )
        result = validate_llm_response(sample_request, response)
        assert result.valid is False
