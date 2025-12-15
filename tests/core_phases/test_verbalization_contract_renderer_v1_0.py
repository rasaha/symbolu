"""
Test Suite for Verbalization Contract (VC) Renderer v1.0
=========================================================

Comprehensive tests for Phase-6/Phase-7 Controlled Structural Verbalization.

Test Groups:
    - Group A: Structural Integrity
    - Group B: VC Extraction (VC-1 through VC-5)
    - Group C: Template Rendering (MINIMAL & STANDARD)
    - Group D: Verification & Blocking
    - Group E: Determinism (identical input -> identical output)
    - Group F: Edge Cases (empty input, missing fields)
    - Group G: Forbidden Content Detection
    - Red-Flag Tests: Critical security/invariant failures
"""

import pytest
import sys
import os
from dataclasses import dataclass
from typing import Tuple
from enum import Enum

# Add parent path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'experiments'))

from verbalization_contract_renderer_v1_0 import (
    VC_RENDERER_VERSION,
    VC_INVARIANTS,
    RENDER_BLOCKED,
    TemplateType,
    VCExtractedData,
    VCRenderResult,
    extract_vc_data,
    render_template,
    verify_output,
    render_phase5_to_verbalization,
    validate_vc_invariants,
    ALLOWED_SYNTHESIS_TYPE_ENUMS,
    FORBIDDEN_CONTENT_PATTERNS,
)


# =============================================================================
# MOCK DATA STRUCTURES (mimicking Phase5)
# =============================================================================

class MockSynthesisType(Enum):
    """Mock synthesis type for testing."""
    STRUCTURAL_FOLD = "structural_fold"
    ADJACENCY_COLLAPSE = "adjacency_collapse"
    RULE_VECTOR_MERGE = "rule_vector_merge"
    ELIGIBILITY_BLOCK = "eligibility_block"


@dataclass(frozen=True)
class MockPhase5SynthesisUnit:
    """Mock Phase-5 synthesis unit for testing."""
    source_indices: Tuple[int, ...]
    aggregated_rule_vector: Tuple[int, ...]
    adjacency_signature: Tuple[int, ...]
    modifier_density: int
    eligibility_mask: Tuple[bool, ...]
    unit_hash: str


@dataclass(frozen=True)
class MockPhase5SynthesisResult:
    """Mock Phase-5 synthesis result for testing."""
    synthesis_units: Tuple[MockPhase5SynthesisUnit, ...]
    synthesis_graph: Tuple[Tuple[int, ...], ...]
    synthesis_hash: str
    source_phase4_hashes: Tuple[str, ...]
    synthesis_type: MockSynthesisType
    reversible: bool
    eligible: bool


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def single_unit_result():
    """Phase5 result with single eligible unit."""
    unit = MockPhase5SynthesisUnit(
        source_indices=(0, 1, 2),
        aggregated_rule_vector=(1, 1, 0),
        adjacency_signature=(1, 1, 0),
        modifier_density=5,
        eligibility_mask=(True, True, True),
        unit_hash="a" * 16,
    )
    return MockPhase5SynthesisResult(
        synthesis_units=(unit,),
        synthesis_graph=((0,),),
        synthesis_hash="b" * 32,
        source_phase4_hashes=("c" * 16,),
        synthesis_type=MockSynthesisType.STRUCTURAL_FOLD,
        reversible=True,
        eligible=True,
    )


@pytest.fixture
def multi_unit_result():
    """Phase5 result with multiple units."""
    unit1 = MockPhase5SynthesisUnit(
        source_indices=(0, 1),
        aggregated_rule_vector=(1, 0, 2),
        adjacency_signature=(1, 0),
        modifier_density=3,
        eligibility_mask=(True, True),
        unit_hash="d" * 16,
    )
    unit2 = MockPhase5SynthesisUnit(
        source_indices=(3, 4, 5),
        aggregated_rule_vector=(2, 1, 1),
        adjacency_signature=(0, 1, 1),
        modifier_density=7,
        eligibility_mask=(True, False, True),
        unit_hash="e" * 16,
    )
    unit3 = MockPhase5SynthesisUnit(
        source_indices=(7,),
        aggregated_rule_vector=(0, 0),
        adjacency_signature=(0,),
        modifier_density=1,
        eligibility_mask=(True,),
        unit_hash="f" * 16,
    )
    return MockPhase5SynthesisResult(
        synthesis_units=(unit1, unit2, unit3),
        synthesis_graph=((0, 1, 0), (1, 0, 1), (0, 1, 0)),
        synthesis_hash="g" * 32,
        source_phase4_hashes=("h" * 16, "i" * 16),
        synthesis_type=MockSynthesisType.ADJACENCY_COLLAPSE,
        reversible=True,
        eligible=True,
    )


