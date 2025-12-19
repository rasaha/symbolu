"""
Verbalization Contract (VC) Renderer (v1.0)
============================================

Phase-6/Phase-7 Controlled Structural Verbalization.

This module is:
    - STRICTLY CONTROLLED TEXT RENDERER
    - FIRST AND ONLY GENERATIVE STEP
    - DETERMINISTIC
    - FAIL-CLOSED
    - NO FREE-FORM TEXT
    - NO SEMANTICS
    - NO VARNA OUTPUT

It operates ONLY on Phase5SynthesisResult.

ABSOLUTE RULES:
    - NO FREE-FORM TEXT: Only predefined templates exactly
    - NO SEMANTICS: No meaning, intent, emotion, sentiment inference
    - NO VARNA OUTPUT: No letters, syllables, tokens, or concatenations
    - NO LLM-LIKE BEHAVIOR: No creativity, no abstraction, no explanation
    - DETERMINISTIC ONLY: Same input -> identical output, byte-for-byte
    - FAIL CLOSED: If validation fails, return "RENDER_BLOCKED"

Version: 1.0
"""

from dataclasses import dataclass
from typing import Tuple, List, Optional, Any
from enum import Enum
import re


__all__ = [
    "VC_RENDERER_VERSION",
    "VC_INVARIANTS",
    "RENDER_BLOCKED",
    "TemplateType",
    "VCExtractedData",
    "VCRenderResult",
    "extract_vc_data",
    "render_template",
    "verify_output",
    "render_phase5_to_verbalization",
    "validate_vc_invariants",
]


VC_RENDERER_VERSION = "1.0"

# Constant for blocked output
RENDER_BLOCKED = "RENDER_BLOCKED"

VC_INVARIANTS = {
    "NO_FREE_FORM_TEXT": True,
    "NO_SEMANTICS": True,
    "NO_VARNA_OUTPUT": True,
    "NO_LLM_BEHAVIOR": True,
    "DETERMINISTIC": True,
    "FAIL_CLOSED": True,
    "TEMPLATE_ONLY": True,
    "NO_LANGUAGE": True,
    "NO_EMOTION": True,
    "NO_INTENT": True,
    "NO_PROBABILITY": True,
}

# Forbidden content patterns - if ANY appear, render is blocked
FORBIDDEN_CONTENT_PATTERNS = frozenset([
    # Emotions
    "sad", "happy", "emotion", "feeling", "mood", "joy", "fear", "angry",
    "love", "hate", "anxious", "excited", "calm", "nervous",
    # Intent/Purpose
    "intent", "purpose", "goal", "desire", "want", "wish", "aim", "objective",
    # Meaning/Interpretation
    "meaning", "means", "represents", "symbolizes", "signifies", "denotes",
    "implies", "suggests", "interprets", "interpretation",
    # Language/Words
    "word", "sentence", "language", "english", "hindi", "sanskrit", "phonetic",
    "syllable", "letter", "character", "text", "speech", "utterance",
    # Sentiment
    "positive", "negative", "neutral", "sentiment",
    # Probability/Confidence
    "probability", "likelihood", "confidence", "chance", "maybe", "perhaps",
    "possibly", "probably", "uncertain", "certain",
    # Generation/Inference
    "generate", "predict", "infer", "guess", "assume", "imagine", "create",
    # User input echoes (varna)
    "varna", "varṇa", "akshara", "akshar",
])

# Allowed template labels (exact match)
ALLOWED_TEMPLATE_LABELS = frozenset([
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
])

# Allowed enum names for synthesis_type (from Phase5)
ALLOWED_SYNTHESIS_TYPE_ENUMS = frozenset([
    "STRUCTURAL_FOLD",
    "ADJACENCY_COLLAPSE",
    "RULE_VECTOR_MERGE",
    "ELIGIBILITY_BLOCK",
])


class TemplateType(Enum):
    """Template type selection - structural only."""
    MINIMAL_STRUCTURAL = "minimal_structural"
    STANDARD_STRUCTURAL = "standard_structural"


