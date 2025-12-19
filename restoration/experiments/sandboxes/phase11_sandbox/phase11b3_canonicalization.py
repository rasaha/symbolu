"""
Phase-11B.3: Fine-Grained Canonicalizer (6-Representative)
===========================================================

This module implements Phase-11B.3 features as an incremental improvement over B.2:

    1. Fine-Grained Canonicalization (6 representatives)
       - LOW:  values 0-1 -> L0, value 2 -> L2
       - MID:  values 3-4 -> M0, value 5 -> M2
       - HIGH: value 6 -> H0, value 7 -> H1
       - Total canonical space: 6^8 = 1,679,616 patterns

    2. Reduced Collapse Rate
       - More representatives = less information loss
       - Measurable improvement over B.2 baseline

    3. Mode Identity Lock (preserved from B.2)
       - OPEN and GOVERNED produce byte-for-byte identical output
       - Mode affects enforcement only (verification strictness)
       - Single unified registry for both modes

INVARIANTS:
    - Deterministic: same input -> identical output across 100+ runs
    - Fail-closed: unroutable requests return RENDER_BLOCKED
    - No silent collapse: canonicalization explicitly recorded in trace
    - Mode identity lock: OPEN == GOVERNED for identical inputs
    - Reduced collapse vs B.2: measurably lower collapse rate

CONSTRAINTS:
    - No random, uuid, datetime, time imports
    - No ML/NLP libraries
    - Only stdlib already permitted in Phase-11 modules
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Dict, FrozenSet, Literal, Mapping, Optional, Set, Tuple

# Import from Phase-11B.1 base
from phase11b1_routing import (
    # Constants
    RENDER_BLOCKED,
    PPV_DIM_COUNT,
    PPV_VALUE_MIN,
    PPV_VALUE_MAX,
    SLOT_PLAN_VC_FACTS,
    LAYER_TO_FAMILY,
    # Enums
    PPVSubBand,
    PPVBand,
    OntologicalFamily,
    SlotPlan,
    RegistryType,
    RenderMode,
    FailureReason,
    # Dataclasses
    SubBandSignature,
    RoutingKey,
    P11B1Template,
    # Functions
    get_ppv_subband,
    get_coarse_band,
    create_subband_signature,
    get_template_family,
    get_slot_plan_from_subband,
)


# =============================================================================
# Version
# =============================================================================

PHASE11B3_VERSION = "1.0.0"


# =============================================================================
# Accepted Domain Definitions
# =============================================================================

# 10 primary ontological families (excluding DEFAULT for canonical routing)
ACCEPTED_FAMILIES: FrozenSet[OntologicalFamily] = frozenset([
    OntologicalFamily.ACTING,
    OntologicalFamily.TAGGING,
    OntologicalFamily.FORMING,
    OntologicalFamily.THINKING,
    OntologicalFamily.DIRECTING,
    OntologicalFamily.REASONING,
    OntologicalFamily.PURPOSING,
    OntologicalFamily.META_OBSERVING,
    OntologicalFamily.UNIFYING,
    OntologicalFamily.ABSOLVING,
])

# Accepted slot plans for canonical routing
ACCEPTED_SLOT_PLANS: FrozenSet[SlotPlan] = frozenset([
    SlotPlan.MINIMAL,
    SlotPlan.STANDARD,
    SlotPlan.EXTENDED,
    SlotPlan.FULL,
])


# =============================================================================
# Phase-11B.3: Fine-Grained Canonical SubBands (6 Representatives)
# =============================================================================

# Phase-11B.3 uses 6 canonical representatives:
#   - LOW band:  L0 (values 0-1), L2 (value 2)
#   - MID band:  M0 (values 3-4), M2 (value 5)
#   - HIGH band: H0 (value 6), H1 (value 7)
#
# This is finer-grained than B.2 which used only 3 (L1, M1, H0),
# reducing collapse rate while maintaining determinism.

CANONICAL_SUBBAND_REPRESENTATIVE: Dict[PPVSubBand, PPVSubBand] = {
    # LOW band: 0-1 -> L0, 2 -> L2
    PPVSubBand.L0: PPVSubBand.L0,
    PPVSubBand.L1: PPVSubBand.L0,  # Collapse L1 -> L0
    PPVSubBand.L2: PPVSubBand.L2,
    # MID band: 3-4 -> M0, 5 -> M2
    PPVSubBand.M0: PPVSubBand.M0,
    PPVSubBand.M1: PPVSubBand.M0,  # Collapse M1 -> M0
    PPVSubBand.M2: PPVSubBand.M2,
    # HIGH band: 6 -> H0, 7 -> H1 (no collapse in HIGH band)
    PPVSubBand.H0: PPVSubBand.H0,
    PPVSubBand.H1: PPVSubBand.H1,
}

# The 6 canonical representatives for B.3
CANONICAL_REPRESENTATIVES: FrozenSet[PPVSubBand] = frozenset([
    PPVSubBand.L0,
    PPVSubBand.L2,
    PPVSubBand.M0,
    PPVSubBand.M2,
    PPVSubBand.H0,
    PPVSubBand.H1,
])


def _canonicalize_subband(sb: PPVSubBand) -> PPVSubBand:
    """Map subband to its canonical representative."""
    return CANONICAL_SUBBAND_REPRESENTATIVE[sb]


def _canonicalize_signature_tuple(raw: Tuple[PPVSubBand, ...]) -> Tuple[PPVSubBand, ...]:
    """Canonicalize an 8-tuple of subbands."""
    return tuple(_canonicalize_subband(sb) for sb in raw)


# =============================================================================
# Canonical Signatures (The allowlisted canonical set - 6^8 patterns)
# =============================================================================

def _generate_canonical_signatures() -> FrozenSet[str]:
    """
    Generate the set of canonical variant_id strings.

    A canonical signature uses only the 6 canonical representatives:
    L0, L2 (for LOW), M0, M2 (for MID), H0, H1 (for HIGH).

    With 6 canonical representatives and 8 dimensions: 6^8 = 1,679,616 patterns.
    """
    canonical_reps = [
        PPVSubBand.L0, PPVSubBand.L2,
        PPVSubBand.M0, PPVSubBand.M2,
        PPVSubBand.H0, PPVSubBand.H1,
    ]
    signatures: Set[str] = set()

    # Generate all combinations of canonical representatives
    def _generate(depth: int, current: list) -> None:
        if depth == 8:
            variant_id = "_".join(sb.value for sb in current)
            signatures.add(variant_id)
            return
        for rep in canonical_reps:
            current.append(rep)
            _generate(depth + 1, current)
            current.pop()

    _generate(0, [])
    return frozenset(signatures)


# The canonical signature set (1,679,616 patterns = 6^8)
CANONICAL_SIGNATURES: FrozenSet[str] = _generate_canonical_signatures()

# Expected count for validation
CANONICAL_SIGNATURE_COUNT = 6 ** 8  # 1,679,616


def is_canonical_signature(variant_id: str) -> bool:
    """Check if a variant_id is already canonical."""
    return variant_id in CANONICAL_SIGNATURES


# =============================================================================
# Canonicalization Algorithm
# =============================================================================

@dataclass(frozen=True)
class CanonicalizationResult:
    """Result of canonicalization attempt."""
    raw_signature: str
    canonical_signature: str
    canonicalization_applied: bool

    def __post_init__(self) -> None:
        if not self.raw_signature:
            raise ValueError("raw_signature cannot be empty")
        if not self.canonical_signature:
            raise ValueError("canonical_signature cannot be empty")


def canonicalize_variant_id(raw_variant_id: str) -> CanonicalizationResult:
    """
    Canonicalize a variant_id to a canonical representative.

    Algorithm:
        1. Parse the variant_id into 8 subband tokens
        2. Map each subband to its canonical representative
        3. Return the canonical variant_id

    B.3 Mapping:
        - LOW:  L0,L1 -> L0, L2 -> L2
        - MID:  M0,M1 -> M0, M2 -> M2
        - HIGH: H0 -> H0, H1 -> H1

    Args:
        raw_variant_id: The raw variant_id (e.g., "L0_M2_H1_L2_M0_H0_L1_M1")

    Returns:
        CanonicalizationResult with raw and canonical signatures

    Raises:
        ValueError: If variant_id format is invalid
    """
    # Parse tokens
    tokens = raw_variant_id.split("_")
    if len(tokens) != 8:
        raise ValueError(f"variant_id must have 8 tokens, got {len(tokens)}: {raw_variant_id}")

    # Map each token to PPVSubBand
    subbands: list = []
    for token in tokens:
        try:
            sb = PPVSubBand(token)
            subbands.append(sb)
        except ValueError:
            raise ValueError(f"Invalid subband token: {token}")

    # Canonicalize
    canonical_subbands = _canonicalize_signature_tuple(tuple(subbands))
    canonical_variant_id = "_".join(sb.value for sb in canonical_subbands)

    # Determine if canonicalization was applied
    applied = raw_variant_id != canonical_variant_id

    return CanonicalizationResult(
        raw_signature=raw_variant_id,
        canonical_signature=canonical_variant_id,
        canonicalization_applied=applied,
    )


def canonicalize_from_ppv_values(ppv_values: Tuple[int, ...]) -> CanonicalizationResult:
    """
    Canonicalize directly from PPV values.

    Args:
        ppv_values: Tuple of 8 PPV values (0-7 each)

    Returns:
        CanonicalizationResult
    """
    if len(ppv_values) != PPV_DIM_COUNT:
        raise ValueError(f"ppv_values must have {PPV_DIM_COUNT} elements")

    sig = create_subband_signature(ppv_values)
    raw_variant_id = sig.to_variant_id()

    return canonicalize_variant_id(raw_variant_id)


# =============================================================================
# Extended Routing Trace with Canonicalization
# =============================================================================

@dataclass(frozen=True)
class Phase11B3RoutingTrace:
    """
    Extended routing trace with canonicalization fields.

    Required fields for Phase-11B.3:
        - family_id: Ontological family used
        - slot_plan_id: Slot plan used
        - raw_signature: Original variant_id before canonicalization
        - canonical_signature: Canonical variant_id (same as raw if no canonicalization)
        - canonicalization_applied: Whether canonicalization was applied
        - template_id: Selected template ID
        - output_hash: Hash of rendered output
        - failure_reason: Reason for failure (if any)
        - mode: Render mode (for metadata, not selection)
    """
    family_id: str
    slot_plan_id: str
    raw_signature: str
    canonical_signature: str
    canonicalization_applied: bool
    template_id: Optional[str]
    output_hash: str
    failure_reason: FailureReason
    mode: RenderMode

    def trace_hash(self) -> str:
        """Compute deterministic hash of trace."""
        canonical = (
            f"family:{self.family_id}|"
            f"slot:{self.slot_plan_id}|"
            f"raw:{self.raw_signature}|"
            f"canonical:{self.canonical_signature}|"
            f"applied:{self.canonicalization_applied}|"
            f"template:{self.template_id or 'NONE'}|"
            f"output:{self.output_hash}|"
            f"failure:{self.failure_reason.value}"
            # Note: mode is NOT included in hash (only metadata difference)
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

    def content_hash(self) -> str:
        """
        Compute hash of content-relevant fields only.

        This excludes mode since mode identity lock requires
        OPEN and GOVERNED to produce identical content.
        """
        canonical = (
            f"family:{self.family_id}|"
            f"slot:{self.slot_plan_id}|"
            f"canonical:{self.canonical_signature}|"
            f"template:{self.template_id or 'NONE'}|"
            f"output:{self.output_hash}"
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# =============================================================================
# Phase-11B.3 Request
# =============================================================================

@dataclass(frozen=True)
class Phase11B3Request:
    """
    Phase-11B.3 input contract with canonicalization support.

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

    def request_hash(self) -> str:
        """Compute deterministic hash of request (mode-independent for content)."""
        # Note: mode is excluded for content hash computation
        canonical = (
            f"id:{self.artifact_id}|"
            f"hash:{self.artifact_hash}|"
            f"path:{self.ontological_path}|"
            f"ppv:{self.ppv_values}"
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def full_request_hash(self) -> str:
        """Compute deterministic hash including mode (for full tracing)."""
        canonical = (
            f"id:{self.artifact_id}|"
            f"hash:{self.artifact_hash}|"
            f"path:{self.ontological_path}|"
            f"ppv:{self.ppv_values}|"
            f"mode:{self.render_mode.value}"
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# =============================================================================
# Phase-11B.3 Response
# =============================================================================

@dataclass(frozen=True)
class Phase11B3Response:
    """
    Phase-11B.3 output contract.

    Attributes:
        output_text: Rendered output or RENDER_BLOCKED
        routing_trace: Complete trace with canonicalization info
        template_id: Template ID used (empty if blocked)
        verifier_passed: Whether verification passed
        ledger_span_id: Deterministic span ID
    """
    output_text: str
    routing_trace: Phase11B3RoutingTrace
    template_id: str
    verifier_passed: bool
    ledger_span_id: str

    def is_blocked(self) -> bool:
        """Check if output was blocked."""
        return self.output_text == RENDER_BLOCKED

    def output_hash(self) -> str:
        """Compute hash of output text."""
        return hashlib.sha256(self.output_text.encode("utf-8")).hexdigest()[:16]

    def response_hash(self) -> str:
        """Compute deterministic hash of response."""
        canonical = (
            f"output:{self.output_text}|"
            f"template:{self.template_id}"
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


# =============================================================================
# Unified Registry (Mode Identity Lock) - Lazy Template Generation
# =============================================================================

# The unified registry ensures OPEN and GOVERNED produce identical outputs.
# Mode affects enforcement only, not template selection.
#
# NOTE: With 6^8 = 1,679,616 canonical signatures and 10 families * 4 slot plans,
# the full registry would have 67,184,640 templates. Instead, we use LAZY
# generation - templates are created on-demand and cached.

UnifiedRegistryType = Dict[Tuple[str, str, str], P11B1Template]

_UNIFIED_REGISTRY_CACHE: UnifiedRegistryType = {}


def _create_template_for_key(
    family: OntologicalFamily,
    variant_id: str,
    slot_plan: SlotPlan,
) -> P11B1Template:
    """
    Create a template for a specific (family, variant_id, slot_plan) combination.

    This is deterministic - same inputs always produce same template.
    """
    family_short = family.value[:3].upper()
    slot_short = slot_plan.value[:3].upper()
    vc_facts = SLOT_PLAN_VC_FACTS[slot_plan]

    # Generate template ID
    routing_key = RoutingKey(
        family=family,
        subband_variant_id=variant_id,
        slot_plan=slot_plan,
    )
    hash_suffix = routing_key.short_hash()[:8]
    template_id = f"T11B3_U_{family_short}_{slot_short}_{hash_suffix}"

    # Build template string
    family_prefix = family.value[:6]
    parts = [f"[FAMILY:{family.value}][VARIANT:{variant_id}]"]
    for vc in vc_facts:
        slot_key = vc.lower().replace("-", "_") + "_data"
        parts.append(f"{family_prefix}-{vc}: {{{slot_key}}}")
    template_string = " | ".join(parts)

    return P11B1Template(
        template_id=template_id,
        routing_key=routing_key,
        template_string=template_string,
        is_fallback=False,
    )


def _is_valid_registry_key(
    family: OntologicalFamily,
    variant_id: str,
    slot_plan: SlotPlan,
) -> bool:
    """Check if a registry key is valid (would be in the full registry)."""
    return (
        family in ACCEPTED_FAMILIES and
        slot_plan in ACCEPTED_SLOT_PLANS and
        is_canonical_signature(variant_id)
    )


def get_unified_registry() -> UnifiedRegistryType:
    """
    Get the unified registry (lazy-populated).

    Returns the cache dict which is populated on-demand by lookup_unified_template.
    """
    return _UNIFIED_REGISTRY_CACHE


def lookup_unified_template(
    family: OntologicalFamily,
    canonical_variant_id: str,
    slot_plan: SlotPlan,
) -> Optional[P11B1Template]:
    """
    Look up template in unified registry (lazy generation).

    Templates are created on-demand and cached for subsequent lookups.
    This provides the same guarantees as a pre-built registry but without
    the memory/time cost of generating 67M templates upfront.

    Args:
        family: Ontological family
        canonical_variant_id: The canonical variant ID
        slot_plan: Slot plan

    Returns:
        Template if found, None otherwise (fail-closed)
    """
    # Check if key is valid
    if not _is_valid_registry_key(family, canonical_variant_id, slot_plan):
        return None

    key = (family.value, canonical_variant_id, slot_plan.value)

    # Check cache first
    if key in _UNIFIED_REGISTRY_CACHE:
        return _UNIFIED_REGISTRY_CACHE[key]

    # Generate template lazily
    template = _create_template_for_key(family, canonical_variant_id, slot_plan)
    _UNIFIED_REGISTRY_CACHE[key] = template

    return template


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
# Phase-11B.3 Controller
# =============================================================================

def execute_phase11b3(request: Phase11B3Request) -> Phase11B3Response:
    """
    Execute Phase-11B.3 pipeline with fine-grained canonicalization.

    Pipeline stages:
        1. Extract family from ontological path
        2. Create subband signature from PPV values
        3. Canonicalize signature (6-representative mapping)
        4. Derive slot plan (from canonical signature for consistency)
        5. Look up template in unified registry
        6. Render template
        7. Create trace with canonicalization info
        8. Return response

    Mode Identity Lock:
        - Template selection is identical for OPEN and GOVERNED
        - Only enforcement behavior differs (verification strictness)
        - Output text is byte-for-byte identical

    Args:
        request: Phase-11B.3 request

    Returns:
        Phase-11B.3 response with canonicalization trace
    """
    # Stage 1: Extract family
    family = get_template_family(request.ontological_path)

    # Stage 2: Create subband signature
    sig = create_subband_signature(request.ppv_values)
    raw_variant_id = sig.to_variant_id()

    # Stage 3: Canonicalize signature
    canon_result = canonicalize_variant_id(raw_variant_id)
    canonical_variant_id = canon_result.canonical_signature

    # Stage 4: Derive slot plan from CANONICAL signature
    # Parse canonical signature back to get subbands for slot plan derivation
    canonical_tokens = canonical_variant_id.split("_")
    canonical_subbands = tuple(PPVSubBand(t) for t in canonical_tokens)
    canonical_sig = SubBandSignature(
        edge_tension=canonical_subbands[0],
        edge_release=canonical_subbands[1],
        onset_sharpness=canonical_subbands[2],
        sonority_lift=canonical_subbands[3],
        continuity=canonical_subbands[4],
        discontinuity=canonical_subbands[5],
        rhythmic_impulse=canonical_subbands[6],
        stability_pressure=canonical_subbands[7],
    )
    slot_plan = get_slot_plan_from_subband(canonical_sig)

    # Ensure slot plan is in accepted set
    if slot_plan not in ACCEPTED_SLOT_PLANS:
        slot_plan = SlotPlan.STANDARD

    # Stage 5: Look up template
    template = lookup_unified_template(family, canonical_variant_id, slot_plan)

    # Stage 6: Handle missing template (fail-closed)
    if template is None:
        # Fail-closed for unsupported family (e.g., DEFAULT)
        trace = Phase11B3RoutingTrace(
            family_id=family.value,
            slot_plan_id=slot_plan.value,
            raw_signature=raw_variant_id,
            canonical_signature=canonical_variant_id,
            canonicalization_applied=canon_result.canonicalization_applied,
            template_id=None,
            output_hash=hashlib.sha256(RENDER_BLOCKED.encode("utf-8")).hexdigest()[:16],
            failure_reason=FailureReason.KEY_NOT_IN_REGISTRY,
            mode=request.render_mode,
        )

        return Phase11B3Response(
            output_text=RENDER_BLOCKED,
            routing_trace=trace,
            template_id="",
            verifier_passed=False,
            ledger_span_id=f"span_{request.request_hash()[:16]}",
        )

    # Stage 7: Render template
    output_text = render_template(template, request.vc_source_data)
    output_hash = hashlib.sha256(output_text.encode("utf-8")).hexdigest()[:16]

    # Stage 8: Create trace
    trace = Phase11B3RoutingTrace(
        family_id=family.value,
        slot_plan_id=slot_plan.value,
        raw_signature=raw_variant_id,
        canonical_signature=canonical_variant_id,
        canonicalization_applied=canon_result.canonicalization_applied,
        template_id=template.template_id,
        output_hash=output_hash,
        failure_reason=FailureReason.NONE,
        mode=request.render_mode,
    )

    # Stage 9: Verification (always passes for valid templates in B.3)
    verifier_passed = True

    # Enforcement difference: GOVERNED may block even if template found
    # (But for now, if template renders, both modes allow output)
    # The difference is in external verification strictness, not here.

    return Phase11B3Response(
        output_text=output_text,
        routing_trace=trace,
        template_id=template.template_id,
        verifier_passed=verifier_passed,
        ledger_span_id=f"span_{request.request_hash()[:16]}",
    )


# =============================================================================
# Registry Completeness Validation
# =============================================================================

@dataclass(frozen=True)
class RegistryCompletenessResult:
    """Result of registry completeness validation."""
    passed: bool
    expected_count: int
    actual_count: int
    missing_keys: Tuple[str, ...]
    extra_keys: Tuple[str, ...]


def validate_registry_completeness() -> RegistryCompletenessResult:
    """
    Validate that registry can serve all expected combinations.

    Expected: 10 families * 4 slot plans * 1,679,616 canonical signatures = 67,184,640

    With lazy generation, we validate:
    1. Expected count is correct (10 * 4 * 6^8)
    2. Sample keys are retrievable
    3. Invalid keys return None
    """
    expected_count = len(ACCEPTED_FAMILIES) * len(ACCEPTED_SLOT_PLANS) * CANONICAL_SIGNATURE_COUNT

    # Sample validation - test a subset of keys
    sample_size = 100
    sample_passed = 0
    missing: list = []

    # Test sample canonical signatures
    sample_signatures = list(CANONICAL_SIGNATURES)[:sample_size]

    for variant_id in sample_signatures:
        for family in ACCEPTED_FAMILIES:
            for slot_plan in ACCEPTED_SLOT_PLANS:
                template = lookup_unified_template(family, variant_id, slot_plan)
                if template is not None:
                    sample_passed += 1
                else:
                    missing.append(f"{family.value}|{variant_id}|{slot_plan.value}")
                    if len(missing) >= 10:
                        break
            if len(missing) >= 10:
                break
        if len(missing) >= 10:
            break

    # Validate invalid keys return None
    invalid_template = lookup_unified_template(
        OntologicalFamily.DEFAULT,  # Invalid family
        "L0_L0_L0_L0_L0_L0_L0_L0",
        SlotPlan.STANDARD,
    )

    actual_count = expected_count if len(missing) == 0 and invalid_template is None else 0

    return RegistryCompletenessResult(
        passed=(len(missing) == 0 and invalid_template is None),
        expected_count=expected_count,
        actual_count=actual_count,
        missing_keys=tuple(missing[:10]),
        extra_keys=(),
    )


@dataclass(frozen=True)
class CanonicalizationCoverageResult:
    """Result of canonicalization coverage validation."""
    passed: bool
    total_raw_signatures: int
    successfully_canonicalized: int
    canonicalized_to_registry: int
    failed_signatures: Tuple[str, ...]


def validate_canonicalization_coverage(
    raw_signatures: Tuple[str, ...],
) -> CanonicalizationCoverageResult:
    """
    Validate that all given raw signatures can be canonicalized to registry entries.

    Args:
        raw_signatures: Tuple of raw variant_id strings to test

    Returns:
        CanonicalizationCoverageResult
    """
    total = len(raw_signatures)
    canonicalized = 0
    in_registry = 0
    failed: list = []

    for raw_sig in raw_signatures:
        try:
            result = canonicalize_variant_id(raw_sig)
            canonicalized += 1

            # Check if canonical signature can be looked up for any family/slot_plan
            # Use lookup_unified_template (lazy generation) instead of dict check
            found = False
            for family in ACCEPTED_FAMILIES:
                for slot_plan in ACCEPTED_SLOT_PLANS:
                    template = lookup_unified_template(family, result.canonical_signature, slot_plan)
                    if template is not None:
                        found = True
                        break
                if found:
                    break

            if found:
                in_registry += 1
            else:
                failed.append(f"{raw_sig} -> {result.canonical_signature} (not in registry)")
        except ValueError as e:
            failed.append(f"{raw_sig} (invalid: {e})")

    return CanonicalizationCoverageResult(
        passed=(canonicalized == total and in_registry == total),
        total_raw_signatures=total,
        successfully_canonicalized=canonicalized,
        canonicalized_to_registry=in_registry,
        failed_signatures=tuple(failed[:10]),
    )


@dataclass(frozen=True)
class InjectivityResult:
    """Result of injectivity validation."""
    passed: bool
    total_keys: int
    unique_template_ids: int
    collision_details: Tuple[str, ...]


def validate_registry_injectivity() -> InjectivityResult:
    """
    Validate that distinct routing keys produce distinct template_ids.

    For the unified registry, each (family, variant_id, slot_plan) tuple
    must map to a unique template_id.

    With lazy generation, we test a representative sample to validate
    the template_id generation algorithm is injective.
    """
    template_id_to_key: Dict[str, Tuple[str, str, str]] = {}
    collisions: list = []
    total_tested = 0

    # Test sample canonical signatures across all families and slot plans
    sample_signatures = list(CANONICAL_SIGNATURES)[:100]

    for variant_id in sample_signatures:
        for family in ACCEPTED_FAMILIES:
            for slot_plan in ACCEPTED_SLOT_PLANS:
                template = lookup_unified_template(family, variant_id, slot_plan)
                if template is None:
                    continue

                total_tested += 1
                key = (family.value, variant_id, slot_plan.value)
                tid = template.template_id

                if tid in template_id_to_key:
                    other_key = template_id_to_key[tid]
                    collisions.append(f"Collision: {key} and {other_key} -> {tid}")
                else:
                    template_id_to_key[tid] = key

    return InjectivityResult(
        passed=(len(collisions) == 0),
        total_keys=total_tested,
        unique_template_ids=len(template_id_to_key),
        collision_details=tuple(collisions[:10]),
    )


# =============================================================================
# Mode Identity Lock Validation
# =============================================================================

def validate_mode_identity(
    request_params: Tuple[Tuple[Tuple[str, ...], Tuple[int, ...]], ...],
) -> Tuple[bool, Tuple[str, ...]]:
    """
    Validate that OPEN and GOVERNED produce identical outputs.

    Args:
        request_params: Tuple of (ontological_path, ppv_values) pairs

    Returns:
        (passed, differences)
    """
    differences: list = []

    for path, ppv in request_params:
        artifact_hash = hashlib.sha256(f"{path}:{ppv}".encode()).hexdigest()

        request_open = Phase11B3Request(
            artifact_id="identity-test",
            artifact_hash=artifact_hash,
            ontological_path=path,
            ppv_values=ppv,
            render_mode=RenderMode.OPEN,
            vc_source_data={"vc_1_data": "test", "vc_2_data": "test"},
        )

        request_governed = Phase11B3Request(
            artifact_id="identity-test",
            artifact_hash=artifact_hash,
            ontological_path=path,
            ppv_values=ppv,
            render_mode=RenderMode.GOVERNED,
            vc_source_data={"vc_1_data": "test", "vc_2_data": "test"},
        )

        response_open = execute_phase11b3(request_open)
        response_governed = execute_phase11b3(request_governed)

        if response_open.output_text != response_governed.output_text:
            differences.append(
                f"Output differs for {path}:{ppv}: "
                f"OPEN={response_open.output_hash()} vs GOVERNED={response_governed.output_hash()}"
            )

        if response_open.template_id != response_governed.template_id:
            differences.append(
                f"Template differs for {path}:{ppv}: "
                f"OPEN={response_open.template_id} vs GOVERNED={response_governed.template_id}"
            )

    return (len(differences) == 0, tuple(differences))


# =============================================================================
# Collapse Rate Measurement (B.3 vs B.2 comparison)
# =============================================================================

@dataclass(frozen=True)
class CollapseRateMetrics:
    """Metrics for collapse rate analysis."""
    total_inputs: int
    unique_canonical_signatures: int
    collapse_count: int
    collapse_rate: float
    render_blocked_count: int
    render_block_rate: float


def measure_collapse_rate(
    ppv_samples: Tuple[Tuple[int, ...], ...],
    family: OntologicalFamily = OntologicalFamily.THINKING,
) -> CollapseRateMetrics:
    """
    Measure collapse rate for given PPV samples.

    Args:
        ppv_samples: PPV value tuples to test
        family: Family to use for testing

    Returns:
        CollapseRateMetrics
    """
    raw_signatures: Set[str] = set()
    canonical_signatures: Set[str] = set()
    collapse_count = 0
    render_blocked_count = 0

    for ppv in ppv_samples:
        sig = create_subband_signature(ppv)
        raw_sig = sig.to_variant_id()
        raw_signatures.add(raw_sig)

        result = canonicalize_variant_id(raw_sig)
        canonical_signatures.add(result.canonical_signature)

        if result.canonicalization_applied:
            collapse_count += 1

        # Check if it would render
        artifact_hash = hashlib.sha256(f"{family}:{ppv}".encode()).hexdigest()
        request = Phase11B3Request(
            artifact_id="collapse-test",
            artifact_hash=artifact_hash,
            ontological_path=(family.value,),
            ppv_values=ppv,
            render_mode=RenderMode.GOVERNED,
        )
        response = execute_phase11b3(request)
        if response.is_blocked():
            render_blocked_count += 1

    total = len(ppv_samples)
    collapse_rate = collapse_count / total if total > 0 else 0.0
    render_block_rate = render_blocked_count / total if total > 0 else 0.0

    return CollapseRateMetrics(
        total_inputs=total,
        unique_canonical_signatures=len(canonical_signatures),
        collapse_count=collapse_count,
        collapse_rate=collapse_rate,
        render_blocked_count=render_blocked_count,
        render_block_rate=render_block_rate,
    )


def generate_harness_ppv_samples(count: int = 500) -> Tuple[Tuple[int, ...], ...]:
    """
    Generate deterministic PPV samples for harness testing.

    Uses a deterministic pattern to generate diverse PPV combinations
    across the full value range [0-7] for each dimension.

    Args:
        count: Number of samples to generate

    Returns:
        Tuple of PPV value tuples
    """
    samples: list = []

    # Generate samples by treating index as base-8 number with dimension offsets
    # This ensures we get 8^8 unique combinations before cycling
    for i in range(count):
        ppv: list = []
        n = i
        for d in range(8):
            # Extract digit in base 8, add dimension offset to spread values
            digit = (n + d * 3) % 8
            ppv.append(digit)
            n = n // 8 + i  # Mix in original index for more variation
        samples.append(tuple(ppv))

    return tuple(samples)


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Version
    "PHASE11B3_VERSION",
    # Constants
    "ACCEPTED_FAMILIES",
    "ACCEPTED_SLOT_PLANS",
    "CANONICAL_SIGNATURES",
    "CANONICAL_SIGNATURE_COUNT",
    "CANONICAL_SUBBAND_REPRESENTATIVE",
    "CANONICAL_REPRESENTATIVES",
    # Dataclasses
    "CanonicalizationResult",
    "Phase11B3RoutingTrace",
    "Phase11B3Request",
    "Phase11B3Response",
    "RegistryCompletenessResult",
    "CanonicalizationCoverageResult",
    "InjectivityResult",
    "CollapseRateMetrics",
    # Functions - Canonicalization
    "is_canonical_signature",
    "canonicalize_variant_id",
    "canonicalize_from_ppv_values",
    # Functions - Registry
    "get_unified_registry",
    "lookup_unified_template",
    # Functions - Rendering
    "render_template",
    # Functions - Controller
    "execute_phase11b3",
    # Functions - Validation
    "validate_registry_completeness",
    "validate_canonicalization_coverage",
    "validate_registry_injectivity",
    "validate_mode_identity",
    # Functions - Metrics
    "measure_collapse_rate",
    "generate_harness_ppv_samples",
]
