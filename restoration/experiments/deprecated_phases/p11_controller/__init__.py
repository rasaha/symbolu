"""
P11 Controller - Phase-11 OPEN/GOVERNED Binary Execution Switch
================================================================

This module provides the Phase-11 Controller, the first controlled
generative surface in Symbol-U.

The Phase-11 Controller provides:
    - Fully wired execution pipeline
    - Full observability via ledger recording
    - Optional enforcement via RenderMode (OPEN vs GOVERNED)
    - Impossible for "unsafe" generation to leak silently

RenderMode Controls:
    OPEN:
        - For experimentation, marketing, exploration
        - Output is released even if verifier fails
        - Verifier STILL RUNS (always observable)
        - Ledger STILL RECORDS (always auditable)

    GOVERNED:
        - For production, compliance, safety
        - Output is BLOCKED if verifier fails
        - Fail-closed behavior
        - No unsafe output can escape

Usage:
    from symbolu.mechanical.pipeline.p11_controller import (
        Phase11Controller,
        Phase11Request,
        Phase11Response,
        Phase10Result,
        RenderMode,
        create_governed_request,
        create_open_request,
    )

    # Create Phase10Result (opaque upstream data)
    phase10_result = Phase10Result(
        artifact_hash="...",
        vc_facts=("VC-1", "VC-2"),
        acoustic_regime="neutral",
        source_data={"vc_1_data": "...", "vc_2_data": "..."},
    )

    # Create request (GOVERNED mode for production)
    request = create_governed_request(
        artifact_id="my_artifact",
        artifact_hash="...",
        phase10_result=phase10_result,
    )

    # Execute controller
    controller = Phase11Controller()
    response = controller.execute(request)

    # Check result
    if response.is_blocked():
        print("Output was blocked by verifier")
    else:
        print(f"Output: {response.output_text}")

Hard Safety Boundaries (ALWAYS ENFORCED regardless of RenderMode):
    - NO randomness
    - NO ML/NLP imports
    - NO time/datetime
    - NO mutation of inputs
    - Same input -> byte-identical output
    - Verifier always executes
    - Ledger always records
    - GOVERNED mode is fail-closed
"""

from symbolu.mechanical.pipeline.p11_controller.p11_schema import (
    # Version
    P11_CONTROLLER_VERSION,
    # Enums
    RenderMode,
    # Dataclasses
    Phase10Result,
    Phase11Request,
    Phase11Response,
    # Validation helpers
    validate_render_mode,
    is_open_mode,
    is_governed_mode,
    compute_hash,
)

from symbolu.mechanical.pipeline.p11_controller.p11_templates import (
    # Version
    TEMPLATE_VERSION,
    # Dataclasses
    VCExtraction,
    TemplateRenderResult,
    PPVMetrics,
    VCPPVExtraction,
    # Constants
    EMPTY_PPV_METRICS,
    # Functions
    extract_vc_facts,
    render_template,
    get_approved_template_count,
    is_approved_template_key,
    get_template_version,
    # PPV Functions
    extract_ppv_metrics,
    extract_vc_ppv_facts,
    render_template_with_ppv,
    is_ppv_template_supported,
    get_ppv_template_count,
)

from symbolu.mechanical.pipeline.p11_controller.p11_verifier import (
    # Version
    VERIFIER_VERSION,
    # Dataclasses
    VerificationCheck,
    VerifierReport,
    # Functions
    verify_output,
    verify_output_with_ppv,
    get_verifier_version,
    get_forbidden_vocabulary_count,
    get_max_line_length,
    get_max_output_length,
)

from symbolu.mechanical.pipeline.p11_controller.p11_ledger import (
    # Version
    LEDGER_VERSION,
    # Dataclasses
    Phase11LedgerEntry,
    # Functions
    compute_span_id,
    create_ledger_entry,
    get_ledger_version,
    # Store
    Phase11LedgerStore,
)

from symbolu.mechanical.pipeline.p11_controller.p11_controller import (
    # Version
    CONTROLLER_VERSION,
    # Classes
    Phase11Controller,
    PipelineState,
    # Functions
    run_phase11_controller,
    create_governed_request,
    create_open_request,
)


__all__ = [
    # === Versions ===
    "P11_CONTROLLER_VERSION",
    "CONTROLLER_VERSION",
    "TEMPLATE_VERSION",
    "VERIFIER_VERSION",
    "LEDGER_VERSION",

    # === Core Enums ===
    "RenderMode",

    # === Core Dataclasses ===
    "Phase10Result",
    "Phase11Request",
    "Phase11Response",

    # === Controller ===
    "Phase11Controller",
    "PipelineState",

    # === Template System ===
    "VCExtraction",
    "TemplateRenderResult",
    "extract_vc_facts",
    "render_template",
    "get_approved_template_count",
    "is_approved_template_key",
    "get_template_version",

    # === PPV Template System ===
    "PPVMetrics",
    "VCPPVExtraction",
    "EMPTY_PPV_METRICS",
    "extract_ppv_metrics",
    "extract_vc_ppv_facts",
    "render_template_with_ppv",
    "is_ppv_template_supported",
    "get_ppv_template_count",

    # === Verifier System ===
    "VerificationCheck",
    "VerifierReport",
    "verify_output",
    "verify_output_with_ppv",
    "get_verifier_version",
    "get_forbidden_vocabulary_count",
    "get_max_line_length",
    "get_max_output_length",

    # === Ledger System ===
    "Phase11LedgerEntry",
    "Phase11LedgerStore",
    "compute_span_id",
    "create_ledger_entry",
    "get_ledger_version",

    # === Convenience Functions ===
    "run_phase11_controller",
    "create_governed_request",
    "create_open_request",
    "validate_render_mode",
    "is_open_mode",
    "is_governed_mode",
    "compute_hash",
]
