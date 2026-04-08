"""
Symbol-U LLM Interface Types
============================

All types are frozen (immutable) dataclasses.
All collections are immutable (tuple, frozenset).

Contract: docs/contracts/SYMBOLU_LLM_INTERFACE_CONTRACT.md
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

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple, FrozenSet


# =============================================================================
# Enums
# =============================================================================

class RenderMode(Enum):
    """
    LLM rendering modes with increasing strictness.

    MINIMAL: LLM may be bypassed; purely mechanical restatement if used
    STANDARD: Tone/clarity improvements allowed; no new content
    REGULATED: Template-driven phrasing only; no metaphors/speculation
    """
    MINIMAL = "minimal"
    STANDARD = "standard"
    REGULATED = "regulated"


class ContractViolationType(Enum):
    """
    Types of contract violations that can be detected.

    Each maps to a failure mode (FM-1 through FM-6) in the contract.
    """
    # FM-1: Token injection
    NEW_TOKEN = "CONTRACT_VIOLATION_NEW_TOKEN"

    # FM-2: Structure addition
    STRUCTURE_ADDITION = "CONTRACT_VIOLATION_STRUCTURE_ADDITION"
    NEW_LAYER = "CONTRACT_VIOLATION_NEW_LAYER"
    CONSTRAINT_MODIFICATION = "CONTRACT_VIOLATION_CONSTRAINT_MODIFICATION"

    # FM-3: Selection leak
    SELECTION = "CONTRACT_VIOLATION_SELECTION"

    # FM-4: Governance override
    GOVERNANCE_OVERRIDE = "CONTRACT_VIOLATION_GOVERNANCE_OVERRIDE"

    # FM-5: Format violation
    FORMAT_VIOLATION = "FORMAT_VIOLATION"

    # FM-6: Provenance violation
    PROVENANCE_VIOLATION = "PROVENANCE_VIOLATION"


# =============================================================================
# Request Types (Symbol-U → LLM)
# =============================================================================

@dataclass(frozen=True)
class TargetConstraints:
    """Target constraints from Phase-7."""
    final_magnitude_min: Optional[float] = None
    final_magnitude_max: Optional[float] = None
    trajectory_shape: str = "any"  # "monotone_non_decreasing" | "any"
    quota: Optional[int] = None


@dataclass(frozen=True)
class Constraints:
    """Structural constraints for the envelope."""
    must_start_with: Optional[str] = None  # "consonant" | "vowel" | None
    max_len: Optional[int] = None
    min_len: Optional[int] = None
    must_include_events: Tuple[str, ...] = ()
    target: Optional[TargetConstraints] = None


@dataclass(frozen=True)
class Envelope:
    """
    Validity envelope defining what the LLM may reference.

    The LLM MUST NOT introduce anything outside this envelope.
    """
    allowed_layers: FrozenSet[str]
    allowed_tokens: FrozenSet[str]
    allowed_templates: FrozenSet[str] = frozenset()
    constraints: Optional[Constraints] = None


@dataclass(frozen=True)
class Provenance:
    """Cryptographic provenance of data origin."""
    phase4a_hash: str
    phase6_ruleset_id: str
    phase7_contract_id: str


@dataclass(frozen=True)
class TrajectoryStep:
    """Single step in a trajectory."""
    i: int
    token: str
    event: str  # "reset" | "modulate"
    magnitude: float


@dataclass(frozen=True)
class Phase7Result:
    """A single result from Phase-7 targeted generation."""
    sequence: Tuple[str, ...]
    trajectory_steps: Tuple[TrajectoryStep, ...]
    final_magnitude: float
    provenance: Provenance


@dataclass(frozen=True)
class RenderHints:
    """Hints for how to render the output."""
    style: str = "neutral"  # "neutral" | "formal" | "conversational"
    format: str = "paragraph"  # "bullet" | "paragraph" | "json"
    max_words: Optional[int] = None


@dataclass(frozen=True)
class AuthoritativePayload:
    """
    The authoritative data provided by Symbol-U.

    This is the ONLY data the LLM may reference for content.
    """
    phase7_results: Tuple[Phase7Result, ...]
    render_hints: RenderHints = RenderHints()


@dataclass(frozen=True)
class RenderRequest:
    """
    Request from Symbol-U to LLM for rendering.

    This is the ONLY allowed input type to the LLM layer.
    """
    contract_version: str
    request_id: str
    mode: RenderMode
    envelope: Envelope
    authoritative_payload: AuthoritativePayload
    forbidden_access: FrozenSet[str] = frozenset({"score", "rank", "search_trace", "policy_internal"})


# =============================================================================
# Response Types (LLM → Symbol-U)
# =============================================================================

@dataclass(frozen=True)
class OutputItem:
    """Single output item from the LLM."""
    modality: str  # "text" | "structured"
    format: str  # "plain_text" | "markdown" | "json"
    content: str


@dataclass(frozen=True)
class Assertions:
    """
    Self-declared assertions by the LLM.

    These are validated by the post-LLM validator.
    """
    no_structure_added: bool
    no_constraints_modified: bool
    no_new_tokens_introduced: bool


@dataclass(frozen=True)
class RenderResponse:
    """
    Response from LLM to Symbol-U.

    This is the ONLY allowed output type from the LLM layer.
    """
    contract_version: str
    request_id: str
    renderer_id: str
    outputs: Tuple[OutputItem, ...]
    assertions: Assertions


# =============================================================================
# Validation Types
# =============================================================================

@dataclass(frozen=True)
class ContractViolation:
    """A single contract violation detected during validation."""
    violation_type: ContractViolationType
    message: str
    evidence: Optional[str] = None  # The offending content, if applicable
    location: Optional[str] = None  # Where in the output the violation occurred


@dataclass(frozen=True)
class ValidationResult:
    """Result of validating an LLM response against the contract."""
    valid: bool
    violations: Tuple[ContractViolation, ...]

    @staticmethod
    def success() -> "ValidationResult":
        """Create a successful validation result."""
        return ValidationResult(valid=True, violations=())

    @staticmethod
    def failure(violations: Tuple[ContractViolation, ...]) -> "ValidationResult":
        """Create a failed validation result."""
        return ValidationResult(valid=False, violations=violations)
