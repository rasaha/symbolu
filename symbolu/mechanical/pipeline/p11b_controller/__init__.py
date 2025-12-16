"""
Phase-11B Controller Package
=============================

Phase-11B is the governed structural generator that fixes Phase-11A's issues:

Problems Fixed:
    - Raw parameter encoding → PPV banding system (LOW/MID/HIGH per dimension)
    - PPV aggregate collapse → Vector-valued structural routing
    - Unused ontological path → Template family selection from path[0]
    - Mode producing no differentiation → Registry switching (GOVERNED/OPEN)
    - Silent collapse → Registry completeness validation

Key Components:
    - p11b_schema: Types for Phase-11B (OntologicalFamily, PPVBand, TemplateKey)
    - p11b_templates: Template registry with (family, variant_id, slot_plan) keys
    - p11b_controller: Pipeline controller with 8-stage execution

Design Principles:
    - Ontological path[0] → Template family
    - PPV dimensions → Band signatures (3 bands × 8 dimensions)
    - Band signature → Variant ID (unique for each combination)
    - Mode → Registry selection (GOVERNED subset of OPEN)
    - Template key: (family, variant_id, slot_plan) → unique template_id

Hard Constraints (NON-NEGOTIABLE):
    - No semantics (no interpretation, no NLP, no embeddings)
    - No learning (no training, no weights)
    - Deterministic core (same input → identical output in GOVERNED)
    - No silent collapse (distinct inputs → distinct templates)

Usage:
    from symbolu.mechanical.pipeline.p11b_controller import (
        Phase11BController,
        Phase11BRequest,
        Phase11BResponse,
        create_phase11b_governed_request,
        create_phase11b_open_request,
    )

    # Create request
    request = create_phase11b_governed_request(
        artifact_id="artifact-001",
        artifact_hash="a" * 64,
        phase10_result=phase10_result,
        ontological_path=("THINKING", "DIRECTING"),
        ppv_values=(3, 4, 5, 2, 3, 4, 5, 6),
    )

    # Execute
    controller = Phase11BController()
    response = controller.execute(request)

    # Check results
    print(response.template_id)     # Unique template identifier
    print(response.template_key)    # (family, variant_id, slot_plan)
    print(response.registry_used)   # GOVERNED or OPEN
    print(response.output_text)     # Rendered output
"""

from symbolu.mechanical.pipeline.p11b_controller.p11b_schema import (
    # Version
    P11B_VERSION,
    # Constants
    PPV_DIM_COUNT,
    PPV_DIM_NAMES,
    PPV_BAND_LOW_MAX,
    PPV_BAND_MID_MAX,
    PPV_BAND_HIGH_MAX,
    LAYER_TO_FAMILY,
    SLOT_PLAN_VC_FACTS,
    # Enums
    OntologicalFamily,
    PPVBand,
    SlotPlan,
    RegistryType,
    # Dataclasses
    PPVBandSignature,
    TemplateKey,
    Phase11BRequest,
    Phase11BResponse,
    # Functions
    get_template_family,
    get_ppv_band,
    create_ppv_band_signature,
    compute_variant_id,
    get_slot_plan_from_ppv,
    create_template_key,
    get_registry_type,
)

from symbolu.mechanical.pipeline.p11b_controller.p11b_templates import (
    # Version
    P11B_TEMPLATE_VERSION,
    # Dataclasses
    P11BTemplate,
    P11BRenderResult,
    CollapseValidationResult,
    # Functions
    generate_template_id,
    build_template_string,
    get_registry,
    lookup_template,
    extract_vc_data,
    render_template,
    validate_no_silent_collapse,
    validate_registry_completeness,
    get_registry_stats,
)

from symbolu.mechanical.pipeline.p11b_controller.p11b_controller import (
    # Version
    P11B_CONTROLLER_VERSION,
    # Classes
    Phase11BController,
    P11BPipelineState,
    # Functions
    run_phase11b_controller,
    create_phase11b_governed_request,
    create_phase11b_open_request,
    verify_structural_differentiation,
    get_differentiation_axes,
)


__all__ = [
    # Versions
    "P11B_VERSION",
    "P11B_TEMPLATE_VERSION",
    "P11B_CONTROLLER_VERSION",
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
    # Schema Dataclasses
    "PPVBandSignature",
    "TemplateKey",
    "Phase11BRequest",
    "Phase11BResponse",
    # Template Dataclasses
    "P11BTemplate",
    "P11BRenderResult",
    "CollapseValidationResult",
    # Controller Classes
    "Phase11BController",
    "P11BPipelineState",
    # Schema Functions
    "get_template_family",
    "get_ppv_band",
    "create_ppv_band_signature",
    "compute_variant_id",
    "get_slot_plan_from_ppv",
    "create_template_key",
    "get_registry_type",
    # Template Functions
    "generate_template_id",
    "build_template_string",
    "get_registry",
    "lookup_template",
    "extract_vc_data",
    "render_template",
    "validate_no_silent_collapse",
    "validate_registry_completeness",
    "get_registry_stats",
    # Controller Functions
    "run_phase11b_controller",
    "create_phase11b_governed_request",
    "create_phase11b_open_request",
    "verify_structural_differentiation",
    "get_differentiation_axes",
]
