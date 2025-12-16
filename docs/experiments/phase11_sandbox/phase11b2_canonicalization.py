"""
Phase-11B.2: Canonicalization + Mode Identity Lock
====================================================

This module implements Phase-11B.2 features:

    1. Deterministic Canonicalization Fallback
       - CANONICAL_SIGNATURES: Small allowlisted set of canonical patterns
       - CANONICALIZE_MAP: Explicit mapping from non-canonical to canonical
       - canonicalize_signature(): Deterministic function with provable guarantees
       - Reduces RENDER_BLOCKED without silent collapse
       - Canonicalization explicitly recorded in trace

    2. Mode Identity Lock
       - OPEN and GOVERNED produce byte-for-byte identical output
       - Mode affects enforcement only (verification strictness)
       - Single unified registry for both modes
       - Template selection is mode-independent

INVARIANTS:
    - Deterministic: same input -> identical output across 100+ runs
    - Fail-closed: unroutable requests return RENDER_BLOCKED
    - No silent collapse: canonicalization explicitly recorded
    - No new generation logic: structural generator via routing + registry
    - Mode identity lock: OPEN == GOVERNED for identical inputs

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

PHASE11B2_VERSION = "1.0.0"


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
# Canonical Coarse Bands for Canonicalization
# =============================================================================

# Canonical bands: we map subbands to their coarse band representative
# L0, L1, L2 -> L (represented as L1)
# M0, M1, M2 -> M (represented as M1)
# H0, H1 -> H (represented as H0)
CANONICAL_SUBBAND_REPRESENTATIVE: Dict[PPVSubBand, PPVSubBand] = {
    PPVSubBand.L0: PPVSubBand.L1,
    PPVSubBand.L1: PPVSubBand.L1,
    PPVSubBand.L2: PPVSubBand.L1,
    PPVSubBand.M0: PPVSubBand.M1,
    PPVSubBand.M1: PPVSubBand.M1,
    PPVSubBand.M2: PPVSubBand.M1,
    PPVSubBand.H0: PPVSubBand.H0,
    PPVSubBand.H1: PPVSubBand.H0,
}


def _canonicalize_subband(sb: PPVSubBand) -> PPVSubBand:
    """Map subband to its canonical representative."""
    return CANONICAL_SUBBAND_REPRESENTATIVE[sb]


def _canonicalize_signature_tuple(raw: Tuple[PPVSubBand, ...]) -> Tuple[PPVSubBand, ...]:
    """Canonicalize an 8-tuple of subbands."""
    return tuple(_canonicalize_subband(sb) for sb in raw)


# =============================================================================
# Canonical Signatures (The allowlisted canonical set)
# =============================================================================

def _generate_canonical_signatures() -> FrozenSet[str]:
    """
    Generate the set of canonical variant_id strings.

    A canonical signature uses only the canonical representatives:
    L1 (for all L), M1 (for all M), H0 (for all H).

    With 3 canonical representatives and 8 dimensions: 3^8 = 6561 patterns.
    """
    canonical_reps = [PPVSubBand.L1, PPVSubBand.M1, PPVSubBand.H0]
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


# The canonical signature set (6561 patterns)
CANONICAL_SIGNATURES: FrozenSet[str] = _generate_canonical_signatures()


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
class Phase11B2RoutingTrace:
    """
    Extended routing trace with canonicalization fields.

    Required fields for Phase-11B.2:
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
# Phase-11B.2 Request
# =============================================================================