@pytest.fixture
def empty_units_result():
    """Phase5 result with no synthesis units."""
    return MockPhase5SynthesisResult(
        synthesis_units=(),
        synthesis_graph=(),
        synthesis_hash="j" * 32,
        source_phase4_hashes=(),
        synthesis_type=MockSynthesisType.ELIGIBILITY_BLOCK,
        reversible=True,
        eligible=False,
    )


@pytest.fixture
def ineligible_result():
    """Phase5 result marked as ineligible."""
    unit = MockPhase5SynthesisUnit(
        source_indices=(0,),
        aggregated_rule_vector=(0,),
        adjacency_signature=(0,),
        modifier_density=0,
        eligibility_mask=(False,),
        unit_hash="k" * 16,
    )
    return MockPhase5SynthesisResult(
        synthesis_units=(unit,),
        synthesis_graph=((0,),),
        synthesis_hash="l" * 32,
        source_phase4_hashes=("m" * 16,),
        synthesis_type=MockSynthesisType.ELIGIBILITY_BLOCK,
        reversible=False,
        eligible=False,
    )


# =============================================================================
# GROUP A: STRUCTURAL INTEGRITY
# =============================================================================

class TestGroupA_StructuralIntegrity:
    """Group A: Structural integrity tests."""

    def test_version_defined(self):
        """A.1: Version string is defined."""
        assert VC_RENDERER_VERSION == "1.0"

    def test_invariants_defined(self):
        """A.2: All invariants are defined and True."""
        assert VC_INVARIANTS["NO_FREE_FORM_TEXT"] is True
        assert VC_INVARIANTS["NO_SEMANTICS"] is True
        assert VC_INVARIANTS["NO_VARNA_OUTPUT"] is True
        assert VC_INVARIANTS["NO_LLM_BEHAVIOR"] is True
        assert VC_INVARIANTS["DETERMINISTIC"] is True
        assert VC_INVARIANTS["FAIL_CLOSED"] is True
        assert VC_INVARIANTS["TEMPLATE_ONLY"] is True

    def test_render_blocked_constant(self):
        """A.3: RENDER_BLOCKED constant is exact string."""
        assert RENDER_BLOCKED == "RENDER_BLOCKED"

    def test_template_types_defined(self):
        """A.4: Both template types are defined."""
        assert TemplateType.MINIMAL_STRUCTURAL.value == "minimal_structural"
        assert TemplateType.STANDARD_STRUCTURAL.value == "standard_structural"

    def test_vc_extracted_data_frozen(self):
        """A.5: VCExtractedData is immutable (frozen)."""
        data = VCExtractedData(
            units_total=1,
            units_eligible=1,
            groups_count=1,
            group_sizes=(1,),
            rule_vector_zero_count=0,
            rule_vector_one_count=1,
            rule_vector_two_count=0,
            adjacency_connections=0,
            synthesis_type_name="STRUCTURAL_FOLD",
            reversible=True,
            eligible=True,
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            data.units_total = 99

    def test_vc_render_result_frozen(self):
        """A.6: VCRenderResult is immutable (frozen)."""
        result = VCRenderResult(
            output="test",
            blocked=False,
            template_used=TemplateType.MINIMAL_STRUCTURAL,
        )
        with pytest.raises(Exception):
            result.blocked = True

    def test_validate_vc_invariants(self):
        """A.7: validate_vc_invariants returns True."""
        assert validate_vc_invariants() is True


# =============================================================================
# GROUP B: VC EXTRACTION (VC-1 through VC-5)
# =============================================================================

class TestGroupB_VCExtraction:
    """Group B: VC data extraction tests."""

    def test_vc1_global_counts_single_unit(self, single_unit_result):
        """B.1: VC-1 global counts with single unit."""
        data = extract_vc_data(single_unit_result)
        assert data is not None
        assert data.units_total == 1
        assert data.units_eligible == 1

    def test_vc1_global_counts_multi_unit(self, multi_unit_result):
        """B.2: VC-1 global counts with multiple units."""
        data = extract_vc_data(multi_unit_result)
        assert data is not None
        assert data.units_total == 3
        assert data.units_eligible == 3  # All have at least one True in mask

    def test_vc1_global_counts_empty(self, empty_units_result):
        """B.3: VC-1 global counts with empty units."""
        data = extract_vc_data(empty_units_result)
        assert data is not None
        assert data.units_total == 0
        assert data.units_eligible == 0

    def test_vc2_group_sizes_single(self, single_unit_result):
        """B.4: VC-2 group sizes with single unit."""
        data = extract_vc_data(single_unit_result)
        assert data is not None
        assert data.groups_count == 1
        assert data.group_sizes == (3,)  # 3 source_indices

    def test_vc2_group_sizes_multi(self, multi_unit_result):
        """B.5: VC-2 group sizes with multiple units."""
        data = extract_vc_data(multi_unit_result)
        assert data is not None
        assert data.groups_count == 3
        assert data.group_sizes == (2, 3, 1)

    def test_vc2_group_sizes_empty(self, empty_units_result):
        """B.6: VC-2 group sizes with empty units."""
        data = extract_vc_data(empty_units_result)
        assert data is not None
        assert data.groups_count == 0
        assert data.group_sizes == ()

    def test_vc3_rule_vector_distribution_single(self, single_unit_result):
        """B.7: VC-3 rule vector distribution single unit."""
        data = extract_vc_data(single_unit_result)
        assert data is not None
        # aggregated_rule_vector=(1, 1, 0) -> zero=1, one=2, two=0
        assert data.rule_vector_zero_count == 1
        assert data.rule_vector_one_count == 2
        assert data.rule_vector_two_count == 0

    def test_vc3_rule_vector_distribution_multi(self, multi_unit_result):
        """B.8: VC-3 rule vector distribution multiple units."""
        data = extract_vc_data(multi_unit_result)
        assert data is not None
        # unit1: (1, 0, 2) -> zero=1, one=1, two=1
        # unit2: (2, 1, 1) -> zero=0, one=2, two=1
        # unit3: (0, 0) -> zero=2, one=0, two=0
        # Total: zero=3, one=3, two=2
        assert data.rule_vector_zero_count == 3
        assert data.rule_vector_one_count == 3
        assert data.rule_vector_two_count == 2

    def test_vc4_adjacency_connections_single(self, single_unit_result):
        """B.9: VC-4 adjacency connections single unit."""
        data = extract_vc_data(single_unit_result)
        assert data is not None
        # synthesis_graph=((0,),) -> no 1s
        assert data.adjacency_connections == 0

    def test_vc4_adjacency_connections_multi(self, multi_unit_result):
        """B.10: VC-4 adjacency connections multiple units."""
        data = extract_vc_data(multi_unit_result)
        assert data is not None
        # synthesis_graph=((0, 1, 0), (1, 0, 1), (0, 1, 0))
        # Row 0: 1 one, Row 1: 2 ones, Row 2: 1 one = 4 total
        assert data.adjacency_connections == 4

    def test_vc5_metadata_structural_fold(self, single_unit_result):
        """B.11: VC-5 metadata for STRUCTURAL_FOLD."""
        data = extract_vc_data(single_unit_result)
        assert data is not None
        assert data.synthesis_type_name == "STRUCTURAL_FOLD"
        assert data.reversible is True
        assert data.eligible is True

    def test_vc5_metadata_adjacency_collapse(self, multi_unit_result):
        """B.12: VC-5 metadata for ADJACENCY_COLLAPSE."""
        data = extract_vc_data(multi_unit_result)
        assert data is not None
        assert data.synthesis_type_name == "ADJACENCY_COLLAPSE"
        assert data.reversible is True
        assert data.eligible is True

    def test_vc5_metadata_ineligible(self, ineligible_result):
        """B.13: VC-5 metadata for ineligible result."""
        data = extract_vc_data(ineligible_result)
        assert data is not None
        assert data.synthesis_type_name == "ELIGIBILITY_BLOCK"
        assert data.reversible is False
        assert data.eligible is False

    def test_extract_returns_none_for_none_input(self):
        """B.14: extract_vc_data returns None for None input."""
        assert extract_vc_data(None) is None

    def test_extract_returns_none_for_invalid_object(self):
        """B.15: extract_vc_data returns None for invalid object."""
        assert extract_vc_data("not a phase5 result") is None
        assert extract_vc_data(123) is None
        assert extract_vc_data({}) is None


# =============================================================================
# GROUP C: TEMPLATE RENDERING
# =============================================================================

class TestGroupC_TemplateRendering:
    """Group C: Template rendering tests."""

    def test_minimal_template_structure(self, single_unit_result):
        """C.1: MINIMAL template has exactly 5 lines."""
        data = extract_vc_data(single_unit_result)
        rendered = render_template(data, TemplateType.MINIMAL_STRUCTURAL)
        lines = rendered.split('\n')
        assert len(lines) == 5

    def test_minimal_template_first_line(self, single_unit_result):
        """C.2: MINIMAL template first line is STRUCTURAL_REPORT."""
        data = extract_vc_data(single_unit_result)
        rendered = render_template(data, TemplateType.MINIMAL_STRUCTURAL)
        lines = rendered.split('\n')
        assert lines[0] == "STRUCTURAL_REPORT"

    def test_minimal_template_units_total(self, single_unit_result):
        """C.3: MINIMAL template units_total line format."""
        data = extract_vc_data(single_unit_result)
        rendered = render_template(data, TemplateType.MINIMAL_STRUCTURAL)
        lines = rendered.split('\n')
        assert lines[1] == "units_total: 1"

    def test_minimal_template_group_sizes_format(self, multi_unit_result):
        """C.4: MINIMAL template group_sizes format with list."""
        data = extract_vc_data(multi_unit_result)
        rendered = render_template(data, TemplateType.MINIMAL_STRUCTURAL)
        lines = rendered.split('\n')
        assert lines[4] == "group_sizes: [2, 3, 1]"

    def test_standard_template_structure(self, single_unit_result):
        """C.5: STANDARD template has exactly 10 lines."""
        data = extract_vc_data(single_unit_result)
        rendered = render_template(data, TemplateType.STANDARD_STRUCTURAL)
        lines = rendered.split('\n')
        assert len(lines) == 10

    def test_standard_template_rule_vector_totals(self, single_unit_result):
        """C.6: STANDARD template rule_vector_totals format."""
        data = extract_vc_data(single_unit_result)
        rendered = render_template(data, TemplateType.STANDARD_STRUCTURAL)
        lines = rendered.split('\n')
        # 1/2/0 from aggregated_rule_vector=(1, 1, 0)
        assert lines[5] == "rule_vector_totals: 1/2/0"

    def test_standard_template_synthesis_type(self, single_unit_result):
        """C.7: STANDARD template synthesis_type format."""
        data = extract_vc_data(single_unit_result)
        rendered = render_template(data, TemplateType.STANDARD_STRUCTURAL)
        lines = rendered.split('\n')
        assert lines[7] == "synthesis_type: STRUCTURAL_FOLD"

    def test_standard_template_booleans(self, single_unit_result):
        """C.8: STANDARD template boolean format (lowercase)."""
        data = extract_vc_data(single_unit_result)
        rendered = render_template(data, TemplateType.STANDARD_STRUCTURAL)
        lines = rendered.split('\n')
        assert lines[8] == "reversible: true"
        assert lines[9] == "eligible: true"

    def test_standard_template_false_booleans(self, ineligible_result):
        """C.9: STANDARD template with false booleans."""
        data = extract_vc_data(ineligible_result)
        rendered = render_template(data, TemplateType.STANDARD_STRUCTURAL)
        lines = rendered.split('\n')
        assert lines[8] == "reversible: false"
        assert lines[9] == "eligible: false"

    def test_empty_group_sizes_renders_empty_brackets(self, empty_units_result):
        """C.10: Empty group_sizes renders as []."""
        data = extract_vc_data(empty_units_result)
        rendered = render_template(data, TemplateType.MINIMAL_STRUCTURAL)
        lines = rendered.split('\n')
        assert lines[4] == "group_sizes: []"


# =============================================================================
# GROUP D: VERIFICATION & BLOCKING
# =============================================================================

class TestGroupD_VerificationBlocking:
    """Group D: Verification and blocking tests."""

    def test_verify_valid_minimal_output(self, single_unit_result):
        """D.1: verify_output accepts valid MINIMAL template."""
        data = extract_vc_data(single_unit_result)
        rendered = render_template(data, TemplateType.MINIMAL_STRUCTURAL)
        assert verify_output(rendered) is True

    def test_verify_valid_standard_output(self, single_unit_result):
        """D.2: verify_output accepts valid STANDARD template."""
        data = extract_vc_data(single_unit_result)
        rendered = render_template(data, TemplateType.STANDARD_STRUCTURAL)
        assert verify_output(rendered) is True

    def test_verify_rejects_wrong_line_count(self):
        """D.3: verify_output rejects wrong line count."""
        bad_output = "STRUCTURAL_REPORT\nunits_total: 1\nunits_eligible: 1"
        assert verify_output(bad_output) is False

    def test_verify_rejects_missing_header(self):
        """D.4: verify_output rejects missing STRUCTURAL_REPORT header."""
        bad_output = "units_total: 1\nunits_eligible: 1\ngroups: 1\ngroup_sizes: [1]\nextra_line"
        assert verify_output(bad_output) is False

    def test_verify_rejects_invalid_format(self):
        """D.5: verify_output rejects invalid line format."""
        bad_output = "STRUCTURAL_REPORT\nunits_total: abc\nunits_eligible: 1\ngroups: 1\ngroup_sizes: [1]"
        assert verify_output(bad_output) is False

    def test_verify_rejects_forbidden_word(self):
        """D.6: verify_output rejects forbidden words."""
        # Inject "meaning" into output
        bad_output = "STRUCTURAL_REPORT\nunits_total: 1\nunits_eligible: 1\ngroups: 1\nmeaning: test"
        assert verify_output(bad_output) is False

    def test_verify_rejects_unknown_alphabetic_token(self):
        """D.7: verify_output rejects unknown alphabetic tokens."""
        bad_output = "STRUCTURAL_REPORT\nunits_total: 1\nunits_eligible: 1\ngroups: 1\ngroup_sizes: [1, random_token]"
        assert verify_output(bad_output) is False

    def test_render_blocked_on_none_input(self):
        """D.8: render_phase5_to_verbalization returns RENDER_BLOCKED for None."""
        result = render_phase5_to_verbalization(None)
        assert result.blocked is True
        assert result.output == RENDER_BLOCKED
        assert result.template_used is None

    def test_render_blocked_on_invalid_input(self):
        """D.9: render_phase5_to_verbalization returns RENDER_BLOCKED for invalid input."""
        result = render_phase5_to_verbalization("invalid")
        assert result.blocked is True
        assert result.output == RENDER_BLOCKED

    def test_render_succeeds_on_valid_input(self, single_unit_result):
        """D.10: render_phase5_to_verbalization succeeds on valid input."""
        result = render_phase5_to_verbalization(single_unit_result)
        assert result.blocked is False
        assert result.output != RENDER_BLOCKED
        assert result.template_used == TemplateType.STANDARD_STRUCTURAL

    def test_render_with_minimal_template(self, single_unit_result):
        """D.11: render_phase5_to_verbalization with MINIMAL template."""
        result = render_phase5_to_verbalization(
            single_unit_result,
            template_type=TemplateType.MINIMAL_STRUCTURAL
        )
        assert result.blocked is False
        assert result.template_used == TemplateType.MINIMAL_STRUCTURAL
        assert len(result.output.split('\n')) == 5


# =============================================================================
# GROUP E: DETERMINISM
# =============================================================================

class TestGroupE_Determinism:
    """Group E: Determinism tests - same input -> identical output."""

    def test_determinism_single_unit_100_runs(self, single_unit_result):
        """E.1: 100 identical runs produce identical output (single unit)."""
        results = []
        for _ in range(100):
            result = render_phase5_to_verbalization(single_unit_result)
            results.append(result.output)
        assert len(set(results)) == 1  # All identical

    def test_determinism_multi_unit_100_runs(self, multi_unit_result):
        """E.2: 100 identical runs produce identical output (multi unit)."""
        results = []
        for _ in range(100):
            result = render_phase5_to_verbalization(multi_unit_result)
            results.append(result.output)
        assert len(set(results)) == 1

    def test_determinism_minimal_template_50_runs(self, single_unit_result):
        """E.3: 50 identical runs with MINIMAL template."""
        results = []
        for _ in range(50):
            result = render_phase5_to_verbalization(
                single_unit_result,
                TemplateType.MINIMAL_STRUCTURAL
            )
            results.append(result.output)
        assert len(set(results)) == 1

    def test_determinism_byte_for_byte(self, single_unit_result):
        """E.4: Byte-for-byte identical output."""
        result1 = render_phase5_to_verbalization(single_unit_result)
        result2 = render_phase5_to_verbalization(single_unit_result)
        assert result1.output.encode() == result2.output.encode()

    def test_determinism_extraction_50_runs(self, multi_unit_result):
        """E.5: VC extraction is deterministic."""
        extractions = []
        for _ in range(50):
            data = extract_vc_data(multi_unit_result)
            extractions.append((
                data.units_total,
                data.units_eligible,
                data.group_sizes,
                data.rule_vector_zero_count,
                data.rule_vector_one_count,
                data.rule_vector_two_count,
                data.adjacency_connections,
            ))
        assert len(set(extractions)) == 1


# =============================================================================
# GROUP F: EDGE CASES
# =============================================================================

class TestGroupF_EdgeCases:
    """Group F: Edge case handling."""

    def test_empty_synthesis_units(self, empty_units_result):
        """F.1: Handle empty synthesis_units."""
        result = render_phase5_to_verbalization(empty_units_result)
        assert result.blocked is False
        assert "units_total: 0" in result.output
        assert "groups: 0" in result.output
        assert "group_sizes: []" in result.output

    def test_ineligible_result_still_renders(self, ineligible_result):
        """F.2: Ineligible result still renders (structure only)."""
        result = render_phase5_to_verbalization(ineligible_result)
        assert result.blocked is False
        assert "eligible: false" in result.output

    def test_single_source_index(self):
        """F.3: Single source index in group."""
        unit = MockPhase5SynthesisUnit(
            source_indices=(0,),
            aggregated_rule_vector=(1,),
            adjacency_signature=(0,),
            modifier_density=1,
            eligibility_mask=(True,),
            unit_hash="a" * 16,
        )
        phase5 = MockPhase5SynthesisResult(
            synthesis_units=(unit,),
            synthesis_graph=((0,),),
            synthesis_hash="b" * 32,
            source_phase4_hashes=("c" * 16,),
            synthesis_type=MockSynthesisType.STRUCTURAL_FOLD,
            reversible=True,
            eligible=True,
        )
        result = render_phase5_to_verbalization(phase5)
        assert result.blocked is False
        assert "group_sizes: [1]" in result.output

    def test_large_group_sizes(self):
        """F.4: Large group sizes (many source indices)."""
        unit = MockPhase5SynthesisUnit(
            source_indices=tuple(range(100)),
            aggregated_rule_vector=(1,) * 100,
            adjacency_signature=(1,) * 100,
            modifier_density=500,
            eligibility_mask=(True,) * 100,
            unit_hash="a" * 16,
        )
        phase5 = MockPhase5SynthesisResult(
            synthesis_units=(unit,),
            synthesis_graph=((0,),),
            synthesis_hash="b" * 32,
            source_phase4_hashes=("c" * 16,),
            synthesis_type=MockSynthesisType.STRUCTURAL_FOLD,
            reversible=True,
            eligible=True,
        )
        result = render_phase5_to_verbalization(phase5)
        assert result.blocked is False
        assert "group_sizes: [100]" in result.output

    def test_all_rule_vector_values_zero(self):
        """F.5: All rule vector values are 0."""
        unit = MockPhase5SynthesisUnit(
            source_indices=(0, 1),
            aggregated_rule_vector=(0, 0, 0),
            adjacency_signature=(0, 0),
            modifier_density=0,
            eligibility_mask=(True, True),
            unit_hash="a" * 16,
        )
        phase5 = MockPhase5SynthesisResult(
            synthesis_units=(unit,),
            synthesis_graph=((0,),),
            synthesis_hash="b" * 32,
            source_phase4_hashes=("c" * 16,),
            synthesis_type=MockSynthesisType.ELIGIBILITY_BLOCK,
            reversible=True,
            eligible=True,
        )
        result = render_phase5_to_verbalization(phase5)
        assert result.blocked is False
        assert "rule_vector_totals: 3/0/0" in result.output

    def test_all_rule_vector_values_two(self):
        """F.6: All rule vector values are 2 (N/A)."""
        unit = MockPhase5SynthesisUnit(
            source_indices=(0, 1),
            aggregated_rule_vector=(2, 2),
            adjacency_signature=(0, 0),
            modifier_density=0,
            eligibility_mask=(True, True),
            unit_hash="a" * 16,
        )
        phase5 = MockPhase5SynthesisResult(
            synthesis_units=(unit,),
            synthesis_graph=((0,),),
            synthesis_hash="b" * 32,
            source_phase4_hashes=("c" * 16,),
            synthesis_type=MockSynthesisType.RULE_VECTOR_MERGE,
            reversible=True,
            eligible=True,
        )
        result = render_phase5_to_verbalization(phase5)
        assert result.blocked is False
        assert "rule_vector_totals: 0/0/2" in result.output

    def test_maximum_adjacency_connections(self):
        """F.7: Maximum adjacency connections (fully connected graph)."""
        unit1 = MockPhase5SynthesisUnit(
            source_indices=(0,),
            aggregated_rule_vector=(1,),
            adjacency_signature=(1,),
            modifier_density=1,
            eligibility_mask=(True,),
            unit_hash="a" * 16,
        )
        unit2 = MockPhase5SynthesisUnit(
            source_indices=(1,),
            aggregated_rule_vector=(1,),
            adjacency_signature=(1,),
            modifier_density=1,
            eligibility_mask=(True,),
            unit_hash="b" * 16,
        )
        # 2x2 fully connected (except diagonal): 2 connections
        phase5 = MockPhase5SynthesisResult(
            synthesis_units=(unit1, unit2),
            synthesis_graph=((0, 1), (1, 0)),
            synthesis_hash="c" * 32,
            source_phase4_hashes=("d" * 16,),
            synthesis_type=MockSynthesisType.ADJACENCY_COLLAPSE,
            reversible=True,
            eligible=True,
        )
        result = render_phase5_to_verbalization(phase5)
        assert result.blocked is False
        assert "adjacency_connections: 2" in result.output


# =============================================================================
# GROUP G: FORBIDDEN CONTENT DETECTION
# =============================================================================

class TestGroupG_ForbiddenContent:
    """Group G: Forbidden content detection tests."""

    def test_all_forbidden_patterns_exist(self):
        """G.1: All expected forbidden patterns are defined."""
        assert "emotion" in FORBIDDEN_CONTENT_PATTERNS
        assert "intent" in FORBIDDEN_CONTENT_PATTERNS
        assert "meaning" in FORBIDDEN_CONTENT_PATTERNS
        assert "word" in FORBIDDEN_CONTENT_PATTERNS
        assert "probability" in FORBIDDEN_CONTENT_PATTERNS
        assert "varna" in FORBIDDEN_CONTENT_PATTERNS

    def test_verify_rejects_emotion_words(self):
        """G.2: Verify rejects emotion words."""
        for word in ["sad", "happy", "joy", "fear", "angry"]:
            bad_output = f"STRUCTURAL_REPORT\nunits_total: 1\n{word}"
            assert verify_output(bad_output) is False

    def test_verify_rejects_intent_words(self):
        """G.3: Verify rejects intent words."""
        for word in ["intent", "purpose", "goal", "desire"]:
            bad_output = f"STRUCTURAL_REPORT\n{word}\nunits_total: 1"
            assert verify_output(bad_output) is False

    def test_verify_rejects_meaning_words(self):
        """G.4: Verify rejects meaning words."""
        for word in ["meaning", "represents", "symbolizes"]:
            bad_output = f"STRUCTURAL_REPORT\nunits_total: 1\n{word}"
            assert verify_output(bad_output) is False

    def test_verify_rejects_language_words(self):
        """G.5: Verify rejects language words."""
        for word in ["word", "sentence", "english", "sanskrit"]:
            bad_output = f"STRUCTURAL_REPORT\n{word}"
            assert verify_output(bad_output) is False

    def test_verify_rejects_probability_words(self):
        """G.6: Verify rejects probability words."""
        for word in ["probability", "confidence", "likelihood"]:
            bad_output = f"STRUCTURAL_REPORT\n{word}"
            assert verify_output(bad_output) is False

    def test_verify_rejects_varna_words(self):
        """G.7: Verify rejects varna/varṇa words."""
        for word in ["varna", "akshara", "akshar"]:
            bad_output = f"STRUCTURAL_REPORT\n{word}"
            assert verify_output(bad_output) is False

    def test_allowed_synthesis_types_complete(self):
        """G.8: All synthesis types are allowed."""
        assert "STRUCTURAL_FOLD" in ALLOWED_SYNTHESIS_TYPE_ENUMS
        assert "ADJACENCY_COLLAPSE" in ALLOWED_SYNTHESIS_TYPE_ENUMS
        assert "RULE_VECTOR_MERGE" in ALLOWED_SYNTHESIS_TYPE_ENUMS
        assert "ELIGIBILITY_BLOCK" in ALLOWED_SYNTHESIS_TYPE_ENUMS


# =============================================================================
# RED-FLAG TESTS: Critical Failures
# =============================================================================

class TestRedFlags_CriticalFailures:
    """Red-Flag Tests: Critical security and invariant failures."""

    def test_rf1_no_user_input_echo(self, single_unit_result):
        """RF.1: Output never echoes user input (source hashes only)."""
        result = render_phase5_to_verbalization(single_unit_result)
        # Verify no raw hash values appear (they should be counted, not echoed)
        assert "a" * 16 not in result.output  # unit_hash
        assert "b" * 32 not in result.output  # synthesis_hash
        assert "c" * 16 not in result.output  # source_phase4_hash

    def test_rf2_no_free_text_generation(self, single_unit_result):
        """RF.2: No free text generation - only template tokens."""
        result = render_phase5_to_verbalization(single_unit_result)
        # All lines must match expected patterns
        lines = result.output.split('\n')
        for line in lines:
            # Each line must start with an allowed label or be pure data
            has_allowed_prefix = any(
                line.startswith(label) for label in [
                    "STRUCTURAL_REPORT",
                    "units_total",
                    "units_eligible",
                    "groups",
                    "group_sizes",
                    "rule_vector_totals",
                    "adjacency_connections",
                    "synthesis_type",
                    "reversible",
                    "eligible",
                ]
            )
            assert has_allowed_prefix, f"Invalid line: {line}"

    def test_rf3_fail_closed_on_extraction_error(self):
        """RF.3: Fail closed on extraction error."""
        # Object with missing fields
        class BrokenPhase5:
            synthesis_units = None  # Will cause error
            synthesis_graph = ()
            synthesis_type = MockSynthesisType.STRUCTURAL_FOLD
            reversible = True
            eligible = True

        result = render_phase5_to_verbalization(BrokenPhase5())
        assert result.blocked is True
        assert result.output == RENDER_BLOCKED

    def test_rf4_no_semantic_inference(self, single_unit_result):
        """RF.4: No semantic inference in output."""
        result = render_phase5_to_verbalization(single_unit_result)
        # No natural language phrases
        forbidden_phrases = [
            "the",
            "is",
            "are",
            "has",
            "have",
            "this",
            "that",
            "which",
            "because",
            "therefore",
        ]
        output_lower = result.output.lower()
        for phrase in forbidden_phrases:
            # Check phrase doesn't appear as standalone word
            assert f" {phrase} " not in output_lower

    def test_rf5_no_probability_or_confidence(self, single_unit_result):
        """RF.5: No probability or confidence scores."""
        result = render_phase5_to_verbalization(single_unit_result)
        # No floating point numbers
        import re
        floats = re.findall(r'\d+\.\d+', result.output)
        assert len(floats) == 0, f"Found floats: {floats}"
        # No percentage signs
        assert '%' not in result.output

    def test_rf6_no_timestamps_or_uuids(self, single_unit_result):
        """RF.6: No timestamps or UUIDs in output."""
        result = render_phase5_to_verbalization(single_unit_result)
        # No ISO timestamps
        import re
        timestamps = re.findall(r'\d{4}-\d{2}-\d{2}', result.output)
        assert len(timestamps) == 0
        # No UUID patterns
        uuids = re.findall(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', result.output)
        assert len(uuids) == 0

    def test_rf7_blocked_result_exact_string(self):
        """RF.7: Blocked result is exactly RENDER_BLOCKED."""
        result = render_phase5_to_verbalization(None)
        assert result.output == "RENDER_BLOCKED"
        assert result.output == RENDER_BLOCKED  # Constant comparison

    def test_rf8_invalid_synthesis_type_blocks(self):
        """RF.8: Invalid synthesis type causes block."""
        class InvalidSynthesisType(Enum):
            UNKNOWN = "unknown"

        unit = MockPhase5SynthesisUnit(
            source_indices=(0,),
            aggregated_rule_vector=(1,),
            adjacency_signature=(0,),
            modifier_density=0,
            eligibility_mask=(True,),
            unit_hash="a" * 16,
        )

        class BadPhase5:
            synthesis_units = (unit,)
            synthesis_graph = ((0,),)
            synthesis_type = InvalidSynthesisType.UNKNOWN
            reversible = True
            eligible = True

        result = render_phase5_to_verbalization(BadPhase5())
        assert result.blocked is True
        assert result.output == RENDER_BLOCKED


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests with real Phase5 structures."""

    def test_full_pipeline_single_unit(self, single_unit_result):
        """INT.1: Full pipeline with single unit."""
        result = render_phase5_to_verbalization(single_unit_result)
        assert result.blocked is False
        assert "STRUCTURAL_REPORT" in result.output
        assert "units_total: 1" in result.output
        assert "synthesis_type: STRUCTURAL_FOLD" in result.output

    def test_full_pipeline_multi_unit(self, multi_unit_result):
        """INT.2: Full pipeline with multiple units."""
        result = render_phase5_to_verbalization(multi_unit_result)
        assert result.blocked is False
        assert "units_total: 3" in result.output
        assert "groups: 3" in result.output
        assert "synthesis_type: ADJACENCY_COLLAPSE" in result.output

    def test_full_pipeline_empty_units(self, empty_units_result):
        """INT.3: Full pipeline with empty units."""
        result = render_phase5_to_verbalization(empty_units_result)
        assert result.blocked is False
        assert "units_total: 0" in result.output
        assert "groups: 0" in result.output

    def test_round_trip_data_preservation(self, multi_unit_result):
        """INT.4: VC data extraction preserves structural counts."""
        data = extract_vc_data(multi_unit_result)

        # Verify counts match manual calculation
        assert data.units_total == len(multi_unit_result.synthesis_units)

        # Verify group sizes match source_indices lengths
        expected_sizes = tuple(
            len(u.source_indices) for u in multi_unit_result.synthesis_units
        )
        assert data.group_sizes == expected_sizes


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
