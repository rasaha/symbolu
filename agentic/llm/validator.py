"""
Symbol-U LLM Contract Validator
===============================

Deterministic validation of LLM responses against the Symbol-U ↔ LLM
Interface Contract.

Contract: docs/contracts/SYMBOLU_LLM_INTERFACE_CONTRACT.md

Invariants enforced:
- INV-1: Determinism envelope
- INV-2: No new tokens
- INV-3: No new layers
- INV-4: No constraint mutation
- INV-5: No governance override
- INV-6: One-way boundary
- INV-7: Provenance integrity
"""

# ---------------------------------------------------------------------------
# MIGRATION MIRROR — DO NOT DRIFT
# ---------------------------------------------------------------------------
# This file is one half of an intentional migration mirror. An identical
# (or namespace-identical) copy lives at the other root:
#   symbolu/llm/*   <->   agentic/llm/*
# Production runtime runs through `symbolu/llm/*` today (see nixpacks.toml
# -> `symbolu.service.api_server:create_app`). The extraction target is
# `agentic/llm/*` (see commit 654b3b8). Both copies must stay in sync
# until the migration completes.
# Drift guard: tests/test_llm_mirror_drift.py
# ---------------------------------------------------------------------------

import re
from typing import List, Tuple, Optional

from agentic.llm.types import (
    RenderRequest,
    RenderResponse,
    ContractViolation,
    ContractViolationType,
    ValidationResult,
)


# =============================================================================
# Forbidden Patterns (from contract Section 14)
# =============================================================================

# Override patterns (FM-4: Governance override)
OVERRIDE_PATTERNS: Tuple[re.Pattern, ...] = (
    re.compile(r"ignore\s+(the\s+)?constraint", re.IGNORECASE),
    re.compile(r"override\s+(the\s+)?", re.IGNORECASE),
    re.compile(r"bypass\s+(the\s+)?", re.IGNORECASE),
    re.compile(r"skip\s+(the\s+)?validation", re.IGNORECASE),
    re.compile(r"disable\s+(the\s+)?", re.IGNORECASE),
    re.compile(r"ignore\s+phase", re.IGNORECASE),
    re.compile(r"skip\s+phase", re.IGNORECASE),
    re.compile(r"bypass\s+phase", re.IGNORECASE),
)

# Selection patterns (FM-3: Selection leak)
SELECTION_PATTERNS: Tuple[re.Pattern, ...] = (
    re.compile(r"best\s+(option|choice|candidate)", re.IGNORECASE),
    re.compile(r"recommend\s+(that|this|you)", re.IGNORECASE),
    re.compile(r"should\s+(pick|select|choose)", re.IGNORECASE),
    re.compile(r"prefer\s+(this|that)", re.IGNORECASE),
    re.compile(r"rank(ed|ing)?\s+(by|as)", re.IGNORECASE),
    re.compile(r"optimal\s+(choice|option|sequence)", re.IGNORECASE),
)

# Authority claim patterns (FM-2: Structure addition)
AUTHORITY_PATTERNS: Tuple[re.Pattern, ...] = (
    re.compile(r"i\s+(think|believe|suggest)\s+", re.IGNORECASE),
    re.compile(r"in\s+my\s+(opinion|view)", re.IGNORECASE),
    re.compile(r"based\s+on\s+my\s+(analysis|judgment)", re.IGNORECASE),
)

# Structure invention patterns (FM-2: Structure addition)
STRUCTURE_PATTERNS: Tuple[re.Pattern, ...] = (
    re.compile(r"new\s+(constraint|layer|token|rule)", re.IGNORECASE),
    re.compile(r"additional\s+(constraint|requirement)", re.IGNORECASE),
    re.compile(r"should\s+(add|include|have)\s+(a\s+)?(new|additional)", re.IGNORECASE),
)

# Layer reference pattern (for detecting layer mentions)
LAYER_PATTERN: re.Pattern = re.compile(r"O\d+[_A-Z]*|layer\s*\d+", re.IGNORECASE)


# =============================================================================
# Individual Validators
# =============================================================================

def validate_tokens(
    request: RenderRequest,
    response: RenderResponse
) -> List[ContractViolation]:
    """
    Validate that no new tokens are introduced (INV-2).

    Checks all output content for token references not in allowed_tokens.
    """
    violations = []
    allowed = request.envelope.allowed_tokens

    if not allowed:
        # If no tokens specified in envelope, skip token validation
        return violations

    for output in response.outputs:
        content = output.content.lower()
        # Check for each allowed token - if we find tokens that aren't allowed
        # This is a simple check; production would need more sophisticated parsing
        for token in _extract_potential_tokens(content):
            if token not in allowed and token.lower() not in {t.lower() for t in allowed}:
                # Only flag if it looks like a varna token (2-3 chars, consonant patterns)
                if _is_likely_token(token):
                    violations.append(ContractViolation(
                        violation_type=ContractViolationType.NEW_TOKEN,
                        message=f"Token '{token}' not in allowed_tokens",
                        evidence=token,
                        location=f"output content"
                    ))

    return violations


