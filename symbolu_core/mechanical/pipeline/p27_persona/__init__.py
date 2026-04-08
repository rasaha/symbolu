"""
P27 Persona Selection Phase
============================

Formal phase wrapper for Persona Engine within the
Delivery Adaptation Band (P27-P31).

Phase Authority: MEDIUM
Band Position: P27 (First in Delivery Adaptation Band)

Usage:
    from symbolu_core.mechanical.pipeline.p27_persona import (
        maybe_run_p27,
        get_p27_output,
        get_p27_persona_id,
    )

    # In orchestrator
    p27_result = maybe_run_p27(ctx)
    if p27_result:
        ctx.p27_persona = p27_result
"""

from .p27_persona_schema import (
    VERSION,
    P27Authority,
    PersonaSelectionMode,
    PersonaCategory,
    P27SelectionSignals,
    P27PersonaDirectives,
    P27Output,
)

from .p27_integration import (
    get_persona_engine,
    get_persona_selector,
    extract_p27_signals,
    run_p27_selection,
    maybe_run_p27,
    get_p27_output,
    get_p27_persona_id,
)

__version__ = VERSION
__all__ = [
    # Schema
    "VERSION",
    "P27Authority",
    "PersonaSelectionMode",
    "PersonaCategory",
    "P27SelectionSignals",
    "P27PersonaDirectives",
    "P27Output",
    # Integration
    "get_persona_engine",
    "get_persona_selector",
    "extract_p27_signals",
    "run_p27_selection",
    "maybe_run_p27",
    "get_p27_output",
    "get_p27_persona_id",
]
