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

PPV Support (v1.1):
    - PPV metrics can be extracted and rendered as numeric-only template slots
    - GOVERNED templates may only include: PPV_PRESENT, PPV_AGGREGATE, PPV_DIM_SUMMARY
    - PPV never as text generation, only numeric metrics
    - No dynamic formatting, no conditional text other than fixed template lines

Hard Constraints:
    - Templates are IMMUTABLE
    - Template selection is DETERMINISTIC
    - Placeholder substitution is LITERAL (no interpretation)
    - Unknown combinations -> default template
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Optional, Tuple

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
# PPV-Aware Templates (Approved for GOVERNED Mode)
# =============================================================================

# PPV templates add NUMERIC-ONLY metrics (PPV_AGGREGATE, PPV_DIM_SUMMARY)
# These are ADDITIVE - they extend the base templates, not replace them

_PPV_AWARE_TEMPLATES: Dict[Tuple[str, FrozenSet[str], bool], str] = {
    # NEUTRAL regime with PPV
    ("neutral", frozenset({"VC-1"}), True): "[REGIME:neutral] Observation: {vc_1_data} [PPV:{ppv_aggregate}]",
    ("neutral", frozenset({"VC-2"}), True): "[REGIME:neutral] State: {vc_2_data} [PPV:{ppv_aggregate}]",
    ("neutral", frozenset({"VC-1", "VC-2"}), True): "[REGIME:neutral] Observation: {vc_1_data}; State: {vc_2_data} [PPV:{ppv_aggregate}]",
    ("neutral", frozenset({"VC-1", "VC-2", "VC-3"}), True): "[REGIME:neutral] Observation: {vc_1_data}; State: {vc_2_data}; Context: {vc_3_data} [PPV:{ppv_aggregate}]",

    # SOFT regime with PPV
    ("soft", frozenset({"VC-1"}), True): "[REGIME:soft] Observed: {vc_1_data} [PPV:{ppv_aggregate}]",
    ("soft", frozenset({"VC-1", "VC-2"}), True): "[REGIME:soft] Observed: {vc_1_data}; Current state: {vc_2_data} [PPV:{ppv_aggregate}]",

    # FLAT regime with PPV
    ("flat", frozenset({"VC-1"}), True): "[REGIME:flat] {vc_1_data} [PPV:{ppv_aggregate}]",
    ("flat", frozenset({"VC-1", "VC-2"}), True): "[REGIME:flat] {vc_1_data}; {vc_2_data} [PPV:{ppv_aggregate}]",

    # RESTRAINED regime with PPV
    ("restrained", frozenset({"VC-1"}), True): "[REGIME:restrained] Note: {vc_1_data} [PPV:{ppv_aggregate}]",
    ("restrained", frozenset({"VC-1", "VC-2"}), True): "[REGIME:restrained] Note: {vc_1_data}; Status: {vc_2_data} [PPV:{ppv_aggregate}]",
}

# Default PPV template (numeric only)
_DEFAULT_PPV_TEMPLATE = "[REGIME:{regime}] Data: {all_facts} [PPV:{ppv_aggregate}]"

# PPV dimension summary template line (for OPEN mode extended output)
_PPV_DIM_LINE_TEMPLATE = "[PPV_DIMS:{ppv_dim_summary}]"


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
# PPV Metrics Extraction
# =============================================================================


@dataclass(frozen=True)
class PPVMetrics:
    """
    Extracted PPV metrics for template rendering.

    These are NUMERIC-ONLY metrics suitable for GOVERNED mode.

    Attributes:
        ppv_present: Whether PPV is attached (bool)
        ppv_aggregate: The aggregate checksum value (int)
        ppv_dim_summary: Tuple of dimension values (ints)
        ppv_hash_prefix: First 16 chars of PPV hash (for ledger only)
    """
    ppv_present: bool
    ppv_aggregate: int
    ppv_dim_summary: Tuple[int, ...]
    ppv_hash_prefix: str

    def __post_init__(self) -> None:
        """Validate PPVMetrics invariants."""
        if not isinstance(self.ppv_present, bool):
            raise ValueError(
                f"PPVMetrics.ppv_present must be bool, "
                f"got {type(self.ppv_present).__name__}"
            )
        if not isinstance(self.ppv_aggregate, int):
            raise ValueError(
                f"PPVMetrics.ppv_aggregate must be int, "
                f"got {type(self.ppv_aggregate).__name__}"
            )
        if not isinstance(self.ppv_dim_summary, tuple):
            raise ValueError(
                f"PPVMetrics.ppv_dim_summary must be tuple, "
                f"got {type(self.ppv_dim_summary).__name__}"
            )
        for i, val in enumerate(self.ppv_dim_summary):
            if not isinstance(val, int):
                raise ValueError(
                    f"PPVMetrics.ppv_dim_summary[{i}] must be int, "
                    f"got {type(val).__name__}"
                )
        if not isinstance(self.ppv_hash_prefix, str):
            raise ValueError(
                f"PPVMetrics.ppv_hash_prefix must be str, "
                f"got {type(self.ppv_hash_prefix).__name__}"
            )


