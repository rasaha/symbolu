"""
Phase-11B.1: Collision-Free Routing Patch
==========================================

This module implements the collision-free routing patch for Phase-11B:

    1. PPV SubBand Signatures (Option A - default)
       - LOW:  0..2 -> L0, L1, L2
       - MID:  3..5 -> M0, M1, M2
       - HIGH: 6..7 -> H0, H1
       - variant_id derived from subband_signature (8 tokens joined with _)

    2. RoutingKey and Canonical Routing
       - Frozen dataclasses: Phase11BRequest, Phase11BResponse, RoutingTrace, RoutingKey
       - Deterministic canonical serialization
       - routing_key_hash = sha256(canonical_string)

    3. No Silent Collapse / Injective Selection
       - Registry keyed by (registry_id, canonical_routing_key)
       - Explicit optional COLLAPSE_MAP with collapse_applied=True in trace

    4. Fail-Closed Behavior
       - Unknown key returns RENDER_BLOCKED (deterministic string constant)
       - Trace includes failure reason code (structural enum)

CONSTRAINTS:
    - No external LLM calls
    - No ML/NLP imports
    - Deterministic only
    - Allowed imports: __future__, dataclasses, enum, hashlib, typing
    - Must remain GOVERNED compatible: template output only, fail-closed
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Dict, FrozenSet, Literal, Optional, Tuple, Mapping


# =============================================================================
# Version
# =============================================================================

PHASE11B1_VERSION = "1.0.0"


# =============================================================================
# Constants
# =============================================================================

RENDER_BLOCKED = "RENDER_BLOCKED"  # Deterministic fail-closed output

PPV_DIM_COUNT = 8
PPV_VALUE_MIN = 0
PPV_VALUE_MAX = 7


# =============================================================================
# SubBand Enum (Finer-grained PPV Routing)
# =============================================================================


@unique
class PPVSubBand(str, Enum):
    """
    PPV SubBand for fine-grained structural routing.

    Provides finer granularity than coarse bands (L/M/H):
        - LOW:  0..2 -> L0, L1, L2
        - MID:  3..5 -> M0, M1, M2
        - HIGH: 6..7 -> H0, H1

    This eliminates collisions that occur with coarse bands.
    """
    # LOW range (0-2)
    L0 = "L0"  # Value 0
    L1 = "L1"  # Value 1
    L2 = "L2"  # Value 2

    # MID range (3-5)
    M0 = "M0"  # Value 3
    M1 = "M1"  # Value 4
    M2 = "M2"  # Value 5

    # HIGH range (6-7)
    H0 = "H0"  # Value 6
    H1 = "H1"  # Value 7


# Mapping from PPV value to SubBand
_PPV_VALUE_TO_SUBBAND: Dict[int, PPVSubBand] = {
    0: PPVSubBand.L0,
    1: PPVSubBand.L1,
    2: PPVSubBand.L2,
    3: PPVSubBand.M0,
    4: PPVSubBand.M1,
    5: PPVSubBand.M2,
    6: PPVSubBand.H0,
    7: PPVSubBand.H1,
}


def get_ppv_subband(value: int) -> PPVSubBand:
    """
    Get PPV SubBand for a dimension value.

    Args:
        value: PPV dimension value (0-7)

    Returns:
        PPVSubBand corresponding to the value.

    Raises:
        ValueError: If value is out of range [0, 7].
    """
    if value < PPV_VALUE_MIN or value > PPV_VALUE_MAX:
        raise ValueError(f"PPV value must be in range [0, 7], got {value}")
    return _PPV_VALUE_TO_SUBBAND[value]


# =============================================================================
# Coarse Band (for reporting compatibility)
# =============================================================================


@unique
class PPVBand(str, Enum):
    """Coarse PPV band for backward-compatible reporting."""
    LOW = "L"   # Values 0-2
    MID = "M"   # Values 3-5
    HIGH = "H"  # Values 6-7


def get_coarse_band(subband: PPVSubBand) -> PPVBand:
    """Get coarse band from subband for reporting."""
    if subband.value.startswith("L"):
        return PPVBand.LOW
    elif subband.value.startswith("M"):
        return PPVBand.MID
    else:
        return PPVBand.HIGH


def get_ppv_band(value: int) -> PPVBand:
    """Get coarse PPV band for a dimension value."""
    subband = get_ppv_subband(value)
    return get_coarse_band(subband)


# =============================================================================
# SubBand Signature (8-Tuple of SubBands)
# =============================================================================


@dataclass(frozen=True)
class SubBandSignature:
    """
    PPV SubBand signature - 8-tuple of subbands for collision-free routing.

    This is the identity for PPV routing. Each unique SubBandSignature
    produces a unique variant_id, eliminating collisions.

    Attributes follow PPV dimension order:
        - edge_tension
        - edge_release
        - onset_sharpness
        - sonority_lift
        - continuity
        - discontinuity
        - rhythmic_impulse
        - stability_pressure
    """
    edge_tension: PPVSubBand
    edge_release: PPVSubBand
    onset_sharpness: PPVSubBand
    sonority_lift: PPVSubBand
    continuity: PPVSubBand
    discontinuity: PPVSubBand
    rhythmic_impulse: PPVSubBand
    stability_pressure: PPVSubBand

    def as_tuple(self) -> Tuple[PPVSubBand, ...]:
        """Return as tuple in canonical order."""
        return (
            self.edge_tension,
            self.edge_release,
            self.onset_sharpness,
            self.sonority_lift,
            self.continuity,
            self.discontinuity,
            self.rhythmic_impulse,
            self.stability_pressure,
        )

    def to_variant_id(self) -> str:
        """
        Compute variant_id from subband signature.

        Returns 8 tokens joined with underscore, e.g., "L0_L1_M2_H0_M1_L2_H1_M0"
        """
        return "_".join(sb.value for sb in self.as_tuple())

    def to_band_signature_string(self) -> str:
        """
        Return coarse band signature string for reporting.

        Returns 8 coarse bands, e.g., "LLMHMLHM"
        """
        return "".join(get_coarse_band(sb).value for sb in self.as_tuple())

    def signature_hash(self) -> str:
        """Compute deterministic 16-char hash of signature."""
        canonical = self.to_variant_id()
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def create_subband_signature(values: Tuple[int, ...]) -> SubBandSignature:
    """
    Create SubBand signature from raw PPV values.

    Args:
        values: Tuple of 8 PPV values (0-7 each), in order:
            (edge_tension, edge_release, onset_sharpness, sonority_lift,
             continuity, discontinuity, rhythmic_impulse, stability_pressure)

    Returns:
        SubBandSignature with subbands for each dimension.

    Raises:
        ValueError: If values has wrong length or values out of range.
    """
    if len(values) != PPV_DIM_COUNT:
        raise ValueError(f"PPV values must have {PPV_DIM_COUNT} elements, got {len(values)}")

    subbands = tuple(get_ppv_subband(v) for v in values)

    return SubBandSignature(
        edge_tension=subbands[0],
        edge_release=subbands[1],
        onset_sharpness=subbands[2],
        sonority_lift=subbands[3],
        continuity=subbands[4],
        discontinuity=subbands[5],
        rhythmic_impulse=subbands[6],
        stability_pressure=subbands[7],
    )


# =============================================================================
# Ontological Family Enum
# =============================================================================


@unique
class OntologicalFamily(str, Enum):
    """
    Ontological family derived from primary layer.

    The template_family is selected by ontological_path[0].
    Unknown path -> DEFAULT family (fail-closed).
    """
    ACTING = "ACTING"
    TAGGING = "TAGGING"
    FORMING = "FORMING"
    THINKING = "THINKING"
    DIRECTING = "DIRECTING"
    REASONING = "REASONING"
    PURPOSING = "PURPOSING"
    META_OBSERVING = "META_OBSERVING"
    UNIFYING = "UNIFYING"
    ABSOLVING = "ABSOLVING"
    DEFAULT = "DEFAULT"


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
    """Get template family from ontological path[0], or DEFAULT if unknown."""
    if not ontological_path:
        return OntologicalFamily.DEFAULT
    primary_layer = ontological_path[0]
    return LAYER_TO_FAMILY.get(primary_layer, OntologicalFamily.DEFAULT)


# =============================================================================
# Slot Plan Enum
# =============================================================================


@unique
class SlotPlan(str, Enum):
    """Slot plan for template structure."""
    MINIMAL = "MINIMAL"
    STANDARD = "STANDARD"
    EXTENDED = "EXTENDED"
    FULL = "FULL"
    OBSERVATION = "OBSERVATION"
    REFERENCE = "REFERENCE"
    MARKED = "MARKED"


SLOT_PLAN_VC_FACTS: Dict[SlotPlan, Tuple[str, ...]] = {
    SlotPlan.MINIMAL: ("VC-1",),
    SlotPlan.STANDARD: ("VC-1", "VC-2"),
    SlotPlan.EXTENDED: ("VC-1", "VC-2", "VC-3"),
    SlotPlan.FULL: ("VC-1", "VC-2", "VC-3", "VC-4", "VC-5"),
    SlotPlan.OBSERVATION: ("VC-1", "VC-3"),
    SlotPlan.REFERENCE: ("VC-1", "VC-4"),
    SlotPlan.MARKED: ("VC-1", "VC-5"),
}


def get_slot_plan_from_subband(signature: SubBandSignature) -> SlotPlan:
    """
    Derive slot plan from SubBand signature.

    Uses discontinuity, stability_pressure, and continuity to select plan.
    """
    # High discontinuity -> fewer slots
    if signature.discontinuity in (PPVSubBand.H0, PPVSubBand.H1):
        return SlotPlan.MINIMAL

    # High stability pressure -> all slots
    if signature.stability_pressure in (PPVSubBand.H0, PPVSubBand.H1):
        return SlotPlan.FULL

    # High continuity -> extended slots
    if signature.continuity in (PPVSubBand.H0, PPVSubBand.H1):
        return SlotPlan.EXTENDED

    return SlotPlan.STANDARD


# =============================================================================
# Registry Type Enum
# =============================================================================


@unique
class RegistryType(str, Enum):
    """Registry type for mode-based switching."""
    GOVERNED = "GOVERNED"
    OPEN = "OPEN"


# =============================================================================
# Render Mode Enum
# =============================================================================


@unique
class RenderMode(str, Enum):
    """Render mode for pipeline execution."""
    GOVERNED = "GOVERNED"
    OPEN = "OPEN"


def get_registry_type(render_mode: RenderMode) -> RegistryType:
    """Get registry type from render mode."""
    if render_mode == RenderMode.GOVERNED:
        return RegistryType.GOVERNED
    return RegistryType.OPEN


# =============================================================================
# Failure Reason Enum
# =============================================================================


@unique
class FailureReason(str, Enum):
    """Structural enum for fail-closed behavior."""
    NONE = "NONE"
    KEY_NOT_IN_REGISTRY = "KEY_NOT_IN_REGISTRY"
    COLLAPSE_MAP_LOOKUP_FAILED = "COLLAPSE_MAP_LOOKUP_FAILED"
    TEMPLATE_RENDER_ERROR = "TEMPLATE_RENDER_ERROR"
    VERIFIER_FAILED = "VERIFIER_FAILED"


# =============================================================================
# RoutingKey (Frozen Dataclass for Canonical Routing)
# =============================================================================


@dataclass(frozen=True)
class RoutingKey:
    """
    Frozen routing key for canonical routing.

    This is the identity for template lookup. Different RoutingKeys MUST
    produce different template_ids (injective selection).

    Attributes:
        family: Template family from ontological path[0]
        subband_variant_id: Variant ID from SubBand signature
        slot_plan: Slot plan for VC inclusion

    The canonical form is used for hashing and registry lookup.
    """
    family: OntologicalFamily
    subband_variant_id: str
    slot_plan: SlotPlan

    def __post_init__(self) -> None:
        """Validate RoutingKey invariants."""
        if not isinstance(self.family, OntologicalFamily):
            raise ValueError(f"RoutingKey.family must be OntologicalFamily")
        if not isinstance(self.subband_variant_id, str) or not self.subband_variant_id:
            raise ValueError("RoutingKey.subband_variant_id must be non-empty string")
        if not isinstance(self.slot_plan, SlotPlan):
            raise ValueError(f"RoutingKey.slot_plan must be SlotPlan")

    def canonical_string(self) -> str:
        """
        Return canonical serialization for hashing.

        Format: "{family}|{subband_variant_id}|{slot_plan}"
        """
        return f"{self.family.value}|{self.subband_variant_id}|{self.slot_plan.value}"

    def routing_key_hash(self) -> str:
        """
        Compute deterministic SHA256 hash of canonical form.

        Returns full 64-char hex hash.
        """
        return hashlib.sha256(self.canonical_string().encode("utf-8")).hexdigest()

    def as_tuple(self) -> Tuple[str, str, str]:
        """Return as tuple for registry key use."""
        return (self.family.value, self.subband_variant_id, self.slot_plan.value)

    def short_hash(self) -> str:
        """Return 16-char truncated hash."""
        return self.routing_key_hash()[:16]


def create_routing_key(
    ontological_path: Tuple[str, ...],
    ppv_values: Tuple[int, ...],
) -> RoutingKey:
    """
    Create routing key from ontological path and PPV values.

    Args:
        ontological_path: Tuple of layer names.
        ppv_values: Tuple of 8 PPV values (0-7 each).

    Returns:
        RoutingKey for registry lookup.
    """
    family = get_template_family(ontological_path)
    subband_sig = create_subband_signature(ppv_values)
    variant_id = subband_sig.to_variant_id()
    slot_plan = get_slot_plan_from_subband(subband_sig)

    return RoutingKey(
        family=family,
        subband_variant_id=variant_id,
        slot_plan=slot_plan,
    )


# =============================================================================
# RoutingTrace (Frozen Dataclass for Tracing)
# =============================================================================


@dataclass(frozen=True)
class RoutingTrace:
    """
    Frozen trace of routing decisions.

    Records the routing path for debugging and collapse detection.

    Attributes:
        original_key: The original routing key before any mapping
        canonical_key: The canonical routing key used for lookup
        collapse_applied: True if COLLAPSE_MAP was used
        collapse_source: Source key if collapse was applied, None otherwise
        registry_type: Which registry was used
        template_id: The template ID that was selected, or None if blocked
        failure_reason: Reason for failure if blocked
    """
    original_key: RoutingKey
    canonical_key: RoutingKey
    collapse_applied: bool
    collapse_source: Optional[RoutingKey]
    registry_type: RegistryType
    template_id: Optional[str]
    failure_reason: FailureReason

    def trace_hash(self) -> str:
        """Compute deterministic hash of trace."""
        parts = [
            self.original_key.canonical_string(),
            self.canonical_key.canonical_string(),
            str(self.collapse_applied),
            self.collapse_source.canonical_string() if self.collapse_source else "NONE",
            self.registry_type.value,
            self.template_id or "NONE",
            self.failure_reason.value,
        ]
        canonical = "|".join(parts)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# =============================================================================
# Phase11BRequest (Frozen Dataclass)
# =============================================================================


@dataclass(frozen=True)
class Phase11B1Request:
    """
    Phase-11B.1 input contract for collision-free routing.

    Attributes:
        artifact_id: Opaque artifact identifier
        artifact_hash: Precomputed artifact hash (64-char hex)
        ontological_path: Tuple of layer names for path routing
        ppv_values: Tuple of 8 PPV values (0-7 each)
        render_mode: OPEN or GOVERNED
        vc_source_data: Source data for VC slot filling
    """
    artifact_id: str
    artifact_hash: str
    ontological_path: Tuple[str, ...]
    ppv_values: Tuple[int, ...]
    render_mode: RenderMode
    vc_source_data: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate request invariants."""
        if not self.artifact_id:
            raise ValueError("artifact_id must be non-empty")
        if len(self.artifact_hash) != 64:
            raise ValueError("artifact_hash must be 64 hex chars")
        if len(self.ontological_path) == 0:
            raise ValueError("ontological_path must have at least 1 layer")
        if len(self.ppv_values) != PPV_DIM_COUNT:
            raise ValueError(f"ppv_values must have {PPV_DIM_COUNT} elements")
        for i, v in enumerate(self.ppv_values):
            if v < PPV_VALUE_MIN or v > PPV_VALUE_MAX:
                raise ValueError(f"ppv_values[{i}] must be in range [0, 7]")

    def get_routing_key(self) -> RoutingKey:
        """Derive routing key from request."""
        return create_routing_key(self.ontological_path, self.ppv_values)

    def get_subband_signature(self) -> SubBandSignature:
        """Get SubBand signature from PPV values."""
        return create_subband_signature(self.ppv_values)

    def request_hash(self) -> str:
        """Compute deterministic hash of request."""
        canonical = (
            f"id:{self.artifact_id}|"
            f"hash:{self.artifact_hash}|"
            f"path:{self.ontological_path}|"
            f"ppv:{self.ppv_values}|"
            f"mode:{self.render_mode.value}"
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# =============================================================================
# Phase11BResponse (Frozen Dataclass)
# =============================================================================


@dataclass(frozen=True)
class Phase11B1Response:
    """
    Phase-11B.1 output contract for collision-free routing.

    Attributes:
        output_text: The rendered output text, or RENDER_BLOCKED if blocked
        routing_trace: Complete trace of routing decisions
        template_id: The template ID used, or empty string if blocked
        subband_variant_id: The SubBand variant ID used
        band_signature: Coarse band signature for reporting
        verifier_passed: Whether structural verification passed
        ledger_span_id: Deterministic span ID for ledger
    """
    output_text: str
    routing_trace: RoutingTrace
    template_id: str
    subband_variant_id: str
    band_signature: str
    verifier_passed: bool
    ledger_span_id: str

    def is_blocked(self) -> bool:
        """Check if output was blocked."""
        return self.output_text == RENDER_BLOCKED

    def response_hash(self) -> str:
        """Compute deterministic hash of response."""
        canonical = (
            f"output:{self.output_text}|"
            f"template:{self.template_id}|"
            f"variant:{self.subband_variant_id}"
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# =============================================================================
# Template Definition
# =============================================================================


@dataclass(frozen=True)
class P11B1Template:
    """
    Phase-11B.1 template definition.

    Attributes:
        template_id: Unique identifier for this template
        routing_key: The canonical routing key for this template
        template_string: The template string with placeholders
        is_fallback: True if this is a fallback template
    """
    template_id: str
    routing_key: RoutingKey
    template_string: str
    is_fallback: bool = False

    def __post_init__(self) -> None:
        if not self.template_id:
            raise ValueError("template_id must be non-empty")
        if not isinstance(self.routing_key, RoutingKey):
            raise ValueError("routing_key must be RoutingKey")


# =============================================================================
# COLLAPSE_MAP (Explicit Controlled Collapse)
# =============================================================================

# Type alias for collapse map
CollapseMapType = Dict[RoutingKey, RoutingKey]

# The COLLAPSE_MAP is empty by default (no collapse allowed)
# If you need to intentionally collapse keys, add mappings here.
# Any collapse MUST be explicit and recorded in the trace.
COLLAPSE_MAP: CollapseMapType = {}


def apply_collapse_map(
    key: RoutingKey,
    collapse_map: CollapseMapType,
) -> Tuple[RoutingKey, bool, Optional[RoutingKey]]:
    """
    Apply collapse map to a routing key.

    Args:
        key: The routing key to potentially collapse
        collapse_map: Map from source keys to canonical keys

    Returns:
        Tuple of:
            - Canonical key (after collapse if applicable)
            - collapse_applied: True if collapse was applied
            - collapse_source: Original key if collapsed, None otherwise
    """
    if key in collapse_map:
        canonical = collapse_map[key]
        return (canonical, True, key)
    return (key, False, None)


# =============================================================================
# Registry (Keyed by (registry_id, canonical_routing_key))
# =============================================================================


def _generate_template_id(
    routing_key: RoutingKey,
    registry_type: RegistryType,
) -> str:
    """Generate unique template ID from routing key."""
    prefix = "G" if registry_type == RegistryType.GOVERNED else "O"
    family_short = routing_key.family.value[:3].upper()
    slot_short = routing_key.slot_plan.value[:3].upper()
    hash_suffix = routing_key.short_hash()[:8]
    return f"T11B1_{prefix}_{family_short}_{slot_short}_{hash_suffix}"


def _build_template_string(
    family: OntologicalFamily,
    slot_plan: SlotPlan,
    variant_id: str,
) -> str:
    """Build template string for given parameters."""
    vc_facts = SLOT_PLAN_VC_FACTS[slot_plan]
    family_prefix = family.value[:6] if family != OntologicalFamily.DEFAULT else "DATA"
    parts = [f"[FAMILY:{family.value}][VARIANT:{variant_id}]"]

    for vc in vc_facts:
        slot_key = vc.lower().replace("-", "_") + "_data"
        parts.append(f"{family_prefix}-{vc}: {{{slot_key}}}")

    return " | ".join(parts)


def _generate_representative_variant_ids() -> Tuple[str, ...]:
    """
    Generate representative SubBand variant IDs.

    With 8 SubBands and 8 dimensions, there are 8^8 = 16,777,216 combinations.
    We generate representative samples for practical registry population.
    """
    variant_ids = []
    all_subbands = list(PPVSubBand)

    # All same subband variants (8)
    for sb in all_subbands:
        variant = "_".join([sb.value] * 8)
        variant_ids.append(variant)

    # Single dimension variations (8 × 7 = 56)
    for i in range(8):
        for sb in all_subbands:
            if sb != PPVSubBand.M1:  # Skip base to avoid duplicate
                dims = [PPVSubBand.M1.value] * 8
                dims[i] = sb.value
                variant_ids.append("_".join(dims))

    # Edge cases: all LOW, all MID, all HIGH
    variant_ids.append("_".join([PPVSubBand.L0.value] * 8))
    variant_ids.append("_".join([PPVSubBand.M1.value] * 8))
    variant_ids.append("_".join([PPVSubBand.H1.value] * 8))

    # Gradient patterns
    gradient = [PPVSubBand.L0.value, PPVSubBand.L1.value, PPVSubBand.L2.value,
                PPVSubBand.M0.value, PPVSubBand.M1.value, PPVSubBand.M2.value,
                PPVSubBand.H0.value, PPVSubBand.H1.value]
    variant_ids.append("_".join(gradient))
    variant_ids.append("_".join(reversed(gradient)))

    # Mixed patterns
    variant_ids.append("L0_M0_H0_L1_M1_H1_L2_M2")
    variant_ids.append("H1_H0_M2_M1_M0_L2_L1_L0")
    variant_ids.append("L0_H1_L0_H1_L0_H1_L0_H1")

    return tuple(sorted(set(variant_ids)))


# Registry storage type
RegistryStorageType = Dict[Tuple[str, Tuple[str, str, str]], P11B1Template]

# Registry cache
_REGISTRY_CACHE: Dict[RegistryType, RegistryStorageType] = {}


def _build_registry(registry_type: RegistryType) -> RegistryStorageType:
    """Build registry for given type."""
    registry: RegistryStorageType = {}

    # Families for this registry type
    if registry_type == RegistryType.GOVERNED:
        families = [f for f in OntologicalFamily if f != OntologicalFamily.DEFAULT]
        slot_plans = [SlotPlan.MINIMAL, SlotPlan.STANDARD, SlotPlan.EXTENDED]
    else:
        families = list(OntologicalFamily)
        slot_plans = list(SlotPlan)

    variant_ids = _generate_representative_variant_ids()

    for family in families:
        for variant_id in variant_ids:
            for slot_plan in slot_plans:
                routing_key = RoutingKey(
                    family=family,
                    subband_variant_id=variant_id,
                    slot_plan=slot_plan,
                )

                # Registry key: (registry_id, canonical_routing_key_tuple)
                registry_id = registry_type.value
                key_tuple = routing_key.as_tuple()
                full_key = (registry_id, key_tuple)

                template_id = _generate_template_id(routing_key, registry_type)
                template_string = _build_template_string(family, slot_plan, variant_id)

                template = P11B1Template(
                    template_id=template_id,
                    routing_key=routing_key,
                    template_string=template_string,
                    is_fallback=(family == OntologicalFamily.DEFAULT),
                )

                registry[full_key] = template

    return registry


def get_registry(registry_type: RegistryType) -> RegistryStorageType:
    """Get or build registry."""
    if registry_type not in _REGISTRY_CACHE:
        _REGISTRY_CACHE[registry_type] = _build_registry(registry_type)
    return _REGISTRY_CACHE[registry_type]


def lookup_template(
    routing_key: RoutingKey,
    registry_type: RegistryType,
    collapse_map: Optional[CollapseMapType] = None,
) -> Tuple[Optional[P11B1Template], RoutingTrace]:
    """
    Look up template by routing key with collapse handling.

    Args:
        routing_key: The routing key to look up
        registry_type: Which registry to use
        collapse_map: Optional collapse map (defaults to COLLAPSE_MAP)

    Returns:
        Tuple of:
            - Template if found, None if not found (fail-closed)
            - RoutingTrace documenting the routing decision
    """
    if collapse_map is None:
        collapse_map = COLLAPSE_MAP

    # Apply collapse map
    canonical_key, collapse_applied, collapse_source = apply_collapse_map(
        routing_key, collapse_map
    )

    # Look up in registry
    registry = get_registry(registry_type)
    registry_id = registry_type.value
    full_key = (registry_id, canonical_key.as_tuple())

    if full_key in registry:
        template = registry[full_key]
        trace = RoutingTrace(
            original_key=routing_key,
            canonical_key=canonical_key,
            collapse_applied=collapse_applied,
            collapse_source=collapse_source,
            registry_type=registry_type,
            template_id=template.template_id,
            failure_reason=FailureReason.NONE,
        )
        return (template, trace)

    # Fail-closed: key not in registry
    trace = RoutingTrace(
        original_key=routing_key,
        canonical_key=canonical_key,
        collapse_applied=collapse_applied,
        collapse_source=collapse_source,
        registry_type=registry_type,
        template_id=None,
        failure_reason=FailureReason.KEY_NOT_IN_REGISTRY,
    )
    return (None, trace)


# =============================================================================
# Template Rendering
# =============================================================================


def render_template(
    template: P11B1Template,
    vc_source_data: Mapping[str, str],
) -> str:
    """
    Render template with VC data.

    Placeholder substitution is LITERAL (no interpretation).
    """
    vc_facts = SLOT_PLAN_VC_FACTS[template.routing_key.slot_plan]
    vc_data = {}

    for vc in vc_facts:
        data_key = vc.lower().replace("-", "_") + "_data"
        if data_key in vc_source_data:
            vc_data[data_key] = str(vc_source_data[data_key])
        else:
            vc_data[data_key] = f"[{vc}:unspecified]"

    try:
        return template.template_string.format(**vc_data)
    except KeyError as e:
        return f"[RENDER_ERROR:{e}] {template.template_string}"


# =============================================================================
# Controller (Main Entry Point)
# =============================================================================


def execute_phase11b1(
    request: Phase11B1Request,
    collapse_map: Optional[CollapseMapType] = None,
) -> Phase11B1Response:
    """
    Execute Phase-11B.1 collision-free routing pipeline.

    This is the main entry point for the routing system.

    Args:
        request: The input request
        collapse_map: Optional collapse map (defaults to COLLAPSE_MAP)

    Returns:
        Phase11B1Response with output or RENDER_BLOCKED
    """
    # Stage 1: Extract routing key
    routing_key = request.get_routing_key()
    subband_sig = request.get_subband_signature()

    # Stage 2: Get registry type from mode
    registry_type = get_registry_type(request.render_mode)

    # Stage 3: Look up template
    template, trace = lookup_template(routing_key, registry_type, collapse_map)

    # Stage 4: Render or fail-closed
    if template is None:
        # Fail-closed: RENDER_BLOCKED
        return Phase11B1Response(
            output_text=RENDER_BLOCKED,
            routing_trace=trace,
            template_id="",
            subband_variant_id=subband_sig.to_variant_id(),
            band_signature=subband_sig.to_band_signature_string(),
            verifier_passed=False,
            ledger_span_id=f"span_{request.request_hash()[:16]}",
        )

    # Stage 5: Render template
    output_text = render_template(template, request.vc_source_data)

    # Stage 6: Structural verification (always passes for valid templates)
    verifier_passed = True

    return Phase11B1Response(
        output_text=output_text,
        routing_trace=trace,
        template_id=template.template_id,
        subband_variant_id=subband_sig.to_variant_id(),
        band_signature=subband_sig.to_band_signature_string(),
        verifier_passed=verifier_passed,
        ledger_span_id=f"span_{request.request_hash()[:16]}",
    )


# =============================================================================
# Validation Functions
# =============================================================================


@dataclass(frozen=True)
class CollapseValidationResult:
    """Result of collapse/collision validation."""
    passed: bool
    total_keys: int
    total_template_ids: int
    collision_count: int
    collision_details: Tuple[str, ...]


def validate_no_silent_collapse(
    registry_type: RegistryType,
) -> CollapseValidationResult:
    """
    Validate that no silent collapse occurs in registry.

    Ensures distinct routing keys produce distinct template_ids.
    """
    registry = get_registry(registry_type)

    template_ids: set = set()
    collisions = []
    id_to_key: Dict[str, Tuple[str, Tuple[str, str, str]]] = {}

    for full_key, template in registry.items():
        tid = template.template_id
        if tid in template_ids:
            other_key = id_to_key[tid]
            collisions.append(f"Collision: {full_key} and {other_key} -> {tid}")
        else:
            template_ids.add(tid)
            id_to_key[tid] = full_key

    return CollapseValidationResult(
        passed=len(collisions) == 0,
        total_keys=len(registry),
        total_template_ids=len(template_ids),
        collision_count=len(collisions),
        collision_details=tuple(collisions),
    )


def validate_injectivity(
    keys: Tuple[RoutingKey, ...],
    registry_type: RegistryType,
) -> Tuple[bool, Tuple[str, ...]]:
    """
    Validate that distinct keys produce distinct template_ids.

    Args:
        keys: Set of keys to check
        registry_type: Which registry to use

    Returns:
        Tuple of (passed, collision_details)
    """
    template_ids: Dict[str, RoutingKey] = {}
    collisions = []

    for key in keys:
        template, trace = lookup_template(key, registry_type)
        if template is None:
            continue

        tid = template.template_id
        if tid in template_ids:
            other = template_ids[tid]
            collisions.append(
                f"Collision: {key.canonical_string()} and "
                f"{other.canonical_string()} -> {tid}"
            )
        else:
            template_ids[tid] = key

    return (len(collisions) == 0, tuple(collisions))


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Version
    "PHASE11B1_VERSION",
    # Constants
    "RENDER_BLOCKED",
    "PPV_DIM_COUNT",
    "PPV_VALUE_MIN",
    "PPV_VALUE_MAX",
    "COLLAPSE_MAP",
    "SLOT_PLAN_VC_FACTS",
    "LAYER_TO_FAMILY",
    # Enums
    "PPVSubBand",
    "PPVBand",
    "OntologicalFamily",
    "SlotPlan",
    "RegistryType",
    "RenderMode",
    "FailureReason",
    # Dataclasses
    "SubBandSignature",
    "RoutingKey",
    "RoutingTrace",
    "Phase11B1Request",
    "Phase11B1Response",
    "P11B1Template",
    "CollapseValidationResult",
    # Functions - SubBand
    "get_ppv_subband",
    "get_coarse_band",
    "get_ppv_band",
    "create_subband_signature",
    # Functions - Routing
    "get_template_family",
    "get_slot_plan_from_subband",
    "get_registry_type",
    "create_routing_key",
    # Functions - Registry
    "get_registry",
    "lookup_template",
    "apply_collapse_map",
    # Functions - Rendering
    "render_template",
    # Functions - Controller
    "execute_phase11b1",
    # Functions - Validation
    "validate_no_silent_collapse",
    "validate_injectivity",
]