def validate_layers(
    request: RenderRequest,
    response: RenderResponse
) -> List[ContractViolation]:
    """
    Validate that no new layers are introduced (INV-3).

    Checks all output content for layer references not in allowed_layers.
    """
    violations = []
    allowed = request.envelope.allowed_layers

    if not allowed:
        return violations

    for output in response.outputs:
        content = output.content
        # Find all layer-like references
        matches = LAYER_PATTERN.findall(content)
        for match in matches:
            # Normalize the match
            normalized = match.upper().replace(" ", "").replace("LAYER", "O")
            if normalized not in allowed and match.upper() not in allowed:
                violations.append(ContractViolation(
                    violation_type=ContractViolationType.NEW_LAYER,
                    message=f"Layer '{match}' not in allowed_layers",
                    evidence=match,
                    location="output content"
                ))

    return violations


def validate_forbidden_phrases(
    request: RenderRequest,
    response: RenderResponse
) -> List[ContractViolation]:
    """
    Validate that no forbidden phrases appear (INV-4, INV-5).

    Checks for override, selection, authority, and structure patterns.
    """
    violations = []

    for output in response.outputs:
        content = output.content

        # Check override patterns (FM-4)
        for pattern in OVERRIDE_PATTERNS:
            match = pattern.search(content)
            if match:
                violations.append(ContractViolation(
                    violation_type=ContractViolationType.GOVERNANCE_OVERRIDE,
                    message=f"Forbidden override phrase detected",
                    evidence=match.group(),
                    location="output content"
                ))

        # Check selection patterns (FM-3)
        for pattern in SELECTION_PATTERNS:
            match = pattern.search(content)
            if match:
                violations.append(ContractViolation(
                    violation_type=ContractViolationType.SELECTION,
                    message=f"Forbidden selection phrase detected",
                    evidence=match.group(),
                    location="output content"
                ))

        # Check authority patterns (FM-2)
        for pattern in AUTHORITY_PATTERNS:
            match = pattern.search(content)
            if match:
                violations.append(ContractViolation(
                    violation_type=ContractViolationType.STRUCTURE_ADDITION,
                    message=f"Forbidden authority claim detected",
                    evidence=match.group(),
                    location="output content"
                ))

        # Check structure patterns (FM-2)
        for pattern in STRUCTURE_PATTERNS:
            match = pattern.search(content)
            if match:
                violations.append(ContractViolation(
                    violation_type=ContractViolationType.STRUCTURE_ADDITION,
                    message=f"Forbidden structure invention phrase detected",
                    evidence=match.group(),
                    location="output content"
                ))

    return violations


def validate_provenance(
    request: RenderRequest,
    response: RenderResponse
) -> List[ContractViolation]:
    """
    Validate provenance integrity (INV-7).

    If the output references provenance hashes, they must match the original.
    """
    violations = []

    # Extract provenance hashes from request
    original_hashes = set()
    for result in request.authoritative_payload.phase7_results:
        original_hashes.add(result.provenance.phase4a_hash)

    for output in response.outputs:
        content = output.content
        # Look for SHA256-like patterns
        hash_pattern = re.compile(r"sha256:[a-f0-9]{64}|[a-f0-9]{64}", re.IGNORECASE)
        found_hashes = hash_pattern.findall(content)

        for found in found_hashes:
            # Normalize
            normalized = found.lower().replace("sha256:", "")
            # Check if it's a fabricated hash
            is_original = any(normalized in h.lower() for h in original_hashes)
            if not is_original:
                violations.append(ContractViolation(
                    violation_type=ContractViolationType.PROVENANCE_VIOLATION,
                    message=f"Provenance hash not from original data",
                    evidence=found,
                    location="output content"
                ))

    return violations


def validate_no_selection(
    request: RenderRequest,
    response: RenderResponse
) -> List[ContractViolation]:
    """
    Validate that no selection/ranking is performed (FM-3).

    Checks for patterns indicating the LLM is making selection decisions.
    """
    violations = []

    # Additional selection indicators beyond SELECTION_PATTERNS
    selection_indicators = [
        r"candidate\s*#?\d+\s+(is|would be)",
        r"(first|second|third)\s+choice",
        r"score[sd]?\s+(higher|lower|better|worse)",
        r"rank[sed]*\s+(higher|lower|first|last)",
    ]

    for output in response.outputs:
        content = output.content
        for indicator in selection_indicators:
            pattern = re.compile(indicator, re.IGNORECASE)
            match = pattern.search(content)
            if match:
                violations.append(ContractViolation(
                    violation_type=ContractViolationType.SELECTION,
                    message=f"Selection/ranking behavior detected",
                    evidence=match.group(),
                    location="output content"
                ))

    return violations


