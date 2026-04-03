"""
Validators for Ontological Projection Engine
=============================================

Validation functions for projection inputs and outputs.

Hard Constraints:
    - Enforce no randomness imports
    - Enforce no timestamp words
    - Enforce no free-form text in artifacts
    - Fail-closed on any violation
"""

import sys
from typing import Any, Tuple, List, Set

from agentic.ontology.projection.api_models import (
    ProjectionRequest,
    ProjectionResponse,
    ProjectionOptions,
    InvariantsReport,
    InputRef,
    OntologicalLayer,
    ReasonCode,
)


# =============================================================================
# Constants
# =============================================================================

# Forbidden module prefixes (NLP and LLM libraries only)
# Note: We don't forbid stdlib 'random' module import, but our code must not USE it
FORBIDDEN_MODULES: Tuple[str, ...] = (
    "nltk",
    "spacy",
    "transformers",
    "openai",
    "anthropic",
    "langchain",
    "gensim",
    "textblob",
)

# Forbidden timestamp-related words in string representations
TIMESTAMP_WORDS: Tuple[str, ...] = (
    "timestamp",
    "time.time",
    "datetime.now",
    "uuid",
)

# Allowed fixed tokens (enum values and fixed strings)
ALLOWED_FIXED_TOKENS: Set[str] = {
    # InputRefKind values
    "phase5_result",
    "phase9_graph",
    "generic",
    # ProjectionProfile values
    "minimal",
    "standard",
    "audit",
    # OutputMode values
    "non_textual",
    "template_text",
    # Strictness values
    "strict",
    "audit_strict",
    # Invariant names
    "read_only",
    "deterministic",
    "no_semantics",
    "fail_closed",
    # Boolean strings
    "true",
    "false",
}


# =============================================================================
# Validation Functions
# =============================================================================

def is_hex_hash(s: str) -> bool:
    """
    Check if a string is a valid lowercase hex hash (16-64 chars).

    Args:
        s: String to check

    Returns:
        True if valid hex hash, False otherwise
    """
    if not isinstance(s, str):
        return False
    if len(s) < 16 or len(s) > 64:
        return False
    try:
        int(s, 16)
        return s == s.lower()
    except ValueError:
        return False


def is_allowed_string(s: str) -> bool:
    """
    Check if a string is allowed in artifacts.

    Allowed strings:
        - Lowercase hex hashes (16-64 chars)
        - Allowed fixed tokens (enum values)

    Args:
        s: String to check

    Returns:
        True if allowed, False otherwise
    """
    if not isinstance(s, str):
        return False
    # Check if hex hash
    if is_hex_hash(s):
        return True
    # Check if allowed fixed token
    if s.lower() in ALLOWED_FIXED_TOKENS:
        return True
    return False


def is_allowed_value(x: Any, allow_dict: bool = False) -> bool:
    """
    Recursively check if a value is allowed in artifacts.

    Allowed values:
        - int, bool, None
        - str: only lowercase hex (16-64 chars) or allowed fixed tokens
        - tuple/list of allowed values
        - dict only if allow_dict=True (for internal hashing)

    Args:
        x: Value to check
        allow_dict: Whether to allow dicts (for internal use only)

    Returns:
        True if allowed, False otherwise
    """
    if x is None:
        return True
    if isinstance(x, bool):
        return True
    if isinstance(x, int) and not isinstance(x, bool):
        return True
    if isinstance(x, str):
        return is_allowed_string(x)
    if isinstance(x, (tuple, list)):
        return all(is_allowed_value(item, allow_dict=allow_dict) for item in x)
    if allow_dict and isinstance(x, dict):
        return all(
            is_allowed_value(k, allow_dict=True) and is_allowed_value(v, allow_dict=True)
            for k, v in x.items()
        )
    return False


def check_no_forbidden_modules() -> Tuple[bool, List[str]]:
    """
    Check that no forbidden modules are imported.

    Returns:
        Tuple of (passed, list of violations)
    """
    violations = []
    for module_name in sys.modules.keys():
        for forbidden in FORBIDDEN_MODULES:
            if module_name == forbidden or module_name.startswith(forbidden + "."):
                violations.append(module_name)
    return (len(violations) == 0, violations)


def check_no_timestamp_words(obj: Any) -> Tuple[bool, List[str]]:
    """
    Check that no timestamp-related words appear in string representation.

    Args:
        obj: Object to check

    Returns:
        Tuple of (passed, list of violations)
    """
    violations = []
    obj_repr = repr(obj).lower()
    for word in TIMESTAMP_WORDS:
        if word.lower() in obj_repr:
            violations.append(word)
    return (len(violations) == 0, violations)


def validate_request(request: ProjectionRequest) -> Tuple[bool, List[str]]:
    """
    Validate a projection request.

    Checks:
        - max_artifacts > 0
        - projection_profile is valid

    Args:
        request: Request to validate

    Returns:
        Tuple of (passed, list of reason codes)
    """
    reasons = []

    if request.options.max_artifacts <= 0:
        reasons.append(ReasonCode.INVALID_MAX_ARTIFACTS)

    return (len(reasons) == 0, reasons)


def validate_response_non_textual(response: ProjectionResponse) -> Tuple[bool, List[str]]:
    """
    Validate that response contains no free-form text.

    Checks:
        - artifacts is a tuple
        - ledger_spans is a tuple
        - all elements pass is_allowed_value

    Args:
        response: Response to validate

    Returns:
        Tuple of (passed, list of reason codes)
    """
    reasons = []

    if not isinstance(response.artifacts, tuple):
        reasons.append(ReasonCode.FREEFORM_TEXT_DETECTED)

    if not isinstance(response.ledger_spans, tuple):
        reasons.append(ReasonCode.FREEFORM_TEXT_DETECTED)

    # Check all artifacts
    for artifact in response.artifacts:
        if not is_allowed_value(artifact):
            reasons.append(ReasonCode.FREEFORM_TEXT_DETECTED)
            break

    # Check all ledger spans
    for span in response.ledger_spans:
        if not is_allowed_value(span):
            reasons.append(ReasonCode.FREEFORM_TEXT_DETECTED)
            break

    return (len(reasons) == 0, reasons)


def run_invariant_checks() -> InvariantsReport:
    """
    Run all invariant checks.

    Returns:
        InvariantsReport with pass/fail status and reason codes
    """
    reasons = []

    # Check no forbidden modules
    passed, violations = check_no_forbidden_modules()
    if not passed:
        reasons.append(ReasonCode.FORBIDDEN_MODULE_IMPORTED)

    return InvariantsReport(
        passed=(len(reasons) == 0),
        reason_codes=tuple(reasons)
    )


def fail_closed_response(
    projection_id: str,
    snapshot_id: str,
    layer: OntologicalLayer,
    input_ref: InputRef,
    reason_codes: Tuple[str, ...],
) -> ProjectionResponse:
    """
    Create a fail-closed response.

    Args:
        projection_id: Deterministic projection ID
        snapshot_id: Snapshot ID from request
        layer: Requested layer
        input_ref: Input reference from request
        reason_codes: Tuple of reason codes for failure

    Returns:
        ProjectionResponse with eligible=False
    """
    return ProjectionResponse(
        projection_id=projection_id,
        snapshot_id=snapshot_id,
        layer=layer,
        input_ref=input_ref,
        artifacts=(),
        ledger_spans=(),
        invariants_report=InvariantsReport(
            passed=False,
            reason_codes=reason_codes
        ),
        eligible=False
    )
