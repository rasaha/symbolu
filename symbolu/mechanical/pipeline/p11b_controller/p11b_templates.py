"""
P11B Template Registry - Phase-11B Governed Structural Templates
===================================================================

This module provides the Phase-11B template registry with:
    - Templates keyed by (family, variant_id, slot_plan)
    - Separate GOVERNED and OPEN registries
    - Silent collapse prevention validation
    - Registry completeness checking

Phase-11B Template Design:
    - Ontological family → Template structure family
    - Variant ID (from PPV bands) → Structural variation
    - Slot plan → VC slot inclusion/ordering

Registry Rules:
    - Different (family, variant_id, slot_plan) → different template_id
    - Same triple → same template_id
    - Missing combination → fallback template (explicitly marked)
    - GOVERNED registry is strict subset of OPEN registry

Hard Constraints (NON-NEGOTIABLE):
    - No semantics (templates are structural patterns only)
    - No free-form generation
    - Templates are IMMUTABLE
    - Template selection is DETERMINISTIC
    - Placeholder substitution is LITERAL (no interpretation)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

from symbolu.mechanical.pipeline.p11_controller.p11_schema import Phase10Result
from symbolu.mechanical.pipeline.p11b_controller.p11b_schema import (
    OntologicalFamily,
    PPVBand,
    PPVBandSignature,
    RegistryType,
    SlotPlan,
    TemplateKey,
    SLOT_PLAN_VC_FACTS,
    create_ppv_band_signature,
    compute_variant_id,
    get_slot_plan_from_ppv,
)


# =============================================================================
# Template Version
# =============================================================================

P11B_TEMPLATE_VERSION = "1.0.0"


# =============================================================================
# Template Definition (Frozen)
# =============================================================================


@dataclass(frozen=True)
class P11BTemplate:
    """
    Phase-11B template definition.

    Attributes:
        template_id: Unique identifier for this template
        family: Template family from ontological path
        variant_id: Variant ID from PPV band signature
        slot_plan: Slot plan for VC inclusion
        template_string: The template string with placeholders
        is_fallback: True if this is a fallback template

    Invariants:
        - template_id is unique across all templates
        - template_string contains valid placeholders
        - Fallback templates are explicitly marked
    """
    template_id: str
    family: OntologicalFamily
    variant_id: str
    slot_plan: SlotPlan
    template_string: str
    is_fallback: bool = False

    def __post_init__(self) -> None:
        """Validate P11BTemplate invariants."""
        if not isinstance(self.template_id, str) or not self.template_id.strip():
            raise ValueError("P11BTemplate.template_id must be non-empty string")
        if not isinstance(self.family, OntologicalFamily):
            raise ValueError(
                f"P11BTemplate.family must be OntologicalFamily, "
                f"got {type(self.family).__name__}"
            )
        if not isinstance(self.variant_id, str) or not self.variant_id.strip():
            raise ValueError("P11BTemplate.variant_id must be non-empty string")
        if not isinstance(self.slot_plan, SlotPlan):
            raise ValueError(
                f"P11BTemplate.slot_plan must be SlotPlan, "
                f"got {type(self.slot_plan).__name__}"
            )
        if not isinstance(self.template_string, str):
            raise ValueError("P11BTemplate.template_string must be string")
        if not isinstance(self.is_fallback, bool):
            raise ValueError("P11BTemplate.is_fallback must be bool")

    def get_key(self) -> TemplateKey:
        """Get template key for this template."""
        return TemplateKey(
            family=self.family,
            variant_id=self.variant_id,
            slot_plan=self.slot_plan,
        )


# =============================================================================
# Template ID Generation
# =============================================================================


def generate_template_id(
    family: OntologicalFamily,
    variant_id: str,
    slot_plan: SlotPlan,
    registry_type: RegistryType = RegistryType.GOVERNED,
) -> str:
    """
    Generate unique template ID from key components.

    The template ID is a deterministic hash ensuring uniqueness.

    Args:
        family: Template family
        variant_id: Variant ID from PPV bands
        slot_plan: Slot plan
        registry_type: Registry type (affects ID prefix)

    Returns:
        Unique template ID string.
    """
    prefix = "G" if registry_type == RegistryType.GOVERNED else "O"
    canonical = f"{prefix}|{family.value}|{variant_id}|{slot_plan.value}"
    hash_suffix = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:8]
    return f"T11B_{prefix}_{family.value[:3]}_{slot_plan.value[:3]}_{hash_suffix}"


# =============================================================================
# Family-Based Template Builders
# =============================================================================


def _build_acting_template(slot_plan: SlotPlan, variant_id: str) -> str:
    """Build template for ACTING family."""
    vc_facts = SLOT_PLAN_VC_FACTS[slot_plan]
    parts = [f"[FAMILY:ACTING][VARIANT:{variant_id}]"]

    for vc in vc_facts:
        slot_key = vc.lower().replace("-", "_") + "_data"
        parts.append(f"Action-{vc}: {{{slot_key}}}")

    return " | ".join(parts)


def _build_tagging_template(slot_plan: SlotPlan, variant_id: str) -> str:
    """Build template for TAGGING family."""
    vc_facts = SLOT_PLAN_VC_FACTS[slot_plan]
    parts = [f"[FAMILY:TAGGING][VARIANT:{variant_id}]"]

    for vc in vc_facts:
        slot_key = vc.lower().replace("-", "_") + "_data"
        parts.append(f"Tag-{vc}: {{{slot_key}}}")

    return " | ".join(parts)


def _build_forming_template(slot_plan: SlotPlan, variant_id: str) -> str:
    """Build template for FORMING family."""
    vc_facts = SLOT_PLAN_VC_FACTS[slot_plan]
    parts = [f"[FAMILY:FORMING][VARIANT:{variant_id}]"]

    for vc in vc_facts:
        slot_key = vc.lower().replace("-", "_") + "_data"
        parts.append(f"Form-{vc}: {{{slot_key}}}")

    return " | ".join(parts)


def _build_thinking_template(slot_plan: SlotPlan, variant_id: str) -> str:
    """Build template for THINKING family."""
    vc_facts = SLOT_PLAN_VC_FACTS[slot_plan]
    parts = [f"[FAMILY:THINKING][VARIANT:{variant_id}]"]

    for vc in vc_facts:
        slot_key = vc.lower().replace("-", "_") + "_data"
        parts.append(f"Thought-{vc}: {{{slot_key}}}")

    return " | ".join(parts)


def _build_directing_template(slot_plan: SlotPlan, variant_id: str) -> str:
    """Build template for DIRECTING family."""
    vc_facts = SLOT_PLAN_VC_FACTS[slot_plan]
    parts = [f"[FAMILY:DIRECTING][VARIANT:{variant_id}]"]

    for vc in vc_facts:
        slot_key = vc.lower().replace("-", "_") + "_data"
        parts.append(f"Direction-{vc}: {{{slot_key}}}")

    return " | ".join(parts)


def _build_reasoning_template(slot_plan: SlotPlan, variant_id: str) -> str:
    """Build template for REASONING family."""
    vc_facts = SLOT_PLAN_VC_FACTS[slot_plan]
    parts = [f"[FAMILY:REASONING][VARIANT:{variant_id}]"]

    for vc in vc_facts:
        slot_key = vc.lower().replace("-", "_") + "_data"
        parts.append(f"Reason-{vc}: {{{slot_key}}}")

    return " | ".join(parts)


def _build_purposing_template(slot_plan: SlotPlan, variant_id: str) -> str:
    """Build template for PURPOSING family."""
    vc_facts = SLOT_PLAN_VC_FACTS[slot_plan]
    parts = [f"[FAMILY:PURPOSING][VARIANT:{variant_id}]"]

    for vc in vc_facts:
        slot_key = vc.lower().replace("-", "_") + "_data"
        parts.append(f"Purpose-{vc}: {{{slot_key}}}")

    return " | ".join(parts)


def _build_meta_observing_template(slot_plan: SlotPlan, variant_id: str) -> str:
    """Build template for META_OBSERVING family."""
    vc_facts = SLOT_PLAN_VC_FACTS[slot_plan]
    parts = [f"[FAMILY:META_OBSERVING][VARIANT:{variant_id}]"]

    for vc in vc_facts:
        slot_key = vc.lower().replace("-", "_") + "_data"
        parts.append(f"Observe-{vc}: {{{slot_key}}}")

    return " | ".join(parts)


def _build_unifying_template(slot_plan: SlotPlan, variant_id: str) -> str:
    """Build template for UNIFYING family."""
    vc_facts = SLOT_PLAN_VC_FACTS[slot_plan]
    parts = [f"[FAMILY:UNIFYING][VARIANT:{variant_id}]"]

    for vc in vc_facts:
        slot_key = vc.lower().replace("-", "_") + "_data"
        parts.append(f"Unity-{vc}: {{{slot_key}}}")

    return " | ".join(parts)


def _build_absolving_template(slot_plan: SlotPlan, variant_id: str) -> str:
    """Build template for ABSOLVING family."""
    vc_facts = SLOT_PLAN_VC_FACTS[slot_plan]
    parts = [f"[FAMILY:ABSOLVING][VARIANT:{variant_id}]"]

    for vc in vc_facts:
        slot_key = vc.lower().replace("-", "_") + "_data"
        parts.append(f"Resolve-{vc}: {{{slot_key}}}")

    return " | ".join(parts)


def _build_default_template(slot_plan: SlotPlan, variant_id: str) -> str:
    """Build template for DEFAULT family (fallback)."""
    vc_facts = SLOT_PLAN_VC_FACTS[slot_plan]
    parts = [f"[FAMILY:DEFAULT][VARIANT:{variant_id}][FALLBACK]"]

    for vc in vc_facts:
        slot_key = vc.lower().replace("-", "_") + "_data"
        parts.append(f"Data-{vc}: {{{slot_key}}}")

    return " | ".join(parts)


# Family to builder mapping
_FAMILY_BUILDERS = {
    OntologicalFamily.ACTING: _build_acting_template,
    OntologicalFamily.TAGGING: _build_tagging_template,
    OntologicalFamily.FORMING: _build_forming_template,
    OntologicalFamily.THINKING: _build_thinking_template,
    OntologicalFamily.DIRECTING: _build_directing_template,
    OntologicalFamily.REASONING: _build_reasoning_template,
    OntologicalFamily.PURPOSING: _build_purposing_template,
    OntologicalFamily.META_OBSERVING: _build_meta_observing_template,
    OntologicalFamily.UNIFYING: _build_unifying_template,
    OntologicalFamily.ABSOLVING: _build_absolving_template,
    OntologicalFamily.DEFAULT: _build_default_template,
}


def build_template_string(
    family: OntologicalFamily,
    slot_plan: SlotPlan,
    variant_id: str,
) -> str:
    """
    Build template string for given parameters.

    Args:
        family: Template family
        slot_plan: Slot plan
        variant_id: Variant ID

    Returns:
        Template string with placeholders.
    """
    builder = _FAMILY_BUILDERS.get(family, _build_default_template)
    return builder(slot_plan, variant_id)


# =============================================================================
# Registry Generation (Governed and Open)
# =============================================================================


def _generate_all_variant_ids() -> List[str]:
    """
    Generate all possible variant IDs from PPV band combinations.

    With 3 bands (L, M, H) and 8 dimensions, there are 3^8 = 6561
    possible combinations. We generate representative samples.

    Returns:
        List of variant ID strings.
    """
    variant_ids: List[str] = []

    # Generate representative variants (not all 6561)
    # Focus on common patterns and edge cases

    bands = [PPVBand.LOW, PPVBand.MID, PPVBand.HIGH]

    # All same band variants (3)
    for band in bands:
        variant = "_".join([band.value] * 8)
        variant_ids.append(variant)

    # Single dimension high, rest low (8)
    for i in range(8):
        dims = [PPVBand.LOW.value] * 8
        dims[i] = PPVBand.HIGH.value
        variant_ids.append("_".join(dims))

    # Single dimension low, rest high (8)
    for i in range(8):
        dims = [PPVBand.HIGH.value] * 8
        dims[i] = PPVBand.LOW.value
        variant_ids.append("_".join(dims))

    # Alternating patterns
    variant_ids.append("L_M_L_M_L_M_L_M")
    variant_ids.append("M_H_M_H_M_H_M_H")
    variant_ids.append("L_H_L_H_L_H_L_H")
    variant_ids.append("H_L_H_L_H_L_H_L")

    # Gradient patterns
    variant_ids.append("L_L_L_L_M_M_H_H")
    variant_ids.append("H_H_M_M_L_L_L_L")
    variant_ids.append("L_L_M_M_M_M_H_H")
    variant_ids.append("H_H_H_M_M_L_L_L")

    # Mixed patterns (commonly occurring)
    variant_ids.append("M_M_M_M_M_M_M_M")  # All mid
    variant_ids.append("L_M_H_L_M_H_L_M")
    variant_ids.append("M_L_M_H_M_L_M_H")
    variant_ids.append("H_M_L_H_M_L_H_M")

    return list(set(variant_ids))  # Remove duplicates


def _generate_governed_registry() -> Dict[Tuple[str, str, str], P11BTemplate]:
    """
    Generate GOVERNED registry (strict, minimal, certified).

    GOVERNED registry contains only certified template combinations.

    Returns:
        Dictionary mapping (family, variant_id, slot_plan) to template.
    """
    registry: Dict[Tuple[str, str, str], P11BTemplate] = {}

    # All families except DEFAULT (DEFAULT is fallback only)
    families = [f for f in OntologicalFamily if f != OntologicalFamily.DEFAULT]

    # Core slot plans for governed mode
    governed_slot_plans = [
        SlotPlan.MINIMAL,
        SlotPlan.STANDARD,
        SlotPlan.EXTENDED,
    ]

    # Representative variant IDs
    variant_ids = _generate_all_variant_ids()

    for family in families:
        for variant_id in variant_ids:
            for slot_plan in governed_slot_plans:
                template_id = generate_template_id(
                    family, variant_id, slot_plan, RegistryType.GOVERNED
                )
                template_string = build_template_string(family, slot_plan, variant_id)

                template = P11BTemplate(
                    template_id=template_id,
                    family=family,
                    variant_id=variant_id,
                    slot_plan=slot_plan,
                    template_string=template_string,
                    is_fallback=False,
                )
                key = template.get_key().as_tuple()
                registry[key] = template

    return registry


def _generate_open_registry() -> Dict[Tuple[str, str, str], P11BTemplate]:
    """
    Generate OPEN registry (expanded, experimental).

    OPEN registry is a superset of GOVERNED with additional templates.

    Returns:
        Dictionary mapping (family, variant_id, slot_plan) to template.
    """
    # Start with governed registry
    registry = _generate_governed_registry()

    # All families including DEFAULT
    families = list(OntologicalFamily)

    # All slot plans for open mode
    all_slot_plans = list(SlotPlan)

    # Extended variant IDs
    variant_ids = _generate_all_variant_ids()

    # Add additional combinations not in governed
    for family in families:
        for variant_id in variant_ids:
            for slot_plan in all_slot_plans:
                key = (family.value, variant_id, slot_plan.value)

                # Skip if already in registry
                if key in registry:
                    continue

                template_id = generate_template_id(
                    family, variant_id, slot_plan, RegistryType.OPEN
                )
                template_string = build_template_string(family, slot_plan, variant_id)

                is_fallback = (family == OntologicalFamily.DEFAULT)

                template = P11BTemplate(
                    template_id=template_id,
                    family=family,
                    variant_id=variant_id,
                    slot_plan=slot_plan,
                    template_string=template_string,
                    is_fallback=is_fallback,
                )
                registry[key] = template

    return registry


# =============================================================================
# Registry Initialization (Lazy)
# =============================================================================


_GOVERNED_REGISTRY: Optional[Dict[Tuple[str, str, str], P11BTemplate]] = None
_OPEN_REGISTRY: Optional[Dict[Tuple[str, str, str], P11BTemplate]] = None


def _get_governed_registry() -> Dict[Tuple[str, str, str], P11BTemplate]:
    """Get or initialize governed registry."""
    global _GOVERNED_REGISTRY
    if _GOVERNED_REGISTRY is None:
        _GOVERNED_REGISTRY = _generate_governed_registry()
    return _GOVERNED_REGISTRY


def _get_open_registry() -> Dict[Tuple[str, str, str], P11BTemplate]:
    """Get or initialize open registry."""
    global _OPEN_REGISTRY
    if _OPEN_REGISTRY is None:
        _OPEN_REGISTRY = _generate_open_registry()
    return _OPEN_REGISTRY


def get_registry(registry_type: RegistryType) -> Dict[Tuple[str, str, str], P11BTemplate]:
    """
    Get registry by type.

    Args:
        registry_type: GOVERNED or OPEN

    Returns:
        The template registry dictionary.
    """
    if registry_type == RegistryType.GOVERNED:
        return _get_governed_registry()
    else:
        return _get_open_registry()


# =============================================================================
# Template Lookup
# =============================================================================


def lookup_template(
    template_key: TemplateKey,
    registry_type: RegistryType,
) -> P11BTemplate:
    """
    Look up template by key.

    Args:
        template_key: The template key to look up
        registry_type: Which registry to use

    Returns:
        The template for the given key, or fallback if not found.
    """
    registry = get_registry(registry_type)
    key_tuple = template_key.as_tuple()

    if key_tuple in registry:
        return registry[key_tuple]

    # Fallback: create a template preserving the original family
    # This ensures distinct families never collapse to the same output
    template_id = generate_template_id(
        template_key.family,
        template_key.variant_id,
        template_key.slot_plan,
        registry_type,
    )
    template_string = build_template_string(
        template_key.family,
        template_key.slot_plan,
        template_key.variant_id,
    )

    return P11BTemplate(
        template_id=template_id + "_DYNAMIC",
        family=template_key.family,
        variant_id=template_key.variant_id,
        slot_plan=template_key.slot_plan,
        template_string=template_string,
        is_fallback=True,
    )


# =============================================================================
# Template Rendering
# =============================================================================


@dataclass(frozen=True)
class P11BRenderResult:
    """
    Result of Phase-11B template rendering.

    Attributes:
        output_text: The rendered output text
        template_id: The template ID that was used
        template_key: The template key used for lookup
        is_fallback: Whether a fallback template was used
        render_hash: Deterministic hash of the rendering
    """
    output_text: str
    template_id: str
    template_key: TemplateKey
    is_fallback: bool
    render_hash: str

    def __post_init__(self) -> None:
        """Validate P11BRenderResult invariants."""
        if not isinstance(self.output_text, str):
            raise ValueError("P11BRenderResult.output_text must be str")
        if not isinstance(self.template_id, str) or not self.template_id.strip():
            raise ValueError("P11BRenderResult.template_id must be non-empty string")
        if not isinstance(self.template_key, TemplateKey):
            raise ValueError("P11BRenderResult.template_key must be TemplateKey")
        if not isinstance(self.is_fallback, bool):
            raise ValueError("P11BRenderResult.is_fallback must be bool")
        if not isinstance(self.render_hash, str) or len(self.render_hash) != 16:
            raise ValueError("P11BRenderResult.render_hash must be 16-char hex string")


def extract_vc_data(
    phase10_result: Phase10Result,
    slot_plan: SlotPlan,
) -> Dict[str, str]:
    """
    Extract VC data for template placeholders.

    Args:
        phase10_result: Phase10 result with source data
        slot_plan: Slot plan determining which VCs to include

    Returns:
        Dictionary mapping placeholder keys to values.
    """
    vc_facts = SLOT_PLAN_VC_FACTS[slot_plan]
    vc_data: Dict[str, str] = {}

    for vc in vc_facts:
        data_key = vc.lower().replace("-", "_") + "_data"
        if data_key in phase10_result.source_data:
            raw_value = phase10_result.source_data[data_key]
            vc_data[data_key] = str(raw_value)
        else:
            vc_data[data_key] = f"[{vc}:unspecified]"

    return vc_data


def render_template(
    template: P11BTemplate,
    phase10_result: Phase10Result,
    ppv_band_signature: PPVBandSignature,
) -> P11BRenderResult:
    """
    Render template with data.

    Args:
        template: The template to render
        phase10_result: Phase10 result with source data
        ppv_band_signature: PPV band signature

    Returns:
        Render result with output text and metadata.
    """
    # Extract VC data based on slot plan
    vc_data = extract_vc_data(phase10_result, template.slot_plan)

    # Render template (deterministic substitution)
    try:
        output_text = template.template_string.format(**vc_data)
    except KeyError as e:
        # If placeholder not found, use template as-is with error marker
        output_text = f"[RENDER_ERROR:{e}] {template.template_string}"

    # Compute render hash
    hash_input = f"{template.template_id}|{output_text}"
    render_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]

    return P11BRenderResult(
        output_text=output_text,
        template_id=template.template_id,
        template_key=template.get_key(),
        is_fallback=template.is_fallback,
        render_hash=render_hash,
    )


# =============================================================================
# Silent Collapse Prevention
# =============================================================================


@dataclass(frozen=True)
class CollapseValidationResult:
    """
    Result of silent collapse validation.

    Attributes:
        passed: True if no silent collapse detected
        total_keys: Total number of unique keys tested
        total_template_ids: Total number of unique template IDs
        collision_count: Number of key collisions detected
        collision_details: Details of any collisions found
    """
    passed: bool
    total_keys: int
    total_template_ids: int
    collision_count: int
    collision_details: Tuple[str, ...]


def validate_no_silent_collapse(
    registry_type: RegistryType,
    sample_size: int = 100,
) -> CollapseValidationResult:
    """
    Validate that no silent collapse occurs in registry.

    This ensures distinct (family, variant_id, slot_plan) combinations
    produce distinct template_ids.

    Args:
        registry_type: Which registry to validate
        sample_size: Number of random samples to test

    Returns:
        CollapseValidationResult indicating pass/fail.
    """
    registry = get_registry(registry_type)

    # Check all entries in registry
    template_ids: Set[str] = set()
    key_to_template_id: Dict[Tuple[str, str, str], str] = {}
    collisions: List[str] = []

    for key, template in registry.items():
        if template.template_id in template_ids:
            # Find which other key has this template_id
            for other_key, other_template in registry.items():
                if other_key != key and other_template.template_id == template.template_id:
                    collisions.append(
                        f"Collision: {key} and {other_key} -> {template.template_id}"
                    )
                    break
        else:
            template_ids.add(template.template_id)

        key_to_template_id[key] = template.template_id

    passed = len(collisions) == 0

    return CollapseValidationResult(
        passed=passed,
        total_keys=len(registry),
        total_template_ids=len(template_ids),
        collision_count=len(collisions),
        collision_details=tuple(collisions),
    )


def validate_registry_completeness(
    registry_type: RegistryType,
    families: Optional[List[OntologicalFamily]] = None,
    variant_ids: Optional[List[str]] = None,
    slot_plans: Optional[List[SlotPlan]] = None,
) -> bool:
    """
    Validate that registry has entries for expected combinations.

    Args:
        registry_type: Which registry to validate
        families: Families to check (default: all non-DEFAULT)
        variant_ids: Variant IDs to check (default: sample)
        slot_plans: Slot plans to check (default: all)

    Returns:
        True if all expected combinations have entries.
    """
    registry = get_registry(registry_type)

    if families is None:
        if registry_type == RegistryType.GOVERNED:
            families = [f for f in OntologicalFamily if f != OntologicalFamily.DEFAULT]
        else:
            families = list(OntologicalFamily)

    if variant_ids is None:
        variant_ids = _generate_all_variant_ids()[:10]  # Sample

    if slot_plans is None:
        if registry_type == RegistryType.GOVERNED:
            slot_plans = [SlotPlan.MINIMAL, SlotPlan.STANDARD, SlotPlan.EXTENDED]
        else:
            slot_plans = list(SlotPlan)

    missing = 0
    for family in families:
        for variant_id in variant_ids:
            for slot_plan in slot_plans:
                key = (family.value, variant_id, slot_plan.value)
                if key not in registry:
                    missing += 1

    return missing == 0


# =============================================================================
# Registry Statistics
# =============================================================================


def get_registry_stats(registry_type: RegistryType) -> Dict[str, Any]:
    """
    Get statistics about a registry.

    Args:
        registry_type: Which registry to analyze

    Returns:
        Dictionary with registry statistics.
    """
    registry = get_registry(registry_type)

    # Count by family
    family_counts: Dict[str, int] = {}
    for key, template in registry.items():
        family = template.family.value
        family_counts[family] = family_counts.get(family, 0) + 1

    # Count by slot plan
    slot_plan_counts: Dict[str, int] = {}
    for key, template in registry.items():
        slot_plan = template.slot_plan.value
        slot_plan_counts[slot_plan] = slot_plan_counts.get(slot_plan, 0) + 1

    # Count fallbacks
    fallback_count = sum(1 for t in registry.values() if t.is_fallback)

    # Unique template IDs
    unique_ids = len(set(t.template_id for t in registry.values()))

    return {
        "registry_type": registry_type.value,
        "total_templates": len(registry),
        "unique_template_ids": unique_ids,
        "fallback_count": fallback_count,
        "family_counts": family_counts,
        "slot_plan_counts": slot_plan_counts,
    }


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Version
    "P11B_TEMPLATE_VERSION",
    # Dataclasses
    "P11BTemplate",
    "P11BRenderResult",
    "CollapseValidationResult",
    # Functions - Template Building
    "generate_template_id",
    "build_template_string",
    # Functions - Registry
    "get_registry",
    "lookup_template",
    # Functions - Rendering
    "extract_vc_data",
    "render_template",
    # Functions - Validation
    "validate_no_silent_collapse",
    "validate_registry_completeness",
    "get_registry_stats",
]