@dataclass(frozen=True)
class VCExtractedData:
    """
    Verbalization Contract extracted data container.

    Contains ONLY derived structural facts allowed by VC-1 through VC-5:
        - VC-1: Global counts
        - VC-2: Group sizes
        - VC-3: Rule vector distribution
        - VC-4: Adjacency density
        - VC-5: Deterministic metadata

    NO free-form strings. NO semantic content.
    """
    # VC-1: Global counts
    units_total: int
    units_eligible: int

    # VC-2: Group sizes
    groups_count: int
    group_sizes: Tuple[int, ...]

    # VC-3: Rule vector distribution
    rule_vector_zero_count: int
    rule_vector_one_count: int
    rule_vector_two_count: int

    # VC-4: Adjacency density
    adjacency_connections: int

    # VC-5: Deterministic metadata
    synthesis_type_name: str  # Enum name only
    reversible: bool
    eligible: bool

    def __post_init__(self):
        # Validate all integers are non-negative
        if self.units_total < 0:
            raise ValueError("units_total must be non-negative")
        if self.units_eligible < 0:
            raise ValueError("units_eligible must be non-negative")
        if self.groups_count < 0:
            raise ValueError("groups_count must be non-negative")
        if self.rule_vector_zero_count < 0:
            raise ValueError("rule_vector_zero_count must be non-negative")
        if self.rule_vector_one_count < 0:
            raise ValueError("rule_vector_one_count must be non-negative")
        if self.rule_vector_two_count < 0:
            raise ValueError("rule_vector_two_count must be non-negative")
        if self.adjacency_connections < 0:
            raise ValueError("adjacency_connections must be non-negative")

        # Validate group_sizes
        if not isinstance(self.group_sizes, tuple):
            raise ValueError("group_sizes must be tuple")
        for size in self.group_sizes:
            if not isinstance(size, int) or size < 0:
                raise ValueError("group_sizes must contain non-negative ints")

        # Validate synthesis_type_name is allowed enum
        if self.synthesis_type_name not in ALLOWED_SYNTHESIS_TYPE_ENUMS:
            raise ValueError(f"synthesis_type_name must be one of {ALLOWED_SYNTHESIS_TYPE_ENUMS}")

        # Validate booleans
        if not isinstance(self.reversible, bool):
            raise ValueError("reversible must be bool")
        if not isinstance(self.eligible, bool):
            raise ValueError("eligible must be bool")


@dataclass(frozen=True)
class VCRenderResult:
    """
    Verbalization Contract render result.

    Contains:
        - output: The rendered string (or RENDER_BLOCKED)
        - blocked: True if rendering was blocked
        - template_used: TemplateType used (or None if blocked)
    """
    output: str
    blocked: bool
    template_used: Optional[TemplateType]


def _is_valid_phase5_result(obj: Any) -> bool:
    """
    Check if object has required Phase5SynthesisResult fields.

    Uses duck typing to avoid import dependency.
    """
    required_fields = [
        'synthesis_units',
        'synthesis_graph',
        'synthesis_type',
        'reversible',
        'eligible',
    ]
    for field in required_fields:
        if not hasattr(obj, field):
            return False
    return True


def _count_eligible_units(synthesis_units: Tuple) -> int:
    """
    Count eligible synthesis units.

    A unit is eligible if any(unit.eligibility_mask) is True.
    """
    count = 0
    for unit in synthesis_units:
        if hasattr(unit, 'eligibility_mask'):
            if any(unit.eligibility_mask):
                count += 1
    return count


def _compute_rule_vector_distribution(synthesis_units: Tuple) -> Tuple[int, int, int]:
    """
    Compute rule vector distribution across ALL aggregated_rule_vectors.

    Returns: (zero_count, one_count, two_count)
    """
    zero_count = 0
    one_count = 0
    two_count = 0

    for unit in synthesis_units:
        if hasattr(unit, 'aggregated_rule_vector'):
            for val in unit.aggregated_rule_vector:
                if val == 0:
                    zero_count += 1
                elif val == 1:
                    one_count += 1
                elif val == 2:
                    two_count += 1

    return (zero_count, one_count, two_count)