# Empty PPV metrics (for when PPV is not present)
EMPTY_PPV_METRICS = PPVMetrics(
    ppv_present=False,
    ppv_aggregate=0,
    ppv_dim_summary=(),
    ppv_hash_prefix="",
)


def extract_ppv_metrics(ppv_data: Optional[Any]) -> PPVMetrics:
    """
    Extract PPV metrics from PPV data.

    This function extracts NUMERIC-ONLY metrics suitable for template use.

    Args:
        ppv_data: Optional PPV data (PPVVector or dict with PPV fields).

    Returns:
        PPVMetrics with extracted numeric values.
    """
    if ppv_data is None:
        return EMPTY_PPV_METRICS

    # Handle PPVVector objects
    if hasattr(ppv_data, "aggregate") and hasattr(ppv_data, "values"):
        return PPVMetrics(
            ppv_present=True,
            ppv_aggregate=int(ppv_data.aggregate),
            ppv_dim_summary=tuple(ppv_data.values),
            ppv_hash_prefix=str(ppv_data.ppv_hash)[:16] if hasattr(ppv_data, "ppv_hash") else "",
        )

    # Handle dict-based PPV metrics
    if isinstance(ppv_data, dict):
        if ppv_data.get("PPV_PRESENT", False):
            return PPVMetrics(
                ppv_present=True,
                ppv_aggregate=int(ppv_data.get("PPV_AGGREGATE", 0)),
                ppv_dim_summary=tuple(ppv_data.get("PPV_DIM_SUMMARY", ())),
                ppv_hash_prefix=str(ppv_data.get("PPV_HASH", ""))[:16],
            )
        return EMPTY_PPV_METRICS

    # Unknown format - return empty
    return EMPTY_PPV_METRICS


@dataclass(frozen=True)
class VCPPVExtraction:
    """
    Combined VC facts and PPV metrics extraction.

    This combines VCExtraction with PPVMetrics for PPV-aware rendering.

    Attributes:
        vc_extraction: The extracted VC facts
        ppv_metrics: The extracted PPV metrics
        combined_hash: Deterministic hash of the combined extraction
    """
    vc_extraction: VCExtraction
    ppv_metrics: PPVMetrics
    combined_hash: str

    def __post_init__(self) -> None:
        """Validate VCPPVExtraction invariants."""
        if not isinstance(self.vc_extraction, VCExtraction):
            raise ValueError(
                f"VCPPVExtraction.vc_extraction must be VCExtraction, "
                f"got {type(self.vc_extraction).__name__}"
            )
        if not isinstance(self.ppv_metrics, PPVMetrics):
            raise ValueError(
                f"VCPPVExtraction.ppv_metrics must be PPVMetrics, "
                f"got {type(self.ppv_metrics).__name__}"
            )
        if not isinstance(self.combined_hash, str) or len(self.combined_hash) != 16:
            raise ValueError(
                "VCPPVExtraction.combined_hash must be 16-char hex string"
            )


def extract_vc_ppv_facts(
    phase10_result: Phase10Result,
    ppv_data: Optional[Any] = None,
) -> VCPPVExtraction:
    """
    Extract VC facts and PPV metrics from Phase10Result.

    This function combines VC extraction with PPV metrics extraction.

    Args:
        phase10_result: The Phase10Result from upstream.
        ppv_data: Optional PPV data (PPVVector or dict).

    Returns:
        VCPPVExtraction with VC facts and PPV metrics.
    """
    # Extract VC facts
    vc_extraction = extract_vc_facts(phase10_result)

    # Extract PPV metrics
    ppv_metrics = extract_ppv_metrics(ppv_data)

    # Compute combined hash
    hash_input = f"{vc_extraction.extraction_hash}|{ppv_metrics.ppv_present}|{ppv_metrics.ppv_aggregate}"
    combined_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]

    return VCPPVExtraction(
        vc_extraction=vc_extraction,
        ppv_metrics=ppv_metrics,
        combined_hash=combined_hash,
    )


