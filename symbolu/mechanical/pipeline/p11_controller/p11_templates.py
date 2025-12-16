"""
P11 Template Renderer - Approved Templates for Phase-11
========================================================

This module provides the approved templates for Phase-11 controlled rendering.

Template Rendering Rules:
    - MUST be deterministic (same input -> same output)
    - MUST only use approved templates
    - NO free-form text generation
    - NO ML/NLP imports
    - NO randomness
    - NO time/datetime

Approved Templates:
    Templates are keyed by (acoustic_regime, vc_fact_combination) tuples.
    Each template is a static string with placeholders for structured data.

Hard Constraints:
    - Templates are IMMUTABLE
    - Template selection is DETERMINISTIC
    - Placeholder substitution is LITERAL (no interpretation)
    - Unknown combinations -> default template
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, FrozenSet, Tuple

from symbolu.mechanical.pipeline.p11_controller.p11_schema import Phase10Result


# =============================================================================
# Template Version
# =============================================================================

TEMPLATE_VERSION = "1.0.0"


# =============================================================================
# Approved Template Registry
# =============================================================================

# Template key: (acoustic_regime, frozenset of VC facts)
# Template value: static template string with placeholders

_APPROVED_TEMPLATES: Dict[Tuple[str, FrozenSet[str]], str] = {
    # NEUTRAL regime templates
    ("neutral", frozenset({"VC-1"})): "[REGIME:neutral] Observation: {vc_1_data}",
    ("neutral", frozenset({"VC-2"})): "[REGIME:neutral] State: {vc_2_data}",
    ("neutral", frozenset({"VC-3"})): "[REGIME:neutral] Context: {vc_3_data}",
    ("neutral", frozenset({"VC-4"})): "[REGIME:neutral] Reference: {vc_4_data}",
    ("neutral", frozenset({"VC-5"})): "[REGIME:neutral] Marker: {vc_5_data}",
    ("neutral", frozenset({"VC-1", "VC-2"})): "[REGIME:neutral] Observation: {vc_1_data}; State: {vc_2_data}",
    ("neutral", frozenset({"VC-1", "VC-3"})): "[REGIME:neutral] Observation: {vc_1_data}; Context: {vc_3_data}",
    ("neutral", frozenset({"VC-1", "VC-2", "VC-3"})): "[REGIME:neutral] Observation: {vc_1_data}; State: {vc_2_data}; Context: {vc_3_data}",
    ("neutral", frozenset({"VC-1", "VC-2", "VC-3", "VC-4"})): "[REGIME:neutral] Observation: {vc_1_data}; State: {vc_2_data}; Context: {vc_3_data}; Reference: {vc_4_data}",
    ("neutral", frozenset({"VC-1", "VC-2", "VC-3", "VC-4", "VC-5"})): "[REGIME:neutral] Observation: {vc_1_data}; State: {vc_2_data}; Context: {vc_3_data}; Reference: {vc_4_data}; Marker: {vc_5_data}",

    # SOFT regime templates
    ("soft", frozenset({"VC-1"})): "[REGIME:soft] Observed: {vc_1_data}",
    ("soft", frozenset({"VC-2"})): "[REGIME:soft] Current state: {vc_2_data}",
    ("soft", frozenset({"VC-3"})): "[REGIME:soft] In context: {vc_3_data}",
    ("soft", frozenset({"VC-4"})): "[REGIME:soft] Referenced: {vc_4_data}",
    ("soft", frozenset({"VC-5"})): "[REGIME:soft] Marked: {vc_5_data}",
    ("soft", frozenset({"VC-1", "VC-2"})): "[REGIME:soft] Observed: {vc_1_data}; Current state: {vc_2_data}",
    ("soft", frozenset({"VC-1", "VC-2", "VC-3"})): "[REGIME:soft] Observed: {vc_1_data}; Current state: {vc_2_data}; In context: {vc_3_data}",

    # FLAT regime templates
    ("flat", frozenset({"VC-1"})): "[REGIME:flat] {vc_1_data}",
    ("flat", frozenset({"VC-2"})): "[REGIME:flat] {vc_2_data}",
    ("flat", frozenset({"VC-3"})): "[REGIME:flat] {vc_3_data}",
    ("flat", frozenset({"VC-4"})): "[REGIME:flat] {vc_4_data}",
    ("flat", frozenset({"VC-5"})): "[REGIME:flat] {vc_5_data}",
    ("flat", frozenset({"VC-1", "VC-2"})): "[REGIME:flat] {vc_1_data}; {vc_2_data}",
    ("flat", frozenset({"VC-1", "VC-2", "VC-3"})): "[REGIME:flat] {vc_1_data}; {vc_2_data}; {vc_3_data}",

    # RESTRAINED regime templates
    ("restrained", frozenset({"VC-1"})): "[REGIME:restrained] Note: {vc_1_data}",
    ("restrained", frozenset({"VC-2"})): "[REGIME:restrained] Status: {vc_2_data}",
    ("restrained", frozenset({"VC-3"})): "[REGIME:restrained] Setting: {vc_3_data}",
    ("restrained", frozenset({"VC-4"})): "[REGIME:restrained] Ref: {vc_4_data}",
    ("restrained", frozenset({"VC-5"})): "[REGIME:restrained] Mark: {vc_5_data}",
    ("restrained", frozenset({"VC-1", "VC-2"})): "[REGIME:restrained] Note: {vc_1_data}; Status: {vc_2_data}",
    ("restrained", frozenset({"VC-1", "VC-2", "VC-3"})): "[REGIME:restrained] Note: {vc_1_data}; Status: {vc_2_data}; Setting: {vc_3_data}",
}

# Default template for unknown combinations
_DEFAULT_TEMPLATE = "[REGIME:{regime}] Data: {all_facts}"


# =============================================================================
# VC Data Extraction
# =============================================================================


@dataclass(frozen=True)
class VCExtraction:
    """
    Extracted VC facts from Phase10Result.

    Attributes:
        vc_facts: Tuple of extracted VC fact identifiers
        vc_data: Dictionary mapping VC-N to extracted data string
        extraction_hash: Deterministic hash of the extraction
    """
    vc_facts: Tuple[str, ...]
    vc_data: Dict[str, str]
    extraction_hash: str

    def __post_init__(self) -> None:
        """Validate VCExtraction invariants."""
        if not isinstance(self.vc_facts, tuple):
            raise ValueError(
                f"VCExtraction.vc_facts must be tuple, "
                f"got {type(self.vc_facts).__name__}"
            )
        if not isinstance(self.vc_data, dict):
            raise ValueError(
                f"VCExtraction.vc_data must be dict, "
                f"got {type(self.vc_data).__name__}"
            )
        if not isinstance(self.extraction_hash, str) or len(self.extraction_hash) != 16:
            raise ValueError(
                "VCExtraction.extraction_hash must be 16-char hex string"
            )


def extract_vc_facts(phase10_result: Phase10Result) -> VCExtraction:
    """
    Extract ONLY allowed VC facts (VC-1 through VC-5) from Phase10Result.

    This function:
        - Extracts only VC-1 through VC-5
        - No text interpretation
        - No scoring
        - Deterministic extraction

    Args:
        phase10_result: The opaque Phase10Result from upstream.

    Returns:
        VCExtraction with extracted facts and data.
    """
    allowed_vc_facts = {"VC-1", "VC-2", "VC-3", "VC-4", "VC-5"}

    # Extract VC facts (filter to only allowed ones)
    vc_facts = tuple(
        fact for fact in phase10_result.vc_facts
        if fact in allowed_vc_facts
    )

    # Extract data for each VC fact from source_data
    vc_data: Dict[str, str] = {}
    for fact in vc_facts:
        # Deterministic key lookup - no interpretation
        data_key = fact.lower().replace("-", "_") + "_data"
        if data_key in phase10_result.source_data:
            raw_value = phase10_result.source_data[data_key]
            # Convert to string deterministically
            vc_data[fact] = str(raw_value)
        else:
            # Default value if not present
            vc_data[fact] = f"[{fact}:unspecified]"

    # Compute deterministic extraction hash
    hash_input = f"{vc_facts}|{sorted(vc_data.items())}"
    extraction_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]

    return VCExtraction(
        vc_facts=vc_facts,
        vc_data=vc_data,
        extraction_hash=extraction_hash,
    )


# =============================================================================
# Template Rendering
# =============================================================================


@dataclass(frozen=True)
class TemplateRenderResult:
    """
    Result of template rendering.

    Attributes:
        output_text: The rendered output text
        template_key: The template key that was used
        template_used: The actual template string
        render_hash: Deterministic hash of the rendering
    """
    output_text: str
    template_key: str
    template_used: str
    render_hash: str

    def __post_init__(self) -> None:
        """Validate TemplateRenderResult invariants."""
        if not isinstance(self.output_text, str):
            raise ValueError(
                f"TemplateRenderResult.output_text must be str, "
                f"got {type(self.output_text).__name__}"
            )
        if not isinstance(self.template_key, str):
            raise ValueError(
                f"TemplateRenderResult.template_key must be str, "
                f"got {type(self.template_key).__name__}"
            )
        if not isinstance(self.template_used, str):
            raise ValueError(
                f"TemplateRenderResult.template_used must be str, "
                f"got {type(self.template_used).__name__}"
            )
        if not isinstance(self.render_hash, str) or len(self.render_hash) != 16:
            raise ValueError(
                "TemplateRenderResult.render_hash must be 16-char hex string"
            )


def render_template(
    vc_extraction: VCExtraction,
    acoustic_regime: str,
) -> TemplateRenderResult:
    """
    Render candidate output using approved templates.

    This function:
        - Must be deterministic
        - Must only use approved templates
        - No free-form generation
        - No ML/NLP

    Args:
        vc_extraction: Extracted VC facts from Phase10Result.
        acoustic_regime: The acoustic regime from Phase10.

    Returns:
        TemplateRenderResult with rendered output.
    """
    # Normalize regime to lowercase for template lookup
    regime_key = acoustic_regime.lower()

    # Build template lookup key
    vc_fact_set = frozenset(vc_extraction.vc_facts)
    template_key = (regime_key, vc_fact_set)

    # Look up template (deterministic)
    if template_key in _APPROVED_TEMPLATES:
        template = _APPROVED_TEMPLATES[template_key]
        template_key_str = f"{regime_key}:{sorted(vc_fact_set)}"
    else:
        # Fall back to default template
        template = _DEFAULT_TEMPLATE
        template_key_str = f"{regime_key}:DEFAULT"

    # Build placeholder substitutions
    placeholders: Dict[str, str] = {
        "regime": regime_key,
    }

    # Add individual VC data placeholders
    for fact, data in vc_extraction.vc_data.items():
        placeholder_key = fact.lower().replace("-", "_") + "_data"
        placeholders[placeholder_key] = data

    # Add combined facts placeholder for default template
    all_facts_parts = [
        f"{fact}={vc_extraction.vc_data.get(fact, 'N/A')}"
        for fact in sorted(vc_extraction.vc_facts)
    ]
    placeholders["all_facts"] = "; ".join(all_facts_parts) if all_facts_parts else "none"

    # Render template (deterministic substitution)
    output_text = template.format(**placeholders)

    # Compute deterministic render hash
    hash_input = f"{template_key_str}|{output_text}"
    render_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]

    return TemplateRenderResult(
        output_text=output_text,
        template_key=template_key_str,
        template_used=template,
        render_hash=render_hash,
    )


# =============================================================================
# Template Validation
# =============================================================================


def get_approved_template_count() -> int:
    """Return the count of approved templates."""
    return len(_APPROVED_TEMPLATES)


def is_approved_template_key(regime: str, vc_facts: FrozenSet[str]) -> bool:
    """Check if a template key is in the approved registry."""
    return (regime.lower(), vc_facts) in _APPROVED_TEMPLATES


def get_template_version() -> str:
    """Return the template version."""
    return TEMPLATE_VERSION


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Version
    "TEMPLATE_VERSION",
    # Dataclasses
    "VCExtraction",
    "TemplateRenderResult",
    # Functions
    "extract_vc_facts",
    "render_template",
    "get_approved_template_count",
    "is_approved_template_key",
    "get_template_version",
]