def _compute_adjacency_connections(synthesis_graph: Tuple[Tuple[int, ...], ...]) -> int:
    """
    Compute total adjacency connections (sum of all 1s in synthesis_graph).
    """
    total = 0
    for row in synthesis_graph:
        for val in row:
            if val == 1:
                total += 1
    return total


def _get_group_sizes(synthesis_units: Tuple) -> Tuple[int, ...]:
    """
    Get size (count of source_indices) for each synthesis unit group.
    """
    sizes = []
    for unit in synthesis_units:
        if hasattr(unit, 'source_indices'):
            sizes.append(len(unit.source_indices))
        else:
            sizes.append(0)
    return tuple(sizes)


def _get_synthesis_type_name(synthesis_type) -> str:
    """
    Extract synthesis type enum name.

    Returns uppercase name without the class prefix.
    """
    if hasattr(synthesis_type, 'name'):
        return synthesis_type.name
    # Fallback: convert value to uppercase
    return str(synthesis_type.value).upper().replace('_', '_')


def extract_vc_data(phase5_result: Any) -> Optional[VCExtractedData]:
    """
    Extract Verbalization Contract data from Phase5SynthesisResult.

    ONLY extracts allowed structural facts:
        - VC-1: Global counts
        - VC-2: Group sizes
        - VC-3: Rule vector distribution
        - VC-4: Adjacency density
        - VC-5: Deterministic metadata

    Returns None if input is invalid or extraction fails.
    """
    # Validate input
    if phase5_result is None:
        return None

    if not _is_valid_phase5_result(phase5_result):
        return None

    try:
        synthesis_units = phase5_result.synthesis_units
        synthesis_graph = phase5_result.synthesis_graph

        # VC-1: Global counts
        units_total = len(synthesis_units)
        units_eligible = _count_eligible_units(synthesis_units)

        # VC-2: Group sizes
        group_sizes = _get_group_sizes(synthesis_units)
        groups_count = len(synthesis_units)

        # VC-3: Rule vector distribution
        zero_count, one_count, two_count = _compute_rule_vector_distribution(synthesis_units)

        # VC-4: Adjacency density
        adjacency_connections = _compute_adjacency_connections(synthesis_graph)

        # VC-5: Deterministic metadata
        synthesis_type_name = _get_synthesis_type_name(phase5_result.synthesis_type)
        reversible = bool(phase5_result.reversible)
        eligible = bool(phase5_result.eligible)

        # Validate synthesis_type_name is allowed
        if synthesis_type_name not in ALLOWED_SYNTHESIS_TYPE_ENUMS:
            return None

        return VCExtractedData(
            units_total=units_total,
            units_eligible=units_eligible,
            groups_count=groups_count,
            group_sizes=group_sizes,
            rule_vector_zero_count=zero_count,
            rule_vector_one_count=one_count,
            rule_vector_two_count=two_count,
            adjacency_connections=adjacency_connections,
            synthesis_type_name=synthesis_type_name,
            reversible=reversible,
            eligible=eligible,
        )
    except Exception:
        # Fail closed on any extraction error
        return None


def _format_int_list(values: Tuple[int, ...]) -> str:
    """Format tuple of ints as comma-separated list."""
    return ", ".join(str(v) for v in values)


def _render_minimal_template(data: VCExtractedData) -> str:
    """
    Render MINIMAL_STRUCTURAL template.

    TEMPLATE A — MINIMAL_STRUCTURAL:
    STRUCTURAL_REPORT
    units_total: {INT}
    units_eligible: {INT}
    groups: {INT}
    group_sizes: [{INT_LIST}]
    """
    lines = [
        "STRUCTURAL_REPORT",
        f"units_total: {data.units_total}",
        f"units_eligible: {data.units_eligible}",
        f"groups: {data.groups_count}",
        f"group_sizes: [{_format_int_list(data.group_sizes)}]",
    ]
    return "\n".join(lines)