# =============================================================================
# PPV-Aware Template Rendering
# =============================================================================


def render_template_with_ppv(
    vc_extraction: VCExtraction,
    acoustic_regime: str,
    ppv_metrics: PPVMetrics,
    include_dim_line: bool = False,
) -> TemplateRenderResult:
    """
    Render candidate output using PPV-aware templates.

    This function:
        - Uses PPV-aware templates if PPV is present
        - Falls back to base templates if PPV not present
        - Adds numeric-only PPV data to output
        - Never adds free-form text interpretation

    Args:
        vc_extraction: Extracted VC facts from Phase10Result.
        acoustic_regime: The acoustic regime from Phase10.
        ppv_metrics: Extracted PPV metrics.
        include_dim_line: If True, append PPV dimension summary line (OPEN mode only).

    Returns:
        TemplateRenderResult with rendered output.
    """
    # Normalize regime to lowercase for template lookup
    regime_key = acoustic_regime.lower()

    # Build template lookup key
    vc_fact_set = frozenset(vc_extraction.vc_facts)

    # Determine if we should use PPV-aware template
    use_ppv_template = ppv_metrics.ppv_present

    # Look up template (deterministic)
    if use_ppv_template:
        ppv_template_key = (regime_key, vc_fact_set, True)
        if ppv_template_key in _PPV_AWARE_TEMPLATES:
            template = _PPV_AWARE_TEMPLATES[ppv_template_key]
            template_key_str = f"{regime_key}:{sorted(vc_fact_set)}:PPV"
        else:
            # Fall back to default PPV template
            template = _DEFAULT_PPV_TEMPLATE
            template_key_str = f"{regime_key}:DEFAULT:PPV"
    else:
        # No PPV - use base templates
        base_template_key = (regime_key, vc_fact_set)
        if base_template_key in _APPROVED_TEMPLATES:
            template = _APPROVED_TEMPLATES[base_template_key]
            template_key_str = f"{regime_key}:{sorted(vc_fact_set)}"
        else:
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

    # Add PPV placeholders (numeric only)
    placeholders["ppv_aggregate"] = str(ppv_metrics.ppv_aggregate)

    # Render template (deterministic substitution)
    output_text = template.format(**placeholders)

    # Optionally add PPV dimension line (for OPEN mode)
    if include_dim_line and ppv_metrics.ppv_present:
        dim_summary_str = ",".join(str(v) for v in ppv_metrics.ppv_dim_summary)
        dim_line = _PPV_DIM_LINE_TEMPLATE.format(ppv_dim_summary=dim_summary_str)
        output_text = f"{output_text}\n{dim_line}"
        template_key_str = f"{template_key_str}:DIMS"

    # Compute deterministic render hash
    hash_input = f"{template_key_str}|{output_text}"
    render_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]

    return TemplateRenderResult(
        output_text=output_text,
        template_key=template_key_str,
        template_used=template,
        render_hash=render_hash,
    )


def is_ppv_template_supported(regime: str, vc_facts: FrozenSet[str]) -> bool:
    """
    Check if a PPV-aware template exists for the given regime and VC facts.

    Args:
        regime: The acoustic regime.
        vc_facts: The set of VC facts.

    Returns:
        True if a PPV-aware template exists, False otherwise.
    """
    return (regime.lower(), vc_facts, True) in _PPV_AWARE_TEMPLATES


def get_ppv_template_count() -> int:
    """Return the count of PPV-aware templates."""
    return len(_PPV_AWARE_TEMPLATES)


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Version
    "TEMPLATE_VERSION",
    # Dataclasses
    "VCExtraction",
    "TemplateRenderResult",
    "PPVMetrics",
    "VCPPVExtraction",
    # Constants
    "EMPTY_PPV_METRICS",
    # Functions
    "extract_vc_facts",
    "render_template",
    "get_approved_template_count",
    "is_approved_template_key",
    "get_template_version",
    # PPV Functions
    "extract_ppv_metrics",
    "extract_vc_ppv_facts",
    "render_template_with_ppv",
    "is_ppv_template_supported",
    "get_ppv_template_count",
]