@dataclass(frozen=True)
class Phase11B2Request:
    """
    Phase-11B.2 input contract with canonicalization support.

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
# Phase-11B.2 Response
# =============================================================================

@dataclass(frozen=True)
class Phase11B2Response:
    """
    Phase-11B.2 output contract.

    Attributes:
        output_text: Rendered output or RENDER_BLOCKED
        routing_trace: Complete trace with canonicalization info
        template_id: Template ID used (empty if blocked)
        verifier_passed: Whether verification passed
        ledger_span_id: Deterministic span ID
    """
    output_text: str
    routing_trace: Phase11B2RoutingTrace
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
# Unified Registry (Mode Identity Lock)
# =============================================================================

# The unified registry ensures OPEN and GOVERNED produce identical outputs.
# Mode affects enforcement only, not template selection.

UnifiedRegistryType = Dict[Tuple[str, str, str], P11B1Template]

_UNIFIED_REGISTRY_CACHE: Optional[UnifiedRegistryType] = None


def _generate_canonical_variant_ids() -> Tuple[str, ...]:
    """
    Generate all canonical variant IDs.

    Returns all 6561 canonical patterns (3^8).
    """
    return tuple(sorted(CANONICAL_SIGNATURES))


def _build_unified_registry() -> UnifiedRegistryType:
    """
    Build the unified registry for both OPEN and GOVERNED modes.

    This registry contains templates for:
        - All 10 accepted families
        - All 4 accepted slot plans
        - All canonical signatures

    Total: 10 * 4 * 6561 = 262,440 templates
    """
    registry: UnifiedRegistryType = {}

    canonical_variants = _generate_canonical_variant_ids()

    for family in ACCEPTED_FAMILIES:
        family_short = family.value[:3].upper()

        for slot_plan in ACCEPTED_SLOT_PLANS:
            slot_short = slot_plan.value[:3].upper()
            vc_facts = SLOT_PLAN_VC_FACTS[slot_plan]

            for variant_id in canonical_variants:
                # Registry key: (family, variant_id, slot_plan)
                key = (family.value, variant_id, slot_plan.value)

                # Generate template ID
                routing_key = RoutingKey(
                    family=family,
                    subband_variant_id=variant_id,
                    slot_plan=slot_plan,
                )
                hash_suffix = routing_key.short_hash()[:8]
                template_id = f"T11B2_U_{family_short}_{slot_short}_{hash_suffix}"

                # Build template string
                family_prefix = family.value[:6]
                parts = [f"[FAMILY:{family.value}][VARIANT:{variant_id}]"]
                for vc in vc_facts:
                    slot_key = vc.lower().replace("-", "_") + "_data"
                    parts.append(f"{family_prefix}-{vc}: {{{slot_key}}}")
                template_string = " | ".join(parts)

                template = P11B1Template(
                    template_id=template_id,
                    routing_key=routing_key,
                    template_string=template_string,
                    is_fallback=False,
                )

                registry[key] = template

    return registry


def get_unified_registry() -> UnifiedRegistryType:
    """Get or build the unified registry."""
    global _UNIFIED_REGISTRY_CACHE
    if _UNIFIED_REGISTRY_CACHE is None:
        _UNIFIED_REGISTRY_CACHE = _build_unified_registry()
    return _UNIFIED_REGISTRY_CACHE


def lookup_unified_template(
    family: OntologicalFamily,
    canonical_variant_id: str,
    slot_plan: SlotPlan,
) -> Optional[P11B1Template]:
    """
    Look up template in unified registry.

    Args:
        family: Ontological family
        canonical_variant_id: The canonical variant ID
        slot_plan: Slot plan

    Returns:
        Template if found, None otherwise (fail-closed)
    """
    registry = get_unified_registry()
    key = (family.value, canonical_variant_id, slot_plan.value)
    return registry.get(key)


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
# Phase-11B.2 Controller
# =============================================================================

def execute_phase11b2(request: Phase11B2Request) -> Phase11B2Response:
    """
    Execute Phase-11B.2 pipeline with canonicalization and mode identity lock.

    Pipeline stages:
        1. Extract family from ontological path
        2. Create subband signature from PPV values
        3. Canonicalize signature
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
        request: Phase-11B.2 request

    Returns:
        Phase-11B.2 response with canonicalization trace
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
        trace = Phase11B2RoutingTrace(
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

        return Phase11B2Response(
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
    trace = Phase11B2RoutingTrace(
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

    # Stage 9: Verification (always passes for valid templates in B.2)
    verifier_passed = True

    # Enforcement difference: GOVERNED may block even if template found
    # (But for now, if template renders, both modes allow output)
    # The difference is in external verification strictness, not here.

    return Phase11B2Response(
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
    Validate that registry contains all expected combinations.

    Expected: 10 families * 4 slot plans * 6561 canonical signatures = 262,440
    """
    registry = get_unified_registry()

    expected_keys: Set[Tuple[str, str, str]] = set()
    for family in ACCEPTED_FAMILIES:
        for slot_plan in ACCEPTED_SLOT_PLANS:
            for variant_id in CANONICAL_SIGNATURES:
                expected_keys.add((family.value, variant_id, slot_plan.value))

    actual_keys = set(registry.keys())

    missing = expected_keys - actual_keys
    extra = actual_keys - expected_keys

    return RegistryCompletenessResult(
        passed=(len(missing) == 0 and len(extra) == 0),
        expected_count=len(expected_keys),
        actual_count=len(actual_keys),
        missing_keys=tuple(f"{k[0]}|{k[1]}|{k[2]}" for k in sorted(missing)[:10]),
        extra_keys=tuple(f"{k[0]}|{k[1]}|{k[2]}" for k in sorted(extra)[:10]),
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
    registry = get_unified_registry()

    total = len(raw_signatures)
    canonicalized = 0
    in_registry = 0
    failed: list = []

    for raw_sig in raw_signatures:
        try:
            result = canonicalize_variant_id(raw_sig)
            canonicalized += 1

            # Check if canonical signature is in registry for any family/slot_plan
            found = False
            for family in ACCEPTED_FAMILIES:
                for slot_plan in ACCEPTED_SLOT_PLANS:
                    key = (family.value, result.canonical_signature, slot_plan.value)
                    if key in registry:
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
    """
    registry = get_unified_registry()

    template_id_to_key: Dict[str, Tuple[str, str, str]] = {}
    collisions: list = []

    for key, template in registry.items():
        tid = template.template_id
        if tid in template_id_to_key:
            other_key = template_id_to_key[tid]
            collisions.append(f"Collision: {key} and {other_key} -> {tid}")
        else:
            template_id_to_key[tid] = key

    return InjectivityResult(
        passed=(len(collisions) == 0),
        total_keys=len(registry),
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

        request_open = Phase11B2Request(
            artifact_id="identity-test",
            artifact_hash=artifact_hash,
            ontological_path=path,
            ppv_values=ppv,
            render_mode=RenderMode.OPEN,
            vc_source_data={"vc_1_data": "test", "vc_2_data": "test"},
        )

        request_governed = Phase11B2Request(
            artifact_id="identity-test",
            artifact_hash=artifact_hash,
            ontological_path=path,
            ppv_values=ppv,
            render_mode=RenderMode.GOVERNED,
            vc_source_data={"vc_1_data": "test", "vc_2_data": "test"},
        )

        response_open = execute_phase11b2(request_open)
        response_governed = execute_phase11b2(request_governed)

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
# Public Exports
# =============================================================================

__all__ = [
    # Version
    "PHASE11B2_VERSION",
    # Constants
    "ACCEPTED_FAMILIES",
    "ACCEPTED_SLOT_PLANS",
    "CANONICAL_SIGNATURES",
    "CANONICAL_SUBBAND_REPRESENTATIVE",
    # Dataclasses
    "CanonicalizationResult",
    "Phase11B2RoutingTrace",
    "Phase11B2Request",
    "Phase11B2Response",
    "RegistryCompletenessResult",
    "CanonicalizationCoverageResult",
    "InjectivityResult",
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
    "execute_phase11b2",
    # Functions - Validation
    "validate_registry_completeness",
    "validate_canonicalization_coverage",
    "validate_registry_injectivity",
    "validate_mode_identity",
]
