"""
P11B Controller Schema - Phase-11B Structural Generator Types
===============================================================

This module defines the data contracts for Phase-11B, the governed
structural generator that fixes Phase-11A's issues:

    - Raw parameter encoding → PPV banding system
    - PPV aggregate collapse → Vector-valued structural routing
    - Unused ontological path → Template family selection
    - Mode producing no differentiation → Registry switching
    - Silent collapse → Registry completeness validation

Phase-11B Design:
    - Ontological path[0] → Template family
    - PPV dimensions → Band signatures (LOW/MID/HIGH)
    - Band signature → Variant ID
    - Mode → Registry selection (GOVERNED/OPEN)
    - Template key: (family, variant_id, slot_plan)

Hard Constraints (NON-NEGOTIABLE):
    - No semantics (no interpretation, no NLP, no embeddings)
    - No learning (no training, no weights)
    - Deterministic core (same input → identical output in GOVERNED)
    - No silent collapse (distinct inputs → distinct templates)

CRITICAL INVARIANTS:
    - PPV bands are fixed: LOW (0-2), MID (3-5), HIGH (6-7)
    - Ontological families map 1:1 to primary layers
    - Template registry has no collisions on distinct keys
    - GOVERNED registry is strict subset of OPEN registry
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum, unique
from typing import Any, Dict, FrozenSet, Literal, Tuple

from symbolu.mechanical.pipeline.p11_controller.p11_schema import (
    Phase10Result,
    RenderMode,
    compute_hash,
)


# =============================================================================
# Version Constant
# =============================================================================

P11B_VERSION = "1.0.0"


# =============================================================================
# Ontological Family Enum (Template Family Selection)
# =============================================================================


@unique
class OntologicalFamily(str, Enum):
    """
    Ontological family derived from primary layer.

    The template_family is selected by ontological_path[0].
    Each family has its own set of templates.

    CRITICAL:
        - 1:1 mapping to primary ontological layer
        - Unknown path → DEFAULT family (fail-closed)
        - Family determines template structure
    """
    # Layer-derived families
    ACTING = "ACTING"                 # Layer 1 - Action-oriented templates
    TAGGING = "TAGGING"               # Layer 2 - Marking templates
    FORMING = "FORMING"               # Layer 3 - Structural templates
    THINKING = "THINKING"             # Layer 4 - Reasoning templates
    DIRECTING = "DIRECTING"           # Layer 5 - Guidance templates
    REASONING = "REASONING"           # Layer 6 - Logic templates
    PURPOSING = "PURPOSING"           # Layer 7 - Goal templates
    META_OBSERVING = "META_OBSERVING" # Layer 8 - Observation templates
    UNIFYING = "UNIFYING"             # Layer 9 - Integration templates
    ABSOLVING = "ABSOLVING"           # Layer 10 - Resolution templates

    # Fallback family
    DEFAULT = "DEFAULT"               # Unknown path → fail-closed to default


# Mapping from layer name to family
LAYER_TO_FAMILY: Dict[str, OntologicalFamily] = {
    "ACTING": OntologicalFamily.ACTING,
    "TAGGING": OntologicalFamily.TAGGING,
    "FORMING": OntologicalFamily.FORMING,
    "THINKING": OntologicalFamily.THINKING,
    "DIRECTING": OntologicalFamily.DIRECTING,
    "REASONING": OntologicalFamily.REASONING,
    "PURPOSING": OntologicalFamily.PURPOSING,
    "META_OBSERVING": OntologicalFamily.META_OBSERVING,
    "UNIFYING": OntologicalFamily.UNIFYING,
    "ABSOLVING": OntologicalFamily.ABSOLVING,
}


def get_template_family(ontological_path: Tuple[str, ...]) -> OntologicalFamily:
    """
    Get template family from ontological path.

    Args:
        ontological_path: Tuple of layer names (e.g., ("THINKING", "DIRECTING"))

    Returns:
        OntologicalFamily based on path[0], or DEFAULT if unknown.
    """
    if not ontological_path:
        return OntologicalFamily.DEFAULT

    primary_layer = ontological_path[0]
    return LAYER_TO_FAMILY.get(primary_layer, OntologicalFamily.DEFAULT)


# =============================================================================
# PPV Band Enum (Vector-Valued Structural Routing)
# =============================================================================


@unique
class PPVBand(str, Enum):
    """
    PPV dimension band for structural routing.

    Each PPV dimension value (0-7) maps to a band:
        - LOW: 0-2 (low intensity)
        - MID: 3-5 (medium intensity)
        - HIGH: 6-7 (high intensity)

    CRITICAL:
        - Bands are fixed and deterministic
        - No overlap between bands
        - Bounds are inclusive
    """
    LOW = "L"   # Values 0, 1, 2
    MID = "M"   # Values 3, 4, 5
    HIGH = "H"  # Values 6, 7


# Band thresholds (inclusive upper bounds)
PPV_BAND_LOW_MAX = 2
PPV_BAND_MID_MAX = 5
PPV_BAND_HIGH_MAX = 7


def get_ppv_band(value: int) -> PPVBand:
    """
    Get PPV band for a dimension value.

    Args:
        value: PPV dimension value (0-7)

    Returns:
        PPVBand corresponding to the value.

    Raises:
        ValueError: If value is out of range [0, 7].
    """
    if value < 0 or value > PPV_BAND_HIGH_MAX:
        raise ValueError(f"PPV value must be in range [0, 7], got {value}")

    if value <= PPV_BAND_LOW_MAX:
        return PPVBand.LOW
    elif value <= PPV_BAND_MID_MAX:
        return PPVBand.MID
    else:
        return PPVBand.HIGH


# =============================================================================
# PPV Band Signature (8-Tuple of Bands)
# =============================================================================


# PPV dimension order (fixed, matches ppv_contract_v1)
PPV_DIM_NAMES: Tuple[str, ...] = (
    "stability_pressure",
    "rhythmic_impulse",
    "discontinuity",
    "continuity",
    "sonority_lift",
    "onset_sharpness",
    "edge_release",
    "edge_tension",
)

PPV_DIM_COUNT = 8


@dataclass(frozen=True)
class PPVBandSignature:
    """
    PPV band signature - 8-tuple of bands for structural routing.

    This is the identity for PPV routing. Different signatures
    may produce different variant IDs.

    Attributes:
        stability_pressure: Band for stability dimension
        rhythmic_impulse: Band for rhythm dimension
        discontinuity: Band for break dimension
        continuity: Band for flow dimension
        sonority_lift: Band for sonority dimension
        onset_sharpness: Band for onset dimension
        edge_release: Band for release dimension
        edge_tension: Band for tension dimension

    Invariants:
        - All 8 dimensions must have a band
        - Bands are deterministically derived from values
        - Same values → same signature
    """
    stability_pressure: PPVBand
    rhythmic_impulse: PPVBand
    discontinuity: PPVBand
    continuity: PPVBand
    sonority_lift: PPVBand
    onset_sharpness: PPVBand
    edge_release: PPVBand
    edge_tension: PPVBand

    def as_tuple(self) -> Tuple[PPVBand, ...]:
        """Return as tuple in canonical order."""
        return (
            self.stability_pressure,
            self.rhythmic_impulse,
            self.discontinuity,
            self.continuity,
            self.sonority_lift,
            self.onset_sharpness,
            self.edge_release,
            self.edge_tension,
        )

    def as_string(self) -> str:
        """Return as string representation (e.g., 'LMHLMHLM')."""
        return "".join(band.value for band in self.as_tuple())

    def signature_hash(self) -> str:
        """Compute deterministic hash of signature."""
        return hashlib.sha256(self.as_string().encode("utf-8")).hexdigest()[:16]


def create_ppv_band_signature(values: Tuple[int, ...]) -> PPVBandSignature:
    """
    Create PPV band signature from raw values.

    Args:
        values: Tuple of 8 PPV values (0-7 each), in order:
            (edge_tension, edge_release, onset_sharpness, sonority_lift,
             continuity, discontinuity, rhythmic_impulse, stability_pressure)

    Returns:
        PPVBandSignature with bands for each dimension.

    Raises:
        ValueError: If values has wrong length or values out of range.
    """
    if len(values) != PPV_DIM_COUNT:
        raise ValueError(
            f"PPV values must have {PPV_DIM_COUNT} elements, got {len(values)}"
        )

    # Values are in contract order (edge_tension first, stability_pressure last)
    # We extract them in the order they appear in the signature
    bands = tuple(get_ppv_band(v) for v in values)

    return PPVBandSignature(
        edge_tension=bands[0],
        edge_release=bands[1],
        onset_sharpness=bands[2],
        sonority_lift=bands[3],
        continuity=bands[4],
        discontinuity=bands[5],
        rhythmic_impulse=bands[6],
        stability_pressure=bands[7],
    )


# =============================================================================
# Variant ID (Composite of Band Signature)
# =============================================================================


def compute_variant_id(band_signature: PPVBandSignature) -> str:
    """
    Compute variant ID from PPV band signature.

    Uses Option 1 - Composite Variant (as per spec):
        variant_id = f"{sp}_{ri}_{disc}_{cont}_{sono}_{onset}_{release}_{tension}"

    This produces a unique variant ID for each distinct band combination.

    Args:
        band_signature: The PPV band signature.

    Returns:
        Variant ID string (e.g., "L_M_H_L_M_H_L_M").
    """
    return (
        f"{band_signature.stability_pressure.value}_"
        f"{band_signature.rhythmic_impulse.value}_"
        f"{band_signature.discontinuity.value}_"
        f"{band_signature.continuity.value}_"
        f"{band_signature.sonority_lift.value}_"
        f"{band_signature.onset_sharpness.value}_"
        f"{band_signature.edge_release.value}_"
        f"{band_signature.edge_tension.value}"
    )


# =============================================================================
# Slot Plan Enum
# =============================================================================


@unique
class SlotPlan(str, Enum):
    """
    Slot plan for template structure.

    Slot plans determine which VC slots are included and their order.
    PPV may influence slot plan selection.

    CRITICAL:
        - Slot plans are fixed
        - PPV influences selection, not content
        - Plans determine structure, not meaning
    """
    # Basic plans
    MINIMAL = "MINIMAL"           # VC-1 only
    STANDARD = "STANDARD"         # VC-1, VC-2
    EXTENDED = "EXTENDED"         # VC-1, VC-2, VC-3
    FULL = "FULL"                 # All VC slots

    # Specialized plans
    OBSERVATION = "OBSERVATION"   # VC-1, VC-3 (observation context)
    REFERENCE = "REFERENCE"       # VC-1, VC-4 (reference based)
    MARKED = "MARKED"             # VC-1, VC-5 (marker focused)


# Slot plan to VC facts mapping
SLOT_PLAN_VC_FACTS: Dict[SlotPlan, Tuple[str, ...]] = {
    SlotPlan.MINIMAL: ("VC-1",),
    SlotPlan.STANDARD: ("VC-1", "VC-2"),
    SlotPlan.EXTENDED: ("VC-1", "VC-2", "VC-3"),
    SlotPlan.FULL: ("VC-1", "VC-2", "VC-3", "VC-4", "VC-5"),
    SlotPlan.OBSERVATION: ("VC-1", "VC-3"),
    SlotPlan.REFERENCE: ("VC-1", "VC-4"),
    SlotPlan.MARKED: ("VC-1", "VC-5"),
}


def get_slot_plan_from_ppv(band_signature: PPVBandSignature) -> SlotPlan:
    """
    Derive slot plan from PPV band signature.

    PPV influences slot selection deterministically:
        - High discontinuity → MINIMAL (fewer slots)
        - High continuity → EXTENDED (more slots)
        - High stability → FULL (all slots)
        - Default → STANDARD

    Args:
        band_signature: The PPV band signature.

    Returns:
        SlotPlan based on PPV characteristics.
    """
    # High discontinuity → fewer slots
    if band_signature.discontinuity == PPVBand.HIGH:
        return SlotPlan.MINIMAL

    # High stability pressure → all slots
    if band_signature.stability_pressure == PPVBand.HIGH:
        return SlotPlan.FULL

    # High continuity → extended slots
    if band_signature.continuity == PPVBand.HIGH:
        return SlotPlan.EXTENDED

    # Default
    return SlotPlan.STANDARD


# =============================================================================
# Template Key (Composite Key for Registry)
# =============================================================================


@dataclass(frozen=True)
class TemplateKey:
    """
    Composite key for template registry lookup.

    Templates are keyed by (family, variant_id, slot_plan).
    Different keys MUST produce different template_ids.

    Attributes:
        family: Template family from ontological path[0]
        variant_id: Variant ID from PPV band signature
        slot_plan: Slot plan for VC inclusion

    Invariants:
        - Different (family, variant_id, slot_plan) → different template_id
        - Same triple → same template_id
        - Missing combination → fallback template (explicitly marked)
    """
    family: OntologicalFamily
    variant_id: str
    slot_plan: SlotPlan

    def __post_init__(self) -> None:
        """Validate TemplateKey invariants."""
        if not isinstance(self.family, OntologicalFamily):
            raise ValueError(
                f"TemplateKey.family must be OntologicalFamily, "
                f"got {type(self.family).__name__}"
            )
        if not isinstance(self.variant_id, str) or not self.variant_id.strip():
            raise ValueError("TemplateKey.variant_id must be non-empty string")
        if not isinstance(self.slot_plan, SlotPlan):
            raise ValueError(
                f"TemplateKey.slot_plan must be SlotPlan, "
                f"got {type(self.slot_plan).__name__}"
            )

    def as_tuple(self) -> Tuple[str, str, str]:
        """Return as tuple for dict key use."""
        return (self.family.value, self.variant_id, self.slot_plan.value)

    def key_hash(self) -> str:
        """Compute deterministic hash of template key."""
        canonical = f"{self.family.value}|{self.variant_id}|{self.slot_plan.value}"
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def create_template_key(
    ontological_path: Tuple[str, ...],
    ppv_values: Tuple[int, ...],
) -> TemplateKey:
    """
    Create template key from ontological path and PPV values.

    Args:
        ontological_path: Tuple of layer names.
        ppv_values: Tuple of 8 PPV values (0-7 each).

    Returns:
        TemplateKey for registry lookup.
    """
    # Get family from path
    family = get_template_family(ontological_path)

    # Get band signature from PPV
    band_signature = create_ppv_band_signature(ppv_values)

    # Get variant ID from band signature
    variant_id = compute_variant_id(band_signature)

    # Get slot plan from PPV
    slot_plan = get_slot_plan_from_ppv(band_signature)

    return TemplateKey(
        family=family,
        variant_id=variant_id,
        slot_plan=slot_plan,
    )


# =============================================================================
# Registry Type Enum (Mode → Registry Switching)
# =============================================================================


@unique
class RegistryType(str, Enum):
    """
    Registry type for mode-based switching.

    Mode MUST affect generation by switching registries:
        - GOVERNED: Strict, minimal, certified templates
        - OPEN: Expanded, experimental templates

    CRITICAL:
        - GOVERNED registry is strict subset of OPEN
        - Mode switches registry, not PPV interpretation
        - Both registries have no collisions
    """
    GOVERNED = "GOVERNED"   # Strict, certified templates only
    OPEN = "OPEN"           # All templates including experimental


def get_registry_type(render_mode: RenderMode) -> RegistryType:
    """
    Get registry type from render mode.

    Args:
        render_mode: The render mode (OPEN or GOVERNED).

    Returns:
        RegistryType for template lookup.
    """
    if render_mode == RenderMode.GOVERNED:
        return RegistryType.GOVERNED
    else:
        return RegistryType.OPEN


# =============================================================================
# Phase11B Request (Extended from Phase11)
# =============================================================================


@dataclass(frozen=True)
class Phase11BRequest:
    """
    Phase-11B input contract for governed structural generation.

    Extends Phase11Request with:
        - Explicit ontological_path for family selection
        - PPV values for band-based variant routing

    Attributes:
        artifact_id: Opaque artifact identifier
        artifact_hash: Precomputed artifact hash (64-char hex)
        phase10_result: Opaque Phase10Result from upstream
        ontological_path: Tuple of layer names for path routing
        ppv_values: Tuple of 8 PPV values (0-7 each)
        render_mode: OPEN (experimentation) or GOVERNED (production)
        explicit_absolving_opt_in: Explicit opt-in for ABSOLVING

    Invariants:
        - ontological_path must have at least 1 layer
        - ppv_values must have exactly 8 elements in range [0, 7]
        - All fields immutable after construction
    """
    artifact_id: str
    artifact_hash: str
    phase10_result: Phase10Result
    ontological_path: Tuple[str, ...]
    ppv_values: Tuple[int, ...]
    render_mode: RenderMode
    explicit_absolving_opt_in: bool = False

    def __post_init__(self) -> None:
        """Validate Phase11BRequest invariants."""
        # Validate artifact_id
        if not isinstance(self.artifact_id, str):
            raise ValueError(
                f"Phase11BRequest.artifact_id must be str, "
                f"got {type(self.artifact_id).__name__}"
            )
        if len(self.artifact_id) == 0:
            raise ValueError("Phase11BRequest.artifact_id must be non-empty")

        # Validate artifact_hash (64 hex chars)
        if not isinstance(self.artifact_hash, str):
            raise ValueError(
                f"Phase11BRequest.artifact_hash must be str, "
                f"got {type(self.artifact_hash).__name__}"
            )
        if len(self.artifact_hash) != 64:
            raise ValueError(
                f"Phase11BRequest.artifact_hash must be 64 hex chars, "
                f"got {len(self.artifact_hash)} chars"
            )
        try:
            int(self.artifact_hash, 16)
        except ValueError:
            raise ValueError(
                "Phase11BRequest.artifact_hash must contain only hex characters"
            )

        # Validate phase10_result
        if not isinstance(self.phase10_result, Phase10Result):
            raise ValueError(
                f"Phase11BRequest.phase10_result must be Phase10Result, "
                f"got {type(self.phase10_result).__name__}"
            )

        # Validate ontological_path
        if not isinstance(self.ontological_path, tuple):
            raise ValueError(
                f"Phase11BRequest.ontological_path must be tuple, "
                f"got {type(self.ontological_path).__name__}"
            )
        if len(self.ontological_path) == 0:
            raise ValueError("Phase11BRequest.ontological_path must have at least 1 layer")
        for layer in self.ontological_path:
            if not isinstance(layer, str):
                raise ValueError(
                    f"Phase11BRequest.ontological_path elements must be str, "
                    f"got {type(layer).__name__}"
                )

        # Validate ppv_values
        if not isinstance(self.ppv_values, tuple):
            raise ValueError(
                f"Phase11BRequest.ppv_values must be tuple, "
                f"got {type(self.ppv_values).__name__}"
            )
        if len(self.ppv_values) != PPV_DIM_COUNT:
            raise ValueError(
                f"Phase11BRequest.ppv_values must have exactly {PPV_DIM_COUNT} elements, "
                f"got {len(self.ppv_values)}"
            )
        for i, val in enumerate(self.ppv_values):
            if not isinstance(val, int):
                raise ValueError(
                    f"Phase11BRequest.ppv_values[{i}] must be int, "
                    f"got {type(val).__name__}"
                )
            if val < 0 or val > PPV_BAND_HIGH_MAX:
                raise ValueError(
                    f"Phase11BRequest.ppv_values[{i}] must be in range [0, 7], "
                    f"got {val}"
                )

        # Validate render_mode
        if not isinstance(self.render_mode, RenderMode):
            raise ValueError(
                f"Phase11BRequest.render_mode must be RenderMode, "
                f"got {type(self.render_mode).__name__}"
            )
        if self.render_mode not in (RenderMode.OPEN, RenderMode.GOVERNED):
            raise ValueError(
                f"Phase11BRequest.render_mode must be OPEN or GOVERNED, "
                f"got {self.render_mode}"
            )

        # Validate explicit_absolving_opt_in
        if not isinstance(self.explicit_absolving_opt_in, bool):
            raise ValueError(
                f"Phase11BRequest.explicit_absolving_opt_in must be bool, "
                f"got {type(self.explicit_absolving_opt_in).__name__}"
            )

    def get_template_key(self) -> TemplateKey:
        """Get template key for this request."""
        return create_template_key(self.ontological_path, self.ppv_values)

    def get_registry_type(self) -> RegistryType:
        """Get registry type based on render mode."""
        return get_registry_type(self.render_mode)

    def get_ppv_band_signature(self) -> PPVBandSignature:
        """Get PPV band signature."""
        return create_ppv_band_signature(self.ppv_values)

    def request_hash(self) -> str:
        """Compute deterministic hash of request."""
        canonical = (
            f"artifact_id:{self.artifact_id}|"
            f"artifact_hash:{self.artifact_hash}|"
            f"path:{self.ontological_path}|"
            f"ppv:{self.ppv_values}|"
            f"mode:{self.render_mode.value}"
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# =============================================================================
# Phase11B Response
# =============================================================================


@dataclass(frozen=True)
class Phase11BResponse:
    """
    Phase-11B output contract for governed structural generation.

    Extends Phase11Response with:
        - template_key: The composite key used for template lookup
        - template_id: The unique template identifier
        - registry_used: Which registry was used (GOVERNED/OPEN)

    Attributes:
        output_text: The rendered output text, or "RENDER_BLOCKED" if blocked
        verifier_passed: Whether the verifier check passed
        verifier_report_hash: Hash of verifier report (16-char hex)
        candidate_output_hash: Hash of candidate output (16-char hex)
        mode_applied: The RenderMode that was applied
        ledger_span_id: Deterministic span ID for ledger
        template_key: The TemplateKey used for lookup
        template_id: The unique template identifier
        registry_used: The registry type used

    Invariants:
        - GOVERNED mode with failed verifier → RENDER_BLOCKED
        - template_id is unique for each distinct template_key
        - Same inputs → same template_id (deterministic)
    """
    output_text: str | Literal["RENDER_BLOCKED"]
    verifier_passed: bool
    verifier_report_hash: str
    candidate_output_hash: str
    mode_applied: RenderMode
    ledger_span_id: str
    template_key: TemplateKey
    template_id: str
    registry_used: RegistryType

    def __post_init__(self) -> None:
        """Validate Phase11BResponse invariants."""
        # Validate output_text
        if not isinstance(self.output_text, str):
            raise ValueError(
                f"Phase11BResponse.output_text must be str, "
                f"got {type(self.output_text).__name__}"
            )

        # Validate verifier_passed
        if not isinstance(self.verifier_passed, bool):
            raise ValueError(
                f"Phase11BResponse.verifier_passed must be bool, "
                f"got {type(self.verifier_passed).__name__}"
            )

        # Validate hash fields (16-char hex)
        for field_name, field_value in [
            ("verifier_report_hash", self.verifier_report_hash),
            ("candidate_output_hash", self.candidate_output_hash),
        ]:
            if not isinstance(field_value, str):
                raise ValueError(
                    f"Phase11BResponse.{field_name} must be str, "
                    f"got {type(field_value).__name__}"
                )
            if len(field_value) != 16:
                raise ValueError(
                    f"Phase11BResponse.{field_name} must be 16 hex chars, "
                    f"got {len(field_value)} chars"
                )
            try:
                int(field_value, 16)
            except ValueError:
                raise ValueError(
                    f"Phase11BResponse.{field_name} must contain only hex characters"
                )

        # Validate mode_applied
        if not isinstance(self.mode_applied, RenderMode):
            raise ValueError(
                f"Phase11BResponse.mode_applied must be RenderMode, "
                f"got {type(self.mode_applied).__name__}"
            )

        # Validate ledger_span_id
        if not isinstance(self.ledger_span_id, str) or not self.ledger_span_id.strip():
            raise ValueError("Phase11BResponse.ledger_span_id must be non-empty string")

        # Validate template_key
        if not isinstance(self.template_key, TemplateKey):
            raise ValueError(
                f"Phase11BResponse.template_key must be TemplateKey, "
                f"got {type(self.template_key).__name__}"
            )

        # Validate template_id
        if not isinstance(self.template_id, str) or not self.template_id.strip():
            raise ValueError("Phase11BResponse.template_id must be non-empty string")

        # Validate registry_used
        if not isinstance(self.registry_used, RegistryType):
            raise ValueError(
                f"Phase11BResponse.registry_used must be RegistryType, "
                f"got {type(self.registry_used).__name__}"
            )

        # CRITICAL INVARIANT: GOVERNED mode with failed verifier → RENDER_BLOCKED
        if (self.mode_applied == RenderMode.GOVERNED and
                not self.verifier_passed and
                self.output_text != "RENDER_BLOCKED"):
            raise ValueError(
                "Phase11BResponse: GOVERNED mode with verifier_passed=False "
                "MUST have output_text='RENDER_BLOCKED'"
            )

    def is_blocked(self) -> bool:
        """Check if output was blocked."""
        return self.output_text == "RENDER_BLOCKED"

    def was_governed(self) -> bool:
        """Check if GOVERNED mode was applied."""
        return self.mode_applied == RenderMode.GOVERNED


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Version
    "P11B_VERSION",
    # Constants
    "PPV_DIM_COUNT",
    "PPV_DIM_NAMES",
    "PPV_BAND_LOW_MAX",
    "PPV_BAND_MID_MAX",
    "PPV_BAND_HIGH_MAX",
    "LAYER_TO_FAMILY",
    "SLOT_PLAN_VC_FACTS",
    # Enums
    "OntologicalFamily",
    "PPVBand",
    "SlotPlan",
    "RegistryType",
    # Dataclasses
    "PPVBandSignature",
    "TemplateKey",
    "Phase11BRequest",
    "Phase11BResponse",
    # Functions
    "get_template_family",
    "get_ppv_band",
    "create_ppv_band_signature",
    "compute_variant_id",
    "get_slot_plan_from_ppv",
    "create_template_key",
    "get_registry_type",
]