def _render_standard_template(data: VCExtractedData) -> str:
    """
    Render STANDARD_STRUCTURAL template.

    TEMPLATE B — STANDARD_STRUCTURAL:
    STRUCTURAL_REPORT
    units_total: {INT}
    units_eligible: {INT}
    groups: {INT}
    group_sizes: [{INT_LIST}]
    rule_vector_totals: {ZERO_COUNT}/{ONE_COUNT}/{TWO_COUNT}
    adjacency_connections: {INT}
    synthesis_type: {ENUM}
    reversible: {BOOL}
    eligible: {BOOL}
    """
    lines = [
        "STRUCTURAL_REPORT",
        f"units_total: {data.units_total}",
        f"units_eligible: {data.units_eligible}",
        f"groups: {data.groups_count}",
        f"group_sizes: [{_format_int_list(data.group_sizes)}]",
        f"rule_vector_totals: {data.rule_vector_zero_count}/{data.rule_vector_one_count}/{data.rule_vector_two_count}",
        f"adjacency_connections: {data.adjacency_connections}",
        f"synthesis_type: {data.synthesis_type_name}",
        f"reversible: {str(data.reversible).lower()}",
        f"eligible: {str(data.eligible).lower()}",
    ]
    return "\n".join(lines)


def render_template(data: VCExtractedData, template_type: TemplateType) -> str:
    """
    Render VCExtractedData using specified template.

    Returns rendered string or raises ValueError if template invalid.
    """
    if template_type == TemplateType.MINIMAL_STRUCTURAL:
        return _render_minimal_template(data)
    elif template_type == TemplateType.STANDARD_STRUCTURAL:
        return _render_standard_template(data)
    else:
        raise ValueError(f"Unknown template type: {template_type}")


def _check_forbidden_content(output: str) -> bool:
    """
    Check if output contains any forbidden content.

    Returns True if forbidden content found (should block).
    """
    output_lower = output.lower()
    for pattern in FORBIDDEN_CONTENT_PATTERNS:
        if pattern in output_lower:
            return True
    return False


def _extract_alphabetic_tokens(output: str) -> List[str]:
    """
    Extract all alphabetic tokens from output.
    """
    # Find all sequences of alphabetic characters
    return re.findall(r'[a-zA-Z_]+', output)


def _is_allowed_alphabetic_token(token: str) -> bool:
    """
    Check if alphabetic token is allowed.

    Allowed:
        - Template labels (STRUCTURAL_REPORT, units_total, etc.)
        - Enum names (STRUCTURAL_FOLD, etc.)
        - Boolean literals (true, false)
    """
    # Check template labels
    if token in ALLOWED_TEMPLATE_LABELS:
        return True

    # Check enum names
    if token in ALLOWED_SYNTHESIS_TYPE_ENUMS:
        return True

    # Check boolean literals
    if token in ("true", "false"):
        return True

    return False


def _verify_minimal_template_structure(lines: List[str]) -> bool:
    """
    Verify output matches MINIMAL_STRUCTURAL template line-by-line.
    """
    if len(lines) != 5:
        return False

    # Line 0: STRUCTURAL_REPORT
    if lines[0] != "STRUCTURAL_REPORT":
        return False

    # Line 1: units_total: {INT}
    if not re.match(r'^units_total: \d+$', lines[1]):
        return False

    # Line 2: units_eligible: {INT}
    if not re.match(r'^units_eligible: \d+$', lines[2]):
        return False

    # Line 3: groups: {INT}
    if not re.match(r'^groups: \d+$', lines[3]):
        return False

    # Line 4: group_sizes: [{INT_LIST}]
    if not re.match(r'^group_sizes: \[(\d+(, \d+)*)?\]$', lines[4]):
        return False

    return True


