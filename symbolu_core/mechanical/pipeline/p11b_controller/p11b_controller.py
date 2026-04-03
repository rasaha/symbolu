"""
P11B Controller - Phase-11B Governed Structural Generator
============================================================

This is the Phase-11B Controller, extending Phase-11A with:
    - Ontological path → Template family selection
    - PPV band signature → Variant ID routing
    - Mode → Registry switching (GOVERNED/OPEN)
    - Silent collapse prevention

Phase-11B Pipeline (EXACT, NEVER CHANGED):
    1. Path Extraction - Get ontological family from path[0]
    2. PPV Banding - Convert PPV values to band signature
    3. Template Key Construction - Build (family, variant_id, slot_plan)
    4. Registry Lookup - Get template from appropriate registry
    5. Template Rendering - Fill placeholders with VC data
    6. Verification - Structural verification (ALWAYS runs)
    7. Ledger Recording - ALWAYS record
    8. Commit Rule - Apply OPEN/GOVERNED switch

Hard Invariants (ALWAYS ENFORCED):
    - No randomness (deterministic core)
    - No ML/NLP imports
    - No semantics (no interpretation)
    - No mutation of inputs
    - Same input → byte-identical output (GOVERNED mode)
    - Distinct inputs → distinct template_ids (no silent collapse)
    - Verifier always executes
    - Ledger always records
    - GOVERNED mode is fail-closed

CRITICAL:
    Phase-11B MUST produce different outputs for different structural inputs.
    This is verified by the silent collapse prevention tests.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

from symbolu_core.mechanical.pipeline.p11_controller.p11_schema import (
    Phase10Result,
    RenderMode,
    compute_hash,
)
from symbolu_core.mechanical.pipeline.p11b_controller.p11b_verifier import (
    P11BVerifierReport,
    verify_p11b_output,
)
from symbolu_core.mechanical.pipeline.p11_controller.p11_ledger import (
    Phase11LedgerEntry,
    Phase11LedgerStore,
    create_ledger_entry,
)
from symbolu_core.mechanical.pipeline.p11b_controller.p11b_schema import (
    P11B_VERSION,
    OntologicalFamily,
    PPVBand,
    PPVBandSignature,
    RegistryType,
    SlotPlan,
    TemplateKey,
    Phase11BRequest,
    Phase11BResponse,
    create_ppv_band_signature,
    compute_variant_id,
    get_template_family,
    get_slot_plan_from_ppv,
    create_template_key,
    get_registry_type,
)
from symbolu_core.mechanical.pipeline.p11b_controller.p11b_templates import (
    P11BTemplate,
    P11BRenderResult,
    lookup_template,
    render_template,
)


# =============================================================================
# Controller Version
# =============================================================================

P11B_CONTROLLER_VERSION = P11B_VERSION


# =============================================================================
# Pipeline Stage Results (Internal)
# =============================================================================


@dataclass(frozen=True)
class P11BPipelineState:
    """
    Internal pipeline state tracking for Phase-11B.

    This captures the state after each pipeline stage for observability.
    This is NOT returned to the caller - only Phase11BResponse is.
    """
    # Stage 1: Path Extraction
    ontological_family: Optional[OntologicalFamily] = None

    # Stage 2: PPV Banding
    ppv_band_signature: Optional[PPVBandSignature] = None
    variant_id: Optional[str] = None

    # Stage 3: Template Key Construction
    slot_plan: Optional[SlotPlan] = None
    template_key: Optional[TemplateKey] = None

    # Stage 4: Registry Lookup
    registry_type: Optional[RegistryType] = None
    template: Optional[P11BTemplate] = None

    # Stage 5: Template Rendering
    render_result: Optional[P11BRenderResult] = None

    # Stage 6: Verification
    verifier_report: Optional[P11BVerifierReport] = None

    # Stage 7: Ledger Recording
    ledger_entry: Optional[Phase11LedgerEntry] = None

    # Stage 8: Commit Decision
    output_released: Optional[bool] = None
    final_output: Optional[str] = None


# =============================================================================
# Phase-11B Controller
# =============================================================================


class Phase11BController:
    """
    Phase-11B Controller with governed structural generation.

    This controller:
        - Routes by ontological path to template families
        - Uses PPV bands for variant selection
        - Switches registries based on mode
        - Prevents silent collapse
        - Records everything in the ledger

    Pipeline Order (EXACT):
        1. Path Extraction
        2. PPV Banding
        3. Template Key Construction
        4. Registry Lookup
        5. Template Rendering
        6. Verification
        7. Ledger Recording (ALWAYS)
        8. Commit Rule (the switch)
    """

    def __init__(self, ledger_store: Optional[Phase11LedgerStore] = None) -> None:
        """
        Initialize the Phase-11B Controller.

        Args:
            ledger_store: Optional ledger store. If not provided, a new one
                          is created internally.
        """
        self._ledger_store = ledger_store if ledger_store is not None else Phase11LedgerStore()
        self._version = P11B_CONTROLLER_VERSION

    @property
    def version(self) -> str:
        """Return the controller version."""
        return self._version

    @property
    def ledger_store(self) -> Phase11LedgerStore:
        """Return the ledger store."""
        return self._ledger_store

    def execute(self, request: Phase11BRequest) -> Phase11BResponse:
        """
        Execute the Phase-11B Controller pipeline.

        This method executes the EXACT pipeline in order:
            1. Path Extraction - Get family from path[0]
            2. PPV Banding - Convert values to band signature
            3. Template Key Construction - Build composite key
            4. Registry Lookup - Get template from registry
            5. Template Rendering - Fill placeholders
            6. Verification - Structural checks (ALWAYS runs)
            7. Ledger Recording - ALWAYS records
            8. Commit Rule - Apply OPEN/GOVERNED switch

        Args:
            request: The Phase11BRequest with path, PPV, and mode.

        Returns:
            Phase11BResponse with output and metadata.

        Raises:
            ValueError: If request validation fails (fail-closed).
        """
        # Validate request (fail-closed)
        self._validate_request(request)

        # =====================================================================
        # STAGE 1: Path Extraction
        # =====================================================================
        # Get ontological family from path[0]
        ontological_family = get_template_family(request.ontological_path)

        # =====================================================================
        # STAGE 2: PPV Banding
        # =====================================================================
        # Convert PPV values to band signature
        ppv_band_signature = create_ppv_band_signature(request.ppv_values)
        variant_id = compute_variant_id(ppv_band_signature)

        # =====================================================================
        # STAGE 3: Template Key Construction
        # =====================================================================
        # Build composite key (family, variant_id, slot_plan)
        slot_plan = get_slot_plan_from_ppv(ppv_band_signature)
        template_key = TemplateKey(
            family=ontological_family,
            variant_id=variant_id,
            slot_plan=slot_plan,
        )

        # =====================================================================
        # STAGE 4: Registry Lookup
        # =====================================================================
        # Get registry based on mode
        registry_type = get_registry_type(request.render_mode)

        # Look up template (deterministic)
        template = lookup_template(template_key, registry_type)

        # =====================================================================
        # STAGE 5: Template Rendering
        # =====================================================================
        # Render template with VC data
        render_result = render_template(
            template=template,
            phase10_result=request.phase10_result,
            ppv_band_signature=ppv_band_signature,
        )

        # Compute candidate output hash
        candidate_output_hash = compute_hash(render_result.output_text)

        # =====================================================================
        # STAGE 6: Verification
        # =====================================================================
        # Run Phase-11B verification (ALWAYS)
        verifier_report = verify_p11b_output(render_result)

        # =====================================================================
        # STAGE 7: Ledger Recording (ALWAYS)
        # =====================================================================
        # Determine if output will be released
        if request.render_mode == RenderMode.GOVERNED:
            output_will_be_released = verifier_report.passed
        else:  # OPEN
            output_will_be_released = True

        # Create and record ledger entry
        ledger_entry = create_ledger_entry(
            artifact_id=request.artifact_id,
            artifact_hash=request.artifact_hash,
            candidate_output_hash=candidate_output_hash,
            verifier_report_hash=verifier_report.report_hash,
            render_mode=request.render_mode,
            verifier_passed=verifier_report.passed,
            output_released=output_will_be_released,
        )

        # Append to ledger store
        self._ledger_store.append(ledger_entry)

        # =====================================================================
        # STAGE 8: Commit Rule (THE SWITCH)
        # =====================================================================
        # Binary OPEN/GOVERNED switch
        if request.render_mode == RenderMode.GOVERNED:
            # GOVERNED: fail-closed
            if not verifier_report.passed:
                output_text = "RENDER_BLOCKED"
            else:
                output_text = render_result.output_text
        else:  # OPEN
            # OPEN: release regardless of verifier (but verifier still ran!)
            output_text = render_result.output_text

        # =====================================================================
        # Build Response
        # =====================================================================
        return Phase11BResponse(
            output_text=output_text,
            verifier_passed=verifier_report.passed,
            verifier_report_hash=verifier_report.report_hash,
            candidate_output_hash=candidate_output_hash,
            mode_applied=request.render_mode,
            ledger_span_id=ledger_entry.span_id,
            template_key=template_key,
            template_id=template.template_id,
            registry_used=registry_type,
        )

    def _validate_request(self, request: Phase11BRequest) -> None:
        """
        Validate the Phase11BRequest (fail-closed).

        Args:
            request: The request to validate.

        Raises:
            ValueError: If validation fails.
        """
        if not isinstance(request, Phase11BRequest):
            raise ValueError(
                f"Expected Phase11BRequest, got {type(request).__name__}"
            )

        # Verify render_mode is valid
        if request.render_mode not in (RenderMode.OPEN, RenderMode.GOVERNED):
            raise ValueError(
                f"Invalid render_mode: {request.render_mode}"
            )


# =============================================================================
# Convenience Functions
# =============================================================================


def run_phase11b_controller(
    request: Phase11BRequest,
    ledger_store: Optional[Phase11LedgerStore] = None,
) -> Phase11BResponse:
    """
    Run the Phase-11B Controller pipeline.

    Convenience function that creates a controller and executes the request.

    Args:
        request: The Phase11BRequest.
        ledger_store: Optional ledger store.

    Returns:
        Phase11BResponse with output and metadata.
    """
    controller = Phase11BController(ledger_store=ledger_store)
    return controller.execute(request)


def create_phase11b_governed_request(
    artifact_id: str,
    artifact_hash: str,
    phase10_result: Phase10Result,
    ontological_path: tuple,
    ppv_values: tuple,
    explicit_absolving_opt_in: bool = False,
) -> Phase11BRequest:
    """
    Create a Phase11BRequest with GOVERNED mode (production/safety).

    Args:
        artifact_id: Opaque artifact identifier.
        artifact_hash: Precomputed artifact hash.
        phase10_result: Opaque Phase10Result from upstream.
        ontological_path: Tuple of layer names.
        ppv_values: Tuple of 8 PPV values (0-7).
        explicit_absolving_opt_in: Explicit opt-in for ABSOLVING.

    Returns:
        Phase11BRequest configured for GOVERNED mode.
    """
    return Phase11BRequest(
        artifact_id=artifact_id,
        artifact_hash=artifact_hash,
        phase10_result=phase10_result,
        ontological_path=ontological_path,
        ppv_values=ppv_values,
        render_mode=RenderMode.GOVERNED,
        explicit_absolving_opt_in=explicit_absolving_opt_in,
    )


def create_phase11b_open_request(
    artifact_id: str,
    artifact_hash: str,
    phase10_result: Phase10Result,
    ontological_path: tuple,
    ppv_values: tuple,
    explicit_absolving_opt_in: bool = False,
) -> Phase11BRequest:
    """
    Create a Phase11BRequest with OPEN mode (experimentation).

    Args:
        artifact_id: Opaque artifact identifier.
        artifact_hash: Precomputed artifact hash.
        phase10_result: Opaque Phase10Result from upstream.
        ontological_path: Tuple of layer names.
        ppv_values: Tuple of 8 PPV values (0-7).
        explicit_absolving_opt_in: Explicit opt-in for ABSOLVING.

    Returns:
        Phase11BRequest configured for OPEN mode.
    """
    return Phase11BRequest(
        artifact_id=artifact_id,
        artifact_hash=artifact_hash,
        phase10_result=phase10_result,
        ontological_path=ontological_path,
        ppv_values=ppv_values,
        render_mode=RenderMode.OPEN,
        explicit_absolving_opt_in=explicit_absolving_opt_in,
    )


# =============================================================================
# Differentiation Verification
# =============================================================================


def verify_structural_differentiation(
    request1: Phase11BRequest,
    request2: Phase11BRequest,
    controller: Optional[Phase11BController] = None,
) -> bool:
    """
    Verify that two structurally different requests produce different outputs.

    This is a key invariant of Phase-11B: distinct structural inputs
    MUST NOT collapse to the same output.

    Args:
        request1: First request.
        request2: Second request.
        controller: Optional controller to use.

    Returns:
        True if outputs differ (expected behavior).
        False if outputs are identical (silent collapse - BAD).
    """
    if controller is None:
        controller = Phase11BController()

    response1 = controller.execute(request1)
    response2 = controller.execute(request2)

    # Check template_id differentiation
    template_ids_differ = response1.template_id != response2.template_id

    # Check output hash differentiation
    outputs_differ = response1.candidate_output_hash != response2.candidate_output_hash

    # At least one should differ for structurally distinct inputs
    return template_ids_differ or outputs_differ


def get_differentiation_axes(
    request1: Phase11BRequest,
    request2: Phase11BRequest,
) -> dict:
    """
    Identify which structural axes differ between two requests.

    Args:
        request1: First request.
        request2: Second request.

    Returns:
        Dictionary indicating which axes differ.
    """
    path_differs = request1.ontological_path != request2.ontological_path
    family_differs = (
        get_template_family(request1.ontological_path) !=
        get_template_family(request2.ontological_path)
    )

    sig1 = create_ppv_band_signature(request1.ppv_values)
    sig2 = create_ppv_band_signature(request2.ppv_values)
    ppv_signature_differs = sig1.as_string() != sig2.as_string()

    slot_plan_differs = (
        get_slot_plan_from_ppv(sig1) !=
        get_slot_plan_from_ppv(sig2)
    )

    mode_differs = request1.render_mode != request2.render_mode

    return {
        "ontological_path": path_differs,
        "ontological_family": family_differs,
        "ppv_band_signature": ppv_signature_differs,
        "slot_plan": slot_plan_differs,
        "render_mode": mode_differs,
    }


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Version
    "P11B_CONTROLLER_VERSION",
    # Classes
    "Phase11BController",
    "P11BPipelineState",
    # Functions
    "run_phase11b_controller",
    "create_phase11b_governed_request",
    "create_phase11b_open_request",
    "verify_structural_differentiation",
    "get_differentiation_axes",
]