def validate_no_governance_override(
    request: RenderRequest,
    response: RenderResponse
) -> List[ContractViolation]:
    """
    Validate that no governance override is suggested (FM-4).

    Checks for patterns suggesting bypassing Symbol-U governance.
    """
    violations = []

    # Additional override indicators
    override_indicators = [
        r"don't\s+need\s+to\s+(follow|obey|respect)",
        r"can\s+safely\s+ignore",
        r"exception\s+to\s+(the\s+)?rule",
        r"workaround\s+for",
        r"get\s+around\s+(the\s+)?constraint",
    ]

    for output in response.outputs:
        content = output.content
        for indicator in override_indicators:
            pattern = re.compile(indicator, re.IGNORECASE)
            match = pattern.search(content)
            if match:
                violations.append(ContractViolation(
                    violation_type=ContractViolationType.GOVERNANCE_OVERRIDE,
                    message=f"Governance override suggestion detected",
                    evidence=match.group(),
                    location="output content"
                ))

    return violations


def validate_format(
    request: RenderRequest,
    response: RenderResponse
) -> List[ContractViolation]:
    """
    Validate format constraints (FM-5).

    Checks word count limits and mode-specific constraints.
    """
    violations = []

    max_words = request.authoritative_payload.render_hints.max_words

    for output in response.outputs:
        content = output.content
        word_count = len(content.split())

        if max_words is not None and word_count > max_words:
            violations.append(ContractViolation(
                violation_type=ContractViolationType.FORMAT_VIOLATION,
                message=f"Output exceeds max_words ({word_count} > {max_words})",
                evidence=f"word_count={word_count}",
                location="output content"
            ))

    return violations


def validate_assertions(
    response: RenderResponse
) -> List[ContractViolation]:
    """
    Validate that the LLM's self-assertions are true.

    If the LLM claims no_structure_added but we detect structure, flag it.
    """
    violations = []

    if not response.assertions.no_structure_added:
        violations.append(ContractViolation(
            violation_type=ContractViolationType.STRUCTURE_ADDITION,
            message="LLM self-reported structure addition",
            evidence="assertions.no_structure_added=False",
            location="assertions"
        ))

    if not response.assertions.no_constraints_modified:
        violations.append(ContractViolation(
            violation_type=ContractViolationType.CONSTRAINT_MODIFICATION,
            message="LLM self-reported constraint modification",
            evidence="assertions.no_constraints_modified=False",
            location="assertions"
        ))

    if not response.assertions.no_new_tokens_introduced:
        violations.append(ContractViolation(
            violation_type=ContractViolationType.NEW_TOKEN,
            message="LLM self-reported new token introduction",
            evidence="assertions.no_new_tokens_introduced=False",
            location="assertions"
        ))

    return violations


# =============================================================================
# Main Validator
# =============================================================================

def validate_llm_response(
    request: RenderRequest,
    response: RenderResponse
) -> ValidationResult:
    """
    Validate an LLM response against the Symbol-U ↔ LLM Interface Contract.

    This is the main entry point for contract validation.

    Checks (in order):
    1. Self-assertions from LLM
    2. Token references against envelope.allowed_tokens
    3. Layer references against envelope.allowed_layers
    4. Forbidden phrases (override, selection, authority, structure)
    5. Provenance integrity
    6. Selection behavior
    7. Governance override suggestions
    8. Format constraints

    Args:
        request: The original RenderRequest sent to the LLM
        response: The RenderResponse received from the LLM

    Returns:
        ValidationResult with all violations found (empty if valid)
    """
    all_violations: List[ContractViolation] = []

    # 1. Check self-assertions
    all_violations.extend(validate_assertions(response))

    # 2. Check tokens (INV-2)
    all_violations.extend(validate_tokens(request, response))

    # 3. Check layers (INV-3)
    all_violations.extend(validate_layers(request, response))

    # 4. Check forbidden phrases (INV-4, INV-5)
    all_violations.extend(validate_forbidden_phrases(request, response))

    # 5. Check provenance (INV-7)
    all_violations.extend(validate_provenance(request, response))

    # 6. Check selection behavior (FM-3)
    all_violations.extend(validate_no_selection(request, response))

    # 7. Check governance override (FM-4)
    all_violations.extend(validate_no_governance_override(request, response))

    # 8. Check format (FM-5)
    all_violations.extend(validate_format(request, response))

    if all_violations:
        return ValidationResult.failure(tuple(all_violations))
    else:
        return ValidationResult.success()


# =============================================================================
# Helper Functions
# =============================================================================

def _extract_potential_tokens(content: str) -> List[str]:
    """
    Extract potential varna tokens from content.

    Looks for 1-3 character sequences that could be tokens.
    """
    # Simple pattern: word boundaries around short strings
    pattern = re.compile(r'\b([a-z]{1,3})\b', re.IGNORECASE)
    return pattern.findall(content)


def _is_likely_token(token: str) -> bool:
    """
    Check if a string is likely a varna token.

    Varna tokens are typically 1-3 chars like: ka, ga, a, i, u
    """
    if len(token) > 3 or len(token) < 1:
        return False
    # Common varna patterns
    varna_patterns = [
        r'^[kgtdpb]a$',  # Consonant + a
        r'^[aiu]$',      # Single vowel
        r'^[kgtdpb][aiu]$',  # Consonant + any vowel
    ]
    for pattern in varna_patterns:
        if re.match(pattern, token.lower()):
            return True
    return False