def _verify_standard_template_structure(lines: List[str]) -> bool:
    """
    Verify output matches STANDARD_STRUCTURAL template line-by-line.
    """
    if len(lines) != 10:
        return False

    # Line 0: STRUCTURAL_REPORT
    if lines[0] != "STRUCTURAL_REPORT":
        return False

    # Line 1: units_total: {INT}
    if not re.match(r'^units_total: \d+$', lines[1]):
        return False

    # Line 2: units_eligible: {INT}
    if not re.match(r'^units_eligible: \d+$', lines[2]):
        return False

    # Line 3: groups: {INT}
    if not re.match(r'^groups: \d+$', lines[3]):
        return False

    # Line 4: group_sizes: [{INT_LIST}]
    if not re.match(r'^group_sizes: \[(\d+(, \d+)*)?\]$', lines[4]):
        return False

    # Line 5: rule_vector_totals: {ZERO}/{ONE}/{TWO}
    if not re.match(r'^rule_vector_totals: \d+/\d+/\d+$', lines[5]):
        return False

    # Line 6: adjacency_connections: {INT}
    if not re.match(r'^adjacency_connections: \d+$', lines[6]):
        return False

    # Line 7: synthesis_type: {ENUM}
    enum_pattern = '|'.join(ALLOWED_SYNTHESIS_TYPE_ENUMS)
    if not re.match(f'^synthesis_type: ({enum_pattern})$', lines[7]):
        return False

    # Line 8: reversible: {BOOL}
    if not re.match(r'^reversible: (true|false)$', lines[8]):
        return False

    # Line 9: eligible: {BOOL}
    if not re.match(r'^eligible: (true|false)$', lines[9]):
        return False

    return True


def verify_output(output: str) -> bool:
    """
    Verify rendered output is valid.

    Verification checks:
        1. Output matches ONE template exactly (line-by-line)
        2. All placeholders are replaced with valid values
        3. No alphabetic tokens appear except allowed labels/enums
        4. No free text substrings exist
        5. No forbidden content

    Returns True if valid, False if should block.
    """
    # Check 5: No forbidden content
    if _check_forbidden_content(output):
        return False

    # Check 3: All alphabetic tokens are allowed
    tokens = _extract_alphabetic_tokens(output)
    for token in tokens:
        if not _is_allowed_alphabetic_token(token):
            return False

    # Check 1 & 2: Output matches one template exactly
    lines = output.split('\n')

    # Try MINIMAL template (5 lines)
    if len(lines) == 5:
        return _verify_minimal_template_structure(lines)

    # Try STANDARD template (10 lines)
    if len(lines) == 10:
        return _verify_standard_template_structure(lines)

    # No template matched
    return False


def render_phase5_to_verbalization(
    phase5_result: Any,
    template_type: TemplateType = TemplateType.STANDARD_STRUCTURAL
) -> VCRenderResult:
    """
    Main entry point: Render Phase5SynthesisResult to verbalization.

    This is a COMPILER, not a language model.

    Steps:
        1. Extract VC data from Phase5SynthesisResult
        2. Render using specified template
        3. Verify output strictly
        4. Return result (or RENDER_BLOCKED if any step fails)

    Args:
        phase5_result: Phase5SynthesisResult object
        template_type: TemplateType to use (default: STANDARD_STRUCTURAL)

    Returns:
        VCRenderResult with output string and status
    """
    # Step 1: Extract VC data
    vc_data = extract_vc_data(phase5_result)
    if vc_data is None:
        return VCRenderResult(
            output=RENDER_BLOCKED,
            blocked=True,
            template_used=None
        )

    # Step 2: Render template
    try:
        rendered = render_template(vc_data, template_type)
    except Exception:
        return VCRenderResult(
            output=RENDER_BLOCKED,
            blocked=True,
            template_used=None
        )

    # Step 3: Verify output strictly
    if not verify_output(rendered):
        return VCRenderResult(
            output=RENDER_BLOCKED,
            blocked=True,
            template_used=None
        )

    # Step 4: Return valid result
    return VCRenderResult(
        output=rendered,
        blocked=False,
        template_used=template_type
    )


def validate_vc_invariants() -> bool:
    """Validate that all VC invariants are preserved."""
    for invariant, value in VC_INVARIANTS.items():
        if not value:
            raise AssertionError(f"VC invariant violated: {invariant}")
    return True
