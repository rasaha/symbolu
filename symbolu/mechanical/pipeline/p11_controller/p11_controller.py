"""
P11 Controller - Phase-11 OPEN/GOVERNED Binary Execution Switch
================================================================

This is the Phase-11 Controller, the first controlled generative surface.

The controller:
    - Always runs the same internal steps
    - Decides at the very end whether output is released or blocked
    - Makes it impossible for "unsafe" generation to leak silently
    - Records everything in the ledger

Pipeline Order (EXACT, NEVER CHANGED):
    1. VC Extractor - Extract ONLY allowed VC facts (VC-1 through VC-5)
    2. Template Renderer - Produce candidate_output_text (deterministic)
    3. Verifier - Line-by-line structural verification
    4. Ledger Recording - ALWAYS record (even in OPEN mode)
    5. Commit Rule - The OPEN/GOVERNED switch (final step)

Hard Invariants (ALWAYS ENFORCED):
    - No randomness
    - No ML/NLP imports
    - No time/datetime
    - No mutation of inputs
    - Same input -> byte-identical output
    - Verifier always executes
    - Ledger always records
    - GOVERNED mode is fail-closed

CRITICAL:
    Even in OPEN mode, the verifier MUST still run.
    It just does not block.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

from symbolu.mechanical.pipeline.p11_controller.p11_schema import (
    P11_CONTROLLER_VERSION,
    Phase10Result,
    Phase11Request,
    Phase11Response,
    RenderMode,
    compute_hash,
)
from symbolu.mechanical.pipeline.p11_controller.p11_templates import (
    VCExtraction,
    TemplateRenderResult,
    extract_vc_facts,
    render_template,
)
from symbolu.mechanical.pipeline.p11_controller.p11_verifier import (
    VerifierReport,
    verify_output,
)
from symbolu.mechanical.pipeline.p11_controller.p11_ledger import (
    Phase11LedgerEntry,
    Phase11LedgerStore,
    create_ledger_entry,
)


# =============================================================================
# Controller Version
# =============================================================================

CONTROLLER_VERSION = P11_CONTROLLER_VERSION


# =============================================================================
# Pipeline Stage Results (Internal)
# =============================================================================


@dataclass(frozen=True)
class PipelineState:
    """
    Internal pipeline state tracking.

    This captures the state after each pipeline stage for observability.
    This is NOT returned to the caller - only Phase11Response is.
    """
    # Stage 1: VC Extraction
    vc_extraction: Optional[VCExtraction] = None

    # Stage 2: Template Rendering
    render_result: Optional[TemplateRenderResult] = None

    # Stage 3: Verification
    verifier_report: Optional[VerifierReport] = None

    # Stage 4: Ledger Recording
    ledger_entry: Optional[Phase11LedgerEntry] = None

    # Stage 5: Commit Decision
    output_released: Optional[bool] = None
    final_output: Optional[str] = None


# =============================================================================
# Phase-11 Controller
# =============================================================================


class Phase11Controller:
    """
    Phase-11 Controller with OPEN/GOVERNED binary execution switch.

    This controller:
        - Always runs the SAME internal steps
        - Decides at the very end whether output is released or blocked
        - Makes it impossible for "unsafe" generation to leak silently
        - Records everything in the ledger

    Pipeline Order (EXACT):
        1. VC Extractor
        2. Template Renderer
        3. Verifier
        4. Ledger Recording (ALWAYS)
        5. Commit Rule (the switch)
    """

    def __init__(self, ledger_store: Optional[Phase11LedgerStore] = None) -> None:
        """
        Initialize the Phase-11 Controller.

        Args:
            ledger_store: Optional ledger store. If not provided, a new one
                          is created internally.
        """
        self._ledger_store = ledger_store if ledger_store is not None else Phase11LedgerStore()
        self._version = CONTROLLER_VERSION

    @property
    def version(self) -> str:
        """Return the controller version."""
        return self._version

    @property
    def ledger_store(self) -> Phase11LedgerStore:
        """Return the ledger store."""
        return self._ledger_store

    def execute(self, request: Phase11Request) -> Phase11Response:
        """
        Execute the Phase-11 Controller pipeline.

        This method executes the EXACT pipeline in order:
            1. VC Extractor - Extract ONLY allowed VC facts
            2. Template Renderer - Produce candidate output (deterministic)
            3. Verifier - Structural verification (ALWAYS runs)
            4. Ledger Recording - ALWAYS records
            5. Commit Rule - Apply OPEN/GOVERNED switch

        Args:
            request: The Phase11Request containing artifact and render mode.

        Returns:
            Phase11Response with output (or "RENDER_BLOCKED") and metadata.

        Raises:
            ValueError: If request validation fails (fail-closed).
        """
        # Validate request (fail-closed)
        self._validate_request(request)

        # =====================================================================
        # STAGE 1: VC Extraction
        # =====================================================================
        # Extract ONLY allowed VC facts (VC-1 through VC-5)
        # No text interpretation, no scoring
        vc_extraction = extract_vc_facts(request.phase10_result)

        # =====================================================================
        # STAGE 2: Template Rendering
        # =====================================================================
        # Produce candidate_output_text
        # Must be deterministic, must only use approved templates
        render_result = render_template(
            vc_extraction=vc_extraction,
            acoustic_regime=request.phase10_result.acoustic_regime,
        )

        # Compute candidate output hash
        candidate_output_hash = compute_hash(render_result.output_text)

        # =====================================================================
        # STAGE 3: Verification
        # =====================================================================
        # Line-by-line structural verification
        # Forbidden vocabulary scan
        # Template shape enforcement
        # IMPORTANT: Verifier ALWAYS runs, even in OPEN mode
        verifier_report = verify_output(render_result)

        # =====================================================================
        # STAGE 4: Ledger Recording (ALWAYS)
        # =====================================================================
        # Determine if output will be released (for ledger)
        # This is the pre-commit calculation
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
        # STAGE 5: Commit Rule (THE SWITCH)
        # =====================================================================
        # This is the binary OPEN/GOVERNED switch
        # It determines final output based on mode and verifier result
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
        return Phase11Response(
            output_text=output_text,
            verifier_passed=verifier_report.passed,
            verifier_report_hash=verifier_report.report_hash,
            candidate_output_hash=candidate_output_hash,
            mode_applied=request.render_mode,
            ledger_span_id=ledger_entry.span_id,
        )

    def _validate_request(self, request: Phase11Request) -> None:
        """
        Validate the Phase11Request (fail-closed).

        Args:
            request: The request to validate.

        Raises:
            ValueError: If validation fails.
        """
        # Request should already be validated by dataclass __post_init__
        # This is an additional safety check

        if not isinstance(request, Phase11Request):
            raise ValueError(
                f"Expected Phase11Request, got {type(request).__name__}"
            )

        # Verify render_mode is valid
        if request.render_mode not in (RenderMode.OPEN, RenderMode.GOVERNED):
            raise ValueError(
                f"Invalid render_mode: {request.render_mode}"
            )


# =============================================================================
# Convenience Functions
# =============================================================================


def run_phase11_controller(
    request: Phase11Request,
    ledger_store: Optional[Phase11LedgerStore] = None,
) -> Phase11Response:
    """
    Run the Phase-11 Controller pipeline.

    Convenience function that creates a controller and executes the request.

    Args:
        request: The Phase11Request.
        ledger_store: Optional ledger store.

    Returns:
        Phase11Response with output and metadata.
    """
    controller = Phase11Controller(ledger_store=ledger_store)
    return controller.execute(request)


def create_governed_request(
    artifact_id: str,
    artifact_hash: str,
    phase10_result: Phase10Result,
    explicit_absolving_opt_in: bool = False,
) -> Phase11Request:
    """
    Create a Phase11Request with GOVERNED mode (production/safety).

    Args:
        artifact_id: Opaque artifact identifier.
        artifact_hash: Precomputed artifact hash.
        phase10_result: Opaque Phase10Result from upstream.
        explicit_absolving_opt_in: Explicit opt-in for ABSOLVING.

    Returns:
        Phase11Request configured for GOVERNED mode.
    """
    return Phase11Request(
        artifact_id=artifact_id,
        artifact_hash=artifact_hash,
        phase10_result=phase10_result,
        render_mode=RenderMode.GOVERNED,
        explicit_absolving_opt_in=explicit_absolving_opt_in,
    )


def create_open_request(
    artifact_id: str,
    artifact_hash: str,
    phase10_result: Phase10Result,
    explicit_absolving_opt_in: bool = False,
) -> Phase11Request:
    """
    Create a Phase11Request with OPEN mode (experimentation).

    Args:
        artifact_id: Opaque artifact identifier.
        artifact_hash: Precomputed artifact hash.
        phase10_result: Opaque Phase10Result from upstream.
        explicit_absolving_opt_in: Explicit opt-in for ABSOLVING.

    Returns:
        Phase11Request configured for OPEN mode.
    """
    return Phase11Request(
        artifact_id=artifact_id,
        artifact_hash=artifact_hash,
        phase10_result=phase10_result,
        render_mode=RenderMode.OPEN,
        explicit_absolving_opt_in=explicit_absolving_opt_in,
    )


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Version
    "CONTROLLER_VERSION",
    # Classes
    "Phase11Controller",
    "PipelineState",
    # Functions
    "run_phase11_controller",
    "create_governed_request",
    "create_open_request",
]
